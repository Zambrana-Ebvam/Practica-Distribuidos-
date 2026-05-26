import { useEffect, useMemo, useState } from "react";

import {
  listarMedidoresLectura,
  obtenerDetalleMedidorLectura,
  registrarLecturaMovil,
} from "../services/lecturaService";
import { formatMoney, formatNumber } from "../utils/formatters";

import "../styles/lec_lectura_movil.css";

function LecturaMovil() {
  const [busqueda, setBusqueda] = useState("");
  const [medidoresBase, setMedidoresBase] = useState([]);
  const [seleccionado, setSeleccionado] = useState(null);
  const [lecturaAnterior, setLecturaAnterior] = useState("");
  const [lecturaActual, setLecturaActual] = useState("");
  const [observacion, setObservacion] = useState("");
  const [loading, setLoading] = useState(false);
  const [detalleLoading, setDetalleLoading] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [resultado, setResultado] = useState(null);

  const consumoCalculado = useMemo(() => {
    const anterior = Number(lecturaAnterior);
    const actual = Number(lecturaActual);

    if (!Number.isFinite(anterior) || !Number.isFinite(actual)) return 0;
    return Math.max(actual - anterior, 0);
  }, [lecturaAnterior, lecturaActual]);

  const medidores = useMemo(() => {
    const texto = busqueda.trim().toUpperCase();
    const base = medidoresBase || [];

    if (!texto) {
      return base.slice(0, 80);
    }

    return base
      .filter((medidor) => {
        const campos = [
          medidor.cuenta_id,
          medidor.cliente,
          medidor.zona,
          medidor.medidor_mac,
          medidor.distrito,
        ];

        return campos.some((campo) =>
          String(campo || "").toUpperCase().includes(texto)
        );
      })
      .slice(0, 80);
  }, [medidoresBase, busqueda]);

  useEffect(() => {
    cargarMedidores("");
  }, []);

  async function cargarMedidores(texto = busqueda) {
    try {
      setLoading(true);
      setError("");

      const data = await listarMedidoresLectura({
        busqueda: texto.trim(),
        limit: texto.trim() ? 120 : 80,
        incluirUltima: false,
      });

      setMedidoresBase(data || []);

      if (texto.trim() && data?.length) {
        elegirMedidor(data[0]);
      }
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          "No se pudieron cargar los medidores IoT."
      );
    } finally {
      setLoading(false);
    }
  }

  async function elegirMedidor(medidor) {
    setSeleccionado(medidor);
    setResultado(null);
    setError("");
    setLecturaAnterior(String(medidor?.lectura_sugerida_anterior || 0));
    setLecturaActual("");
    setObservacion("");

    if (!medidor?.medidor_mac) return;

    try {
      setDetalleLoading(true);
      const detalle = await obtenerDetalleMedidorLectura(medidor.medidor_mac);

      setSeleccionado((actual) => {
        if (actual?.medidor_mac !== medidor.medidor_mac) {
          return actual;
        }

        return detalle;
      });

      setLecturaAnterior(String(detalle?.lectura_sugerida_anterior || 0));
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          "No se pudo cargar la ultima lectura del medidor."
      );
    } finally {
      setDetalleLoading(false);
    }
  }

  async function registrarLectura(e) {
    e.preventDefault();

    if (!seleccionado) {
      setError("Seleccione un medidor IoT.");
      return;
    }

    if (lecturaActual === "") {
      setError("Ingrese la lectura actual.");
      return;
    }

    try {
      setGuardando(true);
      setError("");
      setResultado(null);

      const data = await registrarLecturaMovil({
        cuenta_id: seleccionado.cuenta_id,
        medidor_mac: seleccionado.medidor_mac,
        lectura_anterior: Number(lecturaAnterior),
        lectura_actual: Number(lecturaActual),
        observacion,
      });

      setResultado(data);
      setLecturaAnterior(String(data.lectura_actual));
      setLecturaActual("");
      setMedidoresBase((actual) =>
        actual.map((medidor) =>
          medidor.medidor_mac === seleccionado.medidor_mac
            ? {
                ...medidor,
                lectura_sugerida_anterior: data.lectura_actual,
                ultima_lectura: {
                  periodo: data.periodo,
                  fecha: data.fecha_hora,
                  lectura_anterior: data.lectura_anterior,
                  lectura_actual: data.lectura_actual,
                  consumo_m3: data.consumo_m3,
                  radiobase: data.radiobase,
                  status: 2,
                },
              }
            : medidor
        )
      );
      setSeleccionado((actual) =>
        actual
          ? {
              ...actual,
              ultima_lectura: {
                periodo: data.periodo,
                fecha: data.fecha_hora,
                lectura_anterior: data.lectura_anterior,
                lectura_actual: data.lectura_actual,
                consumo_m3: data.consumo_m3,
                radiobase: data.radiobase,
                status: 2,
              },
              lectura_sugerida_anterior: data.lectura_actual,
            }
          : actual
      );
    } catch (err) {
      setError(
        err?.response?.data?.detail || "No se pudo registrar la lectura."
      );
    } finally {
      setGuardando(false);
    }
  }

  return (
    <main className="lec-page">
      <section className="lec-shell">
        <header className="lec-header">
          <div>
            <h1>Lectura movil SEMAPA</h1>
            <p>Buscar medidor IoT, revisar contrato y registrar lectura.</p>
          </div>

          <span>APP MOVIL</span>
        </header>

        <form
          className="lec-search"
          onSubmit={(e) => {
            e.preventDefault();
            if (medidores.length) {
              elegirMedidor(medidores[0]);
              return;
            }

            cargarMedidores(busqueda);
          }}
        >
          <input
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar cuenta, titular, zona o MAC"
          />

          <button type="submit" disabled={loading}>
            {loading ? "Cargando..." : "Buscar"}
          </button>
        </form>

        {error && <div className="lec-alert lec-alert-error">{error}</div>}

        <div className="lec-layout">
          <aside className="lec-list">
            <h2>Medidores IoT</h2>

            {medidores.map((medidor) => (
              <button
                type="button"
                key={`${medidor.cuenta_id}-${medidor.medidor_mac}`}
                className={
                  seleccionado?.medidor_mac === medidor.medidor_mac
                    ? "lec-meter active"
                    : "lec-meter"
                }
                onClick={() => elegirMedidor(medidor)}
              >
                <strong>{medidor.medidor_mac}</strong>
                <span>{medidor.cliente}</span>
                <small>
                  {medidor.cuenta_id} - D{medidor.distrito} - {medidor.zona}
                </small>
              </button>
            ))}

            {!loading && medidores.length === 0 && (
              <div className="lec-empty">No hay medidores para mostrar.</div>
            )}
          </aside>

          <section className="lec-panel">
            {!seleccionado ? (
              <div className="lec-empty lec-empty-large">
                Seleccione un medidor para registrar la lectura.
              </div>
            ) : (
              <>
                <div className="lec-card">
                  <div>
                    <span>Cuenta</span>
                    <strong>{seleccionado.cuenta_id}</strong>
                  </div>

                  <div>
                    <span>Titular</span>
                    <strong>{seleccionado.cliente}</strong>
                  </div>

                  <div>
                    <span>Medidor</span>
                    <strong>{seleccionado.medidor_mac}</strong>
                  </div>

                  <div>
                    <span>Categoria</span>
                    <strong>
                      {seleccionado.categoria} / {seleccionado.subcategoria}
                    </strong>
                  </div>

                  <div>
                    <span>Zona</span>
                    <strong>
                      D{seleccionado.distrito} - {seleccionado.zona}
                    </strong>
                  </div>

                  <div>
                    <span>Estado</span>
                    <strong>{seleccionado.estado_medidor}</strong>
                  </div>
                </div>

                <div className="lec-last">
                  <span>Ultima lectura registrada</span>
                  <strong>
                    {detalleLoading
                      ? "..."
                      : formatNumber(
                          seleccionado.ultima_lectura?.lectura_actual ||
                            seleccionado.lectura_sugerida_anterior ||
                            0
                        )}
                  </strong>
                  <small>
                    {detalleLoading
                      ? "Consultando historial"
                      : seleccionado.ultima_lectura?.periodo || "Sin historial"}
                  </small>
                </div>

                <form className="lec-form" onSubmit={registrarLectura}>
                  <label>
                    <span>Lectura anterior</span>
                    <input
                      type="number"
                      step="0.01"
                      value={lecturaAnterior}
                      onChange={(e) => setLecturaAnterior(e.target.value)}
                    />
                  </label>

                  <label>
                    <span>Lectura actual</span>
                    <input
                      type="number"
                      step="0.01"
                      value={lecturaActual}
                      onChange={(e) => setLecturaActual(e.target.value)}
                      placeholder="Ejemplo: 4325"
                    />
                  </label>

                  <div className="lec-consumption">
                    <span>Consumo calculado</span>
                    <strong>{formatNumber(consumoCalculado)} m3</strong>
                  </div>

                  <label className="lec-full">
                    <span>Observacion</span>
                    <textarea
                      value={observacion}
                      onChange={(e) => setObservacion(e.target.value)}
                      placeholder="Opcional: medidor sin conexion, lectura manual, visita en campo..."
                    />
                  </label>

                  <button type="submit" disabled={guardando}>
                    {guardando ? "Registrando..." : "Registrar lectura"}
                  </button>
                </form>

                {resultado && (
                  <div className="lec-alert lec-alert-ok">
                    <strong>{resultado.mensaje}</strong>
                    <span>
                      Consumo del periodo:{" "}
                      {formatNumber(resultado.consumo_acumulado_periodo_m3)} m3
                    </span>
                    <span>
                      Factura estimada:{" "}
                      {formatMoney(
                        resultado.factura_estimacion?.monto_facturado_bs
                      )}
                    </span>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}

export default LecturaMovil;
