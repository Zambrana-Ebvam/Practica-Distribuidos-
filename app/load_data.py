import os
import re
import unicodedata
import pandas as pd
from cassandra.concurrent import execute_concurrent_with_args
from db import get_session

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
VALIDACION_DIR = os.path.join(OUTPUTS_DIR, "validacion_carga")

os.makedirs(VALIDACION_DIR, exist_ok=True)

# ==========================================================
# CONFIGURACIÓN
# None = cargar todos los registros.
# 50 = cargar 50 por CSV para prueba.
# ==========================================================
LIMITE_REGISTROS_POR_CSV = None

BATCH_SIZE_INSERT = 5000
CONCURRENCY = 150

DISTRITOS_VALIDOS = {
    "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "10", "11", "12", "13", "14", "15"
}

USOS_SUELO_VALIDOS = {
    "RESIDENCIAL",
    "COMERCIAL",
    "INDUSTRIAL",
    "EDUCATIVO",
    "SALUD",
    "MIXTO"
}

COMUNA_POR_DISTRITO = {
    "1": "TUNARI",
    "2": "TUNARI",
    "13": "TUNARI",

    "10": "ADELA ZAMUDIO",
    "11": "ADELA ZAMUDIO",
    "12": "ADELA ZAMUDIO",

    "3": "MOLLE",
    "4": "MOLLE",

    "5": "ALEJO CALATAYUD",
    "6": "VALLE HERMOSO",
    "7": "VALLE HERMOSO",
    "8": "ALEJO CALATAYUD",
    "14": "VALLE HERMOSO",

    "9": "ITOCTA",
    "15": "ITOCTA"
}

# Catálogo oficial interno zona -> distrito correcto.
# La zona se normaliza sin tildes, en mayúscula.
CATALOGO_ZONAS = {
    # Distrito 1 - Tunari
    "ARANJUEZ ALTO": {"distrito": "1", "zona_canonica": "ARANJUEZ ALTO"},
    "MESADILLA": {"distrito": "1", "zona_canonica": "MESADILLA"},

    # Distrito 2 - Tunari
    "MAYORAZGO": {"distrito": "2", "zona_canonica": "MAYORAZGO"},
    "CONDEBAMBA": {"distrito": "2", "zona_canonica": "CONDEBAMBA"},
    "TEMPORAL PAMPA": {"distrito": "2", "zona_canonica": "TEMPORAL PAMPA"},
    "QUERU QUERU ALTO": {"distrito": "2", "zona_canonica": "QUERU QUERU ALTO"},

    # Distrito 3 - Molle
    "SARCOBAMBA": {"distrito": "3", "zona_canonica": "SARCOBAMBA"},
    "CHIQUICOLLO": {"distrito": "3", "zona_canonica": "CHIQUICOLLO"},

    # Distrito 4 - Molle
    "CHIMBA": {"distrito": "4", "zona_canonica": "CHIMBA"},
    "LA CHIMBA": {"distrito": "4", "zona_canonica": "CHIMBA"},
    "VILLA BUSH": {"distrito": "4", "zona_canonica": "VILLA BUSH"},
    "VILLA BUSCH": {"distrito": "4", "zona_canonica": "VILLA BUSH"},
    "CONA CONA": {"distrito": "4", "zona_canonica": "COÑA COÑA"},
    "COÑA COÑA": {"distrito": "4", "zona_canonica": "COÑA COÑA"},

    # Distrito 5 - Alejo Calatayud
    "LA MAICA": {"distrito": "5", "zona_canonica": "LA MAICA"},
    "JAIHUAYCO": {"distrito": "5", "zona_canonica": "JAIHUAYCO"},
    "LACMA": {"distrito": "5", "zona_canonica": "LACMA"},
    "TICTI": {"distrito": "5", "zona_canonica": "TICTI"},
    "VALLE HERMOSO": {"distrito": "5", "zona_canonica": "VALLE HERMOSO"},

    # Distrito 6 - Valle Hermoso
    "ALALAY NORTE": {"distrito": "6", "zona_canonica": "ALALAY NORTE"},

    # Distrito 7 - Valle Hermoso
    "ALALAY SUD": {"distrito": "7", "zona_canonica": "ALALAY SUD"},

    # Distrito 8 - Alejo Calatayud
    "USPHA USPHA": {"distrito": "8", "zona_canonica": "USPHA USPHA"},
    "USHPA USHPA": {"distrito": "8", "zona_canonica": "USPHA USPHA"},

    # Distrito 9 - Itocta
    "TAMBORADA PUKARITA": {"distrito": "9", "zona_canonica": "TAMBORADA PUKARITA"},
    "1 DE MAYO": {"distrito": "9", "zona_canonica": "1º DE MAYO"},
    "1RO DE MAYO": {"distrito": "9", "zona_canonica": "1º DE MAYO"},
    "1º DE MAYO": {"distrito": "9", "zona_canonica": "1º DE MAYO"},
    "1° DE MAYO": {"distrito": "9", "zona_canonica": "1º DE MAYO"},
    "PUKARA GRANDE NORTE": {"distrito": "9", "zona_canonica": "PUKARA GRANDE NORTE"},
    "PUKARA GRANDE SUR": {"distrito": "9", "zona_canonica": "PUKARA GRANDE SUR"},
    "PUKARA GRANDE OESTE": {"distrito": "9", "zona_canonica": "PUKARA GRANDE OESTE"},

    # Distrito 10 - Adela Zamudio
    "NOROESTE": {"distrito": "10", "zona_canonica": "NOROESTE"},
    "NORESTE": {"distrito": "10", "zona_canonica": "NORESTE"},
    "SUDOESTE": {"distrito": "10", "zona_canonica": "SUDOESTE"},
    "SUDESTE": {"distrito": "10", "zona_canonica": "SUDESTE"},
    "SUD ESTE": {"distrito": "10", "zona_canonica": "SUDESTE"},
    "SUR ESTE": {"distrito": "10", "zona_canonica": "SUDESTE"},

    # Distrito 11 - Adela Zamudio
    "MUYURINA": {"distrito": "11", "zona_canonica": "MUYURINA"},
    "LAS CUADRAS": {"distrito": "11", "zona_canonica": "LAS CUADRAS"},

    # Distrito 12 - Adela Zamudio
    "SARCO": {"distrito": "12", "zona_canonica": "SARCO"},
    "CALA CALA": {"distrito": "12", "zona_canonica": "CALA CALA"},
    "QUERU QUERU": {"distrito": "12", "zona_canonica": "QUERU QUERU"},
    "TUPURAYA": {"distrito": "12", "zona_canonica": "TUPURAYA"},
    "HIPODROMO": {"distrito": "12", "zona_canonica": "HIPÓDROMO"},
    "HIPÓDROMO": {"distrito": "12", "zona_canonica": "HIPÓDROMO"},

    # Distrito 13 - Tunari
    "PARQUE NACIONAL TUNARI": {"distrito": "13", "zona_canonica": "PARQUE NACIONAL TUNARI"},

    # Distrito 14 - Valle Hermoso
    "DISTRITO 14": {"distrito": "14", "zona_canonica": "DISTRITO 14"},

    # Distrito 15 - Itocta
    "VALLE HERMOSO OESTE": {"distrito": "15", "zona_canonica": "VALLE HERMOSO OESTE"},
    "KHARA KHARA ARRUMANI": {"distrito": "15", "zona_canonica": "KHARA KHARA ARRUMANI"},
    "KARA KARA ARRUMANI": {"distrito": "15", "zona_canonica": "KHARA KHARA ARRUMANI"},
    "KARA KARA": {"distrito": "15", "zona_canonica": "KHARA KHARA ARRUMANI"},
    "KHARA KHARA": {"distrito": "15", "zona_canonica": "KHARA KHARA ARRUMANI"},
    "K'ARA K'ARA": {"distrito": "15", "zona_canonica": "KHARA KHARA ARRUMANI"},
    "KARA KARA KARA": {"distrito": "15", "zona_canonica": "KHARA KHARA ARRUMANI"},
}


# ==========================================================
# UTILIDADES
# ==========================================================

def normalizar_texto_base(value, default="SIN DATO"):
    if pd.isna(value):
        return default

    text = str(value).strip()

    if text == "":
        return default

    text = text.upper()
    text = text.replace("°", "º")
    text = text.replace("ª", "A")
    text = re.sub(r"\s+", " ", text)

    return text


def quitar_tildes(value):
    text = normalizar_texto_base(value)
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text


def normalizar_zona(value):
    text = normalizar_texto_base(value)

    if text == "SIN DATO":
        return text

    text = quitar_tildes(text)

    # Variantes frecuentes
    reemplazos = {
        "CONA CONA": "CONA CONA",
        "COÑA COÑA": "CONA CONA",
        "VILLA BUSCH": "VILLA BUSCH",
        "VILLA BUSH": "VILLA BUSH",
        "HIPODROMO": "HIPODROMO",
        "1° DE MAYO": "1º DE MAYO",
        "1 DE MAYO": "1 DE MAYO",
        "1RO DE MAYO": "1RO DE MAYO",
        "USPHA USPHA": "USPHA USPHA",
        "USHPA USHPA": "USHPA USHPA",
        "KARA KARA ARRUMANI": "KARA KARA ARRUMANI",
        "KHARA KHARA ARRUMANI": "KHARA KHARA ARRUMANI",
        "K'ARA K'ARA": "K'ARA K'ARA",
    }

    return reemplazos.get(text, text)


def clean_text(value, default="SIN DATO"):
    return normalizar_texto_base(value, default=default)


def clean_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default

        text = str(value).strip().replace(",", ".")
        if text == "":
            return default

        return float(text)
    except Exception:
        return default


def clean_int(value, default=0):
    try:
        if pd.isna(value):
            return default

        text = str(value).strip().replace(",", ".")
        if text == "":
            return default

        return int(float(text))
    except Exception:
        return default


def normalizar_distrito(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text == "":
        return ""

    try:
        return str(int(float(text.replace(",", "."))))
    except Exception:
        return text.upper()


def safe_date(value):
    fecha = pd.to_datetime(value, errors="coerce")

    if pd.isna(fecha):
        return pd.to_datetime("2026-04-01 00:00:00")

    return fecha


def periodo_from_fecha(fecha):
    return fecha.strftime("%Y-%m")


def bloque_horario(fecha):
    hora = fecha.hour

    if 0 <= hora < 8:
        return "00:00-08:00"

    if 8 <= hora < 16:
        return "08:00-16:00"

    return "16:00-24:00"


def get_first(row, columnas, default="SIN DATO"):
    for col in columnas:
        if col in row and not pd.isna(row.get(col)):
            value = row.get(col)
            if str(value).strip() != "":
                return value

    return default


def leer_csv_seguro(path, nombre):
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe el archivo: {path}")

    try:
        df = pd.read_csv(path, encoding="latin1", low_memory=False)
    except Exception:
        df = pd.read_csv(path, encoding="utf-8", low_memory=False)

    df.columns = [c.strip() for c in df.columns]

    print(f"{nombre}: {len(df)} filas leídas")

    if LIMITE_REGISTROS_POR_CSV is not None:
        df = df.head(LIMITE_REGISTROS_POR_CSV).copy()
        print(f"{nombre}: limitado a {len(df)} filas")

    return df


def ejecutar_lote(session, statement, datos, nombre="registros"):
    total = len(datos)

    if total == 0:
        print(f"{nombre}: 0")
        return

    insertados = 0

    for i in range(0, total, BATCH_SIZE_INSERT):
        bloque = datos[i:i + BATCH_SIZE_INSERT]

        execute_concurrent_with_args(
            session,
            statement,
            bloque,
            concurrency=CONCURRENCY
        )

        insertados += len(bloque)
        print(f"{nombre}: {insertados}/{total}")

    print(f"{nombre} finalizados: {total}")


def guardar_reporte(df, nombre_archivo):
    if df is None or df.empty:
        return

    path = os.path.join(VALIDACION_DIR, nombre_archivo)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"Reporte generado: {path}")


def validar_formato_catastro(value):
    text = str(value).strip()
    patron = r"^\d{2}-\d{2}-\d{3}-\d{4}-\d{3}$"
    return bool(re.match(patron, text))


def coordenadas_sospechosas(latitud, longitud):
    if latitud == 0.0 and longitud == 0.0:
        return True

    if not (-17.50 <= latitud <= -17.30):
        return True

    if not (-66.25 <= longitud <= -66.05):
        return True

    return False


def validar_y_corregir_zona_distrito(row):
    zona_original = clean_text(row.get("zona"))
    distrito_original = normalizar_distrito(row.get("distrito"))
    zona_key = normalizar_zona(zona_original)

    if zona_key not in CATALOGO_ZONAS:
        return {
            "valido": False,
            "corregido": False,
            "zona_original": zona_original,
            "zona_canonica": zona_original,
            "distrito_original": distrito_original,
            "distrito_corregido": distrito_original,
            "motivo": "ZONA NO ENCONTRADA EN CATALOGO"
        }

    info_zona = CATALOGO_ZONAS[zona_key]
    distrito_correcto = info_zona["distrito"]
    zona_canonica = info_zona["zona_canonica"]

    if distrito_original not in DISTRITOS_VALIDOS:
        return {
            "valido": True,
            "corregido": True,
            "zona_original": zona_original,
            "zona_canonica": zona_canonica,
            "distrito_original": distrito_original,
            "distrito_corregido": distrito_correcto,
            "motivo": "DISTRITO INVALIDO CORREGIDO POR ZONA"
        }

    if distrito_original != distrito_correcto:
        return {
            "valido": True,
            "corregido": True,
            "zona_original": zona_original,
            "zona_canonica": zona_canonica,
            "distrito_original": distrito_original,
            "distrito_corregido": distrito_correcto,
            "motivo": "DISTRITO CORREGIDO POR CATALOGO ZONA-DISTRITO"
        }

    return {
        "valido": True,
        "corregido": False,
        "zona_original": zona_original,
        "zona_canonica": zona_canonica,
        "distrito_original": distrito_original,
        "distrito_corregido": distrito_correcto,
        "motivo": "ZONA Y DISTRITO CORRECTOS"
    }


# ==========================================================
# LIMPIEZA
# ==========================================================

def limpiar_infraestructuras(infra_df):
    df = infra_df.copy()

    columnas_obligatorias = [
        "numero_catastro", "propietario", "ci", "direccion",
        "zona", "distrito", "manzano", "lote",
        "superficie_terreno", "area_construida", "uso_suelo",
        "matricula_ddrr", "valor_catastral", "impuesto_anual",
        "latitud", "longitud"
    ]

    for col in columnas_obligatorias:
        if col not in df.columns:
            raise ValueError(f"infraestructuras.csv no tiene la columna obligatoria: {col}")

    registros_validos = []
    registros_corregidos = []
    registros_observados = []

    for _, row in df.iterrows():
        validacion = validar_y_corregir_zona_distrito(row)

        numero_catastro = clean_text(row.get("numero_catastro"))
        propietario = clean_text(row.get("propietario"))
        ci = clean_text(row.get("ci"))
        direccion = clean_text(row.get("direccion"))
        manzano = clean_int(row.get("manzano"))
        lote = clean_int(row.get("lote"))
        superficie_terreno = clean_float(row.get("superficie_terreno"))
        area_construida = clean_float(row.get("area_construida"))
        uso_suelo = clean_text(row.get("uso_suelo"))
        matricula_ddrr = clean_text(row.get("matricula_ddrr"))
        valor_catastral = clean_float(row.get("valor_catastral"))
        impuesto_anual = clean_float(row.get("impuesto_anual"))
        latitud = clean_float(row.get("latitud"))
        longitud = clean_float(row.get("longitud"))

        motivos = []

        if not validacion["valido"]:
            motivos.append(validacion["motivo"])

        if numero_catastro in ["", "SIN DATO"]:
            motivos.append("NUMERO CATASTRO VACIO")

        if not validar_formato_catastro(numero_catastro):
            motivos.append("FORMATO DE NUMERO CATASTRO SOSPECHOSO")

        if propietario in ["", "SIN DATO"]:
            motivos.append("PROPIETARIO VACIO")

        if ci in ["", "SIN DATO"]:
            motivos.append("CI VACIO")

        if direccion in ["", "SIN DATO"]:
            motivos.append("DIRECCION VACIA")

        if manzano <= 0:
            motivos.append("MANZANO INVALIDO")

        if lote <= 0:
            motivos.append("LOTE INVALIDO")

        if superficie_terreno <= 0:
            motivos.append("SUPERFICIE TERRENO INVALIDA")

        if area_construida < 0:
            motivos.append("AREA CONSTRUIDA INVALIDA")

        if uso_suelo not in USOS_SUELO_VALIDOS:
            motivos.append("USO DE SUELO NO PERMITIDO")

        if matricula_ddrr in ["", "SIN DATO"]:
            motivos.append("MATRICULA DDRR VACIA")

        if valor_catastral <= 0:
            motivos.append("VALOR CATASTRAL INVALIDO")

        if impuesto_anual < 0:
            motivos.append("IMPUESTO ANUAL INVALIDO")

        coord_sospechosa = coordenadas_sospechosas(latitud, longitud)

        if coord_sospechosa:
            # No lo bloqueamos, pero lo reportamos.
            motivos.append("COORDENADAS SOSPECHOSAS")

        registro_base = row.to_dict()
        registro_base["zona_original"] = validacion["zona_original"]
        registro_base["zona_canonica"] = validacion["zona_canonica"]
        registro_base["distrito_original"] = validacion["distrito_original"]
        registro_base["distrito_corregido"] = validacion["distrito_corregido"]
        registro_base["comuna_corregida"] = COMUNA_POR_DISTRITO.get(validacion["distrito_corregido"], "SIN COMUNA")
        registro_base["motivo_validacion"] = " | ".join(motivos) if motivos else validacion["motivo"]

        # Bloqueamos solo errores críticos:
        # zona desconocida, catastro vacío, propietario vacío, zona/distrito sin catálogo.
        errores_criticos = [
            "ZONA NO ENCONTRADA EN CATALOGO",
            "NUMERO CATASTRO VACIO",
            "PROPIETARIO VACIO"
        ]

        tiene_error_critico = any(error in registro_base["motivo_validacion"] for error in errores_criticos)

        if tiene_error_critico:
            registros_observados.append(registro_base)
            continue

        registro_limpio = {
            "distrito": validacion["distrito_corregido"],
            "zona": validacion["zona_canonica"],
            "numero_catastro": numero_catastro,
            "propietario": propietario,
            "ci": ci,
            "direccion": direccion,
            "manzano": str(manzano),
            "lote": str(lote),
            "superficie_terreno": superficie_terreno,
            "area_construida": area_construida,
            "uso_suelo": uso_suelo,
            "matricula_ddrr": matricula_ddrr,
            "valor_catastral": valor_catastral,
            "impuesto_anual": impuesto_anual,
            "latitud": latitud,
            "longitud": longitud,
            "comuna": COMUNA_POR_DISTRITO.get(validacion["distrito_corregido"], "SIN COMUNA")
        }

        registros_validos.append(registro_limpio)

        if validacion["corregido"] or coord_sospechosa or motivos:
            registros_corregidos.append(registro_base)

    validos_df = pd.DataFrame(registros_validos)
    corregidos_df = pd.DataFrame(registros_corregidos)
    observados_df = pd.DataFrame(registros_observados)

    guardar_reporte(corregidos_df, "infraestructuras_corregidas_o_advertencias.csv")
    guardar_reporte(observados_df, "infraestructuras_observadas_no_insertadas.csv")

    print("Infraestructuras válidas para insertar:", len(validos_df))
    print("Infraestructuras corregidas/con advertencias:", len(corregidos_df))
    print("Infraestructuras observadas NO insertadas:", len(observados_df))

    return validos_df


def limpiar_contratos(contratos_df):
    df = contratos_df.copy()

    columnas_obligatorias = [
        "numero_contrato", "numero_catastro",
        "titular_contrato", "ci_titular", "medidor_iot"
    ]

    for col in columnas_obligatorias:
        if col not in df.columns:
            raise ValueError(f"contratos.csv no tiene la columna obligatoria: {col}")

    df["numero_contrato"] = df["numero_contrato"].apply(clean_text)
    df["numero_catastro"] = df["numero_catastro"].apply(clean_text)
    df["titular_contrato"] = df["titular_contrato"].apply(clean_text)
    df["ci_titular"] = df["ci_titular"].apply(clean_text)
    df["medidor_iot"] = df["medidor_iot"].apply(clean_text)

    observados = df[
        (df["numero_contrato"].isin(["", "SIN DATO"])) |
        (df["numero_catastro"].isin(["", "SIN DATO"])) |
        (df["titular_contrato"].isin(["", "SIN DATO"])) |
        (df["medidor_iot"].isin(["", "SIN DATO"]))
    ].copy()

    guardar_reporte(observados, "contratos_observados_no_insertados.csv")

    validos = df[
        (~df["numero_contrato"].isin(["", "SIN DATO"])) &
        (~df["numero_catastro"].isin(["", "SIN DATO"])) &
        (~df["titular_contrato"].isin(["", "SIN DATO"])) &
        (~df["medidor_iot"].isin(["", "SIN DATO"]))
    ].copy()

    print("Contratos válidos:", len(validos))
    print("Contratos observados NO insertados:", len(observados))

    return validos


def limpiar_medidores(medidores_df):
    df = medidores_df.copy()

    if "medidor_iot" not in df.columns:
        raise ValueError("medidores.csv no tiene columna obligatoria: medidor_iot")

    df["medidor_iot"] = df["medidor_iot"].apply(clean_text)

    observados = df[df["medidor_iot"].isin(["", "SIN DATO"])].copy()
    guardar_reporte(observados, "medidores_observados_no_insertados.csv")

    validos = df[~df["medidor_iot"].isin(["", "SIN DATO"])].copy()

    print("Medidores válidos:", len(validos))
    print("Medidores observados NO insertados:", len(observados))

    return validos


# ==========================================================
# CARGA A CASSANDRA
# ==========================================================

def cargar_infraestructuras(session, infra_df):
    insert_infra = session.prepare("""
        INSERT INTO infraestructuras_por_distrito (
            distrito, zona, numero_catastro, propietario, ci, direccion,
            manzano, lote, superficie_terreno, area_construida,
            uso_suelo, matricula_ddrr, valor_catastral, impuesto_anual,
            latitud, longitud
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """)

    datos = []

    for _, row in infra_df.iterrows():
        datos.append((
            clean_text(row.get("distrito")),
            clean_text(row.get("zona")),
            clean_text(row.get("numero_catastro")),
            clean_text(row.get("propietario")),
            clean_text(row.get("ci")),
            clean_text(row.get("direccion")),
            clean_text(row.get("manzano")),
            clean_text(row.get("lote")),
            clean_float(row.get("superficie_terreno")),
            clean_float(row.get("area_construida")),
            clean_text(row.get("uso_suelo")),
            clean_text(row.get("matricula_ddrr")),
            clean_float(row.get("valor_catastral")),
            clean_float(row.get("impuesto_anual")),
            clean_float(row.get("latitud")),
            clean_float(row.get("longitud"))
        ))

    ejecutar_lote(session, insert_infra, datos, nombre="Infraestructuras insertadas")


def cargar_distritos_mapa(session, infra_df):
    insert_distrito = session.prepare("""
        INSERT INTO distritos_mapa (
            distrito, lat, lon, total_zonas, total_infraestructuras
        )
        VALUES (?, ?, ?, ?, ?)
    """)

    if infra_df.empty:
        print("Distritos mapa: 0")
        return

    agrupado = infra_df.groupby("distrito").agg(
        lat=("latitud", "mean"),
        lon=("longitud", "mean"),
        total_zonas=("zona", "nunique"),
        total_infraestructuras=("numero_catastro", "count")
    ).reset_index()

    datos = []

    for _, row in agrupado.iterrows():
        datos.append((
            clean_text(row["distrito"]),
            clean_float(row["lat"]),
            clean_float(row["lon"]),
            int(row["total_zonas"]),
            int(row["total_infraestructuras"])
        ))

    ejecutar_lote(session, insert_distrito, datos, nombre="Distritos cargados para mapa")


def cargar_cuentas(session, full_df):
    insert_cuentas_distrito = session.prepare("""
        INSERT INTO cuentas_por_distrito (
            distrito, cuenta_id, numero_catastro, nombre_cliente, ci,
            categoria, subcategoria, zona, direccion, medidor_mac,
            modelo_medidor, estado_medidor, estado_contrato, tipo_servicio,
            latitud, longitud
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """)

    insert_detalle = session.prepare("""
        INSERT INTO cuenta_detalle (
            cuenta_id, numero_catastro, nombre_cliente, ci, distrito,
            zona, categoria, subcategoria, direccion, medidor_mac,
            modelo_medidor, estado_medidor, estado_contrato, tipo_servicio,
            latitud, longitud
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """)

    insert_medidor_zona = session.prepare("""
        INSERT INTO medidores_por_distrito_zona (
            distrito, zona, estado_medidor, medidor_mac, modelo_medidor, cuenta_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """)

    datos_cuentas = []
    datos_detalle = []
    datos_medidores = []

    for _, row in full_df.iterrows():
        cuenta_id = clean_text(row.get("numero_contrato"))
        numero_catastro = clean_text(row.get("numero_catastro"))
        nombre_cliente = clean_text(row.get("titular_contrato"))
        ci = clean_text(row.get("ci_titular"))
        distrito = clean_text(row.get("distrito"))
        zona = clean_text(row.get("zona"))
        categoria = clean_text(row.get("categoria"))
        subcategoria = clean_text(row.get("subcategoria"))
        direccion = clean_text(row.get("direccion"))
        medidor_mac = clean_text(row.get("medidor_iot"))

        modelo_medidor = clean_text(
            get_first(row, ["tipo_medidor_id", "modelo_medidor", "modelo", "modelo_y", "modelo_medidor_y"])
        )

        estado_medidor = clean_text(
            get_first(row, ["estado_medidor", "estado_y", "estado"])
        )

        estado_contrato = clean_text(
            get_first(row, ["estado_contrato", "estado_x"])
        )

        tipo_servicio = clean_text(row.get("tipo_servicio"))
        latitud = clean_float(row.get("latitud"))
        longitud = clean_float(row.get("longitud"))

        datos_cuentas.append((
            distrito,
            cuenta_id,
            numero_catastro,
            nombre_cliente,
            ci,
            categoria,
            subcategoria,
            zona,
            direccion,
            medidor_mac,
            modelo_medidor,
            estado_medidor,
            estado_contrato,
            tipo_servicio,
            latitud,
            longitud
        ))

        datos_detalle.append((
            cuenta_id,
            numero_catastro,
            nombre_cliente,
            ci,
            distrito,
            zona,
            categoria,
            subcategoria,
            direccion,
            medidor_mac,
            modelo_medidor,
            estado_medidor,
            estado_contrato,
            tipo_servicio,
            latitud,
            longitud
        ))

        datos_medidores.append((
            distrito,
            zona,
            estado_medidor,
            medidor_mac,
            modelo_medidor,
            cuenta_id
        ))

    ejecutar_lote(session, insert_cuentas_distrito, datos_cuentas, nombre="Cuentas por distrito insertadas")
    ejecutar_lote(session, insert_detalle, datos_detalle, nombre="Detalle de cuentas insertado")
    ejecutar_lote(session, insert_medidor_zona, datos_medidores, nombre="Medidores por zona insertados")


def cargar_lecturas(session, full_df):
    lecturas_path = os.path.join(DATA_DIR, "lecturas.csv")

    if not os.path.exists(lecturas_path):
        raise FileNotFoundError(f"No existe lecturas.csv en: {lecturas_path}")

    insert_lectura = session.prepare("""
        INSERT INTO lecturas_por_medidor_mes (
            medidor_mac, periodo, fecha, radiobase,
            lectura_anterior, lectura_actual, consumo_m3, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """)

    insert_consumo_cuenta = session.prepare("""
        INSERT INTO consumo_cuenta_mes (
            cuenta_id, periodo, consumo_m3, total_lecturas, lecturas_fallidas
        )
        VALUES (?, ?, ?, ?, ?)
    """)

    insert_consumo_distrito = session.prepare("""
        INSERT INTO consumo_distrito_mes (
            distrito, periodo, consumo_m3, total_cuentas, total_medidores,
            medidores_activos, medidores_fuera_servicio
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """)

    insert_consumo_hora = session.prepare("""
        INSERT INTO consumo_distrito_hora (
            distrito, periodo, bloque_horario, consumo_m3
        )
        VALUES (?, ?, ?, ?)
    """)

    insert_consumo_categoria = session.prepare("""
        INSERT INTO consumo_categoria_distrito_mes (
            distrito, periodo, categoria, consumo_m3, total_cuentas
        )
        VALUES (?, ?, ?, ?, ?)
    """)

    medidor_info = {}

    for _, row in full_df.iterrows():
        medidor = clean_text(row.get("medidor_iot"))

        if medidor in ["", "SIN DATO"]:
            continue

        medidor_info[medidor] = {
            "cuenta_id": clean_text(row.get("numero_contrato")),
            "distrito": clean_text(row.get("distrito")),
            "zona": clean_text(row.get("zona")),
            "categoria": clean_text(row.get("categoria")),
            "estado_medidor": clean_text(get_first(row, ["estado_medidor", "estado_y", "estado"]))
        }

    consumo_cuenta = {}
    consumo_distrito = {}
    consumo_hora = {}
    consumo_categoria = {}

    total_lecturas_leidas = 0
    total_lecturas_insertadas = 0
    total_lecturas_descartadas = 0
    lecturas_descartadas = []

    chunksize = 25000

    try:
        lector_chunks = pd.read_csv(
            lecturas_path,
            encoding="utf-8",
            chunksize=chunksize,
            low_memory=False
        )
    except Exception:
        lector_chunks = pd.read_csv(
            lecturas_path,
            encoding="latin1",
            chunksize=chunksize,
            low_memory=False
        )

    for chunk in lector_chunks:
        chunk.columns = [c.strip() for c in chunk.columns]

        if LIMITE_REGISTROS_POR_CSV is not None:
            restantes = LIMITE_REGISTROS_POR_CSV - total_lecturas_leidas

            if restantes <= 0:
                break

            chunk = chunk.head(restantes).copy()

        total_lecturas_leidas += len(chunk)

        datos_lecturas = []

        for _, row in chunk.iterrows():
            medidor = clean_text(row.get("medidor_iot"))

            if medidor not in medidor_info:
                total_lecturas_descartadas += 1
                registro = row.to_dict()
                registro["motivo"] = "LECTURA DESCARTADA: MEDIDOR SIN CONTRATO/INFRAESTRUCTURA VALIDA"
                lecturas_descartadas.append(registro)
                continue

            info = medidor_info[medidor]

            lectura_anterior = clean_float(row.get("lecturaAnterior"))
            lectura_actual = clean_float(row.get("LecturaActual"))
            consumo_m3 = max(0.0, lectura_actual - lectura_anterior)

            fecha = safe_date(row.get("fechaHoraLectura"))
            periodo = periodo_from_fecha(fecha)
            bloque = bloque_horario(fecha)

            radiobase = clean_text(row.get("radiobase"))

            status = 1
            if consumo_m3 == 0:
                status = 0

            datos_lecturas.append((
                medidor,
                periodo,
                fecha.to_pydatetime(),
                radiobase,
                lectura_anterior,
                lectura_actual,
                consumo_m3,
                status
            ))

            cuenta_id = info["cuenta_id"]
            distrito = info["distrito"]
            categoria = info["categoria"]

            key_cuenta = (cuenta_id, periodo)

            if key_cuenta not in consumo_cuenta:
                consumo_cuenta[key_cuenta] = {
                    "consumo": 0.0,
                    "total_lecturas": 0,
                    "fallidas": 0
                }

            consumo_cuenta[key_cuenta]["consumo"] += consumo_m3
            consumo_cuenta[key_cuenta]["total_lecturas"] += 1

            if status == 0:
                consumo_cuenta[key_cuenta]["fallidas"] += 1

            key_distrito = (distrito, periodo)

            if key_distrito not in consumo_distrito:
                consumo_distrito[key_distrito] = {
                    "consumo": 0.0,
                    "cuentas": set(),
                    "medidores": set(),
                    "fuera_servicio": set()
                }

            consumo_distrito[key_distrito]["consumo"] += consumo_m3
            consumo_distrito[key_distrito]["cuentas"].add(cuenta_id)
            consumo_distrito[key_distrito]["medidores"].add(medidor)

            if info["estado_medidor"] not in ["ACTIVO", "ACTIVA", "EN SERVICIO", "FUNCIONANDO"]:
                consumo_distrito[key_distrito]["fuera_servicio"].add(medidor)

            key_hora = (distrito, periodo, bloque)
            consumo_hora[key_hora] = consumo_hora.get(key_hora, 0.0) + consumo_m3

            key_categoria = (distrito, periodo, categoria)

            if key_categoria not in consumo_categoria:
                consumo_categoria[key_categoria] = {
                    "consumo": 0.0,
                    "cuentas": set()
                }

            consumo_categoria[key_categoria]["consumo"] += consumo_m3
            consumo_categoria[key_categoria]["cuentas"].add(cuenta_id)

        ejecutar_lote(session, insert_lectura, datos_lecturas, nombre="Lecturas insertadas")

        total_lecturas_insertadas += len(datos_lecturas)

        print("Lecturas leídas:", total_lecturas_leidas)
        print("Lecturas insertadas:", total_lecturas_insertadas)
        print("Lecturas descartadas:", total_lecturas_descartadas)

        if LIMITE_REGISTROS_POR_CSV is not None and total_lecturas_leidas >= LIMITE_REGISTROS_POR_CSV:
            break

    if lecturas_descartadas:
        guardar_reporte(
            pd.DataFrame(lecturas_descartadas),
            "lecturas_descartadas_medidor_sin_contrato_valido.csv"
        )

    datos_consumo_cuenta = []

    for (cuenta_id, periodo), data in consumo_cuenta.items():
        datos_consumo_cuenta.append((
            cuenta_id,
            periodo,
            round(data["consumo"], 2),
            int(data["total_lecturas"]),
            int(data["fallidas"])
        ))

    ejecutar_lote(session, insert_consumo_cuenta, datos_consumo_cuenta, nombre="Consumos por cuenta insertados")

    datos_consumo_distrito = []

    for (distrito, periodo), data in consumo_distrito.items():
        total_medidores = len(data["medidores"])
        fuera_servicio = len(data["fuera_servicio"])
        activos = total_medidores - fuera_servicio

        datos_consumo_distrito.append((
            distrito,
            periodo,
            round(data["consumo"], 2),
            len(data["cuentas"]),
            total_medidores,
            activos,
            fuera_servicio
        ))

    ejecutar_lote(session, insert_consumo_distrito, datos_consumo_distrito, nombre="Consumos por distrito insertados")

    datos_hora = []

    for (distrito, periodo, bloque), consumo in consumo_hora.items():
        datos_hora.append((
            distrito,
            periodo,
            bloque,
            round(consumo, 2)
        ))

    ejecutar_lote(session, insert_consumo_hora, datos_hora, nombre="Consumos por bloque horario insertados")

    datos_categoria = []

    for (distrito, periodo, categoria), data in consumo_categoria.items():
        datos_categoria.append((
            distrito,
            periodo,
            categoria,
            round(data["consumo"], 2),
            len(data["cuentas"])
        ))

    ejecutar_lote(session, insert_consumo_categoria, datos_categoria, nombre="Consumos por categoría insertados")


# ==========================================================
# MAIN
# ==========================================================

def main():
    session = get_session()

    infra_path = os.path.join(DATA_DIR, "infraestructuras.csv")
    contratos_path = os.path.join(DATA_DIR, "contratos.csv")
    medidores_path = os.path.join(DATA_DIR, "medidores.csv")

    print("==============================================")
    print("INICIO DE CARGA LIMPIA SEMAPA")
    print("==============================================")

    if LIMITE_REGISTROS_POR_CSV is None:
        print("Modo: cargar todos los registros")
    else:
        print(f"Modo: cargar máximo {LIMITE_REGISTROS_POR_CSV} registros por CSV")

    print("Reportes de validación:")
    print(VALIDACION_DIR)
    print("==============================================")

    infra_df = leer_csv_seguro(infra_path, "infraestructuras.csv")
    contratos_df = leer_csv_seguro(contratos_path, "contratos.csv")
    medidores_df = leer_csv_seguro(medidores_path, "medidores.csv")

    print("==============================================")
    print("LIMPIEZA Y VALIDACIÓN")
    print("==============================================")

    infra_limpia_df = limpiar_infraestructuras(infra_df)
    contratos_limpios_df = limpiar_contratos(contratos_df)
    medidores_limpios_df = limpiar_medidores(medidores_df)

    print("==============================================")
    print("VALIDACIÓN DE DISTRITOS FINALES")
    print("==============================================")

    if not infra_limpia_df.empty:
        distritos_encontrados = sorted(
            infra_limpia_df["distrito"].astype(str).unique().tolist(),
            key=lambda x: int(x) if x.isdigit() else 999
        )
    else:
        distritos_encontrados = []

    print("Distritos finales encontrados:", distritos_encontrados)

    faltantes = sorted(
        list(DISTRITOS_VALIDOS - set(distritos_encontrados)),
        key=lambda x: int(x)
    )

    if faltantes:
        print("Distritos sin registros limpios:", faltantes)
    else:
        print("Todos los distritos 1-15 tienen registros limpios.")

    print("==============================================")
    print("CRUCE DE DATOS")
    print("==============================================")

    print("Uniendo contratos con infraestructuras limpias por numero_catastro...")

    full_df = contratos_limpios_df.merge(
        infra_limpia_df,
        on="numero_catastro",
        how="inner",
        suffixes=("_contrato", "_infra")
    )

    contratos_sin_infra = contratos_limpios_df[
        ~contratos_limpios_df["numero_catastro"].isin(infra_limpia_df["numero_catastro"])
    ].copy()

    guardar_reporte(contratos_sin_infra, "contratos_sin_infraestructura_limpia.csv")

    print("Contratos con infraestructura válida:", len(full_df))
    print("Contratos sin infraestructura válida:", len(contratos_sin_infra))

    print("Uniendo medidores por medidor_iot...")

    full_df = full_df.merge(
        medidores_limpios_df,
        on="medidor_iot",
        how="left",
        suffixes=("", "_medidor")
    )

    cuentas_sin_medidor = full_df[
        full_df["medidor_iot"].isin(["", "SIN DATO"]) |
        full_df["medidor_iot"].isna()
    ].copy()

    guardar_reporte(cuentas_sin_medidor, "cuentas_sin_medidor.csv")

    print("Filas finales listas para Cassandra:", len(full_df))

    print("==============================================")
    print("CARGA A CASSANDRA")
    print("==============================================")

    print("Cargando infraestructuras limpias...")
    cargar_infraestructuras(session, infra_limpia_df)

    print("Cargando distritos para mapa...")
    cargar_distritos_mapa(session, infra_limpia_df)

    print("Cargando cuentas y medidores...")
    cargar_cuentas(session, full_df)

    print("Cargando lecturas y agregados...")
    cargar_lecturas(session, full_df)

    resumen = {
        "infraestructuras_limpias": [len(infra_limpia_df)],
        "contratos_limpios": [len(contratos_limpios_df)],
        "medidores_limpios": [len(medidores_limpios_df)],
        "filas_finales_cuentas": [len(full_df)],
        "distritos_finales": [", ".join(distritos_encontrados)],
        "distritos_faltantes": [", ".join(faltantes)]
    }

    guardar_reporte(pd.DataFrame(resumen), "resumen_carga_limpia.csv")

    print("==============================================")
    print("CARGA FINALIZADA CORRECTAMENTE")
    print("==============================================")
    print("Revisa reportes en:")
    print(VALIDACION_DIR)


if __name__ == "__main__":
    main()