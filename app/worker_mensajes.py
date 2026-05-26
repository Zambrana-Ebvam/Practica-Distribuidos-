import os
import json
import pika
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "outputs", "mensajes")
os.makedirs(LOG_DIR, exist_ok=True)

RABBIT_HOST = os.getenv("RABBITMQ_HOST", "localhost")
QUEUE_NAME = os.getenv("RABBITMQ_QUEUE", "semapa_preavisos")


def procesar_mensaje(ch, method, properties, body):
    data = json.loads(body.decode("utf-8"))

    canal = data.get("canal")
    destinatario = data.get("destinatario")
    cuenta_id = data.get("cuenta_id")
    periodo = data.get("periodo")
    mensaje = data.get("mensaje")

    print("=" * 80)
    print(f"CANAL: {canal}")
    print(f"DESTINATARIO: {destinatario}")
    print(f"CUENTA: {cuenta_id}")
    print(f"PERIODO: {periodo}")
    print(f"MENSAJE: {mensaje}")
    print(f"PDF ROLLO: {data.get('pdf_rollo')}")
    print(f"PDF MEDIA CARTA: {data.get('pdf_media_carta')}")
    print("=" * 80)

    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{canal}_{cuenta_id}.json"
    path = os.path.join(LOG_DIR, filename)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

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

    print("Worker de mensajeria SEMAPA iniciado.")
    print("Esperando mensajes de preaviso...")
    channel.start_consuming()


if __name__ == "__main__":
    main()