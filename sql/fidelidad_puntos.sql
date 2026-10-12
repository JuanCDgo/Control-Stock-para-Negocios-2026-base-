-- =====================================================================
-- Programa de Fidelidad / Puntos de Clientes y Canje de Premios
-- =====================================================================

alter table public.clientes
    add column if not exists puntos numeric(10,2) not null default 0;

alter table public.ventas
    add column if not exists puntos_ganados numeric(10,2) not null default 0;

alter table public.productos
    add column if not exists puntos_canje integer not null default 0;

notify pgrst, 'reload schema';
