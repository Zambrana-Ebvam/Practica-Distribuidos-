import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Funnel,
  FunnelChart,
  LabelList,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import KpiCard from "../components/KpiCard";
import { PIE_COLORS } from "../data/chartColors";
import { formatMoney, formatNumber } from "../utils/formatters";

import "../styles/con_dashboard_contabilidad.css";

function DashboardContabilidad({ contabilidad, periodo }) {
  const pagosEstimados = Math.round(
    (contabilidad?.efectividad_canales || []).reduce(
      (total, c) =>
        total + ((c.preavisos_emitidos || 0) * (c.conversion_pct || 0)) / 100,
      0
    )
  );

  return (
    <section className="con-page">
      <h2>Dashboard 3 - Departamento Financiero / Contabilidad SEMAPA</h2>

      <p className="lay-section-description">
        Indicadores contables calculados cuenta por cuenta, aplicando categoría,
        subcategoría tarifaria, consumo mensual y estado del contrato.
      </p>

      <div className="lay-grid-5">
        <KpiCard
          title="Monto facturado mensual"
          value={formatMoney(contabilidad?.kpis?.monto_facturado_bs)}
          subtitle={`Periodo ${contabilidad?.kpis?.periodo || periodo}`}
        />

        <KpiCard
          title="Monto recaudado"
          value={formatMoney(contabilidad?.kpis?.monto_recaudado_bs)}
          subtitle={`${formatNumber(contabilidad?.kpis?.recuperacion_pct)}% recuperación`}
        />

        <KpiCard
          title="Cartera vencida"
          value={formatMoney(contabilidad?.kpis?.cartera_vencida_bs)}
          subtitle={`${formatNumber(contabilidad?.kpis?.mora_pct)}% mora`}
        />

        <KpiCard
          title="Preavisos planificados"
          value={formatNumber(contabilidad?.kpis?.preavisos_emitidos)}
          subtitle={`${formatMoney(
            contabilidad?.kpis?.monto_preavisos_mensual_bs ??
              contabilidad?.kpis?.cartera_vencida_bs
          )} monto mensual`}
        />

        <KpiCard
          title="Preavisos enviados"
          value={formatNumber(contabilidad?.kpis?.preavisos_enviados_rabbitmq)}
          subtitle={`${formatNumber(
            contabilidad?.kpis?.mensajes_enviados_rabbitmq
          )} mensajes RabbitMQ`}
        />
      </div>

      <div className="lay-dashboard-grid">
        <div className="lay-panel">
          <h3>Monto facturado / preavisos mensual</h3>

          <div className="con-preaviso-summary">
            <div>
              <span>Monto facturado mensual</span>
              <strong>{formatMoney(contabilidad?.kpis?.monto_facturado_bs)}</strong>
            </div>

            <div>
              <span>Monto en preavisos</span>
              <strong>
                {formatMoney(
                  contabilidad?.kpis?.monto_preavisos_mensual_bs ??
                    contabilidad?.kpis?.cartera_vencida_bs
                )}
              </strong>
            </div>

            <div>
              <span>Preavisos emitidos</span>
              <strong>{formatNumber(contabilidad?.kpis?.preavisos_emitidos)}</strong>
            </div>

            <div>
              <span>Enviados por RabbitMQ</span>
              <strong>
                {formatNumber(contabilidad?.kpis?.preavisos_enviados_rabbitmq)}
              </strong>
            </div>

            <div>
              <span>Monto con evidencia RabbitMQ</span>
              <strong>
                {formatMoney(contabilidad?.kpis?.monto_preavisos_enviados_bs)}
              </strong>
            </div>
          </div>
        </div>

        <div className="lay-panel">
          <h3>Facturación por tarifa</h3>

          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={contabilidad?.facturacion_tarifa || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="codigo_tarifa" />
              <YAxis />
              <Tooltip formatter={(value) => formatMoney(value)} />
              <Legend />
              <Bar dataKey="monto_facturado_bs" name="Facturado Bs" />
              <Bar dataKey="cartera_vencida_bs" name="Cartera Bs" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="lay-panel">
          <h3>Facturación por categoría</h3>

          <ResponsiveContainer width="100%" height={350}>
            <PieChart>
              <Pie
                data={contabilidad?.facturacion_categoria || []}
                dataKey="monto_facturado_bs"
                nameKey="categoria"
                outerRadius={110}
                innerRadius={45}
                label={(entry) =>
                  `${entry.categoria}: ${formatMoney(entry.monto_facturado_bs)}`
                }
              >
                {(contabilidad?.facturacion_categoria || []).map(
                  (entry, index) => (
                    <Cell
                      key={`con-cat-${index}`}
                      fill={PIE_COLORS[index % PIE_COLORS.length]}
                    />
                  )
                )}
              </Pie>

              <Tooltip formatter={(value) => formatMoney(value)} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="lay-dashboard-grid">
        <div className="lay-panel">
          <h3>Facturación por distrito</h3>

          <div className="lay-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Distrito</th>
                  <th>Monto facturado</th>
                  <th>Monto recaudado</th>
                  <th>Cartera vencida</th>
                </tr>
              </thead>

              <tbody>
                {(contabilidad?.obligatorios?.facturacion_por_distrito || []).map(
                  (d) => (
                    <tr key={`fact-dist-${d.distrito}`}>
                      <td>D{d.distrito}</td>
                      <td>{formatMoney(d.monto_facturado_bs)}</td>
                      <td>{formatMoney(d.monto_recaudado_bs)}</td>
                      <td>
                        <span className="lay-badge lay-badge-danger">
                          {formatMoney(d.cartera_vencida_bs)}
                        </span>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="lay-panel">
          <h3>Preavisos y cobranza preventiva</h3>

          <ResponsiveContainer width="100%" height={330}>
            <FunnelChart>
              <Tooltip />

              <Funnel
                dataKey="cantidad"
                nameKey="etapa"
                data={[
                  {
                    etapa: "Cuentas morosas",
                    cantidad: contabilidad?.kpis?.cuentas_morosas || 0,
                  },
                  {
                    etapa: "Preavisos emitidos",
                    cantidad: contabilidad?.kpis?.preavisos_emitidos || 0,
                  },
                  {
                    etapa: "Pagos estimados",
                    cantidad: pagosEstimados,
                  },
                ]}
              >
                <LabelList
                  position="right"
                  fill="#0f172a"
                  stroke="none"
                  dataKey="etapa"
                />
              </Funnel>
            </FunnelChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="lay-dashboard-grid">
        <div className="lay-panel">
          <h3>Cartera vencida por zona</h3>

          <ResponsiveContainer width="100%" height={360}>
            <BarChart
              data={contabilidad?.facturacion_zona_top10 || []}
              layout="vertical"
              margin={{ top: 5, right: 20, left: 70, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis type="number" />
              <YAxis dataKey="zona" type="category" width={130} />
              <Tooltip formatter={(value) => formatMoney(value)} />
              <Bar dataKey="cartera_vencida_bs" name="Cartera vencida Bs" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="lay-panel">
          <h3>Efectividad por canal</h3>

          <div className="lay-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Canal</th>
                  <th>Preavisos</th>
                  <th>Cartera asignada</th>
                  <th>Conversión</th>
                  <th>Recuperación estimada</th>
                </tr>
              </thead>

              <tbody>
                {(contabilidad?.efectividad_canales || []).map((c) => (
                  <tr key={c.canal}>
                    <td>
                      <span
                        className={
                          c.canal === contabilidad?.kpis?.mejor_canal_cobranza
                            ? "lay-badge lay-badge-ok"
                            : "lay-badge lay-badge-info"
                        }
                      >
                        {c.canal}
                      </span>
                    </td>
                    <td>{formatNumber(c.preavisos_emitidos)}</td>
                    <td>{formatMoney(c.monto_cartera_bs)}</td>
                    <td>{formatNumber(c.conversion_pct)}%</td>
                    <td>{formatMoney(c.recuperacion_estimada_bs)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="lay-panel">
        <h3>Grandes deudores</h3>

        <div className="lay-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Cuenta</th>
                <th>Cliente</th>
                <th>Zona</th>
                <th>Tarifa</th>
                <th>Estado contrato</th>
                <th>Consumo</th>
                <th>Cartera vencida</th>
                <th>Preaviso</th>
              </tr>
            </thead>

            <tbody>
              {(contabilidad?.grandes_deudores || []).slice(0, 20).map((d) => (
                <tr key={d.cuenta_id}>
                  <td>{d.cuenta_id}</td>
                  <td>{d.cliente}</td>
                  <td>{d.zona}</td>
                  <td>{d.codigo_tarifa}</td>
                  <td>
                    <span className="lay-badge lay-badge-warning">
                      {d.estado_contrato}
                    </span>
                  </td>
                  <td>{formatNumber(d.consumo_m3)} m³</td>
                  <td>
                    <span className="lay-badge lay-badge-danger">
                      {formatMoney(d.cartera_vencida_bs)}
                    </span>
                  </td>
                  <td>
                    {d.debe_emitir_preaviso ? (
                      <span className="lay-badge lay-badge-danger">Emitido</span>
                    ) : (
                      <span className="lay-badge lay-badge-ok">No aplica</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="lay-panel">
        <h3>Resumen contable por categoría</h3>

        <div className="lay-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Categoría</th>
                <th>Cuentas</th>
                <th>Consumo m³</th>
                <th>Facturado</th>
                <th>Recaudado</th>
                <th>Cartera vencida</th>
                <th>Ticket promedio</th>
              </tr>
            </thead>

            <tbody>
              {(contabilidad?.facturacion_categoria || []).map((c) => (
                <tr key={c.categoria}>
                  <td>{c.categoria}</td>
                  <td>{formatNumber(c.cuentas)}</td>
                  <td>{formatNumber(c.consumo_m3)} m³</td>
                  <td>{formatMoney(c.monto_facturado_bs)}</td>
                  <td>{formatMoney(c.monto_recaudado_bs)}</td>
                  <td>{formatMoney(c.cartera_vencida_bs)}</td>
                  <td>{formatMoney(c.ticket_promedio_bs)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export default DashboardContabilidad;
