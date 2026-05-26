# SEMAPA - Guía de Ejecución Rápida 🚀

Esta guía contiene las instrucciones simplificadas para arrancar los componentes principales de la plataforma SEMAPA (Backend API, Worker de mensajería y Frontend).

---🐍 1. Backend (FastAPI con Uvicorn)
Para iniciar el servidor de la API en el puerto 8001 sin errores de importación en Windows:

powershell
$env:PYTHONPATH="app"
venv\Scripts\python -m uvicorn app.api:app --host 127.0.0.1 --port 8001 --reload
Documentación Swagger: http://127.0.0.1:8001/docs
✉️ 2. Worker de Mensajes (RabbitMQ Queue)
Para ejecutar el worker que procesa la cola de preavisos:

powershell
venv\Scripts\python app/worker_mensajes.py
💻 3. Frontend (React con npm)
Para iniciar el servidor de desarrollo del Dashboard principal:

powershell
cd frontend/semapa-dashboard
npm run dev
Dashboard URL: http://127.0.0.1:5173/
Resumen de lo ejecutado en segundo plano
API de FastAPI: Activa y escuchando en el puerto 8001.
Worker de mensajería: Activo y procesando cola de RabbitMQ.
Frontend (Vite): Activo y escuchando en el puerto 5173.

## 🐋 0. Prerrequisitos (Bases de Datos y Colas)

Asegúrate de que los contenedores de Docker para Cassandra y RabbitMQ estén iniciados:

```powershell
docker-compose up -d
```

---

## 🐍 1. Servidor Backend (FastAPI + Uvicorn)

El backend de FastAPI utiliza `uvicorn` para servirse. Dado que la lógica interna del paquete está dentro del directorio `app/`, es necesario definir la variable de entorno `PYTHONPATH` al ejecutar el comando para evitar errores de importación de módulos (`ModuleNotFoundError: No module named 'db'`).

### Comando de ejecución en Windows (PowerShell):
```powershell
$env:PYTHONPATH="app"
venv\Scripts\python -m uvicorn app.api:app --host 127.0.0.1 --port 8001 --reload
```

*   **URL de la API:** [http://127.0.0.1:8001](http://127.0.0.1:8001)
*   **Documentación Interactiva (Swagger/OpenAPI):** [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

---

## ✉️ 2. Worker de Mensajes

El worker se encarga de escuchar y procesar la cola de mensajes de RabbitMQ (`semapa_preavisos`), persistiendo los resultados en formato JSON y gestionando los envíos.

### Comando de ejecución en Windows (PowerShell):
```powershell
venv\Scripts\python app/worker_mensajes.py
```

---

## 💻 3. Frontend Dashboard (React + Vite)

El frontend está desarrollado con React y Vite. Asegúrate de tener las dependencias instaladas y ejecuta el servidor de desarrollo.

### Comandos de ejecución:
```powershell
# 1. Navegar al directorio del frontend
cd frontend/semapa-dashboard

# 2. Instalar dependencias (solo la primera vez)
npm install

# 3. Arrancar el servidor de desarrollo
npm run dev
```

*   **URL del Dashboard principal:** [http://127.0.0.1:5173/](http://127.0.0.1:5173/)
