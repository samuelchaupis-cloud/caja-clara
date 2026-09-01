"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchLiveTelemetry } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { Activity, Cpu, Database, HardDrive, Inbox, ShieldCheck } from "lucide-react";

export function TelemetryView() {
  const { data: telemetry, isLoading, isError, error } = useQuery({
    queryKey: queryKeys.telemetry.live(),
    queryFn: fetchLiveTelemetry,
    refetchInterval: 3000,
  });

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500 text-sm">Cargando telemetría en tiempo real...</div>;
  }

  if (isError) {
    return (
      <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-sm">
        Error al obtener telemetría: {error instanceof Error ? error.message : "Error desconocido"}
      </div>
    );
  }

  const memoryRssBytes = telemetry?.process?.rss_memory_bytes ?? 0;
  const memoryRssMB = (memoryRssBytes / (1024 * 1024)).toFixed(1);
  const isMemorySafe = memoryRssBytes < 45 * 1024 * 1024; // Invariante estricto < 45MB

  const lagSeconds = telemetry?.replication?.lag_seconds ?? 0.0;
  const isLagSafe = lagSeconds < 10.0;

  return (
    <div className="space-y-6">
      <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-4">
        <div>
          <h2 className="text-base font-bold text-white tracking-tight">Telemetría Operacional & Resiliencia</h2>
          <p className="text-xs text-slate-400">
            Observabilidad en vivo de memoria de proceso, latencia Litestream a S3/R2 y salud de buzones IMAP.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Card 1: Memoria RSS */}
          <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-400">
              <span className="flex items-center gap-1.5">
                <Cpu className="h-4 w-4 text-indigo-400" /> Memoria Residente (RSS)
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] ${isMemorySafe ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-rose-950 text-rose-400 border border-rose-800"}`}>
                {isMemorySafe ? "Límite < 45MB OK" : "Excede Límite"}
              </span>
            </div>
            <div className="font-mono text-2xl font-bold text-white tabular-nums">
              {memoryRssMB} MB
            </div>
            <p className="text-[11px] text-slate-500">
              Uso estricto de streaming sin buffers acumulativos.
            </p>
          </div>

          {/* Card 2: Replicación Litestream */}
          <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-400">
              <span className="flex items-center gap-1.5">
                <Database className="h-4 w-4 text-emerald-400" /> Litestream Lag (S3/R2)
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] ${isLagSafe ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-rose-950 text-rose-400 border border-rose-800"}`}>
                {telemetry?.replication?.status?.toUpperCase()}
              </span>
            </div>
            <div className="font-mono text-2xl font-bold text-emerald-400 tabular-nums">
              {lagSeconds.toFixed(3)} s
            </div>
            <p className="text-[11px] text-slate-500">
              Proveedor: {telemetry?.replication?.storage_provider?.toUpperCase()} • Errores: {telemetry?.replication?.sync_errors_total ?? 0}
            </p>
          </div>

          {/* Card 3: Base de Datos SQLite WAL */}
          <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-400">
              <span className="flex items-center gap-1.5">
                <HardDrive className="h-4 w-4 text-amber-400" /> Tamaño Base SQLite
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 font-mono">
                WAL Mode
              </span>
            </div>
            <div className="font-mono text-2xl font-bold text-white tabular-nums">
              {telemetry?.process?.db_size_human ?? "1.0 MB"}
            </div>
            <p className="text-[11px] text-slate-500">
              BEGIN IMMEDIATE + autocheckpoint=1000 activo.
            </p>
          </div>
        </div>

        {/* Lista de Buzones IMAP */}
        <div className="mt-6 space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Buzones IMAP Conectados</h3>
          <div className="rounded-lg border border-slate-800 bg-slate-950 divide-y divide-slate-800/60">
            {telemetry?.mailboxes?.map((mb, idx) => (
              <div key={idx} className="p-3 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <Inbox className="h-4 w-4 text-indigo-400" />
                  <span className="font-mono text-slate-200">{mb.account}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-slate-500">Extraídas: <strong className="text-white font-mono">{mb.total_extracted}</strong></span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800">
                    {mb.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
