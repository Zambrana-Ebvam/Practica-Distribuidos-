CREATE KEYSPACE IF NOT EXISTS semapa
WITH replication = {
  'class': 'SimpleStrategy',
  'replication_factor': 2
};

USE semapa;

CREATE TABLE IF NOT EXISTS infraestructuras_por_distrito (
    distrito text,
    zona text,
    numero_catastro text,
    propietario text,
    ci text,
    direccion text,
    manzano text,
    lote text,
    superficie_terreno double,
    area_construida double,
    uso_suelo text,
    matricula_ddrr text,
    valor_catastral double,
    impuesto_anual double,
    latitud double,
    longitud double,
    PRIMARY KEY ((distrito), zona, numero_catastro)
);

CREATE TABLE IF NOT EXISTS cuentas_por_distrito (
    distrito text,
    cuenta_id text,
    numero_catastro text,
    nombre_cliente text,
    ci text,
    categoria text,
    subcategoria text,
    zona text,
    direccion text,
    medidor_mac text,
    modelo_medidor text,
    estado_medidor text,
    estado_contrato text,
    tipo_servicio text,
    latitud double,
    longitud double,
    PRIMARY KEY (distrito, cuenta_id)
);

CREATE TABLE IF NOT EXISTS cuenta_detalle (
    cuenta_id text PRIMARY KEY,
    numero_catastro text,
    nombre_cliente text,
    ci text,
    distrito text,
    zona text,
    categoria text,
    subcategoria text,
    direccion text,
    medidor_mac text,
    modelo_medidor text,
    estado_medidor text,
    estado_contrato text,
    tipo_servicio text,
    latitud double,
    longitud double
);

CREATE TABLE IF NOT EXISTS consumo_cuenta_mes (
    cuenta_id text,
    periodo text,
    consumo_m3 double,
    total_lecturas int,
    lecturas_fallidas int,
    PRIMARY KEY (cuenta_id, periodo)
) WITH CLUSTERING ORDER BY (periodo DESC);

CREATE TABLE IF NOT EXISTS lecturas_por_medidor_mes (
    medidor_mac text,
    periodo text,
    fecha timestamp,
    radiobase text,
    lectura_anterior double,
    lectura_actual double,
    consumo_m3 double,
    status int,
    PRIMARY KEY ((medidor_mac, periodo), fecha)
) WITH CLUSTERING ORDER BY (fecha DESC);

CREATE TABLE IF NOT EXISTS consumo_distrito_mes (
    distrito text,
    periodo text,
    consumo_m3 double,
    total_cuentas int,
    total_medidores int,
    medidores_activos int,
    medidores_fuera_servicio int,
    PRIMARY KEY (distrito, periodo)
) WITH CLUSTERING ORDER BY (periodo DESC);

CREATE TABLE IF NOT EXISTS medidores_por_distrito_zona (
    distrito text,
    zona text,
    estado_medidor text,
    medidor_mac text,
    modelo_medidor text,
    cuenta_id text,
    PRIMARY KEY ((distrito, zona), estado_medidor, medidor_mac)
);

CREATE TABLE IF NOT EXISTS consumo_distrito_hora (
    distrito text,
    periodo text,
    bloque_horario text,
    consumo_m3 double,
    PRIMARY KEY ((distrito, periodo), bloque_horario)
);

CREATE TABLE IF NOT EXISTS distritos_mapa (
    distrito text PRIMARY KEY,
    lat double,
    lon double,
    total_zonas int,
    total_infraestructuras int
);

CREATE TABLE IF NOT EXISTS consumo_categoria_distrito_mes (
    distrito text,
    periodo text,
    categoria text,
    consumo_m3 double,
    total_cuentas int,
    PRIMARY KEY ((distrito, periodo), categoria)
);