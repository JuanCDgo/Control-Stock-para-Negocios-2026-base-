-- =====================================================================
-- Caja chica: egresos e ingresos manuales de efectivo (tabla movimientos_caja)
--
-- Qué crea:
--   * Tabla public.movimientos_caja  (egresos / ingresos extra de efectivo del cajón)
--   * Índice por (comercio_id, fecha) para el listado diario del Arqueo de Caja
--   * Permisos para que la app (clave anon/authenticated) pueda leer e insertar
--
-- Cómo se usa en la app (Arqueo de Caja / Control Diario):
--   Efectivo esperado en caja = Fondo inicial + Ventas en efectivo
--                             + Cobros de fiados en efectivo + Ingresos extra - Egresos
--
-- Reinicio de datos:
--   La función resetear_datos_comercio (sql/reset_datos.sql) ya vacía esta tabla
--   (DELETE ... WHERE comercio_id) al limpiar movimientos. Volvé a ejecutar
--   sql/reset_datos.sql una vez creada esta tabla para que además reinicie su contador de ID
--   y reporte cuántos movimientos de caja borró.
--
-- Es seguro ejecutarlo más de una vez (idempotente). Ejecutar completo en el editor SQL.
-- NOTA: se asume comercios.id numérico (bigint/int), igual que sql/usuarios_auth.sql.
-- =====================================================================

create table if not exists public.movimientos_caja (
    id              bigint generated always as identity primary key,
    comercio_id     bigint      not null references public.comercios(id),
    tipo            text        not null check (tipo in ('ingreso_extra', 'egreso')),
    monto           numeric(14, 2) not null check (monto > 0),
    concepto        text        not null check (length(btrim(concepto)) > 0),
    usuario_nombre  text,                                   -- quién lo registró (Dueño / Cajero)
    fecha           timestamptz not null default now()
);

create index if not exists movimientos_caja_comercio_fecha_idx
    on public.movimientos_caja (comercio_id, fecha desc);

comment on table  public.movimientos_caja is 'Egresos e ingresos manuales de efectivo (caja chica) por comercio.';
comment on column public.movimientos_caja.tipo is 'ingreso_extra = entra efectivo al cajón; egreso = sale efectivo del cajón.';

-- ---------- Permisos ----------
-- Igual que el resto de las tablas operativas (ventas, clientes, etc.), la app accede con la
-- API key de Supabase. Si en tu proyecto activaste RLS en tus tablas, agregá además políticas
-- de select/insert para esta tabla (con RLS activado y sin políticas, la app no podría usarla).
grant select, insert on public.movimientos_caja to anon, authenticated, service_role;
grant delete on public.movimientos_caja to service_role;
grant usage, select on all sequences in schema public to anon, authenticated, service_role;

notify pgrst, 'reload schema';
