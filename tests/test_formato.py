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


def test_fecha_en_hora_argentina():
    from formato import fmt_fecha
    # 01:30 UTC del 19 = 22:30 del 18 en Argentina (UTC-3)
    assert fmt_fecha("2026-10-19T01:30:00+00:00") == "18/10/2026"
    assert fmt_fecha("2026-10-18T15:00:00.123456+00:00") == "18/10/2026"
    assert fmt_fecha(None) == "-"
    assert fmt_fecha("") == "-"


def test_sin_cero_negativo():
    # el signo se decide sobre el valor ya redondeado
    assert fmt_moneda(-0.004) == "$ 0,00"
    assert fmt_cantidad(-0.0004) == "0"
    assert fmt_puntos(-0.001) == "0"


def test_formatear_df_para_tablas():
    import pandas as pd
    from formato import formatear_df
    df = pd.DataFrame([{"Producto": "Queso", "Venta ($)": 9425.0, "Stock": 4.35, "Puntos": 1250.0}])
    out = formatear_df(df, monedas=["Venta ($)"], cantidades=["Stock"], puntos=["Puntos"])
    assert out.iloc[0].tolist() == ["Queso", "$ 9.425,00", "4,35", "1.250"]
    assert df.iloc[0]["Venta ($)"] == 9425.0  # no modifica el original
