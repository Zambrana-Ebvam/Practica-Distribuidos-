import { useEffect } from "react";
import {
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

import { formatNumber } from "../utils/formatters";
import "../styles/map_mapa_distrital.css";

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

function colorPorSostenibilidad(consumoPromedioCuenta) {
  const consumo = Number(consumoPromedioCuenta || 0);

  if (consumo < 10) {
    return {
      fill: "#1a1a2e",
      stroke: "#16213e",
      label: "ESCASEZ CRÍTICA",
      className: "map-status-critical-blue",
      prioridad: 5,
      intensidad: 0.95,
    };
  }

  if (consumo <= 15) {
    return {
      fill: "#0f3460",
      stroke: "#05234b",
      label: "BAJO",
      className: "map-status-low",
      prioridad: 4,
      intensidad: 0.8,
    };
  }

  if (consumo <= 20) {
    return {
      fill: "#00d4ff",
      stroke: "#00a8cc",
      label: "SOSTENIBLE",
      className: "map-status-sustainable",
      prioridad: 1,
      intensidad: 0.7,
    };
  }

  if (consumo <= 25) {
    return {
      fill: "#22c55e",
      stroke: "#16a34a",
      label: "NORMAL BAJO",
      className: "map-status-normal-low",
      prioridad: 2,
      intensidad: 0.7,
    };
  }

  if (consumo <= 30) {
    return {
      fill: "#84cc16",
      stroke: "#65a30d",
      label: "NORMAL",
      className: "map-status-normal",
      prioridad: 3,
      intensidad: 0.75,
    };
  }

  if (consumo <= 35) {
    return {
      fill: "#eab308",
      stroke: "#ca8a04",
      label: "NORMAL ALTO",
      className: "map-status-normal-high",
      prioridad: 3,
      intensidad: 0.8,
    };
  }

  if (consumo <= 40) {
    return {
      fill: "#f97316",
      stroke: "#d97706",
      label: "ALERTA",
      className: "map-status-alert",
      prioridad: 4,
      intensidad: 0.85,
    };
  }

  if (consumo <= 45) {
    return {
      fill: "#fb923c",
      stroke: "#c2410c",
      label: "SOBRECONSUMO",
      className: "map-status-over",
      prioridad: 4,
      intensidad: 0.9,
    };
  }

  return {
    fill: "#dc2626",
    stroke: "#7f1d1d",
    label: "ESTRÉS CRÍTICO",
    className: "map-status-critical",
    prioridad: 5,
    intensidad: 0.95,
  };
}

function MapaGeneral({ distritos = [], distritoActual, onDistritoClick }) {
  const center =
    distritoActual?.lat && distritoActual?.lon
      ? [distritoActual.lat, distritoActual.lon]
      : [-17.3895, -66.1568];

  return (
    <div className="map-general-box">
      <div className="map-legend-horizontal">
        <strong>Mapa de calor - Consumo promedio por cuenta</strong>
        <p>Basado en datos reales de consumo de agua en Cochabamba</p>

        <div className="map-legend-items">
          <div className="map-legend-item">
            <span className="map-dot map-dot-critical-blue" />
            <small>&lt; 10 m³</small>
            <b>Escasez</b>
          </div>

          <div className="map-legend-item">
            <span className="map-dot map-dot-low" />
            <small>10-15 m³</small>
            <b>Bajo</b>
          </div>

          <div className="map-legend-item">
            <span className="map-dot map-dot-sustainable" />
            <small>15-20 m³</small>
            <b>Sostenible</b>
          </div>

          <div className="map-legend-item">
            <span className="map-dot map-dot-normal-low" />
            <small>20-25 m³</small>
            <b>Normal bajo</b>
          </div>

          <div className="map-legend-item">
            <span className="map-dot map-dot-normal" />
            <small>25-30 m³</small>
            <b>Normal</b>
          </div>

          <div className="map-legend-item">
            <span className="map-dot map-dot-normal-high" />
            <small>30-35 m³</small>
            <b>Normal alto</b>
          </div>

          <div className="map-legend-item">
            <span className="map-dot map-dot-alert" />
            <small>35-40 m³</small>
            <b>Alerta</b>
          </div>

          <div className="map-legend-item">
            <span className="map-dot map-dot-over" />
            <small>40-45 m³</small>
            <b>Sobreconsumo</b>
          </div>

          <div className="map-legend-item">
            <span className="map-dot map-dot-critical" />
            <small>&gt; 45 m³</small>
            <b>Crítico</b>
          </div>
        </div>
      </div>

      <div className="map-wrapper">
        <MapContainer center={center} zoom={12} className="map-map">
          <TileLayer
            attribution="OpenStreetMap"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {distritoActual && (
            <FlyToDistrito lat={distritoActual.lat} lon={distritoActual.lon} />
          )}

          {distritos.map((d) => {
            if (!d.lat || !d.lon) return null;

            const consumoPromedioCuenta = Number(
              d.consumo_promedio_cuenta_m3 || 0
            );
            const color = colorPorSostenibilidad(consumoPromedioCuenta);
            const radius = 15 + color.prioridad * 8;

            return (
              <CircleMarker
                key={d.distrito}
                center={[d.lat, d.lon]}
                radius={radius}
                pathOptions={{
                  color: color.stroke,
                  fillColor: color.fill,
                  fillOpacity: color.intensidad,
                  weight: 2,
                }}
                eventHandlers={{
                  click: () => onDistritoClick(d.distrito),
                }}
              >
                <Popup>
                  <div className="map-popup-card map-popup-resumen">
                    <h3>Distrito {d.distrito}</h3>

                    <p>
                      <b>Subalcaldía:</b> {d.subalcaldia}
                    </p>

                    <div className="map-popup-status">
                      <span className={`map-status-pill ${color.className}`}>
                        {color.label}
                      </span>
                    </div>

                    <hr />

                    <p>
                      <b>Consumo promedio:</b>
                    </p>

                    <p className={`map-popup-highlight ${color.className}`}>
                      {formatNumber(consumoPromedioCuenta)} m³/cuenta/mes
                    </p>

                    <p>
                      <b>Consumo total:</b> {formatNumber(d.consumo_m3)} m³
                    </p>

                    <p>
                      <b>Total cuentas:</b> {formatNumber(d.total_cuentas)}
                    </p>

                    <p>
                      <b>Consumo L/persona/día:</b>{" "}
                      {formatNumber(d.consumo_litros_persona_dia)}
                    </p>

                    <hr />

                    <p>
                      <b>Medidores activos:</b>{" "}
                      {formatNumber(d.medidores_iot_activos)}
                    </p>

                    <p>
                      <b>Sensores con fallas:</b>{" "}
                      {formatNumber(d.sensores_falla_pct)}%
                    </p>

                    <p>
                      <b>Índice estrés hídrico:</b>{" "}
                      {formatNumber(d.indice_estres_hidrico)}
                    </p>

                    <hr />

                    <p>
                      <b>Interpretación:</b>
                    </p>

                    <small>{d.descripcion_sostenibilidad}</small>

                    <button onClick={() => onDistritoClick(d.distrito)}>
                      Ver detalles del distrito
                    </button>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
}

export default MapaGeneral;