"""
Interfaz de usuario con Streamlit para el Sistema de Gestión Interna.
Organizado en 6 módulos principales:
1. 🛒 Punto de Venta (POS) con Lector de Código de Barras, QR y Cuenta Corriente / Fiado
2. 👥 Cuentas Corrientes / Clientes ("La Libreta" de fiados, abonos y límites)
3. 📦 Productos e Inventario (Catálogo, Carga con Fotos, Edición Completa, Ajustes y Alertas)
4. 🏷️ Categorías
5. 📊 Arqueo de Caja y Cierre Diario en PDF / WhatsApp / Correo
6. ⚙️ Configuración del Negocio (Datos Bancarios, QR y SMTP)
"""
import os
import io
import re
import urllib.parse
import importlib
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
from config_manager import (
    cargar_configuracion,
    guardar_configuracion,
    validar_clave_admin,
    cambiar_clave_admin
)

# Configuración del directorio base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuración general de la página Streamlit
st.set_page_config(
    page_title="Sistema de Gestión Comercial",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ---------------- ESTILOS GLOBALES (SaaS Dashboard) ----------------
st.markdown("""
<style>
    /* Botones principales - Primary */
    .stButton > button[kind="primary"] {
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
        box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2), 0 2px 4px -2px rgba(37, 99, 235, 0.2) !important;
        transition: all 0.2s ease-in-out !important;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 8px -1px rgba(37, 99, 235, 0.3), 0 4px 6px -2px rgba(37, 99, 235, 0.3) !important;
    }
    
    /* Botones secundarios */
    .stButton > button[kind="secondary"] {
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease-in-out !important;
    }

    /* Contenedores con border=True (Tarjetas / Paneles) */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 10px !important;
        border: 1px solid #E2E8F0 !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05) !important;
        background-color: #FFFFFF !important;
    }

    /* Métricas nativas de Streamlit (st.metric) */
    [data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        padding: 1rem !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05) !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #0F172A !important;
    }

    /* Info / Success / Warning / Error alerts (Badges/Alerts) */
    [data-testid="stAlert"] {
        border-radius: 8px !important;
        border: none !important;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.02) !important;
    }

    /* Expander */
    [data-testid="stExpander"] {
        border-radius: 8px !important;
        border: 1px solid #E2E8F0 !important;
        background-color: #FFFFFF !important;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.02) !important;
    }

    /* Tablas / DataFrames */
    [data-testid="stDataFrame"] {
        border-radius: 8px !important;
        overflow: hidden !important;
        border: 1px solid #E2E8F0 !important;
    }
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
    /* Reducir espacio superior e inferior en la pantalla principal */
    .block-container {
        padding-top: 1.8rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 98% !important;
    }

    /* Botones primarios destacados y cómodos para touch o clic rápido */
    button[kind="primary"] {
        min-height: 46px !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        border-radius: 8px !important;
        letter-spacing: 0.3px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.08) !important;
        transition: transform 0.1s ease, box-shadow 0.1s ease !important;
    }
    button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.14) !important;
    }

    /* Botones secundarios más cómodos */
    button[kind="secondary"] {
        min-height: 40px !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }

    /* Contenedores con borde suave y moderno */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 10px !important;
        border-color: #E2E8F0 !important;
        background-color: #FFFFFF !important;
    }

    /* Reducir gap excesivo en bloques verticales */
    div[data-testid="stVerticalBlock"] > div {
        gap: 0.65rem !important;
    }

    /* Pestañas (Tabs) estilizadas */
    button[data-baseweb="tab"] {
        font-weight: 600 !important;
        font-size: 0.95rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Inicialización de estado de sesión para el carrito de compras y preferencias de vista
if "carrito" not in st.session_state:
    st.session_state.carrito = []

if "pos_vista_ficha" not in st.session_state:
    st.session_state.pos_vista_ficha = "Compacta"

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
    "🛒 Punto de Venta (POS)",
    "👥 Cuentas Corrientes / Clientes",
]
MODULOS_ADMIN = MODULOS_CAJERO + [
    "📦 Productos e Inventario",
    "🏷️ Categorías",
    "📊 Arqueo de Caja / Control Diario",
    "⚙️ Configuración del Negocio",
]


def _login_digito(digito):
    """Callback del teclado numérico: agrega un dígito al PIN (máx. 4)."""
    actual = st.session_state.get("login_pin", "")
    if len(actual) < 4:
        st.session_state["login_pin"] = actual + digito


def _login_borrar():
    st.session_state["login_pin"] = st.session_state.get("login_pin", "")[:-1]


def _login_limpiar():
    st.session_state["login_pin"] = ""


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
        usuario, error = models.verificar_login(usuario_id, pin)
    except Exception as e:
        usuario, error = None, f"⚠️ {e}"
    if usuario:
        st.session_state["usuario"] = usuario
    else:
        st.session_state["login_error"] = error
    st.rerun()


def _pantalla_login():
    """Pantalla de ingreso: selector de usuario + PIN de 4 dígitos (teclado táctil)."""
    # Pantalla limpia: sin barra lateral y con teclas grandes para uso táctil
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        div[data-testid="stButton"] button { min-height: 64px !important; font-size: 1.4rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        usuarios = models.listar_usuarios_login()
    except Exception as e:
        st.error(f"⚠️ {e}")
        st.stop()
    if not usuarios:
        st.warning("No hay usuarios activos configurados. Ejecutá sql/usuarios_auth.sql en Supabase.")
        st.stop()

    _, centro, _ = st.columns([1, 1.4, 1])
    with centro:
        st.markdown(
            f"<h1 style='text-align:center; margin-bottom:0;'>🏪 {config_negocio.get('nombre_negocio', 'Mi Comercio')}</h1>"
            "<p style='text-align:center; color:#64748B;'>Elegí tu usuario e ingresá tu PIN</p>",
            unsafe_allow_html=True,
        )

        iconos = {models.ROL_ADMIN: "👑", models.ROL_CAJERO: "🧾"}
        por_id = {u["id"]: u for u in usuarios}
        usuario_id = st.radio(
            "Usuario",
            options=list(por_id.keys()),
            format_func=lambda i: f"{iconos.get(por_id[i]['rol'], '👤')} {por_id[i]['nombre']}",
            horizontal=True,
            key="login_usuario_id",
            on_change=_login_limpiar,
        )

        pin = st.session_state.get("login_pin", "")
        st.markdown(
            f"<div style='text-align:center; font-size:2.4rem; letter-spacing:14px; margin:6px 0 2px;'>"
            f"{'●' * len(pin)}{'○' * (4 - len(pin))}</div>",
            unsafe_allow_html=True,
        )

        error = st.session_state.pop("login_error", None)
        if error:
            st.error(error)

        # Teclado numérico táctil
        teclas = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["C", "0", "⌫"]]
        for fila in teclas:
            cols = st.columns(3)
            for col, tecla in zip(cols, fila):
                if tecla == "C":
                    col.button("C", key="kp_clear", use_container_width=True, on_click=_login_limpiar)
                elif tecla == "⌫":
                    col.button("⌫", key="kp_back", use_container_width=True, on_click=_login_borrar)
                else:
                    col.button(tecla, key=f"kp_{tecla}", use_container_width=True,
                               on_click=_login_digito, args=(tecla,))

        # Alternativa con teclado físico (Enter para ingresar)
        with st.expander("⌨️ Escribir el PIN con el teclado"):
            with st.form("form_login_teclado", clear_on_submit=True):
                pin_txt = st.text_input("PIN (4 dígitos)", type="password", max_chars=4)
                if st.form_submit_button("Ingresar", type="primary", use_container_width=True):
                    _intentar_login(usuario_id, pin_txt)

        if len(pin) == 4:
            _intentar_login(usuario_id, pin)


if not st.session_state.get("usuario"):
    _pantalla_login()
    st.stop()

usuario_actual = st.session_state["usuario"]
# Mínimo privilegio: cualquier rol que no sea 'admin' se trata como cajero
es_admin = usuario_actual.get("rol") == models.ROL_ADMIN
modulos_permitidos = MODULOS_ADMIN if es_admin else MODULOS_CAJERO


# ==============================================================================
# BARRA LATERAL (NAVEGACIÓN Y ALERTAS GLOBALES)
# ==============================================================================
st.sidebar.title(f"🏪 {config_negocio.get('nombre_negocio', 'Mi Comercio')}")
st.sidebar.caption("Gestión Integral, POS, Clientes, Inventario & Caja")

st.sidebar.markdown(
    f"👤 **{usuario_actual.get('nombre', '')}** · "
    f"{models.ROL_ETIQUETAS.get(usuario_actual.get('rol'), 'Cajero')}"
)
st.sidebar.button("🚪 Cerrar Sesión", key="btn_logout", use_container_width=True, on_click=_cerrar_sesion)
with st.sidebar.expander("🔑 Cambiar mi PIN"):
    with st.form("form_cambiar_pin", clear_on_submit=True):
        pin_actual_in = st.text_input("PIN actual", type="password", max_chars=4)
        pin_nuevo_in = st.text_input("PIN nuevo (4 dígitos)", type="password", max_chars=4)
        if st.form_submit_button("Guardar PIN", use_container_width=True):
            try:
                models.cambiar_pin(usuario_actual["id"], pin_actual_in, pin_nuevo_in)
                st.success("✅ PIN actualizado.")
            except models.BusinessLogicError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"⚠️ {e}")

st.sidebar.markdown("---")

modulo = st.sidebar.radio("Navegación", modulos_permitidos)

# Guardia defensiva: aunque el menú ya está filtrado, nunca se renderiza un módulo no permitido
if modulo not in modulos_permitidos:
    st.error("⛔ No tenés permisos para acceder a esta sección.")
    st.stop()

st.sidebar.markdown("---")

# Tarjetas Métricas y Alertas Globales en Barra Lateral
prods_criticos_global = models.obtener_productos_bajo_stock()
cant_criticos = len(prods_criticos_global)

if cant_criticos > 0:
    st.sidebar.markdown(
        f"""
        <div style="background: #FEF2F2; border: 1px solid #FECACA; border-radius: 9px; padding: 10px 14px; margin-bottom: 10px;">
            <div style="font-size: 0.72rem; color: #991B1B; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">
                ⚠️ Alerta de Inventario
            </div>
            <div style="font-size: 1.05rem; font-weight: 800; color: #DC2626; margin-top: 2px;">
                {cant_criticos} artículo(s) bajo stock
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    with st.sidebar.expander("🔎 Ver artículos en alerta"):
        for p_crit in (prods_criticos_global.to_dict("records") if hasattr(prods_criticos_global, "to_dict") else prods_criticos_global):
            st.markdown(
                f"- **{p_crit['nombre']}** (`{p_crit['codigo']}`): "
                f"<span style='color:#DC2626; font-weight:bold;'>{p_crit['stock_actual']}</span> / mín. {p_crit['stock_minimo']}",
                unsafe_allow_html=True
            )
else:
    st.sidebar.markdown(
        """
        <div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 9px; padding: 10px 14px; margin-bottom: 10px;">
            <div style="font-size: 0.72rem; color: #166534; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">
                📦 Estado del Stock
            </div>
            <div style="font-size: 0.95rem; font-weight: 700; color: #15803D; margin-top: 2px;">
                ✅ Catálogo con stock saludable
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# KPI de Cuentas Corrientes en la Barra Lateral
resumen_deuda_sidebar = models.obtener_resumen_deuda_total()
total_deuda_side = resumen_deuda_sidebar.get("total_deuda", 0.0)
clientes_deuda_side = resumen_deuda_sidebar.get("clientes_con_deuda", 0)

if total_deuda_side > 0:
    st.sidebar.markdown(
        f"""
        <div style="background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 9px; padding: 10px 14px; margin-bottom: 12px;">
            <div style="font-size: 0.72rem; color: #92400E; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">
                💸 Deuda Total en Clientes
            </div>
            <div style="font-size: 1.25rem; font-weight: 800; color: #B45309; margin-top: 2px;">
                ${total_deuda_side:,.2f}
            </div>
            <div style="font-size: 0.75rem; color: #A16207; margin-top: 2px;">
                👤 {clientes_deuda_side} cliente(s) con saldo en cuenta corriente
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# ==============================================================================
# MÓDULO 1: PUNTO DE VENTA (POS) CON LECTOR DE BARRAS & CUENTA CORRIENTE
# ==============================================================================
if modulo == "🛒 Punto de Venta (POS)":
    st.header("🛒 Terminal de Punto de Venta")

    # 1. INTEGRACIÓN CON LECTORA DE CÓDIGO DE BARRAS (EAN / SKU)
    with st.form("form_barcode_scanner", clear_on_submit=True):
        col_scan_txt, col_scan_btn = st.columns([3.5, 1], gap="small")
        with col_scan_txt:
            barcode_in = st.text_input(
                "🔍 Escanear Código de Barras (EAN / SKU):",
                placeholder="Pase el lector óptico aquí o ingrese el código y presione Enter...",
                key="barcode_scanner_field"
            )
        with col_scan_btn:
            st.write("")
            btn_scan = st.form_submit_button("⚡ Cargar por Código", use_container_width=True)

        if btn_scan and barcode_in:
            prod_esc = models.obtener_producto_por_codigo(barcode_in)
            if not prod_esc:
                st.error(f"❌ Código '{barcode_in}' no registrado en el catálogo.")
            else:
                cant_en_cart = sum(it["cantidad"] for it in st.session_state.carrito if it["producto_id"] == prod_esc["id"])
                if prod_esc["stock_actual"] - cant_en_cart <= 0:
                    st.error(f"❌ Stock insuficiente para '{prod_esc['nombre']}' (Stock actual: {prod_esc['stock_actual']}).")
                else:
                    encontrado = False
                    for it in st.session_state.carrito:
                        if it["producto_id"] == prod_esc["id"]:
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
                            "imagen_path": prod_esc.get("imagen_path")
                        })
                    st.toast(f"🛒 Agregado: {prod_esc['nombre']} x1 ($ {prod_esc['precio_venta']:,.2f})", icon="📦")
                    st.rerun()

    st.markdown("---")

    col_izq, col_der = st.columns([1.05, 1.35], gap="medium")

    with col_izq:
        c_tit, c_vista = st.columns([1.5, 1.5], gap="small")
        with c_tit:
            st.subheader("Búsqueda Manual")
        with c_vista:
            opciones_vista = ["Grande", "Compacta", "Sin imagen"]
            valor_actual = st.session_state.get("pos_vista_ficha", "Compacta")
            vista_idx = opciones_vista.index(valor_actual) if valor_actual in opciones_vista else 1
            vista_elegida = st.radio(
                "Vista Ficha:",
                options=opciones_vista,
                index=vista_idx,
                horizontal=True,
                key="radio_pos_vista_ficha",
                help="Ajustá el tamaño visual de la ficha del producto."
            )
            st.session_state.pos_vista_ficha = vista_elegida

        productos_db = models.obtener_productos()
        if len(productos_db) == 0:
            st.warning("⚠️ No hay productos registrados. Por favor, agregue productos en la sección de Inventario.")
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
                    format_func=lambda p: f"{p['nombre']} - ${p['precio_venta']:,.2f}",
                    key="pos_select_producto"
                )

                stock_actual = float(prod_info.get("stock_actual", 0))
                stock_minimo = float(prod_info.get("stock_minimo", 0))
                es_critico = stock_actual <= stock_minimo

                # 3. Renderizado dinámico de la ficha según la vista elegida
                if st.session_state.pos_vista_ficha == "Grande":
                    with st.container(border=True):
                        col_foto, col_datos = st.columns([1, 2])
                        with col_foto:
                            img_abs = obtener_ruta_imagen_absoluta(prod_info.get("imagen_path"))
                            if img_abs:
                                st.image(img_abs, caption=prod_info["nombre"], width=120)
                            else:
                                st.markdown(
                                    """
                                    <div style="border: 2px dashed #bbb; border-radius: 8px; padding: 25px; text-align: center; color: #777;">
                                        📷<br><small>Sin foto</small>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                        with col_datos:
                            st.subheader(prod_info["nombre"])
                            st.markdown(f"**Código:** `{prod_info['codigo']}`")
                            st.markdown(f"**Precio de Venta:** ${prod_info['precio_venta']:,.2f}`")
                            
                            if es_critico:
                                st.markdown(
                                    f"<div style='background-color: #ffebee; color: #c62828; padding: 10px; border-radius: 5px; font-weight: bold;'>"
                                    f"⚠️ ¡ALERTA DE STOCK CRÍTICO! — Stock disponible: **{stock_actual:g}** unidades (Umbral mínimo: **{stock_minimo:g}**)."
                                    f"</div>",
                                    unsafe_allow_html=True
                                )
                            else:
                                st.success(f"✅ Stock disponible: **{stock_actual:g}** unidades (Mínimo: {stock_minimo:g})")

                elif st.session_state.pos_vista_ficha == "Compacta":
                    with st.container(border=True):
                        col_thumb, col_datos = st.columns([0.8, 3.2], gap="small")
                        with col_thumb:
                            img_abs = obtener_ruta_imagen_absoluta(prod_info.get("imagen_path"))
                            if img_abs:
                                st.image(img_abs, width=80)
                            else:
                                st.markdown(
                                    """
                                    <div style="border: 1px dashed #bbb; border-radius: 8px; width: 80px; height: 80px; display: flex; align-items: center; justify-content: center; font-size: 24px; color: #888; background: #fafafa;">
                                        📦
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                        with col_datos:
                            st.markdown(f"**{prod_info['nombre']}** (`{prod_info['codigo']}`)")
                            st.markdown(f"💰 **Precio:** **${prod_info['precio_venta']:,.2f}**")
                            if es_critico:
                                st.markdown(
                                    f"<div style='color: #c62828; font-size: 0.88rem; font-weight: bold; background: #fee2e2; padding: 3px 8px; border-radius: 4px; display: inline-block;'>"
                                    f"⚠️ Stock Crítico: {stock_actual:g} (Mín: {stock_minimo:g})"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )
                            else:
                                st.markdown(
                                    f"<div style='color: #166534; font-size: 0.88rem; font-weight: bold; background: #dcfce7; padding: 3px 8px; border-radius: 4px; display: inline-block;'>"
                                    f"✅ Stock: {stock_actual:g} unid. (Mín: {stock_minimo:g})"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )

                else:  # "Sin imagen"
                    with st.container(border=True):
                        c_nom, c_pre, c_stk = st.columns([2.2, 1.2, 1.6], gap="small")
                        with c_nom:
                            st.markdown(f"**{prod_info['nombre']}** (`{prod_info['codigo']}`)")
                        with c_pre:
                            st.markdown(f"💰 **${prod_info['precio_venta']:,.2f}**")
                        with c_stk:
                            if es_critico:
                                st.markdown(
                                    f"<div style='color: #c62828; font-weight: bold; font-size: 0.85rem; background: #fee2e2; padding: 3px 6px; border-radius: 4px; text-align: center;'>"
                                    f"⚠️ Stock: {stock_actual:g}"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )
                            else:
                                st.markdown(
                                    f"<div style='color: #166534; font-weight: bold; font-size: 0.85rem; background: #dcfce7; padding: 3px 6px; border-radius: 4px; text-align: center;'>"
                                    f"✅ Stock: {stock_actual:g}"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )
                
                cant_en_carrito = sum(
                    item["cantidad"] for item in st.session_state.carrito if item["producto_id"] == prod_info["id"]
                )
                disponible_para_agregar = stock_actual - cant_en_carrito
                
                col_cant, col_btn = st.columns([1.15, 1.05], gap="medium")
                with col_cant:
                    tipo_venta = st.radio("¿Vender por?", ["Cantidad / Peso", "Monto ($)"], horizontal=True)

                    if tipo_venta == "Cantidad / Peso":
                        # Accesos rápidos de peso/fracción de un clic (on_click: el callback se
                        # ejecuta antes del re-render, por eso puede modificar la key del widget)
                        c_q1, c_q2, c_q3, c_q4 = st.columns(4)
                        with c_q1:
                            st.button("250 g", key="btn_q_250", use_container_width=True,
                                      on_click=_set_pos_cant, args=(0.250,))
                        with c_q2:
                            st.button("500 g", key="btn_q_500", use_container_width=True,
                                      on_click=_set_pos_cant, args=(0.500,))
                        with c_q3:
                            st.button("1 kg", key="btn_q_1kg", use_container_width=True,
                                      on_click=_set_pos_cant, args=(1.000,))
                        with c_q4:
                            st.button("+1", key="btn_q_plus1", use_container_width=True,
                                      on_click=_sumar_pos_cant, args=(1.0,))

                        # Reseteo pendiente tras agregar al carrito (o key perdida): debe
                        # aplicarse ANTES de instanciar el widget.
                        if st.session_state.pop("_pos_reset_cant", False) or "pos_cant_val" not in st.session_state:
                            st.session_state["pos_cant_val"] = 1.0

                        cantidad = st.number_input(
                            "Cantidad / Peso:",
                            min_value=0.001,
                            step=1.0,
                            format="%.3f",
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
                            st.info(f"⚖️ Equivale a **{cantidad:g}** unidades/kg")
                        else:
                            cantidad = 0.0

                with col_btn:
                    st.markdown("<div style='height: 38px;'></div>", unsafe_allow_html=True)
                    deshabilitar_agregar = (disponible_para_agregar <= 0) or (cantidad <= 0)
                    if st.button("➕ AGREGAR AL CARRITO", type="primary", disabled=deshabilitar_agregar, use_container_width=True):
                        if disponible_para_agregar <= 0:
                            st.error("No hay más unidades disponibles de este producto.")
                        elif cantidad <= 0:
                            st.warning("Ingrese una cantidad o monto válido.")
                        else:
                            encontrado = False
                            for item in st.session_state.carrito:
                                if item["producto_id"] == prod_info["id"]:
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
                                    "imagen_path": prod_info.get("imagen_path")
                                })
                            # Resetear cantidad a 1.0 para el siguiente artículo. El widget ya
                            # fue instanciado en este run, así que no se puede tocar su key
                            # acá: se deja una bandera que se aplica ANTES de dibujarlo.
                            st.session_state["_pos_reset_cant"] = True
                            st.toast(f"✅ Agregado: {prod_info['nombre']} x{cantidad:g} (${cantidad * prod_info['precio_venta']:,.2f})", icon="🛒")
                            st.rerun()

    # Panel derecho: Carrito de compras, Selector de Cliente, Medio de pago y Cobro
    with col_der:
        st.subheader("Carrito Actual")

        # 1. Selector opcional de Cliente en la cabecera del carrito
        clientes_pos = models.obtener_clientes()
        opciones_clientes = ["Consumidor Final"]
        mapa_clientes = {}
        for c in clientes_pos:
            lbl = f"{c['nombre']} (Tel: {c.get('telefono') or 'S/T'} | Deuda: ${c['saldo_deudor']:,.2f})"
            opciones_clientes.append(lbl)
            mapa_clientes[lbl] = c

        cliente_elegido_label = st.selectbox(
            "👤 Cliente:",
            opciones_clientes,
            help="Por defecto Consumidor Final. Seleccioná un cliente para asociar la venta, cuenta corriente o enviar comprobante por WhatsApp."
        )
        cliente_pos = mapa_clientes.get(cliente_elegido_label)
        cliente_pos_id = cliente_pos["id"] if cliente_pos else None

        if cliente_pos_id:
            total_venta_previa = round(sum(item["subtotal"] for item in st.session_state.carrito), 2)
            pts_actual = cliente_pos.get('puntos', 0)
            pts_sumar = round(total_venta_previa * 0.01, 2)
            if total_venta_previa > 0:
                st.success(f"🏷️ **Puntos Acumulados:** {pts_actual:,.2f} pts  |  ✨ **Esta compra sumará:** +{pts_sumar:,.2f} pts")
            else:
                st.info(f"🏷️ **Puntos Acumulados:** {pts_actual:,.2f} pts")

        # 2. Bloque de Comprobante / Ticket recién emitido (si existe)
        if "ultimo_ticket" in st.session_state and st.session_state["ultimo_ticket"]:
            tk = st.session_state["ultimo_ticket"]
            with st.container(border=True):
                st.markdown(f"#### 🧾 Comprobante: Ticket #{tk['venta_id']}")
                st.caption(f"Cliente: **{tk['cliente_nombre']}** | Total: **${tk['total']:,.2f}** ({tk['forma_pago']})")

                c_pdf, c_wa = st.columns([1, 1], gap="small")
                with c_pdf:
                    st.download_button(
                        label="📄 Descargar Ticket (PDF 80mm)",
                        data=tk["pdf_bytes"],
                        file_name=f"ticket_{tk['venta_id']}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                with c_wa:
                    tel = tk.get("cliente_telefono")
                    if tel:
                        msg_whatsapp = reportes.armar_mensaje_whatsapp_ticket(tk)
                        wa_url = reportes.armar_url_whatsapp(tel, msg_whatsapp)
                        st.link_button("📲 Enviar por WhatsApp", url=wa_url, use_container_width=True)
                    else:
                        st.caption("ℹ️ Sin teléfono para WhatsApp")

                if st.button("✖️ Cerrar Comprobante", key="btn_cerrar_tk", use_container_width=True):
                    del st.session_state["ultimo_ticket"]
                    st.rerun()

        # 3. Lista de productos del carrito
        if not st.session_state.carrito:
            st.info("El carrito está vacío. Agregue artículos escaneando o desde el panel izquierdo.")
        else:
            for idx, item in enumerate(st.session_state.carrito):
                with st.container(border=True):
                    c_img, c_info, c_sub, c_del = st.columns([0.6, 2.7, 1.4, 0.6], gap="small")
                    with c_img:
                        img_item = obtener_ruta_imagen_absoluta(item.get("imagen_path"))
                        if img_item:
                            st.image(img_item, width=44)
                        else:
                            st.markdown("<div style='font-size: 20px; text-align: center; margin-top: 4px;'>📦</div>", unsafe_allow_html=True)
                    with c_info:
                        st.markdown(f"**{item['nombre']}** (`{item['codigo']}`)")
                        st.caption(f"{item['cantidad']:g} unid. x ${item['precio_unitario']:,.2f}")
                    with c_sub:
                        st.markdown(f"**${item['subtotal']:,.2f}**")
                    with c_del:
                        if st.button("❌", key=f"del_cart_{idx}"):
                            st.session_state.carrito.pop(idx)
                            st.rerun()

            total_venta = round(sum(item["subtotal"] for item in st.session_state.carrito), 2)
            st.markdown(
                f"""
                <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; border-radius: 9px; padding: 10px 16px; margin: 10px 0; display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 1.05rem; font-weight: 700; color: #475569;">Total a Cobrar:</span>
                    <span style="font-size: 1.6rem; font-weight: 800; color: #0F172A;">${total_venta:,.2f}</span>
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
                    st.markdown("#### 📱 Datos para Cobro Electrónico")
                    col_qr_vista, col_banco_vista = st.columns([1, 1.5], gap="small")
                    with col_qr_vista:
                        qr_abs = obtener_ruta_imagen_absoluta(config_negocio.get("qr_imagen_path"))
                        if qr_abs:
                            st.image(qr_abs, caption="Escanear Código QR", use_container_width=True)
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
                    st.markdown("#### 👥 Asignar Venta a Cuenta Corriente")
                    if cliente_pos is None:
                        st.error("⛔ Para fiar en Cuenta Corriente debés seleccionar un cliente registrado arriba en el selector de 'Cliente' (no puede ser Consumidor Final).")
                        bloquear_venta_fiado = True
                    else:
                        saldo_previsto = cliente_pos["saldo_deudor"] + total_venta
                        col_c1, col_c2 = st.columns(2)
                        with col_c1:
                            st.markdown(f"**Saldo Actual:** ${cliente_pos['saldo_deudor']:,.2f}")
                            st.markdown(f"**Límite Máximo:** ${cliente_pos['limite_credito']:,.2f}" if cliente_pos['limite_credito'] > 0 else "**Límite:** Sin límite")
                        with col_c2:
                            st.markdown(f"**Saldo Tras la Venta:** **${saldo_previsto:,.2f}**")

                        if cliente_pos["limite_credito"] > 0 and saldo_previsto > cliente_pos["limite_credito"]:
                            st.error(f"⛔ **LÍMITE EXCEDIDO:** La venta superará el límite de crédito configurado (${cliente_pos['limite_credito']:,.2f}).")
                            bloquear_venta_fiado = True
                        else:
                            st.success(f"✅ Venta autorizada a la cuenta de {cliente_pos['nombre']}.")

            st.write("")
            col_btn_vender, col_btn_vaciar = st.columns([2.5, 1], gap="small")
            with col_btn_vaciar:
                if st.button("🗑️ Vaciar", use_container_width=True):
                    st.session_state.carrito = []
                    st.rerun()
            with col_btn_vender:
                boton_deshabilitado = bloquear_venta_fiado
                if st.button(f"✅ CONFIRMAR Y COBRAR (${total_venta:,.2f})", type="primary", disabled=boton_deshabilitado, use_container_width=True):

                    try:
                        items_venta = [
                            {"producto_id": it["producto_id"], "cantidad": it["cantidad"]}
                            for it in st.session_state.carrito
                        ]
                        items_ticket = [dict(it) for it in st.session_state.carrito]
                        total_ticket = total_venta
                        fecha_ticket = datetime.now(ZONA_HORARIA).strftime("%d/%m/%Y %H:%M")
                        nombre_cli_tk = cliente_pos["nombre"] if cliente_pos else "Consumidor Final"

                        venta_id, puntos_ganados = models.registrar_venta(
                            items=items_venta,
                            forma_pago=forma_pago,
                            cliente_id=cliente_pos_id
                        )

                        puntos_balance = 0.0
                        if cliente_pos_id:
                            cli_upd = next((c for c in models.obtener_clientes() if c["id"] == cliente_pos_id), None)
                            if cli_upd:
                                puntos_balance = cli_upd.get("puntos", 0)

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
                            "negocio_nombre": config_negocio.get("nombre_negocio", "Mi Comercio")
                        }

                        st.session_state.carrito = []
                        st.balloons()
                        st.success(f"🎉 ¡Venta #{venta_id} confirmada por ${total_ticket:,.2f} ({forma_pago})!")
                        st.rerun()
                    except models.InsufficientStockError as err:
                        st.error(f"Stock insuficiente: {err}")
                    except Exception as err:
                        st.error(f"Error al registrar la venta: {err}")


# ==============================================================================
# MÓDULO 2: CUENTAS CORRIENTES / CLIENTES ("LA LIBRETA")
# ==============================================================================
elif modulo == "👥 Cuentas Corrientes / Clientes":
    st.header("👥 Cuentas Corrientes / Clientes (\"La Libreta\")")
    st.caption("Control de fiados, límites de crédito, registro de abonos e historial de cuenta por cliente.")

    # Resumen Financiero de Cuentas Corrientes
    resumen_deuda = models.obtener_resumen_deuda_total()
    col_k1, col_k2, col_k3 = st.columns(3)
    col_k1.metric("💸 Deuda Total en la Calle", f"${resumen_deuda.get('total_deuda', 0.0):,.2f}")
    col_k2.metric("⚠️ Clientes con Deuda Activa", f"{resumen_deuda.get('clientes_con_deuda', 0)} clientes")
    col_k3.metric("👤 Clientes Registrados", f"{resumen_deuda.get('total_clientes', 0)}")

    st.markdown("---")

    _tabs_clientes = [
        "📋 Libreta de Clientes",
        "➕ Nuevo Cliente",
        "💵 Registrar Abono / Pago",
        "📜 Ficha e Historial de Movimientos",
    ]
    if es_admin:
        _tabs_clientes.append("✏️ Modificar / Eliminar Cliente")
    _tabs_obj = st.tabs(_tabs_clientes)
    tab_c_lista, tab_c_nuevo, tab_c_abono, tab_c_ficha = _tabs_obj[:4]
    tab_c_edit = _tabs_obj[4] if es_admin else None

    # 1. Catálogo / Libreta de Clientes
    with tab_c_lista:
        busqueda_cli = st.text_input("🔍 Buscar cliente por nombre o teléfono:", "")
        clientes = models.obtener_clientes(busqueda=busqueda_cli or None)

        if not clientes:
            st.info("No se encontraron clientes registrados.")
        else:
            for c in clientes:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 1.5, 1.5, 1.5])
                    with c1:
                        st.markdown(f"### {c['nombre']}")
                        st.caption(f"📞 Tel: {c['telefono'] or 'Sin teléfono'} | ✉️ {c['email'] or 'Sin correo'}")
                    with c2:
                        limite_txt = f"${c['limite_credito']:,.2f}" if c['limite_credito'] > 0 else "Sin límite"
                        st.markdown(f"**Límite de Crédito:** {limite_txt}")
                    with c3:
                        if c["saldo_deudor"] > 0:
                            st.error(f"🔴 **Debe: ${c['saldo_deudor']:,.2f}**")
                        else:
                            st.success("🟢 **Al día ($0.00)**")
                    with c4:
                        st.markdown(f"🏷️ **Puntos:** {c.get('puntos', 0):,.2f}")
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

            btn_crear_cli = st.form_submit_button("💾 Guardar Cliente", type="primary")
            if btn_crear_cli:
                try:
                    nuevo_cid = models.crear_cliente(
                        nombre=nom_cli,
                        telefono=tel_cli,
                        email=mail_cli,
                        limite_credito=limite_cli
                    )
                    st.success(f"✅ ¡Cliente '{nom_cli}' registrado con éxito! (ID: {nuevo_cid})")
                    st.rerun()
                except models.BusinessLogicError as e:
                    st.error(f"Error de validación: {e}")
                except Exception as e:
                    st.error(f"Error inesperado: {e}")

    # 3. Registrar Abono / Pago
    with tab_c_abono:
        st.subheader("💵 Registrar Pago o Abono a Cuenta Corriente")
        clientes_abono = models.obtener_clientes()
        if not clientes_abono:
            st.info("No hay clientes registrados.")
        else:
            dict_cli_abono = {
                f"{c['nombre']} (Saldo Deudor: ${c['saldo_deudor']:,.2f})": c
                for c in clientes_abono
            }
            sel_cli_abono = st.selectbox("Seleccione el Cliente:", list(dict_cli_abono.keys()), key="select_cli_abono")
            cli_a_abonar = dict_cli_abono[sel_cli_abono]

            with st.container(border=True):
                st.markdown(f"#### Ficha: {cli_a_abonar['nombre']}")
                st.markdown(f"**Deuda Actual:** :red[**${cli_a_abonar['saldo_deudor']:,.2f}**]")

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
                    st.markdown(f"**Saldo Restante:** :green[**${nuevo_saldo_previsto:,.2f}**]")
                    nota_abono = st.text_input("Nota / Comprobante (Opcional):", placeholder="Ej: Pago parcial efectivo")

                if st.button("✅ Confirmar y Registrar Abono", type="primary"):
                    try:
                        mov_id = models.registrar_abono_cliente(
                            cliente_id=cli_a_abonar["id"],
                            monto=monto_abono,
                            metodo_pago=metodo_abono,
                            descripcion=nota_abono or None
                        )
                        st.success(f"🎉 Abono registrado con éxito (#{mov_id}) por ${monto_abono:,.2f}. Nuevo saldo: ${nuevo_saldo_previsto:,.2f}")
                        st.rerun()
                    except models.BusinessLogicError as e:
                        st.error(f"Error: {e}")
                    except Exception as e:
                        st.error(f"Error al registrar abono: {e}")

    # 4. Ficha e Historial Cronológico
    with tab_c_ficha:
        st.subheader("📜 Historial de Cuenta Corriente")
        clientes_ficha = models.obtener_clientes()
        if not clientes_ficha:
            st.info("No hay clientes registrados.")
        else:
            dict_cli_ficha = {f"{c['nombre']} (${c['saldo_deudor']:,.2f})": c for c in clientes_ficha}
            sel_ficha = st.selectbox("Seleccione el cliente a consultar:", list(dict_cli_ficha.keys()), key="sel_ficha_cli")
            cli_f = dict_cli_ficha[sel_ficha]

            with st.container(border=True):
                c_f1, c_f2, c_f3, c_f4 = st.columns([2, 1.5, 1.5, 1.5])
                c_f1.markdown(f"**Cliente:** {cli_f['nombre']}")
                c_f1.caption(f"📞 {cli_f['telefono'] or 'S/T'} | ✉️ {cli_f['email'] or 'S/E'}")
                c_f2.markdown(f"**Límite de Crédito:** ${cli_f['limite_credito']:,.2f}" if cli_f['limite_credito'] > 0 else "**Límite:** Sin límite")
                c_f3.markdown(f"**Saldo Deudor:** :red[**${cli_f['saldo_deudor']:,.2f}**]" if cli_f['saldo_deudor'] > 0 else "**Saldo Deudor:** :green[**$0.00**]")
                c_f4.markdown(f"🏷️ **Puntos:** {cli_f.get('puntos', 0):,.2f}")

            movimientos = models.obtener_movimientos_cliente(cli_f["id"])
            if not movimientos:
                st.info("Este cliente no tiene movimientos registrados aún.")
            else:
                df_movs = pd.DataFrame(movimientos)
                df_movs["tipo_fmt"] = df_movs["tipo"].map({"CARGO": "🔴 CARGO (Compra Fiada)", "PAGO": "🟢 PAGO (Abono)"})
                df_movs["monto_fmt"] = df_movs["monto"].apply(lambda x: f"${x:,.2f}")
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
                st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

    # 5. Edición y Baja de Clientes
    if tab_c_edit is not None:  # Solo el Dueño ve esta solapa
        with tab_c_edit:
            st.subheader("✏️ Modificar o Dar de Baja Cliente")
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

                    btn_guardar_cli = st.form_submit_button("💾 Guardar Cambios de Cliente", type="primary")
                    if btn_guardar_cli:
                        try:
                            models.actualizar_cliente(cid, e_nom, e_tel, e_mail, e_limite)
                            st.success("✅ Datos del cliente actualizados.")
                            st.rerun()
                        except models.BusinessLogicError as e:
                            st.error(f"Error: {e}")

                with st.expander("🗑️ Zona de Baja: Eliminar Cliente"):
                    st.warning("Solo se permite eliminar clientes sin deuda pendiente ($0.00).")
                    chk_del_cli = st.checkbox("Confirmo que deseo eliminar este cliente", key=f"chk_del_c_{cid}")
                    if st.button("Confirmar Eliminación de Cliente", type="secondary", disabled=not chk_del_cli, key=f"btn_del_c_{cid}"):
                        try:
                            models.eliminar_cliente(cid)
                            st.success("Cliente eliminado exitosamente.")
                            st.rerun()
                        except models.BusinessLogicError as e:
                            st.error(f"No se pudo eliminar: {e}")


# ==============================================================================
# MÓDULO 3: GESTIÓN DE PRODUCTOS E INVENTARIO
# ==============================================================================
elif modulo == "📦 Productos e Inventario":
    st.header("📦 Gestión de Productos e Inventario")

    # Mensaje de confirmación de la acción anterior (sobrevive al st.rerun())
    if "flash_inventario" in st.session_state:
        st.success(st.session_state.pop("flash_inventario"))

    tab_catalogo, tab_nuevo, tab_editar, tab_ajuste, tab_alertas = st.tabs([
        "📋 Catálogo de Productos",
        "➕ Nuevo Producto",
        "✏️ Editar Producto",
        "🔄 Ajuste de Stock",
        "🚨 Monitor de Stock Crítico"
    ])

    # 1. Catálogo Completo
    with tab_catalogo:
        categorias = models.obtener_categorias()
        
        with st.expander("📈 Actualización Masiva de Precios"):
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
                    simular = st.form_submit_button("🔍 Simular / Previsualizar", use_container_width=True)
                with col_btn2:
                    aplicar = st.form_submit_button("✅ Aplicar Aumento Masivo", type="primary", use_container_width=True)

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
                                "Precio Actual": f"${float(p['precio_venta']):,.2f}",
                                "Nuevo Precio": f"${nuevo_venta:,.2f}",
                                "Diferencia": f"${(nuevo_venta - float(p['precio_venta'])):,.2f}"
                            })
                        
                        if simular:
                            st.markdown(f"**Previsualización de {len(lista_preview)} producto(s) a modificar:**")
                            st.dataframe(pd.DataFrame(lista_preview), use_container_width=True, hide_index=True)
                            
                        if aplicar:
                            comercio_id_actual = usuario_actual.get("comercio_id", models.COMERCIO_ID_DEFAULT)
                            exitosos = models.actualizar_precios_masivamente(modificados, comercio_id=comercio_id_actual)
                            st.session_state["flash_inventario"] = f"✅ ¡Aumento masivo aplicado con éxito! Se actualizaron {exitosos} productos."
                            st.rerun()

        col_filtro1, col_filtro2 = st.columns([2, 1])
        with col_filtro1:
            busqueda = st.text_input("🔍 Buscar por nombre o código / barra:", "")
        with col_filtro2:
            opciones_cat = {"Todas las categorías": None}
            for c in categorias:
                opciones_cat[c["nombre"]] = c["id"]
            cat_seleccionada = st.selectbox("Filtrar por Categoría:", list(opciones_cat.keys()))
            cat_id_filtro = opciones_cat[cat_seleccionada]

        productos = models.obtener_productos(busqueda=busqueda or None, categoria_id=cat_id_filtro)

        if productos:
            for p in productos:
                with st.container(border=True):
                    col_p_img, col_p_det, col_p_precios, col_p_stock = st.columns([1, 2.5, 2, 2])

                    with col_p_img:
                        img_prod = obtener_ruta_imagen_absoluta(p.get("imagen_path"))
                        if img_prod:
                            st.image(img_prod, use_container_width=True)
                        else:
                            st.markdown(
                                """<div style="border:1px dashed #ccc; border-radius:6px; padding:20px 0; text-align:center; color:#999;">
                                📷<br><small>Sin foto</small></div>""",
                                unsafe_allow_html=True
                            )

                    with col_p_det:
                        st.markdown(f"### {p['nombre']}")
                        st.markdown(f"**Código / Barra:** `{p['codigo']}`")
                        st.caption(f"Categoría: **{p['categoria_nombre']}**")

                    with col_p_precios:
                        st.markdown(f"**Costo:** ${p['precio_costo']:,.2f}")
                        st.markdown(f"**Margen:** {p['margen_ganancia']:.1f}%")
                        tipo_precio = "Manual" if p["usa_precio_manual"] == 1 else "Auto"
                        st.markdown(f"**Venta:** :green[**${p['precio_venta']:,.2f}**] *({tipo_precio})*")

                    with col_p_stock:
                        st.markdown(f"**Stock Mínimo:** {p['stock_minimo']} unid.")
                        if p["stock_actual"] <= p["stock_minimo"]:
                            st.error(f"🚨 **Stock:** **{p['stock_actual']}** unidades")
                            st.caption("⚠️ Requiere reposición")
                        else:
                            st.success(f"📦 **Stock:** **{p['stock_actual']}** unidades")
                            st.caption("Nivel adecuado")
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
            st.info(f"💡 Precio Calculado Automático: **${precio_sugerido:,.2f}**")

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

        if st.button("💾 Guardar Producto", type="primary", key=f"np_guardar_{vnp}"):
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
                    imagen_path=ruta_img_guardada
                )
                st.session_state["flash_inventario"] = f"✅ ¡Producto '{nombre.strip()}' creado con éxito! (ID: {nuevo_id})"
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
        st.subheader("✏️ Edición Completa de Producto")
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
            # Las keys dependen de los datos vigentes: si cambian en la base (ej. una venta baja el stock),
            # los widgets se regeneran con el valor real y no se pisa el stock con uno viejo al guardar.
            kp = (f"{pid}_{prod_actual['stock_actual']:g}_{prod_actual['stock_minimo']:g}_"
                  f"{prod_actual['precio_costo']:g}_{prod_actual['margen_ganancia']:g}_{prod_actual['precio_venta']:g}")

            st.markdown("---")

            col_ed1, col_ed2 = st.columns(2, gap="large")

            with col_ed1:
                st.markdown("#### 📝 Información General y Foto")
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

                st.markdown("##### 📷 Fotografía del Producto")
                img_actual_abs = obtener_ruta_imagen_absoluta(prod_actual.get("imagen_path"))
                eliminar_foto_check = False

                if img_actual_abs:
                    c_f1, c_f2 = st.columns([1, 1.5])
                    with c_f1:
                        st.image(img_actual_abs, caption="Foto actual", width=120)
                    with c_f2:
                        eliminar_foto_check = st.checkbox("🗑️ Eliminar foto actual", key=f"del_foto_{kp}")
                else:
                    st.caption("ℹ️ Sin foto asignada actualmente.")

                nueva_foto_subida = st.file_uploader(
                    "Subir nueva foto (reemplaza o agrega)",
                    type=["jpg", "jpeg", "png"],
                    key=f"upload_foto_{kp}"
                )

            with col_ed2:
                st.markdown("#### 💰 Precios y Control de Inventario")
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
                st.info(f"💡 Precio Calculado Automático: **${precio_sugerido_edit:,.2f}**")

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

            st.write("")
            col_save_btn, col_del_btn = st.columns([1.5, 1], gap="medium")

            with col_save_btn:
                if st.button("💾 Guardar Cambios", type="primary", use_container_width=True, key=f"btn_save_{kp}"):
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
                            eliminar_imagen=eliminar_foto
                        )
                        # Guardado OK: si la foto cambió o se quitó, borrar el archivo local anterior
                        if ruta_img_final or eliminar_foto:
                            borrar_archivo_imagen_local(prod_actual.get("imagen_path"))
                        st.session_state["flash_inventario"] = f"✅ ¡Producto '{nombre_edit.strip()}' actualizado con éxito!"
                        st.rerun()
                    except models.BusinessLogicError as e:
                        borrar_archivo_imagen_local(ruta_img_final)
                        st.error(f"Error de validación: {e}")
                    except Exception as e:
                        borrar_archivo_imagen_local(ruta_img_final)
                        st.error(f"Error inesperado al guardar: {e}")

            with col_del_btn:
                with st.expander("🗑️ Zona de Baja: Eliminar Producto"):
                    st.warning("⚠️ Acción irreversible. No se puede eliminar si posee ventas históricas registradas.")
                    confirmar_del = st.checkbox("Confirmo que deseo eliminar este producto", key=f"chk_del_{pid}")
                    if st.button("🗑️ Confirmar Eliminación", type="secondary", disabled=not confirmar_del, use_container_width=True, key=f"btn_del_{pid}"):
                        try:
                            models.eliminar_producto(pid)
                            borrar_archivo_imagen_local(prod_actual.get("imagen_path"))
                            st.session_state["flash_inventario"] = f"🗑️ Producto '{prod_actual['nombre']}' eliminado correctamente."
                            st.rerun()
                        except models.BusinessLogicError as e:
                            st.error(f"No se pudo eliminar: {e}")
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")

    # 4. Ajuste Rápido de Stock
    with tab_ajuste:
        st.subheader("🔄 Ajuste de Stock en Almacén")
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
                    st.markdown("#### 📦 Ajustar Cantidad en Almacén")
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
                        st.caption(f"Stock resultante: **{nuevo_stock_val:g}** unidades")

                    if st.button("Guardar Stock Actual", type="primary", key=f"aj_guardar_{ka}"):
                        try:
                            models.ajustar_stock(prod_a_ajustar["id"], nuevo_stock_val)
                            st.session_state["flash_inventario"] = f"✅ Stock de '{prod_a_ajustar['nombre']}' actualizado a {nuevo_stock_val:g} unidades."
                            st.rerun()
                        except models.BusinessLogicError as e:
                            st.error(str(e))
                        except Exception as e:
                            st.error(f"Error al actualizar stock: {e}")

            with col_ajuste_der:
                with st.container(border=True):
                    st.markdown("#### ⚙️ Umbral de Stock Mínimo")
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
                            st.session_state["flash_inventario"] = f"✅ Stock mínimo de '{prod_a_ajustar['nombre']}' actualizado a {nuevo_minimo:g}."
                            st.rerun()
                        except models.BusinessLogicError as e:
                            st.error(str(e))
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

    # 5. Monitor Exclusivo de Stock Crítico
    with tab_alertas:
        st.subheader("🚨 Artículos que Requieren Reposición Inmediata")
        bajo_stock_list = models.obtener_productos_bajo_stock()

        if not bajo_stock_list:
            st.success("🎉 ¡Excelente! No hay productos con stock igual o inferior a su mínimo.")
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
            st.dataframe(df_criticos, use_container_width=True, hide_index=True)


# ==============================================================================
# MÓDULO 4: GESTIÓN DE CATEGORÍAS
# ==============================================================================
elif modulo == "🏷️ Categorías":
    st.header("🏷️ Gestión de Categorías")
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
                c1, c2 = st.columns([3, 1])
                c1.write(f"📁 **{cat['nombre']}**")
                if c2.button("Eliminar", key=f"del_cat_{cat['id']}"):
                    models.eliminar_categoria(cat['id'])
                    st.warning(f"Categoría '{cat['nombre']}' eliminada.")
                    st.rerun()


# ==============================================================================
# MÓDULO 5: ARQUEO DE CAJA Y CIERRE DIARIO
# ==============================================================================
elif modulo == "📊 Arqueo de Caja / Control Diario":
    st.header("📊 Control Diario & Cierre de Caja")

    col_fecha, col_btn_cierre = st.columns([1, 1.5], gap="large")
    with col_fecha:
        fecha_elegida = st.date_input("Fecha de consulta:", value=date.today())

    resumen = models.obtener_arqueo_caja(fecha_elegida.strftime("%Y-%m-%d"))

    # ---> NUEVO FORMULARIO DE CAJA CHICA Y TABLA
    st.markdown("### 💵 Registro de Caja Chica (Efectivo)")
    with st.expander("➕ Registrar Ingreso Extra / Egreso Manual", expanded=False):
        with st.form("form_caja_chica"):
            col_cc1, col_cc2, col_cc3 = st.columns([1, 1, 2])
            with col_cc1:
                tipo_mov = st.selectbox("Tipo de Movimiento", ["Egreso", "Ingreso Extra"])
            with col_cc2:
                monto_mov = st.number_input("Monto ($) *", min_value=1.0, value=1000.0, step=100.0)
            with col_cc3:
                concepto_mov = st.text_input("Concepto / Motivo *", placeholder="Ej: Pago a proveedor, Compra de artículos...")
            
            btn_registrar_cc = st.form_submit_button("✅ Registrar Movimiento", type="primary")
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
                    st.success("✅ Movimiento de caja registrado con éxito.")
                    st.rerun()
                except models.BusinessLogicError as e:
                    st.error(f"Error: {e}")
                except Exception as e:
                    st.error(f"Error al registrar: {e}")
                    
    # Mostrar tabla de movimientos si hay
    if resumen.get("movimientos_caja"):
        st.markdown("#### 📝 Movimientos de Caja Chica de la Fecha")
        df_movs = pd.DataFrame(resumen["movimientos_caja"])[["fecha", "tipo", "concepto", "monto", "usuario_nombre"]]
        # Formatear la fecha
        df_movs["fecha"] = pd.to_datetime(df_movs["fecha"], utc=True).dt.tz_convert(ZONA_HORARIA).dt.strftime("%H:%M")
        df_movs["tipo"] = df_movs["tipo"].map({"egreso": "🔴 Egreso", "ingreso_extra": "🟢 Ingreso Extra"})
        df_movs["monto"] = df_movs["monto"].apply(lambda x: f"${float(x):,.2f}")
        df_movs = df_movs.rename(columns={
            "fecha": "Hora", "tipo": "Tipo", "concepto": "Concepto", 
            "monto": "Monto", "usuario_nombre": "Responsable"
        })
        st.dataframe(df_movs, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Métricas Principales (KPI Cards) - Reorganizadas para mostrar el Efectivo Esperado
    st.subheader("📊 Balance del Día")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Total Ventas", f"${resumen['total_vendido']:,.2f}")
    m2.metric("💵 Efectivo Esperado", f"${resumen['total_efectivo_esperado']:,.2f}")
    m3.metric("📈 Ganancia Estimada", f"${resumen['ganancia_estimada']:,.2f}")
    m4.metric("🧾 Tickets", resumen['total_operaciones'])

    # Desglose de Efectivo Esperado en expander
    with st.expander("🔍 Ver Desglose de Efectivo Esperado", expanded=False):
        st.write(f"**+ Ventas en Efectivo:** ${resumen.get('ventas_efectivo', 0):,.2f}")
        st.write(f"**+ Cobros de Fiado (Efectivo):** ${resumen.get('cobros_fiado_efectivo', 0):,.2f}")
        st.write(f"**+ Ingresos Extras (Manual):** ${resumen.get('ingresos_extras', 0):,.2f}")
        st.write(f"**- Egresos (Gastos / Retiros):** ${resumen.get('egresos', 0):,.2f}")
        st.markdown(f"**= EFECTIVO ESPERADO EN CAJA: ${resumen.get('total_efectivo_esperado', 0):,.2f}**")

    st.markdown("---")

    # BOTÓN DESTACADO: REALIZAR CIERRE DE CAJA DEL DÍA
    st.subheader("🔒 Cierre Oficial de Caja Diario")
    
    col_cierre_btn, _ = st.columns([1.5, 1])
    with col_cierre_btn:
        ejecutar_cierre = st.button("🔒 Realizar Cierre de Caja del Día", type="primary", use_container_width=True)

    if ejecutar_cierre:
        st.session_state["cierre_activo"] = True
        st.session_state["cierre_fecha_activa"] = fecha_elegida.strftime("%Y-%m-%d")

    # Panel de Descarga, WhatsApp y Envío de Correo si se activó el cierre
    if st.session_state.get("cierre_activo") and st.session_state.get("cierre_fecha_activa") == fecha_elegida.strftime("%Y-%m-%d"):
        with st.container(border=True):
            st.success(f"🎉 **Cierre de Caja procesado para el día {fecha_elegida.strftime('%d/%m/%Y')}**")

            nombre_neg = config_negocio.get("nombre_negocio", "Mi Comercio")
            pdf_bytes = reportes.generar_pdf_cierre_caja(
                fecha_str=fecha_elegida.strftime("%Y-%m-%d"),
                resumen=resumen,
                nombre_negocio=nombre_neg
            )

            col_acc1, col_acc2, col_acc3 = st.columns(3, gap="medium")

            with col_acc1:
                st.download_button(
                    label="⬇️ Descargar PDF del Cierre",
                    data=pdf_bytes,
                    file_name=f"Cierre_Caja_{fecha_elegida.strftime('%Y-%m-%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            with col_acc2:
                msg_wsp = reportes.armar_mensaje_whatsapp_cierre(
                    resumen=resumen,
                    fecha_str=fecha_elegida.strftime("%d/%m/%Y"),
                    nombre_negocio=nombre_neg
                )
                url_wsp = reportes.armar_url_whatsapp(None, msg_wsp)
                st.link_button("📲 Compartir Cierre por WhatsApp", url_wsp, use_container_width=True)

            with col_acc3:
                email_dest = config_negocio.get("email_destinatario", "").strip()
                if email_dest and config_negocio.get("smtp_usuario") and config_negocio.get("smtp_password"):
                    if st.button("✉️ Enviar / Reenviar por Email", use_container_width=True):
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
                    st.caption("ℹ️ Configure el correo en '⚙️ Configuración' para habilitar el envío automático.")

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
                        st.info(f"📧 Correo automático: {mensaje}")
                    else:
                        st.warning(f"⚠️ Correo automático: {mensaje}")

    st.markdown("---")

    col_desglose, col_tickets = st.columns([1, 1.5], gap="large")

    with col_desglose:
        st.subheader("💳 Ventas por Forma de Pago")
        if resumen["desglose_por_forma_pago"]:
            df_desglose = pd.DataFrame(resumen["desglose_por_forma_pago"]).rename(
                columns={
                    "forma_pago": "Forma de Pago",
                    "operaciones": "Operaciones",
                    "total": "Total ($)"
                }
            )
            st.dataframe(df_desglose, use_container_width=True, hide_index=True)
            chart = alt.Chart(df_desglose).mark_bar(color="#3b82f6", cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("Forma de Pago", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Total ($)")
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No hay ventas registradas en esta fecha.")

    with col_tickets:
        st.subheader("📜 Detalle de Ventas Registradas")
        if resumen["ventas"]:
            for v in resumen["ventas"]:
                try:
                    dt_v = pd.to_datetime(v['fecha_hora'], utc=True).tz_convert(ZONA_HORARIA)
                    hora_str = dt_v.strftime("%H:%M")
                except:
                    hora_str = v['fecha_hora']
                cli_info = f" [Cliente: {v['cliente_nombre']}]" if v.get("cliente_nombre") else ""
                with st.expander(f"Ticket #{v['id']} - {hora_str} | ${v['total_venta']:,.2f} ({v['forma_pago']}){cli_info}"):
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
                        st.dataframe(df_det, use_container_width=True, hide_index=True)
        else:
            st.info("Sin registros de tickets para la fecha seleccionada.")


# ==============================================================================
# MÓDULO 6: CONFIGURACIÓN DEL NEGOCIO
# ==============================================================================
elif modulo == "⚙️ Configuración del Negocio":
    st.header("⚙️ Configuración del Comercio")
    st.caption("Administra tus datos bancarios para cobros con QR y la configuración de notificaciones por email.")

    with st.form("form_config_negocio"):
        col_c1, col_c2 = st.columns(2, gap="large")

        with col_c1:
            st.markdown("### 🏦 Datos Bancarios y QR de Cobro")
            nombre_neg_input = st.text_input("Nombre de Fantasía del Negocio", value=config_negocio.get("nombre_negocio", "Mi Comercio"))
            titular_input = st.text_input("Titular de la Cuenta", value=config_negocio.get("titular_cuenta", ""))
            banco_input = st.text_input("Banco o Billetera Virtual (ej: Mercado Pago, Santander)", value=config_negocio.get("banco", ""))
            alias_input = st.text_input("Alias CBU/CVU", value=config_negocio.get("alias", ""))
            cbu_input = st.text_input("CBU / CVU Numérico", value=config_negocio.get("cbu", ""))

            st.markdown("#### 📷 Código QR de Cobro (Estático)")
            qr_actual_abs = obtener_ruta_imagen_absoluta(config_negocio.get("qr_imagen_path"))
            if qr_actual_abs:
                st.image(qr_actual_abs, caption="Código QR cargado actualmente", width=140)
            
            qr_subido = st.file_uploader(
                "Subir o Reemplazar Código QR (JPG / PNG)",
                type=["jpg", "jpeg", "png"],
                help="Sube una captura del código QR de tu cuenta para mostrar a los clientes en el Punto de Venta."
            )

        with col_c2:
            st.markdown("### ✉️ Configuración de Correo SMTP")
            st.caption("Para el envío automático del PDF de Cierre de Caja.")

            smtp_srv_input = st.text_input("Servidor SMTP", value=config_negocio.get("smtp_servidor", "smtp.gmail.com"))
            smtp_prt_input = st.number_input("Puerto SMTP (587 recomendado para TLS)", min_value=1, max_value=65535, value=int(config_negocio.get("smtp_puerto", 587)))
            smtp_usr_input = st.text_input("Usuario / Email Remitente", value=config_negocio.get("smtp_usuario", ""), placeholder="tu_cuenta@gmail.com")
            smtp_pwd_input = st.text_input("Contraseña de Aplicación", value=config_negocio.get("smtp_password", ""), type="password", help="En Gmail, utiliza una 'Contraseña de Aplicación' generada desde la seguridad de Google.")
            email_dest_input = st.text_input("Email Destinatario del Cierre Diario", value=config_negocio.get("email_destinatario", ""), placeholder="dueno@negocio.com")

        guardar_cfg_btn = st.form_submit_button("💾 Guardar Configuración", type="primary")

        if guardar_cfg_btn:
            ruta_qr_final = config_negocio.get("qr_imagen_path")
            if qr_subido is not None:
                ruta_qr_final = guardar_archivo_imagen(qr_subido, "qr_pago")

            nueva_config = {
                "nombre_negocio": nombre_neg_input.strip() or "Mi Comercio",
                "titular_cuenta": titular_input.strip(),
                "banco": banco_input.strip(),
                "alias": alias_input.strip(),
                "cbu": cbu_input.strip(),
                "qr_imagen_path": ruta_qr_final,
                "smtp_servidor": smtp_srv_input.strip(),
                "smtp_puerto": int(smtp_prt_input),
                "smtp_usuario": smtp_usr_input.strip(),
                "smtp_password": smtp_pwd_input.strip(),
                "email_destinatario": email_dest_input.strip(),
                "admin_password": config_negocio.get("admin_password", "admin123")
            }

            if guardar_configuracion(nueva_config):
                st.success("✅ Configuración guardada correctamente.")
                st.rerun()
            else:
                st.error("Error al persistir la configuración.")

    st.markdown("---")

    # PANEL: CAMBIAR CONTRASEÑA DE DUEÑO / ADMINISTRADOR
    st.subheader("🔑 Clave de Dueño / Administrador")
    with st.expander("Cambiar Contraseña de Dueño / Administrador", expanded=False):
        st.caption("Clave heredada de versiones anteriores. El vaciado de datos ahora se autoriza con el PIN del Dueño.")
        with st.form("form_cambiar_clave_admin"):
            col_k1, col_k2 = st.columns(2)
            with col_k1:
                clave_actual_in = st.text_input("Contraseña Actual *", type="password", placeholder="Clave actual...")
            with col_k2:
                clave_nueva_in = st.text_input("Nueva Contraseña *", type="password", placeholder="Mínimo 4 caracteres...")

            btn_guardar_clave = st.form_submit_button("💾 Actualizar Contraseña de Dueño", type="primary")
            if btn_guardar_clave:
                exito, msg = cambiar_clave_admin(clave_actual_in, clave_nueva_in)
                if exito:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

    st.markdown("---")

    # ZONA DE MANTENIMIENTO / PUESTA A CERO (solo Dueño)
    if not es_admin:
        st.error("⛔ Solo el Dueño puede acceder al mantenimiento del sistema.")
        st.stop()

    # La versión cambia tras cada intento (éxito o error) para que los widgets de confirmación
    # vuelvan a su estado inicial: el botón rojo nunca queda "armado" para un segundo borrado.
    ver_reset = st.session_state.get("reset_ver", 0)

    # Resultado del intento anterior (sobrevive al st.rerun())
    msg_reset = st.session_state.pop("reset_msg", None)
    if msg_reset:
        if msg_reset[0] == "ok":
            st.success(msg_reset[1])
        else:
            st.error(msg_reset[1])

    with st.expander("⚠️ Zona de Mantenimiento / Puesta a Cero", expanded=bool(msg_reset)):
        st.error("🚨 **ZONA DE PELIGRO - ACCIÓN IRREVERSIBLE**")
        st.markdown(
            "Pensada para limpiar los datos de prueba antes de empezar a operar. "
            "**No hay forma de deshacerla.** Se conservan siempre la configuración del comercio y los usuarios."
        )

        OPC_MOV = "Vaciar solo movimientos y pruebas"
        OPC_TOTAL = "Reinicio de fábrica total"
        opcion_reset = st.radio(
            "¿Qué querés borrar?",
            [OPC_MOV, OPC_TOTAL],
            key=f"rst_modo_{ver_reset}",
        )
        if opcion_reset == OPC_MOV:
            st.info(
                "Borra **ventas, detalle de ventas, movimientos de cuenta corriente** (y caja/arqueos si existen) "
                "y deja en **$0** el saldo de todos los clientes. "
                "**Conserva** productos, categorías y clientes."
            )
        else:
            st.warning(
                "Borra **todo**: ventas, movimientos, **productos, categorías, clientes** y fotos de productos. "
                "**Conserva** únicamente la configuración del comercio y los usuarios."
            )

        rst_confirma = st.checkbox("Entiendo que esta acción es irreversible", key=f"rst_chk_{ver_reset}")
        rst_palabra = st.text_input(
            "Para habilitar el botón, escribí la palabra BORRAR (en mayúsculas):",
            placeholder="BORRAR",
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
            and rst_palabra.strip() == "BORRAR"
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
                "💣 BORRAR DATOS AHORA",
                type="primary",
                disabled=not rst_habilitado,
                use_container_width=True,
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
                    f"{resultado.get('detalle_ventas', 0)} renglones de venta",
                    f"{resultado.get('movimientos_cuenta', 0)} movimientos de cuenta corriente",
                ]
                if modo_reset == models.RESET_MOVIMIENTOS:
                    partes.append(f"saldo de {resultado.get('saldos_reseteados', 0)} cliente(s) puesto en $0")
                else:
                    partes += [
                        f"{resultado.get('productos', 0)} productos",
                        f"{resultado.get('categorias', 0)} categorías",
                        f"{resultado.get('clientes', 0)} clientes",
                        f"{resultado.get('fotos_eliminadas', 0)} fotos",
                    ]

                # Vaciar carrito y estado del POS (pueden apuntar a productos/clientes ya borrados)
                st.session_state.carrito = []
                st.session_state["_pos_reset_cant"] = True
                st.session_state["reset_msg"] = (
                    "ok",
                    "🎉 **Puesta a cero completada con éxito.** Se eliminó: " + ", ".join(partes) + ".",
                )
            except models.BusinessLogicError as e:
                st.session_state["reset_msg"] = ("error", f"❌ No se borró nada: {e}")
            except Exception as e:
                st.session_state["reset_msg"] = (
                    "error",
                    f"❌ Error al restablecer la base de datos. No se modificó ningún dato. Detalle: {e}",
                )
            st.session_state["reset_ver"] = ver_reset + 1
            st.rerun()






