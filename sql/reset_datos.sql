-- =====================================================================
-- resetear_datos_comercio: puesta a cero de datos de prueba (TRANSACCIONAL)
--
-- Requiere haber ejecutado antes sql/usuarios_auth.sql (usa verificar_login).
-- caja_chica.sql y fidelidad_puntos.sql son opcionales: si no se corrieron, sus tablas /
-- columnas simplemente no se tocan.
--
-- Modos:
--   'movimientos' -> borra ventas, detalle_ventas, movimientos_cuenta (y, si existen con
--                    columna comercio_id: movimientos_caja, arqueos, arqueo_caja, cierres_caja)
--                    y pone en 0 el saldo_deudor y los puntos de los clientes (los puntos
--                    salen de las ventas que se borran). CONSERVA productos, categorías y clientes.
--   'total'       -> lo anterior + productos, categorías y clientes.
--                    CONSERVA comercios (configuración) y usuarios.
--
-- Seguridad:
--   * La función es invocable con la API key de la app, por eso EXIGE el PIN de un usuario
--     'admin' del mismo comercio (se valida con verificar_login, que tiene bloqueo
--     anti fuerza bruta). Sin PIN de Dueño válido no borra nada.
--   * Solo se usa DELETE con WHERE comercio_id (nunca TRUNCATE: afectaría a otros comercios).
--   * Todo ocurre en una sola transacción: si algo falla, no se borra NADA.
--   * Un PIN incorrecto NO lanza excepción (devuelve ok=false): si lo hiciera, el rollback
--     desharía el contador de intentos y se podría adivinar el PIN sin bloqueo.
--   * Los contadores de ID NO se reinician: con varios comercios en la misma base, volver
--     a 1 podía chocar con ventas de otro comercio todavía sin confirmar (clave duplicada).
--   * Toma pg_advisory_xact_lock('control_stock.comercio', comercio_id), el mismo lock que registrar_venta_atomica:
--     una venta del comercio no puede quedar a medio registrar durante el reset.
--
-- Devuelve jsonb: { ok: true, modo, detalle_ventas, movimientos_cuenta, ventas,
--                   [movimientos_caja, arqueos, arqueo_caja, cierres_caja: si existen],
--                   saldos_reseteados | productos, categorias, clientes }
--              o: { ok: false, motivo: 'modo_invalido' | 'no_autorizado' | 'pin_incorrecto'
--                                      | 'bloqueado' | 'usuario_invalido', ... }
-- =====================================================================

create or replace function public.resetear_datos_comercio(
    p_comercio_id bigint,
    p_modo        text,
    p_usuario_id  bigint,
    p_pin         text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_login    jsonb;
    v_n        bigint;
    v_res      jsonb;
    v_t        text;
    -- Tablas opcionales de caja/arqueo: las crean otros scripts (o no existen)
    v_opcionales constant text[] := array['movimientos_caja', 'arqueos', 'arqueo_caja', 'cierres_caja'];
begin
    if p_modo is null or p_modo not in ('movimientos', 'total') then
        return jsonb_build_object('ok', false, 'motivo', 'modo_invalido');
    end if;

    -- ---------- Autorización: PIN de un Dueño ----------
    v_login := public.verificar_login(p_usuario_id, p_pin);
    if not coalesce((v_login ->> 'ok')::boolean, false) then
        return jsonb_build_object('ok', false, 'motivo', coalesce(v_login ->> 'motivo', 'pin_incorrecto'))
               || (v_login - 'ok' - 'motivo');
    end if;
    if (v_login -> 'usuario' ->> 'rol') is distinct from 'admin'
       or (v_login -> 'usuario' ->> 'comercio_id')::bigint is distinct from p_comercio_id then
        return jsonb_build_object('ok', false, 'motivo', 'no_autorizado');
    end if;

    v_res := jsonb_build_object('ok', true, 'modo', p_modo);

    -- Un reset por comercio a la vez y sin ventas del comercio a medio registrar
    perform pg_advisory_xact_lock(hashtext('control_stock.comercio'), p_comercio_id::int);

    -- ---------- Movimientos (orden respetando claves foráneas) ----------
    delete from detalle_ventas
     where venta_id in (select id from ventas where comercio_id = p_comercio_id);
    get diagnostics v_n = row_count;
    v_res := v_res || jsonb_build_object('detalle_ventas', v_n);

    delete from movimientos_cuenta where comercio_id = p_comercio_id;
    get diagnostics v_n = row_count;
    v_res := v_res || jsonb_build_object('movimientos_cuenta', v_n);

    foreach v_t in array v_opcionales loop
        if exists (
            select 1 from information_schema.columns
             where table_schema = 'public' and table_name = v_t and column_name = 'comercio_id'
        ) then
            execute format('delete from public.%I where comercio_id = $1', v_t) using p_comercio_id;
            get diagnostics v_n = row_count;
            v_res := v_res || jsonb_build_object(v_t, v_n);
        end if;
    end loop;

    delete from ventas where comercio_id = p_comercio_id;
    get diagnostics v_n = row_count;
    v_res := v_res || jsonb_build_object('ventas', v_n);

    -- ---------- Según el modo ----------
    if p_modo = 'movimientos' then
        if exists (
            select 1 from information_schema.columns
             where table_schema = 'public' and table_name = 'clientes' and column_name = 'puntos'
        ) then
            update clientes set saldo_deudor = 0, puntos = 0
             where comercio_id = p_comercio_id and (coalesce(saldo_deudor, 0) <> 0 or coalesce(puntos, 0) <> 0);
        else
            update clientes set saldo_deudor = 0
             where comercio_id = p_comercio_id and coalesce(saldo_deudor, 0) <> 0;
        end if;
        get diagnostics v_n = row_count;
        v_res := v_res || jsonb_build_object('saldos_reseteados', v_n);
    else
        delete from productos where comercio_id = p_comercio_id;
        get diagnostics v_n = row_count;
        v_res := v_res || jsonb_build_object('productos', v_n);

        delete from categorias where comercio_id = p_comercio_id;
        get diagnostics v_n = row_count;
        v_res := v_res || jsonb_build_object('categorias', v_n);

        delete from clientes where comercio_id = p_comercio_id;
        get diagnostics v_n = row_count;
        v_res := v_res || jsonb_build_object('clientes', v_n);
    end if;

    return v_res;
end;
$$;

revoke all on function public.resetear_datos_comercio(bigint, text, bigint, text) from public;
grant execute on function public.resetear_datos_comercio(bigint, text, bigint, text)
    to anon, authenticated, service_role;

notify pgrst, 'reload schema';
