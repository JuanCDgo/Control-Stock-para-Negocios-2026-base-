-- sql/dev/test_auth.sql — prueba de verificar_login / cambiar_pin. SOLO entorno local.
-- Corre dentro de una transacción y termina con ROLLBACK: no deja cambios.
-- Uso: docker exec -i supabase_db_sb psql -U postgres -v ON_ERROR_STOP=1 < sql/dev/test_auth.sql

begin;

insert into public.usuarios (comercio_id, nombre, pin_hash, rol)
values (1, '__test_auth__', extensions.crypt('1234', extensions.gen_salt('bf')), 'cajero');

do $$
declare v_id bigint; r jsonb;
begin
    select id into v_id from public.usuarios where nombre = '__test_auth__';

    -- Entrar con un PIN de ejemplo obliga a cambiarlo
    r := public.verificar_login(v_id, '1234');
    assert (r -> 'usuario' ->> 'debe_cambiar_pin')::boolean, format('con 1234 no pidió cambio: %s', r);

    -- No se puede elegir otro PIN de ejemplo como nuevo
    r := public.cambiar_pin(v_id, '1234', '0000');
    assert r ->> 'motivo' = 'pin_inseguro', format('aceptó 0000 como PIN nuevo: %s', r);

    -- Con un PIN propio ya no lo pide
    r := public.cambiar_pin(v_id, '1234', '5678');
    assert (r ->> 'ok')::boolean, format('no cambió el PIN: %s', r);
    r := public.verificar_login(v_id, '5678');
    assert not (r -> 'usuario' ->> 'debe_cambiar_pin')::boolean, format('con PIN propio pidió cambio: %s', r);
end $$;

\echo 'test_auth: OK'
rollback;
