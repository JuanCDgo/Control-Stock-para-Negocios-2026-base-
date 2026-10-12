-- =====================================================================
-- Migración: Canje de Premios por Puntos de Clientes
-- Ejecutar en el SQL Editor de Supabase
-- =====================================================================

alter table public.productos
    add column if not exists puntos_canje integer not null default 0;

notify pgrst, 'reload schema';
