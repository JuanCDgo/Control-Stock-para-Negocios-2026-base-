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

## Actualizar una base existente

Antes de publicar una versión nueva de la app, volvé a correr **en este orden**:

1. `00_esquema_base.sql` — agrega columnas nuevas (por ejemplo `activo`, `archivado_en`)
2. `caja_chica.sql`
3. `usuarios_auth.sql`, `registrar_venta_atomica.sql` y `reset_datos.sql` — actualizan las funciones

Después: `notify pgrst, 'reload schema';`. Si la app nueva corre contra una base sin actualizar, las pantallas de productos, clientes y arqueo fallan.

## Solo entorno local (`dev/`)

Para un Supabase local (`npx supabase start`), después de los 7 scripts:

- `dev/seed_demo.sql` — categorías, productos y clientes de ejemplo
- `dev/grants_local.sql` — desactiva RLS y da permisos a `anon` (**no usar en producción**)

Después de cambiar el esquema en local: `notify pgrst, 'reload schema';`
