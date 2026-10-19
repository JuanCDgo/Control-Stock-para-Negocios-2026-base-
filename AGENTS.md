# AGENTS.md — Control de Stock para Negocios

Guía para asistentes de IA (y personas) que trabajen en este repo. Leela completa antes de cambiar código.
Qué se hizo y en qué estado quedó cada PR: [docs/HANDOFF-2026-10-18.md](docs/HANDOFF-2026-10-18.md).

## Qué es

POS y gestión para comercios chicos (Argentina): ventas con lector de código de barras, cuenta corriente
("fiado") de clientes, puntos y canje de premios, inventario, caja chica y cierre diario, respaldo JSON.
Multi-comercio por `comercio_id` (hoy la app usa el comercio 1).

- **App:** Python 3.12 + Streamlit **1.66.0** (fijado en `requirements.txt`). Un solo script: `app.py`.
- **Datos:** Supabase (Postgres + PostgREST). La app usa la **anon key**; la lógica sensible vive en
  funciones SQL `security definer` que validan PIN/rol (`sql/*.sql`).
- **Archivos:**
  - `app.py`: pantallas (login, barra superior, POS, Clientes, Productos, Categorías, Caja, Ajustes).
  - `models.py`: acceso a datos y reglas de negocio (`BusinessLogicError` = mensaje para el usuario).
  - `formato.py`: formato argentino de números/fechas. **Usalo siempre** (ver convenciones).
  - `reportes.py`: PDF de ticket y de cierre, textos de WhatsApp, email.
  - `database.py`: cliente de Supabase cacheado (`@st.cache_resource`).
  - `config_manager.py` + `config_negocio.json`: datos del comercio (banco, SMTP, logo).
  - `sql/`: esquema y funciones. Orden de ejecución en `sql/README.md`. `sql/dev/`: solo local (datos demo, permisos, tests SQL).
  - `tests/`: pytest (unitarios + integración contra Supabase local).
  - `.streamlit/config.toml`: tema (colores, tipografías, radios). `secrets.toml` NO se versiona.

## Levantar en local

Requisitos: Docker, Node (para `npx`), Python 3.12.

```bash
# 1) Supabase local (en una carpeta aparte, fuera del repo)
npx supabase init && npx supabase start -x studio,realtime,imgproxy,mailpit,inbucket,edge-runtime,logflare,vector,supavisor,postgres-meta
#    Imprime API_URL (http://127.0.0.1:54321) y ANON_KEY. El contenedor de la base se llama supabase_db_<carpeta>.

# 2) Esquema: correr en orden (ver sql/README.md) y después los de dev/
for f in 00_esquema_base usuarios_auth caja_chica fidelidad_puntos canje_premios registrar_venta_atomica reset_datos dev/seed_demo dev/grants_local; do
  docker exec -i supabase_db_<carpeta> psql -U postgres -v ON_ERROR_STOP=1 -q < sql/$f.sql
done

# 3) Secretos: .streamlit/secrets.toml (ignorado por git)
#    SUPABASE_URL = "http://127.0.0.1:54321"
#    SUPABASE_KEY = "<ANON_KEY>"

# 4) App
pip install -r requirements-dev.txt
streamlit run app.py          # http://localhost:8501 — usuario Dueño, PIN de ejemplo 1234 (pide cambiarlo)
```

## Tests (correr antes de cada commit)

```bash
python -m pytest -q                                    # unitarios + integración (se saltean si no hay Supabase local)
docker exec -i supabase_db_<carpeta> psql -U postgres -v ON_ERROR_STOP=1 -q < sql/dev/test_reset.sql
# idem test_auth.sql, test_formato.sql y (desde el PR #2) test_venta.sql — corren en transacción con ROLLBACK
```

Los tests de integración usan los comercios 9001/9002 en la base local; no tocan el comercio 1.
La UI no tiene tests automáticos: verificala con un navegador en **1366×768, 1024×550 (laptop con escala de
Windows), 820×1180 (tablet) y 390×844 (celular)**. El POS se usa en PC de mostrador, pero se quiere usable en celular.

## Convenciones (respetalas)

**Formato argentino — `formato.py`**
- Montos: `fmt_moneda(x)` → `$ 2.295,00`. Cantidades: `fmt_cantidad` (`1`, `4,35`). Puntos: `fmt_puntos` (con decimales, se ganan con el 1% de la venta). Fechas de la base: `fmt_fecha(iso)` en hora argentina. Tablas: `formatear_df(df, monedas=[...], cantidades=[...])`.
- **`fmt_moneda_md` en todo texto que pasa por markdown** (`st.markdown`, `st.success/error/info/warning`, `st.caption`, `st.toast`, etiquetas de botones/expanders): Streamlit interpreta `$ ... $` como LaTeX y con dos montos en un texto se come los signos. En HTML (`unsafe_allow_html`), `st.metric`, opciones de selectbox, dataframes, PDF y WhatsApp va `fmt_moneda` (sin escape).
- Nunca `f"{x:,.2f}"` ni `f"${x}"`: sale en formato de EE. UU.

**No se borran datos de negocio (desde el PR #2)**
- `productos`, `clientes`, `categorias` tienen `activo` + `fecha_baja`: se usa `models.dar_de_baja(tabla, id)` / `models.reactivar(...)`. `eliminar_*` ya hacen baja lógica.
- `ventas`, `movimientos_cuenta`, `movimientos_caja` tienen `archivado_en` + `archivado_por` (null = vigente). La "Puesta a cero" archiva.
- **Toda consulta nueva de listados filtra** `.eq("activo", True)` o `.is_("archivado_en", "null")`. El respaldo JSON lleva todo.
- Ningún `DELETE` sobre datos de negocio en `models.py` ni en `sql/`.

**SQL**
- Scripts idempotentes (`create table if not exists`, `add column if not exists`, `create or replace`). Una base existente se actualiza volviendo a correr los scripts (ver `sql/README.md`).
- Funciones que modifican datos sensibles validan PIN/rol adentro (`verificar_login`, rol `admin`, mismo `comercio_id`). Un PIN incorrecto devuelve `ok=false`, no lanza excepción (si lanzara, el rollback desharía el contador de intentos).
- Venta y reset toman `pg_advisory_xact_lock(hashtext('control_stock.comercio'), comercio_id)`.
- Mensajes de error con números: `public.fmt_numero_ar(valor, decimales, sin_ceros)`.
- Cada cambio de función lleva su caso en `sql/dev/test_*.sql`.

**UI (Streamlit)**
- Sin barra lateral (desde el PR #3): navegación en la barra superior (`st.segmented_control`), usuario y avisos en `st.popover`/`st.badge`. La barra lateral aplastaba las columnas en pantallas de 800–1100 px.
- Estilo en `.streamlit/config.toml` (tema). CSS propio solo para lo que el tema no cubre; está al principio de `app.py`.
- Íconos `:material/nombre:`; **sin emojis** en ningún texto.
- `width="stretch"` (no `use_container_width`, deprecado).
- Evitá columnas anidadas: Streamlit apila columnas según el ancho de la **ventana** (≤640 px), no del contenedor.
- Acciones lentas con `st.spinner`. Botones ≥44 px (regla global en el CSS).
- Funciones de `models.py` que escriben llevan `@clears_cache`; las que leen, `@st.cache_data(ttl=120)`.

**Idioma:** textos de UI y mensajes en español rioplatense (voseo). Commits en español, descriptivos.

## Cuidados conocidos

- Al cambiar de rama con `streamlit run` corriendo, quedan módulos viejos en memoria (`ImportError`): reiniciar Streamlit.
- `st.markdown` con dos `$` → LaTeX (ver `fmt_moneda_md`).
- El componente de subir archivos de Streamlit no se traduce: sus textos se reemplazan por CSS (busca `stFileUploaderDropzone` en `app.py`).
- Sin RLS en las tablas base y con grants a `anon` en local (`sql/dev/grants_local.sql`). En producción revisar RLS/políticas antes de exponer la anon key.
- pytest muestra 2–4 `DeprecationWarning` de supabase-py (`timeout`/`verify`): son de la librería.
- `st.cache_resource` en `get_connection`: si un test reemplaza `create_client`, tiene que limpiar la caché al terminar (ver `tests/test_database.py`).

## Cómo seguir

1. Leer [docs/HANDOFF-2026-10-18.md](docs/HANDOFF-2026-10-18.md) (estado de los PRs, pasos para publicar, decisiones abiertas).
2. Los planes con el detalle de cada tarea están en `docs/superpowers/plans/`.
3. Antes de un cambio: levantar local, correr los tests, y verificar la UI en los 4 tamaños.
