import "../styles/app_layout.css";

function LoadingState({
  message = "Cargando plataforma SEMAPA...",
  detail = "Consultando datos distribuidos en Cassandra",
}) {
  return (
    <div className="lay-loader-screen">
      <div className="lay-loader-card">
        <div className="lay-water-loader">
          <div className="lay-water-drop"></div>
          <div className="lay-water-ripple"></div>
        </div>

        <h2>{message}</h2>
        <p>{detail}</p>

        <div className="lay-loader-bar">
          <span></span>
        </div>

        <small>Cassandra + FastAPI + RabbitMQ</small>
      </div>
    </div>
  );
}

export default LoadingState;