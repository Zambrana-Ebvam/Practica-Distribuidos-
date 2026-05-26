import { useEffect, useMemo, useState } from "react";

import Sidebar from "./components/Sidebar";
import LoadingState from "./components/LoadingState";
import ErrorState from "./components/ErrorState";
import LoginLocal from "./components/LoginLocal";

import DashboardAlcaldia from "./pages/DashboardAlcaldia";
import DashboardGerencia from "./pages/DashboardGerencia";
import DashboardContabilidad from "./pages/DashboardContabilidad";
import MapaDistrital from "./pages/MapaDistrital";
import TotemAutoservicio from "./pages/TotemAutoservicio";

import {
  getConsumoCuenta,
  getCuentaDetalle,
  getCuentasDistrito,
  getDashboardAlcaldia,
  getDashboardContabilidad,
  getDashboardGerencia,
  getDistritos,
  getResumenDistrito,
} from "./services/dashboardService";

import {
  enviarPreaviso,
  generarPdfPreaviso,
} from "./services/preavisoService";

import {
  getDashboardInicialPorRol,
  getTabsPermitidosPorRol,
} from "./data/localUsers";

import "./styles/app_layout.css";

const MIN_DATOS_PARA_MOSTRAR_FILTRO = 2;

function getUsuarioGuardado() {
  try {
    const data = localStorage.getItem("semapa_user");
    return data ? JSON.parse(data) : null;
  } catch {
    localStorage.removeItem("semapa_user");
    return null;
  }
}

function toNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function round2(value) {
  return Math.round(toNumber(value) * 100) / 100;
}

function groupBySum(items, keyName, fields) {
  const map = new Map();

  items.forEach((item) => {
    const key = String(item?.[keyName] || "SIN DATO");

    if (!map.has(key)) {
      map.set(key, {
        [keyName]: key,
      });
    }

    const current = map.get(key);

    fields.forEach((field) => {
      current[field] = round2(
        toNumber(current[field]) + toNumber(item?.[field])
      );
    });
  });

  return Array.from(map.values());
}

function combinarGerencia(datosPorDistrito, periodoActual) {
  const dashboards = datosPorDistrito.map((item) => item.data).filter(Boolean);

  const kpis = dashboards.reduce(
    (acc, data) => {
      const k = data?.kpis || {};

      acc.total_consumo_acumulado_m3 += toNumber(k.total_consumo_acumulado_m3);
      acc.total_medidores_activos += toNumber(k.total_medidores_activos);
      acc.total_medidores += toNumber(k.total_medidores);
      acc.sensores_con_errores += toNumber(k.sensores_con_errores);
      acc.lecturas_app_movil += toNumber(k.lecturas_app_movil);
      acc.lecturas_iot += toNumber(k.lecturas_iot);
      acc.lecturas_fallidas += toNumber(k.lecturas_fallidas);
      acc.total_cuentas += toNumber(k.total_cuentas);

      return acc;
    },
    {
      distrito: "TODOS",
      periodo: periodoActual,
      total_consumo_acumulado_m3: 0,
      total_medidores_activos: 0,
      total_medidores: 0,
      sensores_con_errores: 0,
      sensores_error_pct: 0,
      lecturas_app_movil: 0,
      lecturas_iot: 0,
      lecturas_fallidas: 0,
      lecturas_app_movil_pct: 0,
      total_cuentas: 0,
    }
  );

  kpis.sensores_error_pct =
    kpis.total_medidores > 0
      ? round2((kpis.sensores_con_errores / kpis.total_medidores) * 100)
      : 0;

  const totalLecturas =
    kpis.lecturas_iot + kpis.lecturas_app_movil + kpis.lecturas_fallidas;

  kpis.lecturas_app_movil_pct =
    totalLecturas > 0
      ? round2((kpis.lecturas_app_movil / totalLecturas) * 100)
      : 0;

  kpis.total_consumo_acumulado_m3 = round2(kpis.total_consumo_acumulado_m3);

  const horas = groupBySum(
    dashboards.flatMap((d) => d?.horas || []),
    "bloque_horario",
    ["consumo_m3"]
  );

  const categoriasBase = groupBySum(
    dashboards.flatMap((d) => d?.categorias || []),
    "categoria",
    ["consumo_m3", "total_cuentas"]
  );

  const totalConsumoCategorias = categoriasBase.reduce(
    (total, c) => total + toNumber(c.consumo_m3),
    0
  );

  const totalCuentasCategorias = categoriasBase.reduce(
    (total, c) => total + toNumber(c.total_cuentas),
    0
  );

  const categorias = categoriasBase.map((c) => ({
    ...c,
    porcentaje_consumo:
      totalConsumoCategorias > 0
        ? round2((toNumber(c.consumo_m3) / totalConsumoCategorias) * 100)
        : 0,
    porcentaje_cuentas:
      totalCuentasCategorias > 0
        ? round2((toNumber(c.total_cuentas) / totalCuentasCategorias) * 100)
        : 0,
    promedio_m3_cuenta:
      toNumber(c.total_cuentas) > 0
        ? round2(toNumber(c.consumo_m3) / toNumber(c.total_cuentas))
        : 0,
  }));

  const topZonas = groupBySum(
    dashboards.flatMap((d) => d?.top_zonas || []),
    "zona",
    ["consumo_m3", "total_cuentas"]
  )
    .sort((a, b) => toNumber(b.consumo_m3) - toNumber(a.consumo_m3))
    .slice(0, 10);

  const fallasModelo = groupBySum(
    dashboards.flatMap((d) => d?.fallas_modelo || []),
    "modelo_medidor",
    ["activos", "sensores_con_error"]
  );

  const anomalias = dashboards
    .flatMap((d) => d?.anomalias || [])
    .slice(0, 100);

  const sensoresError = groupBySum(
    dashboards.flatMap((d) => d?.sensores_error || []),
    "estado_error",
    ["total_sensores", "lecturas_asociadas", "consumo_m3_asociado"]
  );

  return {
    kpis,
    horas,
    categorias,
    top_zonas: topZonas,
    fallas_modelo: fallasModelo,
    anomalias,
    sensores_error: sensoresError,
  };
}

function combinarContabilidad(datosPorDistrito, periodoActual) {
  const dashboards = datosPorDistrito.map((item) => item.data).filter(Boolean);

  const kpis = dashboards.reduce(
    (acc, data) => {
      const k = data?.kpis || {};

      acc.monto_facturado_bs += toNumber(k.monto_facturado_bs);
      acc.monto_recaudado_bs += toNumber(k.monto_recaudado_bs);
      acc.cartera_vencida_bs += toNumber(k.cartera_vencida_bs);
      acc.preavisos_emitidos += toNumber(k.preavisos_emitidos);
      acc.cuentas_morosas += toNumber(k.cuentas_morosas);

      return acc;
    },
    {
      distrito: "TODOS",
      periodo: periodoActual,
      monto_facturado_bs: 0,
      monto_recaudado_bs: 0,
      recuperacion_pct: 0,
      cartera_vencida_bs: 0,
      mora_pct: 0,
      preavisos_emitidos: 0,
      cuentas_morosas: 0,
      mejor_canal_cobranza: "SIN DATOS",
    }
  );

  kpis.monto_facturado_bs = round2(kpis.monto_facturado_bs);
  kpis.monto_recaudado_bs = round2(kpis.monto_recaudado_bs);
  kpis.cartera_vencida_bs = round2(kpis.cartera_vencida_bs);

  kpis.recuperacion_pct =
    kpis.monto_facturado_bs > 0
      ? round2((kpis.monto_recaudado_bs / kpis.monto_facturado_bs) * 100)
      : 0;

  kpis.mora_pct =
    kpis.monto_facturado_bs > 0
      ? round2((kpis.cartera_vencida_bs / kpis.monto_facturado_bs) * 100)
      : 0;

  const facturacionTarifa = groupBySum(
    dashboards.flatMap((d) => d?.facturacion_tarifa || []),
    "codigo_tarifa",
    [
      "monto_facturado_bs",
      "monto_recaudado_bs",
      "cartera_vencida_bs",
      "cuentas",
      "consumo_m3",
    ]
  );

  const facturacionCategoriaBase = groupBySum(
    dashboards.flatMap((d) => d?.facturacion_categoria || []),
    "categoria",
    [
      "cuentas",
      "consumo_m3",
      "monto_facturado_bs",
      "monto_recaudado_bs",
      "cartera_vencida_bs",
    ]
  );

  const facturacionCategoria = facturacionCategoriaBase.map((c) => ({
    ...c,
    ticket_promedio_bs:
      toNumber(c.cuentas) > 0
        ? round2(toNumber(c.monto_facturado_bs) / toNumber(c.cuentas))
        : 0,
  }));

  const facturacionZonaTop10 = groupBySum(
    dashboards.flatMap((d) => d?.facturacion_zona_top10 || []),
    "zona",
    ["monto_facturado_bs", "monto_recaudado_bs", "cartera_vencida_bs"]
  )
    .sort(
      (a, b) => toNumber(b.cartera_vencida_bs) - toNumber(a.cartera_vencida_bs)
    )
    .slice(0, 10);

  const efectividadCanalesBase = groupBySum(
    dashboards.flatMap((d) => d?.efectividad_canales || []),
    "canal",
    ["preavisos_emitidos", "monto_cartera_bs", "recuperacion_estimada_bs"]
  );

  const efectividadCanales = efectividadCanalesBase.map((c) => ({
    ...c,
    conversion_pct:
      toNumber(c.monto_cartera_bs) > 0
        ? round2(
            (toNumber(c.recuperacion_estimada_bs) /
              toNumber(c.monto_cartera_bs)) *
              100
          )
        : 0,
  }));

  const mejorCanal = [...efectividadCanales].sort(
    (a, b) =>
      toNumber(b.recuperacion_estimada_bs) -
      toNumber(a.recuperacion_estimada_bs)
  )[0];

  if (mejorCanal?.canal) {
    kpis.mejor_canal_cobranza = mejorCanal.canal;
  }

  const grandesDeudores = dashboards
    .flatMap((d) => d?.grandes_deudores || [])
    .sort(
      (a, b) => toNumber(b.cartera_vencida_bs) - toNumber(a.cartera_vencida_bs)
    )
    .slice(0, 50);

  const facturacionPorDistrito = datosPorDistrito.map(({ distrito, data }) => {
    const k = data?.kpis || {};

    return {
      distrito,
      monto_facturado_bs: round2(k.monto_facturado_bs),
      monto_recaudado_bs: round2(k.monto_recaudado_bs),
      cartera_vencida_bs: round2(k.cartera_vencida_bs),
    };
  });

  return {
    kpis,
    facturacion_tarifa: facturacionTarifa,
    facturacion_categoria: facturacionCategoria,
    facturacion_zona_top10: facturacionZonaTop10,
    efectividad_canales: efectividadCanales,
    grandes_deudores: grandesDeudores,
    obligatorios: {
      facturacion_por_distrito: facturacionPorDistrito,
    },
  };
}

function App() {
  const usuarioInicial = getUsuarioGuardado();

  const [usuario, setUsuario] = useState(usuarioInicial);

  const [tab, setTab] = useState(
    usuarioInicial ? getDashboardInicialPorRol(usuarioInicial.rol) : "alcaldia"
  );

  const [loading, setLoading] = useState(true);
  const [alcaldiaLoading, setAlcaldiaLoading] = useState(false);
  const [mapaLoading, setMapaLoading] = useState(false);
  const [errorInicial, setErrorInicial] = useState("");
  const [aviso, setAviso] = useState("");

  const [gerenciaLoading, setGerenciaLoading] = useState(false);
  const [contabilidadLoading, setContabilidadLoading] = useState(false);

  const [distritos, setDistritos] = useState([]);
  const [alcaldia, setAlcaldia] = useState(null);

  const [distrito, setDistrito] = useState("");
  const [periodo, setPeriodo] = useState("2026-04");

  // Importante: por defecto Distrito 1, no TODOS.
  // TODOS hace 15 llamadas y tarda mucho.
  const [distritoDashboardFiltro, setDistritoDashboardFiltro] = useState("1");

  const [cuentas, setCuentas] = useState([]);
  const [cuentasMapa, setCuentasMapa] = useState([]);

  const [cuentaSeleccionada, setCuentaSeleccionada] = useState(null);
  const [consumoCuenta, setConsumoCuenta] = useState([]);

  const [gerencia, setGerencia] = useState(null);
  const [contabilidad, setContabilidad] = useState(null);

  const [busqueda, setBusqueda] = useState("");

  const [distritoFiltro, setDistritoFiltro] = useState("TODOS");
  const [zonaFiltro, setZonaFiltro] = useState("TODAS");
  const [categoriaFiltro, setCategoriaFiltro] = useState("TODAS");
  const [subcategoriaFiltro, setSubcategoriaFiltro] = useState("TODAS");
  const [modeloMedidorFiltro, setModeloMedidorFiltro] = useState("TODOS");
  const [estadoMedidorFiltro, setEstadoMedidorFiltro] = useState("TODOS");
  const [estadoContratoFiltro, setEstadoContratoFiltro] = useState("TODOS");
  const [tipoServicioFiltro, setTipoServicioFiltro] = useState("TODOS");

  const [geojson, setGeojson] = useState(null);

  const [whatsapp, setWhatsapp] = useState("");
  const [sms, setSms] = useState("");
  const [email, setEmail] = useState("");
  const [resultadoEnvio, setResultadoEnvio] = useState(null);

  const isTotemRoute = window.location.pathname === "/totem";

  const tabsPermitidos = useMemo(() => {
    return usuario ? getTabsPermitidosPorRol(usuario.rol) : [];
  }, [usuario?.rol]);

  useEffect(() => {
    if (isTotemRoute) return;
    if (!usuario) return;

    cargarBase();
  }, [isTotemRoute, usuario?.id]);

  useEffect(() => {
    if (isTotemRoute) return;
    if (!usuario) return;

    if (tab === "alcaldia" && tabsPermitidos.includes("alcaldia") && !alcaldia) {
      cargarAlcaldia();
    }
  }, [isTotemRoute, usuario?.id, tab, alcaldia, tabsPermitidos]);

  useEffect(() => {
    if (isTotemRoute) return;
    if (!usuario) return;
    if (tab !== "gerencia") return;
    if (!tabsPermitidos.includes("gerencia")) return;
    if (!periodo) return;
    if (gerenciaLoading) return;

    const distritoCargado = String(gerencia?.kpis?.distrito || "");
    const periodoCargado = String(gerencia?.kpis?.periodo || "");

    if (
      distritoCargado === String(distritoDashboardFiltro) &&
      periodoCargado === String(periodo)
    ) {
      return;
    }

    if (distritoDashboardFiltro === "TODOS") {
      if (distritos.length > 0) {
        cargarGerenciaTodos(periodo);
      }
    } else {
      cargarGerencia(distritoDashboardFiltro, periodo);
    }
  }, [
    isTotemRoute,
    usuario?.id,
    tab,
    tabsPermitidos,
    distritoDashboardFiltro,
    periodo,
    distritos.length,
    gerencia?.kpis?.distrito,
    gerencia?.kpis?.periodo,
    gerenciaLoading,
  ]);

  useEffect(() => {
    if (isTotemRoute) return;
    if (!usuario) return;
    if (tab !== "contabilidad") return;
    if (!tabsPermitidos.includes("contabilidad")) return;
    if (!periodo) return;
    if (contabilidadLoading) return;

    const distritoCargado = String(contabilidad?.kpis?.distrito || "");
    const periodoCargado = String(contabilidad?.kpis?.periodo || "");

    if (
      distritoCargado === String(distritoDashboardFiltro) &&
      periodoCargado === String(periodo)
    ) {
      return;
    }

    if (distritoDashboardFiltro === "TODOS") {
      if (distritos.length > 0) {
        cargarContabilidadTodos(periodo);
      }
    } else {
      cargarContabilidad(distritoDashboardFiltro, periodo);
    }
  }, [
    isTotemRoute,
    usuario?.id,
    tab,
    tabsPermitidos,
    distritoDashboardFiltro,
    periodo,
    distritos.length,
    contabilidad?.kpis?.distrito,
    contabilidad?.kpis?.periodo,
    contabilidadLoading,
  ]);

  useEffect(() => {
    if (isTotemRoute) return;
    if (!usuario) return;
    if (tab !== "mapa") return;
    if (!tabsPermitidos.includes("mapa")) return;

    if (distritos.length > 0 && cuentasMapa.length === 0 && !mapaLoading) {
      cargarCuentasMapa(distritos);
    }
  }, [
    isTotemRoute,
    usuario?.id,
    tab,
    tabsPermitidos,
    distritos.length,
    cuentasMapa.length,
    mapaLoading,
  ]);

  function mostrarErrorReal(nombre, error) {
    console.error(`ERROR EN ${nombre}:`, {
      status: error?.response?.status,
      data: error?.response?.data,
      message: error?.message,
      url: error?.config?.url,
    });
  }

  function iniciarSesion(usuarioLocal) {
    setUsuario(usuarioLocal);
    setTab(getDashboardInicialPorRol(usuarioLocal.rol));
    setLoading(true);
    setErrorInicial("");
    setAviso("");
  }

  function cerrarSesion() {
    localStorage.removeItem("semapa_user");

    setUsuario(null);
    setTab("alcaldia");
    setAlcaldia(null);
    setGerencia(null);
    setContabilidad(null);
    setCuentasMapa([]);
    setCuentaSeleccionada(null);
    setConsumoCuenta([]);
    setAviso("");
    setErrorInicial("");
    setLoading(false);
  }

  function obtenerDistritosIds() {
    const ids = distritos
      .map((d) => String(d.distrito))
      .filter(Boolean)
      .sort((a, b) => Number(a) - Number(b));

    return ids.length ? ids : ["1"];
  }

  async function cargarBase() {
    try {
      setLoading(true);
      setErrorInicial("");
      setAviso("");

      const distritosData = await getDistritos();
      setDistritos(distritosData || []);

      const primerDistrito = distritosData?.[0]?.distrito
        ? String(distritosData[0].distrito)
        : "1";

      setDistrito(primerDistrito);

      try {
        const geoResponse = await fetch("/cochabamba_distritos.geojson");

        if (geoResponse.ok) {
          const geo = await geoResponse.json();

          if (
            geo &&
            geo.type &&
            ["FeatureCollection", "Feature", "Polygon", "MultiPolygon"].includes(
              geo.type
            )
          ) {
            setGeojson(geo);
          } else {
            setGeojson(null);
          }
        }
      } catch {
        setGeojson(null);
      }
    } catch (error) {
      mostrarErrorReal("CARGA BASE", error);
      setErrorInicial(
        "No se pudo cargar la información inicial. Revisa que el backend esté prendido y que /api/distritos responda."
      );
    } finally {
      setLoading(false);
    }
  }

  async function cargarAlcaldia() {
    try {
      setAlcaldiaLoading(true);
      setAviso("");

      const alcaldiaData = await getDashboardAlcaldia();
      setAlcaldia(alcaldiaData);
    } catch (error) {
      mostrarErrorReal("DASHBOARD ALCALDIA", error);
      setAlcaldia(null);
      setAviso("No se pudo cargar Dashboard Alcaldía.");
    } finally {
      setAlcaldiaLoading(false);
    }
  }

  async function cargarCuentasMapa(distritosData) {
    try {
      setMapaLoading(true);
      setAviso("");

      const resultados = [];

      for (const d of distritosData || []) {
        try {
          const data = await getCuentasDistrito(String(d.distrito), 5000);
          resultados.push(...(data || []));
        } catch (error) {
          mostrarErrorReal(`CUENTAS MAPA DISTRITO ${d.distrito}`, error);
        }
      }

      const sinDuplicados = Array.from(
        new Map(resultados.map((c) => [c.cuenta_id, c])).values()
      );

      setCuentasMapa(sinDuplicados);
    } catch (error) {
      mostrarErrorReal("CARGA CUENTAS MAPA", error);
      setCuentasMapa([]);
    } finally {
      setMapaLoading(false);
    }
  }

  async function cargarGerencia(distritoId, periodoActual) {
    try {
      setGerenciaLoading(true);
      setAviso("");

      const gerenciaData = await getDashboardGerencia(distritoId, periodoActual);
      setGerencia(gerenciaData);
    } catch (error) {
      mostrarErrorReal(`DASHBOARD GERENCIA DISTRITO ${distritoId}`, error);
      setGerencia(null);
      setAviso(
        `Gerencia no cargó para distrito ${distritoId}. Revisa F12 → Console.`
      );
    } finally {
      setGerenciaLoading(false);
    }
  }

  async function cargarGerenciaTodos(periodoActual) {
    try {
      setGerenciaLoading(true);
      setAviso("");

      const ids = obtenerDistritosIds();
      const validos = [];

      for (const id of ids) {
        try {
          const data = await getDashboardGerencia(id, periodoActual);
          validos.push({ distrito: id, data });
        } catch (error) {
          mostrarErrorReal(`DASHBOARD GERENCIA DISTRITO ${id}`, error);
        }
      }

      if (!validos.length) {
        throw new Error("No se pudo cargar ningún distrito para Gerencia.");
      }

      setGerencia(combinarGerencia(validos, periodoActual));

      if (validos.length < ids.length) {
        setAviso(
          `Gerencia consolidó ${validos.length} de ${ids.length} distritos. Algunos tardaron demasiado.`
        );
      }
    } catch (error) {
      mostrarErrorReal("DASHBOARD GERENCIA TODOS", error);
      setGerencia(null);
      setAviso(
        "Gerencia no cargó para todos los distritos. Revisa F12 → Console."
      );
    } finally {
      setGerenciaLoading(false);
    }
  }

  async function cargarContabilidad(distritoId, periodoActual) {
    try {
      setContabilidadLoading(true);
      setAviso("");

      const contabilidadData = await getDashboardContabilidad(
        distritoId,
        periodoActual
      );

      setContabilidad(contabilidadData);
    } catch (error) {
      mostrarErrorReal(`DASHBOARD CONTABILIDAD DISTRITO ${distritoId}`, error);
      setContabilidad(null);
      setAviso(`Contabilidad no cargó para distrito ${distritoId}.`);
    } finally {
      setContabilidadLoading(false);
    }
  }

  async function cargarContabilidadTodos(periodoActual) {
    try {
      setContabilidadLoading(true);
      setAviso("");

      const ids = obtenerDistritosIds();
      const validos = [];

      for (const id of ids) {
        try {
          const data = await getDashboardContabilidad(id, periodoActual);
          validos.push({ distrito: id, data });
        } catch (error) {
          mostrarErrorReal(`DASHBOARD CONTABILIDAD DISTRITO ${id}`, error);
        }
      }

      if (!validos.length) {
        throw new Error("No se pudo cargar ningún distrito para Contabilidad.");
      }

      setContabilidad(combinarContabilidad(validos, periodoActual));

      if (validos.length < ids.length) {
        setAviso(
          `Contabilidad consolidó ${validos.length} de ${ids.length} distritos. Algunos tardaron demasiado.`
        );
      }
    } catch (error) {
      mostrarErrorReal("DASHBOARD CONTABILIDAD TODOS", error);
      setContabilidad(null);
      setAviso(
        "Contabilidad no cargó para todos los distritos. Revisa F12 → Console."
      );
    } finally {
      setContabilidadLoading(false);
    }
  }

  async function seleccionarCuenta(cuenta) {
    try {
      setAviso("");

      const [detalleData, consumoData] = await Promise.all([
        getCuentaDetalle(cuenta.cuenta_id),
        getConsumoCuenta(cuenta.cuenta_id),
      ]);

      setCuentaSeleccionada(detalleData);
      setConsumoCuenta(consumoData || []);
      setResultadoEnvio(null);
    } catch (error) {
      mostrarErrorReal("DETALLE CUENTA", error);
      setAviso("No se pudo cargar el detalle de la cuenta seleccionada.");
    }
  }

  async function generarPdf() {
    if (!cuentaSeleccionada || !periodo) return;

    try {
      const resultado = await generarPdfPreaviso({
        cuenta_id: cuentaSeleccionada.cuenta_id,
        periodo,
      });

      setResultadoEnvio(resultado);
    } catch (error) {
      mostrarErrorReal("GENERAR PDF", error);
      setAviso("No se pudo generar el PDF del preaviso.");
    }
  }

  async function enviarPreavisoCuenta() {
    if (!cuentaSeleccionada || !periodo) return;

    try {
      const resultado = await enviarPreaviso({
        cuenta_id: cuentaSeleccionada.cuenta_id,
        periodo,
        whatsapp,
        sms,
        email,
      });

      setResultadoEnvio(resultado);
    } catch (error) {
      mostrarErrorReal("ENVIAR PREAVISO", error);
      setAviso("No se pudo enviar el preaviso por RabbitMQ.");
    }
  }

  function normalizarValorFiltro(value) {
    if (value === null || value === undefined) return "";
    return String(value).trim();
  }

  function contarOpcionesPorCampo(data, campo) {
    const conteo = new Map();

    data.forEach((item) => {
      const valor = normalizarValorFiltro(item?.[campo]);

      if (!valor) return;

      conteo.set(valor, (conteo.get(valor) || 0) + 1);
    });

    return conteo;
  }

  function ordenarOpciones(campo, opciones) {
    if (campo === "distrito") {
      return opciones.sort((a, b) => Number(a) - Number(b));
    }

    return opciones.sort((a, b) => a.localeCompare(b));
  }

  function crearOpcionesDesdeData(data, campo, etiquetaTodos = "TODOS") {
    const conteo = contarOpcionesPorCampo(data, campo);

    const opciones = Array.from(conteo.entries())
      .filter(([, cantidad]) => cantidad >= MIN_DATOS_PARA_MOSTRAR_FILTRO)
      .map(([valor]) => valor);

    return [etiquetaTodos, ...ordenarOpciones(campo, opciones)];
  }

  function aplicarFiltrosParaOpciones(data, ignorarCampo = "") {
    return data.filter((c) => {
      if (
        ignorarCampo !== "distrito" &&
        distritoFiltro !== "TODOS" &&
        String(c.distrito) !== String(distritoFiltro)
      ) {
        return false;
      }

      if (
        ignorarCampo !== "zona" &&
        zonaFiltro !== "TODAS" &&
        String(c.zona) !== String(zonaFiltro)
      ) {
        return false;
      }

      if (
        ignorarCampo !== "categoria" &&
        categoriaFiltro !== "TODAS" &&
        String(c.categoria) !== String(categoriaFiltro)
      ) {
        return false;
      }

      if (
        ignorarCampo !== "subcategoria" &&
        subcategoriaFiltro !== "TODAS" &&
        String(c.subcategoria) !== String(subcategoriaFiltro)
      ) {
        return false;
      }

      if (
        ignorarCampo !== "modelo_medidor" &&
        modeloMedidorFiltro !== "TODOS" &&
        String(c.modelo_medidor) !== String(modeloMedidorFiltro)
      ) {
        return false;
      }

      if (
        ignorarCampo !== "estado_medidor" &&
        estadoMedidorFiltro !== "TODOS" &&
        String(c.estado_medidor) !== String(estadoMedidorFiltro)
      ) {
        return false;
      }

      if (
        ignorarCampo !== "estado_contrato" &&
        estadoContratoFiltro !== "TODOS" &&
        String(c.estado_contrato) !== String(estadoContratoFiltro)
      ) {
        return false;
      }

      if (
        ignorarCampo !== "tipo_servicio" &&
        tipoServicioFiltro !== "TODOS" &&
        String(c.tipo_servicio) !== String(tipoServicioFiltro)
      ) {
        return false;
      }

      return true;
    });
  }

  function crearOpcionesDependientes(campo, etiquetaTodos = "TODOS") {
    const base = cuentasMapa.length ? cuentasMapa : cuentas;
    const dataFiltrada = aplicarFiltrosParaOpciones(base, campo);

    return crearOpcionesDesdeData(dataFiltrada, campo, etiquetaTodos);
  }

  const distritoActual = useMemo(() => {
    return distritos.find((d) => String(d.distrito) === String(distrito));
  }, [distritos, distrito]);

  const distritoMapaActual = useMemo(() => {
    if (distritoFiltro !== "TODOS") {
      return distritos.find((d) => String(d.distrito) === String(distritoFiltro));
    }

    return distritoActual;
  }, [distritos, distritoFiltro, distritoActual]);

  const filtrosOpciones = useMemo(() => {
    return {
      distritos: crearOpcionesDependientes("distrito", "TODOS"),
      zonas: crearOpcionesDependientes("zona", "TODAS"),
      categorias: crearOpcionesDependientes("categoria", "TODAS"),
      subcategorias: crearOpcionesDependientes("subcategoria", "TODAS"),
      modelosMedidor: crearOpcionesDependientes("modelo_medidor", "TODOS"),
      estadosMedidor: crearOpcionesDependientes("estado_medidor", "TODOS"),
      estadosContrato: crearOpcionesDependientes("estado_contrato", "TODOS"),
      tiposServicio: crearOpcionesDependientes("tipo_servicio", "TODOS"),
    };
  }, [
    cuentasMapa,
    cuentas,
    distritoFiltro,
    zonaFiltro,
    categoriaFiltro,
    subcategoriaFiltro,
    modeloMedidorFiltro,
    estadoMedidorFiltro,
    estadoContratoFiltro,
    tipoServicioFiltro,
  ]);

  useEffect(() => {
    if (isTotemRoute) return;
    if (!usuario) return;
    if (tab !== "mapa") return;

    if (
      distritoFiltro !== "TODOS" &&
      !filtrosOpciones.distritos.includes(distritoFiltro)
    ) {
      setDistritoFiltro("TODOS");
    }

    if (
      zonaFiltro !== "TODAS" &&
      !filtrosOpciones.zonas.includes(zonaFiltro)
    ) {
      setZonaFiltro("TODAS");
    }

    if (
      categoriaFiltro !== "TODAS" &&
      !filtrosOpciones.categorias.includes(categoriaFiltro)
    ) {
      setCategoriaFiltro("TODAS");
    }

    if (
      subcategoriaFiltro !== "TODAS" &&
      !filtrosOpciones.subcategorias.includes(subcategoriaFiltro)
    ) {
      setSubcategoriaFiltro("TODAS");
    }

    if (
      modeloMedidorFiltro !== "TODOS" &&
      !filtrosOpciones.modelosMedidor.includes(modeloMedidorFiltro)
    ) {
      setModeloMedidorFiltro("TODOS");
    }

    if (
      estadoMedidorFiltro !== "TODOS" &&
      !filtrosOpciones.estadosMedidor.includes(estadoMedidorFiltro)
    ) {
      setEstadoMedidorFiltro("TODOS");
    }

    if (
      estadoContratoFiltro !== "TODOS" &&
      !filtrosOpciones.estadosContrato.includes(estadoContratoFiltro)
    ) {
      setEstadoContratoFiltro("TODOS");
    }

    if (
      tipoServicioFiltro !== "TODOS" &&
      !filtrosOpciones.tiposServicio.includes(tipoServicioFiltro)
    ) {
      setTipoServicioFiltro("TODOS");
    }
  }, [
    isTotemRoute,
    usuario,
    tab,
    filtrosOpciones,
    distritoFiltro,
    zonaFiltro,
    categoriaFiltro,
    subcategoriaFiltro,
    modeloMedidorFiltro,
    estadoMedidorFiltro,
    estadoContratoFiltro,
    tipoServicioFiltro,
  ]);

  const cuentasFiltradas = useMemo(() => {
    let data = cuentasMapa.length ? [...cuentasMapa] : [...cuentas];

    if (distritoFiltro !== "TODOS") {
      data = data.filter((c) => String(c.distrito) === String(distritoFiltro));
    }

    if (zonaFiltro !== "TODAS") {
      data = data.filter((c) => String(c.zona) === String(zonaFiltro));
    }

    if (categoriaFiltro !== "TODAS") {
      data = data.filter((c) => String(c.categoria) === String(categoriaFiltro));
    }

    if (subcategoriaFiltro !== "TODAS") {
      data = data.filter(
        (c) => String(c.subcategoria) === String(subcategoriaFiltro)
      );
    }

    if (modeloMedidorFiltro !== "TODOS") {
      data = data.filter(
        (c) => String(c.modelo_medidor) === String(modeloMedidorFiltro)
      );
    }

    if (estadoMedidorFiltro !== "TODOS") {
      data = data.filter(
        (c) => String(c.estado_medidor) === String(estadoMedidorFiltro)
      );
    }

    if (estadoContratoFiltro !== "TODOS") {
      data = data.filter(
        (c) => String(c.estado_contrato) === String(estadoContratoFiltro)
      );
    }

    if (tipoServicioFiltro !== "TODOS") {
      data = data.filter(
        (c) => String(c.tipo_servicio) === String(tipoServicioFiltro)
      );
    }

    if (busqueda.trim()) {
      const texto = busqueda.trim().toUpperCase();

      data = data.filter((c) => {
        return (
          String(c.cuenta_id || "").toUpperCase().includes(texto) ||
          String(c.nombre_cliente || "").toUpperCase().includes(texto) ||
          String(c.medidor_mac || "").toUpperCase().includes(texto) ||
          String(c.direccion || "").toUpperCase().includes(texto) ||
          String(c.numero_catastro || "").toUpperCase().includes(texto)
        );
      });
    }

    return data;
  }, [
    cuentasMapa,
    cuentas,
    distritoFiltro,
    zonaFiltro,
    categoriaFiltro,
    subcategoriaFiltro,
    modeloMedidorFiltro,
    estadoMedidorFiltro,
    estadoContratoFiltro,
    tipoServicioFiltro,
    busqueda,
  ]);

  const consumoPeriodoCuenta = useMemo(() => {
    if (!consumoCuenta.length) return null;

    return consumoCuenta.find((c) => c.periodo === periodo) || consumoCuenta[0];
  }, [consumoCuenta, periodo]);

  function limpiarFiltrosMapa() {
    setDistritoFiltro("TODOS");
    setZonaFiltro("TODAS");
    setCategoriaFiltro("TODAS");
    setSubcategoriaFiltro("TODAS");
    setModeloMedidorFiltro("TODOS");
    setEstadoMedidorFiltro("TODOS");
    setEstadoContratoFiltro("TODOS");
    setTipoServicioFiltro("TODOS");
    setBusqueda("");
  }

  if (isTotemRoute) {
    return <TotemAutoservicio periodoInicial={periodo || "2026-04"} />;
  }

  if (!usuario) {
    return <LoginLocal onLogin={iniciarSesion} />;
  }

  if (loading) {
    return (
      <LoadingState
        message="Cargando plataforma SEMAPA..."
        detail="Conectando con FastAPI y consultando distritos en Cassandra"
      />
    );
  }

  if (errorInicial) {
    return <ErrorState message={errorInicial} />;
  }

  return (
    <div className="lay-app">
      <Sidebar
        activeTab={tab}
        onChangeTab={setTab}
        visibleTabs={tabsPermitidos}
        usuario={usuario}
        onLogout={cerrarSesion}
      />

      <main className="lay-content">
        <header className="lay-topbar">
          <div>
            <h1>SEMAPA Cochabamba</h1>
            <p>
              Plataforma distribuida para gestión inteligente del consumo de agua
            </p>
          </div>

          <div className="lay-status-pill">
            {usuario.nombre} · Rol: {usuario.rol}
          </div>
        </header>

        {aviso && <div className="lay-state-box lay-state-error">{aviso}</div>}

        {(tab === "gerencia" || tab === "contabilidad") && (
          <div className="lay-panel lay-dashboard-filter-panel">
            <label>
              <span>Filtro de dashboard</span>
              <select
                value={distritoDashboardFiltro}
                onChange={(e) => setDistritoDashboardFiltro(e.target.value)}
              >
                <option value="TODOS">Todos los distritos</option>

                {distritos.map((d) => (
                  <option key={d.distrito} value={String(d.distrito)}>
                    Distrito {d.distrito}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span>Periodo</span>
              <select
                value={periodo}
                onChange={(e) => setPeriodo(e.target.value)}
              >
                <option value="2026-04">2026-04</option>
                <option value="2026-03">2026-03</option>
                <option value="2026-02">2026-02</option>
              </select>
            </label>

            <div className="lay-dashboard-filter-note">
              {distritoDashboardFiltro === "TODOS"
                ? "Mostrando información consolidada de todos los distritos."
                : `Mostrando información del distrito ${distritoDashboardFiltro}.`}
            </div>
          </div>
        )}

        {tab === "alcaldia" &&
          tabsPermitidos.includes("alcaldia") &&
          (alcaldiaLoading ? (
            <div className="lay-inline-loader">
              <LoadingState
                message="Cargando Dashboard Alcaldía..."
                detail="Consultando indicadores Smart City"
              />
            </div>
          ) : alcaldia ? (
            <DashboardAlcaldia
              alcaldia={alcaldia}
              distritoActual={distritoActual}
              onDistritoClick={setDistrito}
            />
          ) : (
            <div className="lay-state-box lay-state-error">
              No se cargaron datos de Alcaldía.
            </div>
          ))}

        {tab === "gerencia" &&
          tabsPermitidos.includes("gerencia") &&
          (gerenciaLoading ? (
            <div className="lay-inline-loader">
              <LoadingState
                message="Cargando Dashboard Gerencia..."
                detail={
                  distritoDashboardFiltro === "TODOS"
                    ? "Consolidando información de todos los distritos"
                    : "Procesando consumo acumulado, sensores, zonas y anomalías"
                }
              />
            </div>
          ) : gerencia ? (
            <DashboardGerencia gerencia={gerencia} periodo={periodo} />
          ) : (
            <div className="lay-state-box lay-state-error">
              No se cargaron datos de Gerencia. Cambia el filtro o revisa F12.
            </div>
          ))}

        {tab === "contabilidad" &&
          tabsPermitidos.includes("contabilidad") &&
          (contabilidadLoading ? (
            <div className="lay-inline-loader">
              <LoadingState
                message="Cargando Dashboard Contabilidad..."
                detail={
                  distritoDashboardFiltro === "TODOS"
                    ? "Sumando facturación y cartera vencida de todos los distritos"
                    : "Calculando facturación, mora, cartera vencida y preavisos"
                }
              />
            </div>
          ) : contabilidad ? (
            <DashboardContabilidad
              contabilidad={contabilidad}
              periodo={periodo}
            />
          ) : (
            <div className="lay-state-box lay-state-error">
              No se cargaron datos de Contabilidad. Cambia el filtro o revisa F12.
            </div>
          ))}

        {tab === "mapa" && tabsPermitidos.includes("mapa") && (
          <MapaDistrital
            mapaLoading={mapaLoading}
            filtrosOpciones={filtrosOpciones}
            distritoFiltro={distritoFiltro}
            setDistritoFiltro={setDistritoFiltro}
            zonaFiltro={zonaFiltro}
            setZonaFiltro={setZonaFiltro}
            categoriaFiltro={categoriaFiltro}
            setCategoriaFiltro={setCategoriaFiltro}
            subcategoriaFiltro={subcategoriaFiltro}
            setSubcategoriaFiltro={setSubcategoriaFiltro}
            modeloMedidorFiltro={modeloMedidorFiltro}
            setModeloMedidorFiltro={setModeloMedidorFiltro}
            estadoMedidorFiltro={estadoMedidorFiltro}
            setEstadoMedidorFiltro={setEstadoMedidorFiltro}
            estadoContratoFiltro={estadoContratoFiltro}
            setEstadoContratoFiltro={setEstadoContratoFiltro}
            tipoServicioFiltro={tipoServicioFiltro}
            setTipoServicioFiltro={setTipoServicioFiltro}
            limpiarFiltrosMapa={limpiarFiltrosMapa}
            busqueda={busqueda}
            setBusqueda={setBusqueda}
            cuentasFiltradas={cuentasFiltradas}
            totalCuentasMapa={(cuentasMapa.length ? cuentasMapa : cuentas).length}
            distritoActual={distritoMapaActual}
            geojson={geojson}
            cuentaSeleccionada={cuentaSeleccionada}
            seleccionarCuenta={seleccionarCuenta}
            consumoCuenta={consumoCuenta}
            consumoPeriodoCuenta={consumoPeriodoCuenta}
            whatsapp={whatsapp}
            setWhatsapp={setWhatsapp}
            sms={sms}
            setSms={setSms}
            email={email}
            setEmail={setEmail}
            generarPdf={generarPdf}
            enviarPreavisoCuenta={enviarPreavisoCuenta}
            resultadoEnvio={resultadoEnvio}
          />
        )}
      </main>
    </div>
  );
}

export default App;