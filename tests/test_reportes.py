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
