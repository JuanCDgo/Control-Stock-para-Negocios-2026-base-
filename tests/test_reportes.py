from reportes import _total_ticket, armar_mensaje_whatsapp_ticket, generar_pdf_ticket_termico


def test_total_ticket_none_y_ausente():
    assert _total_ticket({"total_venta": None}) == 0.0
    assert _total_ticket({}) == 0.0
    assert _total_ticket({"total": 50}) == 50.0
    assert _total_ticket({"total_venta": 1234.5, "total": 1}) == 1234.5


def test_whatsapp_no_explota_con_total_none():
    assert "Total Abonado" in armar_mensaje_whatsapp_ticket({"total_venta": None})


def test_pdf_ticket_imprime_el_monto(monkeypatch):
    import reportlab.rl_config
    monkeypatch.setattr(reportlab.rl_config, "pageCompression", 0)
    pdf = generar_pdf_ticket_termico({"total_venta": 1234.5, "items": []}, "Test")
    assert b"$ 1.234,50" in pdf


def test_normalizar_tel_ar_formatos_habituales():
    from reportes import normalizar_tel_ar
    assert normalizar_tel_ar("3515987654") == "5493515987654"
    assert normalizar_tel_ar("0351 15 412-3456") == "5493514123456"
    assert normalizar_tel_ar("+54 9 351 412-3456") == "5493514123456"
    assert normalizar_tel_ar("+54 351 412 3456") == "5493514123456"
    assert normalizar_tel_ar("011 15 4123-4567") == "5491141234567"


def test_normalizar_tel_ar_sin_numero_completo_no_inventa():
    from reportes import normalizar_tel_ar
    assert normalizar_tel_ar("15 4123456") is None  # falta la característica
    assert normalizar_tel_ar("") is None
    assert normalizar_tel_ar(None) is None


def test_url_whatsapp_sin_numero_valido_deja_elegir_contacto():
    from reportes import armar_url_whatsapp
    assert armar_url_whatsapp("15 4123456", "hola") == "https://wa.me/?text=hola"
    assert armar_url_whatsapp("0351 15 412-3456", "hola") == "https://wa.me/5493514123456?text=hola"
