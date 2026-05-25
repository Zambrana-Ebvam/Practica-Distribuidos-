import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Marker,
  Popup,
  GeoJSON,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  CartesianGrid,
  Legend,
  FunnelChart,
  Funnel,
  LabelList,
} from "recharts";

const API = "http://localhost:8000";

const markerIcon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

function formatNumber(value) {
  if (value === null || value === undefined) return "0";
  return Number(value).toLocaleString("es-BO", {
    maximumFractionDigits: 2,
  });
}

function formatMoney(value) {
  if (value === null || value === undefined) return "Bs 0";
  return `Bs ${Number(value).toLocaleString("es-BO", {
    maximumFractionDigits: 2,
  })}`;
}

function KpiCard({ title, value, subtitle }) {
  return (
    <div className="kpi-card">
      <span>{title}</span>
      <strong>{value}</strong>
      {subtitle && <small>{subtitle}</small>}
    </div>
  );
}

function FlyToDistrito({ lat, lon }) {
  const map = useMap();

  useEffect(() => {
    if (lat && lon) {
      map.flyTo([lat, lon], 13, {
        duration: 0.8,
      });
    }
  }, [lat, lon, map]);

  return null;
}

function App() {
  const [tab, setTab] = useState("alcaldia");

  const [distritos, setDistritos] = useState([]);
  const [alcaldia, setAlcaldia] = useState(null);

  const [distrito, setDistrito] = useState("1");
  const [periodo, setPeriodo] = useState("2026-04");

  const [resumenDistrito, setResumenDistrito] = useState(null);
  const [cuentas, setCuentas] = useState([]);
  const [cuentaSeleccionada, setCuentaSeleccionada] = useState(null);
  const [consumoCuenta, setConsumoCuenta] = useState([]);

  const [gerencia, setGerencia] = useState(null);
  const [contabilidad, setContabilidad] = useState(null);

  const [busqueda, setBusqueda] = useState("");
  const [zona, setZona] = useState("TODAS");

  const [whatsapp, setWhatsapp] = useState("");
  const [sms, setSms] = useState("");
  const [email, setEmail] = useState("");
  const [resultadoEnvio, setResultadoEnvio] = useState(null);

  const [geojson, setGeojson] = useState(null);

  useEffect(() => {
    cargarInicial();
  }, []);

  useEffect(() => {
    if (distrito) {
      cargarDistrito();
    }
  }, [distrito]);

  useEffect(() => {
    if (distrito && periodo) {
      cargarDashboardsDistrito();
    }
  }, [distrito, periodo]);

  async function cargarInicial() {
    const [distritosRes, alcaldiaRes] = await Promise.all([
      axios.get(`${API}/api/distritos`),
      axios.get(`${API}/api/dashboard/alcaldia`),
    ]);

    setDistritos(distritosRes.data);
    setAlcaldia(alcaldiaRes.data);

    const primero = distritosRes.data?.[0]?.distrito || "1";
    setDistrito(primero);

    try {
      const geo = await axios.get("/cochabamba_distritos.geojson");
      console.log("GeoJSON cargado:", geo.data);
      console.log("Cantidad de features:", geo.data.features?.length);

      if (
        geo.data &&
        geo.data.type &&
        ["FeatureCollection", "Feature", "Polygon", "MultiPolygon"].includes(geo.data.type)
      ) {
        setGeojson(geo.data);
      } else {
        console.warn("GeoJSON inválido. Se usará solo OpenStreetMap.");
        setGeojson(null);
      }
    } catch (error) {
      console.error("Error cargando GeoJSON:", error);
      setGeojson(null);
    }
  }

  async function cargarDistrito() {
    const resumenRes = await axios.get(`${API}/api/distritos/${distrito}/resumen`);
    const cuentasRes = await axios.get(`${API}/api/distritos/${distrito}/cuentas?limit=1500`);

    setResumenDistrito(resumenRes.data);
    setCuentas(cuentasRes.data);
    setCuentaSeleccionada(null);
    setConsumoCuenta([]);
    setResultadoEnvio(null);

    const ultimoPeriodo = resumenRes.data?.ultimo?.periodo;
    if (ultimoPeriodo) {
      setPeriodo(ultimoPeriodo);
    }
  }

  async function cargarDashboardsDistrito() {
    const [gerenciaRes, contabilidadRes] = await Promise.all([
      axios.get(`${API}/api/dashboard/gerencia/${distrito}?periodo=${periodo}`),
      axios.get(`${API}/api/dashboard/contabilidad/${distrito}?periodo=${periodo}`),
    ]);

    setGerencia(gerenciaRes.data);
    setContabilidad(contabilidadRes.data);
  }

  async function seleccionarCuenta(cuenta) {
    const [detalleRes, consumoRes] = await Promise.all([
      axios.get(`${API}/api/cuentas/${cuenta.cuenta_id}`),
      axios.get(`${API}/api/cuentas/${cuenta.cuenta_id}/consumo`),
    ]);

    setCuentaSeleccionada(detalleRes.data);
    setConsumoCuenta(consumoRes.data);
    setResultadoEnvio(null);
  }

  async function generarPdf() {
    if (!cuentaSeleccionada || !periodo) return;

    const res = await axios.post(`${API}/api/preaviso/generar-pdf`, {
      cuenta_id: cuentaSeleccionada.cuenta_id,
      periodo,
    });

    setResultadoEnvio(res.data);
  }

  async function enviarPreaviso() {
    if (!cuentaSeleccionada || !periodo) return;

    const res = await axios.post(`${API}/api/preaviso/enviar`, {
      cuenta_id: cuentaSeleccionada.cuenta_id,
      periodo,
      whatsapp,
      sms,
      email,
    });

    setResultadoEnvio(res.data);
  }

  const distritoActual = useMemo(() => {
    return distritos.find((d) => String(d.distrito) === String(distrito));
  }, [distritos, distrito]);

  const zonas = useMemo(() => {
    const values = Array.from(new Set(cuentas.map((c) => c.zona).filter(Boolean))).sort();
    return ["TODAS", ...values];
  }, [cuentas]);

  const cuentasFiltradas = useMemo(() => {
    let data = [...cuentas];

    if (zona !== "TODAS") {
      data = data.filter((c) => c.zona === zona);
    }

    if (busqueda.trim()) {
      const b = busqueda.trim().toUpperCase();
      data = data.filter((c) => {
        return (
          String(c.cuenta_id || "").toUpperCase().includes(b) ||
          String(c.nombre_cliente || "").toUpperCase().includes(b) ||
          String(c.medidor_mac || "").toUpperCase().includes(b) ||
          String(c.direccion || "").toUpperCase().includes(b)
        );
      });
    }

    return data;
  }, [cuentas, zona, busqueda]);

  const consumoPeriodoCuenta = useMemo(() => {
    if (!consumoCuenta.length) return null;
    return consumoCuenta.find((c) => c.periodo === periodo) || consumoCuenta[0];
  }, [consumoCuenta, periodo]);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="logo">S</div>
          <div>
            <h2>SEMAPA</h2>
            <p>Big Data Cassandra</p>
          </div>
        </div>

        <label>Distrito</label>
        <select value={distrito} onChange={(e) => setDistrito(e.target.value)}>
          {distritos.map((d) => (
            <option key={d.distrito} value={d.distrito}>
              Distrito {d.distrito}
            </option>
          ))}
        </select>

        <label>Periodo</label>
        <select value={periodo} onChange={(e) => setPeriodo(e.target.value)}>
          {resumenDistrito?.periodos?.map((p) => (
            <option key={p.periodo} value={p.periodo}>
              {p.periodo}
            </option>
          ))}
        </select>

        <div className="side-note">
          Mapa interactivo con cuentas, medidores, preavisos PDF y mensajería asincrónica.
        </div>

        <nav>
          <button className={tab === "alcaldia" ? "active" : ""} onClick={() => setTab("alcaldia")}>
            Dashboard Alcaldía
          </button>
          <button className={tab === "gerencia" ? "active" : ""} onClick={() => setTab("gerencia")}>
            Dashboard Gerencia
          </button>
          <button className={tab === "contabilidad" ? "active" : ""} onClick={() => setTab("contabilidad")}>
            Dashboard Contabilidad
          </button>
          <button className={tab === "mapa" ? "active" : ""} onClick={() => setTab("mapa")}>
            Mapa y preavisos
          </button>
        </nav>
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <h1>SEMAPA Cochabamba</h1>
            <p>Plataforma distribuida para gestión inteligente del consumo de agua</p>
          </div>

          <div className="status-pill">Cassandra + RabbitMQ + FastAPI</div>
        </header>

        {tab === "alcaldia" && (
          <section>
            <h2>Dashboard 1 - Alcaldía Municipal / Smart City</h2>

            <div className="grid-5">
              <KpiCard title="Consumo ciudad" value={`${formatNumber(alcaldia?.kpis?.consumo_ciudad_m3)} m³`} />
              <KpiCard title="Cuentas conectadas" value={formatNumber(alcaldia?.kpis?.cuentas_conectadas)} />
              <KpiCard title="Cobertura IoT" value={`${formatNumber(alcaldia?.kpis?.cobertura_iot)}%`} />
              <KpiCard title="Sensores con fallas" value={`${formatNumber(alcaldia?.kpis?.sensores_falla_pct)}%`} />
              <KpiCard title="Medidores activos" value={formatNumber(alcaldia?.kpis?.medidores_activos)} />
            </div>

            <div className="dashboard-grid">
              <div className="panel large">
                <h3>Mapa GIS municipal</h3>
                <MapaGeneral
                  distritos={alcaldia?.distritos || []}
                  distritoActual={distritoActual}
                  geojson={geojson}
                  onDistritoClick={(d) => setDistrito(d)}
                />
              </div>

              <div className="panel">
                <h3>Equidad territorial</h3>
                <ResponsiveContainer width="100%" height={330}>
                  <BarChart data={alcaldia?.distritos || []}>
                    <XAxis dataKey="distrito" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="consumo_m3" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="panel">
              <h3>Consumo vs temperatura y sequía</h3>
              <ResponsiveContainer width="100%" height={330}>
                <BarChart data={alcaldia?.distritos || []}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="distrito" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="temperatura_c" name="Temperatura °C" />
                  <Bar dataKey="indice_sequia" name="Índice sequía" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="panel">
              <h3>Alertas ODS por distrito</h3>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Distrito</th>
                    <th>Consumo m³</th>
                    <th>Cuentas</th>
                    <th>Cobertura IoT</th>
                    <th>Sensores falla</th>
                    <th>Alerta</th>
                  </tr>
                </thead>
                <tbody>
                  {(alcaldia?.distritos || []).map((d) => (
                    <tr key={d.distrito}>
                      <td>D{d.distrito}</td>
                      <td>{formatNumber(d.consumo_m3)}</td>
                      <td>{formatNumber(d.total_cuentas)}</td>
                      <td>{formatNumber(d.cobertura_iot)}%</td>
                      <td>{formatNumber(d.sensores_falla_pct)}%</td>
                      <td>
                        <span className={d.alerta === "CRÍTICO" ? "badge danger" : "badge ok"}>
                          {d.alerta}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {tab === "gerencia" && (
          <section>
            <h2>Dashboard 2 - Gerencia / Directorio SEMAPA</h2>

            <div className="grid-5">
              <KpiCard title="Consumo acumulado" value={`${formatNumber(resumenDistrito?.ultimo?.consumo_m3)} m³`} />
              <KpiCard title="Medidores activos" value={formatNumber(resumenDistrito?.ultimo?.medidores_activos)} />
              <KpiCard title="Medidores inactivos" value={formatNumber(resumenDistrito?.ultimo?.medidores_fuera_servicio)} />
              <KpiCard title="Total cuentas" value={formatNumber(resumenDistrito?.ultimo?.total_cuentas)} />
              <KpiCard title="Disponibilidad" value={`${formatNumber((resumenDistrito?.ultimo?.medidores_activos || 0) / Math.max(resumenDistrito?.ultimo?.total_medidores || 1, 1) * 100)}%`} />
            </div>

            <div className="dashboard-grid">
              <div className="panel">
                <h3>Consumo por bloques horarios</h3>
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={gerencia?.horas || []}>
                    <XAxis dataKey="bloque_horario" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="consumo_m3" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="panel">
                <h3>Distribución por categoría tarifaria</h3>
                <ResponsiveContainer width="100%" height={320}>
                  <PieChart>
                    <Pie
                      data={gerencia?.categorias || []}
                      dataKey="consumo_m3"
                      nameKey="categoria"
                      outerRadius={110}
                      label
                    >
                      {(gerencia?.categorias || []).map((_, index) => (
                        <Cell key={index} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="dashboard-grid">
              <div className="panel">
                <h3>Top 10 zonas de mayor demanda</h3>
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={gerencia?.top_zonas || []}>
                    <XAxis dataKey="zona" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="consumo_m3" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="panel">
                <h3>Fallas por modelo</h3>
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={gerencia?.fallas_modelo || []}>
                    <XAxis dataKey="modelo_medidor" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="fallas" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="panel">
              <h3>Tabla de anomalías</h3>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Cuenta</th>
                    <th>Cliente</th>
                    <th>Zona</th>
                    <th>Categoría</th>
                    <th>Medidor</th>
                    <th>Consumo</th>
                    <th>Anomalía</th>
                  </tr>
                </thead>
                <tbody>
                  {(gerencia?.anomalias || []).map((a) => (
                    <tr key={a.cuenta_id}>
                      <td>{a.cuenta_id}</td>
                      <td>{a.nombre_cliente}</td>
                      <td>{a.zona}</td>
                      <td>{a.categoria}</td>
                      <td>{a.medidor_mac}</td>
                      <td>{formatNumber(a.consumo_m3)}</td>
                      <td><span className="badge warning">{a.anomalia}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {tab === "contabilidad" && (
          <section>
            <h2>Dashboard 3 - Departamento Financiero / Contabilidad SEMAPA</h2>

            <div className="grid-5">
              <KpiCard title="Monto facturado" value={formatMoney(contabilidad?.kpis?.monto_facturado_bs)} />
              <KpiCard title="Monto recaudado" value={formatMoney(contabilidad?.kpis?.monto_recaudado_bs)} />
              <KpiCard title="Cartera vencida" value={formatMoney(contabilidad?.kpis?.cartera_vencida_bs)} />
              <KpiCard title="% recuperación" value={`${formatNumber(contabilidad?.kpis?.recuperacion_pct)}%`} />
              <KpiCard title="Preavisos emitidos" value={formatNumber(contabilidad?.kpis?.preavisos_emitidos)} />
            </div>

            <div className="dashboard-grid">
              <div className="panel">
                <h3>Facturación por categoría</h3>
                <ResponsiveContainer width="100%" height={330}>
                  <BarChart data={contabilidad?.categorias || []}>
                    <XAxis dataKey="categoria" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="monto_facturado_bs" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="panel">
                <h3>Embudo de cobranza preventiva</h3>
                <ResponsiveContainer width="100%" height={330}>
                  <FunnelChart>
                    <Tooltip />
                    <Funnel dataKey="cantidad" data={contabilidad?.embudo || []} nameKey="etapa">
                      <LabelList position="right" fill="#111" stroke="none" dataKey="etapa" />
                    </Funnel>
                  </FunnelChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="panel">
              <h3>Proyección financiera 3 meses</h3>
              <ResponsiveContainer width="100%" height={330}>
                <LineChart data={contabilidad?.proyeccion || []}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="mes" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="ingreso_proyectado_bs" />
                  <Line type="monotone" dataKey="recaudacion_estimada_bs" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        {tab === "mapa" && (
          <section>
            <h2>Mapa de Cochabamba, cuentas, medidores y preavisos</h2>

            <div className="map-layout">
              <div className="panel map-panel">
                <div className="filters-inline">
                  <select value={zona} onChange={(e) => setZona(e.target.value)}>
                    {zonas.map((z) => (
                      <option key={z} value={z}>
                        {z}
                      </option>
                    ))}
                  </select>

                  <input
                    placeholder="Buscar cuenta, cliente, medidor o dirección"
                    value={busqueda}
                    onChange={(e) => setBusqueda(e.target.value)}
                  />
                </div>

                <MapaCuentas
                  cuentas={cuentasFiltradas}
                  distritoActual={distritoActual}
                  geojson={geojson}
                  cuentaSeleccionada={cuentaSeleccionada}
                  onCuentaClick={seleccionarCuenta}
                />
              </div>

              <div className="panel detail-panel">
                {!cuentaSeleccionada ? (
                  <div className="empty-state">
                    <h3>Selecciona un medidor en el mapa</h3>
                    <p>Al hacer clic en un punto del mapa se mostrará la información del cliente y los botones de preaviso.</p>
                  </div>
                ) : (
                  <div>
                    <h3>Información del medidor</h3>

                    <div className="client-box">
                      <p><b>Cuenta:</b> {cuentaSeleccionada.cuenta_id}</p>
                      <p><b>Señor(a):</b> {cuentaSeleccionada.nombre_cliente}</p>
                      <p><b>Distrito:</b> {cuentaSeleccionada.distrito}</p>
                      <p><b>Zona:</b> {cuentaSeleccionada.zona}</p>
                      <p><b>Categoría:</b> {cuentaSeleccionada.categoria} {cuentaSeleccionada.subcategoria}</p>
                      <p><b>Medidor:</b> {cuentaSeleccionada.medidor_mac}</p>
                      <p><b>Dirección:</b> {cuentaSeleccionada.direccion}</p>
                    </div>

                    <div className="mini-kpis">
                      <KpiCard
                        title="Consumo periodo"
                        value={`${formatNumber(consumoPeriodoCuenta?.consumo_m3 || 0)} m³`}
                      />
                      <KpiCard
                        title="Lecturas"
                        value={formatNumber(consumoPeriodoCuenta?.total_lecturas || 0)}
                      />
                    </div>

                    <h3>Consumo histórico</h3>
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={[...consumoCuenta].reverse()}>
                        <XAxis dataKey="periodo" />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="consumo_m3" />
                      </BarChart>
                    </ResponsiveContainer>

                    <h3>Enviar preaviso</h3>

                    <input
                      placeholder="WhatsApp +591..."
                      value={whatsapp}
                      onChange={(e) => setWhatsapp(e.target.value)}
                    />

                    <input
                      placeholder="SMS +591..."
                      value={sms}
                      onChange={(e) => setSms(e.target.value)}
                    />

                    <input
                      placeholder="Email cliente@email.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />

                    <div className="buttons">
                      <button onClick={generarPdf}>Generar PDF</button>
                      <button className="primary" onClick={enviarPreaviso}>
                        Enviar WhatsApp, SMS y Email
                      </button>
                    </div>

                    {resultadoEnvio && (
                      <div className="result-box">
                        <h4>Resultado</h4>
                        <p>{resultadoEnvio.mensaje}</p>

                        {resultadoEnvio.pdfs?.rollo && (
                          <a
                            href={`${API}/api/download?path=${encodeURIComponent(resultadoEnvio.pdfs.rollo)}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Descargar PDF rollo 55 mm
                          </a>
                        )}

                        {resultadoEnvio.pdfs?.media_carta && (
                          <a
                            href={`${API}/api/download?path=${encodeURIComponent(resultadoEnvio.pdfs.media_carta)}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Descargar PDF media carta
                          </a>
                        )}

                        {resultadoEnvio.enviados && (
                          <p className="success">Mensajes enviados a RabbitMQ: {resultadoEnvio.enviados.length}</p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

function MapaGeneral({ distritos, distritoActual, geojson, onDistritoClick }) {
  const center = distritoActual?.lat && distritoActual?.lon
    ? [distritoActual.lat, distritoActual.lon]
    : [-17.3895, -66.1568];

  const maxConsumo = Math.max(...distritos.map((d) => Number(d.consumo_m3 || 0)), 1);

  const distritoPolygonStyle = {
    color: '#2c3e50',
    weight: 2,
    opacity: 0.8,
    fillColor: '#3498db',
    fillOpacity: 0.25
  };

  const highlightStyle = {
    color: '#c0392b',
    weight: 3,
    opacity: 1,
    fillColor: '#e74c3c',
    fillOpacity: 0.5
  };

  return (
    <MapContainer center={center} zoom={12} className="map">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {distritoActual && <FlyToDistrito lat={distritoActual.lat} lon={distritoActual.lon} />}

      {geojson && geojson.type === "FeatureCollection" && geojson.features && geojson.features.length > 0 && (
        <GeoJSON 
          data={geojson} 
          style={() => distritoPolygonStyle}
          onEachFeature={(feature, layer) => {
            const nombre = feature?.properties?.nombre || 
                          feature?.properties?.DISTRITO || 
                          feature?.properties?.NAME ||
                          feature?.properties?.name ||
                          feature?.properties?.distrito ||
                          'Distrito';
            
            layer.bindPopup(`
              <div style="font-family: Arial, sans-serif; padding: 8px; min-width: 150px;">
                <strong style="color: #2c3e50;">🏘️ ${nombre}</strong><br/>
                <small>Distrito de Cochabamba</small>
              </div>
            `);
            
            layer.on('mouseover', () => {
              layer.setStyle(highlightStyle);
              layer.bringToFront();
            });
            
            layer.on('mouseout', () => {
              layer.setStyle(distritoPolygonStyle);
            });
          }}
        />
      )}

      {distritos.map((d) => {
        if (!d.lat || !d.lon) return null;

        const radius = 8 + (Number(d.consumo_m3 || 0) / maxConsumo) * 22;

        return (
          <CircleMarker
            key={d.distrito}
            center={[d.lat, d.lon]}
            radius={radius}
            eventHandlers={{
              click: () => onDistritoClick(d.distrito),
            }}
          >
            <Popup>
              <div className="popup-card">
                <h3>Distrito {d.distrito}</h3>
                <p><b>Consumo:</b> {formatNumber(d.consumo_m3)} m³</p>
                <p><b>Zonas:</b> {d.total_zonas}</p>
                <p><b>Infraestructuras:</b> {d.total_infraestructuras}</p>
                <button onClick={() => onDistritoClick(d.distrito)}>Ver distrito</button>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}

function MapaCuentas({ cuentas, distritoActual, geojson, cuentaSeleccionada, onCuentaClick }) {
  const center = distritoActual?.lat && distritoActual?.lon
    ? [distritoActual.lat, distritoActual.lon]
    : [-17.3895, -66.1568];

  const getDistritoStyle = () => {
    return {
      color: '#2c3e50',
      weight: 2,
      opacity: 0.8,
      fillColor: '#3498db',
      fillOpacity: 0.25
    };
  };

  const highlightStyle = {
    color: '#c0392b',
    weight: 3,
    opacity: 1,
    fillColor: '#e74c3c',
    fillOpacity: 0.5
  };

  const selectedIcon = new L.Icon({
    iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
    iconSize: [35, 57],
    iconAnchor: [17, 57],
    popupAnchor: [1, -34]
  });

  return (
    <MapContainer center={center} zoom={13} className="map big-map">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {distritoActual && <FlyToDistrito lat={distritoActual.lat} lon={distritoActual.lon} />}

      {geojson && geojson.type === "FeatureCollection" && geojson.features && geojson.features.length > 0 && (
        <GeoJSON 
          data={geojson} 
          style={getDistritoStyle}
          onEachFeature={(feature, layer) => {
            const nombre = feature?.properties?.nombre || 
                          feature?.properties?.DISTRITO || 
                          feature?.properties?.NAME ||
                          feature?.properties?.name ||
                          feature?.properties?.distrito ||
                          'Área';
            
            layer.bindPopup(`
              <div style="font-family: Arial, sans-serif; padding: 8px; min-width: 150px;">
                <strong style="color: #2c3e50;">🏘️ ${nombre}</strong><br/>
                <small>Área administrativa de Cochabamba</small>
              </div>
            `);
            
            layer.on('mouseover', () => {
              layer.setStyle(highlightStyle);
              layer.bringToFront();
            });
            
            layer.on('mouseout', () => {
              layer.setStyle(getDistritoStyle());
            });
          }}
        />
      )}

      {cuentas.slice(0, 900).map((c) => {
        if (!c.latitud || !c.longitud) return null;

        const isSelected = cuentaSeleccionada?.cuenta_id === c.cuenta_id;

        return (
          <Marker
            key={c.cuenta_id}
            position={[c.latitud, c.longitud]}
            icon={isSelected ? selectedIcon : markerIcon}
            eventHandlers={{
              click: () => onCuentaClick(c),
            }}
          >
            <Popup>
              <div className="popup-card client-popup">
                <h3>Cuenta: {c.cuenta_id}</h3>
                <p><b>Señor(a):</b> {c.nombre_cliente}</p>
                <p><b>Distrito:</b> {c.distrito}</p>
                <p><b>Zona:</b> {c.zona}</p>
                <p><b>Categoría:</b> {c.categoria}</p>
                <p><b>Medidor:</b> {c.medidor_mac}</p>
                <button onClick={() => onCuentaClick(c)}>
                  Ver consumo y enviar preaviso
                </button>
              </div>
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
}

export default App;