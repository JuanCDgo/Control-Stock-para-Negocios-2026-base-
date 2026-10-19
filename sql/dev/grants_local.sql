-- sql/dev/grants_local.sql — SOLO entorno local (Supabase CLI). Correr AL FINAL.
-- La app usa la anon key y en el repo no hay políticas RLS para las tablas base, así que en
-- local se desactiva RLS y se dan grants amplios a anon. En un entorno real: activar RLS y
-- escribir políticas por comercio_id en vez de correr este archivo.
alter table public.comercios          disable row level security;
alter table public.categorias         disable row level security;
alter table public.productos          disable row level security;
alter table public.clientes           disable row level security;
alter table public.ventas             disable row level security;
alter table public.detalle_ventas     disable row level security;
alter table public.movimientos_cuenta disable row level security;

grant usage on schema public to anon, authenticated;
grant all on all tables in schema public to anon, authenticated;
grant usage, select on all sequences in schema public to anon, authenticated;

-- usuarios_auth.sql blinda esta tabla (solo se accede por RPC SECURITY DEFINER, el hash
-- del PIN no debe salir de la base). El grant masivo de arriba la habría reabierto.
revoke all on table public.usuarios from anon, authenticated;

notify pgrst, 'reload schema';
