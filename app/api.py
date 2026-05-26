import os
import json
from datetime import datetime
from functools import lru_cache
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from db import get_session
from pdf_preaviso import (
    generar_pdfs_preaviso,
    calcular_mensaje_preaviso,
    obtener_tarifa,
    calcular_factura_agua,
    preparar_factura_cuenta
)

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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MENSAJES_DIR = os.path.join(BASE_DIR, "outputs", "mensajes")


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
        "Ã": "Á",
        "Ã‰": "É",
        "Ã": "Í",
        "Ã“": "Ó",
        "Ãš": "Ú",

        "Â°": "°",
        "NÂ°": "N°",
        "Nº": "N°",

        "COíA": "COÑA",
        "í": "Ñ",
        "í": "Í",
        "í": "Á",

        "Ã": "í",
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


def to_float(value, default=0.0):
    try:
        return float(value or default)
    except Exception:
        return default


def to_int(value, default=0):
    try:
        return int(float(value or default))
    except Exception:
        return default


def round2(value):
    return round(to_float(value), 2)


def es_distrito_todos(value):
    text = normalizar_distrito(value).strip().upper()
    return text in ["TODOS", "TODO", "ALL", "0", "*"]


@lru_cache(maxsize=24)
def cargar_consumo_periodo_map(periodo):
    rows = session.execute(
        """
        SELECT cuenta_id, periodo, consumo_m3, total_lecturas, lecturas_fallidas
        FROM consumo_cuenta_mes
        WHERE periodo = %s ALLOW FILTERING
        """,
        (periodo,)
    )

    return {row["cuenta_id"]: row_to_dict(row) for row in rows}


@lru_cache(maxsize=24)
def cargar_lecturas_periodo_map(periodo):
    try:
        rows = session.execute(
            """
            SELECT medidor_mac, periodo, radiobase, status
            FROM lecturas_por_medidor_mes
            WHERE periodo = %s ALLOW FILTERING
            """,
            (periodo,)
        )
    except Exception:
        return None

    resumen = {}

    for row in rows:
        medidor_mac = str(row["medidor_mac"] or "").strip()

        if not medidor_mac:
            continue

        if medidor_mac not in resumen:
            resumen[medidor_mac] = {
                "total": 0,
                "app_movil": 0,
                "fallidas": 0,
                "iot": 0,
            }

        item = resumen[medidor_mac]
        radiobase = str(row["radiobase"] or "").strip().upper()
        status = to_int(row["status"])

        item["total"] += 1

        if status == 0:
            item["fallidas"] += 1

        if status == 2 or radiobase in ["APP_MOVIL", "APP MOVIL", "MOVIL", "MÓVIL", "MÃ“VIL", "2"]:
            item["app_movil"] += 1

    for item in resumen.values():
        item["iot"] = max(item["total"] - item["app_movil"] - item["fallidas"], 0)

    return resumen


def limpiar_cache_dashboards():
    cargar_consumo_periodo_map.cache_clear()
    cargar_lecturas_periodo_map.cache_clear()
    cargar_cuentas_todos.cache_clear()
    cargar_medidores_lectura.cache_clear()
    obtener_ultima_lectura_medidor.cache_clear()

TIPOS_MEDIDOR = {
    "1": {
        "marca": "Khomp",
        "modelo": "ITC 100",
        "conectividad": "LoRa",
        "aplicacion": "Agua y gas residencial e industrial",
    },
    "2": {
        "marca": "Sagemcom",
        "modelo": "Siconia WATER WM-NB",
        "conectividad": "NB-IoT",
        "aplicacion": "Redes de distribución de agua",
    },
    "3": {
        "marca": "B Meters / Arcobel",
        "modelo": "OY1320 LoRaWAN",
        "conectividad": "LoRaWAN",
        "aplicacion": "Integración con medidores mecánicos",
    },
    "4": {
        "marca": "EDMI",
        "modelo": "WP20",
        "conectividad": "NB-IoT",
        "aplicacion": "Uso residencial y servicios públicos",
    },
    "5": {
        "marca": "LAIN Holdings",
        "modelo": "Medidor 100% IoT",
        "conectividad": "No especificado",
        "aplicacion": "Agua potable residencial y comercial",
    },
}


ERRORES_IOT = {
    1: {
        "descripcion": "Automático correcto",
        "tipo": "OK",
        "afecta_sensor": False,
        "es_app_movil": False,
        "gateway_id": 1,
        "gateway_name": "Centro C4 / CAD Municipal",
        "gateway_location": "-17.3936, -66.1578",
    },
    2: {
        "descripcion": "Manual / App móvil",
        "tipo": "LECTURA_MANUAL",
        "afecta_sensor": False,
        "es_app_movil": True,
        "gateway_id": 2,
        "gateway_name": "Alcaldía Central / Plaza 14 de Septiembre",
        "gateway_location": "-17.3932, -66.1567",
    },
    3: {
        "descripcion": "Falla en la alimentación eléctrica",
        "tipo": "ERROR_SENSOR",
        "afecta_sensor": True,
        "es_app_movil": False,
        "gateway_id": 3,
        "gateway_name": "Subalcaldía Tunari",
        "gateway_location": "-17.3655, -66.1712",
    },
    4: {
        "descripcion": "Fallo en la conectividad de red",
        "tipo": "ERROR_SENSOR",
        "afecta_sensor": True,
        "es_app_movil": False,
        "gateway_id": 4,
        "gateway_name": "Subalcaldía Adela Zamudio",
        "gateway_location": "-17.3760, -66.1500",
    },
    5: {
        "descripcion": "Configuración incorrecta del sensor o gateway",
        "tipo": "ERROR_SENSOR",
        "afecta_sensor": True,
        "es_app_movil": False,
        "gateway_id": 5,
        "gateway_name": "Base aérea / zona antenas telecom",
        "gateway_location": "-17.4210, -66.1770",
    },
    6: {
        "descripcion": "Obstrucción o daño en el caudalímetro",
        "tipo": "ERROR_SENSOR",
        "afecta_sensor": True,
        "es_app_movil": False,
        "gateway_id": 6,
        "gateway_name": "Cerro San Pedro",
        "gateway_location": "-17.3600, -66.1300",
    },
    7: {
        "descripcion": "Problemas de firmware o software embebido",
        "tipo": "ERROR_SENSOR",
        "afecta_sensor": True,
        "es_app_movil": False,
        "gateway_id": 7,
        "gateway_name": "Colina San Sebastián",
        "gateway_location": "-17.4015, -66.1545",
    },
    8: {
        "descripcion": "Error en el backend o plataforma IoT",
        "tipo": "ERROR_PLATAFORMA",
        "afecta_sensor": True,
        "es_app_movil": False,
        "gateway_id": None,
        "gateway_name": "Plataforma IoT",
        "gateway_location": "",
    },
    9: {
        "descripcion": "Desincronización de reloj",
        "tipo": "ERROR_TIMESTAMP",
        "afecta_sensor": True,
        "es_app_movil": False,
        "gateway_id": None,
        "gateway_name": "Sensor IoT",
        "gateway_location": "",
    },
}


ESTADOS_MEDIDOR_ACTIVO = [
    "OPERATIVO",
    "REACONDICIONADO",
    "ACTIVO",
    "ACTIVA",
    "EN SERVICIO",
    "EN_SERVICIO",
    "INSTALADO",
    "INSTALADA",
    "FUNCIONANDO",
    "OK",
]


ESTADOS_MEDIDOR_FALLA = [
    "MANTENIMIENTO",
    "DAÑADO",
    "DAÑADA",
    "DANADO",
    "DANADA",
    "INACTIVO",
    "INACTIVA",
    "FUERA DE SERVICIO",
    "FUERA_SERVICIO",
    "DESINSTALADO",
    "DESINSTALADA",
    "BAJA",
    "DE BAJA",
]


POBLACION_DISTRITO = {
    "1": 30000,
    "2": 30026,
    "3": 25000,
    "4": 26000,
    "5": 35000,
    "6": 25000,
    "7": 24000,
    "8": 41000,
    "9": 42000,
    "10": 40000,
    "11": 39000,
    "12": 40710,
    "13": 30000,
    "14": 24000,
    "15": 50000,
}


NOMBRE_SUBALCALDIA_DISTRITO = {
    "1": "TUNARI",
    "2": "TUNARI",
    "13": "TUNARI",
    "3": "MOLLE",
    "4": "MOLLE",
    "5": "ALEJO CALATAYUD",
    "8": "ALEJO CALATAYUD",
    "6": "VALLE HERMOSO",
    "7": "VALLE HERMOSO",
    "14": "VALLE HERMOSO",
    "9": "ITOCTA",
    "15": "ITOCTA",
    "10": "ADELA ZAMUDIO",
    "11": "ADELA ZAMUDIO",
    "12": "ADELA ZAMUDIO",
}


def normalizar_estado_medidor(estado):
    estado = fix_text(estado)
    estado = str(estado or "").strip().upper()

    estado = (
        estado.replace("Á", "A")
        .replace("É", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ú", "U")
    )

    return estado


def obtener_info_tipo_medidor(tipo_medidor_id):
    tipo = str(tipo_medidor_id or "").strip()

    if tipo.endswith(".0"):
        tipo = tipo.replace(".0", "")

    return TIPOS_MEDIDOR.get(tipo, {
        "marca": "Desconocido",
        "modelo": f"Tipo {tipo}" if tipo else "Sin tipo",
        "conectividad": "Sin dato",
        "aplicacion": "Sin dato",
    })


def clasificar_estado_medidor(estado_medidor, medidor_mac=None):
    estado = normalizar_estado_medidor(estado_medidor)

    if estado in ESTADOS_MEDIDOR_ACTIVO:
        return {
            "activo": True,
            "falla": False,
            "estado_normalizado": estado,
            "clasificacion": "ACTIVO"
        }

    if estado in ESTADOS_MEDIDOR_FALLA:
        return {
            "activo": False,
            "falla": True,
            "estado_normalizado": estado,
            "clasificacion": "FALLA"
        }

    if medidor_mac and str(medidor_mac).strip() not in ["", "SIN DATO", "NONE", "NULL"]:
        return {
            "activo": True,
            "falla": False,
            "estado_normalizado": estado if estado else "SIN ESTADO",
            "clasificacion": "ACTIVO POR EXISTENCIA DE MEDIDOR"
        }

    return {
        "activo": False,
        "falla": True,
        "estado_normalizado": estado if estado else "SIN ESTADO",
        "clasificacion": "FALLA POR MEDIDOR NO IDENTIFICADO"
    }


def calcular_nivel_consumo_litros(litros_persona_dia):
    valor = float(litros_persona_dia or 0)

    if valor <= 100:
        return {
            "nivel": "Nivel 1",
            "clasificacion": "Consumo ejemplar y consciente",
            "interpretacion": "Uso altamente eficiente y sostenible.",
            "semaforo": "VERDE",
            "prioridad": 1,
        }

    if valor <= 180:
        return {
            "nivel": "Nivel 2",
            "clasificacion": "Consumo responsable",
            "interpretacion": "Uso adecuado con pequeñas oportunidades de mejora.",
            "semaforo": "VERDE",
            "prioridad": 2,
        }

    if valor <= 250:
        return {
            "nivel": "Nivel 3",
            "clasificacion": "Consumo moderado",
            "interpretacion": "Consumo aceptable, pero con señales de exceso.",
            "semaforo": "AMARILLO",
            "prioridad": 3,
        }

    if valor <= 300:
        return {
            "nivel": "Nivel 4",
            "clasificacion": "Consumo elevado",
            "interpretacion": "Cercano al límite crítico. Requiere acciones inmediatas.",
            "semaforo": "NARANJA",
            "prioridad": 4,
        }

    if valor <= 400:
        return {
            "nivel": "Nivel 5",
            "clasificacion": "Consumo inconsciente",
            "interpretacion": "Exceso evidente y desperdicio significativo.",
            "semaforo": "ROJO",
            "prioridad": 5,
        }

    return {
        "nivel": "Nivel 6",
        "clasificacion": "Consumo crítico e insostenible",
        "interpretacion": "Nivel alarmante de desperdicio.",
        "semaforo": "ROJO CRÍTICO",
        "prioridad": 6,
    }


def temperatura_simulada_por_distrito(distrito):
    distrito_num = int(float(distrito))
    temperaturas = {
        1: 24.1,
        2: 24.4,
        3: 25.2,
        4: 25.7,
        5: 26.3,
        6: 27.1,
        7: 27.4,
        8: 26.9,
        9: 28.2,
        10: 25.8,
        11: 25.4,
        12: 24.9,
        13: 23.8,
        14: 27.8,
        15: 28.5,
    }

    return temperaturas.get(distrito_num, 25.0)


def indice_sequia_simulado_por_distrito(distrito):
    distrito_num = int(float(distrito))
    indices = {
        1: 0.38,
        2: 0.42,
        3: 0.45,
        4: 0.48,
        5: 0.57,
        6: 0.62,
        7: 0.66,
        8: 0.60,
        9: 0.78,
        10: 0.46,
        11: 0.44,
        12: 0.40,
        13: 0.35,
        14: 0.70,
        15: 0.82,
    }

    return indices.get(distrito_num, 0.50)


def calcular_indice_estres_hidrico(litros_persona_dia, indice_sequia, sensores_falla_pct):
    consumo_factor = min(float(litros_persona_dia or 0) / 400, 1)
    sequia_factor = min(float(indice_sequia or 0), 1)
    falla_factor = min(float(sensores_falla_pct or 0) / 30, 1)

    indice = (consumo_factor * 0.50) + (sequia_factor * 0.35) + (falla_factor * 0.15)

    return round(indice, 3)


def clasificar_zona_critica(consumo_promedio_cuenta_m3, indice_sequia, sensores_falla_pct):
    consumo = float(consumo_promedio_cuenta_m3 or 0)
    sequia = float(indice_sequia or 0)
    fallas = float(sensores_falla_pct or 0)

    consumo_factor = min(consumo / 45, 1)
    sequia_factor = min(sequia, 1)
    falla_factor = min(fallas / 30, 1)

    indice_estres = round(
        (consumo_factor * 0.55) +
        (sequia_factor * 0.30) +
        (falla_factor * 0.15),
        3
    )

    if consumo > 45:
        return {
            "zona_critica": True,
            "criticidad": "CRÍTICA",
            "indice_estres_hidrico": indice_estres,
            "motivo": "Consumo promedio mayor a 45 m³/cuenta. Posible fuga, derroche masivo o uso intensivo."
        }

    if consumo > 30:
        return {
            "zona_critica": True,
            "criticidad": "ALTA",
            "indice_estres_hidrico": indice_estres,
            "motivo": "Consumo promedio entre 31 y 45 m³/cuenta. Alerta por sobreconsumo."
        }

    if consumo < 10:
        return {
            "zona_critica": True,
            "criticidad": "BRECHA DE ACCESO",
            "indice_estres_hidrico": indice_estres,
            "motivo": "Consumo menor a 10 m³/cuenta. Posible escasez, baja presión, cortes o falta de cobertura."
        }

    if sequia >= 0.70 and fallas >= 15:
        return {
            "zona_critica": True,
            "criticidad": "MEDIA",
            "indice_estres_hidrico": indice_estres,
            "motivo": "Sequía alta combinada con porcentaje elevado de sensores con fallas."
        }

    return {
        "zona_critica": False,
        "criticidad": "NORMAL",
        "indice_estres_hidrico": indice_estres,
        "motivo": "Consumo promedio por cuenta dentro del rango esperado."
    }

def calcular_metricas_medidores_distrito(distrito):
    cuentas = get_cuentas_distrito(distrito=distrito, limit=10000)

    medidores_unicos = {}
    medidores_por_tipo = {}
    estados_resumen = {}

    for cuenta in cuentas:
        medidor = str(cuenta.get("medidor_mac") or "").strip()

        if not medidor or medidor.upper() in ["SIN DATO", "NONE", "NULL"]:
            continue

        estado = cuenta.get("estado_medidor", "")
        tipo_id = cuenta.get("modelo_medidor", "")
        tipo_info = obtener_info_tipo_medidor(tipo_id)
        estado_info = clasificar_estado_medidor(estado, medidor)

        medidores_unicos[medidor] = {
            "medidor": medidor,
            "estado": estado_info["estado_normalizado"],
            "clasificacion": estado_info["clasificacion"],
            "tipo_id": str(tipo_id),
            "modelo": tipo_info["modelo"],
            "marca": tipo_info["marca"],
            "conectividad": tipo_info["conectividad"],
            "activo": estado_info["activo"],
            "falla": estado_info["falla"],
        }

    for _, data in medidores_unicos.items():
        modelo = data["modelo"]
        estado = data["estado"]

        if modelo not in medidores_por_tipo:
            medidores_por_tipo[modelo] = {
                "modelo_medidor": modelo,
                "marca": data["marca"],
                "conectividad": data["conectividad"],
                "total": 0,
                "activos": 0,
                "fallas": 0,
            }

        medidores_por_tipo[modelo]["total"] += 1

        if data["activo"]:
            medidores_por_tipo[modelo]["activos"] += 1
        else:
            medidores_por_tipo[modelo]["fallas"] += 1

        if estado not in estados_resumen:
            estados_resumen[estado] = {
                "estado": estado,
                "total": 0,
                "activos": 0,
                "fallas": 0,
            }

        estados_resumen[estado]["total"] += 1

        if data["activo"]:
            estados_resumen[estado]["activos"] += 1
        else:
            estados_resumen[estado]["fallas"] += 1

    total_medidores = len(medidores_unicos)
    medidores_activos = sum(1 for item in medidores_unicos.values() if item["activo"])
    sensores_con_fallas = total_medidores - medidores_activos

    cobertura_iot = round((medidores_activos / total_medidores) * 100, 2) if total_medidores else 0
    sensores_falla_pct = round((sensores_con_fallas / total_medidores) * 100, 2) if total_medidores else 0

    return {
        "total_medidores": total_medidores,
        "medidores_activos": medidores_activos,
        "sensores_con_fallas": sensores_con_fallas,
        "cobertura_iot": cobertura_iot,
        "sensores_falla_pct": sensores_falla_pct,
        "medidores_por_tipo": list(medidores_por_tipo.values()),
        "estados_resumen": list(estados_resumen.values()),
    }


def resumir_lecturas_medidor_periodo(medidor_mac, periodo):
    if not medidor_mac:
        return {
            "total": 0,
            "app_movil": 0,
            "fallidas": 0,
            "iot": 0,
        }

    rows = session.execute("""
        SELECT medidor_mac, periodo, fecha, radiobase,
               lectura_anterior, lectura_actual, consumo_m3, status
        FROM lecturas_por_medidor_mes
        WHERE medidor_mac = %s AND periodo = %s
    """, (medidor_mac, periodo))

    total = 0
    app_movil = 0
    fallidas = 0

    for row in rows:
        total += 1
        radiobase = str(row["radiobase"] or "").strip().upper()
        status = int(row["status"] or 0)

        if status == 0:
            fallidas += 1

        if status == 2 or radiobase in ["APP_MOVIL", "APP MOVIL", "MOVIL", "MÓVIL", "2"]:
            app_movil += 1

    iot = max(total - app_movil - fallidas, 0)

    return {
        "total": total,
        "app_movil": app_movil,
        "fallidas": fallidas,
        "iot": iot,
    }

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


@lru_cache(maxsize=8)
def cargar_cuentas_todos(limit_por_distrito=10000):
    resultados = []

    for item in get_distritos():
        distrito_id = normalizar_distrito(item.get("distrito"))

        rows = session.execute("""
            SELECT distrito, cuenta_id, numero_catastro, nombre_cliente, ci,
                   categoria, subcategoria, zona, direccion, medidor_mac,
                   modelo_medidor, estado_medidor, estado_contrato, tipo_servicio,
                   latitud, longitud
            FROM cuentas_por_distrito
            WHERE distrito = %s
            LIMIT %s
        """, (distrito_id, limit_por_distrito))

        resultados.extend(rows_to_list(rows))

    return list(
        {
            item.get("cuenta_id"): item
            for item in resultados
            if item.get("cuenta_id")
        }.values()
    )


@app.get("/api/distritos/{distrito}/cuentas")
def get_cuentas_distrito(
    distrito: str,
    zona: Optional[str] = None,
    limit: int = 1000
):
    distrito = normalizar_distrito(distrito)

    if es_distrito_todos(distrito):
        data = cargar_cuentas_todos(10000)[:limit]
    else:
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


def periodo_desde_fecha(fecha):
    return fecha.strftime("%Y-%m")


def bloque_horario_desde_fecha(fecha):
    hora = fecha.hour

    if hora < 8:
        return "00:00-08:00"

    if hora < 16:
        return "08:00-16:00"

    return "16:00-24:00"


def periodos_recientes(cantidad=18):
    hoy = datetime.now()
    periodos = []

    for i in range(cantidad):
        mes_total = hoy.month - i
        anio = hoy.year + ((mes_total - 1) // 12)
        mes = ((mes_total - 1) % 12) + 1
        periodos.append(f"{anio:04d}-{mes:02d}")

    return periodos


@lru_cache(maxsize=10000)
def obtener_ultima_lectura_medidor(medidor_mac):
    for periodo in periodos_recientes():
        rows = session.execute("""
            SELECT medidor_mac, periodo, fecha, radiobase,
                   lectura_anterior, lectura_actual, consumo_m3, status
            FROM lecturas_por_medidor_mes
            WHERE medidor_mac = %s AND periodo = %s
            LIMIT 1
        """, (medidor_mac, periodo))

        row = rows.one()

        if row:
            return row_to_dict(row)

    return None


def buscar_cuenta_por_medidor(medidor_mac):
    medidor_buscado = str(medidor_mac or "").strip().upper()

    if not medidor_buscado:
        return None

    for cuenta in cargar_cuentas_todos(10000):
        if str(cuenta.get("medidor_mac") or "").strip().upper() == medidor_buscado:
            return cuenta

    return None


def texto_busqueda_cuenta(cuenta):
    campos = [
        cuenta.get("cuenta_id"),
        cuenta.get("nombre_cliente"),
        cuenta.get("numero_catastro"),
        cuenta.get("zona"),
        cuenta.get("medidor_mac"),
    ]

    return " ".join(str(campo or "").upper() for campo in campos)


def preparar_item_medidor_lectura(cuenta, incluir_ultima=False):
    medidor = str(cuenta.get("medidor_mac") or "").strip()
    ultima = obtener_ultima_lectura_medidor(medidor) if incluir_ultima else None

    return {
        "cuenta_id": cuenta.get("cuenta_id"),
        "cliente": cuenta.get("nombre_cliente"),
        "ci": cuenta.get("ci"),
        "distrito": cuenta.get("distrito"),
        "zona": cuenta.get("zona"),
        "direccion": cuenta.get("direccion"),
        "categoria": cuenta.get("categoria"),
        "subcategoria": cuenta.get("subcategoria"),
        "medidor_mac": medidor,
        "estado_medidor": cuenta.get("estado_medidor"),
        "estado_contrato": cuenta.get("estado_contrato"),
        "tipo_servicio": cuenta.get("tipo_servicio"),
        "ultima_lectura": ultima,
        "lectura_sugerida_anterior": float(
            ultima.get("lectura_actual", 0)
        ) if ultima else 0,
    }


@lru_cache(maxsize=16)
def cargar_medidores_lectura(distrito="TODOS"):
    cuentas = (
        get_cuentas_distrito(normalizar_distrito(distrito), limit=10000)
        if distrito and not es_distrito_todos(distrito)
        else cargar_cuentas_todos(10000)
    )

    medidores = []

    for cuenta in cuentas:
        medidor = str(cuenta.get("medidor_mac") or "").strip()

        if not medidor or medidor.upper() in ["SIN DATO", "NONE", "NULL"]:
            continue

        item = preparar_item_medidor_lectura(cuenta, incluir_ultima=False)
        item["_texto_busqueda"] = texto_busqueda_cuenta(cuenta)
        medidores.append(item)

    return medidores


@app.get("/api/lectura-movil/medidores")
def listar_medidores_para_lectura(
    busqueda: Optional[str] = None,
    distrito: Optional[str] = None,
    limit: int = 60,
    incluir_ultima: bool = False
):
    texto = str(busqueda or "").strip().upper()
    distrito_cache = normalizar_distrito(distrito or "TODOS")
    medidores = cargar_medidores_lectura(distrito_cache)
    resultados = []

    for item in medidores:
        if len(resultados) >= limit:
            break

        if texto and texto not in item.get("_texto_busqueda", ""):
            continue

        if incluir_ultima:
            cuenta = buscar_cuenta_por_medidor(item.get("medidor_mac"))
            resultados.append(preparar_item_medidor_lectura(cuenta, incluir_ultima=True))
        else:
            resultados.append({
                key: value
                for key, value in item.items()
                if key != "_texto_busqueda"
            })

    return resultados


@app.get("/api/lectura-movil/medidores/{medidor_mac}/detalle")
def obtener_detalle_medidor_lectura(medidor_mac: str):
    detalle = buscar_cuenta_por_medidor(medidor_mac)

    if not detalle:
        raise HTTPException(status_code=404, detail="No existe contrato asociado a ese medidor")

    return preparar_item_medidor_lectura(detalle, incluir_ultima=True)


class RegistroLecturaMovilRequest(BaseModel):
    medidor_mac: str
    lectura_actual: float
    lectura_anterior: Optional[float] = None
    cuenta_id: Optional[str] = None
    fecha_hora: Optional[str] = None
    observacion: Optional[str] = None


@app.post("/api/lectura-movil/registrar")
def registrar_lectura_movil(request: RegistroLecturaMovilRequest):
    medidor = str(request.medidor_mac or "").strip()

    if not medidor:
        raise HTTPException(status_code=400, detail="Debe seleccionar un medidor IoT")

    detalle = None

    if request.cuenta_id:
        detalle = get_cuenta_detalle(request.cuenta_id)

    if not detalle:
        detalle = buscar_cuenta_por_medidor(medidor)

    if not detalle:
        raise HTTPException(status_code=404, detail="No existe contrato asociado a ese medidor")

    if request.fecha_hora:
        fecha = pd.to_datetime(request.fecha_hora, errors="coerce")
        if pd.isna(fecha):
            raise HTTPException(status_code=400, detail="Fecha/hora de lectura no valida")
        fecha = fecha.to_pydatetime()
    else:
        fecha = datetime.now()

    periodo = periodo_desde_fecha(fecha)
    ultima = obtener_ultima_lectura_medidor(medidor)
    lectura_anterior = request.lectura_anterior

    if lectura_anterior is None:
        lectura_anterior = float(ultima.get("lectura_actual", 0)) if ultima else 0.0

    lectura_actual = float(request.lectura_actual)

    if lectura_actual < float(lectura_anterior):
        raise HTTPException(
            status_code=400,
            detail="La lectura actual no puede ser menor que la lectura anterior"
        )

    consumo_m3 = round(lectura_actual - float(lectura_anterior), 2)
    status = 2
    radiobase = "APP_MOVIL"

    session.execute("""
        INSERT INTO lecturas_por_medidor_mes (
            medidor_mac, periodo, fecha, radiobase,
            lectura_anterior, lectura_actual, consumo_m3, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        medidor,
        periodo,
        fecha,
        radiobase,
        float(lectura_anterior),
        lectura_actual,
        consumo_m3,
        status
    ))

    cuenta_id = detalle.get("cuenta_id")
    consumo_actual = session.execute("""
        SELECT cuenta_id, periodo, consumo_m3, total_lecturas, lecturas_fallidas
        FROM consumo_cuenta_mes
        WHERE cuenta_id = %s AND periodo = %s
    """, (cuenta_id, periodo)).one()

    consumo_previo = float(consumo_actual["consumo_m3"]) if consumo_actual else 0.0
    total_lecturas = int(consumo_actual["total_lecturas"]) if consumo_actual else 0
    lecturas_fallidas = int(consumo_actual["lecturas_fallidas"]) if consumo_actual else 0

    session.execute("""
        INSERT INTO consumo_cuenta_mes (
            cuenta_id, periodo, consumo_m3, total_lecturas, lecturas_fallidas
        )
        VALUES (%s, %s, %s, %s, %s)
    """, (
        cuenta_id,
        periodo,
        round(consumo_previo + consumo_m3, 2),
        total_lecturas + 1,
        lecturas_fallidas
    ))

    bloque = bloque_horario_desde_fecha(fecha)
    distrito_id = normalizar_distrito(detalle.get("distrito"))
    consumo_hora = session.execute("""
        SELECT distrito, periodo, bloque_horario, consumo_m3
        FROM consumo_distrito_hora
        WHERE distrito = %s AND periodo = %s AND bloque_horario = %s
    """, (distrito_id, periodo, bloque)).one()

    consumo_hora_previo = float(consumo_hora["consumo_m3"]) if consumo_hora else 0.0

    session.execute("""
        INSERT INTO consumo_distrito_hora (
            distrito, periodo, bloque_horario, consumo_m3
        )
        VALUES (%s, %s, %s, %s)
    """, (
        distrito_id,
        periodo,
        bloque,
        round(consumo_hora_previo + consumo_m3, 2)
    ))

    limpiar_cache_dashboards()

    factura = preparar_factura_cuenta(
        detalle,
        {
            "periodo": periodo,
            "consumo_m3": round(consumo_previo + consumo_m3, 2),
            "total_lecturas": total_lecturas + 1,
            "lecturas_fallidas": lecturas_fallidas,
        }
    )

    return {
        "ok": True,
        "mensaje": "Lectura registrada correctamente por app movil",
        "cuenta_id": cuenta_id,
        "cliente": detalle.get("nombre_cliente"),
        "medidor_mac": medidor,
        "periodo": periodo,
        "fecha_hora": fecha.isoformat(),
        "lectura_anterior": round(float(lectura_anterior), 2),
        "lectura_actual": round(lectura_actual, 2),
        "consumo_m3": consumo_m3,
        "consumo_acumulado_periodo_m3": round(consumo_previo + consumo_m3, 2),
        "radiobase": radiobase,
        "observacion": request.observacion or "",
        "factura_estimacion": factura,
    }


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

    total_consumo_categoria = sum(
        float(x.get("consumo_m3", 0)) for x in data
    )

    total_cuentas_categoria = sum(
        int(x.get("total_cuentas", 0)) for x in data
    )

    for item in data:
        categoria = item.get("categoria", "")
        consumo = float(item.get("consumo_m3", 0))
        cuentas = int(item.get("total_cuentas", 0))

        item["porcentaje_consumo"] = round(
            (consumo / max(total_consumo_categoria, 1)) * 100,
            2
        )

        item["porcentaje_cuentas"] = round(
            (cuentas / max(total_cuentas_categoria, 1)) * 100,
            2
        )

        item["promedio_m3_cuenta"] = round(
            consumo / max(cuentas, 1),
            2
        )

        factura = calcular_factura_agua(
            consumo_m3=consumo,
            categoria=categoria,
            subcategoria=categoria
        )

        monto = factura["monto_bs"]

        item["codigo_tarifa"] = factura["codigo_tarifa"]
        item["tarifa_bs_m3"] = factura["codigo_tarifa"]
        item["monto_facturado_bs"] = round(monto, 2)
        item["monto_recaudado_bs"] = round(monto * 0.82, 2)
        item["cartera_vencida_bs"] = round(monto * 0.18, 2)
        item["detalle_tarifario"] = factura["detalle"]

    data = sorted(
        data,
        key=lambda x: float(x.get("consumo_m3", 0)),
        reverse=True
    )

    return data

POBLACION_DISTRITO = {
    "1": 30000,
    "2": 30026,
    "3": 25000,
    "4": 26000,
    "5": 35000,
    "6": 25000,
    "7": 24000,
    "8": 41000,
    "9": 42000,
    "10": 40000,
    "11": 39000,
    "12": 40710,
    "13": 30000,
    "14": 24000,
    "15": 50000,
}


NOMBRE_SUBALCALDIA_DISTRITO = {
    "1": "TUNARI",
    "2": "TUNARI",
    "13": "TUNARI",
    "3": "MOLLE",
    "4": "MOLLE",
    "5": "ALEJO CALATAYUD",
    "8": "ALEJO CALATAYUD",
    "6": "VALLE HERMOSO",
    "7": "VALLE HERMOSO",
    "14": "VALLE HERMOSO",
    "9": "ITOCTA",
    "15": "ITOCTA",
    "10": "ADELA ZAMUDIO",
    "11": "ADELA ZAMUDIO",
    "12": "ADELA ZAMUDIO",
}

def clasificar_equidad_territorial(consumo_promedio_cuenta_m3):
    consumo = float(consumo_promedio_cuenta_m3 or 0)

    if consumo < 10:
        return {
            "estado_equidad": "ALERTA DE ESCASEZ",
            "color_equidad": "ROJO",
            "descripcion_equidad": "Consumo muy por debajo del estándar. Posible falta de presión, cortes, baja cobertura o brecha de acceso.",
            "prioridad_equidad": 5,
        }

    if consumo <= 30:
        return {
            "estado_equidad": "EQUIDAD",
            "color_equidad": "VERDE",
            "descripcion_equidad": "Consumo dentro del rango territorial esperado.",
            "prioridad_equidad": 1,
        }

    return {
        "estado_equidad": "CONSUMO ALTO",
        "color_equidad": "NARANJA",
        "descripcion_equidad": "Consumo por encima del estándar territorial. Requiere revisión.",
        "prioridad_equidad": 4,
    }


def clasificar_sostenibilidad_hidrica(consumo_promedio_cuenta_m3):
    consumo = float(consumo_promedio_cuenta_m3 or 0)

    if consumo < 10:
        return {
            "estado_sostenibilidad": "BAJO CONSUMO / POSIBLE ESCASEZ",
            "color_sostenibilidad": "GRIS",
            "descripcion_sostenibilidad": "Consumo bajo. Puede indicar falta de acceso, cortes, baja presión o menor cobertura.",
            "alerta_sobreconsumo": False,
            "prioridad_sostenibilidad": 2,
        }

    if consumo <= 20:
        return {
            "estado_sostenibilidad": "SOSTENIBLE",
            "color_sostenibilidad": "VERDE",
            "descripcion_sostenibilidad": "Consumo eficiente y sostenible.",
            "alerta_sobreconsumo": False,
            "prioridad_sostenibilidad": 1,
        }

    if consumo <= 30:
        return {
            "estado_sostenibilidad": "NORMAL ALTO",
            "color_sostenibilidad": "AMARILLO",
            "descripcion_sostenibilidad": "Consumo aceptable, pero requiere vigilancia.",
            "alerta_sobreconsumo": False,
            "prioridad_sostenibilidad": 3,
        }

    if consumo <= 45:
        return {
            "estado_sostenibilidad": "SOBRECONSUMO",
            "color_sostenibilidad": "NARANJA",
            "descripcion_sostenibilidad": "Consumo elevado por cuenta. Puede existir derroche, uso intensivo o fuga.",
            "alerta_sobreconsumo": True,
            "prioridad_sostenibilidad": 4,
        }

    return {
        "estado_sostenibilidad": "ESTRÉS HÍDRICO CRÍTICO",
        "color_sostenibilidad": "ROJO",
        "descripcion_sostenibilidad": "Consumo muy alto por cuenta. Prioridad de inspección por posible fuga o derroche masivo.",
        "alerta_sobreconsumo": True,
        "prioridad_sostenibilidad": 5,
    }

@app.get("/api/dashboard/alcaldia")
def dashboard_alcaldia():
    distritos = get_distritos()
    resultados = []
    dias_mes = 30

    for d in distritos:
        distrito_id = normalizar_distrito(d["distrito"])
        resumen = get_resumen_distrito(distrito_id)
        ultimo = resumen.get("ultimo")

        if not ultimo:
            continue

        metricas_medidores = calcular_metricas_medidores_distrito(distrito_id)

        total_medidores = metricas_medidores["total_medidores"]
        medidores_activos = metricas_medidores["medidores_activos"]
        sensores_con_fallas = metricas_medidores["sensores_con_fallas"]
        cobertura_iot = metricas_medidores["cobertura_iot"]
        sensores_falla_pct = metricas_medidores["sensores_falla_pct"]

        total_cuentas = int(ultimo.get("total_cuentas", 0))
        consumo_m3 = float(ultimo.get("consumo_m3", 0))
        habitantes = int(POBLACION_DISTRITO.get(distrito_id, max(total_cuentas * 5, 1)))
        consumo_promedio_cuenta_m3 = round(
        consumo_m3 / max(total_cuentas, 1),
        2
        )

        equidad_info = clasificar_equidad_territorial(consumo_promedio_cuenta_m3)
        sostenibilidad_info = clasificar_sostenibilidad_hidrica(consumo_promedio_cuenta_m3)

        temperatura_c = temperatura_simulada_por_distrito(distrito_id)
        indice_sequia = indice_sequia_simulado_por_distrito(distrito_id)

        consumo_litros_persona_dia = round(
            (consumo_m3 * 1000) / max(habitantes * dias_mes, 1),
            2
        )

        nivel = calcular_nivel_consumo_litros(consumo_litros_persona_dia)

        zona_critica_info = clasificar_zona_critica(
            consumo_promedio_cuenta_m3=consumo_promedio_cuenta_m3,
            indice_sequia=indice_sequia,
            sensores_falla_pct=sensores_falla_pct
        )

        alerta_sobreconsumo = sostenibilidad_info["alerta_sobreconsumo"]

        item = {
            "distrito": distrito_id,
            "subalcaldia": NOMBRE_SUBALCALDIA_DISTRITO.get(distrito_id, "SIN SUBALCALDÍA"),
            "periodo": ultimo.get("periodo"),
            "lat": d.get("lat"),
            "lon": d.get("lon"),
            "total_zonas": d.get("total_zonas", 0),
            "total_infraestructuras": d.get("total_infraestructuras", 0),

            "habitantes": habitantes,
            "consumo_m3": round(consumo_m3, 2),
            "consumo_litros_persona_dia": consumo_litros_persona_dia,

            "nivel_consumo": nivel["nivel"],
            "clasificacion_consumo": nivel["clasificacion"],
            "interpretacion_consumo": nivel["interpretacion"],
            "semaforo_consumo": nivel["semaforo"],
            "prioridad_consumo": nivel["prioridad"],

            "temperatura_c": temperatura_c,
            "indice_sequia": indice_sequia,

            "alerta_sobreconsumo": alerta_sobreconsumo,
            "alerta": sostenibilidad_info["estado_sostenibilidad"],

            "zona_critica": zona_critica_info["zona_critica"],
            "criticidad": zona_critica_info["criticidad"],
            "indice_estres_hidrico": zona_critica_info["indice_estres_hidrico"],
            "motivo_criticidad": zona_critica_info["motivo"],

            "total_cuentas": total_cuentas,
            "total_medidores": total_medidores,
            "medidores_activos": medidores_activos,
            "medidores_iot_activos": medidores_activos,
            "sensores_con_fallas": sensores_con_fallas,
            "cobertura_iot": cobertura_iot,
            "sensores_falla_pct": sensores_falla_pct,

            "medidores_por_tipo": metricas_medidores["medidores_por_tipo"],
            "estados_medidor": metricas_medidores["estados_resumen"],

            "consumo_promedio_cuenta_m3": consumo_promedio_cuenta_m3,
            "criterio_sobreconsumo": "Consumo promedio mensual por cuenta",
            "unidad_sobreconsumo": "m³/cuenta/mes",
            "formula_sobreconsumo": "consumo_m3 / total_cuentas",

            "estado_equidad": equidad_info["estado_equidad"],
            "color_equidad": equidad_info["color_equidad"],
            "descripcion_equidad": equidad_info["descripcion_equidad"],
            "prioridad_equidad": equidad_info["prioridad_equidad"],

            "estado_sostenibilidad": sostenibilidad_info["estado_sostenibilidad"],
            "color_sostenibilidad": sostenibilidad_info["color_sostenibilidad"],
            "descripcion_sostenibilidad": sostenibilidad_info["descripcion_sostenibilidad"],
            "prioridad_sostenibilidad": sostenibilidad_info["prioridad_sostenibilidad"],
            "motivo_sobreconsumo": sostenibilidad_info["descripcion_sostenibilidad"],

        }

        resultados.append(item)

    total_consumo = sum(float(x["consumo_m3"]) for x in resultados)
    total_habitantes = sum(int(x["habitantes"]) for x in resultados)
    total_cuentas = sum(int(x["total_cuentas"]) for x in resultados)
    total_medidores = sum(int(x["total_medidores"]) for x in resultados)
    total_activos = sum(int(x["medidores_iot_activos"]) for x in resultados)
    total_fallas = sum(int(x["sensores_con_fallas"]) for x in resultados)
    total_zonas_criticas = sum(1 for x in resultados if x["zona_critica"])
    total_alertas_sobreconsumo = sum(1 for x in resultados if x["alerta_sobreconsumo"])

    consumo_litros_ciudad = round(
        (total_consumo * 1000) / max(total_habitantes * dias_mes, 1),
        2
    )

    nivel_ciudad = calcular_nivel_consumo_litros(consumo_litros_ciudad)

    distritos_ordenados_consumo = sorted(
        resultados,
        key=lambda x: x["consumo_m3"],
        reverse=True
    )

    distritos_ordenados_estres = sorted(
        resultados,
        key=lambda x: x["indice_estres_hidrico"],
        reverse=True
    )

    mapa_calor_litros = sorted(
        [
            {
                "distrito": x["distrito"],
                "subalcaldia": x["subalcaldia"],
                "lat": x["lat"],
                "lon": x["lon"],
                "consumo_m3": x["consumo_m3"],
                "litros_persona_dia": x["consumo_litros_persona_dia"],
                "nivel": x["nivel_consumo"],
                "clasificacion": x["clasificacion_consumo"],
                "semaforo": x["semaforo_consumo"],
                "criticidad": x["criticidad"],
                "indice_estres_hidrico": x["indice_estres_hidrico"],
            }
            for x in resultados
        ],
        key=lambda item: item["litros_persona_dia"],
        reverse=True
    )

    return {
        "kpis": {
            "consumo_ciudad_m3": round(total_consumo, 2),
            "habitantes_estimados": total_habitantes,
            "cuentas_conectadas": total_cuentas,

            "consumo_litros_persona_dia_ciudad": consumo_litros_ciudad,
            "nivel_consumo_ciudad": nivel_ciudad["nivel"],
            "clasificacion_consumo_ciudad": nivel_ciudad["clasificacion"],
            "interpretacion_consumo_ciudad": nivel_ciudad["interpretacion"],
            "semaforo_consumo_ciudad": nivel_ciudad["semaforo"],

            "medidores_totales": total_medidores,
            "medidores_iot_activos": total_activos,
            "sensores_con_fallas": total_fallas,
            "cobertura_iot": round((total_activos / total_medidores) * 100, 2) if total_medidores else 0,
            "sensores_falla_pct": round((total_fallas / total_medidores) * 100, 2) if total_medidores else 0,

            "zonas_criticas_estres_hidrico": total_zonas_criticas,
            "alertas_sobreconsumo": total_alertas_sobreconsumo
        },
        "obligatorios": {
            "mapa_equidad_territorial": [
                {
                    "distrito": x["distrito"],
                    "subalcaldia": x["subalcaldia"],
                    "lat": x["lat"],
                    "lon": x["lon"],
                    "consumo_m3": x["consumo_m3"],
                    "total_cuentas": x["total_cuentas"],
                    "consumo_promedio_cuenta_m3": x["consumo_promedio_cuenta_m3"],
                    "estado_equidad": x["estado_equidad"],
                    "color_equidad": x["color_equidad"],
                    "descripcion_equidad": x["descripcion_equidad"],
                }
                for x in resultados
            ],

            "mapa_sostenibilidad_hidrica": [
                {
                    "distrito": x["distrito"],
                    "subalcaldia": x["subalcaldia"],
                    "lat": x["lat"],
                    "lon": x["lon"],
                    "consumo_m3": x["consumo_m3"],
                    "total_cuentas": x["total_cuentas"],
                    "consumo_promedio_cuenta_m3": x["consumo_promedio_cuenta_m3"],
                    "estado_sostenibilidad": x["estado_sostenibilidad"],
                    "color_sostenibilidad": x["color_sostenibilidad"],
                    "descripcion_sostenibilidad": x["descripcion_sostenibilidad"],
                    "alerta_sobreconsumo": x["alerta_sobreconsumo"],
                }
                for x in resultados
            ],
            "consumo_vs_temperatura": [
                {
                    "distrito": x["distrito"],
                    "temperatura_c": x["temperatura_c"],
                    "consumo_m3": x["consumo_m3"],
                    "consumo_litros_persona_dia": x["consumo_litros_persona_dia"]
                }
                for x in resultados
            ],
            "consumo_vs_sequia": [
                {
                    "distrito": x["distrito"],
                    "indice_sequia": x["indice_sequia"],
                    "consumo_m3": x["consumo_m3"],
                    "indice_estres_hidrico": x["indice_estres_hidrico"]
                }
                for x in resultados
            ],
            "alertas_sobreconsumo": [
                x for x in resultados if x["alerta_sobreconsumo"]
            ],
            "zonas_criticas_estres_hidrico": [
                x for x in resultados if x["zona_critica"]
            ],
            "infraestructura_inteligente": [
                {
                    "distrito": x["distrito"],
                    "medidores_iot_activos": x["medidores_iot_activos"],
                    "sensores_con_fallas": x["sensores_con_fallas"],
                    "sensores_falla_pct": x["sensores_falla_pct"],
                    "cobertura_iot": x["cobertura_iot"]
                }
                for x in resultados
            ],
            "mapa_calor_litros": mapa_calor_litros
        },
        "rankings": {
            "top_consumo_distritos": distritos_ordenados_consumo[:10],
            "top_estres_hidrico": distritos_ordenados_estres[:10],
            "top_litros_persona_dia": mapa_calor_litros[:10]
        },
        "distritos": resultados
    }


@app.get("/api/dashboard/gerencia/{distrito}")
def dashboard_gerencia(distrito: str, periodo: str):
    distrito = normalizar_distrito(distrito)

    if es_distrito_todos(distrito):
        return dashboard_gerencia_todos(periodo)

    resumen = get_resumen_distrito(distrito)
    categorias = get_consumo_categoria(distrito, periodo)
    horas = get_consumo_hora(distrito, periodo)
    cuentas = get_cuentas_distrito(distrito, limit=10000)

    metricas_medidores = calcular_metricas_medidores_distrito(distrito)

    # Optimización N+1: Cargar todos los consumos del periodo en memoria de una sola vez
    consumo_map = cargar_consumo_periodo_map(periodo)
    lecturas_periodo_map = cargar_lecturas_periodo_map(periodo)

    total_consumo_acumulado = 0
    total_lecturas_registradas = 0
    total_lecturas_fallidas = 0
    lecturas_app_movil = 0
    lecturas_iot = 0

    zonas = {}
    fallas_modelo = {}
    sensores_error_detalle = {}
    anomalias = []

    for cuenta in cuentas:
        cuenta_id = cuenta.get("cuenta_id")
        zona = cuenta.get("zona") or "SIN ZONA"
        modelo_id = cuenta.get("modelo_medidor") or "SIN MODELO"
        medidor_mac = cuenta.get("medidor_mac") or ""
        estado_medidor = cuenta.get("estado_medidor") or ""

        tipo_info = obtener_info_tipo_medidor(modelo_id)
        estado_info = clasificar_estado_medidor(estado_medidor, medidor_mac)

        # Búsqueda en memoria super rápida en lugar de hacer una consulta de base de datos por cada cuenta (N+1)
        consumo_periodo = consumo_map.get(cuenta_id)

        consumo_m3 = float(consumo_periodo.get("consumo_m3", 0)) if consumo_periodo else 0
        total_lecturas = int(consumo_periodo.get("total_lecturas", 0)) if consumo_periodo else 0
        lecturas_fallidas = int(consumo_periodo.get("lecturas_fallidas", 0)) if consumo_periodo else 0
        if lecturas_periodo_map is not None:
            lecturas_medidor = lecturas_periodo_map.get(
                medidor_mac,
                {"total": 0, "app_movil": 0, "fallidas": 0, "iot": 0}
            )
        else:
            lecturas_medidor = resumir_lecturas_medidor_periodo(medidor_mac, periodo)

        lecturas_validas = max(total_lecturas - lecturas_fallidas, 0)
        lecturas_app_cuenta = int(lecturas_medidor["app_movil"])
        lecturas_iot_cuenta = max(lecturas_validas - lecturas_app_cuenta, 0)

        total_consumo_acumulado += consumo_m3
        total_lecturas_registradas += total_lecturas
        total_lecturas_fallidas += lecturas_fallidas
        lecturas_app_movil += lecturas_app_cuenta
        lecturas_iot += lecturas_iot_cuenta

        if zona not in zonas:
            zonas[zona] = {
                "zona": zona,
                "consumo_m3": 0,
                "total_cuentas": 0,
                "lecturas_registradas": 0,
                "lecturas_fallidas": 0,
                "promedio_m3_cuenta": 0,
            }

        zonas[zona]["consumo_m3"] += consumo_m3
        zonas[zona]["total_cuentas"] += 1
        zonas[zona]["lecturas_registradas"] += total_lecturas
        zonas[zona]["lecturas_fallidas"] += lecturas_fallidas

        modelo_nombre = tipo_info["modelo"]

        if modelo_nombre not in fallas_modelo:
            fallas_modelo[modelo_nombre] = {
                "modelo_medidor": modelo_nombre,
                "marca": tipo_info["marca"],
                "conectividad": tipo_info["conectividad"],
                "total": 0,
                "activos": 0,
                "sensores_con_error": 0,
                "error_pct": 0,
            }

        fallas_modelo[modelo_nombre]["total"] += 1

        if estado_info["activo"]:
            fallas_modelo[modelo_nombre]["activos"] += 1
        else:
            fallas_modelo[modelo_nombre]["sensores_con_error"] += 1

        if estado_info["falla"]:
            estado_error = estado_info["estado_normalizado"]

            if estado_error not in sensores_error_detalle:
                sensores_error_detalle[estado_error] = {
                    "estado_error": estado_error,
                    "total_sensores": 0,
                    "lecturas_asociadas": 0,
                    "consumo_m3_asociado": 0,
                }

            sensores_error_detalle[estado_error]["total_sensores"] += 1
            sensores_error_detalle[estado_error]["lecturas_asociadas"] += total_lecturas
            sensores_error_detalle[estado_error]["consumo_m3_asociado"] += consumo_m3

        if consumo_m3 > 45:
            anomalias.append({
                "cuenta_id": cuenta_id,
                "nombre_cliente": cuenta.get("nombre_cliente"),
                "zona": zona,
                "categoria": cuenta.get("categoria"),
                "medidor_mac": medidor_mac,
                "estado_medidor": estado_info["estado_normalizado"],
                "consumo_m3": round(consumo_m3, 2),
                "anomalia": "POSIBLE FUGA / SOBRECONSUMO",
                "prioridad": "ALTA",
            })

        elif consumo_m3 == 0:
            anomalias.append({
                "cuenta_id": cuenta_id,
                "nombre_cliente": cuenta.get("nombre_cliente"),
                "zona": zona,
                "categoria": cuenta.get("categoria"),
                "medidor_mac": medidor_mac,
                "estado_medidor": estado_info["estado_normalizado"],
                "consumo_m3": round(consumo_m3, 2),
                "anomalia": "LECTURA CERO",
                "prioridad": "MEDIA",
            })

        elif estado_info["falla"]:
            anomalias.append({
                "cuenta_id": cuenta_id,
                "nombre_cliente": cuenta.get("nombre_cliente"),
                "zona": zona,
                "categoria": cuenta.get("categoria"),
                "medidor_mac": medidor_mac,
                "estado_medidor": estado_info["estado_normalizado"],
                "consumo_m3": round(consumo_m3, 2),
                "anomalia": "SENSOR CON ERROR",
                "prioridad": "MEDIA",
            })

    top_zonas_data = []

    for zona, data in zonas.items():
        promedio = data["consumo_m3"] / max(data["total_cuentas"], 1)

        top_zonas_data.append({
            "zona": zona,
            "consumo_m3": round(data["consumo_m3"], 2),
            "total_cuentas": data["total_cuentas"],
            "promedio_m3_cuenta": round(promedio, 2),
            "lecturas_registradas": data["lecturas_registradas"],
            "lecturas_fallidas": data["lecturas_fallidas"],
        })

    top_zonas_data = sorted(
        top_zonas_data,
        key=lambda x: x["consumo_m3"],
        reverse=True
    )[:10]

    fallas_data = []

    for _, data in fallas_modelo.items():
        total = data["total"]
        errores = data["sensores_con_error"]

        data["error_pct"] = round((errores / total) * 100, 2) if total else 0
        fallas_data.append(data)

    fallas_data = sorted(
        fallas_data,
        key=lambda x: x["sensores_con_error"],
        reverse=True
    )

    sensores_error_data = list(sensores_error_detalle.values())

    sensores_error_data = sorted(
        sensores_error_data,
        key=lambda x: x["total_sensores"],
        reverse=True
    )

    anomalias = sorted(
        anomalias,
        key=lambda x: (
            0 if x["prioridad"] == "ALTA" else 1,
            -x["consumo_m3"]
        )
    )

    total_medidores_activos = metricas_medidores["medidores_activos"]
    sensores_con_errores = metricas_medidores["sensores_con_fallas"]
    total_medidores = metricas_medidores["total_medidores"]

    sensores_error_pct = round(
        (sensores_con_errores / total_medidores) * 100,
        2
    ) if total_medidores else 0

    return {
        "kpis": {
            "distrito": distrito,
            "periodo": periodo,

            "total_consumo_acumulado_m3": round(total_consumo_acumulado, 2),
            "total_cuentas": len(cuentas),

            "total_medidores": total_medidores,
            "total_medidores_activos": total_medidores_activos,
            "sensores_con_errores": sensores_con_errores,
            "sensores_error_pct": sensores_error_pct,

            "lecturas_registradas": total_lecturas_registradas,
            "lecturas_fallidas": total_lecturas_fallidas,
            "lecturas_iot": lecturas_iot,
            "lecturas_app_movil": lecturas_app_movil,
            "lecturas_app_movil_pct": round(
                (lecturas_app_movil / max(total_lecturas_registradas, 1)) * 100,
                2
            ),
        },

        "criterios": {
            "total_consumo_acumulado": "Suma del consumo mensual de todas las cuentas del distrito en el periodo seleccionado.",
            "top_10_zonas": "Agrupación real por zona usando consumo_cuenta_mes y cuentas_por_distrito.",
            "sensores_con_errores": "Medidores cuyo estado corresponde a mantenimiento, dañado, inactivo o fuera de servicio.",
            "medidores_activos": "Medidores operativos, reacondicionados, nuevos o en servicio.",
            "lecturas_app_movil": "Lecturas válidas asociadas a cuentas cuyo sensor tiene falla. Se interpretan como registro operativo por app móvil.",
        },

        "obligatorios": {
            "total_consumo_acumulado": {
                "valor": round(total_consumo_acumulado, 2),
                "unidad": "m³",
            },
            "top_10_zonas_mayor_demanda": top_zonas_data,
            "sensores_con_errores": sensores_error_data,
            "total_medidores_activos": {
                "valor": total_medidores_activos,
                "unidad": "medidores",
            },
            "lecturas_registradas_app_movil": {
                "valor": lecturas_app_movil,
                "unidad": "lecturas",
                "porcentaje": round(
                    (lecturas_app_movil / max(total_lecturas_registradas, 1)) * 100,
                    2
                ),
            },
        },

        "resumen": resumen,
        "categorias": categorias,
        "horas": horas,

        "top_zonas": top_zonas_data,
        "fallas_modelo": fallas_data,
        "sensores_error": sensores_error_data,
        "anomalias": anomalias[:100],
    }


def obtener_distritos_ids():
    return [
        normalizar_distrito(item.get("distrito"))
        for item in get_distritos()
        if item.get("distrito") is not None
    ]


def agrupar_sumas(items, key_name, fields):
    agrupado = {}

    for item in items:
        key = str(item.get(key_name) or "SIN DATO")

        if key not in agrupado:
            agrupado[key] = {key_name: key}

        actual = agrupado[key]

        for field in fields:
            actual[field] = round2(to_float(actual.get(field)) + to_float(item.get(field)))

    return list(agrupado.values())


def dashboard_gerencia_todos(periodo):
    distritos_ids = obtener_distritos_ids()
    dashboards = []
    errores = []

    for distrito_id in distritos_ids:
        try:
            dashboards.append({
                "distrito": distrito_id,
                "data": dashboard_gerencia(distrito_id, periodo)
            })
        except Exception as exc:
            errores.append({
                "distrito": distrito_id,
                "error": str(exc)
            })

    if not dashboards:
        raise HTTPException(
            status_code=500,
            detail="No se pudo consolidar Gerencia para todos los distritos"
        )

    datos = [item["data"] for item in dashboards if item.get("data")]
    kpis = {
        "distrito": "TODOS",
        "periodo": periodo,
        "total_consumo_acumulado_m3": 0,
        "total_cuentas": 0,
        "total_medidores": 0,
        "total_medidores_activos": 0,
        "sensores_con_errores": 0,
        "sensores_error_pct": 0,
        "lecturas_registradas": 0,
        "lecturas_fallidas": 0,
        "lecturas_iot": 0,
        "lecturas_app_movil": 0,
        "lecturas_app_movil_pct": 0,
    }

    for data in datos:
        item = data.get("kpis", {})
        kpis["total_consumo_acumulado_m3"] += to_float(item.get("total_consumo_acumulado_m3"))
        kpis["total_cuentas"] += to_int(item.get("total_cuentas"))
        kpis["total_medidores"] += to_int(item.get("total_medidores"))
        kpis["total_medidores_activos"] += to_int(item.get("total_medidores_activos"))
        kpis["sensores_con_errores"] += to_int(item.get("sensores_con_errores"))
        kpis["lecturas_registradas"] += to_int(item.get("lecturas_registradas"))
        kpis["lecturas_fallidas"] += to_int(item.get("lecturas_fallidas"))
        kpis["lecturas_iot"] += to_int(item.get("lecturas_iot"))
        kpis["lecturas_app_movil"] += to_int(item.get("lecturas_app_movil"))

    kpis["total_consumo_acumulado_m3"] = round2(kpis["total_consumo_acumulado_m3"])
    kpis["sensores_error_pct"] = round2(
        (kpis["sensores_con_errores"] / max(kpis["total_medidores"], 1)) * 100
    )
    kpis["lecturas_app_movil_pct"] = round2(
        (kpis["lecturas_app_movil"] / max(kpis["lecturas_registradas"], 1)) * 100
    )

    horas = sorted(
        agrupar_sumas(
            [item for data in datos for item in data.get("horas", [])],
            "bloque_horario",
            ["consumo_m3"]
        ),
        key=lambda item: item.get("bloque_horario", "")
    )

    categorias_base = agrupar_sumas(
        [item for data in datos for item in data.get("categorias", [])],
        "categoria",
        ["consumo_m3", "total_cuentas"]
    )

    total_consumo_categorias = sum(to_float(item.get("consumo_m3")) for item in categorias_base)
    total_cuentas_categorias = sum(to_int(item.get("total_cuentas")) for item in categorias_base)

    categorias = []
    for item in categorias_base:
        consumo = to_float(item.get("consumo_m3"))
        cuentas = to_int(item.get("total_cuentas"))
        categorias.append({
            **item,
            "porcentaje_consumo": round2((consumo / max(total_consumo_categorias, 1)) * 100),
            "porcentaje_cuentas": round2((cuentas / max(total_cuentas_categorias, 1)) * 100),
            "promedio_m3_cuenta": round2(consumo / max(cuentas, 1)),
        })

    categorias = sorted(categorias, key=lambda item: to_float(item.get("consumo_m3")), reverse=True)

    top_zonas = agrupar_sumas(
        [item for data in datos for item in data.get("top_zonas", [])],
        "zona",
        ["consumo_m3", "total_cuentas", "lecturas_registradas", "lecturas_fallidas"]
    )

    for item in top_zonas:
        item["promedio_m3_cuenta"] = round2(
            to_float(item.get("consumo_m3")) / max(to_int(item.get("total_cuentas")), 1)
        )

    top_zonas = sorted(top_zonas, key=lambda item: to_float(item.get("consumo_m3")), reverse=True)[:10]

    fallas_modelo = agrupar_sumas(
        [item for data in datos for item in data.get("fallas_modelo", [])],
        "modelo_medidor",
        ["total", "activos", "sensores_con_error"]
    )

    for item in fallas_modelo:
        item["error_pct"] = round2(
            (to_float(item.get("sensores_con_error")) / max(to_float(item.get("total")), 1)) * 100
        )

    fallas_modelo = sorted(
        fallas_modelo,
        key=lambda item: to_float(item.get("sensores_con_error")),
        reverse=True
    )

    sensores_error = agrupar_sumas(
        [item for data in datos for item in data.get("sensores_error", [])],
        "estado_error",
        ["total_sensores", "lecturas_asociadas", "consumo_m3_asociado"]
    )

    sensores_error = sorted(
        sensores_error,
        key=lambda item: to_float(item.get("total_sensores")),
        reverse=True
    )

    anomalias = [item for data in datos for item in data.get("anomalias", [])][:100]

    return {
        "kpis": kpis,
        "criterios": datos[0].get("criterios", {}) if datos else {},
        "obligatorios": {
            "total_consumo_acumulado": {
                "valor": kpis["total_consumo_acumulado_m3"],
                "unidad": "m3",
            },
            "top_10_zonas_mayor_demanda": top_zonas,
            "sensores_con_errores": sensores_error,
            "total_medidores_activos": {
                "valor": kpis["total_medidores_activos"],
                "unidad": "medidores",
            },
            "lecturas_registradas_app_movil": {
                "valor": kpis["lecturas_app_movil"],
                "unidad": "lecturas",
                "porcentaje": kpis["lecturas_app_movil_pct"],
            },
        },
        "resumen": {
            "distrito": "TODOS",
            "periodos": [],
            "ultimo": {
                "periodo": periodo,
                "consumo_m3": kpis["total_consumo_acumulado_m3"],
                "total_cuentas": kpis["total_cuentas"],
                "total_medidores": kpis["total_medidores"],
                "medidores_activos": kpis["total_medidores_activos"],
                "medidores_fuera_servicio": kpis["sensores_con_errores"],
            },
        },
        "categorias": categorias,
        "horas": horas,
        "top_zonas": top_zonas,
        "fallas_modelo": fallas_modelo,
        "sensores_error": sensores_error,
        "anomalias": anomalias,
        "errores_carga": errores,
    }


def dashboard_contabilidad_todos(periodo):
    distritos_ids = obtener_distritos_ids()
    dashboards = []
    errores = []

    for distrito_id in distritos_ids:
        try:
            dashboards.append({
                "distrito": distrito_id,
                "data": dashboard_contabilidad(distrito_id, periodo)
            })
        except Exception as exc:
            errores.append({
                "distrito": distrito_id,
                "error": str(exc)
            })

    if not dashboards:
        raise HTTPException(
            status_code=500,
            detail="No se pudo consolidar Contabilidad para todos los distritos"
        )

    datos = [item["data"] for item in dashboards if item.get("data")]
    evidencias_periodo = [
        item for item in leer_evidencias_preaviso()
        if item.get("periodo") == periodo
    ]
    cuentas_con_preaviso_real = {
        item.get("cuenta_id") for item in evidencias_periodo if item.get("cuenta_id")
    }

    kpis = {
        "distrito": "TODOS",
        "periodo": periodo,
        "total_cuentas": 0,
        "cuentas_pagadas": 0,
        "cuentas_morosas": 0,
        "consumo_total_m3": 0,
        "monto_facturado_bs": 0,
        "monto_recaudado_bs": 0,
        "cartera_vencida_bs": 0,
        "monto_preavisos_mensual_bs": 0,
        "recuperacion_pct": 0,
        "mora_pct": 0,
        "ticket_promedio_bs": 0,
        "preavisos_emitidos": 0,
        "preavisos_enviados_rabbitmq": len(cuentas_con_preaviso_real),
        "mensajes_enviados_rabbitmq": len(evidencias_periodo),
        "monto_preavisos_enviados_bs": 0,
        "mejor_canal_cobranza": "SIN DATOS",
    }

    for data in datos:
        item = data.get("kpis", {})
        kpis["total_cuentas"] += to_int(item.get("total_cuentas"))
        kpis["cuentas_pagadas"] += to_int(item.get("cuentas_pagadas"))
        kpis["cuentas_morosas"] += to_int(item.get("cuentas_morosas"))
        kpis["consumo_total_m3"] += to_float(item.get("consumo_total_m3"))
        kpis["monto_facturado_bs"] += to_float(item.get("monto_facturado_bs"))
        kpis["monto_recaudado_bs"] += to_float(item.get("monto_recaudado_bs"))
        kpis["cartera_vencida_bs"] += to_float(item.get("cartera_vencida_bs"))
        kpis["monto_preavisos_mensual_bs"] += to_float(item.get("monto_preavisos_mensual_bs"))
        kpis["monto_preavisos_enviados_bs"] += to_float(item.get("monto_preavisos_enviados_bs"))
        kpis["preavisos_emitidos"] += to_int(item.get("preavisos_emitidos"))

    for field in [
        "consumo_total_m3",
        "monto_facturado_bs",
        "monto_recaudado_bs",
        "cartera_vencida_bs",
        "monto_preavisos_mensual_bs",
        "monto_preavisos_enviados_bs",
    ]:
        kpis[field] = round2(kpis[field])

    kpis["recuperacion_pct"] = round2(
        (kpis["monto_recaudado_bs"] / max(kpis["monto_facturado_bs"], 1)) * 100
    )
    kpis["mora_pct"] = round2(
        (kpis["cartera_vencida_bs"] / max(kpis["monto_facturado_bs"], 1)) * 100
    )
    kpis["ticket_promedio_bs"] = round2(
        kpis["monto_facturado_bs"] / max(kpis["total_cuentas"], 1)
    )

    facturacion_tarifa = agrupar_sumas(
        [item for data in datos for item in data.get("facturacion_tarifa", [])],
        "codigo_tarifa",
        ["cuentas", "consumo_m3", "monto_facturado_bs", "monto_recaudado_bs", "cartera_vencida_bs"]
    )

    for item in facturacion_tarifa:
        item["ticket_promedio_bs"] = round2(
            to_float(item.get("monto_facturado_bs")) / max(to_int(item.get("cuentas")), 1)
        )

    facturacion_tarifa = sorted(
        facturacion_tarifa,
        key=lambda item: to_float(item.get("monto_facturado_bs")),
        reverse=True
    )

    facturacion_categoria = agrupar_sumas(
        [item for data in datos for item in data.get("facturacion_categoria", [])],
        "categoria",
        ["cuentas", "consumo_m3", "monto_facturado_bs", "monto_recaudado_bs", "cartera_vencida_bs"]
    )

    for item in facturacion_categoria:
        item["ticket_promedio_bs"] = round2(
            to_float(item.get("monto_facturado_bs")) / max(to_int(item.get("cuentas")), 1)
        )

    facturacion_categoria = sorted(
        facturacion_categoria,
        key=lambda item: to_float(item.get("monto_facturado_bs")),
        reverse=True
    )

    facturacion_zona_top10 = agrupar_sumas(
        [item for data in datos for item in data.get("facturacion_zona_top10", [])],
        "zona",
        ["cuentas", "consumo_m3", "monto_facturado_bs", "cartera_vencida_bs"]
    )

    facturacion_zona_top10 = sorted(
        facturacion_zona_top10,
        key=lambda item: to_float(item.get("cartera_vencida_bs")),
        reverse=True
    )[:10]

    efectividad_canales = agrupar_sumas(
        [item for data in datos for item in data.get("efectividad_canales", [])],
        "canal",
        ["preavisos_emitidos", "monto_cartera_bs", "recuperacion_estimada_bs"]
    )

    for item in efectividad_canales:
        item["conversion_pct"] = round2(
            (to_float(item.get("recuperacion_estimada_bs")) / max(to_float(item.get("monto_cartera_bs")), 1)) * 100
        )

    efectividad_canales = sorted(
        efectividad_canales,
        key=lambda item: to_float(item.get("recuperacion_estimada_bs")),
        reverse=True
    )

    if efectividad_canales:
        kpis["mejor_canal_cobranza"] = efectividad_canales[0].get("canal")

    grandes_deudores = sorted(
        [item for data in datos for item in data.get("grandes_deudores", [])],
        key=lambda item: to_float(item.get("cartera_vencida_bs")),
        reverse=True
    )[:50]

    detalle_cuentas = [item for data in datos for item in data.get("detalle_cuentas", [])][:200]

    facturacion_por_distrito = []
    for item in dashboards:
        distrito_id = item.get("distrito")
        data = item.get("data") or {}
        district_kpis = data.get("kpis", {})
        facturacion_por_distrito.append({
            "distrito": distrito_id,
            "monto_facturado_bs": round2(district_kpis.get("monto_facturado_bs")),
            "monto_recaudado_bs": round2(district_kpis.get("monto_recaudado_bs")),
            "cartera_vencida_bs": round2(district_kpis.get("cartera_vencida_bs")),
        })

    proyeccion = []
    for i in range(4):
        proyeccion.append({
            "mes": f"Mes +{i}",
            "ingreso_proyectado_bs": round2(kpis["monto_facturado_bs"] * (1.026 ** i)),
            "recaudacion_estimada_bs": round2(kpis["monto_recaudado_bs"] * (1.026 ** i)),
            "cartera_estimada_bs": round2(kpis["cartera_vencida_bs"] * (1.026 ** i)),
        })

    return {
        "kpis": kpis,
        "criterios": datos[0].get("criterios", {}) if datos else {},
        "obligatorios": {
            "monto_facturado_mensual": {
                "valor": kpis["monto_facturado_bs"],
                "unidad": "Bs",
            },
            "facturacion_por_distrito": facturacion_por_distrito,
            "cartera_vencida": {
                "valor": kpis["cartera_vencida_bs"],
                "unidad": "Bs",
                "mora_pct": kpis["mora_pct"],
            },
            "preavisos_emitidos": {
                "valor": kpis["preavisos_emitidos"],
                "unidad": "preavisos",
            },
            "preavisos_enviados_rabbitmq": {
                "valor": kpis["preavisos_enviados_rabbitmq"],
                "unidad": "preavisos consumidos por worker",
                "mensajes_por_canal": kpis["mensajes_enviados_rabbitmq"],
            },
            "monto_preavisos_mensual": {
                "valor": kpis["monto_preavisos_mensual_bs"],
                "unidad": "Bs",
                "descripcion": "Monto mensual de deuda incluido en preavisos emitidos",
            },
            "monto_preavisos_enviados": {
                "valor": kpis["monto_preavisos_enviados_bs"],
                "unidad": "Bs",
                "descripcion": "Monto asociado a cuentas con evidencia real en RabbitMQ",
            },
            "efectividad_por_canal": efectividad_canales,
            "canal_que_cobra_mejor": kpis["mejor_canal_cobranza"],
        },
        "facturacion_categoria": facturacion_categoria,
        "facturacion_tarifa": facturacion_tarifa,
        "facturacion_zona_top10": facturacion_zona_top10,
        "efectividad_canales": efectividad_canales,
        "grandes_deudores": grandes_deudores,
        "detalle_cuentas": detalle_cuentas,
        "proyeccion": proyeccion,
        "errores_carga": errores,
    }


ESTADOS_CONTRATO_MOROSOS = [
    "MOROSO",
    "CORTADO",
    "SUSPENDIDO",
    "SUSPENDIDA",
    "BAJA",
    "INACTIVO",
    "INACTIVA",
]


def normalizar_estado_contrato(estado):
    estado = fix_text(estado)
    estado = str(estado or "").strip().upper()

    estado = (
        estado.replace("Á", "A")
        .replace("É", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ú", "U")
    )

    return estado


def clasificar_estado_pago_contable(estado_contrato):
    estado = normalizar_estado_contrato(estado_contrato)

    if estado in ESTADOS_CONTRATO_MOROSOS:
        return {
            "estado_pago": "PENDIENTE",
            "es_moroso": True,
            "debe_emitir_preaviso": True,
        }

    return {
        "estado_pago": "PAGADO",
        "es_moroso": False,
        "debe_emitir_preaviso": False,
    }


def seleccionar_canal_preaviso(cuenta_id):
    cuenta_texto = str(cuenta_id or "")
    valor = sum(ord(c) for c in cuenta_texto)

    canales = ["WHATSAPP", "SMS", "EMAIL"]
    return canales[valor % len(canales)]


def inicializar_resumen_canal():
    return {
        "SMS": {
            "canal": "SMS",
            "preavisos_emitidos": 0,
            "monto_cartera_bs": 0,
            "recuperacion_estimada_bs": 0,
            "conversion_pct": 38,
        },
        "WHATSAPP": {
            "canal": "WHATSAPP",
            "preavisos_emitidos": 0,
            "monto_cartera_bs": 0,
            "recuperacion_estimada_bs": 0,
            "conversion_pct": 54,
        },
        "EMAIL": {
            "canal": "EMAIL",
            "preavisos_emitidos": 0,
            "monto_cartera_bs": 0,
            "recuperacion_estimada_bs": 0,
            "conversion_pct": 31,
        },
    }

ESTADOS_CONTRATO_MOROSOS = [
    "MOROSO",
    "CORTADO",
    "SUSPENDIDO",
    "SUSPENDIDA",
    "BAJA",
    "INACTIVO",
    "INACTIVA",
]


def normalizar_estado_contrato(estado):
    estado = fix_text(estado)
    estado = str(estado or "").strip().upper()

    estado = (
        estado.replace("Á", "A")
        .replace("É", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ú", "U")
    )

    return estado


def clasificar_estado_pago_contable(estado_contrato):
    estado = normalizar_estado_contrato(estado_contrato)

    if estado in ESTADOS_CONTRATO_MOROSOS:
        return {
            "estado_pago": "PENDIENTE",
            "es_moroso": True,
            "debe_emitir_preaviso": True,
        }

    return {
        "estado_pago": "PAGADO",
        "es_moroso": False,
        "debe_emitir_preaviso": False,
    }


def seleccionar_canal_preaviso(cuenta_id):
    cuenta_texto = str(cuenta_id or "")
    valor = sum(ord(c) for c in cuenta_texto)

    canales = ["WHATSAPP", "SMS", "EMAIL"]
    return canales[valor % len(canales)]


def inicializar_resumen_canal():
    return {
        "SMS": {
            "canal": "SMS",
            "preavisos_emitidos": 0,
            "monto_cartera_bs": 0,
            "recuperacion_estimada_bs": 0,
            "conversion_pct": 38,
        },
        "WHATSAPP": {
            "canal": "WHATSAPP",
            "preavisos_emitidos": 0,
            "monto_cartera_bs": 0,
            "recuperacion_estimada_bs": 0,
            "conversion_pct": 54,
        },
        "EMAIL": {
            "canal": "EMAIL",
            "preavisos_emitidos": 0,
            "monto_cartera_bs": 0,
            "recuperacion_estimada_bs": 0,
            "conversion_pct": 31,
        },
    }


def construir_resumen_facturacion(detalle, consumo_periodo):
    factura = preparar_factura_cuenta(detalle, consumo_periodo)
    estado_contrato = detalle.get("estado_contrato") or "SIN ESTADO"
    estado_pago_info = clasificar_estado_pago_contable(estado_contrato)
    monto_facturado = float(factura["monto_facturado_bs"])
    monto_pendiente = monto_facturado if estado_pago_info["es_moroso"] else 0.0

    return {
        **factura,
        "estado_contrato": estado_contrato,
        "estado_pago": estado_pago_info["estado_pago"],
        "estado_deuda": "DEBE" if estado_pago_info["es_moroso"] else "NO DEBE",
        "monto_pendiente_bs": round(monto_pendiente, 2),
        "debe_emitir_preaviso": estado_pago_info["debe_emitir_preaviso"],
    }


def buscar_consumo_periodo_o_vacio(cuenta_id, periodo, consumo):
    for item in consumo:
        if item.get("periodo") == periodo:
            return item, False

    return {
        "cuenta_id": cuenta_id,
        "periodo": periodo,
        "consumo_m3": 0,
        "total_lecturas": 0,
        "lecturas_fallidas": 0,
        "sin_consumo_periodo": True,
    }, True


def leer_evidencias_preaviso(limit=1000):
    if not os.path.isdir(MENSAJES_DIR):
        return []

    archivos = [
        os.path.join(MENSAJES_DIR, nombre)
        for nombre in os.listdir(MENSAJES_DIR)
        if nombre.lower().endswith(".json")
    ]

    archivos = sorted(
        archivos,
        key=lambda path: os.path.getmtime(path),
        reverse=True
    )[: max(1, min(limit, 5000))]

    mensajes = []

    for path in archivos:
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except Exception:
            continue

        data["archivo"] = os.path.basename(path)
        data["ruta"] = path
        data["recibido_en"] = datetime.fromtimestamp(
            os.path.getmtime(path)
        ).isoformat()
        mensajes.append(data)

    return mensajes


@app.get("/api/dashboard/contabilidad/{distrito}")
def dashboard_contabilidad(distrito: str, periodo: str):
    distrito = normalizar_distrito(distrito)

    if es_distrito_todos(distrito):
        return dashboard_contabilidad_todos(periodo)

    cuentas = get_cuentas_distrito(distrito, limit=10000)

    # Optimización N+1: Cargar todos los consumos del periodo en memoria de una sola vez
    consumo_map = cargar_consumo_periodo_map(periodo)

    monto_facturado = 0
    monto_recaudado = 0
    cartera_vencida = 0
    total_consumo_m3 = 0

    total_cuentas = 0
    cuentas_pagadas = 0
    cuentas_morosas = 0
    preavisos_emitidos = 0

    facturacion_categoria = {}
    facturacion_tarifa = {}
    facturacion_zona = {}
    grandes_deudores = []
    detalle_cuentas = []

    canales = inicializar_resumen_canal()
    evidencias_periodo = [
        item for item in leer_evidencias_preaviso()
        if item.get("periodo") == periodo
    ]
    cuentas_con_preaviso_real = {
        item.get("cuenta_id") for item in evidencias_periodo if item.get("cuenta_id")
    }
    mensajes_por_cuenta = {}
    for item in evidencias_periodo:
        cuenta_evidencia = item.get("cuenta_id")
        if cuenta_evidencia:
            mensajes_por_cuenta[cuenta_evidencia] = mensajes_por_cuenta.get(cuenta_evidencia, 0) + 1

    mensajes_enviados_rabbitmq = 0
    monto_preavisos_enviados = 0
    cuentas_con_preaviso_real_distrito = set()

    for cuenta in cuentas:
        cuenta_id = cuenta.get("cuenta_id")
        categoria = cuenta.get("categoria") or "SIN CATEGORIA"
        subcategoria = cuenta.get("subcategoria") or categoria
        zona = cuenta.get("zona") or "SIN ZONA"
        estado_contrato = cuenta.get("estado_contrato") or "SIN ESTADO"

        # Búsqueda en memoria super rápida en lugar de hacer una consulta de base de datos por cada cuenta (N+1)
        consumo_periodo = consumo_map.get(cuenta_id)

        if not consumo_periodo:
            continue

        consumo_m3 = float(consumo_periodo.get("consumo_m3", 0))

        factura = calcular_factura_agua(
            consumo_m3=consumo_m3,
            categoria=categoria,
            subcategoria=subcategoria
        )

        codigo_tarifa = factura["codigo_tarifa"]
        monto_bs = float(factura["monto_bs"])
        detalle_tarifario = factura["detalle"]

        estado_pago_info = clasificar_estado_pago_contable(estado_contrato)

        es_moroso = estado_pago_info["es_moroso"]
        estado_pago = estado_pago_info["estado_pago"]
        debe_emitir_preaviso = estado_pago_info["debe_emitir_preaviso"]

        if es_moroso:
            monto_pagado = 0
            monto_pendiente = monto_bs
            cuentas_morosas += 1
        else:
            monto_pagado = monto_bs
            monto_pendiente = 0
            cuentas_pagadas += 1

        if debe_emitir_preaviso:
            preavisos_emitidos += 1

            canal = seleccionar_canal_preaviso(cuenta_id)
            canales[canal]["preavisos_emitidos"] += 1
            canales[canal]["monto_cartera_bs"] += monto_pendiente

            tasa_conversion = canales[canal]["conversion_pct"] / 100
            canales[canal]["recuperacion_estimada_bs"] += monto_pendiente * tasa_conversion

        if cuenta_id in cuentas_con_preaviso_real:
            monto_preavisos_enviados += monto_pendiente
            cuentas_con_preaviso_real_distrito.add(cuenta_id)
            mensajes_enviados_rabbitmq += mensajes_por_cuenta.get(cuenta_id, 0)

        total_cuentas += 1
        total_consumo_m3 += consumo_m3
        monto_facturado += monto_bs
        monto_recaudado += monto_pagado
        cartera_vencida += monto_pendiente

        if categoria not in facturacion_categoria:
            facturacion_categoria[categoria] = {
                "categoria": categoria,
                "cuentas": 0,
                "consumo_m3": 0,
                "monto_facturado_bs": 0,
                "monto_recaudado_bs": 0,
                "cartera_vencida_bs": 0,
            }

        facturacion_categoria[categoria]["cuentas"] += 1
        facturacion_categoria[categoria]["consumo_m3"] += consumo_m3
        facturacion_categoria[categoria]["monto_facturado_bs"] += monto_bs
        facturacion_categoria[categoria]["monto_recaudado_bs"] += monto_pagado
        facturacion_categoria[categoria]["cartera_vencida_bs"] += monto_pendiente

        if codigo_tarifa not in facturacion_tarifa:
            facturacion_tarifa[codigo_tarifa] = {
                "codigo_tarifa": codigo_tarifa,
                "categoria": categoria,
                "subcategoria": subcategoria,
                "cuentas": 0,
                "consumo_m3": 0,
                "monto_facturado_bs": 0,
                "monto_recaudado_bs": 0,
                "cartera_vencida_bs": 0,
            }

        facturacion_tarifa[codigo_tarifa]["cuentas"] += 1
        facturacion_tarifa[codigo_tarifa]["consumo_m3"] += consumo_m3
        facturacion_tarifa[codigo_tarifa]["monto_facturado_bs"] += monto_bs
        facturacion_tarifa[codigo_tarifa]["monto_recaudado_bs"] += monto_pagado
        facturacion_tarifa[codigo_tarifa]["cartera_vencida_bs"] += monto_pendiente

        if zona not in facturacion_zona:
            facturacion_zona[zona] = {
                "zona": zona,
                "cuentas": 0,
                "consumo_m3": 0,
                "monto_facturado_bs": 0,
                "cartera_vencida_bs": 0,
            }

        facturacion_zona[zona]["cuentas"] += 1
        facturacion_zona[zona]["consumo_m3"] += consumo_m3
        facturacion_zona[zona]["monto_facturado_bs"] += monto_bs
        facturacion_zona[zona]["cartera_vencida_bs"] += monto_pendiente

        cuenta_detalle = {
            "cuenta_id": cuenta_id,
            "cliente": cuenta.get("nombre_cliente"),
            "ci": cuenta.get("ci"),
            "zona": zona,
            "direccion": cuenta.get("direccion"),
            "categoria": categoria,
            "subcategoria": subcategoria,
            "codigo_tarifa": codigo_tarifa,
            "estado_contrato": estado_contrato,
            "estado_pago": estado_pago,
            "consumo_m3": round(consumo_m3, 2),
            "monto_facturado_bs": round(monto_bs, 2),
            "monto_recaudado_bs": round(monto_pagado, 2),
            "cartera_vencida_bs": round(monto_pendiente, 2),
            "debe_emitir_preaviso": debe_emitir_preaviso,
            "detalle_tarifario": detalle_tarifario,
        }

        detalle_cuentas.append(cuenta_detalle)

        if monto_pendiente > 0:
            grandes_deudores.append(cuenta_detalle)

    facturacion_categoria_data = []
    for _, item in facturacion_categoria.items():
        item["consumo_m3"] = round(item["consumo_m3"], 2)
        item["monto_facturado_bs"] = round(item["monto_facturado_bs"], 2)
        item["monto_recaudado_bs"] = round(item["monto_recaudado_bs"], 2)
        item["cartera_vencida_bs"] = round(item["cartera_vencida_bs"], 2)
        item["ticket_promedio_bs"] = round(
            item["monto_facturado_bs"] / max(item["cuentas"], 1),
            2
        )
        facturacion_categoria_data.append(item)

    facturacion_categoria_data = sorted(
        facturacion_categoria_data,
        key=lambda x: x["monto_facturado_bs"],
        reverse=True
    )

    facturacion_tarifa_data = []
    for _, item in facturacion_tarifa.items():
        item["consumo_m3"] = round(item["consumo_m3"], 2)
        item["monto_facturado_bs"] = round(item["monto_facturado_bs"], 2)
        item["monto_recaudado_bs"] = round(item["monto_recaudado_bs"], 2)
        item["cartera_vencida_bs"] = round(item["cartera_vencida_bs"], 2)
        item["ticket_promedio_bs"] = round(
            item["monto_facturado_bs"] / max(item["cuentas"], 1),
            2
        )
        facturacion_tarifa_data.append(item)

    facturacion_tarifa_data = sorted(
        facturacion_tarifa_data,
        key=lambda x: x["monto_facturado_bs"],
        reverse=True
    )

    facturacion_zona_data = []
    for _, item in facturacion_zona.items():
        item["consumo_m3"] = round(item["consumo_m3"], 2)
        item["monto_facturado_bs"] = round(item["monto_facturado_bs"], 2)
        item["cartera_vencida_bs"] = round(item["cartera_vencida_bs"], 2)
        facturacion_zona_data.append(item)

    facturacion_zona_data = sorted(
        facturacion_zona_data,
        key=lambda x: x["monto_facturado_bs"],
        reverse=True
    )[:10]

    canales_data = []
    for _, canal in canales.items():
        canal["monto_cartera_bs"] = round(canal["monto_cartera_bs"], 2)
        canal["recuperacion_estimada_bs"] = round(canal["recuperacion_estimada_bs"], 2)
        canales_data.append(canal)

    canales_data = sorted(
        canales_data,
        key=lambda x: x["recuperacion_estimada_bs"],
        reverse=True
    )

    mejor_canal = canales_data[0]["canal"] if canales_data else "SIN DATOS"

    grandes_deudores = sorted(
        grandes_deudores,
        key=lambda x: x["cartera_vencida_bs"],
        reverse=True
    )[:50]

    ticket_promedio = monto_facturado / max(total_cuentas, 1)
    recuperacion_pct = (monto_recaudado / monto_facturado) * 100 if monto_facturado else 0
    mora_pct = (cartera_vencida / monto_facturado) * 100 if monto_facturado else 0
    monto_preavisos_mensual = cartera_vencida

    proyeccion = []
    for i in range(4):
        proyeccion.append({
            "mes": f"Mes +{i}",
            "ingreso_proyectado_bs": round(monto_facturado * (1.026 ** i), 2),
            "recaudacion_estimada_bs": round(monto_recaudado * (1.026 ** i), 2),
            "cartera_estimada_bs": round(cartera_vencida * (1.026 ** i), 2),
        })

    return {
        "kpis": {
            "distrito": distrito,
            "periodo": periodo,
            "total_cuentas": total_cuentas,
            "cuentas_pagadas": cuentas_pagadas,
            "cuentas_morosas": cuentas_morosas,

            "consumo_total_m3": round(total_consumo_m3, 2),
            "monto_facturado_bs": round(monto_facturado, 2),
            "monto_recaudado_bs": round(monto_recaudado, 2),
            "cartera_vencida_bs": round(cartera_vencida, 2),
            "monto_preavisos_mensual_bs": round(monto_preavisos_mensual, 2),
            "recuperacion_pct": round(recuperacion_pct, 2),
            "mora_pct": round(mora_pct, 2),
            "ticket_promedio_bs": round(ticket_promedio, 2),

            "preavisos_emitidos": preavisos_emitidos,
            "preavisos_enviados_rabbitmq": len(cuentas_con_preaviso_real_distrito),
            "mensajes_enviados_rabbitmq": mensajes_enviados_rabbitmq,
            "monto_preavisos_enviados_bs": round(monto_preavisos_enviados, 2),
            "mejor_canal_cobranza": mejor_canal,
        },

        "criterios": {
            "facturacion": "La factura se calcula cuenta por cuenta usando categoria, subcategoria y consumo mensual.",
            "tarifa": "Se aplica la tabla escalonada por código tarifario R1, R2, R3, R4, C, CE, I, P o S.",
            "mora": "Se considera cartera vencida cuando el estado del contrato es MOROSO, CORTADO o SUSPENDIDO.",
            "preavisos": "Los preavisos se emiten solo a cuentas con cartera vencida.",
            "canales": "La efectividad por canal se simula de forma determinística para el MVP porque la base actual no contiene trazabilidad real de aperturas y pagos por canal.",
        },

        "obligatorios": {
            "monto_facturado_mensual": {
                "valor": round(monto_facturado, 2),
                "unidad": "Bs",
            },
            "facturacion_por_distrito": [
                {
                    "distrito": distrito,
                    "monto_facturado_bs": round(monto_facturado, 2),
                    "monto_recaudado_bs": round(monto_recaudado, 2),
                    "cartera_vencida_bs": round(cartera_vencida, 2),
                }
            ],
            "cartera_vencida": {
                "valor": round(cartera_vencida, 2),
                "unidad": "Bs",
                "mora_pct": round(mora_pct, 2),
            },
            "preavisos_emitidos": {
                "valor": preavisos_emitidos,
                "unidad": "preavisos",
            },
            "preavisos_enviados_rabbitmq": {
                "valor": len(cuentas_con_preaviso_real_distrito),
                "unidad": "preavisos consumidos por worker",
                "mensajes_por_canal": mensajes_enviados_rabbitmq,
            },
            "monto_preavisos_mensual": {
                "valor": round(monto_preavisos_mensual, 2),
                "unidad": "Bs",
                "descripcion": "Monto mensual de deuda incluido en preavisos emitidos",
            },
            "monto_preavisos_enviados": {
                "valor": round(monto_preavisos_enviados, 2),
                "unidad": "Bs",
                "descripcion": "Monto asociado a cuentas con evidencia real en RabbitMQ",
            },
            "efectividad_por_canal": canales_data,
            "canal_que_cobra_mejor": mejor_canal,
        },

        "facturacion_categoria": facturacion_categoria_data,
        "facturacion_tarifa": facturacion_tarifa_data,
        "facturacion_zona_top10": facturacion_zona_data,
        "efectividad_canales": canales_data,
        "grandes_deudores": grandes_deudores,
        "detalle_cuentas": detalle_cuentas[:200],
        "proyeccion": proyeccion,
    }

@app.get("/api/totem/cuenta/{cuenta_id}")
def consultar_cuenta_totem(cuenta_id: str, periodo: Optional[str] = None):
    # Obtener detalles de la cuenta de forma segura
    try:
        detalle = get_cuenta_detalle(cuenta_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(
            status_code=404,
            detail="La cuenta ingresada no existe en el sistema. Verifique el número de cuenta."
        )

    if detalle is None:
        raise HTTPException(
            status_code=404,
            detail="La cuenta ingresada no existe en el sistema. Verifique el número de cuenta."
        )

    # Obtener historial de consumos
    consumo = get_consumo_cuenta(cuenta_id)

    # Si el periodo es inválido o no se envía, buscamos el consumo más reciente registrado
    consumo_periodo = None
    periodo_invalido = (not periodo) or (periodo in ["undefined", "null", ""])

    if periodo_invalido:
        if consumo:
            consumo_periodo = consumo[0] # Al estar ordenado por periodo DESC, el primero es el más nuevo
            periodo_mostrado = consumo_periodo.get("periodo")
        else:
            periodo_mostrado = "S/D"
    else:
        # Buscar el periodo solicitado
        for item in consumo:
            if item.get("periodo") == periodo:
                consumo_periodo = item
                break
        
        # Si no existe consumo para el periodo solicitado pero hay historial, usamos el más nuevo
        if not consumo_periodo:
            if consumo:
                consumo_periodo = consumo[0]
                periodo_mostrado = consumo_periodo.get("periodo")
            else:
                periodo_mostrado = periodo
        else:
            periodo_mostrado = periodo

    # Valores de consumo
    if consumo_periodo:
        consumo_m3 = float(consumo_periodo.get("consumo_m3", 0))
    else:
        consumo_m3 = 0.0

    categoria = detalle.get("categoria") or "SIN CATEGORIA"
    subcategoria = detalle.get("subcategoria") or categoria
    estado_contrato = detalle.get("estado_contrato") or "SIN ESTADO"

    resumen_factura = construir_resumen_facturacion(
        detalle,
        consumo_periodo or {
            "periodo": periodo_mostrado,
            "consumo_m3": consumo_m3,
            "total_lecturas": 0,
            "lecturas_fallidas": 0,
        },
    )

    # Mensaje personalizado e informativo de deuda
    if resumen_factura["estado_deuda"] == "DEBE":
        estado_deuda = "DEBE"
        monto_pendiente = float(resumen_factura["monto_pendiente_bs"])
        mensaje = f"Su cuenta registra un saldo pendiente de {monto_pendiente:.2f} Bs para el periodo {periodo_mostrado}. Por favor, regularice su situación en ventanilla."
    else:
        estado_deuda = "NO DEBE"
        monto_pendiente = 0.0
        mensaje = f"Felicidades. Su cuenta se encuentra al día (PAGADO) para el periodo {periodo_mostrado}. Gracias por ser un usuario responsable."

    return {
        "cuenta_id": cuenta_id,
        "periodo": periodo_mostrado,

        "cliente": detalle.get("nombre_cliente"),
        "ci": detalle.get("ci"),
        "direccion": detalle.get("direccion"),
        "zona": detalle.get("zona"),
        "distrito": detalle.get("distrito"),

        "categoria": categoria,
        "subcategoria": subcategoria,
        "codigo_tarifa": resumen_factura["codigo_tarifa"],

        "medidor": detalle.get("medidor_mac"),
        "estado_medidor": detalle.get("estado_medidor"),
        "estado_contrato": estado_contrato,

        "consumo_m3": round(consumo_m3, 2),
        "monto_facturado_bs": round(float(resumen_factura["monto_facturado_bs"]), 2),
        "monto_pendiente_bs": round(monto_pendiente, 2),

        "estado_deuda": estado_deuda,
        "debe_emitir_preaviso": resumen_factura["debe_emitir_preaviso"],
        "mensaje": mensaje,

        "detalle_tarifario": resumen_factura["detalle_tarifario"]
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

    consumo_periodo, sin_consumo_periodo = buscar_consumo_periodo_o_vacio(
        request.cuenta_id,
        request.periodo,
        consumo
    )

    pdfs = generar_pdfs_preaviso(
        detalle=detalle,
        consumo_periodo=consumo_periodo,
        historial=consumo
    )

    mensaje = calcular_mensaje_preaviso(detalle, consumo_periodo)
    if sin_consumo_periodo:
        mensaje = (
            f"{mensaje} No existe lectura registrada para este periodo; "
            "el preaviso se genera con consumo 0 m3 y cargo fijo segun tarifa."
        )
    resumen_factura = construir_resumen_facturacion(detalle, consumo_periodo)

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
        "monto_facturado_bs": resumen_factura["monto_facturado_bs"],
        "monto_pendiente_bs": resumen_factura["monto_pendiente_bs"],
        "codigo_tarifa": resumen_factura["codigo_tarifa"],
        "detalle_tarifario": resumen_factura["detalle_tarifario"],
        "sin_consumo_periodo": sin_consumo_periodo,
        "pdfs": pdfs,
        "enviados": enviados
    }


@app.post("/api/preaviso/generar-pdf")
def generar_pdf_preaviso(request: EnvioPreavisoRequest):
    detalle = get_cuenta_detalle(request.cuenta_id)
    consumo = get_consumo_cuenta(request.cuenta_id)

    consumo_periodo, sin_consumo_periodo = buscar_consumo_periodo_o_vacio(
        request.cuenta_id,
        request.periodo,
        consumo
    )

    pdfs = generar_pdfs_preaviso(
        detalle=detalle,
        consumo_periodo=consumo_periodo,
        historial=consumo
    )

    mensaje = calcular_mensaje_preaviso(detalle, consumo_periodo)
    if sin_consumo_periodo:
        mensaje = (
            f"{mensaje} No existe lectura registrada para este periodo; "
            "el preaviso se genera con consumo 0 m3 y cargo fijo segun tarifa."
        )
    resumen_factura = construir_resumen_facturacion(detalle, consumo_periodo)

    return {
        "mensaje": mensaje,
        "monto_facturado_bs": resumen_factura["monto_facturado_bs"],
        "monto_pendiente_bs": resumen_factura["monto_pendiente_bs"],
        "codigo_tarifa": resumen_factura["codigo_tarifa"],
        "detalle_tarifario": resumen_factura["detalle_tarifario"],
        "sin_consumo_periodo": sin_consumo_periodo,
        "pdfs": pdfs
    }


@app.get("/api/preaviso/evidencias")
def listar_evidencias_preaviso(limit: int = 30):
    mensajes = [
        {
            "archivo": data.get("archivo"),
            "ruta": data.get("ruta"),
            "recibido_en": data.get("recibido_en"),
            "canal": data.get("canal"),
            "destinatario": data.get("destinatario"),
            "cuenta_id": data.get("cuenta_id"),
            "periodo": data.get("periodo"),
            "mensaje": data.get("mensaje"),
            "pdf_rollo": data.get("pdf_rollo"),
            "pdf_media_carta": data.get("pdf_media_carta"),
            "fecha_envio": data.get("fecha_envio"),
        }
        for data in leer_evidencias_preaviso(limit)
    ]

    return {
        "directorio": MENSAJES_DIR,
        "total": len(mensajes),
        "mensajes": mensajes,
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
