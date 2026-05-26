# Guía de Despliegue y Configuración - SEMAPA

Esta guía describe cómo ejecutar la plataforma SEMAPA utilizando **Docker Desktop** y **Windows**, facilitando la transición entre un entorno local híbrido (bases de datos en Docker, backend/frontend en Windows) y un entorno completamente contenedorizado con Docker Compose.

---

## 🛠️ Modificaciones Realizadas

Para dar soporte completo y automático a ambos esquemas sin tener que editar el código constantemente, hemos implementado una arquitectura basada en **Variables de Entorno con Fallbacks Inteligentes**:

1. **Frontend (`frontend/semapa-dashboard/.env` y `apiClient.js`)**:
   - Se configuró la URL base del API a `http://localhost:8001` por defecto, que es el puerto estándar expuesto por la API de FastAPI.
2. **Base de Datos (`app/db.py`)**:
   - Ahora lee dinámicamente `CASSANDRA_HOST` (por ejemplo, `cassandra-node1` dentro de Docker) y `CASSANDRA_PORT`.
   - Si no se definen, utiliza `127.0.0.1:9042` de manera automática, ideal para Windows.
3. **Mensajería (`app/mensajeria.py` y `app/worker_mensajes.py`)**:
   - Ahora leen dinámicamente `RABBITMQ_HOST` de la variable `RABBITMQ_HOST`.
   - Si no se define, utiliza `localhost` de manera automática, ideal para Windows.
4. **Dockerfile del Backend (`Dockerfile.backend`)**:
   - Se creó un archivo optimizado de Docker para construir e iniciar el servicio API de FastAPI.

---

## 📂 Opción A: Modo Híbrido (Docker Desktop + Windows Local)

Esta opción es ideal para desarrollo rápido y depuración activa. Los motores de base de datos corren en contenedores ultrarrápidos, y tu frontend/backend corren directamente sobre Windows.

### 1. Iniciar Base de Datos y RabbitMQ en Docker
Ejecuta en la raíz del proyecto para iniciar Cassandra y RabbitMQ:
```powershell
docker-compose up -d
```
> [!NOTE]
> Esto levantará los contenedores de Cassandra (`cassandra-node1`, `cassandra-node2`) y RabbitMQ (`semapa-rabbitmq`), exponiendo los puertos `9042`, `5672` y `15672` a tu máquina Windows en `localhost`.

### 2. Iniciar el Backend (FastAPI API) en Windows
Abre una terminal en la raíz del proyecto, activa tu entorno virtual y ejecuta:
```powershell
venv\Scripts\activate
uvicorn app.api:app --host 127.0.0.1 --port 8001 --reload
```
* **Documentación Interactiva (Swagger/OpenAPI):** [http://localhost:8001/docs](http://localhost:8001/docs)

### 3. Iniciar el Worker de Mensajería en Windows
Abre otra terminal, activa el entorno virtual y ejecuta:
```powershell
venv\Scripts\activate
python app/worker_mensajes.py
```

### 4. Iniciar el Dashboard Analítico (Streamlit) en Windows
Abre otra terminal, activa el entorno virtual y ejecuta:
```powershell
venv\Scripts\activate
streamlit run app/dashboard.py
```
* **Dashboard Streamlit:** [http://localhost:8501](http://localhost:8501)

### 5. Iniciar el Frontend (React/Vite) en Windows
Abre una terminal en `frontend/semapa-dashboard/` y ejecuta:
```powershell
npm install
npm run dev
```
* **Dashboard Web Principal:** [http://localhost:5173](http://localhost:5173)

---

## 🐳 Opción B: Modo Docker Compose Completo (Todo en Docker)

Si quieres meter el backend y la API dentro de Docker Compose para que todo se levante con un solo comando, puedes actualizar tu archivo `docker-compose.yml` para incluir los servicios del backend.

### 1. Actualización de `docker-compose.yml`
Puedes añadir estos servicios a tu `docker-compose.yml`:

```yaml
  backend-api:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: semapa-backend-api
    ports:
      - "8001:8001"
    environment:
      - CASSANDRA_HOST=cassandra-node1
      - CASSANDRA_PORT=9042
      - RABBITMQ_HOST=semapa-rabbitmq
    depends_on:
      - cassandra-node1
      - rabbitmq
    networks:
      - cassandra-net

  backend-worker:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: semapa-backend-worker
    command: python app/worker_mensajes.py
    environment:
      - CASSANDRA_HOST=cassandra-node1
      - CASSANDRA_PORT=9042
      - RABBITMQ_HOST=semapa-rabbitmq
    depends_on:
      - rabbitmq
    networks:
      - cassandra-net
```

### 2. Iniciar todo el ecosistema
Con el `docker-compose.yml` actualizado, solo necesitas ejecutar:
```powershell
docker-compose up -d --build
```
Esto construirá la imagen del backend, configurará las variables de entorno correctas para que se comuniquen internamente a través de la red `cassandra-net` y levantará todo el sistema de forma automatizada y aislada.
