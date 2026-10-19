# Mejoras Control-Stock (bugs, rendimiento, UI escritorio + celular, SQL, seguridad) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corregir los bugs encontrados en la revisión de código, seguridad y UX del 2026-10-18, hacer la app rápida y usable en PC y en celular, y dejar la base de datos reproducible desde el repo.

**Architecture:** Se mantiene Streamlit + Supabase. Cambios chicos y localizados en `app.py`, `reportes.py`, `database.py`, `config_manager.py` y `sql/`. Se suma un módulo `formato.py` (formato es-AR) y una carpeta `tests/` con pytest. La verificación visual se hace con Playwright contra el entorno local (Supabase CLI en Docker + `streamlit run`).

**Tech Stack:** Python 3.12, Streamlit (versión instalada 1.66.0), supabase-py, reportlab, pytest, Postgres 15 (Supabase local), Playwright MCP.

**Spec:** Revisiones de esta sesión (code review `HEAD~2..HEAD`, security review, revisión UX/UI con Playwright). Capturas de referencia: `scratchpad/ux/*.png`.

## Global Constraints

- Uso principal: PC de mostrador con lector de código de barras. Todo cambio de UI se verifica también a 390 px de ancho (criterio del usuario).
- No cambiar de framework (Streamlit se queda).
- Formato argentino: moneda `$ 2.295,00`, cantidades sin ceros sobrantes (`1`, `4,35`), fechas `DD/MM/YYYY`.
- Textos de UI en español rioplatense (voseo), como el resto de la app.
- No tocar datos reales: toda verificación corre contra Supabase local (`http://127.0.0.1:54321`, DB en `127.0.0.1:54322`, contenedor `supabase_db_sb`).
- Nada de dependencias nuevas de runtime. `pytest` va solo en `requirements-dev.txt`.
- Un commit por tarea. No hacer push sin pedido explícito.

## Review Focus

- Ticket con `total_venta` en `None` o ausente → muestra `$ 0,00`, no explota (Task 1).
- Montos negativos, cero y grandes (`-1500`, `0`, `1234567.891`) → `-$ 1.500,00`, `$ 0,00`, `$ 1.234.567,89` (Task 6).
- Cantidad por peso `4.35` vs unidad `1.0` → `4,35` y `1`, nunca `1,000` (Task 6).
- Reset de datos en una base sin `caja_chica.sql` ni `fidelidad_puntos.sql` aplicados → termina `ok`, no `relation does not exist` (Task 9).
- Barra de resumen del carrito con carrito vacío → no se muestra (Task 4).

## Entorno local (precondición de todas las tareas)

- Supabase: `cd <scratchpad>/sb && npx supabase start -x studio,realtime,imgproxy,mailpit,inbucket,edge-runtime,logflare,vector,supavisor,postgres-meta`
- App: `<scratchpad>/venv/Scripts/streamlit.exe run app.py --server.headless true --server.port 8501`
- Login local: usuario Dueño, PIN `1234`.
- Correr SQL: `docker exec -i supabase_db_sb psql -U postgres -d postgres -v ON_ERROR_STOP=1 < archivo.sql`
- Tests: `<scratchpad>/venv/Scripts/python -m pytest -q`

---

## Fase 1 — Bugs que rompen

### Task 1: Infra de tests + total del ticket (PDF y WhatsApp)

**Files:**
- Create: `requirements-dev.txt` (`-r requirements.txt` + `pytest>=8`)
- Create: `tests/conftest.py` (agrega la raíz del repo a `sys.path`)
- Create: `tests/test_reportes.py`
- Modify: `reportes.py:452-453` (PDF), `reportes.py:489` (WhatsApp)

**Interfaces:**
- Produces: `reportes._total_ticket(datos_ticket: dict) -> float` — usa `total_venta`, si es falsy usa `total`, si no `0.0`.

- [ ] **Step 1: Tests que fallan**

```python
from reportes import _total_ticket, armar_mensaje_whatsapp_ticket, generar_pdf_ticket_termico

def test_total_ticket_none_y_ausente():
    assert _total_ticket({"total_venta": None}) == 0.0
    assert _total_ticket({}) == 0.0
    assert _total_ticket({"total": 50}) == 50.0
    assert _total_ticket({"total_venta": 1234.5, "total": 1}) == 1234.5

def test_whatsapp_no_explota_con_total_none():
    assert "Total Abonado" in armar_mensaje_whatsapp_ticket({"total_venta": None})

def test_pdf_ticket_imprime_el_monto():
    pdf = generar_pdf_ticket_termico({"total_venta": 1234.5, "items": []}, "Test")
    assert b"1,234.50" in pdf  # Task 6 cambia esta aserción al formato es-AR
```

- [ ] **Step 2:** `python -m pytest tests/test_reportes.py -q` → FAIL (`_total_ticket` no existe; el PDF no tiene el monto).
- [ ] **Step 3:** Implementar `_total_ticket` y usarlo en los dos lugares. PDF: `Paragraph(f"TOTAL: ${total_venta:,.2f}", total_style)`. Si el PDF sale comprimido y la aserción de bytes no matchea, construir el doc con `SimpleDocTemplate(..., pageCompression=0)` solo en el test vía monkeypatch de `reportlab.rl_config.pageCompression = 0`.
- [ ] **Step 4:** `python -m pytest -q` → PASS.
- [ ] **Step 5:** Commit `fix: el ticket PDF imprime el total y ambos tickets toleran total nulo`.

### Task 2: Scripts SQL rotos o duplicados

**Files:**
- Modify: `sql/registrar_venta_atomica.sql:153` (`$;` → `$$;`)
- Delete: `sql/01_esquema_base.sql` (copia byte a byte de `sql/reset_datos.sql`)
- Delete: `app.py.bak`

- [ ] **Step 1:** Verificar que hoy falla. La base local ya tiene la función (se cargó desde una copia corregida), así que primero: `docker exec supabase_db_sb psql -U postgres -c "drop function public.registrar_venta_atomica(bigint,bigint,text,numeric,jsonb,numeric)"`; después `docker exec -i supabase_db_sb psql -U postgres -v ON_ERROR_STOP=1 < sql/registrar_venta_atomica.sql` → error (delimitador `$$` sin cerrar).
- [ ] **Step 2:** Corregir la línea 153.
- [ ] **Step 3:** Aplicar de nuevo y verificar: `docker exec supabase_db_sb psql -U postgres -tAc "select to_regprocedure('public.registrar_venta_atomica(bigint,bigint,text,numeric,jsonb,numeric)') is not null"` → `t`.
- [ ] **Step 4:** `git rm sql/01_esquema_base.sql app.py.bak`; confirmar con `grep -rn "01_esquema_base" .` → sin resultados.
- [ ] **Step 5:** Commit `fix: cierra el delimitador de registrar_venta_atomica y borra duplicados`.

## Fase 2 — Rendimiento

### Task 3: Un solo cliente de Supabase por proceso

**Files:**
- Modify: `database.py:4` (decorar `get_connection` con `@st.cache_resource`)
- Create: `tests/test_database.py`

**Interfaces:**
- Produces: `database.get_connection() -> Client`, misma firma, ahora cacheada.

- [ ] **Step 1: Medir línea base con Playwright:** ir de POS a "Arqueo de Caja" y anotar el tiempo hasta que desaparece "Stop" (referencia previa: 8,9 s).
- [ ] **Step 2: Test que falla**

```python
def test_get_connection_reutiliza_el_cliente(monkeypatch):
    import database
    llamadas = []
    monkeypatch.setattr(database, "create_client", lambda u, k: llamadas.append(1) or object())
    monkeypatch.setattr(database.st, "secrets", {"SUPABASE_URL": "u", "SUPABASE_KEY": "k"})
    database.get_connection.clear() if hasattr(database.get_connection, "clear") else None
    assert database.get_connection() is database.get_connection()
    assert len(llamadas) == 1
```

- [ ] **Step 3:** `pytest tests/test_database.py -q` → FAIL (`len(llamadas) == 2`).
- [ ] **Step 4:** Agregar `@st.cache_resource`.
- [ ] **Step 5:** `pytest -q` → PASS. Medir otra vez con Playwright; registrar antes/después en el commit.
- [ ] **Step 6:** Commit `perf: reutiliza el cliente de Supabase entre consultas`.

## Fase 3 — UI escritorio + celular

### Task 4: POS — botones de peso, orden del flujo y resumen del carrito

**Files:**
- Modify: `app.py:843-892` (bloque cantidad / agregar)
- Modify: `app.py` cabecera del POS (después del `st.header` del POS, antes del escáner)

**Decisiones:**
- Botones `250 g / 500 g / 1 kg / +1` en grilla 2×2 (dos `st.columns(2)`), no 4 en fila.
- "AGREGAR AL CARRITO" va debajo del campo de cantidad (se elimina `col_btn` y el spacer `height: 38px`).
- Barra de resumen arriba del POS, solo si el carrito tiene ítems: `🛒 {n} ítem(s) · {total} — [Ir a cobrar ↓](#carrito-actual)`. `n = len(carrito)`, `total = sum(subtotal)`. El ancla `#carrito-actual` ya existe (heading "Carrito Actual").

- [ ] **Step 1:** Captura "antes" a 1440 y 390 px (ya existen en `scratchpad/ux/03-pos-carrito.png` y `11-mobile-pos.png`).
- [ ] **Step 2:** Implementar los tres cambios.
- [ ] **Step 3: Verificar con Playwright:**
  - 1440 px: los 4 botones muestran su texto completo (sin `..`); el botón Agregar queda debajo de la cantidad.
  - Carrito vacío: no hay barra de resumen.
  - Agregar 1 ítem: aparece la barra con `1 ítem(s)` y el total; el link baja al carrito.
  - 390 px: la barra se ve sin scroll al entrar al POS.
- [ ] **Step 4:** Commit `feat(pos): grilla de pesos, flujo cantidad→agregar y resumen del carrito`.

### Task 5: Shell de la app — menú, toolbar, CSS chico y sección muerta

**Files:**
- Modify: `app.py:49` → `initial_sidebar_state="auto"`
- Modify: `.streamlit/config.toml` → agregar `[client]` `toolbarMode = "viewer"`
- Modify: `app.py:~200-229` (bloque `<style>` global) → agregar una `@media (max-width: 640px)` que achique `h1` a `1.6rem`, `h2` a `1.3rem`, `h3` a `1.1rem` y el padding de `[data-testid="stMainBlockContainer"]` a `1rem`
- Modify: `app.py:2765-2785` → borrar la sección "Clave de Dueño / Administrador" (su propio caption dice que es heredada y ya no se usa)
- Modify: `app.py:34-38` (imports) y `config_manager.py:54-75` → borrar `validar_clave_admin` y `cambiar_clave_admin`

- [ ] **Step 1:** `grep -rn "validar_clave_admin\|cambiar_clave_admin\|clave_admin" .` → anotar todos los usos antes de borrar; si aparece alguno fuera de los listados, frenar y consultar.
- [ ] **Step 2:** Implementar.
- [ ] **Step 3: Verificar con Playwright:**
  - 1440 px tras login: menú lateral abierto; no aparece el botón "Deploy".
  - 390 px tras login: menú cerrado; el título del POS entra en una línea o dos sin cortar palabras.
  - Configuración: ya no está "Clave de Dueño"; el resto de la página carga sin error.
- [ ] **Step 4:** Commit `feat(ui): menú auto, toolbar de usuario, CSS para celular y fuera la clave heredada`.

### Task 6: Formato argentino (moneda, cantidades, puntos, fechas)

**Files:**
- Create: `formato.py`
- Create: `tests/test_formato.py`
- Modify: `app.py` (48 usos de `:,.2f`), `reportes.py` (16), `models.py` (1)
- Modify: `app.py:2468` → `st.date_input(..., format="DD/MM/YYYY")`
- Modify: `app.py:~867` → `number_input` de cantidad con `format="%g"` (si Streamlit lo rechaza, `"%.3g"`; verificar en pantalla)
- Modify: `tests/test_reportes.py` → la aserción del PDF pasa a `fmt_moneda(1234.5).encode()` (o el texto en latin-1 que use reportlab)

**Interfaces:**
- Produces:
  - `fmt_moneda(valor: float | None) -> str` → `"$ 2.295,00"`; negativos `"-$ 1.500,00"`; `None` → `"$ 0,00"`
  - `fmt_cantidad(valor: float | None) -> str` → `"1"`, `"4,35"`, `"0,25"`; hasta 3 decimales, sin ceros sobrantes
  - `fmt_puntos(valor: float | None) -> str` → entero con separador de miles: `"1.250"`

- [ ] **Step 1: Tests que fallan**

```python
from formato import fmt_moneda, fmt_cantidad, fmt_puntos

def test_moneda():
    assert fmt_moneda(2295) == "$ 2.295,00"
    assert fmt_moneda(0) == "$ 0,00"
    assert fmt_moneda(None) == "$ 0,00"
    assert fmt_moneda(-1500) == "-$ 1.500,00"
    assert fmt_moneda(1234567.891) == "$ 1.234.567,89"

def test_cantidad():
    assert fmt_cantidad(1.0) == "1"
    assert fmt_cantidad(4.35) == "4,35"
    assert fmt_cantidad(0.25) == "0,25"
    assert fmt_cantidad(1500) == "1.500"

def test_puntos():
    assert fmt_puntos(1250.0) == "1.250"
    assert fmt_puntos(None) == "0"
```

- [ ] **Step 2:** `pytest tests/test_formato.py -q` → FAIL (módulo inexistente).
- [ ] **Step 3:** Implementar con `f"{abs(v):,.2f}"` + swap de `,`/`.` (sin `locale`, que depende del SO).
- [ ] **Step 4:** `pytest -q` → PASS.
- [ ] **Step 5:** Reemplazar los usos. Patrón: `${x:,.2f}` → `{fmt_moneda(x)}`; puntos (`app.py:1313`, `app.py:1415` y similares) → `fmt_puntos`. Verificar: `grep -c ',\.2f' app.py reportes.py models.py` → 0 (o solo casos que no son moneda, justificados en el commit).
- [ ] **Step 6:** `pytest -q` → PASS (incluye la aserción actualizada del PDF).
- [ ] **Step 7: Verificar con Playwright:** POS (precio, total, cantidad `1`), Clientes (límite, puntos), Productos (precios), Arqueo (métricas y fecha `18/10/2026`).
- [ ] **Step 8:** Commit `feat(ui): formato argentino para moneda, cantidades, puntos y fechas`.

### Task 7: Arqueo y Clientes — acciones que tengan sentido

**Files:**
- Modify: `app.py:2540-2542` → `st.button(..., disabled=resumen["total_operaciones"] == 0)` + `st.caption("No hay ventas para cerrar en esta fecha.")` cuando está deshabilitado
- Modify: `app.py:~1305-1315` (tarjeta de cliente) → teléfono como link `reportes.armar_url_whatsapp(telefono, "")` si hay teléfono

**Interfaces:**
- Consumes: `reportes.armar_url_whatsapp(telefono: Optional[str], mensaje: str) -> str` (existente).

- [ ] **Step 1:** Implementar.
- [ ] **Step 2: Verificar con Playwright:** Arqueo con 0 ventas → botón deshabilitado + caption. Clientes → el teléfono de Carlos Pérez es un `<a href="https://wa.me/...">`.
- [ ] **Step 3:** Commit `feat(ui): cierre deshabilitado sin ventas y teléfono a WhatsApp`.

## Fase 4 — Base de datos reproducible

### Task 8: Esquema base en el repo

**Files:**
- Create: `sql/00_esquema_base.sql` (desde `scratchpad/sb/00_esquema_reconstruido.sql`, sin datos demo ni grants)
- Create: `sql/dev/seed_demo.sql` (los datos demo de ese archivo)
- Create: `sql/dev/grants_local.sql` (desde `scratchpad/sb/99_grants.sql`, con el `revoke` sobre `usuarios`; encabezado "solo entorno local")
- Create: `sql/README.md` → orden: `00_esquema_base`, `usuarios_auth`, `caja_chica`, `fidelidad_puntos`, `canje_premios`, `registrar_venta_atomica`, `reset_datos`; después `dev/` solo en local. No se renombran los scripts existentes (los referencian 9 mensajes en `app.py`/`models.py`).

- [ ] **Step 1: Verificar en base vacía:** `npx supabase db reset` (en `scratchpad/sb`), aplicar los archivos en el orden del README con `ON_ERROR_STOP=1` → todos sin error.
- [ ] **Step 2:** `notify pgrst, 'reload schema'`; login con Playwright y abrir las 6 pantallas → ninguna muestra error.
- [ ] **Step 3:** Commit `feat(sql): esquema base reproducible y orden de scripts`.

### Task 9: `resetear_datos_comercio` robusto

**Files:**
- Modify: `sql/reset_datos.sql`
- Create: `sql/dev/test_reset.sql` (bloques `do $$ ... assert ... $$;`)
- Modify: `models.py:~985-995` (docstring) para que coincida con el comportamiento final

**Decisiones:**
- `movimientos_caja`, `arqueos`, `arqueo_caja`, `cierres_caja`: borrar solo si `to_regclass('public.<tabla>') is not null`; contar las filas borradas en el jsonb de resultado.
- `clientes.puntos`: tocar solo si la columna existe (`information_schema.columns`).
- Se elimina el bloque que reinicia secuencias (`setval`): causa IDs duplicados con otros comercios y no aporta.
- `perform pg_advisory_xact_lock(p_comercio_id)` al inicio del reset y al inicio de `registrar_venta_atomica`.
- **A confirmar con el usuario antes de implementar:** en modo `movimientos`, ¿los puntos de los clientes se ponen en 0 o se conservan? Según la respuesta, se ajusta el código o el encabezado + docstring.

- [ ] **Step 1: Test que falla** (`sql/dev/test_reset.sql`): en una base con solo `00_esquema_base` + `usuarios_auth` + `reset_datos` (sin `caja_chica` ni `fidelidad_puntos`), `select resetear_datos_comercio(1, 'movimientos', 1, '1234')` devuelve `ok = true`; y tras un reset completo la siguiente venta de otro comercio no reutiliza IDs.
- [ ] **Step 2:** Correr → FAIL (`relation "movimientos_caja" does not exist`).
- [ ] **Step 3:** Implementar las decisiones.
- [ ] **Step 4:** Correr el test en la base mínima y en la base completa → PASS en ambas.
- [ ] **Step 5:** Commit `fix(sql): reset tolera tablas opcionales, sin setval y con lock por comercio`.

## Fase 5 — Seguridad

### Task 10: PIN de ejemplo obligatorio de cambiar

**Files:**
- Modify: `sql/usuarios_auth.sql` → columna `debe_cambiar_pin boolean not null default false`; el seed la pone en `true`; `cambiar_pin` la pone en `false`; `verificar_login` la devuelve en `usuario`
- Modify: `app.py:454-466` (`_intentar_login`) → si `usuario["debe_cambiar_pin"]`, mostrar formulario de PIN nuevo antes de entrar
- Modify: `sql/dev/test_reset.sql` o nuevo `sql/dev/test_auth.sql` → assert de que el seed queda con `debe_cambiar_pin = true` y `cambiar_pin` lo apaga

**A confirmar con el usuario antes de implementar:** (a) PIN de 4 o 6 dígitos; (b) si `listar_usuarios_login` deja de devolver el rol (hoy se usa solo para el ícono 👑/👤 del login).

- [ ] **Step 1:** Test SQL que falla. **Step 2:** Implementar SQL. **Step 3:** Test SQL pasa.
- [ ] **Step 4: Verificar con Playwright:** login con `1234` → pide PIN nuevo; tras cambiarlo entra al POS; cerrar sesión y entrar con el nuevo PIN.
- [ ] **Step 5:** Commit `feat(auth): obliga a cambiar el PIN de ejemplo`.

## Fase 6 — Mantenimiento

### Task 11: APIs deprecadas y versión fijada

**Files:**
- Modify: `app.py` (43 usos) → `use_container_width=True` → `width="stretch"`; `False` → `width="content"`
- Modify: `requirements.txt` → `streamlit==1.66.0` (la versión probada)

- [ ] **Step 1:** Reemplazar; `grep -c use_container_width app.py` → 0.
- [ ] **Step 2:** Levantar la app y recorrer las 6 pantallas con Playwright; el log de Streamlit no muestra el aviso de `use_container_width`.
- [ ] **Step 3:** `pytest -q` → PASS.
- [ ] **Step 4:** Commit `chore: reemplaza use_container_width y fija la versión de Streamlit`.

---

## Fuera de alcance (decisiones pendientes, no se implementan en este plan)

- Mantener la sesión al recargar (F5): Streamlit no tiene cookies nativas; requiere token firmado en `st.query_params` o un componente de cookies. Decisión de seguridad aparte.
- Mostrar los botones de peso solo en productos por peso: requiere columna nueva en `productos` (`se_vende_por_peso`).
- Teclado numérico para el PIN en celular: requiere inyectar JS.
- POS fuera de Streamlit (React): solo si el celular pasa a ser dispositivo principal.
