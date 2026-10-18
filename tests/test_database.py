import database


def test_get_connection_reutiliza_el_cliente(monkeypatch):
    llamadas = []
    monkeypatch.setattr(database, "create_client", lambda u, k: llamadas.append(1) or object())
    monkeypatch.setattr(database.st, "secrets", {"SUPABASE_URL": "u", "SUPABASE_KEY": "k"})
    if hasattr(database.get_connection, "clear"):
        database.get_connection.clear()
    assert database.get_connection() is database.get_connection()
    assert len(llamadas) == 1
