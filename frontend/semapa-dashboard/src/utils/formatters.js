export function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "0";
  }

  return Number(value).toLocaleString("es-BO", {
    maximumFractionDigits: 2,
  });
}

export function formatMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Bs 0";
  }

  return `Bs ${Number(value).toLocaleString("es-BO", {
    maximumFractionDigits: 2,
  })}`;
}