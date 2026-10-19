"""
Integración contra el Supabase LOCAL: puntos con decimales (se ganan con el 1% de la venta).
Usa el comercio 9002. Se saltea si la base local no responde.
"""
import subprocess
import urllib.request
import uuid

import pytest

import models

COMERCIO_TEST = 9002


def _supabase_local_arriba():
    try:
        urllib.request.urlopen("http://127.0.0.1:54321/rest/v1/", timeout=2)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _supabase_local_arriba(), reason="Supabase local no está corriendo")


def _psql(sql):
    subprocess.run(["docker", "exec", "supabase_db_sb", "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1",
                    "-qc", sql], check=True, capture_output=True)


@pytest.fixture(scope="module")
def comercio_test():
    _psql(f"insert into comercios (id, nombre_negocio) overriding system value "
          f"values ({COMERCIO_TEST}, 'Test puntos') on conflict (id) do nothing")
    return COMERCIO_TEST


def test_canje_no_redondea_puntos_a_favor_del_cliente(comercio_test):
    pid = models.crear_producto(f"PTS-{uuid.uuid4().hex[:8]}", "Premio", None, 10, 0, False, None, 5, 0,
                                puntos_canje=100, comercio_id=comercio_test)
    cid = models.crear_cliente(f"Puntos-{uuid.uuid4().hex[:8]}", comercio_id=comercio_test)
    _psql(f"update clientes set puntos = 99.5 where id = {cid}")

    with pytest.raises(models.BusinessLogicError, match="Puntos insuficientes"):
        models.registrar_venta([{"producto_id": pid, "cantidad": 1, "es_canje": True}], "Efectivo",
                               cliente_id=cid, comercio_id=comercio_test)

    # el saldo se muestra con sus decimales, no redondeado
    cli = next(c for c in models.obtener_clientes(comercio_id=comercio_test) if c["id"] == cid)
    assert cli["puntos"] == 99.5
