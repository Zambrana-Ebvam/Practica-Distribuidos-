import { useEffect } from "react";
import {
  GeoJSON,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import "../styles/map_mapa_distrital.css";

const markerIcon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

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

function MapaCuentas({
  cuentas = [],
  distritoActual,
  geojson,
  cuentaSeleccionada,
  onCuentaClick,
}) {
  const center =
    distritoActual?.lat && distritoActual?.lon
      ? [distritoActual.lat, distritoActual.lon]
      : [-17.3895, -66.1568];

  return (
    <MapContainer center={center} zoom={13} className="map-map map-big-map">
      <TileLayer
        attribution="OpenStreetMap"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {distritoActual && (
        <FlyToDistrito lat={distritoActual.lat} lon={distritoActual.lon} />
      )}

      {geojson?.type && <GeoJSON data={geojson} />}

      {cuentas.slice(0, 900).map((c) => {
        if (!c.latitud || !c.longitud) return null;

        const selected = cuentaSeleccionada?.cuenta_id === c.cuenta_id;

        return (
          <Marker
            key={c.cuenta_id}
            position={[c.latitud, c.longitud]}
            icon={markerIcon}
            opacity={selected ? 1 : 0.85}
            eventHandlers={{
              click: () => onCuentaClick(c),
            }}
          >
            <Popup>
              <div className="map-popup-card map-client-popup">
                <h3>Cuenta: {c.cuenta_id}</h3>

                <p>
                  <b>Señor(a):</b> {c.nombre_cliente}
                </p>

                <p>
                  <b>Distrito:</b> {c.distrito}
                </p>

                <p>
                  <b>Zona:</b> {c.zona}
                </p>

                <p>
                  <b>Categoría:</b> {c.categoria}
                </p>

                <p>
                  <b>Medidor:</b> {c.medidor_mac}
                </p>

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

export default MapaCuentas;