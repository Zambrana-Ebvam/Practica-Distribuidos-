import { apiClient } from "./apiClient";

export async function consultarCuentaTotem(cuentaId, periodo) {
  const response = await apiClient.get(
    `/api/totem/cuenta/${encodeURIComponent(cuentaId)}?periodo=${periodo}`
  );

  return response.data;
}