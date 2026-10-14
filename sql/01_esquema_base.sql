-- =====================================================================
-- resetear_datos_comercio: puesta a cero de datos de prueba (TRANSACCIONAL)
--
-- Requiere haber ejecutado antes sql/usuarios_auth.sql (usa verificar_login).
--
-- Modos:
--   'movimientos' -> borra ventas, detalle_ventas, movimientos_cuenta (y, si existen con
--                    columna comercio_id: movimientos_caja, arqueos, arqueo_caja, cierres_caja)
--                    y pone saldo_deudor = 0. CONSERVA productos, categorías y clientes.
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
--   * Los contadores de ID (tickets, etc.) se reinician a 1 SOLO en tablas que quedaron
--     totalmente vacías (si hay datos de otro comercio, no se tocan).
--
-- Devuelve jsonb: { ok: true, modo, detalle_ventas, movimientos_cuenta, ventas,
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
    v_tablas   text[];
    v_vacia    boolean;
    v_seq      text;
    -- Tablas opcionales de caja/arqueo (hoy el arqueo se calcula desde ventas)
    v_opcionales constant text[] := array['arqueos', 'arqueo_caja', 'cierres_caja'];
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

    -- ---------- Movimientos (orden respetando claves foráneas) ----------
    delete from detalle_ventas
     where venta_id in (select id from ventas where comercio_id = p_comercio_id);
    get diagnostics v_n = row_count;
    v_res := v_res || jsonb_build_object('detalle_ventas', v_n);

    delete from movimientos_cuenta where comercio_id = p_comercio_id;
    get diagnostics v_n = row_count;
    v_res := v_res || jsonb_build_object('movimientos_cuenta', v_n);

    delete from movimientos_caja where comercio_id = p_comercio_id;
    get diagnostics v_n = row_count;
    v_res := v_res || jsonb_build_object('movimientos_caja', v_n);

    delete from ventas where comercio_id = p_comercio_id;
    get diagnostics v_n = row_count;
    v_res := v_res || jsonb_build_object('ventas', v_n);

    foreach v_t in array v_opcionales loop
        if exists (
            select 1 from information_schema.columns
             where table_schema = 'public' and table_name = v_t and column_name = 'comercio_id'
        ) then
            execute format('delete from public.%I where comercio_id = $1', v_t) using p_comercio_id;
        end if;
    end loop;

    -- ---------- Según el modo ----------
    if p_modo = 'movimientos' then
        update clientes set saldo_deudor = 0, puntos = 0
         where comercio_id = p_comercio_id and (coalesce(saldo_deudor, 0) <> 0 or coalesce(puntos, 0) <> 0);
        get diagnostics v_n = row_count;
        v_res := v_res || jsonb_build_object('saldos_reseteados', v_n);

        v_tablas := array['detalle_ventas', 'movimientos_cuenta', 'movimientos_caja', 'ventas'];
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

        v_tablas := array['detalle_ventas', 'movimientos_cuenta', 'movimientos_caja', 'ventas',
                          'productos', 'categorias', 'clientes'];
    end if;

    -- ---------- Reiniciar contadores de ID solo en tablas totalmente vacías ----------
    foreach v_t in array v_tablas loop
        execute format('select not exists (select 1 from public.%I)', v_t) into v_vacia;
        if v_vacia then
            v_seq := pg_get_serial_sequence(format('public.%I', v_t), 'id');
            if v_seq is not null then
                perform setval(v_seq, 1, false);
            end if;
        end if;
    end loop;

    return v_res;
end;
$$;

revoke all on function public.resetear_datos_comercio(bigint, text, bigint, text) from public;
grant execute on function public.resetear_datos_comercio(bigint, text, bigint, text)
    to anon, authenticated, service_role;

notify pgrst, 'reload schema';
