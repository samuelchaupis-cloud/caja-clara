import Decimal from "decimal.js";

export function formatCurrency(amount: string | number | null | undefined, currency: string = "PEN"): string {
  if (amount === null || amount === undefined || amount === "") {
    return currency === "USD" ? "$ 0.00" : "S/ 0.00";
  }

  try {
    const dec = new Decimal(amount);
    const formatted = dec.toFixed(2);
    const parts = formatted.split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    const numStr = parts.join(".");
    return currency.toUpperCase() === "USD" ? `$ ${numStr}` : `S/ ${numStr}`;
  } catch {
    return currency === "USD" ? "$ 0.00" : "S/ 0.00";
  }
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "-";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("es-PE", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return dateStr;
  }
}

export function getDocumentTypeLabel(typeCode: string | null | undefined): string {
  switch (typeCode) {
    case "01":
      return "Factura";
    case "03":
      return "Boleta";
    case "07":
      return "Nota de Crédito";
    case "08":
      return "Nota de Débito";
    default:
      return typeCode || "Otro";
  }
}
