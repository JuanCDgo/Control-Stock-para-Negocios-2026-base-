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

-- cambiar_pin con PIN actual incorrecto cuenta intentos: no sirve para adivinar el PIN sin bloqueo
insert into public.usuarios (comercio_id, nombre, pin_hash, rol)
values (1, '__test_auth_bloqueo__', extensions.crypt('4321', extensions.gen_salt('bf')), 'cajero');
do $$
declare v_id bigint; r jsonb; i int;
begin
    select id into v_id from public.usuarios where nombre = '__test_auth_bloqueo__';
    for i in 1..5 loop
        r := public.cambiar_pin(v_id, '0001', '5678');
    end loop;
    assert r ->> 'motivo' = 'bloqueado', format('5 PIN actuales incorrectos no bloquearon: %s', r);
    r := public.verificar_login(v_id, '4321');
    assert r ->> 'motivo' = 'bloqueado', format('el usuario no quedó bloqueado: %s', r);
end $$;

\echo 'test_auth: OK'
rollback;
