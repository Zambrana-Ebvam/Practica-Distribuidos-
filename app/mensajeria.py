import json
import pika
from datetime import datetime


RABBIT_HOST = "localhost"
QUEUE_NAME = "semapa_preavisos"


def publicar_preaviso(canal, destinatario, cuenta_id, periodo, mensaje, pdf_rollo, pdf_media_carta):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBIT_HOST)
    )

    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    payload = {
        "canal": canal,
        "destinatario": destinatario,
        "cuenta_id": cuenta_id,
        "periodo": periodo,
        "mensaje": mensaje,
        "pdf_rollo": pdf_rollo,
        "pdf_media_carta": pdf_media_carta,
        "fecha_envio": datetime.now().isoformat()
    }

    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        properties=pika.BasicProperties(
            delivery_mode=2
        )
    )

    connection.close()

    return payload


def publicar_tres_canales(destinatarios, cuenta_id, periodo, mensaje, pdf_rollo, pdf_media_carta):
    enviados = []

    for canal, destino in destinatarios.items():
        if destino and str(destino).strip():
            enviados.append(
                publicar_preaviso(
                    canal=canal,
                    destinatario=destino,
                    cuenta_id=cuenta_id,
                    periodo=periodo,
                    mensaje=mensaje,
                    pdf_rollo=pdf_rollo,
                    pdf_media_carta=pdf_media_carta
                )
            )

    return enviados