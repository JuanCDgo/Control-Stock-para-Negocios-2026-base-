-- sql/dev/test_venta.sql — prueba de registrar_venta_atomica con registros dados de baja. SOLO local.
-- Corre dentro de una transacción y termina con ROLLBACK: no deja cambios.
-- Uso: docker exec -i supabase_db_sb psql -U postgres -v ON_ERROR_STOP=1 < sql/dev/test_venta.sql

begin;

insert into public.productos (comercio_id, codigo, nombre, precio_venta, stock_actual)
values (1, '__test_venta__', 'Producto test venta', 100, 10);
insert into public.clientes (comercio_id, nombre) values (1, '__cliente_test_venta__');

create temp table _t on commit drop as
select (select id from public.productos where codigo = '__test_venta__') as producto_id,
       (select id from public.clientes where nombre = '__cliente_test_venta__') as cliente_id;

-- ---------- 1. Un producto dado de baja no se vende (aunque haya quedado en un carrito) ----------
do $$
declare v_items jsonb;
begin
    update public.productos set activo = false where id = (select producto_id from _t);
    v_items := jsonb_build_array(jsonb_build_object('producto_id', (select producto_id from _t),
               'cantidad', 1, 'precio_unitario', 100, 'costo_unitario', 50));
    begin
        perform public.registrar_venta_atomica(1, null, 'Efectivo', 100, v_items, 0);
        raise exception 'se vendió un producto dado de baja';
    exception when sqlstate 'SV002' then
        null;  -- esperado: "ya no existe en el catálogo"
    end;
    update public.productos set activo = true where id = (select producto_id from _t);
end $$;

-- ---------- 2. No se fía a un cliente dado de baja ----------
do $$
declare v_items jsonb;
begin
    update public.clientes set activo = false where id = (select cliente_id from _t);
    v_items := jsonb_build_array(jsonb_build_object('producto_id', (select producto_id from _t),
               'cantidad', 1, 'precio_unitario', 100, 'costo_unitario', 50));
    begin
        perform public.registrar_venta_atomica(1, (select cliente_id from _t), 'Cuenta Corriente', 100, v_items, 0);
        raise exception 'se registró una venta a un cliente dado de baja';
    exception when sqlstate 'SV002' then
        null;  -- esperado: "el cliente seleccionado no existe"
    end;
end $$;

\echo 'test_venta: OK'
rollback;
