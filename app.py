"""
Interfaz de usuario con Streamlit para el Sistema de Gestión Interna.
Organizado en 6 módulos principales:
1. :material/point_of_sale: Punto de Venta (POS) con Lector de Código de Barras, QR y Cuenta Corriente / Fiado
2. :material/group: Cuentas Corrientes / Clientes ("La Libreta" de fiados, abonos y límites)
3. :material/inventory_2: Productos e Inventario (Catálogo, Carga con Fotos, Edición Completa, Ajustes y Alertas)
4. :material/sell: Categorías
5. Arqueo de Caja y Cierre Diario en PDF / WhatsApp / Correo
6. :material/settings: Configuración del Negocio (Datos Bancarios, QR y SMTP)
"""
import os
import io
import re
import html
import textwrap
import urllib.parse
import importlib
import json
import streamlit as st
import altair as alt
import pandas as pd
from datetime import datetime, date
import zoneinfo
from typing import Optional
from PIL import Image, ImageOps

ZONA_HORARIA = zoneinfo.ZoneInfo("America/Argentina/Buenos_Aires")

from database import init_db
import models
importlib.reload(models)
import reportes
importlib.reload(reportes)
from formato import fmt_moneda, fmt_moneda_md, fmt_cantidad, fmt_puntos, fmt_fecha, formatear_df
from config_manager import (
    cargar_configuracion,
    guardar_configuracion,
)

# Configuración del directorio base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuración general de la página Streamlit
st.set_page_config(
    page_title="Sistema de Gestión Comercial",
    page_icon=":material/storefront:",
    layout="wide",
    initial_sidebar_state="collapsed"  # la navegación está en la barra superior
)


# ---------------- ESTILOS GLOBALES (SaaS Dashboard) ----------------
st.markdown("""
<style>
    /* Tarjetas de métricas (st.metric): misma superficie y borde que los paneles */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 0.5rem;
        padding: 0.875rem 1rem;
    }

    /* Vista Compacta de Productos / Inventario */
    [data-testid="stHtml"] {
        margin: 0 !important;
        padding: 0 !important;
    }
    .inv-cp-row {
        display: flex;
        align-items: center;
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 3px 12px;
        min-height: 42px;
        box-sizing: border-box;
        transition: all 0.15s ease-in-out;
        gap: 12px;
        margin-bottom: 3px;
        width: 100%;
    }
    .inv-cp-row:hover {
        background-color: #f8fafc;
        border-color: #cbd5e1;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    }
    .inv-cp-thumb {
        width: 36px;
        height: 36px;
        min-width: 36px;
        max-width: 45px;
        border-radius: 5px;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        background-color: #f1f5f9;
        flex-shrink: 0;
        border: 1px solid #e2e8f0;
    }
    .inv-cp-thumb img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .inv-cp-info {
        flex: 1;
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 8px;
        overflow: hidden;
    }
    .inv-cp-title {
        font-weight: 600;
        font-size: 0.92rem;
        color: #0f172a;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .inv-cp-badge {
        background-color: #eff6ff;
        color: #1d4ed8;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 1px 7px;
        border-radius: 9999px;
        white-space: nowrap;
        flex-shrink: 0;
        border: 1px solid #dbeafe;
    }
    .inv-cp-code {
        color: #64748b;
        font-size: 0.75rem;
        white-space: nowrap;
        flex-shrink: 0;
    }
    .inv-cp-end {
        display: flex;
        align-items: center;
        gap: 16px;
        flex-shrink: 0;
        margin-left: auto;
    }
    .inv-cp-stock {
        font-size: 0.78rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 4px;
        white-space: nowrap;
    }
    .inv-cp-stock-ok {
        background-color: #f0fdf4;
        color: #166534;
        border: 1px solid #bbf7d0;
    }
    .inv-cp-stock-critico {
        background-color: #fef2f2;
        color: #b91c1c;
        border: 1px solid #fecaca;
    }
    .inv-cp-price {
        font-size: 1.02rem;
        font-weight: 700;
        color: #0f172a;
        white-space: nowrap;
        min-width: 90px;
        text-align: right;
    }

    /* Celular: títulos más chicos y menos margen para que entre más contenido */
    @media (max-width: 640px) {
        [data-testid="stMainBlockContainer"] { padding-left: 1rem !important; padding-right: 1rem !important; }
        /* Objetivo táctil mínimo de 44px en campos y selectores (los botones ya lo tienen) */
        [data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"],
        [data-testid="stSelectbox"] > div > div { min-height: 44px !important; }
    }

    /* Dígitos de ancho fijo: precios y totales no "bailan" al cambiar */
    [data-testid="stMain"] { font-variant-numeric: tabular-nums; }

    /* Cobrar: la acción principal del POS, en verde (#047857 cumple contraste AA con texto blanco) */
    .st-key-btn_cobrar button[kind="primary"] { background-color: #047857 !important; border-color: #047857 !important; }
    .st-key-btn_cobrar button[kind="primary"]:hover { background-color: #065F46 !important; border-color: #065F46 !important; }
</style>
""", unsafe_allow_html=True)
# -------------------------------------------------------------------

# Inicializar y migrar la base de datos automáticamente
init_db()

# Cargar configuración global del negocio
config_negocio = cargar_configuracion()

# Estilos CSS globales para interfaz limpia, ágil y optimizada para mostrador / touch
st.markdown(
    """
    <style>
    /* Sin el encabezado de Streamlit: tapaba el comienzo de la página en celular. La app
       tiene su propia barra superior y avisos de carga en las acciones lentas. */
    [data-testid="stHeader"], [data-testid="stDecoration"] { display: none !important; }

    /* Contenido centrado con ancho máximo: en monitores grandes no se estira de borde a borde */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 1280px !important;
    }

    /* Separadores con menos aire: los de Streamlit dejan bandas vacías muy grandes */
    hr { margin: 0.75rem 0 !important; }

    /* Objetivo táctil mínimo de 44px en todos los botones */
    button[kind="primary"], button[kind="primaryFormSubmit"],
    button[kind="secondary"], button[kind="secondaryFormSubmit"] {
        min-height: 44px !important;
    }
    button[kind="primary"], button[kind="primaryFormSubmit"] { font-weight: 700 !important; }

    /* Foco visible al navegar con teclado (Streamlit no lo marca en todos los botones) */
    button:focus-visible, [role="tab"]:focus-visible, [role="radio"]:focus-visible,
    [role="combobox"]:focus-visible, input:focus-visible {
        outline: 2px solid #2563EB !important;
        outline-offset: 2px !important;
    }

    /* Respetar la preferencia del sistema de reducir movimiento */
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { transition: none !important; animation: none !important; }
    }

    /* Celular: campos con letra de 16px para que iOS no haga zoom al tocarlos,
       y las filas de métricas en grilla de 2x2 en vez de una columna larga */
    @media (max-width: 640px) {
        input, textarea { font-size: 16px !important; }
        [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) {
            flex-direction: row !important;
            flex-wrap: wrap !important;
        }
        [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) > [data-testid="stColumn"] {
            flex: 1 1 calc(50% - 0.5rem) !important;
            min-width: calc(50% - 0.5rem) !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Inicialización de estado de sesión para el carrito de compras y preferencias de vista
if "carrito" not in st.session_state:
    st.session_state.carrito = []

if "inv_vista_ficha" not in st.session_state:
    st.session_state.inv_vista_ficha = "Compacta"

if "pos_cant_val" not in st.session_state:
    st.session_state.pos_cant_val = 1.0


def _set_pos_cant(valor):
    """Callback on_click: fija la cantidad del POS (corre antes de instanciar el widget)."""
    st.session_state["pos_cant_val"] = float(valor)


def _sumar_pos_cant(delta):
    """Callback on_click: suma `delta` a la cantidad actual del POS."""
    actual = float(st.session_state.get("pos_cant_val", 1.0) or 0.0)
    st.session_state["pos_cant_val"] = round(actual + float(delta), 3)


# ==============================================================================
# FUNCIONES AUXILIARES PARA ARCHIVOS DE IMÁGENES
# ==============================================================================
def guardar_archivo_imagen(uploaded_file, prefijo: str = "img", max_dim: int = 400, calidad: int = 80) -> Optional[str]:
    """
    Procesa, redimensiona y comprime una imagen subida usando Pillow.
    - Corrige orientación EXIF.
    - Redimensiona proporcionalmente para que el lado mayor no supere max_dim.
    - Convierte a formato RGB y exporta como JPEG optimizado en memoria.
    - Sube la imagen directamente al bucket de Supabase 'productos'.
    - Retorna la URL pública, o None si no hay imagen o falla el procesamiento.
    """
    if uploaded_file is None:
        return None

    try:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        img = Image.open(uploaded_file)

        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            fondo_blanco = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            fondo_blanco.paste(img, mask=img.split()[3])
            img_final = fondo_blanco
        else:
            img_final = img.convert("RGB")

        prefijo_limpio = "".join(c for c in prefijo if c.isalnum() or c in ("-", "_")).lower()
        timestamp = int(datetime.now().timestamp() * 1000)
        nombre_archivo = f"{prefijo_limpio}_{timestamp}.jpg"

        buffer = io.BytesIO()
        img_final.save(buffer, format="JPEG", quality=calidad, optimize=True)
        buffer.seek(0)

        from database import get_connection
        supabase = get_connection()
        bucket_name = 'productos'
        
        supabase.storage.from_(bucket_name).upload(
            path=nombre_archivo,
            file=buffer.getvalue(),
            file_options={"content-type": "image/jpeg"}
        )
        
        url_publica = supabase.storage.from_(bucket_name).get_public_url(nombre_archivo)
        return url_publica

    except Exception as e:
        raise Exception(f"Error al procesar o subir la imagen al bucket 'productos' de Supabase: {e}")


def obtener_ruta_imagen_absoluta(ruta_relativa):
    if not ruta_relativa or not isinstance(ruta_relativa, str) or ruta_relativa.strip().lower() in ("", "none", "nan", "null"):
        return None
    if ruta_relativa.lower().startswith(("http://", "https://")):
        return ruta_relativa
    ruta_abs = os.path.join(BASE_DIR, ruta_relativa)
    return ruta_abs if os.path.exists(ruta_abs) else None


def obtener_src_imagen_html(ruta_relativa):
    ruta_abs = obtener_ruta_imagen_absoluta(ruta_relativa)
    if not ruta_abs:
        return None
    if str(ruta_abs).lower().startswith(("http://", "https://")):
        return ruta_abs
    if os.path.exists(ruta_abs):
        try:
            import base64
            with open(ruta_abs, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            ext = os.path.splitext(ruta_abs)[1].lower().replace(".", "")
            mime = "jpeg" if ext in ("jpg", "jpeg") else ext
            return f"data:image/{mime};base64,{b64}"
        except Exception:
            return None
    return None


def borrar_archivo_imagen_local(ruta: Optional[str]) -> None:
    """Borra una foto subida al bucket de Supabase."""
    if not ruta or not str(ruta).lower().startswith(("http://", "https://")):
        return
    try:
        import urllib.parse
        from database import get_connection
        
        parsed = urllib.parse.urlparse(ruta)
        nombre_archivo = parsed.path.split('/')[-1]
        
        if nombre_archivo:
            supabase = get_connection()
            supabase.storage.from_('productos').remove([nombre_archivo])
    except Exception:
        pass


# ==============================================================================
# AUTENTICACIÓN Y CONTROL DE ROLES (Dueño / Cajero)
# ==============================================================================
MODULOS_CAJERO = [
    ":material/point_of_sale: Punto de Venta (POS)",
    ":material/group: Cuentas Corrientes / Clientes",
]
MODULOS_ADMIN = MODULOS_CAJERO + [
    ":material/inventory_2: Productos e Inventario",
    ":material/sell: Categorías",
    ":material/bar_chart: Arqueo de Caja / Control Diario",
    ":material/settings: Configuración del Negocio",
]





def _seccion_dados_de_baja(tabla, titulo):
    """Expander con los registros dados de baja de `tabla` y un botón para reactivar cada uno."""
    bajas = models.listar_dados_de_baja(tabla)
    with st.expander(f":material/restore: {titulo} ({len(bajas)})"):
        if not bajas:
            st.caption("No hay registros dados de baja.")
        for reg in bajas:
            c_nom, c_btn = st.columns([3, 1])
            c_nom.markdown(f"**{html.escape(str(reg['nombre']))}** · baja: {fmt_fecha(reg.get('fecha_baja'))}")
            if c_btn.button("Reactivar", key=f"react_{tabla}_{reg['id']}", width="stretch"):
                try:
                    models.reactivar(tabla, reg["id"])
                    st.rerun()
                except models.BusinessLogicError as e:
                    st.error(str(e))


def _cerrar_sesion():
    """Callback de 'Cerrar Sesión': descarta el usuario y los datos de la caja en curso."""
    st.session_state.pop("usuario", None)
    st.session_state["login_pin"] = ""
    st.session_state.carrito = []
    st.session_state["pos_cant_val"] = 1.0


def _intentar_login(usuario_id, pin):
    """Valida el PIN contra la base. Siempre limpia el PIN tipeado y vuelve a renderizar."""
    st.session_state["login_pin"] = ""
    try:
        with st.spinner("Verificando PIN..."):
            usuario, error = models.verificar_login(usuario_id, pin)
    except Exception as e:
        usuario, error = None, f"{e}"
    if usuario:
        st.session_state["usuario"] = usuario
    else:
        st.session_state["login_error"] = error
    st.rerun()


def _pantalla_login():
    """Pantalla de ingreso: selector de usuario + PIN."""
    # Pantalla limpia: sin barra lateral
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        usuarios = models.listar_usuarios_login()
    except Exception as e:
        st.error(f"{e}")
        st.stop()
    if not usuarios:
        st.warning("No hay usuarios activos configurados. Ejecutá sql/usuarios_auth.sql en Supabase.")
        st.stop()

    _, centro, _ = st.columns([1, 1.4, 1])
    with centro:
        st.markdown(
            f"<h1 style='text-align:center; margin-bottom:0;'>{config_negocio.get('nombre_negocio', 'Mi Comercio')}</h1>"
            "<p style='text-align:center; color:#64748B;'>Elegí tu usuario e ingresá tu PIN</p>",
            unsafe_allow_html=True,
        )

        iconos = {models.ROL_ADMIN: ":material/shield_person:", models.ROL_CAJERO: ":material/person:"}
        por_id = {u["id"]: u for u in usuarios}
        usuario_id = st.radio(
            "Usuario",
            options=list(por_id.keys()),
            format_func=lambda i: f"{iconos.get(por_id[i]['rol'], ':material/person:')} {por_id[i]['nombre']}",
            horizontal=True,
            key="login_usuario_id"
        )

        error = st.session_state.pop("login_error", None)
        if error:
            st.error(error)

        with st.form("form_login", clear_on_submit=True):
            pin_txt = st.text_input("Ingrese su PIN", type="password", max_chars=4)
            if st.form_submit_button("Ingresar", type="primary", width="stretch"):
                if not pin_txt:
                    st.session_state["login_error"] = "El PIN no puede estar vacío."
                    st.rerun()
                else:
                    _intentar_login(usuario_id, pin_txt)


def _pantalla_cambio_pin_obligatorio(usuario):
    """Quien entró con un PIN de ejemplo (1234 / 0000) elige uno propio antes de seguir."""
    _, centro, _ = st.columns([1, 1.4, 1])
    with centro:
        st.markdown("### Elegí tu PIN")
        st.warning("Entraste con un PIN de ejemplo. Por seguridad, elegí uno propio para continuar.")
        with st.form("form_pin_obligatorio", clear_on_submit=True):
            pin_actual_in = st.text_input("PIN actual", type="password", max_chars=4)
            pin_nuevo_in = st.text_input("PIN nuevo (4 dígitos)", type="password", max_chars=4)
            if st.form_submit_button("Guardar y entrar", type="primary", width="stretch"):
                try:
                    models.cambiar_pin(usuario["id"], pin_actual_in, pin_nuevo_in)
                    usuario["debe_cambiar_pin"] = False
                    st.rerun()
                except models.BusinessLogicError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"{e}")
        st.button("Cerrar sesión", on_click=_cerrar_sesion, width="stretch")


if not st.session_state.get("usuario"):
    _pantalla_login()
    st.stop()

if st.session_state["usuario"].get("debe_cambiar_pin"):
    _pantalla_cambio_pin_obligatorio(st.session_state["usuario"])
    st.stop()

usuario_actual = st.session_state["usuario"]
# Mínimo privilegio: cualquier rol que no sea 'admin' se trata como cajero
es_admin = usuario_actual.get("rol") == models.ROL_ADMIN
modulos_permitidos = MODULOS_ADMIN if es_admin else MODULOS_CAJERO


# ==============================================================================
# BARRA SUPERIOR: comercio, avisos, usuario y navegación.
# Reemplaza la barra lateral: ocupaba 300px fijos y en pantallas de 800-1100px
# (laptops con escala de Windows, tablets) aplastaba las columnas del contenido.
# ==============================================================================
ETIQUETAS_MODULOS = {
    ":material/point_of_sale: Punto de Venta (POS)": ":material/point_of_sale: Vender",
    ":material/group: Cuentas Corrientes / Clientes": ":material/group: Clientes",
    ":material/inventory_2: Productos e Inventario": ":material/inventory_2: Productos",
    ":material/sell: Categorías": ":material/sell: Categorías",
    ":material/bar_chart: Arqueo de Caja / Control Diario": ":material/bar_chart: Caja",
    ":material/settings: Configuración del Negocio": ":material/settings: Ajustes",
}

prods_criticos_global = models.obtener_productos_bajo_stock()
cant_criticos = len(prods_criticos_global)
resumen_deuda_global = models.obtener_resumen_deuda_total()

with st.container(key="barra_superior"):
    col_marca, col_acciones = st.columns([3, 2], vertical_alignment="center")
    with col_marca:
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            logo_barra = obtener_ruta_imagen_absoluta(config_negocio.get("logo_imagen_path"))
            if logo_barra:
                st.image(logo_barra, width=40)
            st.markdown(
                f"<span style='font-size:1.125rem; font-weight:700'>{html.escape(config_negocio.get('nombre_negocio', 'Mi Comercio'))}</span>",
                unsafe_allow_html=True,
            )

    with col_acciones:
        with st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center", gap="small"):
            if cant_criticos > 0:
                with st.popover(f"{cant_criticos} con stock bajo", icon=":material/warning:"):
                    for p_crit in prods_criticos_global:
                        st.markdown(
                            f"**{html.escape(str(p_crit['nombre']))}** · stock {fmt_cantidad(p_crit['stock_actual'])} "
                            f"(mín. {fmt_cantidad(p_crit['stock_minimo'])})"
                        )
            if resumen_deuda_global.get("total_deuda", 0) > 0:
                st.badge(f"Fiado: {fmt_moneda_md(resumen_deuda_global['total_deuda'])}",
                         icon=":material/account_balance_wallet:", color="orange")

            with st.popover(usuario_actual.get("nombre", ""), icon=":material/account_circle:"):
                st.caption(models.ROL_ETIQUETAS.get(usuario_actual.get("rol"), "Cajero"))
                with st.form("form_cambiar_pin", clear_on_submit=True):
                    st.markdown("**Cambiar mi PIN**")
                    pin_actual_in = st.text_input("PIN actual", type="password", max_chars=4)
                    pin_nuevo_in = st.text_input("PIN nuevo (4 dígitos)", type="password", max_chars=4)
                    if st.form_submit_button("Guardar PIN", width="stretch"):
                        try:
                            models.cambiar_pin(usuario_actual["id"], pin_actual_in, pin_nuevo_in)
                            st.success("PIN actualizado.")
                        except models.BusinessLogicError as e:
                            st.error(str(e))
                        except Exception as e:
                            st.error(f"No se pudo cambiar el PIN: {e}")
                st.button("Cerrar sesión", key="btn_logout", icon=":material/logout:",
                          width="stretch", on_click=_cerrar_sesion)

    modulo = st.segmented_control(
        "Sección",
        options=modulos_permitidos,
        format_func=lambda m: ETIQUETAS_MODULOS.get(m, m),
        default=modulos_permitidos[0],
        required=True,
        key="nav_modulo",
        label_visibility="collapsed",
        width="stretch",
    )

# Guardia defensiva: aunque el menú ya está filtrado, nunca se renderiza un módulo no permitido
if modulo not in modulos_permitidos:
    st.error("No tenés permisos para acceder a esta sección.")
    st.stop()


# ==============================================================================
# MÓDULO 1: PUNTO DE VENTA (POS) CON LECTOR DE BARRAS & CUENTA CORRIENTE
# ==============================================================================
if modulo == ":material/point_of_sale: Punto de Venta (POS)":
    st.header(":material/point_of_sale: Terminal de Punto de Venta")

    # Resumen del carrito siempre a la vista (en celular el carrito queda muy abajo)
    if st.session_state.carrito:
        _n_items = len(st.session_state.carrito)
        _total_carrito = sum(it["subtotal"] for it in st.session_state.carrito)
        st.info(f"**{_n_items} ítem(s)** · Total **{fmt_moneda_md(_total_carrito)}** — [Ir a cobrar ↓](#carrito-actual)",
                icon=":material/shopping_cart:")

    # 1. INTEGRACIÓN CON LECTORA DE CÓDIGO DE BARRAS (EAN / SKU)
    with st.form("form_barcode_scanner", clear_on_submit=True):
        col_scan_txt, col_scan_btn = st.columns([4, 1], gap="small", vertical_alignment="bottom")
        with col_scan_txt:
            barcode_in = st.text_input(
                "Código de barras",
                placeholder="Pase el lector óptico aquí o ingrese el código y presione Enter...",
                key="barcode_scanner_field"
            )
        with col_scan_btn:
            btn_scan = st.form_submit_button("Agregar", icon=":material/barcode_scanner:", width="stretch")

        if btn_scan and barcode_in:
            prod_esc = models.obtener_producto_por_codigo(barcode_in)
            if not prod_esc:
                st.error(f"Código '{barcode_in}' no registrado en el catálogo.")
            else:
                cant_en_cart = sum(it["cantidad"] for it in st.session_state.carrito if it["producto_id"] == prod_esc["id"])
                if prod_esc["stock_actual"] - cant_en_cart <= 0:
                    st.error(f"Stock insuficiente para '{prod_esc['nombre']}' (Stock actual: {prod_esc['stock_actual']}).")
                else:
                    encontrado = False
                    for it in st.session_state.carrito:
                        if it["producto_id"] == prod_esc["id"] and not it.get("es_canje"):
                            it["cantidad"] += 1
                            it["subtotal"] = round(it["cantidad"] * it["precio_unitario"], 2)
                            encontrado = True
                            break
                    if not encontrado:
                        st.session_state.carrito.append({
                            "producto_id": prod_esc["id"],
                            "codigo": prod_esc["codigo"],
                            "nombre": prod_esc["nombre"],
                            "precio_unitario": prod_esc["precio_venta"],
                            "cantidad": 1,
                            "subtotal": round(prod_esc["precio_venta"], 2),
                            "imagen_path": prod_esc.get("imagen_path"),
                            "puntos_canje": int(prod_esc.get("puntos_canje") or 0),
                            "es_canje": False,
                            "precio_original": prod_esc["precio_venta"]
                        })
                    st.toast(f"Agregado: {prod_esc['nombre']} x1 ({fmt_moneda_md(prod_esc['precio_venta'])})", icon=":material/shopping_cart:")
                    st.rerun()

    col_izq, col_der = st.columns([1, 1], gap="large")

    with col_izq:
        st.subheader("Buscar producto")

        productos_db = models.obtener_productos()
        if len(productos_db) == 0:
            st.warning("No hay productos registrados. Por favor, agregue productos en la sección de Inventario.")
        else:
            prods_todos = productos_db.to_dict('records') if hasattr(productos_db, "to_dict") else productos_db

            # 1. Filtro previo por Categoría
            categorias = models.obtener_categorias()
            opciones_cat = {"Todas las categorías": None}
            for c in categorias:
                opciones_cat[c["nombre"]] = c["id"]

            cat_seleccionada = st.selectbox(
                "Filtrar por Categoría:",
                options=list(opciones_cat.keys()),
                key="pos_filtro_cat"
            )
            cat_id_filtro = opciones_cat[cat_seleccionada]

            if cat_id_filtro is not None:
                prods_lista = [p for p in prods_todos if p.get("categoria_id") == cat_id_filtro]
            else:
                prods_lista = prods_todos

            if not prods_lista:
                st.info(f"ℹ️ No hay productos registrados en la categoría '{cat_seleccionada}'.")
            else:
                # 2. Selector de Producto limpio: únicamente Nombre - $Precio
                prod_info = st.selectbox(
                    "Seleccionar de la lista:",
                    options=prods_lista,
                    format_func=lambda p: f"{p['nombre']} - {fmt_moneda(p['precio_venta'])}",
                    key="pos_select_producto"
                )

                stock_actual = float(prod_info.get("stock_actual", 0))
                stock_minimo = float(prod_info.get("stock_minimo", 0))
                es_critico = stock_actual <= stock_minimo

                # 3. Ficha del producto elegido (la foto solo si existe)
                with st.container(border=True):
                    img_abs = obtener_ruta_imagen_absoluta(prod_info.get("imagen_path"))
                    if img_abs:
                        col_foto, col_datos = st.columns([1, 3], vertical_alignment="center")
                        col_foto.image(img_abs, width=96)
                    else:
                        col_datos = st.container()
                    with col_datos:
                        st.markdown(f"**{html.escape(str(prod_info['nombre']))}**")
                        st.caption(f"Código {prod_info['codigo']}")
                        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                            st.markdown(
                                f"<span style='font-size:1.375rem; font-weight:700'>{fmt_moneda(prod_info['precio_venta'])}</span>",
                                unsafe_allow_html=True,
                            )
                            if es_critico:
                                st.badge(f"Stock {fmt_cantidad(stock_actual)} · mín. {fmt_cantidad(stock_minimo)}",
                                         icon=":material/warning:", color="red")
                            else:
                                st.badge(f"Stock {fmt_cantidad(stock_actual)}", icon=":material/inventory:", color="green")

                cant_en_carrito = sum(
                    item["cantidad"] for item in st.session_state.carrito if item["producto_id"] == prod_info["id"]
                )
                disponible_para_agregar = stock_actual - cant_en_carrito
                
                # Un solo bloque vertical: primero la cantidad, debajo el botón Agregar
                col_cant = col_btn = st.container()
                with col_cant:
                    tipo_venta = st.radio("¿Vender por?", ["Cantidad / Peso", "Monto ($)"], horizontal=True)

                    if tipo_venta == "Cantidad / Peso":
                        # Accesos rápidos de peso/fracción de un clic (on_click: el callback se
                        # ejecuta antes del re-render, por eso puede modificar la key del widget)
                        # Grilla 2x2: con 4 en fila los textos se cortaban ("2..", "5..")
                        c_q1, c_q2 = st.columns(2)
                        c_q3, c_q4 = st.columns(2)
                        with c_q1:
                            st.button("250 g", key="btn_q_250", width="stretch",
                                      on_click=_set_pos_cant, args=(0.250,))
                        with c_q2:
                            st.button("500 g", key="btn_q_500", width="stretch",
                                      on_click=_set_pos_cant, args=(0.500,))
                        with c_q3:
                            st.button("1 kg", key="btn_q_1kg", width="stretch",
                                      on_click=_set_pos_cant, args=(1.000,))
                        with c_q4:
                            st.button("+1", key="btn_q_plus1", width="stretch",
                                      on_click=_sumar_pos_cant, args=(1.0,))

                        # Reseteo pendiente tras agregar al carrito (o key perdida): debe
                        # aplicarse ANTES de instanciar el widget.
                        if st.session_state.pop("_pos_reset_cant", False) or "pos_cant_val" not in st.session_state:
                            st.session_state["pos_cant_val"] = 1.0

                        cantidad = st.number_input(
                            "Cantidad / Peso:",
                            min_value=0.001,
                            step=1.0,
                            format="%g",
                            key="pos_cant_val"
                        )
                    else:
                        monto = st.number_input(
                            "Monto en plata ($):",
                            min_value=0.0,
                            value=None,
                            placeholder="Monto a cobrar...",
                            step=100.0,
                            key="pos_monto_input"
                        )
                        if monto and monto > 0 and prod_info["precio_venta"] > 0:
                            cantidad = round(monto / prod_info["precio_venta"], 4)
                            st.info(f"Equivale a **{fmt_cantidad(cantidad)}** unidades/kg")
                        else:
                            cantidad = 0.0

                with col_btn:
                    deshabilitar_agregar = (disponible_para_agregar <= 0) or (cantidad <= 0)
                    if st.button(":material/add: AGREGAR AL CARRITO", type="primary", disabled=deshabilitar_agregar, width="stretch"):
                        if disponible_para_agregar <= 0:
                            st.error("No hay más unidades disponibles de este producto.")
                        elif cantidad <= 0:
                            st.warning("Ingrese una cantidad o monto válido.")
                        else:
                            encontrado = False
                            for item in st.session_state.carrito:
                                if item["producto_id"] == prod_info["id"] and not item.get("es_canje"):
                                    item["cantidad"] += cantidad
                                    item["subtotal"] = round(item["cantidad"] * item["precio_unitario"], 2)
                                    encontrado = True
                                    break
                            if not encontrado:
                                st.session_state.carrito.append({
                                    "producto_id": prod_info["id"],
                                    "codigo": prod_info["codigo"],
                                    "nombre": prod_info["nombre"],
                                    "precio_unitario": prod_info["precio_venta"],
                                    "cantidad": cantidad,
                                    "subtotal": round(cantidad * prod_info["precio_venta"], 2),
                                    "imagen_path": prod_info.get("imagen_path"),
                                    "puntos_canje": int(prod_info.get("puntos_canje") or 0),
                                    "es_canje": False,
                                    "precio_original": prod_info["precio_venta"]
                                })
                            # Resetear cantidad a 1.0 para el siguiente artículo. El widget ya
                            # fue instanciado en este run, así que no se puede tocar su key
                            # acá: se deja una bandera que se aplica ANTES de dibujarlo.
                            st.session_state["_pos_reset_cant"] = True
                            st.toast(f"Agregado: {prod_info['nombre']} x{fmt_cantidad(cantidad)} ({fmt_moneda_md(cantidad * prod_info['precio_venta'])})", icon="")
                            st.rerun()

    # Panel derecho: Carrito de compras, Selector de Cliente, Medio de pago y Cobro
    with col_der:
        st.subheader("Carrito Actual")

        # 1. Selector opcional de Cliente en la cabecera del carrito
        clientes_pos = models.obtener_clientes()
        opciones_clientes = ["Consumidor Final"]
        mapa_clientes = {}
        for c in clientes_pos:
            lbl = f"{c['nombre']} (Tel: {c.get('telefono') or 'S/T'} | Deuda: {fmt_moneda(c['saldo_deudor'])})"
            opciones_clientes.append(lbl)
            mapa_clientes[lbl] = c

        cliente_elegido_label = st.selectbox(
            ":material/person: Cliente",
            opciones_clientes,
            help="Por defecto Consumidor Final. Seleccioná un cliente para asociar la venta, cuenta corriente o enviar comprobante por WhatsApp."
        )
        cliente_pos = mapa_clientes.get(cliente_elegido_label)
        cliente_pos_id = cliente_pos["id"] if cliente_pos else None

        if cliente_pos_id:
            pts_actual = round(float(cliente_pos.get('puntos') or 0), 2)
            pts_canjes_carrito = sum(
                int(round(it.get("puntos_canje", 0) * it.get("cantidad", 1)))
                for it in st.session_state.carrito if it.get("es_canje")
            )
            total_venta_previa = round(sum(item["subtotal"] for item in st.session_state.carrito), 2)
            pts_sumar = round(total_venta_previa * 0.01, 2)
            pts_restantes = pts_actual - pts_canjes_carrito
            color_saldo = "#16A34A" if pts_restantes >= 0 else "#DC2626"

            st.markdown(
                f"""
                <div style="background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%); border: 1.5px solid #3B82F6; border-radius: 9px; padding: 10px 14px; margin: 8px 0 12px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 700; color: #1E3A8A; font-size: 0.95rem;">Club de Puntos: {cliente_pos['nombre']}</span>
                        <span style="background: #2563EB; color: white; padding: 2px 10px; border-radius: 12px; font-weight: 800; font-size: 0.95rem;">{fmt_puntos(pts_actual)} pts</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px; font-size: 0.82rem; color: #1E40AF;">
                        <span>Canjes en carrito: <b>{fmt_puntos(pts_canjes_carrito)} pts</b></span>
                        <span>Saldo disponible: <b style="color: {color_saldo};">{fmt_puntos(pts_restantes)} pts</b></span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        # 2. Bloque de Comprobante / Ticket recién emitido (si existe)
        if "ultimo_ticket" in st.session_state and st.session_state["ultimo_ticket"]:
            tk = st.session_state["ultimo_ticket"]
            with st.container(border=True):
                st.markdown(f"#### Comprobante: Ticket #{tk['venta_id']}")
                st.caption(f"Cliente: **{tk['cliente_nombre']}** | Total: **{fmt_moneda_md(tk['total'])}** ({tk['forma_pago']})")

                c_pdf, c_wa = st.columns([1, 1], gap="small")
                with c_pdf:
                    st.download_button(
                        label=":material/download: Descargar Ticket (PDF 80mm)",
                        data=tk["pdf_bytes"],
                        file_name=f"ticket_{tk['venta_id']}.pdf",
                        mime="application/pdf",
                        width="stretch"
                    )
                with c_wa:
                    tel = tk.get("cliente_telefono")
                    if tel:
                        msg_whatsapp = reportes.armar_mensaje_whatsapp_ticket(tk)
                        wa_url = reportes.armar_url_whatsapp(tel, msg_whatsapp)
                        st.link_button(":material/send: Enviar por WhatsApp", url=wa_url, width="stretch")
                    else:
                        st.caption("ℹ️ Sin teléfono para WhatsApp")

                if st.button(":material/close: Cerrar Comprobante", key="btn_cerrar_tk", width="stretch"):
                    del st.session_state["ultimo_ticket"]
                    st.rerun()

        # 3. Lista de productos del carrito
        if not st.session_state.carrito:
            st.info("El carrito está vacío. Agregue artículos escaneando o desde el panel izquierdo.")
        else:
            for idx, item in enumerate(st.session_state.carrito):
                item.setdefault("puntos_canje", 0)
                item.setdefault("es_canje", False)
                item.setdefault("precio_original", item.get("precio_unitario", 0.0))

                es_canje_item = bool(item.get("es_canje", False))
                pts_unit = int(item.get("puntos_canje", 0))
                pts_tot_item = int(round(pts_unit * item.get("cantidad", 1)))

                with st.container(border=True):
                    c_img, c_info, c_sub, c_del = st.columns([0.6, 2.5, 1.4, 0.5], gap="small")
                    with c_img:
                        img_item = obtener_ruta_imagen_absoluta(item.get("imagen_path"))
                        if img_item:
                            st.image(img_item, width=44)
                        else:
                            st.markdown(":material/inventory_2:")
                    with c_info:
                        st.markdown(f"**{item['nombre']}** (`{item['codigo']}`)")
                        if es_canje_item:
                            st.markdown("<span style='background: #FEF3C7; color: #92400E; font-size: 0.75rem; font-weight: 700; padding: 2px 7px; border-radius: 4px; border: 1px solid #FDE68A;'>Canje por Puntos ($ 0,00)</span>", unsafe_allow_html=True)
                            st.caption(f"{fmt_cantidad(item['cantidad'])} unid. | Costo: {pts_tot_item} pts")
                        else:
                            st.caption(f"{fmt_cantidad(item['cantidad'])} unid. x {fmt_moneda_md(item['precio_unitario'])}")
                    with c_sub:
                        if es_canje_item:
                            st.markdown("<span style='color: #16A34A; font-weight: 800; font-size: 1.15rem;'>$ 0,00</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{fmt_moneda_md(item['subtotal'])}**")
                    with c_del:
                        if st.button(":material/close:", key=f"del_cart_{idx}"):
                            st.session_state.carrito.pop(idx)
                            st.rerun()

                    # Opción/Botón de Canje con Puntos
                    if pts_unit > 0:
                        c_canje_act, c_canje_txt = st.columns([1.5, 2.5], gap="small")
                        with c_canje_act:
                            if not es_canje_item:
                                if st.button(":material/redeem: Canjear con Puntos", key=f"btn_canje_{idx}", width="stretch"):
                                    if not cliente_pos:
                                        st.warning("Debés seleccionar un cliente registrado arriba para canjear con puntos.")
                                    else:
                                        pts_cli = round(float(cliente_pos.get("puntos") or 0), 2)
                                        otros_canjes = sum(
                                            int(round(it.get("puntos_canje", 0) * it.get("cantidad", 1)))
                                            for i, it in enumerate(st.session_state.carrito)
                                            if i != idx and it.get("es_canje")
                                        )
                                        pts_disponibles = pts_cli - otros_canjes
                                        if pts_disponibles < pts_tot_item:
                                            st.error(f"Puntos insuficientes: Se requieren {pts_tot_item} pts y {cliente_pos['nombre']} solo dispone de {pts_disponibles} pts.")
                                        else:
                                            item["es_canje"] = True
                                            item["precio_original"] = item.get("precio_original") or item["precio_unitario"]
                                            item["precio_unitario"] = 0.0
                                            item["subtotal"] = 0.0
                                            st.toast(f"Canje activado para {item['nombre']} ({pts_tot_item} pts)", icon=":material/redeem:")
                                            st.rerun()
                            else:
                                if st.button(":material/undo: Cancelar Canje", key=f"btn_cancel_canje_{idx}", width="stretch"):
                                    item["es_canje"] = False
                                    p_orig = float(item.get("precio_original") or 0.0)
                                    item["precio_unitario"] = p_orig
                                    item["subtotal"] = round(item["cantidad"] * p_orig, 2)
                                    st.toast(f"Canje cancelado para {item['nombre']}", icon=":material/info:")
                                    st.rerun()
                        with c_canje_txt:
                            if es_canje_item:
                                st.caption(f"Canjeando por **{pts_tot_item} pts**")
                            else:
                                st.caption(f"Requiere **{pts_tot_item} pts** ({pts_unit} pts c/u)")

            total_venta = round(sum(item["subtotal"] for item in st.session_state.carrito), 2)
            st.markdown(
                f"""
                <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; border-radius: 9px; padding: 10px 16px; margin: 10px 0; display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 1.05rem; font-weight: 700; color: #475569;">Total a Cobrar:</span>
                    <span style="font-size: 1.6rem; font-weight: 800; color: #0F172A;">{fmt_moneda(total_venta)}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Formas de Pago con opción de Cuenta Corriente / Fiado
            forma_pago = st.selectbox(
                "Forma de Pago:",
                [
                    "Efectivo",
                    "Mercado Pago / QR",
                    "Transferencia",
                    "Cuenta Corriente / Fiado",
                    "Tarjeta de Débito",
                    "Tarjeta de Crédito"
                ]
            )

            # Tarjeta de Datos Bancarios y QR
            if forma_pago in ["Mercado Pago / QR", "Transferencia"]:
                with st.container(border=True):
                    st.markdown("#### Datos para Cobro Electrónico")
                    col_qr_vista, col_banco_vista = st.columns([1, 1.5], gap="small")
                    with col_qr_vista:
                        qr_abs = obtener_ruta_imagen_absoluta(config_negocio.get("qr_imagen_path"))
                        if qr_abs:
                            st.image(qr_abs, caption="Escanear Código QR", width="stretch")
                        else:
                            st.info("Sin QR cargado en Configuración.")
                    with col_banco_vista:
                        st.markdown(f"**Titular:** {config_negocio.get('titular_cuenta', '-')}")
                        st.markdown(f"**Banco:** {config_negocio.get('banco', '-')}")
                        st.markdown(f"**Alias:** `{config_negocio.get('alias', '-')}`")
                        st.markdown(f"**CBU:** `{config_negocio.get('cbu', '-')}`")

            # CUENTA CORRIENTE / FIADO: Validar cliente y límite de crédito
            bloquear_venta_fiado = False

            if forma_pago == "Cuenta Corriente / Fiado":
                with st.container(border=True):
                    st.markdown("#### Asignar Venta a Cuenta Corriente")
                    if cliente_pos is None:
                        st.error("Para fiar en Cuenta Corriente debés seleccionar un cliente registrado arriba en el selector de 'Cliente' (no puede ser Consumidor Final).")
                        bloquear_venta_fiado = True
                    else:
                        saldo_previsto = cliente_pos["saldo_deudor"] + total_venta
                        col_c1, col_c2 = st.columns(2)
                        with col_c1:
                            st.markdown(f"**Saldo Actual:** {fmt_moneda_md(cliente_pos['saldo_deudor'])}")
                            st.markdown(f"**Límite Máximo:** {fmt_moneda_md(cliente_pos['limite_credito'])}" if cliente_pos['limite_credito'] > 0 else "**Límite:** Sin límite")
                        with col_c2:
                            st.markdown(f"**Saldo Tras la Venta:** **{fmt_moneda_md(saldo_previsto)}**")

                        if cliente_pos["limite_credito"] > 0 and saldo_previsto > cliente_pos["limite_credito"]:
                            st.error(f"**LÍMITE EXCEDIDO:** La venta superará el límite de crédito configurado ({fmt_moneda_md(cliente_pos['limite_credito'])}).")
                            bloquear_venta_fiado = True
                        else:
                            st.success(f"Venta autorizada a la cuenta de {cliente_pos['nombre']}.")

            # CANJE DE PREMIOS POR PUNTOS: Validar cliente y saldo suficiente
            bloquear_canje_puntos = False
            canjes_carrito = [it for it in st.session_state.carrito if it.get("es_canje")]
            if canjes_carrito:
                total_pts_pedidos = sum(
                    int(round(it.get("puntos_canje", 0) * it.get("cantidad", 1)))
                    for it in canjes_carrito
                )
                with st.container(border=True):
                    st.markdown("#### Canje de Premios con Puntos")
                    if cliente_pos is None:
                        st.error("Para canjear productos con puntos debés seleccionar un cliente registrado arriba en el selector de 'Cliente' (no puede ser Consumidor Final).")
                        bloquear_canje_puntos = True
                    else:
                        pts_cli = round(float(cliente_pos.get("puntos") or 0), 2)
                        c_p1, c_p2 = st.columns(2)
                        with c_p1:
                            st.markdown(f"**Puntos Acumulados:** {fmt_puntos(pts_cli)} pts")
                            st.markdown(f"**Puntos a Canjear:** {fmt_puntos(total_pts_pedidos)} pts")
                        with c_p2:
                            saldo_pts_post = pts_cli - total_pts_pedidos
                            color_pts = "#16A34A" if saldo_pts_post >= 0 else "#DC2626"
                            st.markdown(f"**Saldo Final:** <b style='color: {color_pts};'>{fmt_puntos(saldo_pts_post)} pts</b>", unsafe_allow_html=True)
                        if pts_cli < total_pts_pedidos:
                            st.error(f"**PUNTOS INSUFICIENTES:** Los canjes en el carrito suman {fmt_puntos(total_pts_pedidos)} pts y {cliente_pos['nombre']} solo posee {fmt_puntos(pts_cli)} pts acumulados. Cancelá el canje o ajustá la cantidad.")
                            bloquear_canje_puntos = True
                        else:
                            st.success(f"Canje autorizado: Se descontarán {fmt_puntos(total_pts_pedidos)} puntos de la cuenta de {cliente_pos['nombre']}.")

            st.write("")
            col_btn_vender, col_btn_vaciar = st.columns([2.5, 1], gap="small")
            with col_btn_vaciar:
                if st.button(":material/delete: Vaciar", width="stretch"):
                    st.session_state.carrito = []
                    st.rerun()
            with col_btn_vender:
                boton_deshabilitado = bloquear_venta_fiado or bloquear_canje_puntos
                with st.container(key="btn_cobrar"):
                    cobrar = st.button(f":material/check_circle: CONFIRMAR Y COBRAR ({fmt_moneda_md(total_venta)})", type="primary", disabled=boton_deshabilitado, width="stretch")
                if cobrar:

                    try:
                        items_venta = [
                            {
                                "producto_id": it["producto_id"],
                                "cantidad": it["cantidad"],
                                "es_canje": it.get("es_canje", False),
                                "puntos_canje": it.get("puntos_canje", 0)
                            }
                            for it in st.session_state.carrito
                        ]
                        items_ticket = [dict(it) for it in st.session_state.carrito]
                        total_ticket = total_venta
                        fecha_ticket = datetime.now(ZONA_HORARIA).strftime("%d/%m/%Y %H:%M")
                        nombre_cli_tk = cliente_pos["nombre"] if cliente_pos else "Consumidor Final"

                        puntos_canjeados = sum(
                            int(round(it.get("puntos_canje", 0) * it.get("cantidad", 1)))
                            for it in st.session_state.carrito if it.get("es_canje")
                        )

                        with st.spinner("Registrando la venta..."):
                            venta_id, puntos_ganados = models.registrar_venta(
                                items=items_venta,
                                forma_pago=forma_pago,
                                cliente_id=cliente_pos_id
                            )

                        puntos_balance = 0
                        if cliente_pos_id:
                            models.get_clientes.clear()
                            models.obtener_clientes.clear()
                            cli_upd = next((c for c in models.obtener_clientes() if c["id"] == cliente_pos_id), None)
                            if cli_upd:
                                puntos_balance = round(float(cli_upd.get("puntos") or 0), 2)

                        # Generar comprobante en PDF formato térmico 80 mm
                        datos_tk = {
                            "venta_id": venta_id,
                            "fecha_hora": fecha_ticket,
                            "cliente_nombre": nombre_cli_tk,
                            "forma_pago": forma_pago,
                            "items": items_ticket,
                            "total_venta": total_ticket,
                            "puntos_ganados": puntos_ganados,
                            "puntos_balance": puntos_balance,
                            "puntos_canjeados": puntos_canjeados,
                            "direccion_negocio": config_negocio.get("direccion", ""),
                            "telefono_negocio": config_negocio.get("telefono", "")
                        }
                        pdf_bytes = reportes.generar_pdf_ticket_termico(
                            datos_tk,
                            nombre_negocio=config_negocio.get("nombre_negocio", "Mi Comercio")
                        )

                        st.session_state["ultimo_ticket"] = {
                            "venta_id": venta_id,
                            "pdf_bytes": pdf_bytes,
                            "total": total_ticket,
                            "fecha": fecha_ticket,
                            "forma_pago": forma_pago,
                            "cliente_nombre": nombre_cli_tk,
                            "cliente_telefono": cliente_pos.get("telefono") if cliente_pos else None,
                            "negocio_nombre": config_negocio.get("nombre_negocio", "Mi Comercio"),
                            "puntos_ganados": puntos_ganados,
                            "puntos_balance": puntos_balance,
                            "puntos_canjeados": puntos_canjeados
                        }

                        st.session_state.carrito = []
                        st.balloons()
                        st.success(f"¡Venta #{venta_id} confirmada por {fmt_moneda_md(total_ticket)} ({forma_pago})!")
                        st.rerun()
                    except models.InsufficientStockError as err:
                        st.error(f"Stock insuficiente: {err}")
                    except Exception as err:
                        st.error(f"Error al registrar la venta: {err}")


# ==============================================================================
# MÓDULO 2: CUENTAS CORRIENTES / CLIENTES ("LA LIBRETA")
# ==============================================================================
elif modulo == ":material/group: Cuentas Corrientes / Clientes":
    st.header(":material/group: Cuentas Corrientes / Clientes (\"La Libreta\")")
    st.caption("Control de fiados, límites de crédito, registro de abonos e historial de cuenta por cliente.")

    # Resumen Financiero de Cuentas Corrientes
    resumen_deuda = models.obtener_resumen_deuda_total()
    col_k1, col_k2, col_k3 = st.columns(3)
    col_k1.metric(":material/account_balance_wallet: Deuda Total en la Calle", f"{fmt_moneda(resumen_deuda.get('total_deuda', 0.0))}")
    col_k2.metric(":material/warning: Clientes con Deuda Activa", f"{resumen_deuda.get('clientes_con_deuda', 0)} clientes")
    col_k3.metric(":material/person: Clientes Registrados", f"{resumen_deuda.get('total_clientes', 0)}")

    st.markdown("---")

    _tabs_clientes = [
        ":material/menu_book: Libreta de Clientes",
        ":material/person_add: Nuevo Cliente",
        ":material/payments: Registrar Abono / Pago",
        ":material/history: Ficha e Historial de Movimientos",
    ]
    if es_admin:
        _tabs_clientes.append(":material/edit: Modificar / Dar de baja")
    _tabs_obj = st.tabs(_tabs_clientes)
    tab_c_lista, tab_c_nuevo, tab_c_abono, tab_c_ficha = _tabs_obj[:4]
    tab_c_edit = _tabs_obj[4] if es_admin else None

    # 1. Catálogo / Libreta de Clientes
    with tab_c_lista:
        busqueda_cli = st.text_input(":material/search: Buscar cliente por nombre o teléfono:", "")
        clientes = models.obtener_clientes(busqueda=busqueda_cli or None)

        if not clientes:
            st.info("No se encontraron clientes registrados.")
        else:
            for c in clientes:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 1.5, 1.5, 1.5])
                    with c1:
                        st.markdown(f"### {c['nombre']}")
                        tel_txt = c['telefono'] or "Sin teléfono"
                        if reportes.normalizar_tel_ar(c['telefono']):  # sin número completo, sin link
                            tel_vis = str(c['telefono']).replace('[', '').replace(']', '')
                            tel_txt = f"[{tel_vis}]({reportes.armar_url_whatsapp(c['telefono'], '')})"
                        st.caption(f":material/call: {tel_txt} · :material/mail: {c['email'] or 'Sin correo'}")
                    with c2:
                        limite_txt = f"{fmt_moneda_md(c['limite_credito'])}" if c['limite_credito'] > 0 else "Sin límite"
                        st.markdown(f"**Límite de Crédito:** {limite_txt}")
                    with c3:
                        if c["saldo_deudor"] > 0:
                            st.badge(f"Debe {fmt_moneda_md(c['saldo_deudor'])}", icon=":material/error:", color="red")
                        else:
                            st.badge("Al día", icon=":material/check_circle:", color="green")
                    with c4:
                        st.markdown(f"**Puntos:** {fmt_puntos(c.get('puntos', 0))}")
    # 2. Alta de Cliente
    with tab_c_nuevo:
        st.subheader("Registrar Nuevo Cliente")
        with st.form("form_nuevo_cliente", clear_on_submit=True):
            col_nc1, col_nc2 = st.columns(2)
            with col_nc1:
                nom_cli = st.text_input("Nombre y Apellido *", placeholder="Ej: Carlos Gómez")
                tel_cli = st.text_input("Teléfono / WhatsApp", placeholder="Ej: 11-5555-1234")
            with col_nc2:
                mail_cli = st.text_input("Correo Electrónico (Opcional)", placeholder="carlos@email.com")
                limite_cli = st.number_input(
                    "Límite de Crédito ($)",
                    min_value=0.0,
                    value=0.0,
                    step=5000.0,
                    help="0 = Sin límite de crédito establecido."
                )

            btn_crear_cli = st.form_submit_button(":material/save: Guardar Cliente", type="primary")
            if btn_crear_cli:
                try:
                    nuevo_cid = models.crear_cliente(
                        nombre=nom_cli,
                        telefono=tel_cli,
                        email=mail_cli,
                        limite_credito=limite_cli
                    )
                    st.success(f"¡Cliente '{nom_cli}' registrado con éxito! (ID: {nuevo_cid})")
                    st.rerun()
                except models.BusinessLogicError as e:
                    st.error(f"Error de validación: {e}")
                except Exception as e:
                    st.error(f"Error inesperado: {e}")

    # 3. Registrar Abono / Pago
    with tab_c_abono:
        st.subheader(":material/payments: Registrar Pago o Abono a Cuenta Corriente")
        clientes_abono = models.obtener_clientes()
        if not clientes_abono:
            st.info("No hay clientes registrados.")
        else:
            dict_cli_abono = {
                f"{c['nombre']} (Saldo Deudor: {fmt_moneda(c['saldo_deudor'])})": c
                for c in clientes_abono
            }
            sel_cli_abono = st.selectbox("Seleccione el Cliente:", list(dict_cli_abono.keys()), key="select_cli_abono")
            cli_a_abonar = dict_cli_abono[sel_cli_abono]

            with st.container(border=True):
                st.markdown(f"#### Ficha: {cli_a_abonar['nombre']}")
                st.markdown(f"**Deuda Actual:** :red[**{fmt_moneda_md(cli_a_abonar['saldo_deudor'])}**]")

                col_ab1, col_ab2 = st.columns(2)
                with col_ab1:
                    monto_abono = st.number_input(
                        "Monto del Abono / Pago ($) *",
                        min_value=1.0,
                        max_value=max(1.0, float(cli_a_abonar["saldo_deudor"])) if cli_a_abonar["saldo_deudor"] > 0 else 1000000.0,
                        value=float(cli_a_abonar["saldo_deudor"]) if cli_a_abonar["saldo_deudor"] > 0 else 1000.0,
                        step=500.0,
                        format="%.2f"
                    )
                    metodo_abono = st.selectbox("Forma de Pago del Abono:", ["Efectivo", "Transferencia", "Mercado Pago", "Tarjeta"])
                with col_ab2:
                    nuevo_saldo_previsto = max(0.0, cli_a_abonar["saldo_deudor"] - monto_abono)
                    st.markdown("#### Balance Estimado:")
                    st.markdown(f"**Saldo Restante:** :green[**{fmt_moneda_md(nuevo_saldo_previsto)}**]")
                    nota_abono = st.text_input("Nota / Comprobante (Opcional):", placeholder="Ej: Pago parcial efectivo")

                if st.button(":material/check_circle: Confirmar y Registrar Abono", type="primary"):
                    try:
                        mov_id = models.registrar_abono_cliente(
                            cliente_id=cli_a_abonar["id"],
                            monto=monto_abono,
                            metodo_pago=metodo_abono,
                            descripcion=nota_abono or None
                        )
                        st.success(f"Abono registrado con éxito (#{mov_id}) por {fmt_moneda_md(monto_abono)}. Nuevo saldo: {fmt_moneda_md(nuevo_saldo_previsto)}")
                        st.rerun()
                    except models.BusinessLogicError as e:
                        st.error(f"Error: {e}")
                    except Exception as e:
                        st.error(f"Error al registrar abono: {e}")

    # 4. Ficha e Historial Cronológico
    with tab_c_ficha:
        st.subheader(":material/history: Historial de Cuenta Corriente")
        clientes_ficha = models.obtener_clientes()
        if not clientes_ficha:
            st.info("No hay clientes registrados.")
        else:
            dict_cli_ficha = {f"{c['nombre']} ({fmt_moneda(c['saldo_deudor'])})": c for c in clientes_ficha}
            sel_ficha = st.selectbox("Seleccione el cliente a consultar:", list(dict_cli_ficha.keys()), key="sel_ficha_cli")
            cli_f = dict_cli_ficha[sel_ficha]

            with st.container(border=True):
                c_f1, c_f2, c_f3, c_f4 = st.columns([2, 1.5, 1.5, 1.5])
                c_f1.markdown(f"**Cliente:** {cli_f['nombre']}")
                c_f1.caption(f":material/call: {cli_f['telefono'] or 'Sin teléfono'} · :material/mail: {cli_f['email'] or 'S/E'}")
                c_f2.markdown(f"**Límite de Crédito:** {fmt_moneda_md(cli_f['limite_credito'])}" if cli_f['limite_credito'] > 0 else "**Límite:** Sin límite")
                c_f3.markdown(f"**Saldo Deudor:** :red[**{fmt_moneda_md(cli_f['saldo_deudor'])}**]" if cli_f['saldo_deudor'] > 0 else f"**Saldo Deudor:** :green[**{fmt_moneda_md(0)}**]")
                c_f4.markdown(f"**Puntos:** {fmt_puntos(cli_f.get('puntos', 0))}")

            movimientos = models.obtener_movimientos_cliente(cli_f["id"])
            if not movimientos:
                st.info("Este cliente no tiene movimientos registrados aún.")
            else:
                df_movs = pd.DataFrame(movimientos)
                df_movs["tipo_fmt"] = df_movs["tipo"].map({"CARGO": "Cargo (compra fiada)", "PAGO": "Pago (abono)"})
                df_movs["monto_fmt"] = df_movs["monto"].apply(lambda x: f"{fmt_moneda(x)}")
                df_movs["fecha_hora"] = pd.to_datetime(df_movs["fecha_hora"], utc=True).dt.tz_convert(ZONA_HORARIA).dt.strftime("%d/%m/%Y %H:%M")
                
                df_mostrar = df_movs[["fecha_hora", "tipo_fmt", "monto_fmt", "descripcion", "ticket_id"]].rename(
                    columns={
                        "fecha_hora": "Fecha y Hora",
                        "tipo_fmt": "Tipo de Movimiento",
                        "monto_fmt": "Monto",
                        "descripcion": "Detalle / Concepto",
                        "ticket_id": "Ticket #"
                    }
                )
                st.dataframe(df_mostrar, width="stretch", hide_index=True)

    # 5. Edición y Baja de Clientes
    if tab_c_edit is not None:  # Solo el Dueño ve esta solapa
        with tab_c_edit:
            st.subheader(":material/edit: Modificar o Dar de Baja Cliente")
            clientes_edit = models.obtener_clientes()
            if not clientes_edit:
                st.info("No hay clientes registrados.")
            else:
                dict_cli_edit = {f"{c['nombre']} (ID: {c['id']})": c for c in clientes_edit}
                sel_cli_ed = st.selectbox("Seleccione el cliente a editar:", list(dict_cli_edit.keys()), key="sel_cli_ed")
                cli_ed = dict_cli_edit[sel_cli_ed]
                cid = cli_ed["id"]

                with st.form(f"form_edit_cli_{cid}"):
                    c_ed1, c_ed2 = st.columns(2)
                    with c_ed1:
                        e_nom = st.text_input("Nombre y Apellido *", value=cli_ed["nombre"])
                        e_tel = st.text_input("Teléfono / WhatsApp", value=cli_ed["telefono"])
                    with c_ed2:
                        e_mail = st.text_input("Correo Electrónico", value=cli_ed["email"])
                        e_limite = st.number_input("Límite de Crédito ($)", min_value=0.0, value=float(cli_ed["limite_credito"]), step=5000.0)

                    btn_guardar_cli = st.form_submit_button(":material/save: Guardar Cambios de Cliente", type="primary")
                    if btn_guardar_cli:
                        try:
                            models.actualizar_cliente(cid, e_nom, e_tel, e_mail, e_limite)
                            st.success("Datos del cliente actualizados.")
                            st.rerun()
                        except models.BusinessLogicError as e:
                            st.error(f"Error: {e}")

                with st.expander("Dar de baja cliente"):
                    st.info("Se oculta de las listas y conserva su historial de cuenta corriente. "
                            "Se puede reactivar. Solo clientes sin deuda ($ 0,00).")
                    chk_del_cli = st.checkbox("Confirmo dar de baja a este cliente", key=f"chk_del_c_{cid}")
                    if st.button("Dar de baja", type="secondary", disabled=not chk_del_cli, key=f"btn_del_c_{cid}"):
                        try:
                            models.eliminar_cliente(cid)
                            st.success("Cliente dado de baja.")
                            st.rerun()
                        except models.BusinessLogicError as e:
                            st.error(f"No se pudo dar de baja: {e}")

            _seccion_dados_de_baja("clientes", "Clientes dados de baja")


# ==============================================================================
# MÓDULO 3: GESTIÓN DE PRODUCTOS E INVENTARIO
# ==============================================================================
elif modulo == ":material/inventory_2: Productos e Inventario":
    st.header(":material/inventory_2: Gestión de Productos e Inventario")

    # Mensaje de confirmación de la acción anterior (sobrevive al st.rerun())
    if "flash_inventario" in st.session_state:
        st.success(st.session_state.pop("flash_inventario"))

    tab_catalogo, tab_nuevo, tab_editar, tab_ajuste, tab_alertas, tab_masiva = st.tabs([
        ":material/list: Catálogo de Productos",
        ":material/add_box: Nuevo Producto",
        ":material/edit: Editar Producto",
        ":material/sync_alt: Ajuste de Stock",
        ":material/warning: Monitor de Stock Crítico",
        ":material/upload_file: Carga Masiva"
    ])

    # 1. Catálogo Completo
    with tab_catalogo:
        categorias = models.obtener_categorias()
        
        with st.expander(":material/trending_up: Actualización Masiva de Precios"):
            st.markdown("Aplica un aumento o descuento porcentual a todos los productos o a una categoría específica.")
            
            with st.form("form_act_masiva"):
                col_m1, col_m2, col_m3 = st.columns([1.5, 1, 1])
                with col_m1:
                    opciones_cat_mas = {"Todas las categorías": None}
                    for c in categorias:
                        opciones_cat_mas[c["nombre"]] = c["id"]
                    cat_masiva = st.selectbox("Categoría a actualizar", list(opciones_cat_mas.keys()), key="cat_masiva")
                with col_m2:
                    porcentaje = st.number_input("Porcentaje de ajuste (%)", value=0.0, step=1.0, help="Ej: 10 para aumentar 10%, -5 para descontar 5%.")
                with col_m3:
                    redondeo = st.selectbox("Redondear a", ["Sin redondear", "Múltiplo de 10", "Múltiplo de 50", "Múltiplo de 100"], index=0)
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    simular = st.form_submit_button(":material/search: Simular / Previsualizar", width="stretch")
                with col_btn2:
                    aplicar = st.form_submit_button(":material/check_circle: Aplicar Aumento Masivo", type="primary", width="stretch")

            cat_id_masiva = opciones_cat_mas[cat_masiva]
            
            if simular or aplicar:
                if porcentaje == 0:
                    st.warning("El porcentaje de ajuste no puede ser 0.")
                else:
                    prods_obj = models.obtener_productos(categoria_id=cat_id_masiva)
                    prods_masivos = prods_obj.to_dict('records') if hasattr(prods_obj, "to_dict") else prods_obj
                    
                    if not prods_masivos:
                        st.info("No se encontraron productos para aplicar el ajuste.")
                    else:
                        modificados = []
                        lista_preview = []
                        
                        factor = 1 + (porcentaje / 100.0)
                        for p in prods_masivos:
                            nuevo_costo = float(p["precio_costo"]) * factor
                            usa_manual = bool(p.get("usa_precio_manual", False))
                            margen = float(p["margen_ganancia"])
                            
                            if usa_manual:
                                nuevo_venta = float(p["precio_venta"]) * factor
                            else:
                                nuevo_venta = nuevo_costo * (1 + margen / 100.0)
                            
                            if redondeo != "Sin redondear":
                                multi = 10 if "10" in redondeo else 50 if "50" in redondeo else 100
                                nuevo_venta = round(nuevo_venta / multi) * multi
                            else:
                                nuevo_venta = round(nuevo_venta, 2)
                            
                            nuevo_costo = round(nuevo_costo, 2)
                                
                            modificados.append({
                                "id": p["id"],
                                "precio_costo": nuevo_costo,
                                "precio_venta": nuevo_venta,
                                "margen_ganancia": margen,
                                "usa_precio_manual": usa_manual
                            })
                            
                            lista_preview.append({
                                "Producto": p["nombre"],
                                "Precio Actual": f"{fmt_moneda(float(p['precio_venta']))}",
                                "Nuevo Precio": f"{fmt_moneda(nuevo_venta)}",
                                "Diferencia": f"{fmt_moneda((nuevo_venta - float(p['precio_venta'])))}"
                            })
                        
                        if simular:
                            st.markdown(f"**Previsualización de {len(lista_preview)} producto(s) a modificar:**")
                            st.dataframe(pd.DataFrame(lista_preview), width="stretch", hide_index=True)
                            
                        if aplicar:
                            comercio_id_actual = usuario_actual.get("comercio_id", models.COMERCIO_ID_DEFAULT)
                            exitosos = models.actualizar_precios_masivamente(modificados, comercio_id=comercio_id_actual)
                            st.session_state["flash_inventario"] = f"¡Aumento masivo aplicado con éxito! Se actualizaron {exitosos} productos."
                            st.rerun()

        col_filtro1, col_filtro2, col_filtro3, col_exp = st.columns([1.8, 1.1, 1, 1.1], gap="small")
        with col_filtro1:
            busqueda = st.text_input(":material/search: Buscar por nombre o código / barra:", "")
        with col_filtro2:
            opciones_cat = {"Todas las categorías": None}
            for c in categorias:
                opciones_cat[c["nombre"]] = c["id"]
            cat_seleccionada = st.selectbox("Filtrar por Categoría:", list(opciones_cat.keys()))
            cat_id_filtro = opciones_cat[cat_seleccionada]
        with col_filtro3:
            opciones_vista = ["Compacta", "Tarjetas", "Tabla"]
            valor_actual = st.session_state.get("inv_vista_ficha", "Compacta")
            vista_idx = opciones_vista.index(valor_actual) if valor_actual in opciones_vista else 0
            vista_elegida = st.selectbox("Vista del Catálogo:", opciones_vista, index=vista_idx, key="inv_vista_ficha_sel")
            st.session_state.inv_vista_ficha = vista_elegida
        with col_exp:
            st.write('<div style="height: 28px;"></div>', unsafe_allow_html=True)
            fecha_export = datetime.now(ZONA_HORARIA).strftime("%d-%m-%Y")
            todos_para_exp = models.obtener_productos(comercio_id=usuario_actual.get("comercio_id", models.COMERCIO_ID_DEFAULT))
            excel_bytes = models.generar_excel_inventario(todos_para_exp)
            st.download_button(
                label=":material/download: Exportar a Excel",
                data=excel_bytes,
                file_name=f"inventario_productos_{fecha_export}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
                help="Exportar el inventario completo a un archivo .xlsx"
            )

        productos = models.obtener_productos(busqueda=busqueda or None, categoria_id=cat_id_filtro)

        if productos:
            if vista_elegida == "Tabla":
                cols_tabla = ["codigo", "nombre", "categoria_nombre", "precio_costo", "margen_ganancia", "precio_venta", "stock_actual", "stock_minimo", "puntos_canje"]
                df_prods = pd.DataFrame(productos)[cols_tabla]
                df_prods.rename(columns={
                    "codigo": "Código", "nombre": "Producto", "categoria_nombre": "Categoría",
                    "precio_costo": "Costo ($)", "margen_ganancia": "Margen (%)", 
                    "precio_venta": "Venta ($)", "stock_actual": "Stock", "stock_minimo": "Mínimo",
                    "puntos_canje": "Puntos Canje"
                }, inplace=True)
                st.dataframe(formatear_df(df_prods, monedas=["Costo ($)", "Venta ($)"],
                                          cantidades=["Margen (%)", "Stock", "Mínimo"],
                                          puntos=[c for c in ["Puntos Canje"] if c in df_prods.columns]),
                             width="stretch", hide_index=True)
            elif vista_elegida == "Tarjetas":
                # Grilla de 3 columnas (st.columns(3))
                columnas = st.columns(3)
                for i, p in enumerate(productos):
                    with columnas[i % 3].container(border=True):
                        # Imagen destacada arriba (tamaño mediano/visible)
                        img_prod = obtener_ruta_imagen_absoluta(p.get("imagen_path") or p.get("imagen_url"))
                        if img_prod:
                            st.image(img_prod, width="stretch")
                        else:
                            st.markdown(
                                """<div style="height: 140px; background-color: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #94a3b8; margin-bottom: 8px;">
                                    <span style="font-size: 0.9rem;">Sin foto</span>
                                    
                                </div>""",
                                unsafe_allow_html=True
                            )

                        nombre_esc = html.escape(str(p.get("nombre", "")))
                        cat_esc = html.escape(str(p.get("categoria_nombre") or p.get("categoria") or "General"))
                        cod_esc = html.escape(str(p.get("codigo", "S/C")))
                        precio_venta = float(p.get("precio_venta", 0))
                        stock_actual = float(p.get("stock_actual", 0))
                        stock_minimo = float(p.get("stock_minimo", 0))
                        puntos_canje = int(p.get("puntos_canje") or 0)
                        canje_html = f'<span style="background-color: #fef3c7; color: #92400e; padding: 2px 7px; border-radius: 12px; font-size: 0.72rem; font-weight: 700; border: 1px solid #fde68a; margin-left: 6px;">{puntos_canje} pts</span>' if puntos_canje > 0 else ''

                        # Nombre del producto
                        st.markdown(f"<div style='font-weight: 700; font-size: 1.05rem; color: #0f172a; margin-top: 6px; line-height: 1.3;'>{nombre_esc}</div>", unsafe_allow_html=True)

                        # Badge de categoría y código
                        st.markdown(
                            f"""<div style="margin: 4px 0 6px 0;">
                                <span style="background-color: #eff6ff; color: #1d4ed8; padding: 2px 8px; border-radius: 12px; font-size: 0.72rem; font-weight: 600; border: 1px solid #bfdbfe;">{cat_esc}</span>
                                <span style="color: #64748b; font-size: 0.72rem; margin-left: 6px;">Cod: {cod_esc}</span>
                                {canje_html}
                            </div>""",
                            unsafe_allow_html=True
                        )

                        # Precio en grande
                        st.markdown(
                            f"""<div style="font-size: 1.45rem; font-weight: 800; color: #0f172a; margin: 4px 0;">
                                {fmt_moneda(precio_venta)}
                            </div>""",
                            unsafe_allow_html=True
                        )

                        # Stock
                        if stock_actual <= stock_minimo:
                            st.markdown(
                                f"""<div style="background-color: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; padding: 5px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; margin-top: 4px;">
                                    Stock: {fmt_cantidad(stock_actual)} (Mín: {fmt_cantidad(stock_minimo)})
                                </div>""",
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                f"""<div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; padding: 5px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; margin-top: 4px;">
                                    Stock: {fmt_cantidad(stock_actual)} (Mín: {fmt_cantidad(stock_minimo)})
                                </div>""",
                                unsafe_allow_html=True
                            )
            else: # Compacta
                css_compacto = textwrap.dedent("""
                <style>
                [data-testid="stHtml"] {
                    margin: 0 !important;
                    padding: 0 !important;
                }
                .inv-cp-row {
                    display: flex;
                    flex-wrap: wrap;          /* si no entra, stock y precio pasan a una segunda línea */
                    align-items: center;
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                    padding: 3px 12px;
                    min-height: 42px;
                    box-sizing: border-box;
                    transition: all 0.15s ease-in-out;
                    gap: 12px;
                    margin-bottom: 3px;
                    width: 100%;
                }
                .inv-cp-row:hover {
                    background-color: #f8fafc;
                    border-color: #cbd5e1;
                    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
                }
                .inv-cp-thumb {
                    width: 36px;
                    height: 36px;
                    min-width: 36px;
                    max-width: 45px;
                    border-radius: 5px;
                    overflow: hidden;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background-color: #f1f5f9;
                    flex-shrink: 0;
                    border: 1px solid #e2e8f0;
                }
                .inv-cp-thumb img {
                    width: 100%;
                    height: 100%;
                    object-fit: cover;
                }
                .inv-cp-info {
                    flex: 1 1 12rem;
                    min-width: 0;
                    display: flex;
                    flex-wrap: wrap;          /* en pantallas angostas, categoría y código pasan abajo */
                    align-items: center;
                    gap: 4px 8px;
                    overflow: hidden;
                }
                .inv-cp-title {
                    flex: 1 1 10rem;          /* el nombre nunca se achica a cero */
                    font-weight: 600;
                    font-size: 0.92rem;
                    color: #0f172a;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .inv-cp-badge {
                    background-color: #eff6ff;
                    color: #1d4ed8;
                    font-size: 0.72rem;
                    font-weight: 600;
                    padding: 1px 7px;
                    border-radius: 9999px;
                    white-space: nowrap;
                    flex-shrink: 0;
                    border: 1px solid #dbeafe;
                }
                .inv-cp-code {
                    color: #64748b;
                    font-size: 0.75rem;
                    white-space: nowrap;
                    flex-shrink: 0;
                }
                .inv-cp-end {
                    display: flex;
                    align-items: center;
                    gap: 16px;
                    flex-shrink: 0;
                    margin-left: auto;
                }
                .inv-cp-stock {
                    font-size: 0.78rem;
                    font-weight: 600;
                    padding: 2px 8px;
                    border-radius: 4px;
                    white-space: nowrap;
                }
                .inv-cp-stock-ok {
                    background-color: #f0fdf4;
                    color: #166534;
                    border: 1px solid #bbf7d0;
                }
                .inv-cp-stock-critico {
                    background-color: #fef2f2;
                    color: #b91c1c;
                    border: 1px solid #fecaca;
                }
                .inv-cp-price {
                    font-size: 1.02rem;
                    font-weight: 700;
                    color: #0f172a;
                    white-space: nowrap;
                    min-width: 90px;
                    text-align: right;
                }
                </style>
                """).strip()
                st.markdown(css_compacto, unsafe_allow_html=True)

                for p in productos:
                    img_src = obtener_src_imagen_html(p.get("imagen_path") or p.get("imagen_url"))
                    nombre_esc = html.escape(str(p.get("nombre", "")))
                    cod_esc = html.escape(str(p.get("codigo", "")))
                    cat_esc = html.escape(str(p.get("categoria_nombre") or p.get("categoria") or "General"))
                    precio_val = float(p.get("precio_venta", 0))
                    stock_act = float(p.get("stock_actual", 0))
                    stock_min = float(p.get("stock_minimo", 0))
                    es_critico = stock_act <= stock_min

                    if img_src:
                        thumb_html = f'<div class="inv-cp-thumb"><img src="{img_src}" alt="" loading="lazy" /></div>'
                    else:
                        thumb_html = ''  # sin foto no se dibuja un recuadro vacío

                    stock_badge = (
                        f'<span class="inv-cp-stock inv-cp-stock-critico" title="Stock Crítico (Mín: {fmt_cantidad(stock_min)})">Stock bajo: {fmt_cantidad(stock_act)}</span>'
                        if es_critico
                        else f'<span class="inv-cp-stock inv-cp-stock-ok" title="Stock Normal (Mín: {fmt_cantidad(stock_min)})">Stock: {fmt_cantidad(stock_act)}</span>'
                    )

                    pts_canje_val = int(p.get("puntos_canje") or 0)
                    canje_badge = (
                        f'<span class="inv-cp-badge" style="background-color: #fef3c7; color: #92400e; border: 1px solid #fde68a;" title="Premio por Puntos">Canje: {pts_canje_val} pts</span>'
                        if pts_canje_val > 0 else ''
                    )

                    fila_html = (
                        f'<div class="inv-cp-row">'
                        f'{thumb_html}'
                        f'<div class="inv-cp-info">'
                        f'<span class="inv-cp-title" title="{nombre_esc}">{nombre_esc}</span>'
                        f'<span class="inv-cp-badge" title="Categoría">{cat_esc}</span>'
                        f'<span class="inv-cp-code" title="Código">#{cod_esc}</span>'
                        f'{canje_badge}'
                        f'</div>'
                        f'<div class="inv-cp-end">'
                        f'{stock_badge}'
                        f'<span class="inv-cp-price">{fmt_moneda(precio_val)}</span>'
                        f'</div>'
                        f'</div>'
                    )

                    if hasattr(st, "html"):
                        st.html(fila_html)
                    else:
                        st.markdown(fila_html, unsafe_allow_html=True)
        else:
            st.info("No se encontraron productos coincidentes.")

    # 2. Alta de Producto con Imagen, Código de Barras y Stock Mínimo
    with tab_nuevo:
        st.subheader("Registrar Nuevo Producto")

        # Se usa una versión en las keys para "limpiar" el formulario tras guardar.
        # (No se usa st.form porque ahí el checkbox de precio manual y el precio calculado no reaccionan en vivo.)
        vnp = st.session_state.get("nuevo_prod_version", 0)

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            codigo = st.text_input("Código de Barras / SKU *", placeholder="Ej: 7791234567890 o PROD-001", help="Puedes usar la lectora de código de barras directamente aquí.", key=f"np_codigo_{vnp}")
            nombre = st.text_input("Nombre del producto *", placeholder="Ej: Gaseosa Cola 1.5L", key=f"np_nombre_{vnp}")

            cat_options = {c["nombre"]: c["id"] for c in categorias}
            cat_options_con_ninguna = {"(Sin Categoría)": None, **cat_options}
            cat_elegida = st.selectbox("Categoría", list(cat_options_con_ninguna.keys()), key=f"np_cat_{vnp}")
            cat_id_elegida = cat_options_con_ninguna[cat_elegida]

            imagen_subida = st.file_uploader(
                "Foto del Producto (JPG / PNG)",
                type=["jpg", "jpeg", "png"],
                help="Sube una fotografía del artículo.",
                key=f"np_foto_{vnp}"
            )

        with col_f2:
            costo = st.number_input("Precio de Costo ($)", min_value=0.0, value=100.0, step=10.0, format="%.2f", key=f"np_costo_{vnp}")
            margen = st.number_input("Margen de Ganancia (%)", min_value=0.0, value=30.0, step=5.0, format="%.2f", key=f"np_margen_{vnp}")

            precio_sugerido = models.calcular_precio_venta(costo, margen)
            st.info(f"Precio Calculado Automático: **{fmt_moneda_md(precio_sugerido)}**")

            usa_manual = st.checkbox("Sobreescribir precio de venta manualmente", key=f"np_usa_manual_{vnp}")
            precio_manual = None
            if usa_manual:
                precio_manual = st.number_input(
                    "Precio de Venta Manual ($)",
                    min_value=0.0,
                    value=precio_sugerido,
                    step=10.0,
                    format="%.2f",
                    key=f"np_precio_manual_{vnp}"
                )

            col_stk1, col_stk2 = st.columns(2)
            with col_stk1:
                stock_inicial = st.number_input("Stock Inicial", min_value=0.0, value=15.0, step=1.0, format="%g", help="Admite decimales para productos por peso (kg).", key=f"np_stock_{vnp}")
            with col_stk2:
                stock_minimo_input = st.number_input(
                    "Stock Mínimo de Alerta",
                    min_value=0.0,
                    value=5.0,
                    step=1.0,
                    format="%g",
                    help="Umbral mínimo para emitir alertas de reposición.",
                    key=f"np_minimo_{vnp}"
                )

            puntos_canje_nuevo = st.number_input(
                "Puntos para Canje",
                min_value=0,
                value=0,
                step=10,
                help="Indicar los puntos requeridos para canjear este producto. Dejar en 0 si no participa del programa de premios",
                key=f"np_puntos_{vnp}"
            )

        if st.button(":material/save: Guardar Producto", type="primary", key=f"np_guardar_{vnp}"):
            ruta_img_guardada = None
            try:
                if imagen_subida is not None:
                    ruta_img_guardada = guardar_archivo_imagen(imagen_subida, f"prod_{codigo}")

                nuevo_id = models.crear_producto(
                    codigo=codigo,
                    nombre=nombre,
                    categoria_id=cat_id_elegida,
                    precio_costo=costo,
                    margen_ganancia=margen,
                    usa_precio_manual=usa_manual,
                    precio_venta_manual=precio_manual if usa_manual else None,
                    stock_actual=stock_inicial,
                    stock_minimo=stock_minimo_input,
                    imagen_path=ruta_img_guardada,
                    puntos_canje=int(puntos_canje_nuevo)
                )
                st.session_state["flash_inventario"] = f"¡Producto '{nombre.strip()}' creado con éxito! (ID: {nuevo_id})"
                st.session_state["nuevo_prod_version"] = vnp + 1
                st.rerun()
            except models.BusinessLogicError as e:
                borrar_archivo_imagen_local(ruta_img_guardada)
                st.error(f"Error de validación: {e}")
            except Exception as e:
                borrar_archivo_imagen_local(ruta_img_guardada)
                st.error(f"Error inesperado: {e}")

    # 3. Edición Completa de Producto Existente
    with tab_editar:
        st.subheader(":material/edit: Edición Completa de Producto")
        todos_prods_edit = models.obtener_productos()

        if not todos_prods_edit:
            st.info("No hay productos registrados para editar.")
        else:
            dict_opciones_edit = {
                f"[{p['codigo']}] {p['nombre']} (Stock: {p['stock_actual']} | Mín: {p['stock_minimo']})": p
                for p in todos_prods_edit
            }
            prod_edit_label = st.selectbox(
                "Seleccione un producto para editar:",
                options=list(dict_opciones_edit.keys()),
                key="select_producto_a_editar"
            )
            prod_actual = dict_opciones_edit[prod_edit_label]
            pid = prod_actual["id"]
            prod = models.get_producto_por_id(pid) or prod_actual
            prod_actual = prod
            # Las keys dependen de los datos vigentes: si cambian en la base (ej. una venta baja el stock),
            # los widgets se regeneran con el valor real y no se pisa el stock con uno viejo al guardar.
            kp = (f"{pid}_{prod['stock_actual']:g}_{prod['stock_minimo']:g}_"
                  f"{prod['precio_costo']:g}_{prod['margen_ganancia']:g}_{prod['precio_venta']:g}_"
                  f"{int(prod.get('puntos_canje') or 0)}")

            st.markdown("---")

            col_ed1, col_ed2 = st.columns(2, gap="large")

            with col_ed1:
                st.markdown("#### Información General y Foto")
                codigo_edit = st.text_input(
                    "Código de Barras / SKU *",
                    value=prod_actual["codigo"],
                    key=f"edit_cod_{kp}"
                )
                nombre_edit = st.text_input(
                    "Nombre del producto *",
                    value=prod_actual["nombre"],
                    key=f"edit_nom_{kp}"
                )

                cat_options = {c["nombre"]: c["id"] for c in categorias}
                cat_options_con_ninguna = {"(Sin Categoría)": None, **cat_options}
                lista_nombres_cat = list(cat_options_con_ninguna.keys())

                cat_actual_nombre = "(Sin Categoría)"
                for c_nombre, c_id in cat_options.items():
                    if c_id == prod_actual["categoria_id"]:
                        cat_actual_nombre = c_nombre
                        break
                index_cat_actual = lista_nombres_cat.index(cat_actual_nombre) if cat_actual_nombre in lista_nombres_cat else 0

                cat_edit_elegida = st.selectbox(
                    "Categoría",
                    options=lista_nombres_cat,
                    index=index_cat_actual,
                    key=f"edit_cat_{kp}"
                )
                cat_edit_id = cat_options_con_ninguna[cat_edit_elegida]

                st.markdown("##### Fotografía del Producto")
                img_actual_abs = obtener_ruta_imagen_absoluta(prod_actual.get("imagen_path"))
                eliminar_foto_check = False

                if img_actual_abs:
                    c_f1, c_f2 = st.columns([1, 1.5])
                    with c_f1:
                        st.image(img_actual_abs, caption="Foto actual", width=120)
                    with c_f2:
                        eliminar_foto_check = st.checkbox(":material/delete: Eliminar foto actual", key=f"del_foto_{kp}")
                else:
                    st.caption("ℹ️ Sin foto asignada actualmente.")

                nueva_foto_subida = st.file_uploader(
                    "Subir nueva foto (reemplaza o agrega)",
                    type=["jpg", "jpeg", "png"],
                    key=f"upload_foto_{kp}"
                )

            with col_ed2:
                st.markdown("#### Precios y Control de Inventario")
                costo_edit = st.number_input(
                    "Precio de Costo ($)",
                    min_value=0.0,
                    value=float(prod_actual["precio_costo"]),
                    step=10.0,
                    format="%.2f",
                    key=f"edit_costo_{kp}"
                )
                margen_edit = st.number_input(
                    "Margen de Ganancia (%)",
                    min_value=0.0,
                    value=float(prod_actual["margen_ganancia"]),
                    step=5.0,
                    format="%.2f",
                    key=f"edit_margen_{kp}"
                )

                precio_sugerido_edit = models.calcular_precio_venta(costo_edit, margen_edit)
                st.info(f"Precio Calculado Automático: **{fmt_moneda_md(precio_sugerido_edit)}**")

                usa_manual_edit = st.checkbox(
                    "Sobreescribir precio de venta manualmente",
                    value=bool(prod_actual["usa_precio_manual"]),
                    key=f"edit_manual_{kp}"
                )
                precio_manual_edit = None
                if usa_manual_edit:
                    precio_manual_edit = st.number_input(
                        "Precio de Venta Manual ($)",
                        min_value=0.0,
                        value=float(prod_actual["precio_venta"]),
                        step=10.0,
                        format="%.2f",
                        key=f"edit_pval_{kp}"
                    )

                col_stk_e1, col_stk_e2 = st.columns(2)
                with col_stk_e1:
                    stock_actual_edit = st.number_input(
                        "Stock Actual",
                        min_value=0.0,
                        value=float(prod_actual["stock_actual"]),
                        step=1.0,
                        format="%g",
                        key=f"edit_stk_{kp}"
                    )
                with col_stk_e2:
                    stock_minimo_edit = st.number_input(
                        "Stock Mínimo de Alerta",
                        min_value=0.0,
                        value=float(prod_actual["stock_minimo"]),
                        step=1.0,
                        format="%g",
                        help="Umbral mínimo para activar alertas de reposición.",
                        key=f"edit_min_{kp}"
                    )

                puntos_canje_edit = st.number_input(
                    "Puntos para Canje",
                    min_value=0,
                    value=int(prod.get("puntos_canje") or 0),
                    step=10,
                    help="Indicar los puntos requeridos para canjear este producto. Dejar en 0 si no participa del programa de premios",
                    key=f"edit_pts_{kp}"
                )

            st.write("")
            col_save_btn, col_del_btn = st.columns([1.5, 1], gap="medium")

            with col_save_btn:
                if st.button(":material/save: Guardar Cambios", type="primary", width="stretch", key=f"btn_save_{kp}"):
                    ruta_img_final = None
                    try:
                        if nueva_foto_subida is not None:
                            ruta_img_final = guardar_archivo_imagen(nueva_foto_subida, f"prod_{codigo_edit}")

                        eliminar_foto = eliminar_foto_check and nueva_foto_subida is None
                        models.actualizar_producto(
                            producto_id=pid,
                            codigo=codigo_edit,
                            nombre=nombre_edit,
                            categoria_id=cat_edit_id,
                            precio_costo=costo_edit,
                            margen_ganancia=margen_edit,
                            usa_precio_manual=usa_manual_edit,
                            precio_venta_manual=precio_manual_edit if usa_manual_edit else None,
                            stock_actual=stock_actual_edit,
                            stock_minimo=stock_minimo_edit,
                            imagen_path=ruta_img_final,
                            eliminar_imagen=eliminar_foto,
                            puntos_canje=int(puntos_canje_edit)
                        )
                        # Guardado OK: si la foto cambió o se quitó, borrar el archivo local anterior
                        if ruta_img_final or eliminar_foto:
                            borrar_archivo_imagen_local(prod.get("imagen_path"))
                        st.cache_data.clear()
                        st.session_state["flash_inventario"] = f"¡Producto '{nombre_edit.strip()}' actualizado con éxito!"
                        st.rerun()
                    except models.BusinessLogicError as e:
                        borrar_archivo_imagen_local(ruta_img_final)
                        st.error(f"Error de validación: {e}")
                    except Exception as e:
                        borrar_archivo_imagen_local(ruta_img_final)
                        st.error(f"Error inesperado al guardar: {e}")

            with col_del_btn:
                with st.expander("Dar de baja producto"):
                    st.info("Sale del catálogo y del POS; sus ventas quedan intactas. Se puede reactivar.")
                    confirmar_del = st.checkbox("Confirmo dar de baja este producto", key=f"chk_del_{pid}")
                    if st.button("Dar de baja", type="secondary", disabled=not confirmar_del, width="stretch", key=f"btn_del_{pid}"):
                        try:
                            models.eliminar_producto(pid)
                            st.session_state["flash_inventario"] = f"Producto '{prod_actual['nombre']}' dado de baja."
                            st.rerun()
                        except models.BusinessLogicError as e:
                            st.error(f"No se pudo dar de baja: {e}")
                        except Exception as e:
                            st.error(f"Error al dar de baja: {e}")

        _seccion_dados_de_baja("productos", "Productos dados de baja")

    # 4. Ajuste Rápido de Stock
    with tab_ajuste:
        st.subheader(":material/sync_alt: Ajuste de Stock en Almacén")
        todos_los_prods = models.obtener_productos()

        if not todos_los_prods:
            st.info("No hay productos disponibles para ajustar.")
        else:
            dict_prods_ajuste = {
                f"[{p['codigo']}] {p['nombre']} (Stock actual: {p['stock_actual']} | Mín: {p['stock_minimo']})": p
                for p in todos_los_prods
            }
            sel_ajuste = st.selectbox("Seleccione el producto a modificar:", list(dict_prods_ajuste.keys()))
            prod_a_ajustar = dict_prods_ajuste[sel_ajuste]

            # Las keys incluyen el stock/mínimo vigentes: si el stock cambia (ej. por una venta) los widgets
            # se regeneran con el valor real en vez de arrastrar uno viejo guardado por Streamlit.
            ka = f"{prod_a_ajustar['id']}_{prod_a_ajustar['stock_actual']:g}_{prod_a_ajustar['stock_minimo']:g}"

            col_ajuste_izq, col_ajuste_der = st.columns([1, 1], gap="medium")

            with col_ajuste_izq:
                with st.container(border=True):
                    st.markdown("#### Ajustar Cantidad en Almacén")
                    tipo_ajuste = st.radio("Método de Ajuste", ["Establecer Conteo Físico Exacto", "Sumar Ingreso de Mercadería"], key=f"aj_tipo_{ka}")

                    if tipo_ajuste == "Establecer Conteo Físico Exacto":
                        nuevo_stock_val = st.number_input(
                            "Nuevo Stock Total",
                            min_value=0.0,
                            value=float(prod_a_ajustar["stock_actual"]),
                            step=1.0,
                            format="%g",
                            key=f"aj_total_{ka}"
                        )
                    else:
                        ingreso_cant = st.number_input("Cantidad ingresada", min_value=0.001, value=10.0, step=1.0, format="%g", key=f"aj_ingreso_{ka}")
                        nuevo_stock_val = round(prod_a_ajustar["stock_actual"] + ingreso_cant, 3)
                        st.caption(f"Stock resultante: **{fmt_cantidad(nuevo_stock_val)}** unidades")

                    if st.button("Guardar Stock Actual", type="primary", key=f"aj_guardar_{ka}"):
                        try:
                            models.ajustar_stock(prod_a_ajustar["id"], nuevo_stock_val)
                            st.session_state["flash_inventario"] = f"Stock de '{prod_a_ajustar['nombre']}' actualizado a {fmt_cantidad(nuevo_stock_val)} unidades."
                            st.rerun()
                        except models.BusinessLogicError as e:
                            st.error(str(e))
                        except Exception as e:
                            st.error(f"Error al actualizar stock: {e}")

            with col_ajuste_der:
                with st.container(border=True):
                    st.markdown("#### Umbral de Stock Mínimo")
                    nuevo_minimo = st.number_input(
                        "Stock Mínimo Personalizado",
                        min_value=0.0,
                        value=float(prod_a_ajustar["stock_minimo"]),
                        step=1.0,
                        format="%g",
                        help="Umbral de alerta para este producto específico.",
                        key=f"aj_minimo_{ka}"
                    )
                    if st.button("Guardar Stock Mínimo", key=f"aj_guardar_min_{ka}"):
                        try:
                            models.actualizar_stock_minimo(prod_a_ajustar["id"], nuevo_minimo)
                            st.session_state["flash_inventario"] = f"Stock mínimo de '{prod_a_ajustar['nombre']}' actualizado a {fmt_cantidad(nuevo_minimo)}."
                            st.rerun()
                        except models.BusinessLogicError as e:
                            st.error(str(e))
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

    # 5. Monitor Exclusivo de Stock Crítico
    with tab_alertas:
        st.subheader(":material/warning: Artículos que Requieren Reposición Inmediata")
        bajo_stock_list = models.obtener_productos_bajo_stock()

        if not bajo_stock_list:
            st.success("¡Excelente! No hay productos con stock igual o inferior a su mínimo.")
        else:
            st.warning(f"Se encontraron **{len(bajo_stock_list)}** artículos con necesidad de reposición.")

            df_criticos = pd.DataFrame(bajo_stock_list)[[
                "codigo", "nombre", "categoria_nombre", "stock_actual", "stock_minimo", "deficit"
            ]].rename(columns={
                "codigo": "Código",
                "nombre": "Producto",
                "categoria_nombre": "Categoría",
                "stock_actual": "Stock Actual",
                "stock_minimo": "Stock Mínimo",
                "deficit": "Déficit / Faltante"
            })
            st.dataframe(formatear_df(df_criticos, cantidades=["Stock Actual", "Stock Mínimo", "Déficit / Faltante"]),
                         width="stretch", hide_index=True)

    # 6. Carga Masiva de Productos (Excel / CSV)
    with tab_masiva:
        st.subheader(":material/upload_file: Carga Masiva de Productos")
        st.caption("Importá nuevos artículos o actualizá precios y stock en lote desde una planilla Excel (.xlsx) o CSV.")

        col_p1, col_p2 = st.columns([1, 1], gap="large")

        with col_p1:
            with st.container(border=True):
                st.markdown("#### Paso 1: Descargar Plantilla de Ejemplo")
                st.markdown(
                    "Descargá la planilla modelo con las columnas requeridas:  \n"
                    "`codigo`, `nombre`, `categoria`, `precio_costo`, `precio_venta`, `stock`, `stock_minimo`, `puntos_canje`"
                )
                plantilla_bytes = models.generar_plantilla_excel_productos()
                st.download_button(
                    label=":material/download: Descargar Plantilla de Ejemplo (.xlsx)",
                    data=plantilla_bytes,
                    file_name="plantilla_productos_ejemplo.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch"
                )

        with col_p2:
            with st.container(border=True):
                st.markdown("#### Paso 2: Subir Archivo (.xlsx / .csv)")
                st.markdown("Seleccioná el archivo con tus productos para procesar.")
                archivo_subido = st.file_uploader(
                    "Subir archivo Excel o CSV",
                    type=["xlsx", "csv"],
                    key="uploader_carga_masiva",
                    label_visibility="collapsed"
                )

        if archivo_subido is not None:
            st.markdown("---")
            st.markdown("#### Paso 3: Previsualización y Validaciones")

            df_cargado = None
            try:
                if archivo_subido.name.lower().endswith(".xlsx"):
                    df_cargado = pd.read_excel(archivo_subido, dtype={"codigo": str, "Código": str})
                else:
                    try:
                        df_cargado = pd.read_csv(archivo_subido, dtype={"codigo": str, "Código": str}, sep=None, engine="python", encoding="utf-8")
                    except UnicodeDecodeError:
                        archivo_subido.seek(0)
                        df_cargado = pd.read_csv(archivo_subido, dtype={"codigo": str, "Código": str}, sep=None, engine="python", encoding="latin1")
            except Exception as e:
                st.error(f"Error al leer el archivo: {e}")

            if df_cargado is not None:
                df_cargado = df_cargado.dropna(how="all").reset_index(drop=True)

                if df_cargado.empty:
                    st.warning("El archivo subido no contiene filas con datos.")
                else:
                    # Mapeo normalizado
                    mapeo_prev = {}
                    for col in df_cargado.columns:
                        c_norm = str(col).strip().lower().replace(" ", "_")
                        c_norm = c_norm.replace("ó", "o").replace("í", "i").replace("á", "a").replace("é", "e").replace("ú", "u")
                        if c_norm in ["codigo", "código", "sku", "barcode", "cod"]:
                            mapeo_prev[col] = "codigo"
                        elif c_norm in ["nombre", "producto", "descripcion", "articulo"]:
                            mapeo_prev[col] = "nombre"
                        elif c_norm in ["categoria", "categoria_nombre", "rubro"]:
                            mapeo_prev[col] = "categoria"
                        elif c_norm in ["precio_costo", "costo", "costo_unitario"]:
                            mapeo_prev[col] = "precio_costo"
                        elif c_norm in ["precio_venta", "venta", "precio"]:
                            mapeo_prev[col] = "precio_venta"
                        elif c_norm in ["stock", "stock_actual", "cantidad"]:
                            mapeo_prev[col] = "stock"
                        elif c_norm in ["stock_minimo", "stock_min", "minimo"]:
                            mapeo_prev[col] = "stock_minimo"
                        elif c_norm in ["puntos_canje", "puntos_de_canje", "puntos", "puntos_canje_premio"]:
                            mapeo_prev[col] = "puntos_canje"

                    df_validar = df_cargado.rename(columns=mapeo_prev)

                    # Validaciones básicas
                    errores_validacion = []
                    for idx, row in df_validar.iterrows():
                        fila_num = idx + 2
                        nom = str(row.get("nombre", "")).strip() if pd.notna(row.get("nombre")) else ""
                        cod = str(row.get("codigo", "")).strip() if pd.notna(row.get("codigo")) else ""

                        if not cod:
                            errores_validacion.append(f"Fila {fila_num}: Falta el código de barras / SKU.")
                        if not nom:
                            errores_validacion.append(f"Fila {fila_num} (código {cod or 'S/C'}): Falta el nombre del producto.")

                        try:
                            pc = float(row.get("precio_costo", 0)) if pd.notna(row.get("precio_costo")) else 0.0
                            if pc < 0:
                                errores_validacion.append(f"Fila {fila_num} ('{nom}'): Precio de costo negativo ({fmt_moneda_md(pc)}).")
                        except (ValueError, TypeError):
                            errores_validacion.append(f"Fila {fila_num} ('{nom}'): Precio de costo no numérico.")

                        try:
                            pv = float(row.get("precio_venta", 0)) if pd.notna(row.get("precio_venta")) else 0.0
                            if pv < 0:
                                errores_validacion.append(f"Fila {fila_num} ('{nom}'): Precio de venta negativo ({fmt_moneda_md(pv)}).")
                        except (ValueError, TypeError):
                            errores_validacion.append(f"Fila {fila_num} ('{nom}'): Precio de venta no numérico.")

                    m1, m2, m3 = st.columns(3)
                    with m1:
                        st.metric("Total Filas Detectadas", len(df_cargado))
                    with m2:
                        if not errores_validacion:
                            st.metric("Validación de Datos", "Sin errores")
                        else:
                            st.metric("Validación de Datos", f"{len(errores_validacion)} fila(s) con aviso")
                    with m3:
                        cats_en_archivo = [c for c in df_validar["categoria"].dropna().unique().tolist() if str(c).strip()] if "categoria" in df_validar.columns else []
                        st.metric("Categorías en Archivo", len(cats_en_archivo) if cats_en_archivo else 1)

                    if errores_validacion:
                        with st.expander(f":material/warning: Ver detalles de {len(errores_validacion)} fila(s) con observaciones", expanded=True):
                            for err in errores_validacion[:10]:
                                st.warning(err)
                            if len(errores_validacion) > 10:
                                st.caption(f"...y {len(errores_validacion) - 10} observaciones más.")

                    st.markdown("**Vista previa del archivo cargado:**")
                    st.dataframe(df_cargado, width="stretch", hide_index=False)

                    st.markdown("---")
                    st.markdown("#### Paso 4: Confirmación")
                    st.caption("Al confirmar, se crearán o actualizarán los productos y las categorías inexistentes se darán de alta automáticamente.")

                    btn_confirmar = st.button(
                        "Confirmar e Importar a Base de Datos",
                        type="primary",
                        width="stretch",
                        key="btn_confirmar_carga_masiva"
                    )

                    if btn_confirmar:
                        with st.spinner("Importando productos y actualizando base de datos en Supabase..."):
                            comercio_id_actual = usuario_actual.get("comercio_id", models.COMERCIO_ID_DEFAULT)
                            res_imp = models.importar_productos_masivo(df_cargado, comercio_id=comercio_id_actual)
                            
                            cats_msg = f", {res_imp['categorias_creadas']} categorías nuevas creadas" if res_imp.get("categorias_creadas") else ""
                            msg_exito = (
                                f"¡Carga masiva completada! Se procesaron {res_imp['total']} productos "
                                f"({res_imp['creados']} creados, {res_imp['actualizados']} actualizados{cats_msg})."
                            )
                            st.session_state["flash_inventario"] = msg_exito
                            st.rerun()


# ==============================================================================
# MÓDULO 4: GESTIÓN DE CATEGORÍAS
# ==============================================================================
elif modulo == ":material/sell: Categorías":
    st.header(":material/sell: Gestión de Categorías")
    col_nueva, col_lista = st.columns([1, 1.2], gap="large")

    with col_nueva:
        st.subheader("Nueva Categoría")
        with st.form("form_categoria", clear_on_submit=True):
            nombre_cat = st.text_input("Nombre de la Categoría", placeholder="Ej: Bebidas, Almacén, Limpieza")
            btn_guardar_cat = st.form_submit_button("Crear Categoría", type="primary")

            if btn_guardar_cat:
                try:
                    cat_id = models.crear_categoria(nombre_cat)
                    st.success(f"Categoría '{nombre_cat}' creada con éxito.")
                    st.rerun()
                except models.BusinessLogicError as e:
                    st.error(str(e))

    with col_lista:
        st.subheader("Categorías Existentes")
        lista_categorias = models.obtener_categorias()
        if not lista_categorias:
            st.info("Aún no existen categorías registradas.")
        else:
            for cat in lista_categorias:
                with st.expander(f":material/folder: {cat['nombre']}"):
                    with st.form(f"form_edit_cat_{cat['id']}"):
                        nuevo_nombre = st.text_input("Renombrar categoría", value=cat['nombre'])
                        confirma_baja_cat = st.checkbox("Confirmo dar de baja esta categoría", key=f"chk_baja_cat_{cat['id']}")
                        c_btn_edit, c_btn_del = st.columns(2)

                        btn_editar = c_btn_edit.form_submit_button(":material/save: Guardar Cambios", type="primary")
                        btn_eliminar = c_btn_del.form_submit_button("Dar de baja", type="secondary")
                        
                        if btn_editar:
                            if nuevo_nombre.strip() != cat['nombre']:
                                try:
                                    models.actualizar_categoria(cat['id'], nuevo_nombre)
                                    st.success(f"Categoría renombrada a '{nuevo_nombre}'.")
                                    st.rerun()
                                except models.BusinessLogicError as e:
                                    st.error(str(e))
                                except Exception as e:
                                    st.error(f"Error al actualizar: {e}")
                            else:
                                st.info("No se realizaron cambios en el nombre.")
                                
                        if btn_eliminar and not confirma_baja_cat:
                            st.warning("Marcá la confirmación para dar de baja la categoría.")
                        elif btn_eliminar:
                            try:
                                models.eliminar_categoria(cat['id'])
                                st.success(f"Categoría '{cat['nombre']}' dada de baja.")
                                st.rerun()
                            except models.BusinessLogicError as e:
                                st.warning(str(e))
                            except Exception as e:
                                st.error(f"Error al dar de baja: {e}")
        _seccion_dados_de_baja("categorias", "Categorías dadas de baja")


# ==============================================================================
# MÓDULO 5: ARQUEO DE CAJA Y CIERRE DIARIO
# ==============================================================================
elif modulo == ":material/bar_chart: Arqueo de Caja / Control Diario":
    st.header(":material/bar_chart: Control Diario & Cierre de Caja")

    col_fecha, col_btn_cierre = st.columns([1, 1.5], gap="large")
    with col_fecha:
        fecha_elegida = st.date_input("Fecha de consulta:", value=date.today(), format="DD/MM/YYYY")

    resumen = models.obtener_arqueo_caja(fecha_elegida.strftime("%Y-%m-%d"))

    # ---> NUEVO FORMULARIO DE CAJA CHICA Y TABLA
    st.markdown("### Registro de Caja Chica (Efectivo)")
    with st.expander(":material/add: Registrar Ingreso Extra / Egreso Manual", expanded=False):
        with st.form("form_caja_chica"):
            col_cc1, col_cc2, col_cc3 = st.columns([1, 1, 2])
            with col_cc1:
                tipo_mov = st.selectbox("Tipo de Movimiento", ["Egreso", "Ingreso Extra"])
            with col_cc2:
                monto_mov = st.number_input("Monto ($) *", min_value=1.0, value=1000.0, step=100.0)
            with col_cc3:
                concepto_mov = st.text_input("Concepto / Motivo *", placeholder="Ej: Pago a proveedor, Compra de artículos...")
            
            btn_registrar_cc = st.form_submit_button(":material/check_circle: Registrar Movimiento", type="primary")
            if btn_registrar_cc:
                try:
                    tipo_db = "egreso" if tipo_mov == "Egreso" else "ingreso_extra"
                    comercio_id_actual = usuario_actual.get("comercio_id", models.COMERCIO_ID_DEFAULT)
                    models.registrar_movimiento_caja(
                        comercio_id=comercio_id_actual,
                        tipo=tipo_db, 
                        monto=monto_mov, 
                        concepto=concepto_mov, 
                        usuario_nombre=usuario_actual.get("nombre", "Desconocido")
                    )
                    st.success("Movimiento de caja registrado con éxito.")
                    st.rerun()
                except models.BusinessLogicError as e:
                    st.error(f"Error: {e}")
                except Exception as e:
                    st.error(f"Error al registrar: {e}")
                    
    # Mostrar tabla de movimientos si hay
    if resumen.get("movimientos_caja"):
        st.markdown("#### Movimientos de Caja Chica de la Fecha")
        df_movs = pd.DataFrame(resumen["movimientos_caja"])[["fecha", "tipo", "concepto", "monto", "usuario_nombre"]]
        # Formatear la fecha
        df_movs["fecha"] = pd.to_datetime(df_movs["fecha"], utc=True).dt.tz_convert(ZONA_HORARIA).dt.strftime("%H:%M")
        df_movs["tipo"] = df_movs["tipo"].map({"egreso": "Egreso", "ingreso_extra": "Ingreso extra"})
        df_movs["monto"] = df_movs["monto"].apply(lambda x: f"{fmt_moneda(float(x))}")
        df_movs = df_movs.rename(columns={
            "fecha": "Hora", "tipo": "Tipo", "concepto": "Concepto", 
            "monto": "Monto", "usuario_nombre": "Responsable"
        })
        st.dataframe(df_movs, width="stretch", hide_index=True)

    st.markdown("---")

    # Métricas Principales (KPI Cards) - Reorganizadas para mostrar el Efectivo Esperado
    st.subheader(":material/bar_chart: Balance del Día")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(":material/payments: Total Ventas", f"{fmt_moneda(resumen['total_vendido'])}")
    m2.metric(":material/payments: Efectivo Esperado", f"{fmt_moneda(resumen['total_efectivo_esperado'])}")
    m3.metric(":material/trending_up: Ganancia Estimada", f"{fmt_moneda(resumen['ganancia_estimada'])}")
    m4.metric(":material/receipt_long: Tickets", resumen['total_operaciones'])

    # Desglose de Efectivo Esperado en expander
    with st.expander(":material/search: Ver Desglose de Efectivo Esperado", expanded=False):
        st.write(f"**+ Ventas en Efectivo:** {fmt_moneda_md(resumen.get('ventas_efectivo', 0))}")
        st.write(f"**+ Cobros de Fiado (Efectivo):** {fmt_moneda_md(resumen.get('cobros_fiado_efectivo', 0))}")
        st.write(f"**+ Ingresos Extras (Manual):** {fmt_moneda_md(resumen.get('ingresos_extras', 0))}")
        st.write(f"**- Egresos (Gastos / Retiros):** {fmt_moneda_md(resumen.get('egresos', 0))}")
        st.markdown(f"**= EFECTIVO ESPERADO EN CAJA: {fmt_moneda_md(resumen.get('total_efectivo_esperado', 0))}**")

    st.markdown("---")

    # BOTÓN DESTACADO: REALIZAR CIERRE DE CAJA DEL DÍA
    st.subheader(":material/lock: Cierre Oficial de Caja Diario")
    
    col_cierre_btn, _ = st.columns([1.5, 1])
    with col_cierre_btn:
        sin_ventas = resumen["total_operaciones"] == 0
        ejecutar_cierre = st.button(":material/lock: Realizar Cierre de Caja del Día", type="primary", width="stretch", disabled=sin_ventas)
        if sin_ventas:
            st.caption("No hay ventas para cerrar en esta fecha.")

    if ejecutar_cierre:
        st.session_state["cierre_activo"] = True
        st.session_state["cierre_fecha_activa"] = fecha_elegida.strftime("%Y-%m-%d")

    # Panel de Descarga, WhatsApp y Envío de Correo si se activó el cierre
    if st.session_state.get("cierre_activo") and st.session_state.get("cierre_fecha_activa") == fecha_elegida.strftime("%Y-%m-%d"):
        with st.container(border=True):
            st.success(f"**Cierre de Caja procesado para el día {fecha_elegida.strftime('%d/%m/%Y')}**")

            nombre_neg = config_negocio.get("nombre_negocio", "Mi Comercio")
            pdf_bytes = reportes.generar_pdf_cierre_caja(
                fecha_str=fecha_elegida.strftime("%Y-%m-%d"),
                resumen=resumen,
                nombre_negocio=nombre_neg
            )

            col_acc1, col_acc2, col_acc3 = st.columns(3, gap="medium")

            with col_acc1:
                st.download_button(
                    label=":material/download: Descargar PDF del Cierre",
                    data=pdf_bytes,
                    file_name=f"Cierre_Caja_{fecha_elegida.strftime('%Y-%m-%d')}.pdf",
                    mime="application/pdf",
                    width="stretch"
                )

            with col_acc2:
                msg_wsp = reportes.armar_mensaje_whatsapp_cierre(
                    resumen=resumen,
                    fecha_str=fecha_elegida.strftime("%d/%m/%Y"),
                    nombre_negocio=nombre_neg
                )
                url_wsp = reportes.armar_url_whatsapp(None, msg_wsp)
                st.link_button(":material/send: Compartir Cierre por WhatsApp", url_wsp, width="stretch")

            with col_acc3:
                email_dest = config_negocio.get("email_destinatario", "").strip()
                if email_dest and config_negocio.get("smtp_usuario") and config_negocio.get("smtp_password"):
                    if st.button(":material/mail: Enviar / Reenviar por Email", width="stretch"):
                        exito, mensaje = reportes.enviar_email_cierre(
                            destinatario=email_dest,
                            pdf_bytes=pdf_bytes,
                            fecha_str=fecha_elegida.strftime("%Y-%m-%d"),
                            resumen=resumen,
                            config_smtp=config_negocio
                        )
                        if exito:
                            st.success(mensaje)
                        else:
                            st.error(mensaje)
                else:
                    st.caption("ℹ️ Configure el correo en 'Ajustes' para habilitar el envío automático.")

            clave_envio = f"email_sent_{fecha_elegida.strftime('%Y-%m-%d')}"
            if not st.session_state.get(clave_envio):
                if email_dest and config_negocio.get("smtp_usuario") and config_negocio.get("smtp_password"):
                    exito, mensaje = reportes.enviar_email_cierre(
                        destinatario=email_dest,
                        pdf_bytes=pdf_bytes,
                        fecha_str=fecha_elegida.strftime("%Y-%m-%d"),
                        resumen=resumen,
                        config_smtp=config_negocio
                    )
                    st.session_state[clave_envio] = True
                    if exito:
                        st.info(f"Correo automático: {mensaje}")
                    else:
                        st.warning(f"Correo automático: {mensaje}")

    st.markdown("---")

    col_desglose, col_tickets = st.columns([1, 1.5], gap="large")

    with col_desglose:
        st.subheader(":material/credit_card: Ventas por Forma de Pago")
        if resumen["desglose_por_forma_pago"]:
            df_desglose = pd.DataFrame(resumen["desglose_por_forma_pago"]).rename(
                columns={
                    "forma_pago": "Forma de Pago",
                    "operaciones": "Operaciones",
                    "total": "Total ($)"
                }
            )
            st.dataframe(formatear_df(df_desglose, monedas=["Total ($)"]), width="stretch", hide_index=True)
            chart = alt.Chart(df_desglose).mark_bar(color="#3b82f6", cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("Forma de Pago", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Total ($)")
            )
            st.altair_chart(chart, width="stretch")
        else:
            st.info("No hay ventas registradas en esta fecha.")

    with col_tickets:
        st.subheader(":material/history: Detalle de Ventas Registradas")
        if resumen["ventas"]:
            for v in resumen["ventas"]:
                try:
                    dt_v = pd.to_datetime(v['fecha_hora'], utc=True).tz_convert(ZONA_HORARIA)
                    hora_str = dt_v.strftime("%H:%M")
                except:
                    hora_str = v['fecha_hora']
                cli_info = f" [Cliente: {v['cliente_nombre']}]" if v.get("cliente_nombre") else ""
                with st.expander(f"Ticket #{v['id']} - {hora_str} | {fmt_moneda_md(v['total_venta'])} ({v['forma_pago']}){cli_info}"):
                    detalles = models.obtener_detalle_de_venta(v["id"])
                    if detalles:
                        df_det = pd.DataFrame(detalles)[["codigo", "nombre", "cantidad", "precio_unitario", "subtotal"]].rename(
                            columns={
                                "codigo": "Código",
                                "nombre": "Producto",
                                "cantidad": "Cant.",
                                "precio_unitario": "Precio Unit.",
                                "subtotal": "Subtotal"
                            }
                        )
                        st.dataframe(formatear_df(df_det, monedas=["Precio Unit.", "Subtotal"], cantidades=["Cant."]),
                                     width="stretch", hide_index=True)
        else:
            st.info("Sin registros de tickets para la fecha seleccionada.")


# ==============================================================================
# MÓDULO 6: CONFIGURACIÓN DEL NEGOCIO
# ==============================================================================
elif modulo == ":material/settings: Configuración del Negocio":
    st.header(":material/settings: Configuración del Comercio")
    st.caption("Administra tus datos bancarios para cobros con QR y la configuración de notificaciones por email.")

    if "flash_config" in st.session_state:
        st.success(st.session_state.pop("flash_config"))

    with st.form("form_config_negocio"):
        col_c1, col_c2 = st.columns(2, gap="large")

        with col_c1:
            st.markdown("### Identidad del Negocio")
            nombre_neg_input = st.text_input("Nombre de Fantasía del Negocio", value=config_negocio.get("nombre_negocio", "Mi Comercio"))

            st.markdown("#### Logo del Local")
            logo_actual_abs = obtener_ruta_imagen_absoluta(config_negocio.get("logo_imagen_path"))
            eliminar_logo_check = False
            if logo_actual_abs:
                c_l1, c_l2, c_l3 = st.columns([1, 1.5, 2.5])
                with c_l1:
                    st.image(logo_actual_abs, caption="Logo actual", width="stretch")
                with c_l2:
                    st.write("")
                    st.write("")
                    eliminar_logo_check = st.checkbox(":material/delete: Eliminar Logo", key="del_logo_cfg")
            
            logo_subido = st.file_uploader(
                "Subir o Reemplazar Logo (JPG / PNG / WEBP)",
                type=["jpg", "jpeg", "png", "webp"],
                key="uploader_logo_cfg"
            )

            st.markdown("### Datos Bancarios y QR de Cobro")
            titular_input = st.text_input("Titular de la Cuenta", value=config_negocio.get("titular_cuenta", ""))
            banco_input = st.text_input("Banco o Billetera Virtual (ej: Mercado Pago, Santander)", value=config_negocio.get("banco", ""))
            alias_input = st.text_input("Alias CBU/CVU", value=config_negocio.get("alias", ""))
            cbu_input = st.text_input("CBU / CVU Numérico", value=config_negocio.get("cbu", ""))

            st.markdown("#### Código QR de Cobro (Estático)")
            qr_actual_abs = obtener_ruta_imagen_absoluta(config_negocio.get("qr_imagen_path"))
            if qr_actual_abs:
                st.image(qr_actual_abs, caption="Código QR cargado actualmente", width=140)
            
            qr_subido = st.file_uploader(
                "Subir o Reemplazar Código QR (JPG / PNG)",
                type=["jpg", "jpeg", "png"],
                help="Sube una captura del código QR de tu cuenta para mostrar a los clientes en el Punto de Venta."
            )

        with col_c2:
            st.markdown("### Configuración de Correo SMTP")
            st.caption("Para el envío automático del PDF de Cierre de Caja.")

            smtp_srv_input = st.text_input("Servidor SMTP", value=config_negocio.get("smtp_servidor", "smtp.gmail.com"))
            smtp_prt_input = st.number_input("Puerto SMTP (587 recomendado para TLS)", min_value=1, max_value=65535, value=int(config_negocio.get("smtp_puerto", 587)))
            smtp_usr_input = st.text_input("Usuario / Email Remitente", value=config_negocio.get("smtp_usuario", ""), placeholder="tu_cuenta@gmail.com")
            smtp_pwd_input = st.text_input("Contraseña de Aplicación", value=config_negocio.get("smtp_password", ""), type="password", help="En Gmail, utiliza una 'Contraseña de Aplicación' generada desde la seguridad de Google.")
            email_dest_input = st.text_input("Email Destinatario del Cierre Diario", value=config_negocio.get("email_destinatario", ""), placeholder="dueno@negocio.com")

        guardar_cfg_btn = st.form_submit_button(":material/save: Guardar Configuración", type="primary")

        if guardar_cfg_btn:
            ruta_qr_final = config_negocio.get("qr_imagen_path")
            if qr_subido is not None:
                ruta_qr_final = guardar_archivo_imagen(qr_subido, "qr_pago")

            ruta_logo_final = config_negocio.get("logo_imagen_path")
            if logo_subido is not None:
                ruta_logo_final = guardar_archivo_imagen(logo_subido, "logo_negocio", max_dim=300)
            elif eliminar_logo_check:
                ruta_logo_final = None

            nueva_config = {
                "nombre_negocio": nombre_neg_input.strip() or "Mi Comercio",
                "titular_cuenta": titular_input.strip(),
                "banco": banco_input.strip(),
                "alias": alias_input.strip(),
                "cbu": cbu_input.strip(),
                "qr_imagen_path": ruta_qr_final,
                "logo_imagen_path": ruta_logo_final,
                "smtp_servidor": smtp_srv_input.strip(),
                "smtp_puerto": int(smtp_prt_input),
                "smtp_usuario": smtp_usr_input.strip(),
                "smtp_password": smtp_pwd_input.strip(),
                "email_destinatario": email_dest_input.strip(),
                "admin_password": config_negocio.get("admin_password", "admin123")
            }

            if guardar_configuracion(nueva_config):
                if logo_subido or eliminar_logo_check:
                    borrar_archivo_imagen_local(config_negocio.get("logo_imagen_path"))
                st.success("Configuración guardada correctamente.")
                st.rerun()
            else:
                st.error("Error al persistir la configuración.")

    st.markdown("---")

    # PANEL: COPIA DE SEGURIDAD Y RESTAURACIÓN (SNAPSHOT)
    st.subheader(":material/save: Respaldo y Restauración de Base de Datos")
    st.caption("Crea una instantánea completa (Snapshot JSON) de tu negocio o restaura tus datos.")

    with st.container(border=True):
        col_bk1, col_bk2 = st.columns([1, 1], gap="large")

        with col_bk1:
            st.markdown("#### Descargar Copia de Seguridad")
            st.markdown(
                "Exporta todos los registros de las tablas principales (**categorías, productos, clientes, ventas, detalles y movimientos de caja**) en un archivo JSON descargable."
            )
            comercio_id_actual = usuario_actual.get("comercio_id", models.COMERCIO_ID_DEFAULT)
            backup_json_str = models.generar_backup_completo(comercio_id=comercio_id_actual)
            nombre_archivo_backup = f"backup_sistema_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            st.download_button(
                label=":material/download: Descargar Copia de Seguridad Completa (JSON)",
                data=backup_json_str,
                file_name=nombre_archivo_backup,
                mime="application/json",
                width="stretch",
                help="Haz clic para descargar la copia de seguridad de la base de datos."
            )

        with col_bk2:
            st.markdown("#### Restaurar desde Copia de Seguridad")
            st.caption("Recupera tus datos cargando un archivo de respaldo previo.")

            archivo_respaldo = st.file_uploader(
                "Seleccionar archivo .json de respaldo",
                type=["json"],
                key="uploader_backup_json"
            )

            if archivo_respaldo is not None:
                try:
                    contenido_json = json.loads(archivo_respaldo.getvalue().decode("utf-8"))
                    tablas_preview = contenido_json.get("tablas") or contenido_json.get("datos") or contenido_json

                    fecha_bk = contenido_json.get("timestamp", "No informada")
                    try:
                        dt_bk = pd.to_datetime(fecha_bk, utc=True).tz_convert(ZONA_HORARIA)
                        fecha_bk_fmt = dt_bk.strftime("%d/%m/%Y %H:%M:%S")
                    except Exception:
                        fecha_bk_fmt = str(fecha_bk)

                    cant_prods = len(tablas_preview.get("productos", [])) if isinstance(tablas_preview, dict) else 0
                    cant_clis = len(tablas_preview.get("clientes", [])) if isinstance(tablas_preview, dict) else 0

                    st.info(
                        f"**Fecha del Backup:** {fecha_bk_fmt}  \n"
                        f"**Productos:** {cant_prods} | **Clientes:** {cant_clis}"
                    )

                    chk_restaurar = st.checkbox(
                        "Confirmo que deseo restaurar la base de datos con esta copia",
                        key="chk_confirmar_restauracion"
                    )

                    btn_restaurar = st.button(
                        ":material/restore: Restaurar Base de Datos",
                        type="primary",
                        disabled=not chk_restaurar,
                        width="stretch",
                        key="btn_restaurar_backup"
                    )

                    if btn_restaurar and chk_restaurar:
                        with st.spinner("Restaurando base de datos en Supabase..."):
                            comercio_id_actual = usuario_actual.get("comercio_id", models.COMERCIO_ID_DEFAULT)
                            res_rest = models.restaurar_backup_completo(contenido_json, comercio_id=comercio_id_actual)

                        if res_rest.get("ok"):
                            partes = [f"{v} {k}" for k, v in res_rest.get("resumen", {}).items() if v > 0]
                            st.session_state["flash_config"] = (
                                f"¡Base de datos restaurada con éxito! Se restauraron: {', '.join(partes)}. "
                                "Por favor refrescá la aplicación (recargá la página) para actualizar la vista de todos los módulos."
                            )
                            st.rerun()
                        else:
                            st.error(f"Error al restaurar la copia de seguridad: {res_rest.get('error')}")

                except json.JSONDecodeError:
                    st.error("El archivo seleccionado no contiene un formato JSON válido.")
                except Exception as e:
                    st.error(f"Error al procesar el archivo: {e}")

    st.markdown("---")

    # ZONA DE MANTENIMIENTO / PUESTA A CERO (solo Dueño)
    if not es_admin:
        st.error("Solo el Dueño puede acceder al mantenimiento del sistema.")
        st.stop()

    # La versión cambia tras cada intento (éxito o error) para que los widgets de confirmación
    # vuelvan a su estado inicial: el botón rojo nunca queda "armado" para una segunda puesta a cero.
    ver_reset = st.session_state.get("reset_ver", 0)

    # Resultado del intento anterior (sobrevive al st.rerun())
    msg_reset = st.session_state.pop("reset_msg", None)
    if msg_reset:
        if msg_reset[0] == "ok":
            st.success(msg_reset[1])
        else:
            st.error(msg_reset[1])

    with st.expander(":material/warning: Zona de Mantenimiento / Puesta a Cero", expanded=bool(msg_reset)):
        st.warning("**Puesta a cero de datos de prueba**")
        st.markdown(
            "Pensada para limpiar los datos de prueba antes de empezar a operar. **No se borra nada:** "
            "las ventas y movimientos quedan archivados (siguen en la base y en el respaldo) y dejan de verse "
            "en la app. Se conservan siempre la configuración del comercio y los usuarios."
        )

        OPC_MOV = "Archivar movimientos y pruebas"
        OPC_TOTAL = "Reinicio total: archivar y dar de baja todo"
        opcion_reset = st.radio(
            "¿Qué querés poner a cero?",
            [OPC_MOV, OPC_TOTAL],
            key=f"rst_modo_{ver_reset}",
        )
        if opcion_reset == OPC_MOV:
            st.info(
                "Archiva **ventas, movimientos de cuenta corriente y de caja chica** "
                "y deja en **0** el saldo y los puntos de todos los clientes. "
                "Productos, categorías y clientes no cambian."
            )
        else:
            st.warning(
                "Archiva ventas y movimientos y además **da de baja productos, categorías y clientes**. "
                "Se pueden reactivar desde cada pantalla, en 'Dados de baja'."
            )

        rst_confirma = st.checkbox("Entiendo que las ventas y movimientos dejan de verse en la app", key=f"rst_chk_{ver_reset}")
        rst_palabra = st.text_input(
            "Para habilitar el botón, escribí la palabra ARCHIVAR (en mayúsculas):",
            placeholder="ARCHIVAR",
            key=f"rst_txt_{ver_reset}",
        )
        rst_pin = st.text_input(
            f"PIN de Dueño ({usuario_actual.get('nombre', '')}) para autorizar:",
            type="password",
            max_chars=4,
            key=f"rst_pin_{ver_reset}",
        )

        rst_habilitado = (
            rst_confirma
            and rst_palabra.strip() == "ARCHIVAR"
            and len(rst_pin) == 4
            and rst_pin.isdigit()
        )

        # Botón de ejecución en rojo (estilo acotado a este contenedor)
        st.markdown(
            "<style>.st-key-zona_peligro_btn button[kind='primary'] "
            "{ background-color:#DC2626 !important; border-color:#DC2626 !important; color:#fff !important; }"
            ".st-key-zona_peligro_btn button[kind='primary']:disabled { opacity:0.45 !important; }</style>",
            unsafe_allow_html=True,
        )
        with st.container(key="zona_peligro_btn"):
            ejecutar_reset = st.button(
                "PONER A CERO AHORA",
                type="primary",
                disabled=not rst_habilitado,
                width="stretch",
                key=f"rst_btn_{ver_reset}",
            )

        if ejecutar_reset and rst_habilitado:
            modo_reset = models.RESET_MOVIMIENTOS if opcion_reset == OPC_MOV else models.RESET_FABRICA
            try:
                with st.spinner("Ejecutando la puesta a cero..."):
                    resultado = models.resetear_datos(
                        modo=modo_reset,
                        usuario_id=usuario_actual["id"],
                        pin=rst_pin,
                        comercio_id=usuario_actual.get("comercio_id", models.COMERCIO_ID_DEFAULT)
                    )
                partes = [
                    f"{resultado.get('ventas', 0)} ventas",
                    f"{resultado.get('movimientos_cuenta', 0)} movimientos de cuenta corriente",
                    f"{resultado.get('movimientos_caja', 0)} movimientos de caja",
                ]
                texto = "Se archivaron: " + ", ".join(partes) + "."
                if modo_reset == models.RESET_MOVIMIENTOS:
                    texto += f" Saldo y puntos en 0 para {resultado.get('saldos_reseteados', 0)} cliente(s)."
                else:
                    texto += (f" Se dieron de baja: {resultado.get('productos', 0)} productos, "
                              f"{resultado.get('categorias', 0)} categorías y {resultado.get('clientes', 0)} clientes.")

                # Vaciar carrito y estado del POS (pueden apuntar a productos/clientes dados de baja)
                st.session_state.carrito = []
                st.session_state["_pos_reset_cant"] = True
                st.session_state["reset_msg"] = (
                    "ok",
                    "**Puesta a cero completada.** " + texto,
                )
            except models.BusinessLogicError as e:
                st.session_state["reset_msg"] = ("error", f"No se cambió nada: {e}")
            except Exception as e:
                st.session_state["reset_msg"] = (
                    "error",
                    f"Error al restablecer la base de datos. No se modificó ningún dato. Detalle: {e}",
                )
            st.session_state["reset_ver"] = ver_reset + 1
            st.rerun()






