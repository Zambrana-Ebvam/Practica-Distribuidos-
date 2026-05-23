import os
import re
import qrcode
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "preavisos")
os.makedirs(OUTPUT_DIR, exist_ok=True)


TARIFAS_BS = {
    "RESIDENCIAL": 2.80,
    "COMERCIAL": 10.43,
    "COMERCIAL ESPECIAL": 12.16,
    "INDUSTRIAL": 9.39,
    "PREFERENCIAL": 4.58,
    "SOCIAL": 7.64,
    "R1": 1.39,
    "R2": 2.78,
    "R3": 5.21,
    "R4": 8.69,
    "C": 10.43,
    "CE": 12.16,
    "I": 9.39,
    "P": 4.58,
    "S": 7.64
}


def limpiar_nombre_archivo(texto):
    texto = str(texto)
    texto = re.sub(r"[^a-zA-Z0-9_-]", "_", texto)
    return texto[:80]


def obtener_tarifa(categoria, subcategoria=""):
    categoria = str(categoria or "").upper().strip()
    subcategoria = str(subcategoria or "").upper().strip()

    if subcategoria in TARIFAS_BS:
        return TARIFAS_BS[subcategoria]

    if categoria in TARIFAS_BS:
        return TARIFAS_BS[categoria]

    if "RESIDENCIAL" in categoria:
        return TARIFAS_BS["RESIDENCIAL"]

    if "COMERCIAL ESPECIAL" in categoria:
        return TARIFAS_BS["COMERCIAL ESPECIAL"]

    if "COMERCIAL" in categoria:
        return TARIFAS_BS["COMERCIAL"]

    if "INDUSTRIAL" in categoria:
        return TARIFAS_BS["INDUSTRIAL"]

    if "PREFERENCIAL" in categoria:
        return TARIFAS_BS["PREFERENCIAL"]

    if "SOCIAL" in categoria:
        return TARIFAS_BS["SOCIAL"]

    return 3.00


def crear_qr(texto):
    qr = qrcode.QRCode(
        version=1,
        box_size=4,
        border=2
    )
    qr.add_data(texto)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return ImageReader(img.convert("RGB"))


def preparar_datos(detalle, consumo_periodo, historial):
    cuenta = detalle.get("cuenta_id", "")
    cliente = detalle.get("nombre_cliente", "")
    distrito = detalle.get("distrito", "")
    zona = detalle.get("zona", "")
    categoria = detalle.get("categoria", "")
    subcategoria = detalle.get("subcategoria", "")
    medidor = detalle.get("medidor_mac", "")
    direccion = detalle.get("direccion", "")

    periodo = consumo_periodo.get("periodo", "SIN PERIODO")
    consumo_m3 = float(consumo_periodo.get("consumo_m3", 0))
    total_lecturas = int(consumo_periodo.get("total_lecturas", 0))
    lecturas_fallidas = int(consumo_periodo.get("lecturas_fallidas", 0))

    tarifa = obtener_tarifa(categoria, subcategoria)
    monto = consumo_m3 * tarifa

    qr_text = (
        f"SEMAPA|CUENTA={cuenta}|PERIODO={periodo}|"
        f"CONSUMO={consumo_m3:.2f}|MONTO={monto:.2f}|MEDIDOR={medidor}"
    )

    return {
        "cuenta": cuenta,
        "cliente": cliente,
        "distrito": distrito,
        "zona": zona,
        "categoria": categoria,
        "subcategoria": subcategoria,
        "medidor": medidor,
        "direccion": direccion,
        "periodo": periodo,
        "consumo_m3": consumo_m3,
        "total_lecturas": total_lecturas,
        "lecturas_fallidas": lecturas_fallidas,
        "tarifa": tarifa,
        "monto": monto,
        "qr_text": qr_text,
        "historial": historial
    }


def generar_pdf_rollo(detalle, consumo_periodo, historial):
    datos = preparar_datos(detalle, consumo_periodo, historial)

    nombre = limpiar_nombre_archivo(
        f"preaviso_rollo_{datos['cuenta']}_{datos['periodo']}.pdf"
    )

    path = os.path.join(OUTPUT_DIR, nombre)

    width = 55 * mm
    height = 260 * mm

    c = canvas.Canvas(path, pagesize=(width, height))
    y = height - 8 * mm

    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width / 2, y, "SEMAPA")
    y -= 5 * mm

    c.setFont("Helvetica", 7)
    c.drawCentredString(width / 2, y, "PREAVISO DE CONSUMO")
    y -= 7 * mm

    c.line(3 * mm, y, width - 3 * mm, y)
    y -= 5 * mm

    c.setFont("Helvetica", 6.5)
    c.drawString(3 * mm, y, f"Cuenta: {datos['cuenta']}")
    y -= 4 * mm
    c.drawString(3 * mm, y, f"Cliente: {datos['cliente'][:26]}")
    y -= 4 * mm
    c.drawString(3 * mm, y, f"Distrito: {datos['distrito']}  Zona: {datos['zona'][:14]}")
    y -= 4 * mm
    c.drawString(3 * mm, y, f"Categoria: {datos['categoria']} {datos['subcategoria']}")
    y -= 4 * mm
    c.drawString(3 * mm, y, f"Medidor: {datos['medidor']}")
    y -= 4 * mm
    c.drawString(3 * mm, y, f"Periodo: {datos['periodo']}")
    y -= 5 * mm

    c.line(3 * mm, y, width - 3 * mm, y)
    y -= 5 * mm

    c.setFont("Helvetica-Bold", 7)
    c.drawString(3 * mm, y, "Detalle tarifario")
    y -= 5 * mm

    c.setFont("Helvetica", 6.5)
    c.drawString(3 * mm, y, f"Consumo m3: {datos['consumo_m3']:.2f}")
    y -= 4 * mm
    c.drawString(3 * mm, y, f"Tarifa Bs/m3: {datos['tarifa']:.2f}")
    y -= 4 * mm
    c.drawString(3 * mm, y, f"Lecturas: {datos['total_lecturas']}")
    y -= 4 * mm
    c.drawString(3 * mm, y, f"Lecturas fallidas: {datos['lecturas_fallidas']}")
    y -= 6 * mm

    c.setFont("Helvetica-Bold", 9)
    c.drawString(3 * mm, y, f"TOTAL Bs: {datos['monto']:.2f}")
    y -= 7 * mm

    c.line(3 * mm, y, width - 3 * mm, y)
    y -= 5 * mm

    c.setFont("Helvetica-Bold", 7)
    c.drawString(3 * mm, y, "Historial")
    y -= 5 * mm

    c.setFont("Helvetica", 6)
    for item in datos["historial"][:6]:
        periodo = item.get("periodo", "")
        consumo = float(item.get("consumo_m3", 0))
        c.drawString(3 * mm, y, f"{periodo}: {consumo:.2f} m3")
        y -= 4 * mm

    y -= 3 * mm

    qr_img = crear_qr(datos["qr_text"])
    qr_size = 25 * mm
    c.drawImage(qr_img, (width - qr_size) / 2, y - qr_size, qr_size, qr_size)
    y -= qr_size + 4 * mm

    c.setFont("Helvetica", 5.5)
    c.drawCentredString(width / 2, y, "QR de validacion SEMAPA")
    y -= 5 * mm
    c.drawCentredString(width / 2, y, datetime.now().strftime("%Y-%m-%d %H:%M"))

    c.showPage()
    c.save()

    return path


def generar_pdf_media_carta(detalle, consumo_periodo, historial):
    datos = preparar_datos(detalle, consumo_periodo, historial)

    nombre = limpiar_nombre_archivo(
        f"preaviso_media_carta_{datos['cuenta']}_{datos['periodo']}.pdf"
    )

    path = os.path.join(OUTPUT_DIR, nombre)

    width = letter[0]
    height = letter[1] / 2

    c = canvas.Canvas(path, pagesize=(width, height))

    margin = 28
    y = height - 30

    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "SEMAPA")
    c.setFont("Helvetica", 12)
    c.drawString(margin + 100, y, "Aviso de cobranza / Preaviso de consumo")
    y -= 25

    c.setStrokeColor(colors.HexColor("#0E7C86"))
    c.setLineWidth(2)
    c.line(margin, y, width - margin, y)
    y -= 25

    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y, "Datos del cliente")
    y -= 16

    c.setFont("Helvetica", 9)
    c.drawString(margin, y, f"Codigo cliente / Cuenta: {datos['cuenta']}")
    c.drawString(300, y, f"Periodo: {datos['periodo']}")
    y -= 14

    c.drawString(margin, y, f"Nombre: {datos['cliente']}")
    y -= 14

    c.drawString(margin, y, f"Direccion: {datos['direccion'][:75]}")
    y -= 14

    c.drawString(margin, y, f"Distrito: {datos['distrito']}     Zona: {datos['zona']}")
    y -= 14

    c.drawString(margin, y, f"Categoria: {datos['categoria']} {datos['subcategoria']}     Medidor: {datos['medidor']}")
    y -= 24

    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y, "Detalle de consumo y tarifa")
    y -= 18

    c.setFont("Helvetica", 9)
    c.drawString(margin, y, f"Consumo registrado: {datos['consumo_m3']:.2f} m3")
    c.drawString(260, y, f"Tarifa aplicada: Bs {datos['tarifa']:.2f} / m3")
    y -= 16

    c.drawString(margin, y, f"Lecturas registradas: {datos['total_lecturas']}")
    c.drawString(260, y, f"Lecturas fallidas: {datos['lecturas_fallidas']}")
    y -= 22

    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, f"Importe estimado a pagar: Bs {datos['monto']:.2f}")

    qr_img = crear_qr(datos["qr_text"])
    c.drawImage(qr_img, width - 130, 38, 90, 90)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, 105, "Historial de consumo")
    c.setFont("Helvetica", 8)

    x = margin
    y_hist = 88

    for item in datos["historial"][:6]:
        periodo = item.get("periodo", "")
        consumo = float(item.get("consumo_m3", 0))
        c.drawString(x, y_hist, f"{periodo}: {consumo:.2f} m3")
        y_hist -= 12

    c.setFont("Helvetica", 7)
    c.drawString(margin, 25, "Documento generado automaticamente por la Plataforma Big Data SEMAPA.")
    c.drawString(width - 150, 25, datetime.now().strftime("%Y-%m-%d %H:%M"))

    c.showPage()
    c.save()

    return path


def generar_pdfs_preaviso(detalle, consumo_periodo, historial):
    pdf_rollo = generar_pdf_rollo(detalle, consumo_periodo, historial)
    pdf_media_carta = generar_pdf_media_carta(detalle, consumo_periodo, historial)

    return {
        "rollo": pdf_rollo,
        "media_carta": pdf_media_carta
    }


def calcular_mensaje_preaviso(detalle, consumo_periodo):
    cliente = detalle.get("nombre_cliente", "Cliente")
    periodo = consumo_periodo.get("periodo", "")
    consumo_m3 = float(consumo_periodo.get("consumo_m3", 0))
    categoria = detalle.get("categoria", "")
    subcategoria = detalle.get("subcategoria", "")

    tarifa = obtener_tarifa(categoria, subcategoria)
    monto = consumo_m3 * tarifa

    primer_nombre = str(cliente).split(" ")[0].title()

    return (
        f"Sr(a). {primer_nombre}, SEMAPA le recuerda que su preaviso de consumo "
        f"de agua correspondiente al periodo {periodo} es de Bs {monto:.2f}, "
        f"con un consumo registrado de {consumo_m3:.2f} m3."
    )