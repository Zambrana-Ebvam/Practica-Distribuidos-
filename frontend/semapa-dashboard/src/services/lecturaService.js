import { apiClient } from "./apiClient";

export async function listarMedidoresLectura({
  busqueda = "",
  distrito = "",
  limit = 60,
  incluirUltima = false,
} = {}) {
  const params = new URLSearchParams();

  if (busqueda) params.set("busqueda", busqueda);
  if (distrito) params.set("distrito", distrito);
  params.set("limit", String(limit));
  params.set("incluir_ultima", incluirUltima ? "true" : "false");

  const response = await apiClient.get(
    `/api/lectura-movil/medidores?${params.toString()}`
  );

  return response.data;
}

export async function obtenerDetalleMedidorLectura(medidorMac) {
  const response = await apiClient.get(
    `/api/lectura-movil/medidores/${encodeURIComponent(medidorMac)}/detalle`
  );
  return response.data;
}

export async function registrarLecturaMovil(payload) {
  const response = await apiClient.post("/api/lectura-movil/registrar", payload);
  return response.data;
}
