import { useState } from "react";

import { consultarCuentaTotem } from "../services/totemService";
import { formatMoney, formatNumber } from "../utils/formatters";

import "../styles/tot_totem_autoservicio.css";

function TotemAutoservicio({ periodo }) {
  const [totemCuenta, setTotemCuenta] = useState("");
  const [totemResultado, setTotemResultado] = useState(null);
  const [totemError, setTotemError] = useState("");
  const [totemLoading, setTotemLoading] = useState(false);

  async function consultarTotem(e) {
    e.preventDefault();

    const cuenta = String(totemCuenta || "").trim();

    if (!cuenta) {
      setTotemError("Ingrese un número de cuenta.");
      setTotemResultado(null);
      return;
    }

    try {
      setTotemLoading(true);
      setTotemError("");
      setTotemResultado(null);

      const data = await consultarCuentaTotem(cuenta, periodo);

      setTotemResultado(data);
    } catch (error) {
      setTotemError(
        error?.response?.data?.detail ||
          "No se encontró información para la cuenta ingresada."
      );
      setTotemResultado(null);
    } finally {
      setTotemLoading(false);
    }
  }

  return (
    <div className="tot-page">
      <div className="tot-card">
        <div className="tot-header">
          <h1>Tótem de Consulta SEMAPA</h1>
          <p>
            Consulte su consumo y estado de deuda ingresando su número de cuenta.
          </p>
        </div>

        <form className="tot-form" onSubmit={consultarTotem}>
          <input
            value={totemCuenta}
            onChange={(e) => setTotemCuenta(e.target.value)}
            placeholder="Ejemplo: CT-00000001"
          />

          <button type="submit" disabled={totemLoading}>
            {totemLoading ? "Consultando..." : "Consultar"}
          </button>
        </form>

        {totemError && <div className="tot-error">{totemError}</div>}

        {totemResultado && (
          <div className="tot-result">
            <div
              className={
                totemResultado.estado_deuda === "DEBE"
                  ? "tot-status tot-status-danger"
                  : "tot-status tot-status-ok"
              }
            >
              {totemResultado.estado_deuda === "DEBE"
                ? "Tiene deuda pendiente"
                : "No tiene deuda pendiente"}
            </div>

            <div className="tot-grid">
              <div>
                <span>Cuenta</span>
                <strong>{totemResultado.cuenta_id}</strong>
              </div>

              <div>
                <span>Periodo</span>
                <strong>{totemResultado.periodo}</strong>
              </div>

              <div>
                <span>Titular</span>
                <strong>{totemResultado.cliente}</strong>
              </div>

              <div>
                <span>Zona</span>
                <strong>{totemResultado.zona}</strong>
              </div>

              <div>
                <span>Categoría</span>
                <strong>
                  {totemResultado.categoria} / {totemResultado.subcategoria}
                </strong>
              </div>

              <div>
                <span>Medidor</span>
                <strong>{totemResultado.medidor || "Sin dato"}</strong>
              </div>

              <div>
                <span>Consumo</span>
                <strong>{formatNumber(totemResultado.consumo_m3)} m³</strong>
              </div>

              <div>
                <span>Monto facturado</span>
                <strong>
                  {formatMoney(totemResultado.monto_facturado_bs)}
                </strong>
              </div>

              <div>
                <span>Monto pendiente</span>
                <strong>{formatMoney(totemResultado.monto_pendiente_bs)}</strong>
              </div>

              <div>
                <span>Estado contrato</span>
                <strong>{totemResultado.estado_contrato}</strong>
              </div>
            </div>

            <div className="tot-message">{totemResultado.mensaje}</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default TotemAutoservicio;