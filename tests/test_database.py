import database


def test_get_connection_reutiliza_el_cliente(monkeypatch):
    llamadas = []
    monkeypatch.setattr(database, "create_client", lambda u, k: llamadas.append(1) or object())
    monkeypatch.setattr(database.st, "secrets", {"SUPABASE_URL": "u", "SUPABASE_KEY": "k"})
    database.get_connection.clear()
    try:
        assert database.get_connection() is database.get_connection()
        assert len(llamadas) == 1
    finally:
        # que el cliente falso no quede en la caché para los tests que siguen
        database.get_connection.clear()
