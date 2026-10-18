import pytest

import models


def test_cambiar_pin_rechaza_pin_de_ejemplo(monkeypatch):
    monkeypatch.setattr(models, "_rpc_auth", lambda *a, **k: {"ok": False, "motivo": "pin_inseguro"})
    with pytest.raises(models.BusinessLogicError, match="de ejemplo"):
        models.cambiar_pin(1, "1234", "0000")
