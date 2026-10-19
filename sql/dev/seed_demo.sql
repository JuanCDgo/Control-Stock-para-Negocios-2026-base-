-- sql/dev/seed_demo.sql — SOLO entorno local: categorías, productos y clientes de ejemplo para el comercio 1.
-- Correr después de 00_esquema_base.sql y de los scripts de sql/.

insert into public.categorias (id, comercio_id, nombre)
overriding system value
values
    (1, 1, 'Almacén'),
    (2, 1, 'Bebidas'),
    (3, 1, 'Golosinas'),
    (4, 1, 'Limpieza')
on conflict (id) do nothing;

-- stock_actual <= stock_minimo dispara la alerta de reposición (ids 3, 5, 8)
insert into public.productos
    (id, comercio_id, codigo, nombre, categoria_id, precio_costo, margen_ganancia,
     precio_venta, usa_precio_manual, stock_actual, stock_minimo)
overriding system value
values
    (1, 1, '7791234567890', 'Yerba Mate Clásica 500g',        1, 1200.00, 50.00, 1800.00, false, 25,    5),
    (2, 1, '7790070318169', 'Arroz Largo Fino 1kg',           1,  900.00, 40.00, 1260.00, false, 40,   10),
    (3, 1, '7790580120245', 'Aceite de Girasol 900ml',        1, 1700.00, 35.00, 2295.00, false,  3,    6),
    (4, 1, '7799876543210', 'Gaseosa Cola 2.25L',             2, 1500.00, 53.33, 2300.00, true,  18,    6),
    (5, 1, '7798113300107', 'Agua Mineral 1.5L',              2,  450.00, 60.00,  720.00, false,  2,   12),
    (6, 1, '7795555444433', 'Galletitas Rellenas Vainilla 160g', 3, 650.00, 61.54, 1050.00, true,  30,   10),
    (7, 1, '7790580660000', 'Queso Cremoso x kg',             1, 6500.00, 45.00, 9425.00, false,  4.350, 2),
    (8, 1, '7791290012347', 'Lavandina 1L',                   4,  550.00, 50.00,  825.00, false,  0,    4)
on conflict (id) do nothing;

insert into public.clientes (id, comercio_id, nombre, telefono, email, limite_credito, saldo_deudor)
overriding system value
values
    (1, 1, 'María González', '3514123456', 'maria.gonzalez@example.com', 50000.00, 0),
    (2, 1, 'Carlos Pérez',   '3515987654', '',                           20000.00, 0),
    (3, 1, 'Lucía Fernández','',           'lucia.f@example.com',            0.00, 0)
on conflict (id) do nothing;

-- Reajustar los contadores de identidad tras insertar ids explícitos
select setval(pg_get_serial_sequence('public.categorias', 'id'), (select max(id) from public.categorias));
select setval(pg_get_serial_sequence('public.productos',  'id'), (select max(id) from public.productos));
select setval(pg_get_serial_sequence('public.clientes',   'id'), (select max(id) from public.clientes));
