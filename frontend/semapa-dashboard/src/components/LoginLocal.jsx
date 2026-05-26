import { useState } from "react";
import { validarUsuarioLocal } from "../data/localUsers";
import "../styles/login_local.css";

function LoginLocal({ onLogin }) {
  const [username, setUsername] = useState("alcalde");
  const [password, setPassword] = useState("1234");
  const [error, setError] = useState("");

  function iniciarSesion(e) {
    e.preventDefault();

    const usuario = validarUsuarioLocal(username, password);

    if (!usuario) {
      setError("Usuario o contraseña incorrectos.");
      return;
    }

    localStorage.setItem("semapa_user", JSON.stringify(usuario));
    onLogin(usuario);
  }

  function accesoRapido(user, pass) {
    const usuario = validarUsuarioLocal(user, pass);

    if (!usuario) {
      setError("No se pudo iniciar sesión.");
      return;
    }

    localStorage.setItem("semapa_user", JSON.stringify(usuario));
    onLogin(usuario);
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <div className="login-logo">S</div>
          <div>
            <h1>SEMAPA</h1>
            <p>Sistema Big Data Distribuido</p>
          </div>
        </div>

        <h2>Acceso institucional</h2>

        <p className="login-description">
          Ingrese con un rol local para cargar únicamente los procesos que
          corresponden a su área.
        </p>

        <form onSubmit={iniciarSesion} className="login-form">
          <label>
            Usuario
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="alcalde / gerente / contador"
            />
          </label>

          <label>
            Contraseña
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="1234"
            />
          </label>

          {error && <div className="login-error">{error}</div>}

          <button type="submit">Ingresar</button>
        </form>

        <div className="login-demo-box">
          <h3>Usuarios de prueba</h3>

          <div className="login-demo-grid">
            <button onClick={() => accesoRapido("alcalde", "1234")}>
              Alcaldía
            </button>

            <button onClick={() => accesoRapido("gerente", "1234")}>
              Gerencia
            </button>

            <button onClick={() => accesoRapido("contador", "1234")}>
              Contabilidad
            </button>
          </div>
        </div>

        <small>
          Demo local. No representa autenticación real de producción.
        </small>
      </div>
    </div>
  );
}

export default LoginLocal;