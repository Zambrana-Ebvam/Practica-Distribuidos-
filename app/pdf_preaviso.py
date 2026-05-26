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


TARIFAS_ESCALONADAS = {
    "R1": {
        "fijo": 16.74,
        "rangos": [
            (13, 25, 1.10),
            (26, 50, 1.26),
            (51, 75, 1.87),
            (76, 100, 2.39),
            (101, 150, 2.84),
            (151, None, 3.34),
        ],
    },
    "R2": {
        "fijo": 33.37,
        "rangos": [
            (13, 25, 1.78),
            (26, 50, 1.98),
            (51, 75, 2.96),
            (76, 100, 3.59),
            (101, 150, 4.16),
            (151, None, 4.75),
        ],
    },
    "R3": {
        "fijo": 62.57,
        "rangos": [
            (13, 25, 2.17),
            (26, 50, 3.38),
            (51, 75, 3.76),
            (76, 100, 4.36),
            (101, 150, 4.96),
            (151, None, 5.54),
        ],
    },
    "R4": {
        "fijo": 104.22,
        "rangos": [
            (13, 25, 2.58),
            (26, 50, 2.80),
            (51, 75, 4.39),
            (76, 100, 4.99),
            (101, 150, 5.59),
            (151, None, 6.20),
        ],
    },
    "C": {
        "fijo": 125.16,
        "rangos": [
            (13, 25, 5.35),
            (26, 50, 5.73),
            (51, 75, 6.14),
            (76, 100, 6.53),
            (101, 150, 6.92),
            (151, None, 7.34),
        ],
    },
    "CE": {
        "fijo": 145.98,
        "rangos": [
            (13, 25, 8.72),
            (26, 50, 8.72),
            (51, 75, 9.12),
            (76, 100, 9.50),
            (101, 150, 9.90),
            (151, None, 10.29),
        ],
    },
    "I": {
        "fijo": 112.64,
        "rangos": [
            (13, 25, 4.95),
            (26, 50, 5.66),
            (51, 75, 5.94),
            (76, 100, 6.33),
            (101, 150, 6.73),
            (151, None, 7.11),
        ],
    },
    "P": {
        "fijo": 54.98,
        "rangos": [
            (13, 25, 2.17),
            (26, 50, 2.39),
            (51, 75, 2.98),
            (76, 100, 3.35),
            (101, 150, 3.76),
            (151, None, 4.10),
        ],
    },
    "S": {
        "fijo": 91.72,
        "rangos": [
            (13, 25, 3.57),
            (26, 50, 3.77),
            (51, 75, 3.96),
            (76, 100, 4.35),
            (101, 150, 4.75),
            (151, None, 5.15),
        ],
    },
}

CARGO_FIJO_M3 = 12


def normalizar_subcategoria(categoria, subcategoria=""):
    categoria = str(categoria or "").upper().strip()
    subcategoria = str(subcategoria or "").upper().strip()

    if subcategoria in TARIFAS_ESCALONADAS:
        return subcategoria

    if categoria in TARIFAS_ESCALONADAS:
        return categoria

    if "COMERCIAL ESPECIAL" in categoria:
        return "CE"

    if "RESIDENCIAL" in categoria:
        return "R2"

    if "COMERCIAL" in categoria:
        return "C"

    if "INDUSTRIAL" in categoria:
        return "I"

    if "PREFERENCIAL" in categoria:
        return "P"

    if "SOCIAL" in categoria:
        return "S"

    return "R2"


def calcular_factura_agua(consumo_m3, categoria, subcategoria=""):
    consumo_m3 = max(float(consumo_m3 or 0), 0)
    codigo = normalizar_subcategoria(categoria, subcategoria)
    tarifa = TARIFAS_ESCALONADAS[codigo]

    fijo = tarifa["fijo"]

    detalle = [
        {
            "concepto": f"Cargo fijo hasta {CARGO_FIJO_M3} m3",
            "m3": min(consumo_m3, CARGO_FIJO_M3),
            "tarifa": fijo,
            "subtotal": fijo,
        }
    ]

    if consumo_m3 <= CARGO_FIJO_M3:
        return {
            "codigo_tarifa": codigo,
            "consumo_m3": round(consumo_m3, 2),
            "monto_bs": round(fijo, 2),
            "detalle": detalle,
        }

    monto = fijo

    for desde, hasta, precio in tarifa["rangos"]:
        if consumo_m3 < desde:
            continue

        limite = hasta if hasta is not None else consumo_m3
        m3_rango = min(consumo_m3, limite) - desde + 1

        if m3_rango <= 0:
            continue

        subtotal = m3_rango * precio
        monto += subtotal

        detalle.append({
            "concepto": f"Rango {desde}-{hasta if hasta else 'mas'} m3",
            "m3": round(m3_rango, 2),
            "tarifa": precio,
            "subtotal": round(subtotal, 2),
        })

    return {
        "codigo_tarifa": codigo,
        "consumo_m3": round(consumo_m3, 2),
        "monto_bs": round(monto, 2),
        "detalle": detalle,
    }


def obtener_tarifa(categoria, subcategoria=""):
    codigo = normalizar_subcategoria(categoria, subcategoria)
    return TARIFAS_ESCALONADAS[codigo]["fijo"]


def preparar_factura_cuenta(detalle, consumo_periodo):
    categoria = detalle.get("categoria", "")
    subcategoria = detalle.get("subcategoria", "")
    consumo_m3 = float(consumo_periodo.get("consumo_m3", 0))
    factura = calcular_factura_agua(consumo_m3, categoria, subcategoria)

    return {
        "cuenta_id": detalle.get("cuenta_id", ""),
        "medidor": detalle.get("medidor_mac", ""),
        "categoria": categoria,
        "subcategoria": subcategoria,
        "codigo_tarifa": factura["codigo_tarifa"],
        "consumo_m3": factura["consumo_m3"],
        "monto_facturado_bs": factura["monto_bs"],
        "detalle_tarifario": factura["detalle"],
    }


def limpiar_nombre_archivo(texto):
    texto = str(texto)
    nombre, ext = os.path.splitext(texto)
    nombre = re.sub(r"[^a-zA-Z0-9_-]", "_", nombre)
    return (nombre + ext)[:80]


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

    factura = calcular_factura_agua(consumo_m3, categoria, subcategoria)
    tarifa = factura["codigo_tarifa"]
    monto = factura["monto_bs"]
    detalle_tarifario = factura["detalle"]

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
        "detalle_tarifario": detalle_tarifario,
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
    c.drawString(3 * mm, y, f"Tarifa: {datos['tarifa']}")
    y -= 4 * mm
    c.drawString(3 * mm, y, f"Lecturas: {datos['total_lecturas']}")
    y -= 4 * mm
    c.drawString(3 * mm, y, f"Lecturas fallidas: {datos['lecturas_fallidas']}")
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(3 * mm, y, "Detalle por rangos:")
    y -= 4 * mm

    c.setFont("Helvetica", 5.5)
    for item in datos["detalle_tarifario"][:7]:
        concepto = item["concepto"][:22]
        m3 = item["m3"]
        subtotal = item["subtotal"]
        c.drawString(3 * mm, y, f"{concepto} {m3:.1f}m3 Bs{subtotal:.2f}")
        y -= 3.5 * mm

    y -= 3 * mm

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
    c.drawString(260, y, f"Tarifa aplicada: {datos['tarifa']}")
    y -= 16

    c.drawString(margin, y, f"Lecturas registradas: {datos['total_lecturas']}")
    c.drawString(260, y, f"Lecturas fallidas: {datos['lecturas_fallidas']}")
    y -= 22
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "Detalle tarifario escalonado")
    y -= 14

    c.setFont("Helvetica", 8)
    for item in datos["detalle_tarifario"][:7]:
        c.drawString(
            margin,
            y,
            f"{item['concepto']} | {item['m3']:.2f} m3 | Bs {item['tarifa']:.2f} | Subtotal Bs {item['subtotal']:.2f}"
        )
        y -= 11

    y -= 8

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

    factura = calcular_factura_agua(consumo_m3, categoria, subcategoria)
    monto = factura["monto_bs"]

    primer_nombre = str(cliente).split(" ")[0].title()

    return (
        f"Sr(a). {primer_nombre}, SEMAPA le recuerda que su preaviso de consumo "
        f"de agua correspondiente al periodo {periodo} es de Bs {monto:.2f}, "
        f"con un consumo registrado de {consumo_m3:.2f} m3."
    )
