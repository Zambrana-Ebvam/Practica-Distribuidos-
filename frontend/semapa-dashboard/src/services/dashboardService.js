import { apiClient } from "./apiClient";

export async function getDistritos() {
  const response = await apiClient.get("/api/distritos");
  return response.data;
}

export async function getDashboardAlcaldia() {
  const response = await apiClient.get("/api/dashboard/alcaldia");
  return response.data;
}

export async function getResumenDistrito(distrito) {
  const response = await apiClient.get(`/api/distritos/${distrito}/resumen`);
  return response.data;
}

export async function getCuentasDistrito(distrito, limit = 1500) {
  const response = await apiClient.get(
    `/api/distritos/${distrito}/cuentas?limit=${limit}`
  );
  return response.data;
}

export async function getDashboardGerencia(distrito, periodo) {
  const response = await apiClient.get(
    `/api/dashboard/gerencia/${distrito}?periodo=${periodo}`
  );
  return response.data;
}

export async function getDashboardContabilidad(distrito, periodo) {
  const response = await apiClient.get(
    `/api/dashboard/contabilidad/${distrito}?periodo=${periodo}`
  );
  return response.data;
}

export async function getCuentaDetalle(cuentaId) {
  const response = await apiClient.get(`/api/cuentas/${cuentaId}`);
  return response.data;
}

export async function getConsumoCuenta(cuentaId) {
  const response = await apiClient.get(`/api/cuentas/${cuentaId}/consumo`);
  return response.data;
}