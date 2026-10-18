# Baja lógica en vez de borrado Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la app nunca borre datos de negocio: clientes, productos y categorías se dan de baja (y se pueden reactivar); la "Puesta a cero" archiva ventas y movimientos en vez de borrarlos.

**Architecture:** Dos estados nuevos. Catálogos (`productos`, `clientes`, `categorias`): `activo boolean` + `fecha_baja timestamptz`. Historial (`ventas`, `movimientos_cuenta`, `movimientos_caja`): `archivado_en timestamptz` + `archivado_por bigint` (null = vigente; `detalle_ventas` sigue a su venta). Los listados y el arqueo filtran; el respaldo JSON sigue llevando todo. Rama `mejoras/baja-logica` apilada sobre `mejoras/2026-10-18` (PR #1), PR aparte.

**Tech Stack:** Python 3.12, Streamlit 1.66, supabase-py, Postgres (Supabase local), pytest, Playwright MCP.

**Spec:** Pedido del usuario (2026-10-18): "soy partidario de dar de baja o cambiar de estado y no borrar nada" + respuestas: reset = archivar; entrega = PR aparte.

## Global Constraints

- Ningún `DELETE` sobre datos de negocio en `models.py` ni en `sql/reset_datos.sql`.
- Migración idempotente: `alter table ... add column if not exists` dentro de `sql/00_esquema_base.sql` (tablas base) y `sql/caja_chica.sql` (`movimientos_caja`), así una base existente se actualiza volviendo a correr esos scripts.
- Textos de UI: "Dar de baja" / "Reactivar" / "Archivar", voseo.
- Verificación contra Supabase local (`supabase_db_sb`); PIN local del Dueño: `2468`.

## Review Focus

- Crear un producto con el código de uno dado de baja → mensaje claro que indique reactivarlo, no un error de clave duplicada (Task 2).
- Crear una categoría con el nombre de una dada de baja → mismo criterio (Task 2).
- Escanear el código de un producto dado de baja en el POS → "no encontrado", no se vende (Task 2).
- Arqueo de un día con ventas archivadas → no las suma (Task 3).
- Reset dos veces seguidas → la segunda no vuelve a archivar ni a pisar `archivado_en` de lo ya archivado (Task 1).

---

### Task 1: Esquema de estados + reset que archiva

**Files:**
- Modify: `sql/00_esquema_base.sql` → `activo boolean not null default true` y `fecha_baja timestamptz` en `productos`, `clientes`, `categorias`; `archivado_en timestamptz` y `archivado_por bigint` en `ventas`, `movimientos_cuenta`. Columnas en el `create table` y además `alter table ... add column if not exists` (para bases existentes). Índices parciales `where archivado_en is null` en `ventas (comercio_id, fecha_hora)`.
- Modify: `sql/caja_chica.sql` → `archivado_en`, `archivado_por` en `movimientos_caja` (mismo patrón).
- Modify: `sql/reset_datos.sql`:
  - `'movimientos'`: `update ... set archivado_en = now(), archivado_por = p_usuario_id where comercio_id = p_comercio_id and archivado_en is null` sobre `ventas`, `movimientos_cuenta` y `movimientos_caja` (esta última solo si existe la columna). `saldo_deudor` / `puntos` a 0 como hoy.
  - `'total'`: lo anterior + `update productos|clientes|categorias set activo = false, fecha_baja = now() where comercio_id = p_comercio_id and activo`.
  - Claves del jsonb: `ventas`, `movimientos_cuenta`, `movimientos_caja` (si existe), `saldos_reseteados` | `productos`, `categorias`, `clientes` (= filas actualizadas). Se quita `detalle_ventas` y la lista de opcionales `arqueos/arqueo_caja/cierres_caja` (ningún script las crea).
  - Encabezado: "no borra nada; archiva / da de baja".
- Modify: `sql/dev/test_reset.sql` → casos nuevos (abajo); se quita el caso 3 de arqueos.

- [ ] **Step 1: Tests que fallan** en `sql/dev/test_reset.sql` (dentro de la transacción con rollback):
  - Tras `'movimientos'`: `select count(*) from ventas where comercio_id = 1` no cambia, y todas tienen `archivado_en is not null` y `archivado_por = <usuario test>`.
  - Tras `'total'`: `count(*)` de `productos` no cambia y `not exists (select 1 from productos where comercio_id = 1 and activo)`.
  - Segundo `'movimientos'` seguido: devuelve `ventas = 0` y no cambia el `archivado_en` del primero.
  - Se mantienen: base sin `caja_chica`/`fidelidad_puntos` → `ok`; IDs no se reutilizan; saldo y puntos en 0.
- [ ] **Step 2:** Correr → FAIL (las ventas se borran).
- [ ] **Step 3:** Implementar esquema + función. Aplicar `00_esquema_base.sql`, `caja_chica.sql`, `reset_datos.sql`, `dev/grants_local.sql` en la base local.
- [ ] **Step 4:** `test_reset.sql` → `test_reset: OK`; `test_auth.sql` sigue OK; pytest sigue verde.
- [ ] **Step 5:** Commit `feat(sql): estados activo/archivado y reset que archiva en vez de borrar`.

### Task 2: Baja lógica de productos, clientes y categorías (models)

**Files:**
- Modify: `models.py`
- Create: `tests/test_baja_logica.py` (integración contra Supabase local; usa `comercio_id = 9001`, creado por un fixture con `psql`; se saltea si `127.0.0.1:54321` no responde)

**Interfaces:**
- Produces:
  - `dar_de_baja(tabla: str, registro_id: int, comercio_id=COMERCIO_ID_DEFAULT) -> None` y `reactivar(tabla: str, registro_id: int, comercio_id=...) -> None`; `tabla` ∈ `TABLAS_CON_BAJA = ("productos", "clientes", "categorias")`, otra → `ValueError`.
  - `listar_dados_de_baja(tabla: str, comercio_id=...) -> list[dict]` (`id`, `nombre`, `fecha_baja`).
  - `eliminar_producto`, `eliminar_cliente`, `eliminar_categoria`: mismas firmas, ahora llaman a `dar_de_baja` (la UI no cambia de función).
- Reglas:
  - `eliminar_cliente`: sigue exigiendo saldo 0; **no** toca `movimientos_cuenta`.
  - `eliminar_producto`: ya no exige "sin ventas".
  - `eliminar_categoria`: bloquea solo si tiene productos **activos**.
  - `get_categorias`, `get_productos`, `obtener_producto_por_codigo`, `obtener_clientes`, `obtener_resumen_deuda_total`: filtran `activo = true`.
  - `_verificar_codigo_libre` y `crear_categoria`: si el choque es con un registro dado de baja → `BusinessLogicError` "… está dado de baja: reactivalo desde 'Dados de baja'".
  - `importar_productos_masivo`: si el código existe dado de baja, lo actualiza y lo reactiva (`activo = true`, `fecha_baja = null`); igual para la categoría por nombre.
  - Se borra la función muerta `delete_producto` (models.py:206, sin usos).

- [ ] **Step 1: Tests que fallan**

```python
def test_baja_de_cliente_conserva_historial(comercio_test):
    cid = models.crear_cliente("Test Baja", comercio_id=comercio_test)  # firma real de crear_cliente
    # registrar un movimiento (abono/cargo) con la función existente
    models.eliminar_cliente(cid, comercio_id=comercio_test)
    assert cid not in [c["id"] for c in models.obtener_clientes(comercio_id=comercio_test)]
    assert models.obtener_movimientos_cliente(cid, comercio_id=comercio_test)  # el historial sigue
    models.reactivar("clientes", cid, comercio_id=comercio_test)
    assert cid in [c["id"] for c in models.obtener_clientes(comercio_id=comercio_test)]

def test_producto_dado_de_baja_no_se_vende_ni_se_duplica(comercio_test): ...
    # baja → obtener_producto_por_codigo devuelve None; crear otro con el mismo código → BusinessLogicError con "reactivalo"

def test_categoria_con_nombre_de_baja_pide_reactivar(comercio_test): ...

def test_tabla_no_permitida():
    with pytest.raises(ValueError):
        models.dar_de_baja("ventas", 1)
```

- [ ] **Step 2:** `pytest tests/test_baja_logica.py -q` → FAIL.
- [ ] **Step 3:** Implementar las reglas.
- [ ] **Step 4:** `pytest -q` → PASS (todos).
- [ ] **Step 5:** Commit `feat: baja logica de productos, clientes y categorias`.

### Task 3: Historial archivado fuera de pantallas y reportes (models)

**Files:**
- Modify: `models.py` → `.is_("archivado_en", "null")` en: `obtener_arqueo_caja` (ventas y abonos de `movimientos_cuenta`), `obtener_movimientos_cliente`, `obtener_movimientos_caja`, y cualquier otra lectura de `ventas` / `movimientos_cuenta` / `movimientos_caja` fuera del respaldo.
- Modify: `models.py` `resetear_datos` docstring.
- Modify: `tests/test_baja_logica.py`

- [ ] **Step 1: Test que falla:** en `comercio_test`, registrar una venta con `registrar_venta`, marcarla archivada por `psql`, y `obtener_arqueo_caja(hoy, comercio_id=comercio_test)["total_operaciones"] == 0`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** `pytest -q` → PASS.
- [ ] **Step 5:** Commit `feat: el arqueo y los historiales ignoran lo archivado`.

### Task 4: UI — dar de baja, reactivar y textos del reset

**Files:**
- Modify: `app.py`
  - Clientes (`app.py:~1512`): "🗑️ Zona de Baja: Eliminar Cliente" → "Dar de baja cliente"; texto: "Se oculta de las listas y conserva su historial. Se puede reactivar."
  - Productos (`app.py:~2182`): igual; ya no borra la foto del producto.
  - Categorías (`app.py:~2478`): botón "Dar de baja".
  - "Dar de baja" pide confirmación: un `st.checkbox("Confirmo dar de baja a <nombre>")` que habilita el botón (regla `confirmation-dialogs` de la revisión UX).
  - En cada una de las 3 pantallas: `st.expander(f"Dados de baja ({n})")` con `listar_dados_de_baja` y un botón "Reactivar" por fila (key `f"react_{tabla}_{id}"`).
  - Reset (`app.py:~2930-3000`): textos "archiva" / "da de baja" en vez de "borra"; mensaje de resultado "N ventas archivadas, …".
- [ ] **Step 1: Verificar con Playwright** (local, PIN 2468): dar de baja un cliente sin deuda → desaparece de la libreta y aparece en "Dados de baja (1)"; "Reactivar" lo devuelve. Lo mismo con un producto (el POS no lo ofrece mientras está de baja) y una categoría. Reset 'movimientos' con PIN → Arqueo muestra 0 y la base conserva las filas (`psql count`).
- [ ] **Step 2:** `pytest -q` + tests SQL → verdes.
- [ ] **Step 3:** Commit `feat(ui): dar de baja y reactivar; el reset archiva`.

---

## Fuera de alcance

- Pantalla para consultar ventas archivadas (quedan en la base y en el respaldo JSON).
- Auditoría de quién dio de baja un cliente/producto (solo se guarda `fecha_baja`).
