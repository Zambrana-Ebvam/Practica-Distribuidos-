import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import KpiCard from "../components/KpiCard";
import MapaCuentas from "../components/MapaCuentas";
import LoadingState from "../components/LoadingState";
import { API_BASE_URL } from "../services/apiClient";
import { formatMoney, formatNumber } from "../utils/formatters";

import "../styles/map_mapa_distrital.css";

function MapaDistrital({
  mapaLoading,
  filtrosOpciones,
  distritoFiltro,
  setDistritoFiltro,
  zonaFiltro,
  setZonaFiltro,
  categoriaFiltro,
  setCategoriaFiltro,
  subcategoriaFiltro,
  setSubcategoriaFiltro,
  modeloMedidorFiltro,
  setModeloMedidorFiltro,
  estadoMedidorFiltro,
  setEstadoMedidorFiltro,
  estadoContratoFiltro,
  setEstadoContratoFiltro,
  tipoServicioFiltro,
  setTipoServicioFiltro,
  limpiarFiltrosMapa,
  busqueda,
  setBusqueda,
  cuentasFiltradas,
  totalCuentasMapa,
  distritoActual,
  geojson,
  cuentaSeleccionada,
  seleccionarCuenta,
  consumoCuenta,
  consumoPeriodoCuenta,
  whatsapp,
  setWhatsapp,
  sms,
  setSms,
  email,
  setEmail,
  generarPdf,
  enviarPreavisoCuenta,
  resultadoEnvio,
}) {
  const totalFiltrado = cuentasFiltradas?.length || 0;

  return (
    <section className="map-page">
      <div className="map-header-row">
        <div>
          <h2>Mapa de Cochabamba, cuentas, medidores y preavisos</h2>
          <p className="lay-section-description">
            Filtros independientes por distrito, zona, categoría, subcategoría,
            tipo de medidor, estado del medidor, estado del contrato y tipo de
            agua.
          </p>
        </div>

        <div className="map-counter-box">
          <span>Resultados</span>
          <strong>
            {formatNumber(totalFiltrado)} / {formatNumber(totalCuentasMapa)}
          </strong>
        </div>
      </div>

      <div className="lay-panel map-filter-panel">
        <div className="map-filter-grid">
          <label>
            <span>Distrito</span>
            <select
              value={distritoFiltro}
              onChange={(e) => setDistritoFiltro(e.target.value)}
            >
              {(filtrosOpciones?.distritos || ["TODOS"]).map((d) => (
                <option key={d} value={d}>
                  {d === "TODOS" ? "Todos los distritos" : `Distrito ${d}`}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Zona</span>
            <select
              value={zonaFiltro}
              onChange={(e) => setZonaFiltro(e.target.value)}
            >
              {(filtrosOpciones?.zonas || ["TODAS"]).map((z) => (
                <option key={z} value={z}>
                  {z === "TODAS" ? "Todas las zonas" : z}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Categoría</span>
            <select
              value={categoriaFiltro}
              onChange={(e) => setCategoriaFiltro(e.target.value)}
            >
              {(filtrosOpciones?.categorias || ["TODAS"]).map((c) => (
                <option key={c} value={c}>
                  {c === "TODAS" ? "Todas las categorías" : c}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Subcategoría</span>
            <select
              value={subcategoriaFiltro}
              onChange={(e) => setSubcategoriaFiltro(e.target.value)}
            >
              {(filtrosOpciones?.subcategorias || ["TODAS"]).map((s) => (
                <option key={s} value={s}>
                  {s === "TODAS" ? "Todas las subcategorías" : s}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Tipo de medidor</span>
            <select
              value={modeloMedidorFiltro}
              onChange={(e) => setModeloMedidorFiltro(e.target.value)}
            >
              {(filtrosOpciones?.modelosMedidor || ["TODOS"]).map((m) => (
                <option key={m} value={m}>
                  {m === "TODOS" ? "Todos los medidores" : `Modelo ${m}`}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Estado medidor</span>
            <select
              value={estadoMedidorFiltro}
              onChange={(e) => setEstadoMedidorFiltro(e.target.value)}
            >
              {(filtrosOpciones?.estadosMedidor || ["TODOS"]).map((e) => (
                <option key={e} value={e}>
                  {e === "TODOS" ? "Todos los estados" : e}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Estado contrato</span>
            <select
              value={estadoContratoFiltro}
              onChange={(e) => setEstadoContratoFiltro(e.target.value)}
            >
              {(filtrosOpciones?.estadosContrato || ["TODOS"]).map((e) => (
                <option key={e} value={e}>
                  {e === "TODOS" ? "Todos los contratos" : e}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Tipo de agua / servicio</span>
            <select
              value={tipoServicioFiltro}
              onChange={(e) => setTipoServicioFiltro(e.target.value)}
            >
              {(filtrosOpciones?.tiposServicio || ["TODOS"]).map((t) => (
                <option key={t} value={t}>
                  {t === "TODOS" ? "Todos los servicios" : t}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="map-search-row">
          <input
            placeholder="Buscar cuenta, cliente, medidor, catastro o dirección"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />

          <button type="button" onClick={limpiarFiltrosMapa}>
            Limpiar filtros
          </button>
        </div>
      </div>

      {mapaLoading ? (
        <div className="lay-inline-loader">
          <LoadingState
            message="Cargando cuentas del mapa..."
            detail="Consultando cuentas por distrito desde Cassandra"
          />
        </div>
      ) : (
        <div className="map-layout">
          <div className="lay-panel map-panel">
            <MapaCuentas
              cuentas={cuentasFiltradas}
              distritoActual={distritoActual}
              geojson={geojson}
              cuentaSeleccionada={cuentaSeleccionada}
              onCuentaClick={seleccionarCuenta}
            />
          </div>

          <div className="lay-panel map-detail-panel">
            {!cuentaSeleccionada ? (
              <div className="map-empty-state">
                <h3>Selecciona un medidor en el mapa</h3>
                <p>
                  Al hacer clic en un punto del mapa se mostrará la información
                  del cliente y los botones de preaviso.
                </p>
              </div>
            ) : (
              <div>
                <h3>Información del medidor</h3>

                <div className="map-client-box">
                  <p>
                    <b>Cuenta:</b> {cuentaSeleccionada.cuenta_id}
                  </p>
                  <p>
                    <b>Señor(a):</b> {cuentaSeleccionada.nombre_cliente}
                  </p>
                  <p>
                    <b>Distrito:</b> {cuentaSeleccionada.distrito}
                  </p>
                  <p>
                    <b>Zona:</b> {cuentaSeleccionada.zona}
                  </p>
                  <p>
                    <b>Categoría:</b> {cuentaSeleccionada.categoria}{" "}
                    {cuentaSeleccionada.subcategoria}
                  </p>
                  <p>
                    <b>Tipo de medidor:</b>{" "}
                    {cuentaSeleccionada.modelo_medidor || "Sin dato"}
                  </p>
                  <p>
                    <b>Estado medidor:</b>{" "}
                    {cuentaSeleccionada.estado_medidor || "Sin dato"}
                  </p>
                  <p>
                    <b>Estado contrato:</b>{" "}
                    {cuentaSeleccionada.estado_contrato || "Sin dato"}
                  </p>
                  <p>
                    <b>Tipo de servicio:</b>{" "}
                    {cuentaSeleccionada.tipo_servicio || "Sin dato"}
                  </p>
                  <p>
                    <b>Medidor:</b> {cuentaSeleccionada.medidor_mac}
                  </p>
                  <p>
                    <b>Dirección:</b> {cuentaSeleccionada.direccion}
                  </p>
                </div>

                <div className="map-mini-kpis">
                  <KpiCard
                    title="Consumo periodo"
                    value={`${formatNumber(
                      consumoPeriodoCuenta?.consumo_m3 || 0
                    )} m³`}
                  />

                  <KpiCard
                    title="Lecturas"
                    value={formatNumber(
                      consumoPeriodoCuenta?.total_lecturas || 0
                    )}
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

                <div className="map-buttons">
                  <button onClick={generarPdf}>Generar PDF</button>

                  <button
                    className="map-primary-button"
                    onClick={enviarPreavisoCuenta}
                  >
                    Enviar WhatsApp, SMS y Email
                  </button>
                </div>

                {resultadoEnvio && (
                  <div className="map-result-box">
                    <h4>Resultado</h4>
                    <p>{resultadoEnvio.mensaje}</p>

                    {resultadoEnvio.monto_facturado_bs !== undefined && (
                      <p>
                        <b>Monto facturado:</b>{" "}
                        {formatMoney(resultadoEnvio.monto_facturado_bs)}
                      </p>
                    )}

                    {resultadoEnvio.pdfs?.rollo && (
                      <a
                        href={`${API_BASE_URL}/api/download?path=${encodeURIComponent(
                          resultadoEnvio.pdfs.rollo
                        )}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Descargar PDF rollo 55 mm
                      </a>
                    )}

                    {resultadoEnvio.pdfs?.media_carta && (
                      <a
                        href={`${API_BASE_URL}/api/download?path=${encodeURIComponent(
                          resultadoEnvio.pdfs.media_carta
                        )}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Descargar PDF media carta
                      </a>
                    )}

                    {resultadoEnvio.enviados && (
                      <p className="map-success">
                        Mensajes enviados a RabbitMQ:{" "}
                        {resultadoEnvio.enviados.length}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

export default MapaDistrital;