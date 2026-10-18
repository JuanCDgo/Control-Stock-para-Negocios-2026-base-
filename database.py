import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def get_connection() -> Client:
    """Obtiene la conexión a Supabase usando el archivo secrets.toml."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except KeyError:
        raise Exception("Faltan configurar SUPABASE_URL y SUPABASE_KEY en .streamlit/secrets.toml")

    return create_client(url, key)

def _log(mensaje: str) -> None:
    """Imprime sin romper si la consola (ej. cp1252 en Windows) no soporta emojis/acentos."""
    try:
        print(mensaje)
    except UnicodeEncodeError:
        print(mensaje.encode("ascii", errors="replace").decode("ascii"))

def init_db():
    """Prueba rápida de conexión leyendo la tabla de comercios."""
    try:
        supabase = get_connection()
        respuesta = supabase.table("comercios").select("id, nombre_negocio").eq("id", 1).execute()
        
        if respuesta.data:
            _log(f"✅ ¡Conectado con éxito a Supabase! Comercio activo: {respuesta.data[0]['nombre_negocio']}")
        else:
            _log("⚠️ Conectó a Supabase, pero no se encontró el comercio inicial.")
            
    except Exception as e:
        _log(f"❌ Error al conectar con Supabase: {e}")

if __name__ == "__main__":
    init_db()