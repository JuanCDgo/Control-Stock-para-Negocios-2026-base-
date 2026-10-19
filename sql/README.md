# Scripts SQL

Correr en el SQL Editor de Supabase (o con `psql`), **en este orden**, sobre un proyecto nuevo:

1. `00_esquema_base.sql` — tablas base, comercio 1 y bucket de fotos `productos`
2. `usuarios_auth.sql` — usuarios, login por PIN
3. `caja_chica.sql` — movimientos de caja
4. `fidelidad_puntos.sql` — puntos de clientes
5. `canje_premios.sql` — productos canjeables por puntos
6. `registrar_venta_atomica.sql` — RPC de venta
7. `reset_datos.sql` — RPC de puesta a cero

Todos se pueden volver a correr sin romper nada (`if not exists` / `create or replace`).

## Solo entorno local (`dev/`)

Para un Supabase local (`npx supabase start`), después de los 7 scripts:

- `dev/seed_demo.sql` — categorías, productos y clientes de ejemplo
- `dev/grants_local.sql` — desactiva RLS y da permisos a `anon` (**no usar en producción**)

Después de cambiar el esquema en local: `notify pgrst, 'reload schema';`
