"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchLiveTelemetry } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { Activity, Database, Inbox, ShieldCheck } from "lucide-react";

interface HeaderProps {
  activeTab: "ledger" | "dlq" | "telemetry" | "reports";
  onTabChange: (tab: "ledger" | "dlq" | "telemetry" | "reports") => void;
}

export function Header({ activeTab, onTabChange }: HeaderProps) {
  const { data: telemetry } = useQuery({
    queryKey: queryKeys.telemetry.live(),
    queryFn: fetchLiveTelemetry,
    refetchInterval: 5000,
  });

  const lagSeconds = telemetry?.replication?.lag_seconds ?? 0.0;
  const isHealthy = telemetry?.replication?.is_healthy ?? true;
  const activeMailboxes = telemetry?.mailboxes?.filter((m) => m.is_active).length ?? 1;

  // Semáforo visual de replicación Litestream a S3/R2
  let lagColor = "text-emerald-400 bg-emerald-950/40 border-emerald-800";
  let lagLabel = `Lag: ${lagSeconds.toFixed(2)}s`;
  if (lagSeconds >= 10.0 || !isHealthy) {
    lagColor = "text-rose-400 bg-rose-950/40 border-rose-800";
    lagLabel = `Lag Crítico: ${lagSeconds.toFixed(2)}s`;
  } else if (lagSeconds >= 5.0) {
    lagColor = "text-amber-400 bg-amber-950/40 border-amber-800";
    lagLabel = `Lag Moderado: ${lagSeconds.toFixed(2)}s`;
  }

  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo y Nombre */}
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold shadow-lg shadow-indigo-500/20">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-white">CajaClara</span>
              <span className="ml-2 text-xs font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-400 border border-indigo-800">
                Enterprise v1.1
              </span>
            </div>
          </div>

          {/* Navegación por pestañas */}
          <nav className="hidden md:flex items-center space-x-1" aria-label="Navegación principal">
            <button
              onClick={() => onTabChange("ledger")}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === "ledger"
                  ? "bg-slate-800 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              Libro Contable UBL
            </button>
            <button
              onClick={() => onTabChange("dlq")}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
                activeTab === "dlq"
                  ? "bg-slate-800 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              Consola DLQ
              {telemetry?.outbox_dlq?.dead_letter_depth ? (
                <span className="px-1.5 py-0.2 rounded-full text-xs bg-rose-600 text-white font-mono">
                  {telemetry.outbox_dlq.dead_letter_depth}
                </span>
              ) : null}
            </button>
            <button
              onClick={() => onTabChange("telemetry")}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === "telemetry"
                  ? "bg-slate-800 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              Telemetría & Memoria
            </button>
            <button
              onClick={() => onTabChange("reports")}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === "reports"
                  ? "bg-slate-800 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              Reportes SIRE & ERP
            </button>
          </nav>

          {/* Telemetría Pills en vivo */}
          <div className="flex items-center gap-2 text-xs font-mono">
            {/* Estado Litestream */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border ${lagColor}`}
              title="Latencia de replicación continua Litestream a S3/R2"
            >
              <Database className="h-3.5 w-3.5" />
              <span>{lagLabel}</span>
            </div>

            {/* Buzones Activos */}
            <div
              className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-slate-800 bg-slate-900/60 text-slate-300"
              title="Buzones IMAP sincronizados"
            >
              <Inbox className="h-3.5 w-3.5 text-indigo-400" />
              <span>Buzones: {activeMailboxes}</span>
            </div>

            {/* Sistema Online */}
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-emerald-800 bg-emerald-950/40 text-emerald-400">
              <Activity className="h-3.5 w-3.5 animate-pulse" />
              <span className="hidden sm:inline">Online</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
