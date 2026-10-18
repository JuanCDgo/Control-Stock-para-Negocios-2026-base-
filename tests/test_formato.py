from formato import fmt_moneda, fmt_cantidad, fmt_puntos


def test_moneda():
    assert fmt_moneda(2295) == "$ 2.295,00"
    assert fmt_moneda(0) == "$ 0,00"
    assert fmt_moneda(None) == "$ 0,00"
    assert fmt_moneda(-1500) == "-$ 1.500,00"
    assert fmt_moneda(1234567.891) == "$ 1.234.567,89"


def test_cantidad():
    assert fmt_cantidad(1.0) == "1"
    assert fmt_cantidad(4.35) == "4,35"
    assert fmt_cantidad(0.25) == "0,25"
    assert fmt_cantidad(1500) == "1.500"


def test_puntos():
    assert fmt_puntos(1250.0) == "1.250"
    assert fmt_puntos(None) == "0"
    assert fmt_puntos(22.95) == "22,95"  # se ganan con el 1% de la venta: pueden tener decimales


def test_moneda_md_escapa_el_signo_para_markdown():
    # st.markdown toma "$ ... $" como LaTeX: con dos montos en un texto se comía los signos
    from formato import fmt_moneda_md
    assert fmt_moneda_md(2295) == r"\$ 2.295,00"
    assert fmt_moneda_md(-1500) == r"-\$ 1.500,00"
