export const localUsers = [
  {
    id: 1,
    username: "alcalde",
    password: "1234",
    nombre: "Usuario Alcaldía Municipal",
    rol: "alcalde",
    dashboardInicial: "alcaldia",
  },
  {
    id: 2,
    username: "gerente",
    password: "1234",
    nombre: "Usuario Gerencia SEMAPA",
    rol: "gerente",
    dashboardInicial: "gerencia",
  },
  {
    id: 3,
    username: "contador",
    password: "1234",
    nombre: "Usuario Contabilidad SEMAPA",
    rol: "contabilidad",
    dashboardInicial: "contabilidad",
  },
];

export function validarUsuarioLocal(username, password) {
  const usuario = localUsers.find(
    (u) =>
      u.username.toLowerCase() === String(username).trim().toLowerCase() &&
      u.password === String(password).trim()
  );

  if (!usuario) return null;

  const { password: _password, ...usuarioSeguro } = usuario;
  return usuarioSeguro;
}

export function getDashboardInicialPorRol(rol) {
  if (rol === "alcalde") return "alcaldia";
  if (rol === "gerente") return "gerencia";
  if (rol === "contabilidad") return "contabilidad";

  return "mapa";
}

export function getTabsPermitidosPorRol(rol) {
  if (rol === "alcalde") {
    return ["alcaldia", "mapa"];
  }

  if (rol === "gerente") {
    return ["gerencia", "mapa"];
  }

  if (rol === "contabilidad") {
    return ["contabilidad", "mapa"];
  }

  return ["mapa"];
}