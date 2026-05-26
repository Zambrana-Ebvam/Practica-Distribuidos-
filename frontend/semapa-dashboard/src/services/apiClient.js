import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8001";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,

  // Antes estaba en 20 segundos.
  // Con Cassandra y dashboards pesados necesitamos más tiempo.
  timeout: 300000,
});

export { API_BASE_URL };