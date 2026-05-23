import os
import pandas as pd
from cassandra.concurrent import execute_concurrent_with_args
from db import get_session

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


def clean_text(value, default="SIN DATO"):
    if pd.isna(value):
        return default
    text = str(value).strip()
    if text == "":
        return default
    return text.upper()


def clean_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(str(value).replace(",", "."))
    except Exception:
        return default


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
        distrito = clean_text(row.get("distrito"))
        zona = clean_text(row.get("zona"))
        numero_catastro = clean_text(row.get("numero_catastro"))
        propietario = clean_text(row.get("propietario"))
        ci = clean_text(row.get("ci"))
        direccion = clean_text(row.get("direccion"))
        manzano = clean_text(row.get("manzano"))
        lote = clean_text(row.get("lote"))
        superficie_terreno = clean_float(row.get("superficie_terreno"))
        area_construida = clean_float(row.get("area_construida"))
        uso_suelo = clean_text(row.get("uso_suelo"))
        matricula_ddrr = clean_text(row.get("matricula_ddrr"))
        valor_catastral = clean_float(row.get("valor_catastral"))
        impuesto_anual = clean_float(row.get("impuesto_anual"))
        latitud = clean_float(row.get("latitud"))
        longitud = clean_float(row.get("longitud"))

        datos.append((
            distrito,
            zona,
            numero_catastro,
            propietario,
            ci,
            direccion,
            manzano,
            lote,
            superficie_terreno,
            area_construida,
            uso_suelo,
            matricula_ddrr,
            valor_catastral,
            impuesto_anual,
            latitud,
            longitud
        ))

    execute_concurrent_with_args(session, insert_infra, datos, concurrency=150)
    print(f"Infraestructuras cargadas: {len(datos)}")


def cargar_distritos_mapa(session, infra_df):
    insert_distrito = session.prepare("""
        INSERT INTO distritos_mapa (
            distrito, lat, lon, total_zonas, total_infraestructuras
        )
        VALUES (?, ?, ?, ?, ?)
    """)

    datos = []

    agrupado = infra_df.groupby("distrito").agg(
        lat=("latitud", "mean"),
        lon=("longitud", "mean"),
        total_zonas=("zona", "nunique"),
        total_infraestructuras=("numero_catastro", "count")
    ).reset_index()

    for _, row in agrupado.iterrows():
        datos.append((
            clean_text(row["distrito"]),
            clean_float(row["lat"]),
            clean_float(row["lon"]),
            int(row["total_zonas"]),
            int(row["total_infraestructuras"])
        ))

    execute_concurrent_with_args(session, insert_distrito, datos, concurrency=50)
    print(f"Distritos cargados para mapa: {len(datos)}")


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
        modelo_medidor = clean_text(row.get("tipo_medidor_id"))
        estado_medidor = clean_text(row.get("estado"))
        estado_contrato = clean_text(row.get("estado_contrato"))
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

    execute_concurrent_with_args(session, insert_cuentas_distrito, datos_cuentas, concurrency=150)
    execute_concurrent_with_args(session, insert_detalle, datos_detalle, concurrency=150)
    execute_concurrent_with_args(session, insert_medidor_zona, datos_medidores, concurrency=150)

    print(f"Cuentas cargadas: {len(datos_cuentas)}")
    print(f"Medidores por zona cargados: {len(datos_medidores)}")


def cargar_lecturas(session, full_df):
    lecturas_path = os.path.join(DATA_DIR, "lecturas.csv")

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
        medidor_info[medidor] = {
            "cuenta_id": clean_text(row.get("numero_contrato")),
            "distrito": clean_text(row.get("distrito")),
            "zona": clean_text(row.get("zona")),
            "categoria": clean_text(row.get("categoria")),
            "estado_medidor": clean_text(row.get("estado"))
        }

    consumo_cuenta = {}
    consumo_distrito = {}
    consumo_hora = {}
    consumo_categoria = {}

    total_lecturas = 0
    chunksize = 25000

    for chunk in pd.read_csv(lecturas_path, encoding="utf-8", chunksize=chunksize, low_memory=False):
        chunk.columns = [c.strip() for c in chunk.columns]

        datos_lecturas = []

        for _, row in chunk.iterrows():
            medidor = clean_text(row.get("medidor_iot"))

            if medidor not in medidor_info:
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

            if info["estado_medidor"] not in ["ACTIVO", "ACTIVA", "EN SERVICIO"]:
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

        execute_concurrent_with_args(session, insert_lectura, datos_lecturas, concurrency=150)

        total_lecturas += len(datos_lecturas)
        print(f"Lecturas cargadas: {total_lecturas}")

    datos_consumo_cuenta = []

    for (cuenta_id, periodo), data in consumo_cuenta.items():
        datos_consumo_cuenta.append((
            cuenta_id,
            periodo,
            round(data["consumo"], 2),
            int(data["total_lecturas"]),
            int(data["fallidas"])
        ))

    execute_concurrent_with_args(session, insert_consumo_cuenta, datos_consumo_cuenta, concurrency=150)
    print(f"Consumos por cuenta cargados: {len(datos_consumo_cuenta)}")

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

    execute_concurrent_with_args(session, insert_consumo_distrito, datos_consumo_distrito, concurrency=150)
    print(f"Consumos por distrito cargados: {len(datos_consumo_distrito)}")

    datos_hora = []

    for (distrito, periodo, bloque), consumo in consumo_hora.items():
        datos_hora.append((
            distrito,
            periodo,
            bloque,
            round(consumo, 2)
        ))

    execute_concurrent_with_args(session, insert_consumo_hora, datos_hora, concurrency=150)
    print(f"Consumos por bloque horario cargados: {len(datos_hora)}")

    datos_categoria = []

    for (distrito, periodo, categoria), data in consumo_categoria.items():
        datos_categoria.append((
            distrito,
            periodo,
            categoria,
            round(data["consumo"], 2),
            len(data["cuentas"])
        ))

    execute_concurrent_with_args(session, insert_consumo_categoria, datos_categoria, concurrency=150)
    print(f"Consumos por categoría cargados: {len(datos_categoria)}")


def main():
    session = get_session()

    infra_path = os.path.join(DATA_DIR, "infraestructuras.csv")
    contratos_path = os.path.join(DATA_DIR, "contratos.csv")
    medidores_path = os.path.join(DATA_DIR, "medidores.csv")

    # Asegúrate de usar latin1 aquí si tus infraestructuras también tienen acentos o Ñ
    infra_df = pd.read_csv(infra_path, encoding="latin1", low_memory=False)
    contratos_df = pd.read_csv(contratos_path, encoding="latin1", low_memory=False)
    medidores_df = pd.read_csv(medidores_path, encoding="latin1", low_memory=False)

    infra_df.columns = [c.strip() for c in infra_df.columns]
    contratos_df.columns = [c.strip() for c in contratos_df.columns]
    medidores_df.columns = [c.strip() for c in medidores_df.columns]

    # --- FILTRO DEL DISTRITO 15 ---
    # Lo convertimos a string y eliminamos cualquier fila que sea 15 o 15.0
    infra_df = infra_df[~infra_df['distrito'].astype(str).str.strip().isin(['15', '15.0'])]

    print("Filas infraestructuras (sin D15):", len(infra_df))
    print("Filas contratos:", len(contratos_df))
    print("Filas medidores:", len(medidores_df))

    print("Uniendo contratos con infraestructuras por numero_catastro...")
    # Cambiamos a 'inner' para que descarte los contratos que pertenecían al Distrito 15
    full_df = contratos_df.merge(
        infra_df,
        on="numero_catastro",
        how="inner" 
    )

    print("Uniendo medidores por medidor_iot...")
    full_df = full_df.merge(
        medidores_df,
        on="medidor_iot",
        how="left"
    )

    print("Filas finales unidas (sin D15):", len(full_df))

    print("Cargando infraestructuras...")
    cargar_infraestructuras(session, infra_df)

    print("Cargando distritos para mapa...")
    cargar_distritos_mapa(session, infra_df)

    print("Cargando cuentas y medidores...")
    cargar_cuentas(session, full_df)

    print("Cargando lecturas y agregados...")
    cargar_lecturas(session, full_df)

    print("Carga finalizada correctamente.")


if __name__ == "__main__":
    main()