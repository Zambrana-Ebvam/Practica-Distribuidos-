import os
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
    calcular_factura_agua
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

    resumen = get_resumen_distrito(distrito)
    categorias = get_consumo_categoria(distrito, periodo)
    horas = get_consumo_hora(distrito, periodo)
    cuentas = get_cuentas_distrito(distrito, limit=10000)

    metricas_medidores = calcular_metricas_medidores_distrito(distrito)

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

        consumo = get_consumo_cuenta(cuenta_id)

        consumo_periodo = None
        for item in consumo:
            if item.get("periodo") == periodo:
                consumo_periodo = item
                break

        consumo_m3 = float(consumo_periodo.get("consumo_m3", 0)) if consumo_periodo else 0
        total_lecturas = int(consumo_periodo.get("total_lecturas", 0)) if consumo_periodo else 0
        lecturas_fallidas = int(consumo_periodo.get("lecturas_fallidas", 0)) if consumo_periodo else 0

        lecturas_validas = max(total_lecturas - lecturas_fallidas, 0)

        total_consumo_acumulado += consumo_m3
        total_lecturas_registradas += total_lecturas
        total_lecturas_fallidas += lecturas_fallidas

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

            if lecturas_validas > 0:
                lecturas_app_movil += lecturas_validas
            elif consumo_m3 > 0:
                lecturas_app_movil += 1

        else:
            lecturas_iot += lecturas_validas

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
@app.get("/api/dashboard/contabilidad/{distrito}")
def dashboard_contabilidad(distrito: str, periodo: str):
    distrito = normalizar_distrito(distrito)

    cuentas = get_cuentas_distrito(distrito, limit=10000)

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

    for cuenta in cuentas:
        cuenta_id = cuenta.get("cuenta_id")
        categoria = cuenta.get("categoria") or "SIN CATEGORIA"
        subcategoria = cuenta.get("subcategoria") or categoria
        zona = cuenta.get("zona") or "SIN ZONA"
        estado_contrato = cuenta.get("estado_contrato") or "SIN ESTADO"

        consumo_historial = get_consumo_cuenta(cuenta_id)

        consumo_periodo = None
        for item in consumo_historial:
            if item.get("periodo") == periodo:
                consumo_periodo = item
                break

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
            "recuperacion_pct": round(recuperacion_pct, 2),
            "mora_pct": round(mora_pct, 2),
            "ticket_promedio_bs": round(ticket_promedio, 2),

            "preavisos_emitidos": preavisos_emitidos,
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
def consultar_cuenta_totem(cuenta_id: str, periodo: str):
    detalle = get_cuenta_detalle(cuenta_id)
    consumo = get_consumo_cuenta(cuenta_id)

    consumo_periodo = None
    for item in consumo:
        if item.get("periodo") == periodo:
            consumo_periodo = item
            break

    if not consumo_periodo:
        raise HTTPException(
            status_code=404,
            detail="No existe consumo registrado para esa cuenta en el periodo seleccionado"
        )

    consumo_m3 = float(consumo_periodo.get("consumo_m3", 0))

    categoria = detalle.get("categoria") or "SIN CATEGORIA"
    subcategoria = detalle.get("subcategoria") or categoria
    estado_contrato = detalle.get("estado_contrato") or "SIN ESTADO"

    factura = calcular_factura_agua(
        consumo_m3=consumo_m3,
        categoria=categoria,
        subcategoria=subcategoria
    )

    estado_pago_info = clasificar_estado_pago_contable(estado_contrato)

    if estado_pago_info["es_moroso"]:
        estado_deuda = "DEBE"
        monto_pendiente = float(factura["monto_bs"])
        mensaje = "La cuenta tiene deuda pendiente. Se recomienda regularizar el pago."
    else:
        estado_deuda = "NO DEBE"
        monto_pendiente = 0
        mensaje = "La cuenta no registra deuda pendiente para el periodo consultado."

    return {
        "cuenta_id": cuenta_id,
        "periodo": periodo,

        "cliente": detalle.get("nombre_cliente"),
        "ci": detalle.get("ci"),
        "direccion": detalle.get("direccion"),
        "zona": detalle.get("zona"),
        "distrito": detalle.get("distrito"),

        "categoria": categoria,
        "subcategoria": subcategoria,
        "codigo_tarifa": factura["codigo_tarifa"],

        "medidor": detalle.get("medidor_mac"),
        "estado_medidor": detalle.get("estado_medidor"),
        "estado_contrato": estado_contrato,

        "consumo_m3": round(consumo_m3, 2),
        "monto_facturado_bs": round(float(factura["monto_bs"]), 2),
        "monto_pendiente_bs": round(monto_pendiente, 2),

        "estado_deuda": estado_deuda,
        "debe_emitir_preaviso": estado_pago_info["debe_emitir_preaviso"],
        "mensaje": mensaje,

        "detalle_tarifario": factura["detalle"]
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