"""
Integración contra el Supabase LOCAL (npx supabase start): baja lógica en vez de borrado.
Usa el comercio 9001, que el fixture crea si falta. Se saltea si la base local no responde.
"""
import subprocess
import urllib.request
import uuid

import pytest

import models

COMERCIO_TEST = 9001


def _supabase_local_arriba():
    try:
        urllib.request.urlopen("http://127.0.0.1:54321/rest/v1/", timeout=2)
        return True
    except urllib.error.HTTPError:
        return True  # responde (401 sin key): está arriba
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _supabase_local_arriba(), reason="Supabase local no está corriendo")


def _psql(sql):
    subprocess.run(["docker", "exec", "supabase_db_sb", "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1",
                    "-qc", sql], check=True, capture_output=True)


@pytest.fixture(scope="module")
def comercio_test():
    _psql(f"insert into comercios (id, nombre_negocio) overriding system value "
          f"values ({COMERCIO_TEST}, 'Test baja logica') on conflict (id) do nothing")
    return COMERCIO_TEST


def _unico(prefijo):
    return f"{prefijo}-{uuid.uuid4().hex[:8]}"


def test_baja_de_cliente_conserva_historial(comercio_test):
    cid = models.crear_cliente(_unico("Cliente"), comercio_id=comercio_test)
    models.registrar_abono_cliente(cid, 100, comercio_id=comercio_test)

    models.eliminar_cliente(cid, comercio_id=comercio_test)

    assert cid not in [c["id"] for c in models.obtener_clientes(comercio_id=comercio_test)]
    assert models.obtener_movimientos_cliente(cid, comercio_id=comercio_test), "se perdió el historial"
    assert cid in [c["id"] for c in models.listar_dados_de_baja("clientes", comercio_id=comercio_test)]

    models.reactivar("clientes", cid, comercio_id=comercio_test)
    assert cid in [c["id"] for c in models.obtener_clientes(comercio_id=comercio_test)]


def test_producto_dado_de_baja_no_se_vende_ni_se_duplica(comercio_test):
    codigo = _unico("COD")
    pid = models.crear_producto(codigo, "Producto test", None, 100, 30, False, None, 5, 1,
                                comercio_id=comercio_test)
    assert models.obtener_producto_por_codigo(codigo, comercio_id=comercio_test)

    models.eliminar_producto(pid, comercio_id=comercio_test)

    assert models.obtener_producto_por_codigo(codigo, comercio_id=comercio_test) is None
    assert pid not in [p["id"] for p in models.obtener_productos(comercio_id=comercio_test)]
    with pytest.raises(models.BusinessLogicError, match="reactivalo"):
        models.crear_producto(codigo, "Otro", None, 100, 30, False, None, 5, 1, comercio_id=comercio_test)


def test_categoria_con_nombre_de_baja_pide_reactivar(comercio_test):
    nombre = _unico("Categoria")
    cat_id = models.crear_categoria(nombre, comercio_id=comercio_test)

    models.eliminar_categoria(cat_id, comercio_id=comercio_test)

    assert cat_id not in [c["id"] for c in models.get_categorias(comercio_id=comercio_test)]
    with pytest.raises(models.BusinessLogicError, match="reactivala"):
        models.crear_categoria(nombre, comercio_id=comercio_test)


def test_tabla_no_permitida():
    with pytest.raises(ValueError):
        models.dar_de_baja("ventas", 1)


def test_carga_masiva_reactiva_producto_y_categoria_de_baja(comercio_test):
    import pandas as pd
    nombre_cat = _unico("CatImport")
    cat_id = models.crear_categoria(nombre_cat, comercio_id=comercio_test)
    codigo = _unico("IMP")
    pid = models.crear_producto(codigo, "Importado", cat_id, 100, 30, False, None, 5, 1, comercio_id=comercio_test)
    models.eliminar_producto(pid, comercio_id=comercio_test)
    models.eliminar_categoria(cat_id, comercio_id=comercio_test)

    df = pd.DataFrame([{"codigo": codigo, "nombre": "Importado", "categoria": nombre_cat,
                        "precio_costo": 100, "precio_venta": 150, "stock": 3, "stock_minimo": 1}])
    models.importar_productos_masivo(df, comercio_id=comercio_test)

    assert models.obtener_producto_por_codigo(codigo, comercio_id=comercio_test), "el producto sigue de baja"
    assert cat_id in [c["id"] for c in models.get_categorias(comercio_id=comercio_test)], "la categoría sigue de baja"


def test_lo_archivado_no_aparece_en_arqueo_ni_historiales(comercio_test):
    from datetime import datetime, timezone
    hoy = datetime.now(timezone.utc).date().isoformat()
    archivar = "update {t} set archivado_en = now() where comercio_id = %d and archivado_en is null" % comercio_test

    _psql(archivar.format(t="ventas"))
    _psql(f"insert into ventas (comercio_id, total_venta) values ({comercio_test}, 100)")
    cid = models.crear_cliente(_unico("Archivo"), comercio_id=comercio_test)
    models.registrar_abono_cliente(cid, 50, comercio_id=comercio_test)
    _psql(archivar.format(t="movimientos_caja"))
    _psql(f"insert into movimientos_caja (comercio_id, tipo, monto, concepto) "
          f"values ({comercio_test}, 'egreso', 10, 'test')")
    models.st.cache_data.clear()
    assert models.obtener_arqueo_caja(hoy, comercio_id=comercio_test)["total_operaciones"] == 1
    assert models.obtener_movimientos_cliente(cid, comercio_id=comercio_test)
    assert len(models.obtener_movimientos_caja(comercio_test, hoy)) == 1

    for t in ("ventas", "movimientos_cuenta", "movimientos_caja"):
        _psql(archivar.format(t=t))
    models.st.cache_data.clear()

    assert models.obtener_arqueo_caja(hoy, comercio_id=comercio_test)["total_operaciones"] == 0
    assert models.obtener_movimientos_cliente(cid, comercio_id=comercio_test) == []
    assert models.obtener_movimientos_caja(comercio_test, hoy) == []


def _psql_valor(sql):
    out = subprocess.run(["docker", "exec", "supabase_db_sb", "psql", "-U", "postgres", "-tAc", sql],
                         check=True, capture_output=True, text=True)
    return out.stdout.strip()


def test_restaurar_respaldo_viejo_deshace_archivado_y_bajas(comercio_test):
    # Un respaldo anterior a la baja lógica no trae activo / archivado_en: solo tenía filas vigentes
    vid = _psql_valor(f"insert into ventas (comercio_id, total_venta, archivado_en) "
                      f"values ({comercio_test}, 77, now()) returning id").splitlines()[0]
    codigo = _unico("BAK")
    pid = models.crear_producto(codigo, "Respaldo", None, 10, 0, False, None, 1, 0, comercio_id=comercio_test)
    models.eliminar_producto(pid, comercio_id=comercio_test)

    respaldo_viejo = {"tablas": {
        "productos": [{"id": pid, "codigo": codigo, "nombre": "Respaldo", "precio_costo": 10,
                       "margen_ganancia": 0, "precio_venta": 10, "usa_precio_manual": False,
                       "stock_actual": 1, "stock_minimo": 0}],
        "ventas": [{"id": int(vid), "total_venta": 77, "forma_pago": "Efectivo"}],
    }}
    assert models.restaurar_backup_completo(respaldo_viejo, comercio_id=comercio_test)["ok"]

    assert _psql_valor(f"select archivado_en is null from ventas where id = {vid}") == "t"
    assert models.obtener_producto_por_codigo(codigo, comercio_id=comercio_test)


def test_reactivar_producto_reactiva_su_categoria(comercio_test):
    cat_id = models.crear_categoria(_unico("CatReact"), comercio_id=comercio_test)
    pid = models.crear_producto(_unico("RC"), "Prod", cat_id, 10, 0, False, None, 1, 0, comercio_id=comercio_test)
    models.eliminar_producto(pid, comercio_id=comercio_test)
    models.eliminar_categoria(cat_id, comercio_id=comercio_test)

    models.reactivar("productos", pid, comercio_id=comercio_test)

    assert cat_id in [c["id"] for c in models.get_categorias(comercio_id=comercio_test)], \
        "el producto volvió en una categoría dada de baja"


def test_renombrar_categoria_al_nombre_de_una_de_baja_pide_reactivar(comercio_test):
    nombre_baja = _unico("CatBaja")
    cat_baja = models.crear_categoria(nombre_baja, comercio_id=comercio_test)
    models.eliminar_categoria(cat_baja, comercio_id=comercio_test)
    otra = models.crear_categoria(_unico("CatOtra"), comercio_id=comercio_test)

    with pytest.raises(models.BusinessLogicError, match="reactivala"):
        models.actualizar_categoria(otra, nombre_baja, comercio_id=comercio_test)


def test_restaurar_respaldo_viejo_desarchiva_caja_chica(comercio_test):
    # movimientos_caja tiene id GENERATED ALWAYS: el restore va por el camino que compara
    # (fecha, monto, concepto) en vez de hacer upsert por id
    concepto = _unico("caja")
    mid = _psql_valor(f"insert into movimientos_caja (comercio_id, tipo, monto, concepto, archivado_en) "
                      f"values ({comercio_test}, 'egreso', 12, '{concepto}', now()) returning id").splitlines()[0]
    fila = models.get_connection().table("movimientos_caja").select("id, tipo, monto, concepto, fecha") \
        .eq("id", int(mid)).execute().data[0]

    assert models.restaurar_backup_completo({"tablas": {"movimientos_caja": [fila]}}, comercio_id=comercio_test)["ok"]

    assert _psql_valor(f"select archivado_en is null from movimientos_caja where id = {mid}") == "t"
    assert _psql_valor(f"select count(*) from movimientos_caja where concepto = '{concepto}'") == "1", "duplicó el movimiento"
