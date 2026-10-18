"""
Formato de números para Argentina: punto de miles y coma decimal.
Se arma a mano (sin `locale`) porque `locale` depende de lo instalado en el sistema.
"""
from typing import Optional


def _swap(texto: str) -> str:
    """Convierte '1,234.56' (en-US) en '1.234,56' (es-AR)."""
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_moneda(valor: Optional[float]) -> str:
    """$ 2.295,00 · -$ 1.500,00 · None -> $ 0,00"""
    v = float(valor or 0)
    signo = "-" if v < 0 else ""
    return f"{signo}$ {_swap(f'{abs(v):,.2f}')}"


def fmt_moneda_md(valor: Optional[float]) -> str:
    """Para textos que pasan por markdown (st.markdown, st.success, st.caption, botones...):
    escapa el $ porque Streamlit toma '$ ... $' como LaTeX y se come los signos."""
    return fmt_moneda(valor).replace("$", r"\$")


def _sin_ceros(valor: Optional[float], decimales: int) -> str:
    return _swap(f"{float(valor or 0):,.{decimales}f}".rstrip("0").rstrip("."))


def fmt_cantidad(valor: Optional[float]) -> str:
    """1 · 4,35 · 0,25 · 1.500 (hasta 3 decimales, sin ceros sobrantes)"""
    return _sin_ceros(valor, 3)


def fmt_puntos(valor: Optional[float]) -> str:
    """1.250 · 22,95 (hasta 2 decimales: se ganan con el 1% de la venta)"""
    return _sin_ceros(valor, 2)
