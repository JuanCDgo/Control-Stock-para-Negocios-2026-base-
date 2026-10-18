-- =====================================================================
-- registrar_venta_atomica
-- Registra una venta de forma ATÓMICA: stock + cabecera + detalle + fiado.
-- Cualquier RAISE EXCEPTION revierte TODO (una función PL/pgSQL se ejecuta
-- dentro de la transacción de la llamada RPC, no deja nada a medias).
--
-- Tablas reales del proyecto: ventas, detalle_ventas, productos, clientes,
-- movimientos_cuenta (las mismas que usa models.py).
--
-- Códigos de error propios (SQLSTATE) que models.py traduce:
--   SV001 -> stock insuficiente
--   SV002 -> error de regla de negocio (dato inválido, límite de crédito, etc.)
--
-- NOTA: se asume que los IDs (comercio, cliente, producto, venta) son bigint.
-- Si alguno es uuid/text, cambiá el tipo en los parámetros y en jsonb_to_recordset.
-- =====================================================================

create or replace function public.registrar_venta_atomica(
    p_comercio_id bigint,
    p_cliente_id  bigint,
    p_metodo_pago text,
    p_total       numeric,
    p_items       jsonb,
    p_puntos_ganados numeric default 0
)
returns bigint
language plpgsql
set search_path = public
as $$
declare
    v_venta_id   bigint;
    v_es_fiado   boolean;
    v_total_calc numeric;
    v_item       record;
    v_prod       record;
    v_cli        record;
begin
    -- Mismo lock que resetear_datos_comercio: una venta no se cruza con un reset del comercio
    perform pg_advisory_xact_lock(p_comercio_id);

    -- ---------- 0. Validaciones de entrada ----------
    if p_items is null or jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items) = 0 then
        raise exception 'El carrito está vacío.' using errcode = 'SV002';
    end if;

    if exists (
        select 1
        from jsonb_to_recordset(p_items)
             as x(producto_id bigint, cantidad numeric, precio_unitario numeric, costo_unitario numeric)
        where x.producto_id is null
           or x.cantidad is null or x.cantidad <= 0
           or x.precio_unitario is null or x.precio_unitario < 0
           or x.costo_unitario is null or x.costo_unitario < 0
    ) then
        raise exception 'Hay un ítem inválido en el carrito (producto, cantidad o precio incorrectos).'
            using errcode = 'SV002';
    end if;

    select coalesce(sum(round(x.cantidad * x.precio_unitario, 2)), 0)
      into v_total_calc
      from jsonb_to_recordset(p_items)
           as x(producto_id bigint, cantidad numeric, precio_unitario numeric, costo_unitario numeric);

    if p_total is null or abs(p_total - v_total_calc) > 0.01 then
        raise exception 'El total informado (%) no coincide con la suma de los renglones (%).',
            p_total, v_total_calc using errcode = 'SV002';
    end if;

    v_es_fiado := coalesce(p_metodo_pago, '') like 'Cuenta Corriente%';
    if v_es_fiado and p_cliente_id is null then
        raise exception 'Para vender a Cuenta Corriente tenés que elegir un cliente.' using errcode = 'SV002';
    end if;

    -- ---------- a) Validar y descontar stock ----------
    -- Se agrupa por producto (puede venir repetido) y se bloquea cada fila con
    -- FOR UPDATE, en orden de id, para evitar carreras y deadlocks entre ventas.
    for v_item in
        select x.producto_id, sum(x.cantidad) as cantidad
          from jsonb_to_recordset(p_items)
               as x(producto_id bigint, cantidad numeric, precio_unitario numeric, costo_unitario numeric)
         group by x.producto_id
         order by x.producto_id
    loop
        select id, nombre, stock_actual
          into v_prod
          from productos
         where id = v_item.producto_id
           and comercio_id = p_comercio_id
           and activo                      -- dado de baja: no se vende aunque esté en un carrito
           for update;

        if not found then
            raise exception 'El producto #% ya no existe en el catálogo.', v_item.producto_id
                using errcode = 'SV002';
        end if;

        if coalesce(v_prod.stock_actual, 0) < v_item.cantidad then
            raise exception '''%'': pediste % y hay % en stock.',
                v_prod.nombre, v_item.cantidad::float8, coalesce(v_prod.stock_actual, 0)::float8
                using errcode = 'SV001';
        end if;

        update productos
           set stock_actual = stock_actual - v_item.cantidad
         where id = v_item.producto_id;
    end loop;

        -- Cliente (solo fiado o fidelidad): se bloquea la fila
    if p_cliente_id is not null then
        select id, nombre, saldo_deudor, limite_credito
          into v_cli
          from clientes
         where id = p_cliente_id
           and comercio_id = p_comercio_id
           and activo                      -- a un cliente dado de baja no se le fía
           for update;

        if not found then
            raise exception 'El cliente seleccionado no existe.' using errcode = 'SV002';
        end if;

        if v_es_fiado and coalesce(v_cli.limite_credito, 0) > 0
           and coalesce(v_cli.saldo_deudor, 0) + p_total > v_cli.limite_credito then
            raise exception '% superaria su limite de credito de $%.',
                v_cli.nombre, to_char(v_cli.limite_credito, 'FM999G999G990D00')
                using errcode = 'SV002';
        end if;
    end if;

    -- ---------- b) Cabecera ----------
    insert into ventas (comercio_id, total_venta, forma_pago, cliente_id, puntos_ganados)
    values (p_comercio_id, p_total, p_metodo_pago,
            p_cliente_id, coalesce(p_puntos_ganados, 0))
    returning id into v_venta_id;

    -- ---------- c) Renglones ----------
    insert into detalle_ventas (venta_id, producto_id, cantidad, precio_unitario, costo_unitario)
    select v_venta_id, x.producto_id, x.cantidad, x.precio_unitario, x.costo_unitario
      from jsonb_to_recordset(p_items)
           as x(producto_id bigint, cantidad numeric, precio_unitario numeric, costo_unitario numeric);

    -- ---------- d) Cuenta corriente y Fidelidad ----------
    if p_cliente_id is not null then
        update clientes
           set saldo_deudor = case when v_es_fiado then round(coalesce(saldo_deudor, 0) + p_total, 2) else saldo_deudor end,
               puntos = round(coalesce(puntos, 0) + coalesce(p_puntos_ganados, 0), 2)
         where id = p_cliente_id;

        if v_es_fiado then
            insert into movimientos_cuenta (comercio_id, cliente_id, tipo, monto, descripcion, ticket_id)
            values (p_comercio_id, p_cliente_id, 'CARGO', p_total,
                    'Compra segun Ticket #' || v_venta_id, v_venta_id);
        end if;
    end if;

    return v_venta_id;
end;
$$;

-- Permisos: solo roles de la API (no PUBLIC). Al ser SECURITY INVOKER, respeta RLS
-- igual que las escrituras directas que hace hoy la app.
revoke all on function public.registrar_venta_atomica(bigint, bigint, text, numeric, jsonb, numeric) from public;
grant execute on function public.registrar_venta_atomica(bigint, bigint, text, numeric, jsonb, numeric)
    to anon, authenticated, service_role;

-- Refresca el cache de esquema de PostgREST para que el RPC este disponible ya
notify pgrst, 'reload schema';
