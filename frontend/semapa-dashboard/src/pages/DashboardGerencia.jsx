import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import KpiCard from "../components/KpiCard";
import { BAR_COLORS, PIE_COLORS } from "../data/chartColors";
import { formatNumber } from "../utils/formatters";

import "../styles/ger_dashboard_gerencia.css";

function DashboardGerencia({ gerencia, periodo }) {
  return (
    <section className="ger-page">
      <h2>Dashboard 2 - Gerencia / Directorio SEMAPA</h2>

      <p className="lay-section-description">
        Control operativo del consumo, parque de medidores, sensores con errores
        y productividad de lecturas registradas.
      </p>

      <div className="lay-grid-5">
        <KpiCard
          title="Consumo acumulado"
          value={`${formatNumber(gerencia?.kpis?.total_consumo_acumulado_m3)} m³`}
          subtitle={`Periodo ${gerencia?.kpis?.periodo || periodo}`}
        />

        <KpiCard
          title="Medidores activos"
          value={formatNumber(gerencia?.kpis?.total_medidores_activos)}
          subtitle={`${formatNumber(gerencia?.kpis?.total_medidores)} medidores totales`}
        />

        <KpiCard
          title="Sensores con errores"
          value={formatNumber(gerencia?.kpis?.sensores_con_errores)}
          subtitle={`${formatNumber(gerencia?.kpis?.sensores_error_pct)}% del parque IoT`}
        />

        <KpiCard
          title="Lecturas por app móvil"
          value={formatNumber(gerencia?.kpis?.lecturas_app_movil)}
          subtitle={`${formatNumber(gerencia?.kpis?.lecturas_app_movil_pct)}% de lecturas`}
        />

        <KpiCard
          title="Total cuentas"
          value={formatNumber(gerencia?.kpis?.total_cuentas)}
          subtitle={`Distrito ${gerencia?.kpis?.distrito || "-"}`}
        />
      </div>

      <div className="lay-dashboard-grid">
        <div className="lay-panel">
          <h3>Consumo por bloques horarios</h3>

          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={gerencia?.horas || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="bloque_horario" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="consumo_m3" name="Consumo m³" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="lay-panel">
          <h3>Consumo total por categoría tarifaria</h3>

          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={gerencia?.categorias || []}
                dataKey="consumo_m3"
                nameKey="categoria"
                outerRadius={110}
                innerRadius={45}
                label={(entry) =>
                  `${entry.categoria}: ${formatNumber(
                    entry.porcentaje_consumo
                  )}%`
                }
              >
                {(gerencia?.categorias || []).map((entry, index) => (
                  <Cell
                    key={`ger-cat-${index}`}
                    fill={PIE_COLORS[index % PIE_COLORS.length]}
                  />
                ))}
              </Pie>

              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>

          <div className="lay-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Categoría</th>
                  <th>Consumo m³</th>
                  <th>% consumo</th>
                  <th>Cuentas</th>
                  <th>% cuentas</th>
                  <th>Promedio m³/cuenta</th>
                </tr>
              </thead>

              <tbody>
                {(gerencia?.categorias || []).map((c) => (
                  <tr key={c.categoria}>
                    <td>{c.categoria}</td>
                    <td>{formatNumber(c.consumo_m3)} m³</td>
                    <td>{formatNumber(c.porcentaje_consumo)}%</td>
                    <td>{formatNumber(c.total_cuentas)}</td>
                    <td>{formatNumber(c.porcentaje_cuentas)}%</td>
                    <td>{formatNumber(c.promedio_m3_cuenta)} m³</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="lay-dashboard-grid">
        <div className="lay-panel">
          <h3>Top 10 zonas de mayor demanda</h3>

          <ResponsiveContainer width="100%" height={380}>
            <BarChart
              data={gerencia?.top_zonas || []}
              layout="vertical"
              margin={{ top: 5, right: 20, left: 50, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis type="number" stroke="#475569" />
              <YAxis
                dataKey="zona"
                type="category"
                stroke="#475569"
                width={120}
              />
              <Tooltip />

              <Bar
                dataKey="consumo_m3"
                name="Consumo m³"
                radius={[0, 10, 10, 0]}
              >
                {(gerencia?.top_zonas || []).map((entry, index) => (
                  <Cell
                    key={`ger-zona-${index}`}
                    fill={BAR_COLORS[index % BAR_COLORS.length]}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="lay-panel">
          <h3>Sensores con errores por modelo</h3>

          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={gerencia?.fallas_modelo || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="modelo_medidor" stroke="#475569" />
              <YAxis stroke="#475569" />
              <Tooltip />
              <Legend />
              <Bar dataKey="activos" name="Activos" />
              <Bar dataKey="sensores_con_error" name="Con error" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="lay-panel">
        <h3>Tabla de anomalías</h3>

        <div className="lay-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Cuenta</th>
                <th>Cliente</th>
                <th>Zona</th>
                <th>Categoría</th>
                <th>Medidor</th>
                <th>Estado</th>
                <th>Consumo</th>
                <th>Anomalía</th>
                <th>Prioridad</th>
              </tr>
            </thead>

            <tbody>
              {(gerencia?.anomalias || []).map((a) => (
                <tr key={`${a.cuenta_id}-${a.anomalia}`}>
                  <td>{a.cuenta_id}</td>
                  <td>{a.nombre_cliente}</td>
                  <td>{a.zona}</td>
                  <td>{a.categoria}</td>
                  <td>{a.medidor_mac}</td>
                  <td>{a.estado_medidor}</td>
                  <td>{formatNumber(a.consumo_m3)} m³</td>
                  <td>
                    <span className="lay-badge lay-badge-warning">
                      {a.anomalia}
                    </span>
                  </td>
                  <td>
                    <span
                      className={
                        a.prioridad === "ALTA"
                          ? "lay-badge lay-badge-danger"
                          : "lay-badge lay-badge-warning"
                      }
                    >
                      {a.prioridad}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="lay-dashboard-grid">
        <div className="lay-panel">
          <h3>Lecturas registradas por canal</h3>

          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={[
                  {
                    canal: "IoT automático",
                    cantidad: gerencia?.kpis?.lecturas_iot || 0,
                  },
                  {
                    canal: "App móvil",
                    cantidad: gerencia?.kpis?.lecturas_app_movil || 0,
                  },
                  {
                    canal: "Fallidas",
                    cantidad: gerencia?.kpis?.lecturas_fallidas || 0,
                  },
                ]}
                dataKey="cantidad"
                nameKey="canal"
                outerRadius={95}
                label
              >
                {[0, 1, 2].map((index) => (
                  <Cell key={`ger-canal-${index}`} />
                ))}
              </Pie>

              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="lay-panel">
          <h3>Detalle de sensores con errores</h3>

          <div className="lay-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Estado</th>
                  <th>Sensores</th>
                  <th>Lecturas asociadas</th>
                  <th>Consumo asociado</th>
                </tr>
              </thead>

              <tbody>
                {(gerencia?.sensores_error || []).map((e) => (
                  <tr key={e.estado_error}>
                    <td>{e.estado_error}</td>
                    <td>{formatNumber(e.total_sensores)}</td>
                    <td>{formatNumber(e.lecturas_asociadas)}</td>
                    <td>{formatNumber(e.consumo_m3_asociado)} m³</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}

export default DashboardGerencia;