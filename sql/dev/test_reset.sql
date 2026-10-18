-- sql/dev/test_reset.sql — prueba de resetear_datos_comercio. SOLO entorno local.
-- Corre todo dentro de una transacción y termina con ROLLBACK: no deja cambios.
-- Uso: docker exec -i supabase_db_sb psql -U postgres -v ON_ERROR_STOP=1 < sql/dev/test_reset.sql
-- Si una aserción falla, psql corta con "ERROR: ... assert" y código de salida distinto de 0.

begin;

-- Usuario admin propio del test (PIN 9999), para no depender del PIN de ejemplo
insert into public.usuarios (comercio_id, nombre, pin_hash, rol)
values (1, '__test_reset__', extensions.crypt('9999', extensions.gen_salt('bf')), 'admin');

create temp table _t on commit drop as
select id as usuario_id from public.usuarios where nombre = '__test_reset__';

-- Una venta vigente del comercio 1 para los casos de abajo
insert into public.ventas (comercio_id, total_venta) values (1, 100);

-- ---------- 1. Base sin los scripts opcionales (caja_chica, fidelidad_puntos) ----------
savepoint sin_opcionales;
drop table public.movimientos_caja cascade;
alter table public.clientes drop column puntos cascade;
do $$
declare r jsonb;
begin
    r := public.resetear_datos_comercio(1, 'movimientos', (select usuario_id from _t), '9999');
    assert (r ->> 'ok')::boolean, format('reset sin tablas opcionales devolvió %s', r);
end $$;
rollback to savepoint sin_opcionales;

-- ---------- 1b. Base sin migrar (ventas sin archivado_en): falla, no informa ok sin archivar ----------
savepoint sin_migrar;
alter table public.ventas drop column archivado_en cascade;
do $$
begin
    begin
        perform public.resetear_datos_comercio(1, 'movimientos', (select usuario_id from _t), '9999');
        raise exception 'el reset devolvió ok con ventas sin la columna archivado_en';
    exception when undefined_column then
        null;  -- esperado: hay que correr 00_esquema_base.sql
    end;
end $$;
rollback to savepoint sin_migrar;

-- ---------- 2. 'movimientos' archiva: no borra ninguna venta ----------
savepoint archiva;
do $$
declare r jsonb; v_antes bigint; v_max bigint; v_nuevo bigint; v_vigentes bigint[];
begin
    select count(*), max(id) into v_antes, v_max from public.ventas where comercio_id = 1;
    select array_agg(id) into v_vigentes from public.ventas where comercio_id = 1 and archivado_en is null;
    r := public.resetear_datos_comercio(1, 'movimientos', (select usuario_id from _t), '9999');
    assert (r ->> 'ok')::boolean, format('reset devolvió %s', r);
    assert (select count(*) from public.ventas where comercio_id = 1) = v_antes, 'el reset borró ventas';
    assert not exists (select 1 from public.ventas where comercio_id = 1 and archivado_en is null),
        'quedaron ventas sin archivar';
    -- solo las que estaban vigentes: lo archivado antes conserva su archivado_por
    assert not exists (select 1 from public.ventas where id = any(v_vigentes)
                        and archivado_por is distinct from (select usuario_id from _t)),
        'archivado_por no es el usuario que hizo el reset';
    -- los IDs no se reutilizan
    insert into public.ventas (comercio_id, total_venta) values (1, 50) returning id into v_nuevo;
    assert v_nuevo > v_max, format('la venta nueva reutilizó un id: %s <= %s', v_nuevo, v_max);
end $$;
rollback to savepoint archiva;

-- ---------- 3. Un segundo reset no vuelve a archivar lo ya archivado ----------
savepoint dos_veces;
do $$
declare r jsonb; v_fecha timestamptz;
begin
    r := public.resetear_datos_comercio(1, 'movimientos', (select usuario_id from _t), '9999');
    select max(archivado_en) into v_fecha from public.ventas where comercio_id = 1;
    perform pg_sleep(0.01);
    r := public.resetear_datos_comercio(1, 'movimientos', (select usuario_id from _t), '9999');
    assert (r ->> 'ventas')::int = 0, format('el segundo reset archivó %s ventas', r ->> 'ventas');
    assert (select max(archivado_en) from public.ventas where comercio_id = 1) = v_fecha,
        'el segundo reset pisó archivado_en';
end $$;
rollback to savepoint dos_veces;

-- ---------- 4. 'total' da de baja el catálogo: no borra productos ----------
savepoint total;
do $$
declare r jsonb; v_antes bigint;
begin
    select count(*) into v_antes from public.productos where comercio_id = 1;
    update public.clientes set saldo_deudor = 500, puntos = 10 where comercio_id = 1;
    r := public.resetear_datos_comercio(1, 'total', (select usuario_id from _t), '9999');
    -- un cliente dado de baja no puede quedar con deuda (la regla de eliminar_cliente)
    assert not exists (select 1 from public.clientes where comercio_id = 1 and (saldo_deudor <> 0 or puntos <> 0)),
        'el reinicio total dejó clientes de baja con saldo o puntos';
    assert (r ->> 'ok')::boolean, format('reset total devolvió %s', r);
    assert (select count(*) from public.productos where comercio_id = 1) = v_antes, 'el reset borró productos';
    assert not exists (select 1 from public.productos where comercio_id = 1 and activo), 'quedaron productos activos';
    assert not exists (select 1 from public.clientes where comercio_id = 1 and activo), 'quedaron clientes activos';
    assert not exists (select 1 from public.categorias where comercio_id = 1 and activo), 'quedaron categorías activas';
end $$;
rollback to savepoint total;

-- ---------- 5. Modo movimientos: saldo y puntos de clientes en 0 ----------
do $$
declare r jsonb;
begin
    update public.clientes set saldo_deudor = 500, puntos = 10 where comercio_id = 1;
    r := public.resetear_datos_comercio(1, 'movimientos', (select usuario_id from _t), '9999');
    assert not exists (select 1 from public.clientes where comercio_id = 1 and (saldo_deudor <> 0 or puntos <> 0)),
        'quedaron clientes con saldo o puntos';
end $$;

\echo 'test_reset: OK'
rollback;
