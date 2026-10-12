import streamlit as st
import functools

def clears_cache(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        res = func(*args, **kwargs)
        st.cache_data.clear()
        return res
    return wrapper

import os
import pandas as pd
from database import get_connection

# ID de comercio por defecto para el primer cliente
COMERCIO_ID_DEFAULT = 1


class BusinessLogicError(Exception):
    """Error de regla de negocio (dato inválido, límite de crédito, etc.). Mensaje apto para mostrar al usuario."""


class InsufficientStockError(BusinessLogicError):
    """No hay stock suficiente para completar la operación."""

# ==========================================
# 1. GESTIÓN DE PRODUCTOS Y CATEGORÍAS
# ==========================================

@st.cache_data(ttl=120)
def get_categorias(comercio_id=COMERCIO_ID_DEFAULT):
    """Devuelve la lista de categorías del comercio."""
    supabase = get_connection()
    res = supabase.table("categorias").select("*").eq("comercio_id", comercio_id).order("nombre").execute()
    return res.data or []

@clears_cache
def add_categoria(nombre, comercio_id=COMERCIO_ID_DEFAULT):
    """Agrega una nueva categoría (alias interno)."""
    return crear_categoria(nombre, comercio_id)

@clears_cache
def crear_categoria(nombre, comercio_id=COMERCIO_ID_DEFAULT):
    """Crea una categoría verificando nombre no vacío ni duplicado."""
    nombre_limpio = (nombre or "").strip()
    if not nombre_limpio:
        raise BusinessLogicError("El nombre de la categoría es obligatorio.")
    supabase = get_connection()
    dup = supabase.table("categorias").select("id").eq("comercio_id", comercio_id).ilike("nombre", nombre_limpio).execute()
    if dup.data:
        raise BusinessLogicError(f"Ya existe una categoría llamada '{nombre_limpio}'.")
    res = supabase.table("categorias").insert({"nombre": nombre_limpio, "comercio_id": comercio_id}).execute()
    if not res.data:
        raise Exception("Error al crear la categoría en Supabase.")
    return res.data[0]["id"]

@clears_cache
def actualizar_categoria(categoria_id, nuevo_nombre, comercio_id=COMERCIO_ID_DEFAULT):
    """Actualiza el nombre de una categoría verificando que no esté duplicado."""
    nombre_limpio = (nuevo_nombre or "").strip()
    if not nombre_limpio:
        raise BusinessLogicError("El nombre de la categoría es obligatorio.")
    supabase = get_connection()
    dup = supabase.table("categorias").select("id").eq("comercio_id", comercio_id).ilike("nombre", nombre_limpio).execute()
    for fila in (dup.data or []):
        if fila["id"] != categoria_id:
            raise BusinessLogicError(f"Ya existe otra categoría llamada '{nombre_limpio}'.")
    res = supabase.table("categorias").update({"nombre": nombre_limpio}).eq("id", categoria_id).eq("comercio_id", comercio_id).execute()
    if not res.data:
        raise BusinessLogicError("No se encontró la categoría o no pudo ser actualizada.")
    return True

@clears_cache
def eliminar_categoria(categoria_id, comercio_id=COMERCIO_ID_DEFAULT):
    """Elimina una categoría si no tiene productos asociados."""
    supabase = get_connection()
    prods_count = supabase.table("productos").select("id", count="exact").eq("categoria_id", categoria_id).execute()
    if prods_count.count and prods_count.count > 0:
        raise BusinessLogicError(f"No se puede eliminar la categoría porque tiene {prods_count.count} producto(s) asignado(s).")
    res = supabase.table("categorias").delete().eq("id", categoria_id).eq("comercio_id", comercio_id).execute()
    if not res.data:
        raise BusinessLogicError("No se encontró la categoría o no pudo ser eliminada.")
    return True

def _formatear_producto(p):
    """
    Normaliza una fila de `productos` (con el JOIN a categorias) al formato que consume la app.

    La foto vive en la columna `imagen_url` de Supabase. Puede ser una URL http(s) o una ruta
    relativa local (ej: static/uploads/x.jpg). Se expone además como `imagen_path`, que es el
    nombre que usa app.py.
    """
    cat = p.get("categorias")
    if isinstance(cat, list):
        cat = cat[0] if cat else None
    cat_nombre = cat["nombre"] if cat else "Sin categoría"
    imagen = p.get("imagen_url") or ""
    return {
        "id": p["id"],
        "codigo": p["codigo"],
        "nombre": p["nombre"],
        "categoria_id": p.get("categoria_id"),
        "categoria": cat_nombre,
        "categoria_nombre": cat_nombre,
        "precio_costo": float(p.get("precio_costo") or 0.0),
        "margen_ganancia": float(p.get("margen_ganancia") or 0.0),
        "precio_venta": float(p.get("precio_venta") or 0.0),
        "usa_precio_manual": bool(p.get("usa_precio_manual")),
        "stock_actual": float(p.get("stock_actual") or 0.0),
        "stock_minimo": float(p.get("stock_minimo") or 0.0),
        "imagen_url": imagen,
        "imagen_path": imagen or None,
        "puntos_canje": int(p.get("puntos_canje") or 0),
    }

@st.cache_data(ttl=120)
def get_productos(comercio_id=COMERCIO_ID_DEFAULT):
    """Devuelve todos los productos con su categoría asociada como DataFrame."""
    supabase = get_connection()
    # Hacemos el JOIN con categorías directamente desde Supabase
    res = supabase.table("productos").select("*, categorias(nombre)").eq("comercio_id", comercio_id).order("nombre").execute()
    
    if not res.data:
        return pd.DataFrame()
    
    return pd.DataFrame([_formatear_producto(p) for p in res.data])

@st.cache_data(ttl=120)
def obtener_producto_por_codigo(codigo, comercio_id=COMERCIO_ID_DEFAULT):
    """Busca un producto por código de barras / SKU exacto. Devuelve un dict o None si no existe."""
    codigo = (codigo or "").strip()
    if not codigo:
        return None

    supabase = get_connection()
    res = (
        supabase.table("productos")
        .select("*, categorias(nombre)")
        .eq("comercio_id", comercio_id)
        .eq("codigo", codigo)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    return _formatear_producto(res.data[0])

@st.cache_data(ttl=120)
def get_producto_por_id(producto_id, comercio_id=COMERCIO_ID_DEFAULT):
    """Devuelve un producto individual por ID incluyendo categorias y puntos_canje."""
    supabase = get_connection()
    res = (
        supabase.table("productos")
        .select("*, categorias(nombre)")
        .eq("comercio_id", comercio_id)
        .eq("id", producto_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    return _formatear_producto(res.data[0])

@st.cache_data(ttl=120)
def obtener_producto_por_id(producto_id, comercio_id=COMERCIO_ID_DEFAULT):
    """Alias para get_producto_por_id."""
    return get_producto_por_id(producto_id, comercio_id=comercio_id)

@clears_cache
def save_producto(datos, comercio_id=COMERCIO_ID_DEFAULT):
    """Guarda o actualiza un producto en Supabase."""
    supabase = get_connection()
    payload = {
        "comercio_id": comercio_id,
        "codigo": datos["codigo"],
        "nombre": datos["nombre"],
        "categoria_id": datos["categoria_id"],
        "precio_costo": datos["precio_costo"],
        "margen_ganancia": datos["margen_ganancia"],
        "precio_venta": datos["precio_venta"],
        "usa_precio_manual": datos.get("usa_precio_manual", False),
        "stock_actual": datos["stock_actual"],
        "stock_minimo": datos["stock_minimo"],
        "imagen_url": datos.get("imagen_url", ""),
        "puntos_canje": int(datos.get("puntos_canje") or 0),
    }

    try:
        if datos.get("id"):
            res = supabase.table("productos").update(payload).eq("id", datos["id"]).execute()
        else:
            res = supabase.table("productos").insert(payload).execute()
    except Exception as e:
        if "puntos_canje" in str(e).lower() or "PGRST204" in str(e):
            raise BusinessLogicError(
                "La base de datos en Supabase no tiene la columna 'puntos_canje' en la tabla 'productos'. "
                "Por favor ejecutá el script 'sql/canje_premios.sql' en el SQL Editor de Supabase."
            )
        raise e
    st.cache_data.clear()
    return res.data

@clears_cache
def delete_producto(producto_id):
    """Elimina un producto por su ID."""
    supabase = get_connection()
    res = supabase.table("productos").delete().eq("id", producto_id).execute()
    return res.data


# --- API de productos usada por app.py (Productos e Inventario) ---

def calcular_precio_venta(precio_costo, margen_ganancia):
    """Precio de venta = costo + margen porcentual, redondeado a 2 decimales."""
    return round(float(precio_costo or 0.0) * (1 + float(margen_ganancia or 0.0) / 100.0), 2)


@st.cache_data(ttl=120)
def obtener_productos(busqueda=None, categoria_id=None, comercio_id=COMERCIO_ID_DEFAULT, **kwargs):
    """
    Lista de productos (dicts), ordenada por nombre. Filtros opcionales:
    `busqueda` (texto en nombre o código, sin distinguir mayúsculas) y `categoria_id`.
    """
    df = get_productos(comercio_id)
    if df.empty:
        return []
    productos = df.to_dict("records")

    if categoria_id is not None:
        productos = [p for p in productos if p["categoria_id"] == categoria_id]
    if busqueda and busqueda.strip():
        q = busqueda.strip().lower()
        productos = [p for p in productos if q in p["nombre"].lower() or q in str(p["codigo"]).lower()]
    return productos


def _validar_datos_producto(codigo, nombre, precio_costo, margen_ganancia, usa_precio_manual,
                            precio_venta_manual, stock_actual, stock_minimo):
    """Valida y normaliza los datos de un producto. Devuelve (codigo, nombre, precio_venta)."""
    codigo = (codigo or "").strip()
    nombre = (nombre or "").strip()
    if not codigo:
        raise BusinessLogicError("El código de barras / SKU es obligatorio.")
    if not nombre:
        raise BusinessLogicError("El nombre del producto es obligatorio.")
    if float(precio_costo) < 0:
        raise BusinessLogicError("El precio de costo no puede ser negativo.")
    if float(margen_ganancia) < 0:
        raise BusinessLogicError("El margen de ganancia no puede ser negativo.")
    if float(stock_actual) < 0 or float(stock_minimo) < 0:
        raise BusinessLogicError("El stock no puede ser negativo.")

    if usa_precio_manual:
        if precio_venta_manual is None or float(precio_venta_manual) <= 0:
            raise BusinessLogicError("Si sobreescribís el precio, el precio de venta manual debe ser mayor a 0.")
        precio_venta = round(float(precio_venta_manual), 2)
    else:
        precio_venta = calcular_precio_venta(precio_costo, margen_ganancia)
        if precio_venta <= 0:
            raise BusinessLogicError("El precio de venta calculado es 0. Cargá un costo mayor a 0 o un precio manual.")
    return codigo, nombre, precio_venta


def _verificar_codigo_libre(supabase, codigo, comercio_id, excluir_id=None):
    """Levanta BusinessLogicError si ya existe otro producto con ese código en el comercio."""
    res = supabase.table("productos").select("id, nombre").eq("comercio_id", comercio_id).eq("codigo", codigo).execute()
    for fila in (res.data or []):
        if excluir_id is None or fila["id"] != excluir_id:
            raise BusinessLogicError(f"Ya existe un producto con el código '{codigo}' ({fila['nombre']}).")


@clears_cache
def crear_producto(codigo, nombre, categoria_id, precio_costo, margen_ganancia, usa_precio_manual,
                   precio_venta_manual, stock_actual, stock_minimo, imagen_path=None,
                   puntos_canje=0, comercio_id=COMERCIO_ID_DEFAULT):
    """Crea un producto en Supabase y devuelve su ID. `imagen_path` se guarda en la columna imagen_url."""
    codigo, nombre, precio_venta = _validar_datos_producto(
        codigo, nombre, precio_costo, margen_ganancia, usa_precio_manual,
        precio_venta_manual, stock_actual, stock_minimo,
    )
    supabase = get_connection()
    _verificar_codigo_libre(supabase, codigo, comercio_id)

    payload = {
        "comercio_id": comercio_id,
        "codigo": codigo,
        "nombre": nombre,
        "categoria_id": categoria_id,
        "precio_costo": float(precio_costo),
        "margen_ganancia": float(margen_ganancia),
        "precio_venta": precio_venta,
        "usa_precio_manual": bool(usa_precio_manual),
        "stock_actual": float(stock_actual),
        "stock_minimo": float(stock_minimo),
        "imagen_url": imagen_path or "",
        "puntos_canje": int(puntos_canje or 0),
    }
    try:
        res = supabase.table("productos").insert(payload).execute()
    except Exception as e:
        if "puntos_canje" in str(e).lower() or "PGRST204" in str(e):
            raise BusinessLogicError(
                "La base de datos en Supabase no tiene la columna 'puntos_canje' en la tabla 'productos'. "
                "Por favor ejecutá el script 'sql/canje_premios.sql' en el SQL Editor de Supabase."
            )
        raise e

    if not res.data:
        raise Exception("Supabase no confirmó la creación del producto (revisá los permisos / RLS de la tabla productos).")
    st.cache_data.clear()
    return res.data[0]["id"]


@clears_cache
def actualizar_producto(producto_id, codigo, nombre, categoria_id, precio_costo, margen_ganancia,
                        usa_precio_manual, precio_venta_manual, stock_actual, stock_minimo,
                        imagen_path=None, eliminar_imagen=False, puntos_canje=0, comercio_id=COMERCIO_ID_DEFAULT):
    """
    Actualiza un producto. Foto: si viene `imagen_path` se reemplaza; si `eliminar_imagen` es True
    se borra la referencia; si no, se conserva la actual.
    """
    codigo, nombre, precio_venta = _validar_datos_producto(
        codigo, nombre, precio_costo, margen_ganancia, usa_precio_manual,
        precio_venta_manual, stock_actual, stock_minimo,
    )
    supabase = get_connection()
    _verificar_codigo_libre(supabase, codigo, comercio_id, excluir_id=producto_id)

    payload = {
        "codigo": codigo,
        "nombre": nombre,
        "categoria_id": categoria_id,
        "precio_costo": float(precio_costo),
        "margen_ganancia": float(margen_ganancia),
        "precio_venta": precio_venta,
        "usa_precio_manual": bool(usa_precio_manual),
        "stock_actual": float(stock_actual),
        "stock_minimo": float(stock_minimo),
        "puntos_canje": int(puntos_canje or 0),
    }
    if imagen_path:
        payload["imagen_url"] = imagen_path
    elif eliminar_imagen:
        payload["imagen_url"] = ""

    try:
        res = supabase.table("productos").update(payload).eq("id", producto_id).eq("comercio_id", comercio_id).execute()
    except Exception as e:
        if "puntos_canje" in str(e).lower() or "PGRST204" in str(e):
            raise BusinessLogicError(
                "La base de datos en Supabase no tiene la columna 'puntos_canje' en la tabla 'productos'. "
                "Por favor ejecutá el script 'sql/canje_premios.sql' en el SQL Editor de Supabase."
            )
        raise e

    if not res.data:
        raise BusinessLogicError("No se pudo actualizar: el producto no existe o no hay permiso de escritura (RLS).")
    st.cache_data.clear()
    return True


@clears_cache
def eliminar_producto(producto_id, comercio_id=COMERCIO_ID_DEFAULT):
    """Elimina un producto. Se bloquea si tiene ventas históricas, para no romper tickets viejos."""
    supabase = get_connection()
    ventas = supabase.table("detalle_ventas").select("id").eq("producto_id", producto_id).limit(1).execute()
    if ventas.data:
        raise BusinessLogicError("El producto tiene ventas históricas registradas y no se puede eliminar.")

    try:
        res = supabase.table("productos").delete().eq("id", producto_id).eq("comercio_id", comercio_id).execute()
    except Exception as e:
        if "23503" in str(e):  # foreign_key_violation
            raise BusinessLogicError("El producto está referenciado por otros registros y no se puede eliminar.")
        raise
    if not res.data:
        raise BusinessLogicError("No se pudo eliminar: el producto no existe o no hay permiso de escritura (RLS).")
    return True


@clears_cache
def ajustar_stock(producto_id, nuevo_stock, comercio_id=COMERCIO_ID_DEFAULT):
    """Fija el stock actual de un producto (conteo físico o ingreso de mercadería ya sumado)."""
    if float(nuevo_stock) < 0:
        raise BusinessLogicError("El stock no puede ser negativo.")
    supabase = get_connection()
    res = (supabase.table("productos").update({"stock_actual": float(nuevo_stock)})
           .eq("id", producto_id).eq("comercio_id", comercio_id).execute())
    if not res.data:
        raise BusinessLogicError("No se pudo ajustar el stock: el producto no existe o no hay permiso de escritura (RLS).")
    return True


@clears_cache
def actualizar_stock_minimo(producto_id, nuevo_minimo, comercio_id=COMERCIO_ID_DEFAULT):
    """Actualiza el umbral de stock mínimo (alerta de reposición) de un producto."""
    if float(nuevo_minimo) < 0:
        raise BusinessLogicError("El stock mínimo no puede ser negativo.")
    supabase = get_connection()
    res = (supabase.table("productos").update({"stock_minimo": float(nuevo_minimo)})
           .eq("id", producto_id).eq("comercio_id", comercio_id).execute())
    if not res.data:
        raise BusinessLogicError("No se pudo actualizar el mínimo: el producto no existe o no hay permiso de escritura (RLS).")
    return True

# ==========================================
# 2. GESTIÓN DE CLIENTES ("LA LIBRETA")
# ==========================================

def _formatear_cliente(c):
    """Normaliza los tipos de datos de un cliente."""
    return {
        "id": c["id"],
        "nombre": c.get("nombre") or "",
        "telefono": c.get("telefono") or "",
        "email": c.get("email") or "",
        "limite_credito": float(c.get("limite_credito") or 0.0),
        "saldo_deudor": float(c.get("saldo_deudor") or 0.0),
        "puntos": int(round(float(c.get("puntos") or 0.0))),
        "created_at": c.get("created_at") or ""
    }

@st.cache_data(ttl=120)
def get_clientes(comercio_id=COMERCIO_ID_DEFAULT):
    """Obtiene la lista de clientes."""
    return obtener_clientes(comercio_id=comercio_id)

@st.cache_data(ttl=120)
def obtener_clientes(busqueda=None, comercio_id=COMERCIO_ID_DEFAULT):
    """Obtiene clientes ordenados por nombre con filtro opcional de búsqueda."""
    supabase = get_connection()
    res = supabase.table("clientes").select("*").eq("comercio_id", comercio_id).order("nombre").execute()
    clientes = [_formatear_cliente(c) for c in (res.data or [])]
    if busqueda and busqueda.strip():
        q = busqueda.strip().lower()
        clientes = [
            c for c in clientes 
            if q in c["nombre"].lower() or q in c["telefono"].lower() or q in c["email"].lower()
        ]
    return clientes

@clears_cache
def crear_cliente(nombre, telefono="", email="", limite_credito=0.0, comercio_id=COMERCIO_ID_DEFAULT):
    """Registra un nuevo cliente validando datos."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise BusinessLogicError("El nombre del cliente es obligatorio.")
    limite = float(limite_credito or 0.0)
    if limite < 0:
        raise BusinessLogicError("El límite de crédito no puede ser negativo.")
    
    supabase = get_connection()
    payload = {
        "comercio_id": comercio_id,
        "nombre": nombre,
        "telefono": (telefono or "").strip(),
        "email": (email or "").strip(),
        "limite_credito": limite,
        "saldo_deudor": 0.0
    }
    res = supabase.table("clientes").insert(payload).execute()
    if not res.data:
        raise Exception("Error al registrar el cliente en Supabase.")
    return res.data[0]["id"]

@clears_cache
def add_cliente(nombre, telefono="", email="", limite_credito=0.0, comercio_id=COMERCIO_ID_DEFAULT):
    """Alias para crear_cliente."""
    return crear_cliente(nombre, telefono, email, limite_credito, comercio_id)

@clears_cache
def actualizar_cliente(cliente_id, nombre, telefono="", email="", limite_credito=0.0, comercio_id=COMERCIO_ID_DEFAULT):
    """Actualiza la información de contacto y límite de crédito de un cliente."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise BusinessLogicError("El nombre del cliente es obligatorio.")
    limite = float(limite_credito or 0.0)
    if limite < 0:
        raise BusinessLogicError("El límite de crédito no puede ser negativo.")
    
    supabase = get_connection()
    payload = {
        "nombre": nombre,
        "telefono": (telefono or "").strip(),
        "email": (email or "").strip(),
        "limite_credito": limite
    }
    res = supabase.table("clientes").update(payload).eq("id", cliente_id).eq("comercio_id", comercio_id).execute()
    if not res.data:
        raise BusinessLogicError("No se pudo actualizar: el cliente no existe o hubo un fallo de escritura.")
    return True

@clears_cache
def eliminar_cliente(cliente_id, comercio_id=COMERCIO_ID_DEFAULT):
    """Elimina un cliente verificando que no posea deuda pendiente."""
    supabase = get_connection()
    cli = supabase.table("clientes").select("id, nombre, saldo_deudor").eq("id", cliente_id).eq("comercio_id", comercio_id).execute()
    if not cli.data:
        raise BusinessLogicError("El cliente especificado no existe.")
    
    saldo = float(cli.data[0].get("saldo_deudor") or 0.0)
    if saldo > 0:
        raise BusinessLogicError(f"No se puede eliminar a '{cli.data[0]['nombre']}' porque registra una deuda activa de ${saldo:,.2f}.")
    
    try:
        supabase.table("movimientos_cuenta").delete().eq("cliente_id", cliente_id).execute()
        res = supabase.table("clientes").delete().eq("id", cliente_id).eq("comercio_id", comercio_id).execute()
        if not res.data:
            raise BusinessLogicError("No se pudo eliminar el cliente.")
    except Exception as e:
        if "23503" in str(e):
            raise BusinessLogicError("El cliente está vinculado a tickets de venta y no puede ser eliminado.")
        raise
    return True

@clears_cache
def registrar_abono_cliente(cliente_id, monto, metodo_pago="Efectivo", descripcion=None, comercio_id=COMERCIO_ID_DEFAULT):
    """Registra una entrega de dinero / abono de un cliente para amortizar su saldo deudor."""
    monto_val = float(monto or 0.0)
    if monto_val <= 0:
        raise BusinessLogicError("El monto del abono debe ser mayor a $0.00.")
    
    supabase = get_connection()
    cli = supabase.table("clientes").select("id, nombre, saldo_deudor").eq("id", cliente_id).eq("comercio_id", comercio_id).execute()
    if not cli.data:
        raise BusinessLogicError("Cliente no encontrado.")
    
    saldo_actual = float(cli.data[0].get("saldo_deudor") or 0.0)
    nuevo_saldo = max(0.0, round(saldo_actual - monto_val, 2))
    
    supabase.table("clientes").update({"saldo_deudor": nuevo_saldo}).eq("id", cliente_id).execute()
    
    detalle_desc = f"Abono ({metodo_pago})"
    if descripcion and descripcion.strip():
        detalle_desc += f": {descripcion.strip()}"
        
    mov_payload = {
        "comercio_id": comercio_id,
        "cliente_id": cliente_id,
        "tipo": "PAGO",
        "monto": monto_val,
        "descripcion": detalle_desc
    }
    mov_res = supabase.table("movimientos_cuenta").insert(mov_payload).execute()
    if not mov_res.data:
        raise Exception("Error al asentar el movimiento en la cuenta corriente.")
    return mov_res.data[0]["id"]

@clears_cache
def registrar_pago_cliente(cliente_id, monto, descripcion="Pago a cuenta", comercio_id=COMERCIO_ID_DEFAULT):
    """Alias compatible con versiones previas."""
    return registrar_abono_cliente(cliente_id, monto, metodo_pago="Efectivo", descripcion=descripcion, comercio_id=comercio_id)

@clears_cache
def sumar_puntos_cliente(cliente_id, puntos_a_sumar, comercio_id=COMERCIO_ID_DEFAULT):
    """
    Suma puntos al cliente en el programa de fidelidad.
    Devuelve el nuevo balance de puntos (entero).
    """
    puntos_val = int(puntos_a_sumar or 0)
    if puntos_val <= 0:
        return 0
    supabase = get_connection()
    cli = supabase.table("clientes").select("id, puntos").eq("id", cliente_id).eq("comercio_id", comercio_id).execute()
    if not cli.data:
        raise BusinessLogicError("Cliente no encontrado.")
    actual = int(round(float(cli.data[0].get("puntos") or 0.0)))
    nuevo = actual + puntos_val
    supabase.table("clientes").update({"puntos": nuevo}).eq("id", cliente_id).execute()
    return nuevo

@clears_cache
def restar_puntos_cliente(cliente_id, puntos_a_restar, comercio_id=COMERCIO_ID_DEFAULT):
    """
    Resta puntos al cliente cuando se realiza un canje de premios.
    Valida que el cliente posea puntos suficientes; si no alcanza, lanza BusinessLogicError.
    Devuelve el nuevo balance de puntos (entero).
    """
    puntos_val = int(puntos_a_restar or 0)
    if puntos_val <= 0:
        return 0
    supabase = get_connection()
    cli = supabase.table("clientes").select("id, nombre, puntos").eq("id", cliente_id).eq("comercio_id", comercio_id).execute()
    if not cli.data:
        raise BusinessLogicError("Cliente no encontrado.")
    actual = int(round(float(cli.data[0].get("puntos") or 0.0)))
    if actual < puntos_val:
        nombre = cli.data[0].get("nombre") or "El cliente"
        raise BusinessLogicError(f"Puntos insuficientes: {nombre} tiene {actual} puntos y el canje requiere {puntos_val} puntos.")
    nuevo = actual - puntos_val
    supabase.table("clientes").update({"puntos": nuevo}).eq("id", cliente_id).execute()
    return nuevo

@st.cache_data(ttl=120)
def obtener_movimientos_cliente(cliente_id, comercio_id=COMERCIO_ID_DEFAULT):
    """Obtiene el historial cronológico de movimientos (cargos y pagos) de un cliente."""
    supabase = get_connection()
    res = (
        supabase.table("movimientos_cuenta")
        .select("*")
        .eq("cliente_id", cliente_id)
        .eq("comercio_id", comercio_id)
        .order("id", desc=True)
        .execute()
    )
    movs = []
    for m in (res.data or []):
        movs.append({
            "id": m["id"],
            "fecha_hora": m.get("fecha_hora") or "",
            "tipo": m.get("tipo") or "CARGO",
            "monto": float(m.get("monto") or 0.0),
            "descripcion": m.get("descripcion") or "",
            "ticket_id": m.get("ticket_id")
        })
    return movs

# ==========================================
# 3. REGISTRO DE VENTAS Y CUENTA CORRIENTE
# ==========================================

def _error_rpc(e):
    """Extrae (codigo, mensaje) de un error de PostgREST/Supabase (APIError)."""
    codigo = getattr(e, "code", None)
    mensaje = getattr(e, "message", None)
    if (codigo is None or mensaje is None) and e.args and isinstance(e.args[0], dict):
        codigo = codigo or e.args[0].get("code")
        mensaje = mensaje or e.args[0].get("message")
    return codigo, (mensaje or str(e))


@clears_cache
def registrar_venta(items, forma_pago, cliente_id=None, comercio_id=COMERCIO_ID_DEFAULT):
    """
    Registra la venta, descuenta stock y, si es fiado, carga la deuda al cliente.

    `items`: lista de dicts con `producto_id` (o `id`), `cantidad`, y opcionalmente `es_canje`.
    Para ítems normales el precio se toma de la base. Para ítems en canje (`es_canje=True`),
    el precio de venta pasa a $0.00, el stock se descuenta de forma habitual y se descuentan
    los puntos correspondientes de la cuenta del cliente en Supabase.
    Devuelve el ID de la venta (ticket) y los puntos ganados o netos.

    Toda la escritura (stock, cabecera, detalle, cuenta corriente y fidelidad) ocurre en UNA
    sola transacción dentro de la función RPC `registrar_venta_atomica`.
    """
    if not items:
        raise BusinessLogicError("El carrito está vacío.")

    es_fiado = str(forma_pago).startswith("Cuenta Corriente")
    if es_fiado and not cliente_id:
        raise BusinessLogicError("Para vender a Cuenta Corriente tenés que elegir un cliente.")

    supabase = get_connection()

    # 1. Consolidar cantidades por (producto_id, es_canje)
    grupos = {}  # (pid, es_canje): cantidad
    for it in items:
        pid = it.get("producto_id", it.get("id"))
        cantidad = float(it.get("cantidad", 0))
        es_canje = bool(it.get("es_canje", False))
        if pid is None or cantidad <= 0:
            raise BusinessLogicError("Hay un ítem inválido en el carrito (producto o cantidad incorrectos).")
        key = (pid, es_canje)
        grupos[key] = grupos.get(key, 0.0) + cantidad

    todos_pids = list({pid for pid, _ in grupos.keys()})

    # 2. Leer datos vigentes de los productos desde la base de datos
    try:
        prods_res = (
            supabase.table("productos")
            .select("id, nombre, precio_costo, precio_venta, puntos_canje")
            .eq("comercio_id", comercio_id)
            .in_("id", todos_pids)
            .execute()
        )
    except Exception:
        # Fallback si la columna puntos_canje aún no estuviese en la base
        prods_res = (
            supabase.table("productos")
            .select("id, nombre, precio_costo, precio_venta")
            .eq("comercio_id", comercio_id)
            .in_("id", todos_pids)
            .execute()
        )
    productos = {p["id"]: p for p in (prods_res.data or [])}

    detalles = []
    total_venta = 0.0
    total_puntos_canje = 0

    for (pid, es_canje), cantidad in grupos.items():
        prod = productos.get(pid)
        if prod is None:
            raise BusinessLogicError(f"El producto #{pid} ya no existe en el catálogo.")

        costo = float(prod.get("precio_costo") or 0.0)

        if es_canje:
            puntos_unidad = int(prod.get("puntos_canje") or 0)
            if puntos_unidad <= 0:
                raise BusinessLogicError(f"El producto '{prod['nombre']}' no participa del programa de canje por premios.")
            total_puntos_canje += int(round(puntos_unidad * cantidad))
            precio = 0.0
        else:
            precio = float(prod.get("precio_venta") or 0.0)
            total_venta += round(cantidad * precio, 2)

        detalles.append({
            "producto_id": pid,
            "cantidad": cantidad,
            "precio_unitario": precio,
            "costo_unitario": costo,
        })

    total_venta = round(total_venta, 2)

    # Validar cliente y puntos acumulados para canje
    if total_puntos_canje > 0:
        if not cliente_id:
            raise BusinessLogicError("Para canjear productos por puntos tenés que seleccionar un cliente registrado.")
        cli_res = supabase.table("clientes").select("id, nombre, puntos").eq("id", cliente_id).eq("comercio_id", comercio_id).execute()
        if not cli_res.data:
            raise BusinessLogicError("El cliente seleccionado no existe.")
        puntos_actuales = int(round(float(cli_res.data[0].get("puntos") or 0.0)))
        if puntos_actuales < total_puntos_canje:
            nombre_cli = cli_res.data[0].get("nombre") or "El cliente"
            raise BusinessLogicError(
                f"Puntos insuficientes: {nombre_cli} tiene {puntos_actuales} puntos y el canje requiere {total_puntos_canje} puntos."
            )

    # 3. Cálculo de puntos ganados y puntos netos
    puntos_ganados_compra = 0.0
    if cliente_id is not None:
        puntos_ganados_compra = round(total_venta * 0.01, 2)

    puntos_netos = round(puntos_ganados_compra - total_puntos_canje, 2)

    payload = {
        "p_comercio_id": comercio_id,
        "p_cliente_id": cliente_id,
        "p_metodo_pago": forma_pago,
        "p_total": total_venta,
        "p_items": detalles,
        "p_puntos_ganados": puntos_netos
    }
    try:
        res = supabase.rpc("registrar_venta_atomica", payload).execute()
    except Exception as e:
        codigo, mensaje = _error_rpc(e)
        if codigo == "SV001":
            raise InsufficientStockError(mensaje)
        if codigo == "SV002":
            raise BusinessLogicError(mensaje)
        if codigo == "PGRST202":
            raise Exception(
                "Falta la función 'registrar_venta_atomica' en Supabase. "
                "Ejecutá sql/registrar_venta_atomica.sql en el editor SQL."
            )
        raise Exception(f"Error al registrar la venta en la base de datos: {mensaje}")

    venta_id = res.data
    if isinstance(venta_id, list):
        venta_id = venta_id[0] if venta_id else None
    if venta_id is None:
        raise Exception("Error al registrar la venta en la base de datos.")
    return venta_id, puntos_netos

@st.cache_data(ttl=120)
def obtener_productos_bajo_stock(comercio_id=COMERCIO_ID_DEFAULT):
    """
    Productos en o por debajo de su stock mínimo, como lista de dicts ordenada por faltante
    (mayor déficit primero). Incluye `categoria_nombre` y `deficit` (mínimo - actual).
    """
    bajo_stock = []
    for p in obtener_productos(comercio_id=comercio_id):
        if p["stock_actual"] <= p["stock_minimo"]:
            bajo_stock.append({**p, "deficit": round(p["stock_minimo"] - p["stock_actual"], 3)})
    bajo_stock.sort(key=lambda x: x["deficit"], reverse=True)
    return bajo_stock


@st.cache_data(ttl=120)
def obtener_resumen_deuda_total(comercio_id=COMERCIO_ID_DEFAULT):
    """Suma el saldo deudor de todos los clientes para mostrar en el panel."""
    supabase = get_connection()
    res = supabase.table("clientes").select("saldo_deudor").eq("comercio_id", comercio_id).execute()
    
    if not res.data:
        return {"total_deuda": 0.0, "clientes_con_deuda": 0, "total_clientes": 0}
        
    clientes = res.data
    total_deuda = sum(float(c["saldo_deudor"] or 0.0) for c in clientes)
    con_deuda = sum(1 for c in clientes if float(c["saldo_deudor"] or 0.0) > 0)
    return {
        "total_deuda": round(total_deuda, 2),
        "clientes_con_deuda": con_deuda,
        "total_clientes": len(clientes)
    }


# ==========================================
# 4. ARQUEO DE CAJA Y CONTROL DIARIO
# ==========================================

@st.cache_data(ttl=120)
def obtener_detalle_de_venta(venta_id):
    """Devuelve los ítems individuales de un ticket de venta con datos del producto."""
    supabase = get_connection()
    res = (
        supabase.table("detalle_ventas")
        .select("*, productos(codigo, nombre)")
        .eq("venta_id", venta_id)
        .execute()
    )
    detalles = []
    for d in (res.data or []):
        prod = d.get("productos")
        if isinstance(prod, list):
            prod = prod[0] if prod else None
        codigo = prod.get("codigo") if prod else "-"
        nombre = prod.get("nombre") if prod else "Producto eliminado"
        cant = float(d.get("cantidad") or 0.0)
        p_unit = float(d.get("precio_unitario") or 0.0)
        detalles.append({
            "codigo": codigo,
            "nombre": nombre,
            "cantidad": cant,
            "precio_unitario": p_unit,
            "subtotal": round(cant * p_unit, 2)
        })
    return detalles


@clears_cache
def registrar_movimiento_caja(comercio_id, tipo, monto, concepto, usuario_nombre):
    """Registra un ingreso extra o egreso de efectivo en la caja chica."""
    monto_val = float(monto or 0.0)
    if monto_val <= 0:
        raise BusinessLogicError("El monto debe ser mayor a $0.00.")
    if tipo not in ('ingreso_extra', 'egreso'):
        raise BusinessLogicError("Tipo de movimiento inválido.")
    if not concepto or not str(concepto).strip():
        raise BusinessLogicError("El concepto es obligatorio.")
        
    supabase = get_connection()
    payload = {
        "comercio_id": comercio_id,
        "tipo": tipo,
        "monto": monto_val,
        "concepto": str(concepto).strip(),
        "usuario_nombre": str(usuario_nombre).strip() if usuario_nombre else "Desconocido"
    }
    res = supabase.table("movimientos_caja").insert(payload).execute()
    if not res.data:
        raise Exception("Error al registrar el movimiento de caja.")
    return res.data[0]["id"]


@st.cache_data(ttl=120)
def obtener_movimientos_caja(comercio_id, fecha_inicio, fecha_fin=None):
    """Obtiene los movimientos de caja chica en un rango de fechas."""
    supabase = get_connection()
    query = supabase.table("movimientos_caja").select("*").eq("comercio_id", comercio_id).order("id", desc=True)
    
    if fecha_inicio:
        inicio = f"{fecha_inicio} 00:00:00"
        query = query.gte("fecha", inicio)
    if fecha_fin:
        fin = f"{fecha_fin} 23:59:59"
        query = query.lte("fecha", fin)
    elif fecha_inicio:
        fin = f"{fecha_inicio} 23:59:59"
        query = query.lte("fecha", fin)
        
    res = query.execute()
    return res.data or []


@st.cache_data(ttl=120)
def obtener_arqueo_caja(fecha_str=None, comercio_id=COMERCIO_ID_DEFAULT, **kwargs):
    """
    Retorna el informe consolidado de ventas del día:
    totales, ganancias estimadas, tickets y desglose por medio de pago.
    Acepta tanto fecha_str como fecha por nombre o posición.
    """
    fecha_filtro = kwargs.get("fecha", fecha_str)
    supabase = get_connection()
    query = (
        supabase.table("ventas")
        .select("*, clientes(nombre)")
        .eq("comercio_id", comercio_id)
        .order("id", desc=True)
    )
    
    if fecha_filtro:
        query = query.gte("fecha_hora", f"{fecha_filtro} 00:00:00").lte("fecha_hora", f"{fecha_filtro} 23:59:59")
        
    res_ventas = query.execute()
    ventas_data = res_ventas.data or []
    
    # Calcular costo total de lo vendido para estimar ganancia
    venta_ids = [v["id"] for v in ventas_data]
    costo_total = 0.0
    if venta_ids:
        res_detalles = supabase.table("detalle_ventas").select("venta_id, cantidad, costo_unitario").in_("venta_id", venta_ids).execute()
        for d in (res_detalles.data or []):
            cant = float(d.get("cantidad") or 0.0)
            costo = float(d.get("costo_unitario") or 0.0)
            costo_total += round(cant * costo, 2)
            
    total_vendido = 0.0
    desglose_dict = {}
    ventas_list = []
    
    for v in ventas_data:
        monto = float(v.get("total_venta") or 0.0)
        fp = v.get("forma_pago") or "Efectivo"
        total_vendido += monto
        
        if fp not in desglose_dict:
            desglose_dict[fp] = {"forma_pago": fp, "total": 0.0, "operaciones": 0}
        desglose_dict[fp]["total"] = round(desglose_dict[fp]["total"] + monto, 2)
        desglose_dict[fp]["operaciones"] += 1
        
        cli = v.get("clientes")
        if isinstance(cli, list):
            cli = cli[0] if cli else None
        cli_nom = cli.get("nombre") if cli else None
        
        ventas_list.append({
            "id": v["id"],
            "fecha_hora": str(v.get("fecha_hora") or ""),
            "total_venta": monto,
            "forma_pago": fp,
            "cliente_nombre": cli_nom
        })
        
    ganancia_estimada = max(0.0, round(total_vendido - costo_total, 2))
    
    # --- INCORPORACIÓN DE CAJA CHICA ---
    movs_caja = obtener_movimientos_caja(comercio_id, fecha_filtro, fecha_filtro)
    ingresos_extras = sum(float(m["monto"]) for m in movs_caja if m["tipo"] == "ingreso_extra")
    egresos = sum(float(m["monto"]) for m in movs_caja if m["tipo"] == "egreso")
    
    query_abonos = supabase.table("movimientos_cuenta").select("*").eq("comercio_id", comercio_id).eq("tipo", "PAGO").like("descripcion", "%(Efectivo)%")
    if fecha_filtro:
        query_abonos = query_abonos.gte("fecha_hora", f"{fecha_filtro} 00:00:00").lte("fecha_hora", f"{fecha_filtro} 23:59:59")
    res_abonos = query_abonos.execute()
    
    cobros_fiado_efectivo = sum(float(m.get("monto") or 0.0) for m in (res_abonos.data or []))
    
    ventas_efectivo = 0.0
    for fp_dict in desglose_dict.values():
        if fp_dict["forma_pago"] == "Efectivo":
            ventas_efectivo = fp_dict["total"]
            
    total_efectivo_esperado = ventas_efectivo + cobros_fiado_efectivo + ingresos_extras - egresos
    
    return {
        "total_vendido": round(total_vendido, 2),
        "ganancia_estimada": ganancia_estimada,
        "total_operaciones": len(ventas_data),
        "desglose_por_forma_pago": list(desglose_dict.values()),
        "ventas": ventas_list,
        "movimientos_caja": movs_caja,
        "ingresos_extras": ingresos_extras,
        "egresos": egresos,
        "cobros_fiado_efectivo": cobros_fiado_efectivo,
        "ventas_efectivo": ventas_efectivo,
        "total_efectivo_esperado": total_efectivo_esperado
    }


# ==========================================
# 5. MANTENIMIENTO Y REINICIO DE BASE
# ==========================================

RESET_MOVIMIENTOS = "movimientos"   # ventas, detalle, cuenta corriente; saldos a 0
RESET_FABRICA = "total"              # además: productos, categorías y clientes


@clears_cache
def resetear_datos(modo, usuario_id, pin, comercio_id=COMERCIO_ID_DEFAULT):
    """
    Puesta a cero de datos de prueba del comercio, en UNA transacción (RPC
    `resetear_datos_comercio`, ver sql/reset_datos.sql). Exige el PIN de un usuario admin.

    modo = RESET_MOVIMIENTOS: borra ventas, detalle, movimientos de cuenta corriente (y
           caja/arqueos si existieran) y pone saldo_deudor = 0. Conserva productos,
           categorías y clientes.
    modo = RESET_FABRICA: lo anterior + productos, categorías y clientes. Conserva la
           configuración del comercio y los usuarios.

    Devuelve un dict con la cantidad de filas borradas por tabla. Lanza BusinessLogicError
    (PIN incorrecto, sin permisos, bloqueo) o Exception (fallo técnico: no se borró nada).
    Las fotos locales de productos solo se borran DESPUÉS de que la base confirmó el reset.
    """
    if modo not in (RESET_MOVIMIENTOS, RESET_FABRICA):
        raise BusinessLogicError("Modo de reinicio inválido.")
    pin = str(pin or "").strip()
    if not (pin.isdigit() and len(pin) == 4):
        raise BusinessLogicError("Ingresá tu PIN de Dueño (4 dígitos).")

    res = _rpc_auth("resetear_datos_comercio", {
        "p_comercio_id": comercio_id,
        "p_modo": modo,
        "p_usuario_id": usuario_id,
        "p_pin": pin,
    }, archivo_sql="reset_datos.sql") or {}

    if not res.get("ok"):
        if res.get("motivo") == "no_autorizado":
            raise BusinessLogicError("Solo un usuario Dueño (admin) puede realizar esta acción.")
        if res.get("motivo") == "modo_invalido":
            raise BusinessLogicError("Modo de reinicio inválido.")
        raise BusinessLogicError(_mensaje_fallo_login(res))

    fotos_eliminadas = 0
    res["fotos_eliminadas"] = fotos_eliminadas
    return res


# --- ALIAS COMPATIBILIDAD ---
@st.cache_data(ttl=120)
def obtener_categorias(comercio_id=COMERCIO_ID_DEFAULT):
    return get_categorias(comercio_id)


# ==========================================
# 4. AUTENTICACIÓN Y ROLES (Dueño / Cajero)
# ==========================================
# El PIN se guarda hasheado (bcrypt) en la tabla `usuarios` y se valida SOLO dentro de
# Postgres, vía RPC (ver sql/usuarios_auth.sql). El hash nunca viaja a la app.

ROL_ADMIN = "admin"
ROL_CAJERO = "cajero"
ROLES_VALIDOS = (ROL_ADMIN, ROL_CAJERO)
ROL_ETIQUETAS = {ROL_ADMIN: "Dueño", ROL_CAJERO: "Cajero"}


def _rpc_auth(nombre_rpc, payload, archivo_sql="usuarios_auth.sql"):
    """Ejecuta una RPC de autenticación/mantenimiento y devuelve su `data`, con errores legibles."""
    try:
        return get_connection().rpc(nombre_rpc, payload).execute().data
    except Exception as e:
        codigo, mensaje = _error_rpc(e)
        if codigo == "PGRST202":
            raise Exception(
                f"Falta una función en Supabase ('{nombre_rpc}'). "
                f"Ejecutá sql/{archivo_sql} en el editor SQL."
            )
        raise Exception(f"No se pudo completar la operación en la base de datos: {mensaje}")


def _mensaje_fallo_login(res):
    """Mensaje apto para el usuario a partir de la respuesta (ok=false) de verificar_login."""
    motivo = res.get("motivo")
    if motivo == "bloqueado":
        mins = res.get("minutos_bloqueo") or 5
        return f"Demasiados intentos fallidos. Usuario bloqueado por {mins} min."
    if motivo == "pin_incorrecto":
        restan = res.get("intentos_restantes")
        extra = f" Te quedan {restan} intento(s)." if restan is not None else ""
        return f"PIN incorrecto.{extra}"
    return "Usuario no disponible. Elegí otro usuario."


@st.cache_data(ttl=120)
def listar_usuarios_login(comercio_id=COMERCIO_ID_DEFAULT):
    """Usuarios activos para la pantalla de login: [{id, nombre, rol}] (sin hash)."""
    data = _rpc_auth("listar_usuarios_login", {"p_comercio_id": comercio_id}) or []
    return [
        {"id": u["id"], "nombre": u["nombre"], "rol": u["rol"]}
        for u in data
        if u.get("rol") in ROLES_VALIDOS
    ]


def verificar_login(usuario_id, pin):
    """
    Valida el PIN de un usuario.
    Devuelve (usuario, error): `usuario` es {id, nombre, rol, comercio_id} si el login es
    correcto, o None con `error` como mensaje apto para mostrar al usuario.
    """
    pin = str(pin or "").strip()
    if not (pin.isdigit() and len(pin) == 4):
        return None, "El PIN debe tener 4 dígitos."

    res = _rpc_auth("verificar_login", {"p_usuario_id": usuario_id, "p_pin": pin}) or {}
    if res.get("ok"):
        usuario = res.get("usuario") or {}
        if usuario.get("rol") not in ROLES_VALIDOS:
            return None, "El usuario tiene un rol no reconocido."
        return usuario, None

    return None, _mensaje_fallo_login(res)


@clears_cache
def cambiar_pin(usuario_id, pin_actual, pin_nuevo):
    """Cambia el PIN (4 dígitos). Lanza BusinessLogicError si no se puede."""
    pin_nuevo = str(pin_nuevo or "").strip()
    if not (pin_nuevo.isdigit() and len(pin_nuevo) == 4):
        raise BusinessLogicError("El PIN nuevo debe tener exactamente 4 dígitos numéricos.")

    res = _rpc_auth("cambiar_pin", {
        "p_usuario_id": usuario_id,
        "p_pin_actual": str(pin_actual or "").strip(),
        "p_pin_nuevo": pin_nuevo,
    }) or {}
    if res.get("ok"):
        return True
    motivo = res.get("motivo")
    if motivo == "pin_actual_incorrecto":
        raise BusinessLogicError("El PIN actual es incorrecto.")
    if motivo == "pin_invalido":
        raise BusinessLogicError("El PIN nuevo debe tener exactamente 4 dígitos numéricos.")
    raise BusinessLogicError("No se pudo cambiar el PIN (usuario no disponible).")



@clears_cache
def actualizar_precios_masivamente(productos_modificados, comercio_id=COMERCIO_ID_DEFAULT):
    """
    Actualiza masivamente precio_costo, precio_venta, margen_ganancia y usa_precio_manual
    para una lista de productos modificados.
    `productos_modificados` es una lista de dicts:
    [{"id": 1, "precio_costo": 100, "precio_venta": 150, "usa_precio_manual": True, "margen_ganancia": 50}, ...]
    """
    supabase = get_connection()
    exitosos = 0
    for p in productos_modificados:
        try:
            payload = {
                "precio_costo": float(p["precio_costo"]),
                "precio_venta": float(p["precio_venta"]),
                "margen_ganancia": float(p.get("margen_ganancia", 0)),
                "usa_precio_manual": bool(p.get("usa_precio_manual", False))
            }
            res = supabase.table("productos").update(payload).eq("id", p["id"]).eq("comercio_id", comercio_id).execute()
            if res.data:
                exitosos += 1
        except Exception as e:
            print(f"Error actualizando producto {p['id']}: {e}")
    return exitosos


def generar_excel_inventario(productos=None, comercio_id=COMERCIO_ID_DEFAULT):
    """
    Exporta el inventario completo a un archivo .xlsx (Excel).
    Columnas: Código, Nombre, Categoría, Precio Costo, Precio Venta, Stock, Stock Mínimo, Puntos de Canje.
    """
    import io
    if productos is None:
        productos = obtener_productos(comercio_id=comercio_id)

    filas = []
    for p in productos:
        cat_nom = p.get("categoria_nombre") or p.get("categoria") or "Sin categoría"
        filas.append({
            "Código": str(p.get("codigo", "")),
            "Nombre": str(p.get("nombre", "")),
            "Categoría": str(cat_nom),
            "Precio Costo": round(float(p.get("precio_costo") or 0.0), 2),
            "Precio Venta": round(float(p.get("precio_venta") or 0.0), 2),
            "Stock": round(float(p.get("stock_actual") or 0.0), 2),
            "Stock Mínimo": round(float(p.get("stock_minimo") or 0.0), 2),
            "Puntos de Canje": int(p.get("puntos_canje") or 0),
        })

    columnas_orden = [
        "Código", "Nombre", "Categoría", "Precio Costo", 
        "Precio Venta", "Stock", "Stock Mínimo", "Puntos de Canje"
    ]
    df_exp = pd.DataFrame(filas) if filas else pd.DataFrame(columns=columnas_orden)
    if not df_exp.empty:
        df_exp = df_exp[columnas_orden]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_exp.to_excel(writer, index=False, sheet_name="Inventario")
    return output.getvalue()


def generar_plantilla_excel_productos():
    """
    Genera un archivo Excel (.xlsx) con la plantilla de ejemplo para la carga masiva.
    Columnas: codigo, nombre, categoria, precio_costo, precio_venta, stock, stock_minimo, puntos_canje
    """
    import io
    filas_ejemplo = [
        {
            "codigo": "7791234567890",
            "nombre": "Yerba Mate Clásica 500g",
            "categoria": "Almacén",
            "precio_costo": 1200.00,
            "precio_venta": 1800.00,
            "stock": 25.0,
            "stock_minimo": 5.0,
            "puntos_canje": 0,
        },
        {
            "codigo": "7799876543210",
            "nombre": "Gaseosa Cola 2.25L",
            "categoria": "Bebidas",
            "precio_costo": 1500.00,
            "precio_venta": 2300.00,
            "stock": 18.0,
            "stock_minimo": 6.0,
            "puntos_canje": 150,
        },
        {
            "codigo": "7795555444433",
            "nombre": "Galletitas Rellenas Vainilla 160g",
            "categoria": "Golosinas",
            "precio_costo": 650.00,
            "precio_venta": 1050.00,
            "stock": 30.0,
            "stock_minimo": 10.0,
            "puntos_canje": 50,
        },
    ]
    df_plantilla = pd.DataFrame(filas_ejemplo)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_plantilla.to_excel(writer, index=False, sheet_name="Plantilla")
    return output.getvalue()


@clears_cache
def importar_productos_masivo(df, comercio_id=COMERCIO_ID_DEFAULT):
    """
    Importa o actualiza productos en lote en Supabase a partir de un DataFrame.
    - Si la categoría del archivo no existe, la crea automáticamente.
    - Si el código ya existe, actualiza el producto existente.
    - Si el código no existe, inserta el nuevo producto.
    - Limpia la caché de Streamlit.
    """
    supabase = get_connection()
    if df is None or df.empty:
        return {"creados": 0, "actualizados": 0, "total": 0, "categorias_creadas": 0, "errores": []}

    # 1. Normalizar nombres de columnas
    mapeo_columnas = {}
    for col in df.columns:
        c_norm = str(col).strip().lower().replace(" ", "_")
        c_norm = c_norm.replace("ó", "o").replace("í", "i").replace("á", "a").replace("é", "e").replace("ú", "u")
        if c_norm in ["codigo", "código", "sku", "barcode", "cod"]:
            mapeo_columnas[col] = "codigo"
        elif c_norm in ["nombre", "producto", "descripcion", "articulo"]:
            mapeo_columnas[col] = "nombre"
        elif c_norm in ["categoria", "categoria_nombre", "rubro"]:
            mapeo_columnas[col] = "categoria"
        elif c_norm in ["precio_costo", "costo", "costo_unitario"]:
            mapeo_columnas[col] = "precio_costo"
        elif c_norm in ["precio_venta", "venta", "precio"]:
            mapeo_columnas[col] = "precio_venta"
        elif c_norm in ["stock", "stock_actual", "cantidad"]:
            mapeo_columnas[col] = "stock"
        elif c_norm in ["stock_minimo", "stock_min", "minimo"]:
            mapeo_columnas[col] = "stock_minimo"
        elif c_norm in ["puntos_canje", "puntos_de_canje", "puntos", "puntos_canje_premio"]:
            mapeo_columnas[col] = "puntos_canje"

    df_renombrado = df.rename(columns=mapeo_columnas)

    # 2. Categorías existentes
    res_cats = supabase.table("categorias").select("id, nombre").eq("comercio_id", comercio_id).execute()
    cat_map = {c["nombre"].strip().lower(): c["id"] for c in (res_cats.data or [])}
    categorias_creadas = 0

    # 3. Productos existentes
    res_prods = supabase.table("productos").select("id, codigo").eq("comercio_id", comercio_id).execute()
    prod_map = {str(p["codigo"]).strip(): p["id"] for p in (res_prods.data or [])}

    creados = 0
    actualizados = 0
    errores = []

    for idx, row in df_renombrado.iterrows():
        fila_num = idx + 2
        codigo_raw = row.get("codigo")
        nombre_raw = row.get("nombre")

        if pd.isna(codigo_raw) or str(codigo_raw).strip() == "":
            errores.append(f"Fila {fila_num}: El código de barras / SKU está vacío.")
            continue

        if isinstance(codigo_raw, float) and codigo_raw.is_integer():
            codigo = str(int(codigo_raw)).strip()
        else:
            codigo = str(codigo_raw).strip()
            if codigo.endswith(".0"):
                codigo = codigo[:-2]

        if pd.isna(nombre_raw) or str(nombre_raw).strip() == "":
            errores.append(f"Fila {fila_num} (código {codigo}): El nombre del producto está vacío.")
            continue
        nombre = str(nombre_raw).strip()

        try:
            precio_costo = float(row.get("precio_costo") if pd.notna(row.get("precio_costo")) else 0.0)
            if precio_costo < 0:
                errores.append(f"Fila {fila_num} ('{nombre}'): El precio de costo no puede ser negativo.")
                continue
        except (ValueError, TypeError):
            errores.append(f"Fila {fila_num} ('{nombre}'): Precio de costo inválido.")
            continue

        try:
            precio_venta = float(row.get("precio_venta") if pd.notna(row.get("precio_venta")) else 0.0)
            if precio_venta < 0:
                errores.append(f"Fila {fila_num} ('{nombre}'): El precio de venta no puede ser negativo.")
                continue
        except (ValueError, TypeError):
            errores.append(f"Fila {fila_num} ('{nombre}'): Precio de venta inválido.")
            continue

        try:
            stock = float(row.get("stock") if pd.notna(row.get("stock")) else 0.0)
            if stock < 0:
                errores.append(f"Fila {fila_num} ('{nombre}'): El stock no puede ser negativo.")
                continue
        except (ValueError, TypeError):
            stock = 0.0

        try:
            stock_minimo = float(row.get("stock_minimo") if pd.notna(row.get("stock_minimo")) else 0.0)
            if stock_minimo < 0:
                errores.append(f"Fila {fila_num} ('{nombre}'): El stock mínimo no puede ser negativo.")
                continue
        except (ValueError, TypeError):
            stock_minimo = 0.0

        try:
            puntos_canje = int(row.get("puntos_canje") if pd.notna(row.get("puntos_canje")) else 0)
            if puntos_canje < 0:
                puntos_canje = 0
        except (ValueError, TypeError):
            puntos_canje = 0

        # Categoría
        cat_raw = row.get("categoria")
        cat_nombre = str(cat_raw).strip() if pd.notna(cat_raw) and str(cat_raw).strip() else "General"
        cat_key = cat_nombre.lower()

        if cat_key not in cat_map:
            try:
                res_c = supabase.table("categorias").insert({"nombre": cat_nombre, "comercio_id": comercio_id}).execute()
                if res_c.data:
                    cat_id = res_c.data[0]["id"]
                    cat_map[cat_key] = cat_id
                    categorias_creadas += 1
                else:
                    cat_id = None
            except Exception:
                res_c = supabase.table("categorias").select("id").eq("comercio_id", comercio_id).ilike("nombre", cat_nombre).limit(1).execute()
                cat_id = res_c.data[0]["id"] if res_c.data else None
                if cat_id:
                    cat_map[cat_key] = cat_id
        else:
            cat_id = cat_map[cat_key]

        if precio_costo > 0 and precio_venta >= precio_costo:
            margen = round(((precio_venta - precio_costo) / precio_costo) * 100.0, 2)
        else:
            margen = 0.0

        if codigo in prod_map:
            prod_id = prod_map[codigo]
            payload = {
                "nombre": nombre,
                "categoria_id": cat_id,
                "precio_costo": precio_costo,
                "margen_ganancia": margen,
                "precio_venta": precio_venta,
                "usa_precio_manual": True,
                "stock_actual": stock,
                "stock_minimo": stock_minimo,
                "puntos_canje": puntos_canje,
            }
            try:
                supabase.table("productos").update(payload).eq("id", prod_id).eq("comercio_id", comercio_id).execute()
            except Exception as e:
                if "puntos_canje" in str(e).lower() or "PGRST204" in str(e):
                    payload.pop("puntos_canje", None)
                    supabase.table("productos").update(payload).eq("id", prod_id).eq("comercio_id", comercio_id).execute()
                else:
                    errores.append(f"Error actualizando producto '{nombre}' ({codigo}): {e}")
                    continue
            actualizados += 1
        else:
            payload = {
                "comercio_id": comercio_id,
                "codigo": codigo,
                "nombre": nombre,
                "categoria_id": cat_id,
                "precio_costo": precio_costo,
                "margen_ganancia": margen,
                "precio_venta": precio_venta,
                "usa_precio_manual": True,
                "stock_actual": stock,
                "stock_minimo": stock_minimo,
                "imagen_url": "",
                "puntos_canje": puntos_canje,
            }
            try:
                res_p = supabase.table("productos").insert(payload).execute()
            except Exception as e:
                if "puntos_canje" in str(e).lower() or "PGRST204" in str(e):
                    payload.pop("puntos_canje", None)
                    res_p = supabase.table("productos").insert(payload).execute()
                else:
                    errores.append(f"Error creando producto '{nombre}' ({codigo}): {e}")
                    continue
            if res_p and res_p.data:
                prod_map[codigo] = res_p.data[0]["id"]
            creados += 1

    st.cache_data.clear()
    return {
        "creados": creados,
        "actualizados": actualizados,
        "total": creados + actualizados,
        "categorias_creadas": categorias_creadas,
        "errores": errores
    }


