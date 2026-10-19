"""
Gestor de configuración del negocio (Datos Bancarios, QR de Pago, Parámetros de Email/SMTP
y Clave de Dueño / Administrador).
Persiste la configuración en un archivo JSON local en el directorio del proyecto.
"""
import os
import json
from typing import Dict, Any

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_negocio.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "nombre_negocio": "Mi Comercio",
    "titular_cuenta": "Titular de la Cuenta",
    "cbu": "0000003100012345678901",
    "alias": "comercio.pagos",
    "banco": "Banco / Billetera Virtual",
    "qr_imagen_path": None,
    "logo_imagen_path": None,
    "smtp_servidor": "smtp.gmail.com",
    "smtp_puerto": 587,
    "smtp_usuario": "",
    "smtp_password": "",
    "email_destinatario": ""
}


def cargar_configuracion() -> Dict[str, Any]:
    """Carga la configuración existente o retorna la configuración por defecto."""
    if not os.path.exists(CONFIG_FILE):
        guardar_configuracion(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(data)
            return cfg
    except Exception:
        return DEFAULT_CONFIG.copy()


def guardar_configuracion(nueva_config: Dict[str, Any]) -> bool:
    """Guarda la configuración actualizada en disco."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(nueva_config, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False
