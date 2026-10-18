"""
Módulo de generación de reportes PDF y despacho de correos electrónicos.
Utiliza ReportLab para compilar documentos estilizados y smtplib para el envío automático.
"""
import io
import re
import urllib.parse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def generar_pdf_cierre_caja(
    fecha_str: str,
    resumen: Dict[str, Any],
    nombre_negocio: str = "Mi Comercio"
) -> bytes:
    """
    Genera en memoria un documento PDF profesional del Cierre Diario de Caja.
    Retorna los bytes del archivo PDF generado.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Estilos tipográficos personalizados
    titulo_style = ParagraphStyle(
        "TituloReporte",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1E293B"),
        alignment=0
    )
    
    subtitulo_style = ParagraphStyle(
        "SubtituloReporte",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748B")
    )
    
    seccion_style = ParagraphStyle(
        "TituloSeccion",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0F172A")
    )

    cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#0F172A")
    )

    cell_normal = ParagraphStyle(
        "CellNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#334155")
    )

    elements = []

    # 1. ENCABEZADO
    elements.append(Paragraph(nombre_negocio.upper(), titulo_style))
    elements.append(Paragraph(f"INFORME OFICIAL DE CIERRE DE CAJA & ARQUEO DIARIO", subtitulo_style))
    elements.append(Paragraph(f"Fecha Contable: <b>{fecha_str}</b> | Emisión: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", subtitulo_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#CBD5E1"), spaceAfter=15))

    # 2. TARJETAS DE INDICADORES (KPIs)
    total_vendido = resumen.get("total_vendido", 0.0)
    ganancia_estimada = resumen.get("ganancia_estimada", 0.0)
    total_operaciones = resumen.get("total_operaciones", 0)

    kpi_data = [
        [
            Paragraph("<font size='9' color='#64748B'>TOTAL FACTURADO</font><br/><br/><b><font size='16' color='#0F172A'>${:,.2f}</font></b>".format(total_vendido), styles["Normal"]),
            Paragraph("<font size='9' color='#64748B'>GANANCIA ESTIMADA</font><br/><br/><b><font size='16' color='#16A34A'>${:,.2f}</font></b>".format(ganancia_estimada), styles["Normal"]),
            Paragraph("<font size='9' color='#64748B'>TOTAL DE OPERACIONES</font><br/><br/><b><font size='16' color='#2563EB'>{}</font></b>".format(total_operaciones), styles["Normal"])
        ]
    ]

    t_kpi = Table(kpi_data, colWidths=[180, 180, 180])
    t_kpi.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (0, 0), 1, colors.HexColor("#E2E8F0")),
        ("BOX", (1, 0), (1, 0), 1, colors.HexColor("#E2E8F0")),
        ("BOX", (2, 0), (2, 0), 1, colors.HexColor("#E2E8F0")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    elements.append(t_kpi)
    elements.append(Spacer(1, 20))

    # 3. DESGLOSE POR MEDIO DE PAGO
    elements.append(Paragraph("💳 Desglose por Medio de Pago", seccion_style))
    elements.append(Spacer(1, 8))

    desglose = resumen.get("desglose_por_forma_pago", [])
    if desglose:
        tabla_pago_data = [
            [
                Paragraph("<b>Medio de Pago</b>", cell_bold),
                Paragraph("<b>Operaciones</b>", cell_bold),
                Paragraph("<b>Subtotal Recaudado</b>", cell_bold),
                Paragraph("<b>% Participación</b>", cell_bold)
            ]
        ]

        for item in desglose:
            pct = (item["total"] / total_vendido * 100.0) if total_vendido > 0 else 0.0
            tabla_pago_data.append([
                Paragraph(item["forma_pago"], cell_normal),
                Paragraph(str(item["operaciones"]), cell_normal),
                Paragraph(f"${item['total']:,.2f}", cell_bold),
                Paragraph(f"{pct:.1f}%", cell_normal)
            ])

        t_pago = Table(tabla_pago_data, colWidths=[180, 100, 140, 120])
        t_pago.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]))
        elements.append(t_pago)
    else:
        elements.append(Paragraph("<i>No se registraron ventas en esta jornada.</i>", cell_normal))

    elements.append(Spacer(1, 20))

    # 4. LISTA DE TICKETS DEL DÍA
    elements.append(Paragraph("📜 Detalle Cronológico de Ventas", seccion_style))
    elements.append(Spacer(1, 8))

    ventas = resumen.get("ventas", [])
    if ventas:
        tabla_ventas_data = [
            [
                Paragraph("<b>Ticket #</b>", cell_bold),
                Paragraph("<b>Hora</b>", cell_bold),
                Paragraph("<b>Medio de Pago</b>", cell_bold),
                Paragraph("<b>Total Ticket</b>", cell_bold)
            ]
        ]

        for v in ventas:
            hora_str = v.get("fecha_hora", "")
            if " " in hora_str:
                hora_str = hora_str.split(" ")[1]

            tabla_ventas_data.append([
                Paragraph(f"#{v['id']}", cell_normal),
                Paragraph(hora_str, cell_normal),
                Paragraph(v.get("forma_pago", ""), cell_normal),
                Paragraph(f"${v.get('total_venta', 0.0):,.2f}", cell_bold)
            ])

        t_ventas = Table(tabla_ventas_data, colWidths=[100, 120, 180, 140])
        t_ventas.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]))
        elements.append(t_ventas)
    else:
        elements.append(Paragraph("<i>Sin tickets emitidos en la fecha indicada.</i>", cell_normal))

    elements.append(Spacer(1, 30))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=10))
    elements.append(Paragraph("Documento de control interno generado automáticamente por el Sistema de Gestión Comercial.", subtitulo_style))

    # Construir documento
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def enviar_email_cierre(
    destinatario: str,
    pdf_bytes: bytes,
    fecha_str: str,
    resumen: Dict[str, Any],
    config_smtp: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Envía por correo electrónico el PDF de cierre de caja adjunto usando smtplib.
    Retorna una tupla (éxito: bool, mensaje: str).
    """
    destinatario_limpio = (destinatario or config_smtp.get("email_destinatario", "")).strip()
    if not destinatario_limpio:
        return False, "No se especificó ninguna dirección de correo de destino."

    servidor_smtp = config_smtp.get("smtp_servidor", "").strip()
    puerto_smtp = int(config_smtp.get("smtp_puerto", 587))
    usuario_smtp = config_smtp.get("smtp_usuario", "").strip()
    password_smtp = config_smtp.get("smtp_password", "").strip()
    nombre_negocio = config_smtp.get("nombre_negocio", "Mi Comercio")

    if not servidor_smtp or not usuario_smtp or not password_smtp:
        return False, "La configuración de servidor SMTP, usuario o contraseña está incompleta."

    try:
        total_vendido = resumen.get("total_vendido", 0.0)
        ganancia_estimada = resumen.get("ganancia_estimada", 0.0)
        total_ops = resumen.get("total_operaciones", 0)

        # Crear mensaje MIME
        msg = MIMEMultipart()
        msg["From"] = f"{nombre_negocio} <{usuario_smtp}>"
        msg["To"] = destinatario_limpio
        msg["Subject"] = f"📊 Cierre de Caja {fecha_str} - {nombre_negocio}"

        cuerpo_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
            <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; max-width: 600px;">
                <h2 style="color: #0f172a; margin-top: 0;">Resumen Diario de Ventas - {nombre_negocio}</h2>
                <p>Adjunto encontrarás el informe oficial en formato PDF correspondiente al cierre del día <b>{fecha_str}</b>.</p>
                <hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 15px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #64748b;">Total Facturado:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; font-size: 16px; color: #0f172a;">${total_vendido:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #64748b;">Ganancia Estimada:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; font-size: 16px; color: #16a34a;">${ganancia_estimada:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #64748b;">Cantidad de Operaciones:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; color: #2563eb;">{total_ops} tickets</td>
                    </tr>
                </table>
                <hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 15px 0;">
                <p style="font-size: 12px; color: #94a3b8; margin-bottom: 0;">Enviado automáticamente por el Sistema de Gestión Comercial.</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(cuerpo_html, "html"))

        # Adjuntar archivo PDF
        adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
        adjunto.add_header("Content-Disposition", "attachment", filename=f"Cierre_Caja_{fecha_str}.pdf")
        msg.attach(adjunto)

        # Conectar al servidor SMTP y enviar
        with smtplib.SMTP(servidor_smtp, puerto_smtp, timeout=20) as server:
            server.ehlo()
            if puerto_smtp == 587:
                server.starttls()
                server.ehlo()
            server.login(usuario_smtp, password_smtp)
            server.send_message(msg)

        return True, f"Correo enviado exitosamente a {destinatario_limpio}."

    except Exception as e:
        return False, f"Error al enviar correo por SMTP: {str(e)}"


def _total_ticket(datos_ticket: Dict[str, Any]) -> float:
    """Total del ticket: 'total_venta', o 'total' si falta o es nulo; 0.0 si no hay ninguno."""
    return float(datos_ticket.get("total_venta") or datos_ticket.get("total") or 0.0)


def generar_pdf_ticket_termico(
    datos_ticket: Dict[str, Any],
    nombre_negocio: str = "Mi Comercio"
) -> bytes:
    """
    Genera en memoria un comprobante de ticket en formato térmico estándar de 80 mm.
    Retorna los bytes del archivo PDF generado.
    """
    items = datos_ticket.get("items", [])
    
    # Calcular altura dinámica en mm según la cantidad de renglones de productos
    alto_mm = max(115.0, 75.0 + (len(items) * 8.5))
    ancho_pt = 80 * mm
    alto_pt = alto_mm * mm
    margen_pt = 11.3  # aprox 4 mm

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(ancho_pt, alto_pt),
        leftMargin=margen_pt,
        rightMargin=margen_pt,
        topMargin=margen_pt,
        bottomMargin=margen_pt
    )

    styles = getSampleStyleSheet()

    negocio_style = ParagraphStyle(
        "TicketNegocio",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        alignment=1,
        textColor=colors.black
    )

    centrado_chico = ParagraphStyle(
        "TicketCentradoChico",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        alignment=1,
        textColor=colors.HexColor("#222222")
    )

    normal_ticket = ParagraphStyle(
        "TicketNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.black
    )

    bold_ticket = ParagraphStyle(
        "TicketBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.black
    )

    total_style = ParagraphStyle(
        "TicketTotal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=13,
        alignment=2,
        textColor=colors.black
    )

    elements = []

    # 1. ENCABEZADO DEL COMERCIO
    elements.append(Paragraph(nombre_negocio.upper(), negocio_style))
    direccion = datos_ticket.get("direccion_negocio", "")
    telefono = datos_ticket.get("telefono_negocio", "")
    sub_lineas = []
    if direccion:
        sub_lineas.append(direccion)
    if telefono:
        sub_lineas.append(f"Tel: {telefono}")
    sub_lineas.append("TICKET DE VENTA")
    elements.append(Paragraph("<br/>".join(sub_lineas), centrado_chico))
    
    elements.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#333333"), spaceBefore=3, spaceAfter=4))

    # 2. DATOS DE LA VENTA
    venta_id = datos_ticket.get("venta_id", "-")
    fecha_hora = datos_ticket.get("fecha_hora", datetime.now().strftime("%d/%m/%Y %H:%M"))
    cliente_nombre = datos_ticket.get("cliente_nombre", "Consumidor Final")
    forma_pago = datos_ticket.get("forma_pago", "Efectivo")

    info_venta = [
        [Paragraph(f"<b>Ticket:</b> #{venta_id}", normal_ticket), Paragraph(f"<b>Fecha:</b> {fecha_hora}", normal_ticket)],
        [Paragraph(f"<b>Cliente:</b> {cliente_nombre}", normal_ticket), Paragraph(f"<b>Pago:</b> {forma_pago}", normal_ticket)]
    ]
    t_info = Table(info_venta, colWidths=[95, 109])
    t_info.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(t_info)

    elements.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#333333"), spaceBefore=3, spaceAfter=4))

    # 3. TABLA DE ARTÍCULOS
    # Ancho disponible: 204 pt aprox. Reparto: Cant (26), Detalle (96), P.Unit (40), Total (42)
    tabla_items_data = [
        [
            Paragraph("<b>Cant</b>", bold_ticket),
            Paragraph("<b>Detalle</b>", bold_ticket),
            Paragraph("<b>P.Unit</b>", bold_ticket),
            Paragraph("<b>Subtot</b>", bold_ticket)
        ]
    ]

    for it in items:
        cant = it.get("cantidad", 1)
        cant_str = f"{cant:g}" if isinstance(cant, (int, float)) else str(cant)
        nombre_it = it.get("nombre", "Artículo")
        p_unit = it.get("precio_unitario", 0.0)
        subt = it.get("subtotal", 0.0)

        tabla_items_data.append([
            Paragraph(cant_str, normal_ticket),
            Paragraph(nombre_it[:30], normal_ticket),
            Paragraph(f"${p_unit:,.2f}", normal_ticket),
            Paragraph(f"${subt:,.2f}", bold_ticket)
        ])

    t_articulos = Table(tabla_items_data, colWidths=[26, 96, 40, 42])
    t_articulos.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
    ]))
    elements.append(t_articulos)

    elements.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#333333"), spaceBefore=3, spaceAfter=4))

    # 4. TOTAL
    total_venta = _total_ticket(datos_ticket)
    elements.append(Paragraph(f"TOTAL: ${total_venta:,.2f}", total_style))
    
    puntos_ganados = datos_ticket.get("puntos_ganados", 0)
    puntos_canjeados = datos_ticket.get("puntos_canjeados", 0)
    if puntos_canjeados > 0:
        elements.append(Spacer(1, 2))
        elements.append(Paragraph(f"Puntos canjeados: -{puntos_canjeados:,}", normal_ticket))
    if puntos_ganados > 0:
        elements.append(Spacer(1, 2))
        elements.append(Paragraph(f"Puntos ganados: +{puntos_ganados:,.2f}", normal_ticket))
    if puntos_canjeados > 0 or puntos_ganados > 0:
        puntos_balance = datos_ticket.get("puntos_balance", 0)
        elements.append(Paragraph(f"Balance total de puntos: {puntos_balance:,.2f}", normal_ticket))

    elements.append(Spacer(1, 4))

    # 5. PIE DE TICKET
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#888888"), spaceBefore=2, spaceAfter=4))
    elements.append(Paragraph("¡GRACIAS POR SU COMPRA!", centrado_chico))
    elements.append(Paragraph("Comprobante de control interno", centrado_chico))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def armar_mensaje_whatsapp_ticket(datos_ticket: Dict[str, Any]) -> str:
    """
    Arma el texto del comprobante de venta para WhatsApp utilizando viñetas
    estándar (-) sin caracteres especiales ni emojis que se corrompan en la URL.
    """
    negocio = datos_ticket.get("negocio_nombre", "Mi Comercio")
    cliente = datos_ticket.get("cliente_nombre", "Consumidor Final")
    venta_id = datos_ticket.get("venta_id", "-")
    fecha = datos_ticket.get("fecha", "-")
    forma_pago = datos_ticket.get("forma_pago", "-")
    total = _total_ticket(datos_ticket)

    lineas = [
        f"Hola {cliente}! Te compartimos el comprobante de tu compra en *{negocio}*:",
        "",
        f"- *Ticket Nro:* #{venta_id}",
        f"- *Fecha:* {fecha}",
        f"- *Medio de Pago:* {forma_pago}",
        f"- *Total Abonado:* ${total:,.2f}",
    ]

    puntos_ganados = datos_ticket.get("puntos_ganados", 0)
    puntos_canjeados = datos_ticket.get("puntos_canjeados", 0)
    if puntos_canjeados > 0:
        lineas.append(f"- *Puntos canjeados:* -{puntos_canjeados:,}")
    if puntos_ganados > 0:
        lineas.append(f"- *Puntos ganados:* +{puntos_ganados:,.2f}")
    if puntos_canjeados > 0 or puntos_ganados > 0:
        puntos_balance = datos_ticket.get("puntos_balance", 0)
        lineas.append(f"- *Balance de puntos:* {puntos_balance:,.2f}")

    lineas.extend([
        "",
        "Muchas gracias por tu compra!"
    ])
    return "\n".join(lineas)


def armar_mensaje_whatsapp_cierre(
    resumen: Dict[str, Any],
    fecha_str: str,
    nombre_negocio: str = "Mi Comercio"
) -> str:
    """
    Arma el texto del Cierre de Caja para WhatsApp con viñetas estándar (-).
    """
    total_vendido = resumen.get("total_vendido", 0.0)
    ganancia = resumen.get("ganancia_estimada", 0.0)
    total_ops = resumen.get("total_operaciones", 0)

    lineas = [
        f"*CIERRE DE CAJA - {nombre_negocio.upper()}*",
        f"- *Fecha:* {fecha_str}",
        f"- *Total Facturado:* ${total_vendido:,.2f}",
        f"- *Ganancia Estimada:* ${ganancia:,.2f}",
        f"- *Total Operaciones:* {total_ops} tickets",
        "",
        "*Desglose por Medio de Pago:*"
    ]
    for dp in resumen.get("desglose_por_forma_pago", []):
        lineas.append(f"- {dp['forma_pago']}: ${dp['total']:,.2f} ({dp['operaciones']} ops)")

    return "\n".join(lineas)


def armar_url_whatsapp(telefono: Optional[str], mensaje: str) -> str:
    """
    Limpia el teléfono a formato internacional y retorna el enlace wa.me 
    con codificación de texto limpia y segura para URL.
    """
    tel_limpio = re.sub(r"\D", "", str(telefono or ""))
    if len(tel_limpio) == 10:
        tel_limpio = f"549{tel_limpio}"
    elif len(tel_limpio) > 0 and not tel_limpio.startswith("54"):
        tel_limpio = f"54{tel_limpio}"

    texto_encoded = urllib.parse.quote(mensaje, safe="")
    if tel_limpio:
        return f"https://wa.me/{tel_limpio}?text={texto_encoded}"
    return f"https://wa.me/?text={texto_encoded}"



