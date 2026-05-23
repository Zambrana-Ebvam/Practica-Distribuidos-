import os
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from db import get_session
from pdf_preaviso import generar_pdfs_preaviso, calcular_mensaje_preaviso, obtener_tarifa
from mensajeria import publicar_tres_canales


app = FastAPI(
    title="SEMAPA Big Data API",
    description="API para dashboards, mapa, preavisos PDF y mensajería SEMAPA",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session = get_session()


def fix_text(value):
    if value is None:
        return ""
    text = str(value)
    replacements = {
        "Ã¡": "á",
        "Ã©": "é",
        "Ã­": "í",
        "Ã³": "ó",
        "Ãº": "ú",
        "Ã±": "ñ",
        "Ã‘": "Ñ",
        "Ã‰": "É",
        "Ã“": "Ó",
        "Ã": "í"
    }
    for wrong, right in replacements.items():
        text = text.replace(wrong, right)
    return text


def normalizar_distrito(value):
    text = str(value).strip()
    if text.endswith(".0"):
        text = text.replace(".0", "")
    return text


def row_to_dict(row):
    if row is None:
        return None
    data = dict(row)

    for key in data:
        if isinstance(data[key], str):
            data[key] = fix_text(data[key])

    if "distrito" in data:
        data["distrito"] = normalizar_distrito(data["distrito"])

    return data


def rows_to_list(rows):
    return [row_to_dict(row) for row in rows]


@app.get("/")
def home():
    return {
        "status": "OK",
        "message": "API SEMAPA funcionando con Cassandra"
    }


@app.get("/api/distritos")
def get_distritos():
    rows = session.execute("""
        SELECT distrito, lat, lon, total_zonas, total_infraestructuras
        FROM distritos_mapa
    """)

    data = rows_to_list(rows)

    data = sorted(
        data,
        key=lambda x: int(float(x["distrito"])) if str(x["distrito"]).replace(".", "").isdigit() else 0
    )

    return data


@app.get("/api/distritos/{distrito}/resumen")
def get_resumen_distrito(distrito: str):
    distrito = normalizar_distrito(distrito)

    rows = session.execute("""
        SELECT distrito, periodo, consumo_m3, total_cuentas, total_medidores,
               medidores_activos, medidores_fuera_servicio
        FROM consumo_distrito_mes
        WHERE distrito = %s
    """, (distrito,))

    data = rows_to_list(rows)

    if not data:
        return {
            "distrito": distrito,
            "periodos": [],
            "ultimo": None
        }

    data = sorted(data, key=lambda x: x["periodo"], reverse=True)

    return {
        "distrito": distrito,
        "periodos": data,
        "ultimo": data[0]
    }


@app.get("/api/distritos/{distrito}/cuentas")
def get_cuentas_distrito(
    distrito: str,
    zona: Optional[str] = None,
    limit: int = 1000
):
    distrito = normalizar_distrito(distrito)

    rows = session.execute("""
        SELECT distrito, cuenta_id, numero_catastro, nombre_cliente, ci,
               categoria, subcategoria, zona, direccion, medidor_mac,
               modelo_medidor, estado_medidor, estado_contrato, tipo_servicio,
               latitud, longitud
        FROM cuentas_por_distrito
        WHERE distrito = %s
        LIMIT %s
    """, (distrito, limit))

    data = rows_to_list(rows)

    if zona and zona != "TODAS":
        zona_upper = zona.upper()
        data = [item for item in data if str(item.get("zona", "")).upper() == zona_upper]

    return data


@app.get("/api/cuentas/{cuenta_id}")
def get_cuenta_detalle(cuenta_id: str):
    row = session.execute("""
        SELECT cuenta_id, numero_catastro, nombre_cliente, ci, distrito,
               zona, categoria, subcategoria, direccion, medidor_mac,
               modelo_medidor, estado_medidor, estado_contrato, tipo_servicio,
               latitud, longitud
        FROM cuenta_detalle
        WHERE cuenta_id = %s
    """, (cuenta_id,)).one()

    if row is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    return row_to_dict(row)


@app.get("/api/cuentas/{cuenta_id}/consumo")
def get_consumo_cuenta(cuenta_id: str):
    rows = session.execute("""
        SELECT cuenta_id, periodo, consumo_m3, total_lecturas, lecturas_fallidas
        FROM consumo_cuenta_mes
        WHERE cuenta_id = %s
    """, (cuenta_id,))

    data = rows_to_list(rows)
    data = sorted(data, key=lambda x: x["periodo"], reverse=True)

    return data


@app.get("/api/distritos/{distrito}/consumo-hora")
def get_consumo_hora(distrito: str, periodo: str):
    distrito = normalizar_distrito(distrito)

    rows = session.execute("""
        SELECT distrito, periodo, bloque_horario, consumo_m3
        FROM consumo_distrito_hora
        WHERE distrito = %s AND periodo = %s
    """, (distrito, periodo))

    data = rows_to_list(rows)

    orden = {
        "00:00-08:00": 1,
        "08:00-16:00": 2,
        "16:00-24:00": 3
    }

    data = sorted(data, key=lambda x: orden.get(x["bloque_horario"], 99))

    return data


@app.get("/api/distritos/{distrito}/consumo-categoria")
def get_consumo_categoria(distrito: str, periodo: str):
    distrito = normalizar_distrito(distrito)

    rows = session.execute("""
        SELECT distrito, periodo, categoria, consumo_m3, total_cuentas
        FROM consumo_categoria_distrito_mes
        WHERE distrito = %s AND periodo = %s
    """, (distrito, periodo))

    data = rows_to_list(rows)

    for item in data:
        tarifa = obtener_tarifa(item.get("categoria", ""))
        consumo = float(item.get("consumo_m3", 0))
        item["tarifa_bs_m3"] = tarifa
        item["monto_facturado_bs"] = round(consumo * tarifa, 2)
        item["monto_recaudado_bs"] = round(consumo * tarifa * 0.82, 2)
        item["cartera_vencida_bs"] = round(consumo * tarifa * 0.18, 2)

    return data


@app.get("/api/dashboard/alcaldia")
def dashboard_alcaldia():
    distritos = get_distritos()
    resultados = []

    for d in distritos:
        resumen = get_resumen_distrito(d["distrito"])
        ultimo = resumen.get("ultimo")

        if ultimo:
            item = {
                **d,
                **ultimo
            }

            total_medidores = int(item.get("total_medidores", 0))
            activos = int(item.get("medidores_activos", 0))
            fallas = int(item.get("medidores_fuera_servicio", 0))
            cuentas = int(item.get("total_cuentas", 0))
            consumo = float(item.get("consumo_m3", 0))

            item["cobertura_iot"] = round((activos / total_medidores) * 100, 2) if total_medidores else 0
            item["sensores_falla_pct"] = round((fallas / total_medidores) * 100, 2) if total_medidores else 0
            item["consumo_per_capita"] = round(consumo / max(cuentas * 5, 1), 2)
            item["temperatura_c"] = 24 + int(float(item["distrito"])) % 6
            item["indice_sequia"] = round(0.35 + (int(float(item["distrito"])) % 5) * 0.10, 2)
            item["alerta"] = "CRÍTICO" if item["consumo_per_capita"] > 45 else "NORMAL"

            resultados.append(item)

    total_consumo = sum(float(x["consumo_m3"]) for x in resultados)
    total_cuentas = sum(int(x["total_cuentas"]) for x in resultados)
    total_medidores = sum(int(x["total_medidores"]) for x in resultados)
    total_activos = sum(int(x["medidores_activos"]) for x in resultados)
    total_fallas = sum(int(x["medidores_fuera_servicio"]) for x in resultados)

    return {
        "kpis": {
            "consumo_ciudad_m3": round(total_consumo, 2),
            "cuentas_conectadas": total_cuentas,
            "medidores_totales": total_medidores,
            "medidores_activos": total_activos,
            "sensores_con_fallas": total_fallas,
            "cobertura_iot": round((total_activos / total_medidores) * 100, 2) if total_medidores else 0,
            "sensores_falla_pct": round((total_fallas / total_medidores) * 100, 2) if total_medidores else 0
        },
        "distritos": resultados
    }


@app.get("/api/dashboard/gerencia/{distrito}")
def dashboard_gerencia(distrito: str, periodo: str):
    resumen = get_resumen_distrito(distrito)
    categorias = get_consumo_categoria(distrito, periodo)
    horas = get_consumo_hora(distrito, periodo)
    cuentas = get_cuentas_distrito(distrito, limit=1500)

    top_zonas = {}
    fallas_modelo = {}
    anomalias = []

    for cuenta in cuentas[:500]:
        cuenta_id = cuenta["cuenta_id"]
        consumo = get_consumo_cuenta(cuenta_id)

        consumo_periodo = None
        for item in consumo:
            if item["periodo"] == periodo:
                consumo_periodo = item
                break

        consumo_m3 = float(consumo_periodo["consumo_m3"]) if consumo_periodo else 0
        zona = cuenta.get("zona", "SIN ZONA")
        modelo = cuenta.get("modelo_medidor", "SIN MODELO")
        estado = str(cuenta.get("estado_medidor", "")).upper()

        top_zonas[zona] = top_zonas.get(zona, 0) + consumo_m3

        if modelo not in fallas_modelo:
            fallas_modelo[modelo] = {
                "modelo_medidor": modelo,
                "total": 0,
                "fallas": 0
            }

        fallas_modelo[modelo]["total"] += 1

        if estado not in ["ACTIVO", "ACTIVA", "EN SERVICIO"]:
            fallas_modelo[modelo]["fallas"] += 1

        if consumo_m3 > 45 or consumo_m3 == 0:
            anomalias.append({
                "cuenta_id": cuenta_id,
                "nombre_cliente": cuenta.get("nombre_cliente"),
                "zona": zona,
                "categoria": cuenta.get("categoria"),
                "medidor_mac": cuenta.get("medidor_mac"),
                "consumo_m3": consumo_m3,
                "anomalia": "POSIBLE FUGA / SOBRECONSUMO" if consumo_m3 > 45 else "LECTURA CERO"
            })

    top_zonas_data = [
        {
            "zona": zona,
            "consumo_m3": round(consumo, 2)
        }
        for zona, consumo in top_zonas.items()
    ]

    top_zonas_data = sorted(top_zonas_data, key=lambda x: x["consumo_m3"], reverse=True)[:10]

    fallas_data = list(fallas_modelo.values())

    return {
        "resumen": resumen,
        "categorias": categorias,
        "horas": horas,
        "top_zonas": top_zonas_data,
        "fallas_modelo": fallas_data,
        "anomalias": anomalias[:100]
    }


@app.get("/api/dashboard/contabilidad/{distrito}")
def dashboard_contabilidad(distrito: str, periodo: str):
    categorias = get_consumo_categoria(distrito, periodo)

    monto_facturado = sum(float(x["monto_facturado_bs"]) for x in categorias)
    monto_recaudado = sum(float(x["monto_recaudado_bs"]) for x in categorias)
    cartera_vencida = sum(float(x["cartera_vencida_bs"]) for x in categorias)
    total_cuentas = sum(int(x["total_cuentas"]) for x in categorias)
    ticket_promedio = monto_facturado / max(total_cuentas, 1)

    preavisos = total_cuentas
    entregados = preavisos * 0.93
    abiertos = entregados * 0.71
    pagos = abiertos * 0.54

    proyeccion = []
    for i in range(4):
        proyeccion.append({
            "mes": f"Mes +{i}",
            "ingreso_proyectado_bs": round(monto_facturado * (1.026 ** i), 2),
            "recaudacion_estimada_bs": round(monto_recaudado * (1.026 ** i), 2)
        })

    return {
        "kpis": {
            "monto_facturado_bs": round(monto_facturado, 2),
            "monto_recaudado_bs": round(monto_recaudado, 2),
            "cartera_vencida_bs": round(cartera_vencida, 2),
            "recuperacion_pct": round((monto_recaudado / monto_facturado) * 100, 2) if monto_facturado else 0,
            "ticket_promedio_bs": round(ticket_promedio, 2),
            "preavisos_emitidos": preavisos
        },
        "categorias": categorias,
        "embudo": [
            {"etapa": "Preavisos emitidos", "cantidad": round(preavisos, 2)},
            {"etapa": "Entregados", "cantidad": round(entregados, 2)},
            {"etapa": "Abiertos", "cantidad": round(abiertos, 2)},
            {"etapa": "Pagos convertidos", "cantidad": round(pagos, 2)}
        ],
        "proyeccion": proyeccion
    }


class EnvioPreavisoRequest(BaseModel):
    cuenta_id: str
    periodo: str
    whatsapp: Optional[str] = None
    sms: Optional[str] = None
    email: Optional[str] = None


@app.post("/api/preaviso/enviar")
def enviar_preaviso(request: EnvioPreavisoRequest):
    detalle = get_cuenta_detalle(request.cuenta_id)
    consumo = get_consumo_cuenta(request.cuenta_id)

    consumo_periodo = None
    for item in consumo:
        if item["periodo"] == request.periodo:
            consumo_periodo = item
            break

    if not consumo_periodo:
        raise HTTPException(status_code=404, detail="No existe consumo para ese periodo")

    pdfs = generar_pdfs_preaviso(
        detalle=detalle,
        consumo_periodo=consumo_periodo,
        historial=consumo
    )

    mensaje = calcular_mensaje_preaviso(detalle, consumo_periodo)

    destinatarios = {
        "WHATSAPP": request.whatsapp,
        "SMS": request.sms,
        "EMAIL": request.email
    }

    enviados = publicar_tres_canales(
        destinatarios=destinatarios,
        cuenta_id=request.cuenta_id,
        periodo=request.periodo,
        mensaje=mensaje,
        pdf_rollo=pdfs["rollo"],
        pdf_media_carta=pdfs["media_carta"]
    )

    return {
        "mensaje": mensaje,
        "pdfs": pdfs,
        "enviados": enviados
    }


@app.post("/api/preaviso/generar-pdf")
def generar_pdf_preaviso(request: EnvioPreavisoRequest):
    detalle = get_cuenta_detalle(request.cuenta_id)
    consumo = get_consumo_cuenta(request.cuenta_id)

    consumo_periodo = None
    for item in consumo:
        if item["periodo"] == request.periodo:
            consumo_periodo = item
            break

    if not consumo_periodo:
        raise HTTPException(status_code=404, detail="No existe consumo para ese periodo")

    pdfs = generar_pdfs_preaviso(
        detalle=detalle,
        consumo_periodo=consumo_periodo,
        historial=consumo
    )

    mensaje = calcular_mensaje_preaviso(detalle, consumo_periodo)

    return {
        "mensaje": mensaje,
        "pdfs": pdfs
    }


@app.get("/api/download")
def download_pdf(path: str):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="PDF no encontrado")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=os.path.basename(path)
    )