import os
import json
import pika
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Directorios de configuración del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "outputs", "mensajes")
os.makedirs(LOG_DIR, exist_ok=True)

RABBIT_HOST = os.getenv("RABBITMQ_HOST", "localhost")
QUEUE_NAME = os.getenv("RABBITMQ_QUEUE", "semapa_preavisos")

# =====================================================================
# CONFIGURACIÓN DE CORREO SALIENTE (GMAIL SMTP REAL)
# =====================================================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "exozed117e.z.v@gmail.com"
SMTP_PASSWORD = "xywb oczo orwg hctp"  # Tu contraseña de aplicación segura de Google

# =====================================================================
# CONFIGURACIÓN DE WHATSAPP API (DESDE TU NÚMERO +59178304012)
# =====================================================================
WHATSAPP_API_URL = "http://localhost:8080/message/sendText"
WHATSAPP_API_TOKEN = "SEMAPA-Zambrana"
MI_NUMERO_WHATSAPP = "59178304012"


def generar_html_correo(cuenta_id, periodo, texto_mensaje):
    """
    Genera una plantilla de correo HTML profesional y elegante
    con diseño responsivo y colores corporativos para SEMAPA.
    """
    fecha_emision = datetime.now().strftime("%d/%m/%Y")
    
    # Intentamos formatear o limpiar líneas del mensaje original si vienen separadas por saltos de línea
    lineas = texto_mensaje.split("\n")
    lineas_html = "".join([f"<p style='margin: 6px 0; color: #4a5568;'>{linea}</p>" for linea in lineas if linea.strip()])

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Preaviso SEMAPA</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f4f7f6; font-family: 'Segoe UI', Arial, sans-serif; -webkit-font-smoothing: antialiased;">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f4f7f6; padding: 20px 0;">
            <tr>
                <td align="center">
                    <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                        
                        <tr>
                            <td style="background: linear-gradient(135deg, #0f4c81 0%, #1d72b8 100%); padding: 35px 40px; text-align: left;">
                                <table width="100%" border="0" cellspacing="0" cellpadding="0">
                                    <tr>
                                        <td>
                                            <h1 style="margin: 0; color: #ffffff; font-size: 26px; font-weight: 700; letter-spacing: 0.5px;">SEMAPA</h1>
                                            <p style="margin: 4px 0 0 0; color: #cbd5e1; font-size: 13px; text-transform: uppercase; letter-spacing: 1px;">Servicio de Agua Potable y Alcantarillado</p>
                                        </td>
                                        <td align="right" valign="middle">
                                            <span style="background-color: rgba(255,255,255,0.2); color: #ffffff; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 600;">PREAVISO DIGITAL</span>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding: 40px;">
                                <h2 style="margin: 0 0 15px 0; color: #1e293b; font-size: 20px; font-weight: 600;">Estimado Usuario,</h2>
                                <p style="margin: 0 0 25px 0; color: #64748b; font-size: 15px; line-height: 1.6;">
                                    Le hacemos llegar el preaviso correspondiente al consumo de agua potable de su inmueble. A continuación, se detallan los datos registrados en nuestro sistema distribuido:
                                </p>

                                <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; border-left: 4px solid #1d72b8; border-radius: 4px; margin-bottom: 30px;">
                                    <tr>
                                        <td style="padding: 20px;">
                                            <table width="100%" border="0" cellspacing="0" cellpadding="5">
                                                <tr>
                                                    <td width="35%" style="color: #64748b; font-size: 14px; font-weight: 600;">Código de Cuenta:</td>
                                                    <td style="color: #0f4c81; font-size: 15px; font-weight: 700;">{cuenta_id}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color: #64748b; font-size: 14px; font-weight: 600;">Período Facturado:</td>
                                                    <td style="color: #334155; font-size: 15px; font-weight: 600;">{periodo}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color: #64748b; font-size: 14px; font-weight: 600;">Fecha de Emisión:</td>
                                                    <td style="color: #334155; font-size: 14px;">{fecha_emision}</td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>

                                <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 20px; margin-bottom: 30px;">
                                    <h3 style="margin: 0 0 12px 0; color: #0f4c81; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #edf2f7; padding-bottom: 6px;">Detalle de Consumo y Valores</h3>
                                    <div style="font-size: 14px; line-height: 1.7;">
                                        {lineas_html}
                                    </div>
                                </div>

                                <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin-top: 20px; text-align: center;">
                                    <tr>
                                        <td>
                                            <a href="http://localhost:5173" target="_blank" style="background-color: #1d72b8; color: #ffffff; text-decoration: none; padding: 12px 30px; font-size: 15px; font-weight: 600; border-radius: 5px; display: inline-block; box-shadow: 0 3px 6px rgba(29,114,184,0.2);">
                                                Verificar en Oficina Virtual
                                            </a>
                                        </td>
                                    </tr>
                                </table>

                                <p style="margin: 35px 0 0 0; color: #94a3b8; font-size: 12px; line-height: 1.5; text-align: center;">
                                    Este es un mensaje automático generado de forma asincrónica mediante colas distribuidas por el sistema de preavisos SEMAPA. Por favor, no responda a esta dirección de correo.
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <td style="background-color: #0f4c81; padding: 20px; text-align: center;">
                                <p style="margin: 0; color: #ffffff; font-size: 12px; font-weight: 600;">&copy; {datetime.now().year} SEMAPA S.A. - Cochabamba, Bolivia</p>
                                <p style="margin: 4px 0 0 0; color: #93c5fd; font-size: 11px;">Tecnología y Saneamiento Ambiental Básico</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html_template


def enviar_correo_real(destinatario_email, asunto, cuerpo_mensaje, cuenta_id, periodo):
    """
    Envía un correo electrónico en formato HTML enriquecido utilizando smtplib.
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"SEMAPA Preavisos <{SMTP_USER}>"
        msg['To'] = destinatario_email
        msg['Subject'] = asunto

        # Generamos el diseño HTML profesional con los datos reales
        html_contenido = generar_html_correo(cuenta_id, periodo, cuerpo_mensaje)
        
        # Adjuntamos la versión en texto plano (como respaldo) y la versión HTML
        parte_texto = MIMEText(cuerpo_mensaje, 'plain', 'utf-8')
        parte_html = MIMEText(html_contenido, 'html', 'utf-8')
        
        msg.attach(parte_texto)
        msg.attach(parte_html)

        # Conexión segura TLS con Gmail
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, destinatario_email, msg.as_string())
        server.quit()

        print(f"[CORREO] ¡Éxito! Preaviso en formato HTML Premium enviado a: {destinatario_email}")
        return True
    except Exception as e:
        print(f"[CORREO ERROR] Falló el envío automático a {destinatario_email}: {str(e)}")
        return False


def enviar_whatsapp_real(numero_destino, texto_mensaje):
    """
    Envía un mensaje de WhatsApp real conectándose a tu pasarela local.
    """
    try:
        num_limpio = str(numero_destino).strip().replace("+", "").replace(" ", "")
        
        payload = {
            "number": num_limpio,
            "options": {"delay": 1000, "presence": "composing"},
            "textMessage": {"text": texto_mensaje}
        }
        headers = {
            "Content-Type": "application/json",
            "apikey": WHATSAPP_API_TOKEN
        }

        response = requests.post(WHATSAPP_API_URL, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            print(f"[WHATSAPP] ¡Éxito! Mensaje enviado desde tu número a: {numero_destino}")
            return True
        else:
            print(f"[WHATSAPP ALERTA] La API respondió {response.status_code}. Registrado en logs del sistema.")
            return False
            
    except Exception as e:
        print(f"[WHATSAPP ERROR] No se pudo conectar con el servidor local de WhatsApp: {str(e)}")
        return False


def procesar_mensaje(ch, method, properties, body):
    """
    Manejador principal de la cola de RabbitMQ. Mantiene intacta la persistencia original.
    """
    data = json.loads(body.decode("utf-8"))

    canal = str(data.get("canal", "")).lower().strip()
    destinatario = data.get("destinatario")
    cuenta_id = data.get("cuenta_id")
    periodo = data.get("periodo")
    mensaje = data.get("mensaje")

    print("\n" + "=" * 80)
    print(f"📥 [RABBITMQ] PROCESANDO PREAVISO ASINCRÓNICO")
    print(f"CANAL: {canal.upper()} | DESTINATARIO: {destinatario} | CUENTA: {cuenta_id} | PERIODO: {periodo}")
    print("=" * 80)

    # Bifurcación de canales configurados en tu Frontend
    if canal == "whatsapp":
        enviar_whatsapp_real(numero_destino=destinatario, texto_mensaje=mensaje)
        
    elif canal in ["email", "correo"]:
        asunto_preaviso = f"SEMAPA - Preaviso de Consumo de Agua (Período {periodo})"
        enviar_correo_real(
            destinatario_email=destinatario, 
            asunto=asunto_preaviso, 
            cuerpo_mensaje=mensaje,
            cuenta_id=cuenta_id,
            periodo=periodo
        )
        
    else:
        print(f"[WORKER] Canal '{canal}' detectado. No requiere procesamiento en esta etapa.")

    # PERSISTENCIA ORIGINAL EXACTA:
    # Genera el archivo .json en outputs/mensajes/ para que el botón "Ver Evidencia" del Frontend siga funcionando
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{canal}_{cuenta_id}.json"
    path = os.path.join(LOG_DIR, filename)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    # Confirmación segura a RabbitMQ para remover el mensaje de la cola
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBIT_HOST)
    )

    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=procesar_mensaje
    )

    print("🚀 Worker de Mensajería Distribuida SEMAPA Iniciado Correctamente.")
    print(f"📥 Escuchando cola '{QUEUE_NAME}' conectada a tu número +59178304012 y Gmail HTML Premium...")
    channel.start_consuming()


if __name__ == "__main__":
    main()