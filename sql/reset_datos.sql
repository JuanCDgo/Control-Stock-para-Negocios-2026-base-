-- =====================================================================
-- resetear_datos_comercio: puesta a cero de datos de prueba (TRANSACCIONAL)
-- NO BORRA NADA: archiva el historial y da de baja el catálogo.
--
-- Requiere haber ejecutado antes sql/00_esquema_base.sql (columnas activo / archivado_en)
-- y sql/usuarios_auth.sql (usa verificar_login).
-- caja_chica.sql y fidelidad_puntos.sql son opcionales: si no se corrieron, sus tablas /
-- columnas simplemente no se tocan.
--
-- Modos:
--   'movimientos' -> archiva ventas (su detalle las sigue), movimientos_cuenta y, si existe,
--                    movimientos_caja (archivado_en = now(), archivado_por = usuario).
--                    Pone en 0 el saldo_deudor y los puntos de los clientes (salen de las
--                    ventas que se archivan). El catálogo queda como está.
--   'total'       -> lo anterior (incluido saldo y puntos en 0) + da de baja productos, categorías y clientes
--                    (activo = false, fecha_baja = now()). Se pueden reactivar desde la app.
--                    CONSERVA comercios (configuración) y usuarios.
--   Lo que ya estaba archivado o dado de baja no se vuelve a tocar.
--
-- Seguridad:
--   * La función es invocable con la API key de la app, por eso EXIGE el PIN de un usuario
--     'admin' del mismo comercio (se valida con verificar_login, que tiene bloqueo
--     anti fuerza bruta). Sin PIN de Dueño válido no cambia nada.
--   * Solo toca filas con WHERE comercio_id.
--   * Todo ocurre en una sola transacción: si algo falla, no cambia NADA.
--   * Un PIN incorrecto NO lanza excepción (devuelve ok=false): si lo hiciera, el rollback
--     desharía el contador de intentos y se podría adivinar el PIN sin bloqueo.
--   * Toma pg_advisory_xact_lock(comercio_id), el mismo lock que registrar_venta_atomica:
--     una venta del comercio no puede quedar a medio registrar durante el reset.
--
-- Devuelve jsonb: { ok: true, modo, ventas, movimientos_cuenta, [movimientos_caja],
--                   saldos_reseteados, [productos, categorias, clientes] }   (filas afectadas)
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
    v_login jsonb;
    v_n     bigint;
    v_res   jsonb;
    v_t     text;
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
    perform pg_advisory_xact_lock(p_comercio_id);

    -- ---------- Historial: se archiva ----------
    foreach v_t in array array['ventas', 'movimientos_cuenta', 'movimientos_caja'] loop
        -- Solo movimientos_caja es opcional (la crea caja_chica.sql). Si a ventas o
        -- movimientos_cuenta les falta archivado_en, el update falla: falta correr 00_esquema_base.sql.
        if v_t <> 'movimientos_caja' or exists (
            select 1 from information_schema.columns
             where table_schema = 'public' and table_name = v_t and column_name = 'archivado_en'
        ) then
            execute format(
                'update public.%I set archivado_en = now(), archivado_por = $2
                  where comercio_id = $1 and archivado_en is null', v_t)
            using p_comercio_id, p_usuario_id;
            get diagnostics v_n = row_count;
            v_res := v_res || jsonb_build_object(v_t, v_n);
        end if;
    end loop;

    -- ---------- Saldo y puntos en 0 (en los dos modos: un cliente de baja no puede quedar con deuda) ----------
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

    -- ---------- Reinicio total: además se da de baja el catálogo ----------
    if p_modo = 'total' then
        foreach v_t in array array['productos', 'categorias', 'clientes'] loop
            execute format(
                'update public.%I set activo = false, fecha_baja = now()
                  where comercio_id = $1 and activo', v_t)
            using p_comercio_id;
            get diagnostics v_n = row_count;
            v_res := v_res || jsonb_build_object(v_t, v_n);
        end loop;
    end if;

    return v_res;
end;
$$;

revoke all on function public.resetear_datos_comercio(bigint, text, bigint, text) from public;
grant execute on function public.resetear_datos_comercio(bigint, text, bigint, text)
    to anon, authenticated, service_role;

notify pgrst, 'reload schema';
