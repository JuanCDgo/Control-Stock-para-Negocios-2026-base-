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
