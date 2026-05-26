import { apiClient } from "./apiClient";

export async function generarPdfPreaviso({ cuenta_id, periodo }) {
  const response = await apiClient.post("/api/preaviso/generar-pdf", {
    cuenta_id,
    periodo,
  });

  return response.data;
}

export async function enviarPreaviso({
  cuenta_id,
  periodo,
  whatsapp,
  sms,
  email,
}) {
  const response = await apiClient.post("/api/preaviso/enviar", {
    cuenta_id,
    periodo,
    whatsapp,
    sms,
    email,
  });

  return response.data;
}