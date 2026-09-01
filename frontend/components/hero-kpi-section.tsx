"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchLiveTelemetry, fetchLedger } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { formatCurrency } from "@/lib/formatters";
import { Banknote, CheckCircle2, FileCheck, Layers } from "lucide-react";

export function HeroKPISection() {
  const { data: telemetry } = useQuery({
    queryKey: queryKeys.telemetry.live(),
    queryFn: fetchLiveTelemetry,
    refetchInterval: 5000,
  });

  const { data: ledgerData } = useQuery({
    queryKey: queryKeys.ledger.list({ page: 1, page_size: 1 }),
    queryFn: () => fetchLedger({ page: 1, page_size: 1 }),
    refetchInterval: 10000,
  });

  const totalInvoices = telemetry?.invoices?.total_processed ?? ledgerData?.pagination?.total_records ?? 0;
  const totalAmountPEN = ledgerData?.summary?.total_amount_pen ?? "0.00";
  const totalAmountUSD = ledgerData?.summary?.total_amount_usd ?? "0.00";
  const totalDetractionsPEN = ledgerData?.summary?.total_detractions_pen ?? "0.00";

  const totalErrors = telemetry?.invoices?.total_errors ?? 0;
  const cdrAcceptanceRate = totalInvoices > 0 ? (((totalInvoices - totalErrors) / totalInvoices) * 100).toFixed(1) : "100.0";

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* KPI 1: Volumen Procesado PEN */}
      <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm relative overflow-hidden">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Total Volumen (PEN)</span>
          <div className="p-2 rounded-lg bg-indigo-950/60 text-indigo-400 border border-indigo-900">
            <Banknote className="h-5 w-5" />
          </div>
        </div>
        <div className="mt-3">
          <span className="text-2xl font-bold font-mono tracking-tight text-white tabular-nums">
            {formatCurrency(totalAmountPEN, "PEN")}
          </span>
          <p className="text-xs text-slate-500 mt-1">
            USD equivalente: <span className="font-mono text-slate-400">{formatCurrency(totalAmountUSD, "USD")}</span>
          </p>
        </div>
      </div>

      {/* KPI 2: Total Comprobantes */}
      <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm relative overflow-hidden">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Comprobantes</span>
          <div className="p-2 rounded-lg bg-emerald-950/60 text-emerald-400 border border-emerald-900">
            <FileCheck className="h-5 w-5" />
          </div>
        </div>
        <div className="mt-3">
          <span className="text-2xl font-bold font-mono tracking-tight text-white tabular-nums">
            {totalInvoices}
          </span>
          <p className="text-xs text-slate-500 mt-1">
            Facturas, Boletas, Notas Crédito / Débito
          </p>
        </div>
      </div>

      {/* KPI 3: Detracciones SPOT */}
      <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm relative overflow-hidden">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Detracciones SPOT</span>
          <div className="p-2 rounded-lg bg-amber-950/60 text-amber-400 border border-amber-900">
            <Layers className="h-5 w-5" />
          </div>
        </div>
        <div className="mt-3">
          <span className="text-2xl font-bold font-mono tracking-tight text-amber-400 tabular-nums">
            {formatCurrency(totalDetractionsPEN, "PEN")}
          </span>
          <p className="text-xs text-slate-500 mt-1">
            Depósito obligatorio Banco de la Nación
          </p>
        </div>
      </div>

      {/* KPI 4: Tasa de Aceptación SUNAT */}
      <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm relative overflow-hidden">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Aceptación SUNAT</span>
          <div className="p-2 rounded-lg bg-teal-950/60 text-teal-400 border border-teal-900">
            <CheckCircle2 className="h-5 w-5" />
          </div>
        </div>
        <div className="mt-3">
          <span className="text-2xl font-bold font-mono tracking-tight text-white tabular-nums">
            {cdrAcceptanceRate}%
          </span>
          <p className="text-xs text-slate-500 mt-1">
            CDRs con código de respuesta exitoso (0)
          </p>
        </div>
      </div>
    </div>
  );
}
