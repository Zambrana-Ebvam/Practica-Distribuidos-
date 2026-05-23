import pandas as pd
import streamlit as st
import folium
import plotly.express as px
import plotly.graph_objects as go
from streamlit_folium import st_folium
from db import get_session
from pdf_preaviso import generar_pdfs_preaviso, calcular_mensaje_preaviso
from mensajeria import publicar_tres_canales

st.set_page_config(
    page_title="SEMAPA - Big Data Cassandra",
    layout="wide"
)

session = get_session()


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
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text.replace(".0", "")
    return text


def tarifa_categoria(categoria, subcategoria=None):
    cat = fix_text(categoria).upper().strip()
    sub = fix_text(subcategoria).upper().strip() if subcategoria else ""

    if sub in TARIFAS_BS:
        return TARIFAS_BS[sub]

    if cat in TARIFAS_BS:
        return TARIFAS_BS[cat]

    if "RESIDENCIAL" in cat:
        return TARIFAS_BS["RESIDENCIAL"]
    if "COMERCIAL ESPECIAL" in cat:
        return TARIFAS_BS["COMERCIAL ESPECIAL"]
    if "COMERCIAL" in cat:
        return TARIFAS_BS["COMERCIAL"]
    if "INDUSTRIAL" in cat:
        return TARIFAS_BS["INDUSTRIAL"]
    if "PREFERENCIAL" in cat:
        return TARIFAS_BS["PREFERENCIAL"]
    if "SOCIAL" in cat:
        return TARIFAS_BS["SOCIAL"]

    return 3.00


@st.cache_data(ttl=60)
def obtener_distritos():
    rows = session.execute("""
        SELECT distrito, lat, lon, total_zonas, total_infraestructuras
        FROM distritos_mapa
    """)
    df = pd.DataFrame(list(rows))

    if df.empty:
        return df

    df["distrito"] = df["distrito"].apply(normalizar_distrito)
    df = df.drop_duplicates(subset=["distrito"])
    df = df.sort_values("distrito", key=lambda x: x.astype(int))
    return df


@st.cache_data(ttl=60)
def obtener_consumo_distrito(distrito):
    distrito = normalizar_distrito(distrito)

    rows = session.execute("""
        SELECT distrito, periodo, consumo_m3, total_cuentas, total_medidores,
               medidores_activos, medidores_fuera_servicio
        FROM consumo_distrito_mes
        WHERE distrito = %s
    """, (distrito,))

    df = pd.DataFrame(list(rows))
    if not df.empty:
        df["distrito"] = df["distrito"].apply(normalizar_distrito)
    return df


@st.cache_data(ttl=60)
def obtener_cuentas_distrito(distrito):
    distrito = normalizar_distrito(distrito)

    rows = session.execute("""
        SELECT distrito, cuenta_id, numero_catastro, nombre_cliente, ci,
               categoria, subcategoria, zona, direccion, medidor_mac,
               modelo_medidor, estado_medidor, estado_contrato, tipo_servicio,
               latitud, longitud
        FROM cuentas_por_distrito
        WHERE distrito = %s
        LIMIT 2000
    """, (distrito,))

    df = pd.DataFrame(list(rows))

    if not df.empty:
        df["distrito"] = df["distrito"].apply(normalizar_distrito)
        for col in ["nombre_cliente", "categoria", "subcategoria", "zona", "direccion", "estado_medidor", "estado_contrato"]:
            if col in df.columns:
                df[col] = df[col].apply(fix_text)

    return df


@st.cache_data(ttl=60)
def obtener_detalle_cuenta(cuenta_id):
    row = session.execute("""
        SELECT cuenta_id, numero_catastro, nombre_cliente, ci, distrito,
               zona, categoria, subcategoria, direccion, medidor_mac,
               modelo_medidor, estado_medidor, estado_contrato, tipo_servicio,
               latitud, longitud
        FROM cuenta_detalle
        WHERE cuenta_id = %s
    """, (str(cuenta_id),)).one()

    if row:
        row["distrito"] = normalizar_distrito(row.get("distrito"))
        for col in ["nombre_cliente", "categoria", "subcategoria", "zona", "direccion", "estado_medidor", "estado_contrato"]:
            row[col] = fix_text(row.get(col))

    return row


@st.cache_data(ttl=60)
def obtener_consumo_cuenta(cuenta_id):
    rows = session.execute("""
        SELECT cuenta_id, periodo, consumo_m3, total_lecturas, lecturas_fallidas
        FROM consumo_cuenta_mes
        WHERE cuenta_id = %s
    """, (str(cuenta_id),))
    return pd.DataFrame(list(rows))


@st.cache_data(ttl=60)
def obtener_consumo_hora(distrito, periodo):
    distrito = normalizar_distrito(distrito)

    rows = session.execute("""
        SELECT distrito, periodo, bloque_horario, consumo_m3
        FROM consumo_distrito_hora
        WHERE distrito = %s AND periodo = %s
    """, (distrito, str(periodo)))

    return pd.DataFrame(list(rows))


@st.cache_data(ttl=60)
def obtener_consumo_categoria(distrito, periodo):
    distrito = normalizar_distrito(distrito)

    rows = session.execute("""
        SELECT distrito, periodo, categoria, consumo_m3, total_cuentas
        FROM consumo_categoria_distrito_mes
        WHERE distrito = %s AND periodo = %s
    """, (distrito, str(periodo)))

    df = pd.DataFrame(list(rows))
    if not df.empty:
        df["categoria"] = df["categoria"].apply(fix_text)
    return df


def calcular_resumen_ciudad(distritos):
    registros = []

    for distrito in distritos:
        df = obtener_consumo_distrito(distrito)
        if not df.empty:
            ultimo_periodo = sorted(df["periodo"].astype(str).unique(), reverse=True)[0]
            fila = df[df["periodo"].astype(str) == ultimo_periodo].iloc[0]
            registros.append({
                "distrito": distrito,
                "periodo": ultimo_periodo,
                "consumo_m3": float(fila["consumo_m3"]),
                "total_cuentas": int(fila["total_cuentas"]),
                "total_medidores": int(fila["total_medidores"]),
                "medidores_activos": int(fila["medidores_activos"]),
                "medidores_fuera_servicio": int(fila["medidores_fuera_servicio"])
            })

    return pd.DataFrame(registros)


def generar_facturacion(categoria_df):
    if categoria_df.empty:
        return categoria_df

    df = categoria_df.copy()
    df["tarifa_bs_m3"] = df["categoria"].apply(lambda c: tarifa_categoria(c))
    df["monto_facturado_bs"] = df["consumo_m3"] * df["tarifa_bs_m3"]
    df["monto_recaudado_bs"] = df["monto_facturado_bs"] * 0.82
    df["cartera_vencida_bs"] = df["monto_facturado_bs"] * 0.18
    df["preavisos_emitidos"] = df["total_cuentas"]
    df["tasa_entrega"] = 0.93
    df["tasa_apertura"] = 0.71
    df["conversion_pago"] = 0.54
    return df


def crear_mapa_base():
    return folium.Map(
        location=[-17.3895, -66.1568],
        zoom_start=12,
        tiles="OpenStreetMap"
    )


st.markdown("""
<style>
.main {
    background-color: #FFFFFF;
}
.block-container {
    padding-top: 2rem;
}
h1, h2, h3 {
    color: #0F172A;
}
[data-testid="stMetricValue"] {
    color: #0F172A;
}
.big-card {
    padding: 18px;
    border-radius: 14px;
    background-color: #F8FAFC;
    border: 1px solid #E5E7EB;
}
</style>
""", unsafe_allow_html=True)


st.title("SEMAPA Cochabamba - Plataforma Big Data Distribuida con Cassandra")
st.caption("Clúster Cassandra de 2 nodos en Docker + Python + Dashboard analítico estratégico")

distritos_df = obtener_distritos()

if distritos_df.empty:
    st.error("No hay distritos cargados. Ejecuta primero: python load_data.py")
    st.stop()

lista_distritos = distritos_df["distrito"].astype(str).tolist()
resumen_ciudad_df = calcular_resumen_ciudad(lista_distritos)

with st.sidebar:
    st.header("Filtros generales")

    distrito = st.selectbox(
        "Distrito",
        lista_distritos
    )

    consumo_distrito_df = obtener_consumo_distrito(distrito)

    if consumo_distrito_df.empty:
        st.warning("Este distrito no tiene consumo agregado.")
        periodo = None
    else:
        periodos = sorted(consumo_distrito_df["periodo"].astype(str).unique(), reverse=True)
        periodo = st.selectbox("Periodo", periodos)

    st.info("Los indicadores financieros y climáticos se calculan como simulación del MVP porque los CSV actuales no tienen pagos reales ni temperatura.")


tab_alcaldia, tab_gerencia, tab_contabilidad, tab_cuentas = st.tabs([
    "Dashboard 1 - Alcaldía / Smart City",
    "Dashboard 2 - Gerencia SEMAPA",
    "Dashboard 3 - Contabilidad SEMAPA",
    "Consulta de cuentas"
])


with tab_alcaldia:
    st.header("Dashboard 1 - Alcaldía Municipal")
    st.caption("Enfoque: Smart City, ODS 6, ODS 11, ODS 13 y calidad de vida.")

    if resumen_ciudad_df.empty:
        st.warning("No hay datos agregados de ciudad.")
    else:
        consumo_total_ciudad = resumen_ciudad_df["consumo_m3"].sum()
        total_cuentas_ciudad = resumen_ciudad_df["total_cuentas"].sum()
        total_medidores_ciudad = resumen_ciudad_df["total_medidores"].sum()
        total_activos_ciudad = resumen_ciudad_df["medidores_activos"].sum()
        total_fallas_ciudad = resumen_ciudad_df["medidores_fuera_servicio"].sum()

        cobertura = (total_activos_ciudad / total_medidores_ciudad) * 100 if total_medidores_ciudad else 0
        sensores_falla = (total_fallas_ciudad / total_medidores_ciudad) * 100 if total_medidores_ciudad else 0
        consumo_per_capita = consumo_total_ciudad / max(total_cuentas_ciudad * 5, 1)

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Consumo ciudad m³", f"{consumo_total_ciudad:,.2f}")
        k2.metric("Cuentas conectadas", f"{total_cuentas_ciudad:,}")
        k3.metric("Cobertura IoT", f"{cobertura:.2f}%")
        k4.metric("Sensores con fallas", f"{sensores_falla:.2f}%")
        k5.metric("Consumo per cápita m³", f"{consumo_per_capita:.2f}")

        c1, c2 = st.columns([1.1, 1])

        with c1:
            st.subheader("Mapa GIS municipal")

            mapa = crear_mapa_base()

            max_consumo = resumen_ciudad_df["consumo_m3"].max()

            for _, row in distritos_df.iterrows():
                d = row["distrito"]
                datos = resumen_ciudad_df[resumen_ciudad_df["distrito"] == d]

                consumo = 0
                if not datos.empty:
                    consumo = float(datos.iloc[0]["consumo_m3"])

                radio = 5 + (consumo / max_consumo * 20 if max_consumo else 0)

                lat = row.get("lat")
                lon = row.get("lon")

                if pd.notna(lat) and pd.notna(lon) and lat != 0 and lon != 0:
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=radio,
                        popup=f"""
                        <b>Distrito:</b> {d}<br>
                        <b>Consumo:</b> {consumo:,.2f} m³<br>
                        <b>Zonas:</b> {row.get('total_zonas', 0)}<br>
                        <b>Infraestructuras:</b> {row.get('total_infraestructuras', 0)}
                        """,
                        tooltip=f"Distrito {d}"
                    ).add_to(mapa)

            st_folium(mapa, width=780, height=500)

        with c2:
            st.subheader("Equidad territorial")

            ranking = resumen_ciudad_df.sort_values("consumo_m3", ascending=False)

            fig_rank = px.bar(
                ranking,
                x="distrito",
                y="consumo_m3",
                title="Consumo por distrito",
                text="consumo_m3"
            )
            fig_rank.update_traces(texttemplate="%{text:.0f}", textposition="outside")
            st.plotly_chart(fig_rank, use_container_width=True)

        st.subheader("Sostenibilidad hídrica y alertas ODS")

        resumen_ciudad_df["consumo_por_cuenta"] = resumen_ciudad_df["consumo_m3"] / resumen_ciudad_df["total_cuentas"].replace(0, 1)
        resumen_ciudad_df["alerta_sobreconsumo"] = resumen_ciudad_df["consumo_por_cuenta"].apply(
            lambda x: "CRÍTICO" if x > 45 else "NORMAL"
        )

        st.dataframe(
            resumen_ciudad_df[
                [
                    "distrito",
                    "periodo",
                    "consumo_m3",
                    "total_cuentas",
                    "consumo_por_cuenta",
                    "medidores_activos",
                    "medidores_fuera_servicio",
                    "alerta_sobreconsumo"
                ]
            ],
            use_container_width=True
        )

        st.subheader("Consumo vs temperatura y sequía")

        clima_df = resumen_ciudad_df.copy()
        clima_df["temperatura_c"] = 24 + clima_df["distrito"].astype(int) % 6
        clima_df["indice_sequia"] = 0.35 + (clima_df["distrito"].astype(int) % 5) * 0.10

        fig_clima = px.scatter(
            clima_df,
            x="temperatura_c",
            y="consumo_m3",
            size="indice_sequia",
            color="alerta_sobreconsumo",
            hover_name="distrito",
            title="Consumo vs temperatura e índice de sequía"
        )
        st.plotly_chart(fig_clima, use_container_width=True)

        st.subheader("Proyección de demanda futura 5 años")

        base = resumen_ciudad_df[["distrito", "consumo_m3"]].copy()
        for year in range(2026, 2031):
            factor = (1 + 0.026) ** (year - 2025)
            base[str(year)] = base["consumo_m3"] * factor

        st.dataframe(base, use_container_width=True)


with tab_gerencia:
    st.header("Dashboard 2 - Gerencia / Directorio SEMAPA")
    st.caption("Enfoque: operación, mantenimiento, anomalías y decisiones comerciales.")

    if not periodo:
        st.warning("Selecciona un distrito con datos.")
    else:
        cuentas_df = obtener_cuentas_distrito(distrito)
        hora_df = obtener_consumo_hora(distrito, periodo)
        categoria_df = obtener_consumo_categoria(distrito, periodo)

        if consumo_distrito_df.empty:
            st.warning("No existen datos de operación para este distrito.")
        else:
            fila = consumo_distrito_df[consumo_distrito_df["periodo"].astype(str) == str(periodo)].iloc[0]

            consumo_total = float(fila["consumo_m3"])
            total_medidores = int(fila["total_medidores"])
            medidores_activos = int(fila["medidores_activos"])
            medidores_fuera = int(fila["medidores_fuera_servicio"])
            sensores_error = medidores_fuera

            g1, g2, g3, g4, g5 = st.columns(5)
            g1.metric("Total consumo acumulado", f"{consumo_total:,.2f} m³")
            g2.metric("Medidores activos", f"{medidores_activos:,}")
            g3.metric("Medidores inactivos", f"{medidores_fuera:,}")
            g4.metric("Sensores con errores", f"{sensores_error:,}")
            g5.metric("Disponibilidad", f"{(medidores_activos / max(total_medidores, 1)) * 100:.2f}%")

            col_a, col_b = st.columns(2)

            with col_a:
                st.subheader("Consumo por bloques horarios")

                if hora_df.empty:
                    st.warning("No hay consumo horario.")
                else:
                    orden = ["00:00-08:00", "08:00-16:00", "16:00-24:00"]
                    hora_df["bloque_horario"] = pd.Categorical(
                        hora_df["bloque_horario"],
                        categories=orden,
                        ordered=True
                    )
                    hora_df = hora_df.sort_values("bloque_horario")

                    fig_hora = px.bar(
                        hora_df,
                        x="bloque_horario",
                        y="consumo_m3",
                        text="consumo_m3",
                        title=f"Pico máximo horario - Distrito {distrito}"
                    )
                    fig_hora.update_traces(texttemplate="%{text:.0f}", textposition="outside")
                    st.plotly_chart(fig_hora, use_container_width=True)

            with col_b:
                st.subheader("Distribución por categoría tarifaria")

                if categoria_df.empty:
                    st.warning("No hay consumo por categoría.")
                else:
                    fig_cat = px.pie(
                        categoria_df,
                        names="categoria",
                        values="consumo_m3",
                        title="Consumo por categoría"
                    )
                    st.plotly_chart(fig_cat, use_container_width=True)

            st.subheader("Top 10 zonas de mayor demanda")

            if cuentas_df.empty:
                st.warning("No hay cuentas del distrito.")
            else:
                consumos_cuentas = []

                for cuenta in cuentas_df["cuenta_id"].head(700).astype(str).tolist():
                    cdf = obtener_consumo_cuenta(cuenta)
                    if not cdf.empty:
                        cdf_periodo = cdf[cdf["periodo"].astype(str) == str(periodo)]
                        if not cdf_periodo.empty:
                            consumos_cuentas.append({
                                "cuenta_id": cuenta,
                                "consumo_m3": float(cdf_periodo.iloc[0]["consumo_m3"])
                            })

                consumo_cuentas_df = pd.DataFrame(consumos_cuentas)

                if not consumo_cuentas_df.empty:
                    cuentas_zonas = cuentas_df.merge(consumo_cuentas_df, on="cuenta_id", how="inner")
                    top_zonas = cuentas_zonas.groupby("zona")["consumo_m3"].sum().reset_index()
                    top_zonas = top_zonas.sort_values("consumo_m3", ascending=False).head(10)

                    fig_top = px.bar(
                        top_zonas,
                        x="zona",
                        y="consumo_m3",
                        text="consumo_m3",
                        title="Top 10 zonas con mayor demanda"
                    )
                    fig_top.update_traces(texttemplate="%{text:.0f}", textposition="outside")
                    st.plotly_chart(fig_top, use_container_width=True)

                    st.subheader("Tabla de anomalías operativas")

                    cuentas_zonas["anomalia"] = cuentas_zonas["consumo_m3"].apply(
                        lambda x: "POSIBLE FUGA / SOBRECONSUMO" if x > 45 else ("LECTURA CERO" if x == 0 else "NORMAL")
                    )

                    anomalias = cuentas_zonas[cuentas_zonas["anomalia"] != "NORMAL"]

                    st.dataframe(
                        anomalias[
                            [
                                "cuenta_id",
                                "nombre_cliente",
                                "zona",
                                "categoria",
                                "medidor_mac",
                                "estado_medidor",
                                "consumo_m3",
                                "anomalia"
                            ]
                        ].head(100),
                        use_container_width=True
                    )
                else:
                    st.warning("No se encontraron consumos por cuenta para este periodo.")

            st.subheader("Fallas por modelo de medidor")

            if not cuentas_df.empty:
                fallas_modelo = cuentas_df.copy()
                fallas_modelo["es_falla"] = fallas_modelo["estado_medidor"].apply(
                    lambda x: 0 if str(x).upper() in ["ACTIVO", "ACTIVA", "EN SERVICIO"] else 1
                )

                fallas_modelo = fallas_modelo.groupby("modelo_medidor").agg(
                    total_medidores=("medidor_mac", "count"),
                    fallas=("es_falla", "sum")
                ).reset_index()

                fallas_modelo["tasa_falla"] = (fallas_modelo["fallas"] / fallas_modelo["total_medidores"]) * 100

                fig_fallas = px.bar(
                    fallas_modelo,
                    x="modelo_medidor",
                    y="fallas",
                    text="fallas",
                    title="Fallas reportadas por modelo"
                )
                st.plotly_chart(fig_fallas, use_container_width=True)

                st.dataframe(fallas_modelo, use_container_width=True)


with tab_contabilidad:
    st.header("Dashboard 3 - Departamento Financiero / Contabilidad SEMAPA")
    st.caption("Enfoque: facturación, recaudación, mora, preavisos y proyección financiera.")

    if not periodo:
        st.warning("Selecciona un distrito con datos.")
    else:
        categoria_df = obtener_consumo_categoria(distrito, periodo)

        if categoria_df.empty:
            st.warning("No hay datos financieros para calcular.")
        else:
            financiero_df = generar_facturacion(categoria_df)

            monto_facturado = financiero_df["monto_facturado_bs"].sum()
            monto_recaudado = financiero_df["monto_recaudado_bs"].sum()
            cartera_vencida = financiero_df["cartera_vencida_bs"].sum()
            preavisos = financiero_df["preavisos_emitidos"].sum()
            ticket_promedio = monto_facturado / max(financiero_df["total_cuentas"].sum(), 1)
            recuperacion = (monto_recaudado / monto_facturado) * 100 if monto_facturado else 0

            f1, f2, f3, f4, f5 = st.columns(5)
            f1.metric("Monto facturado mensual", f"Bs {monto_facturado:,.2f}")
            f2.metric("Monto recaudado", f"Bs {monto_recaudado:,.2f}")
            f3.metric("Cartera vencida", f"Bs {cartera_vencida:,.2f}")
            f4.metric("% recuperación", f"{recuperacion:.2f}%")
            f5.metric("Ticket promedio", f"Bs {ticket_promedio:,.2f}")

            col_f1, col_f2 = st.columns(2)

            with col_f1:
                st.subheader("Facturación por categoría tarifaria")

                fig_fact = px.bar(
                    financiero_df,
                    x="categoria",
                    y="monto_facturado_bs",
                    text="monto_facturado_bs",
                    title="Monto facturado por categoría"
                )
                fig_fact.update_traces(texttemplate="%{text:.0f}", textposition="outside")
                st.plotly_chart(fig_fact, use_container_width=True)

            with col_f2:
                st.subheader("Recaudación vs mora")

                comparativo = pd.DataFrame({
                    "concepto": ["Recaudado", "Cartera vencida"],
                    "monto_bs": [monto_recaudado, cartera_vencida]
                })

                fig_mora = px.pie(
                    comparativo,
                    names="concepto",
                    values="monto_bs",
                    title="Distribución financiera"
                )
                st.plotly_chart(fig_mora, use_container_width=True)

            st.subheader("Detalle financiero por categoría")

            st.dataframe(
                financiero_df[
                    [
                        "categoria",
                        "consumo_m3",
                        "tarifa_bs_m3",
                        "total_cuentas",
                        "monto_facturado_bs",
                        "monto_recaudado_bs",
                        "cartera_vencida_bs",
                        "preavisos_emitidos"
                    ]
                ],
                use_container_width=True
            )

            st.subheader("Embudo de cobranza preventiva")

            funnel = go.Figure(go.Funnel(
                y=[
                    "Preavisos emitidos",
                    "Preavisos entregados",
                    "Preavisos abiertos",
                    "Pagos convertidos"
                ],
                x=[
                    preavisos,
                    preavisos * 0.93,
                    preavisos * 0.93 * 0.71,
                    preavisos * 0.93 * 0.71 * 0.54
                ]
            ))

            funnel.update_layout(title="Efectividad de preavisos")
            st.plotly_chart(funnel, use_container_width=True)

            st.subheader("Proyección financiera 3 meses")

            proy = pd.DataFrame({
                "mes": ["Mes actual", "Mes +1", "Mes +2", "Mes +3"],
                "ingreso_proyectado_bs": [
                    monto_facturado,
                    monto_facturado * 1.026,
                    monto_facturado * 1.026 ** 2,
                    monto_facturado * 1.026 ** 3
                ],
                "recaudacion_estimada_bs": [
                    monto_recaudado,
                    monto_recaudado * 1.026,
                    monto_recaudado * 1.026 ** 2,
                    monto_recaudado * 1.026 ** 3
                ]
            })

            fig_proy = px.line(
                proy,
                x="mes",
                y=["ingreso_proyectado_bs", "recaudacion_estimada_bs"],
                markers=True,
                title="Flujo financiero proyectado"
            )
            st.plotly_chart(fig_proy, use_container_width=True)

            st.subheader("Impacto de cambio tarifario Preferencial a Residencial R4")

            consumo_preferencial = financiero_df[
                financiero_df["categoria"].str.upper().str.contains("PREFERENCIAL|P", na=False)
            ]["consumo_m3"].sum()

            ingreso_p = consumo_preferencial * TARIFAS_BS["P"]
            ingreso_r4 = consumo_preferencial * TARIFAS_BS["R4"]
            incremento = ingreso_r4 - ingreso_p

            impacto = pd.DataFrame({
                "escenario": ["Tarifa Preferencial", "Cambio a R4", "Incremento"],
                "monto_bs": [ingreso_p, ingreso_r4, incremento]
            })

            st.dataframe(impacto, use_container_width=True)


with tab_cuentas:
    st.header("Consulta de cuentas por distrito")
    st.caption("Esta parte sirve para defender que al seleccionar un distrito se puede revisar cada cuenta.")

    if not periodo:
        st.warning("Selecciona un distrito con datos.")
    else:
        cuentas_df = obtener_cuentas_distrito(distrito)

        if cuentas_df.empty:
            st.warning("No hay cuentas para este distrito.")
        else:
            zonas = ["TODAS"] + sorted(cuentas_df["zona"].dropna().astype(str).unique().tolist())

            col_z1, col_z2 = st.columns([1, 2])

            with col_z1:
                zona = st.selectbox("Zona", zonas)

            with col_z2:
                buscar = st.text_input("Buscar por cuenta, cliente, medidor o dirección")

            if zona != "TODAS":
                cuentas_df = cuentas_df[cuentas_df["zona"] == zona]

            if buscar.strip():
                b = buscar.strip().upper()
                cuentas_df = cuentas_df[
                    cuentas_df["cuenta_id"].astype(str).str.upper().str.contains(b, na=False) |
                    cuentas_df["nombre_cliente"].astype(str).str.upper().str.contains(b, na=False) |
                    cuentas_df["medidor_mac"].astype(str).str.upper().str.contains(b, na=False) |
                    cuentas_df["direccion"].astype(str).str.upper().str.contains(b, na=False)
                ]

            st.dataframe(
                cuentas_df[
                    [
                        "cuenta_id",
                        "nombre_cliente",
                        "categoria",
                        "subcategoria",
                        "zona",
                        "medidor_mac",
                        "estado_medidor",
                        "estado_contrato"
                    ]
                ],
                use_container_width=True,
                height=350
            )

            if not cuentas_df.empty:
                cuenta_id = st.selectbox(
                    "Selecciona una cuenta",
                    cuentas_df["cuenta_id"].astype(str).tolist()
                )

                detalle = obtener_detalle_cuenta(cuenta_id)

                if detalle:
                    st.subheader("Información de la cuenta")

                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Cuenta", detalle.get("cuenta_id", ""))
                    c2.metric("Distrito", detalle.get("distrito", ""))
                    c3.metric("Categoría", detalle.get("categoria", ""))
                    c4.metric("Subcategoría", detalle.get("subcategoria", ""))

                    d1, d2, d3 = st.columns(3)
                    d1.info(f"**Cliente:** {detalle.get('nombre_cliente', '')}")
                    d2.info(f"**CI/NIT:** {detalle.get('ci', '')}")
                    d3.info(f"**Zona:** {detalle.get('zona', '')}")

                    s1, s2, s3 = st.columns(3)
                    s1.success(f"**Medidor:** {detalle.get('medidor_mac', '')}")
                    s2.success(f"**Modelo:** {detalle.get('modelo_medidor', '')}")
                    s3.success(f"**Estado:** {detalle.get('estado_medidor', '')}")

                    st.warning(f"Dirección: {detalle.get('direccion', '')}")

                    consumo_cuenta_df = obtener_consumo_cuenta(cuenta_id)

                    if consumo_cuenta_df.empty:
                        st.warning("Esta cuenta no tiene consumo registrado.")
                    else:
                        consumo_cuenta_df = consumo_cuenta_df.sort_values("periodo")

                        fig_cuenta = px.bar(
                            consumo_cuenta_df,
                            x="periodo",
                            y="consumo_m3",
                            text="consumo_m3",
                            title=f"Consumo mensual de la cuenta {cuenta_id}"
                        )
                        fig_cuenta.update_traces(texttemplate="%{text:.2f}", textposition="outside")
                        st.plotly_chart(fig_cuenta, use_container_width=True)

                        st.dataframe(consumo_cuenta_df, use_container_width=True)

                        st.divider()
                        st.subheader("Preaviso, PDF y mensajería asincrónica")

                        consumo_cuenta_df = consumo_cuenta_df.sort_values("periodo", ascending=False)

                        periodos_cuenta = consumo_cuenta_df["periodo"].astype(str).tolist()

                        periodo_preaviso = st.selectbox(
                            "Periodo para generar preaviso",
                            periodos_cuenta,
                            key=f"periodo_preaviso_{cuenta_id}"
                        )

                        consumo_periodo_df = consumo_cuenta_df[
                            consumo_cuenta_df["periodo"].astype(str) == str(periodo_preaviso)
                        ]

                        consumo_periodo = consumo_periodo_df.iloc[0].to_dict()
                        historial = consumo_cuenta_df.to_dict("records")

                        mensaje_preaviso = calcular_mensaje_preaviso(detalle, consumo_periodo)

                        st.text_area(
                            "Mensaje generado",
                            mensaje_preaviso,
                            height=100,
                            key=f"mensaje_{cuenta_id}"
                        )

                        col_dest1, col_dest2, col_dest3 = st.columns(3)

                        with col_dest1:
                            destino_whatsapp = st.text_input(
                                "WhatsApp",
                                placeholder="+59170000000",
                                key=f"wp_{cuenta_id}"
                            )

                        with col_dest2:
                            destino_sms = st.text_input(
                                "SMS",
                                placeholder="+59170000000",
                                key=f"sms_{cuenta_id}"
                            )

                        with col_dest3:
                            destino_email = st.text_input(
                                "Email",
                                placeholder="cliente@email.com",
                                key=f"email_{cuenta_id}"
                            )

                        generar_col, enviar_col = st.columns(2)

                        with generar_col:
                            if st.button("Generar PDF rollo y media carta", key=f"pdf_{cuenta_id}"):
                                pdfs = generar_pdfs_preaviso(
                                    detalle=detalle,
                                    consumo_periodo=consumo_periodo,
                                    historial=historial
                                )

                                st.session_state[f"pdfs_{cuenta_id}"] = pdfs

                                st.success("PDFs generados correctamente.")

                                with open(pdfs["rollo"], "rb") as file:
                                    st.download_button(
                                        "Descargar PDF rollo 55 mm",
                                        data=file,
                                        file_name=pdfs["rollo"].split("\\")[-1],
                                        mime="application/pdf",
                                        key=f"download_rollo_{cuenta_id}"
                                    )

                                with open(pdfs["media_carta"], "rb") as file:
                                    st.download_button(
                                        "Descargar PDF media carta",
                                        data=file,
                                        file_name=pdfs["media_carta"].split("\\")[-1],
                                        mime="application/pdf",
                                        key=f"download_media_{cuenta_id}"
                                    )

                        with enviar_col:
                            if st.button("Enviar por WhatsApp, SMS y Email", key=f"enviar_{cuenta_id}"):
                                pdfs = st.session_state.get(f"pdfs_{cuenta_id}")

                                if not pdfs:
                                    pdfs = generar_pdfs_preaviso(
                                        detalle=detalle,
                                        consumo_periodo=consumo_periodo,
                                        historial=historial
                                    )

                                    st.session_state[f"pdfs_{cuenta_id}"] = pdfs

                                destinatarios = {
                                    "WHATSAPP": destino_whatsapp,
                                    "SMS": destino_sms,
                                    "EMAIL": destino_email
                                }

                                enviados = publicar_tres_canales(
                                    destinatarios=destinatarios,
                                    cuenta_id=detalle.get("cuenta_id"),
                                    periodo=periodo_preaviso,
                                    mensaje=mensaje_preaviso,
                                    pdf_rollo=pdfs["rollo"],
                                    pdf_media_carta=pdfs["media_carta"]
                                )

                                if enviados:
                                    st.success(f"Se enviaron {len(enviados)} mensajes a RabbitMQ.")
                                    st.info("Revisa la terminal del worker_mensajes.py para ver el despacho.")
                                else:
                                    st.warning("Debes escribir al menos un WhatsApp, SMS o Email.")

                    st.subheader("Mapa de la cuenta")

                    mapa_cuenta = crear_mapa_base()

                    lat = detalle.get("latitud")
                    lon = detalle.get("longitud")

                    if lat and lon:
                        folium.Marker(
                            location=[lat, lon],
                            popup=f"""
                            <b>Cuenta:</b> {detalle.get('cuenta_id', '')}<br>
                            <b>Cliente:</b> {detalle.get('nombre_cliente', '')}<br>
                            <b>Distrito:</b> {detalle.get('distrito', '')}<br>
                            <b>Zona:</b> {detalle.get('zona', '')}<br>
                            <b>Medidor:</b> {detalle.get('medidor_mac', '')}
                            """,
                            tooltip=detalle.get("cuenta_id", "")
                        ).add_to(mapa_cuenta)

                    st_folium(mapa_cuenta, width=1000, height=450)