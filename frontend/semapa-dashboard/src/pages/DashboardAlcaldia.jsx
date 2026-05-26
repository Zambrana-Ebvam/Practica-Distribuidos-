import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import KpiCard from "../components/KpiCard";
import MapaGeneral from "../components/MapaGeneral";
import { formatNumber } from "../utils/formatters";

import "../styles/alc_dashboard_alcaldia.css";

function DashboardAlcaldia({ alcaldia, distritoActual, onDistritoClick }) {
  return (
    <section className="alc-page">
      <h2>Dashboard 1 - Alcaldía Municipal / Smart City</h2>

      <p className="lay-section-description">
        Indicadores estratégicos alineados a ODS 6, ODS 11 y ODS 13: impacto
        climático, sostenibilidad hídrica e infraestructura inteligente.
      </p>

      <div className="lay-grid-5">
        <KpiCard
          title="Consumo ciudad"
          value={`${formatNumber(alcaldia?.kpis?.consumo_ciudad_m3)} m³`}
          subtitle="Consumo mensual total"
        />

        <KpiCard
          title="Consumo per cápita"
          value={`${formatNumber(
            alcaldia?.kpis?.consumo_litros_persona_dia_ciudad
          )} L/día`}
          subtitle={alcaldia?.kpis?.clasificacion_consumo_ciudad}
        />

        <KpiCard
          title="Medidores IoT activos"
          value={formatNumber(alcaldia?.kpis?.medidores_iot_activos)}
          subtitle={`${formatNumber(alcaldia?.kpis?.cobertura_iot)}% cobertura IoT`}
        />

        <KpiCard
          title="% sensores con fallas"
          value={`${formatNumber(alcaldia?.kpis?.sensores_falla_pct)}%`}
          subtitle={`${formatNumber(alcaldia?.kpis?.sensores_con_fallas)} sensores`}
        />

        <KpiCard
          title="Zonas críticas"
          value={formatNumber(alcaldia?.kpis?.zonas_criticas_estres_hidrico)}
          subtitle={`${formatNumber(
            alcaldia?.kpis?.alertas_sobreconsumo
          )} alertas por sobreconsumo`}
        />
      </div>

      <div className="lay-dashboard-grid">
        <div className="lay-panel lay-panel-large">
          <h3>Mapa de calor municipal - alertas por sobreconsumo</h3>

          <MapaGeneral
            distritos={alcaldia?.distritos || []}
            distritoActual={distritoActual}
            onDistritoClick={onDistritoClick}
          />
        </div>

        <div className="lay-panel">
          <h3>Consumo vs temperatura</h3>

          <ResponsiveContainer width="100%" height={330}>
            <BarChart data={alcaldia?.obligatorios?.consumo_vs_temperatura || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="distrito" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="consumo_m3" name="Consumo m³" />
              <Bar dataKey="temperatura_c" name="Temperatura °C" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="lay-dashboard-grid">
        <div className="lay-panel">
          <h3>Consumo vs sequía</h3>

          <ResponsiveContainer width="100%" height={330}>
            <BarChart data={alcaldia?.obligatorios?.consumo_vs_sequia || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="distrito" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="consumo_m3" name="Consumo m³" />
              <Bar dataKey="indice_sequia" name="Índice sequía" />
              <Bar dataKey="indice_estres_hidrico" name="Índice estrés hídrico" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="lay-panel">
          <h3>Infraestructura inteligente</h3>

          <ResponsiveContainer width="100%" height={330}>
            <BarChart
              data={alcaldia?.obligatorios?.infraestructura_inteligente || []}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="distrito" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="medidores_iot_activos" name="Medidores IoT activos" />
              <Bar dataKey="sensores_falla_pct" name="% sensores con fallas" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="alc-stacked-panels">
        <div className="lay-panel">
          <h3>Alertas por sobreconsumo</h3>

          {(alcaldia?.obligatorios?.alertas_sobreconsumo || []).length === 0 ? (
            <div className="lay-empty-box">
              No existen alertas por sobreconsumo para el periodo seleccionado.
            </div>
          ) : (
            <div className="lay-table-wrap">
              <table className="alc-small-table">
                <thead>
                  <tr>
                    <th>Dist.</th>
                    <th>Subalcaldía</th>
                    <th>Consumo m³</th>
                    <th>Cuentas</th>
                    <th>Prom. m³</th>
                    <th>Criterio</th>
                    <th>Estado</th>
                    <th>Descripción</th>
                  </tr>
                </thead>

                <tbody>
                  {(alcaldia?.obligatorios?.alertas_sobreconsumo || []).map(
                    (d) => (
                      <tr key={`alerta-${d.distrito}`}>
                        <td>D{d.distrito}</td>
                        <td>{d.subalcaldia}</td>
                        <td>{formatNumber(d.consumo_m3)}</td>
                        <td>{formatNumber(d.total_cuentas)}</td>
                        <td>{formatNumber(d.consumo_promedio_cuenta_m3)}</td>
                        <td>{d.formula_sobreconsumo}</td>
                        <td>
                          <span
                            className={
                              d.estado_sostenibilidad ===
                              "ESTRÉS HÍDRICO CRÍTICO"
                                ? "lay-badge lay-badge-danger"
                                : "lay-badge lay-badge-warning"
                            }
                          >
                            {d.estado_sostenibilidad}
                          </span>
                        </td>
                        <td>{d.descripcion_sostenibilidad}</td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="lay-panel">
          <h3>Zonas críticas por estrés hídrico</h3>

          {(alcaldia?.obligatorios?.zonas_criticas_estres_hidrico || [])
            .length === 0 ? (
            <div className="lay-empty-box">
              No existen zonas críticas para el periodo seleccionado.
            </div>
          ) : (
            <div className="lay-table-wrap">
              <table className="alc-small-table">
                <thead>
                  <tr>
                    <th>Dist.</th>
                    <th>Subalcaldía</th>
                    <th>Índice seq.</th>
                    <th>% fallas</th>
                    <th>Motivo</th>
                    <th>Índice estrés</th>
                    <th>Criticidad</th>
                  </tr>
                </thead>

                <tbody>
                  {(
                    alcaldia?.obligatorios?.zonas_criticas_estres_hidrico || []
                  ).map((d) => (
                    <tr key={`critico-${d.distrito}`}>
                      <td>D{d.distrito}</td>
                      <td>{d.subalcaldia}</td>
                      <td>{formatNumber(d.indice_sequia)}</td>
                      <td>{formatNumber(d.sensores_falla_pct)}%</td>
                      <td>{d.motivo_criticidad}</td>
                      <td>{formatNumber(d.indice_estres_hidrico)}</td>
                      <td>
                        <span
                          className={
                            d.criticidad === "CRÍTICA" ||
                            d.criticidad === "ALTA"
                              ? "lay-badge lay-badge-danger"
                              : "lay-badge lay-badge-warning"
                          }
                        >
                          {d.criticidad}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="lay-panel">
        <h3>Semáforo ODS ciudadano - consumo diario por persona</h3>

        <div className="lay-table-wrap">
          <table className="alc-ods-table">
            <thead>
              <tr>
                <th>Distrito</th>
                <th>Subalcaldía</th>
                <th>Habitantes</th>
                <th>Consumo m³</th>
                <th>Litros/persona/día</th>
                <th>Nivel</th>
                <th>Semáforo</th>
                <th>Medidores activos</th>
                <th>% sensores falla</th>
                <th>Estrés hídrico</th>
              </tr>
            </thead>

            <tbody>
              {(alcaldia?.distritos || []).map((d) => (
                <tr key={`ods-${d.distrito}`}>
                  <td>D{d.distrito}</td>
                  <td>{d.subalcaldia}</td>
                  <td>{formatNumber(d.habitantes)}</td>
                  <td>{formatNumber(d.consumo_m3)}</td>
                  <td>{formatNumber(d.consumo_litros_persona_dia)}</td>
                  <td>{d.nivel_consumo}</td>
                  <td>
                    <span
                      className={
                        d.semaforo_consumo?.includes("ROJO")
                          ? "lay-badge lay-badge-danger"
                          : d.semaforo_consumo === "NARANJA" ||
                            d.semaforo_consumo === "AMARILLO"
                          ? "lay-badge lay-badge-warning"
                          : "lay-badge lay-badge-ok"
                      }
                    >
                      {d.semaforo_consumo}
                    </span>
                  </td>
                  <td>{formatNumber(d.medidores_activos)}</td>
                  <td>{formatNumber(d.sensores_falla_pct)}%</td>
                  <td>{formatNumber(d.indice_estres_hidrico)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export default DashboardAlcaldia;