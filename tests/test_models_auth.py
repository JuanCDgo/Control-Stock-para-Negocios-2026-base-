import pytest

import models


def test_cambiar_pin_rechaza_pin_de_ejemplo(monkeypatch):
    monkeypatch.setattr(models, "_rpc_auth", lambda *a, **k: {"ok": False, "motivo": "pin_inseguro"})
    with pytest.raises(models.BusinessLogicError, match="de ejemplo"):
        models.cambiar_pin(1, "1234", "0000")


def test_cambiar_pin_bloqueado_avisa_el_bloqueo(monkeypatch):
    monkeypatch.setattr(models, "_rpc_auth", lambda *a, **k: {"ok": False, "motivo": "bloqueado", "minutos_bloqueo": 5})
    with pytest.raises(models.BusinessLogicError, match="(?i)bloque"):
        models.cambiar_pin(1, "0001", "5678")
