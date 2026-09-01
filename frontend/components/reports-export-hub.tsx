"use client";

import { useState } from "react";
import { Download, FileSpreadsheet, FileText, Loader2 } from "lucide-react";

export function ReportsExportHub() {
  const [downloadingSire, setDownloadingSire] = useState(false);
  const [downloadingCsv, setDownloadingCsv] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const handleDownload = async (type: "sire" | "csv") => {
    try {
      setDownloadError(null);
      if (type === "sire") setDownloadingSire(true);
      else setDownloadingCsv(true);

      const endpoint = type === "sire" ? "/api/proxy/api/v1/reports/sire" : "/api/proxy/api/v1/reports/export";
      const filename = type === "sire" ? "sire_compras_rce.txt" : "facturas_cajaclara.csv";

      const res = await fetch(endpoint);
      if (!res.ok) {
        throw new Error(`Error en descarga: ${res.status} ${res.statusText}`);
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: unknown) {
      setDownloadError(err instanceof Error ? err.message : "Fallo al exportar reporte");
    } finally {
      setDownloadingSire(false);
      setDownloadingCsv(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
        <h2 className="text-base font-bold text-white tracking-tight">Centro de Exportación Fiscal & Contable</h2>
        <p className="text-xs text-slate-400 mt-1">
          Generación en 1-clic de libros oficiales para SUNAT y archivos estructurados para importación en ERPs.
        </p>

        {downloadError ? (
          <div className="mt-4 p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-xs text-rose-300">
            {downloadError}
          </div>
        ) : null}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
          {/* Tarjeta SIRE RCE */}
          <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 flex flex-col justify-between space-y-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
                <FileText className="h-5 w-5" />
                <span>SIRE / RCE — SUNAT</span>
              </div>
              <p className="text-xs text-slate-400">
                Archivo plano oficial del Registro de Compras Electrónico estructurado bajo la R.S. de SUNAT, con desglose de base gravada, IGV, tipo de cambio y detracciones SPOT.
              </p>
            </div>
            <button
              disabled={downloadingSire}
              onClick={() => handleDownload("sire")}
              className="w-full py-2 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
            >
              {downloadingSire ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              Descargar Archivo SIRE RCE (.txt)
            </button>
          </div>

          {/* Tarjeta ERP CSV */}
          <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 flex flex-col justify-between space-y-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
                <FileSpreadsheet className="h-5 w-5" />
                <span>CSV Estructurado para ERPs</span>
              </div>
              <p className="text-xs text-slate-400">
                Libro diario de facturas en formato CSV listo para importar en software contable y ERPs (Concar, Siigo Cloud, Odoo, SAP Business One y Microsoft Excel).
              </p>
            </div>
            <button
              disabled={downloadingCsv}
              onClick={() => handleDownload("csv")}
              className="w-full py-2 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
            >
              {downloadingCsv ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              Descargar CSV Contable (.csv)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
