"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchDLQEvents, replayAllDLQEvents, replayDLQEvent } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { formatDate } from "@/lib/formatters";
import { OutboxEvent } from "@/types/api";
import {
  AlertOctagon,
  CheckCircle2,
  Code2,
  ListRestart,
  RefreshCw,
  RotateCcw,
  X,
} from "lucide-react";

export function DLQManagementConsole() {
  const [selectedStatus, setSelectedStatus] = useState<string>("DEAD_LETTER");
  const [inspectPayloadEvent, setInspectPayloadEvent] = useState<OutboxEvent | null>(null);
  const [showBatchModal, setShowBatchModal] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const queryClient = useQueryClient();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: queryKeys.dlq.list(selectedStatus),
    queryFn: () => fetchDLQEvents(selectedStatus),
    refetchInterval: 5000,
  });

  // Mutación Pesimista para Replay Individual
  const replaySingleMutation = useMutation({
    mutationFn: (eventId: number) => replayDLQEvent(eventId),
    onSuccess: (res) => {
      setActionMessage(`Evento #${res.event_id} re-encolado con éxito a PENDING.`);
      queryClient.invalidateQueries({ queryKey: queryKeys.dlq.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.telemetry.live() });
      setTimeout(() => setActionMessage(null), 4000);
    },
    onError: (err: Error) => {
      setActionMessage(`Error al reintentar: ${err.message}`);
      setTimeout(() => setActionMessage(null), 6000);
    },
  });

  // Mutación Pesimista para Replay Masivo
  const replayBatchMutation = useMutation({
    mutationFn: () => replayAllDLQEvents(),
    onSuccess: (res) => {
      setShowBatchModal(false);
      setActionMessage(`Re-encolados ${res.replayed_count} eventos masivamente a PENDING.`);
      queryClient.invalidateQueries({ queryKey: queryKeys.dlq.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.telemetry.live() });
      setTimeout(() => setActionMessage(null), 5000);
    },
    onError: (err: Error) => {
      setActionMessage(`Error en replay masivo: ${err.message}`);
      setTimeout(() => setActionMessage(null), 6000);
    },
  });

  const events = data?.events ?? [];
  const deadLettersCount = data?.total_dead_letters ?? 0;

  return (
    <div className="space-y-4">
      {/* Banner de Estado y Acciones Superiores */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-rose-950/60 text-rose-400 border border-rose-900">
            <AlertOctagon className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white tracking-tight">
              Dead Letter Queue (Transactional Outbox)
            </h2>
            <p className="text-xs text-slate-400">
              Gestión y re-despacho atómico de eventos fallidos hacia Webhooks ERP y Alertas
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Selector de Estado */}
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-lg bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
          >
            <option value="DEAD_LETTER">DEAD_LETTER ({deadLettersCount})</option>
            <option value="PENDING">PENDING</option>
            <option value="DELIVERED">DELIVERED</option>
          </select>

          {/* Botón Replay Masivo */}
          {selectedStatus === "DEAD_LETTER" && deadLettersCount > 0 ? (
            <button
              onClick={() => setShowBatchModal(true)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white flex items-center gap-1.5 shadow-sm transition-colors"
            >
              <ListRestart className="h-4 w-4" />
              Reintentar Todos ({deadLettersCount})
            </button>
          ) : null}
        </div>
      </div>

      {/* Mensaje de Feedback Operacional */}
      {actionMessage ? (
        <div className="p-3 rounded-lg bg-indigo-950/80 border border-indigo-800 text-indigo-200 text-xs flex items-center justify-between">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-indigo-400 hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : null}

      {/* Tabla de Eventos DLQ */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden shadow-sm">
        <table className="w-full text-left text-sm" role="table" aria-label="Consola de Eventos DLQ">
          <thead className="bg-slate-950/70 border-b border-slate-800 text-xs font-semibold uppercase tracking-wider text-slate-400 font-sans">
            <tr>
              <th className="py-3 px-4">ID</th>
              <th className="py-3 px-4">Tipo de Evento</th>
              <th className="py-3 px-4">Intentos</th>
              <th className="py-3 px-4">Detalle del Error</th>
              <th className="py-3 px-4">Fecha Creación</th>
              <th className="py-3 px-4 text-center">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500 font-sans">
                  Cargando eventos de la cola outbox...
                </td>
              </tr>
            ) : isError ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-rose-400 font-sans">
                  Error: {error instanceof Error ? error.message : "Error desconocido"}
                </td>
              </tr>
            ) : events.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500 font-sans">
                  No hay eventos en estado {selectedStatus}.
                </td>
              </tr>
            ) : (
              events.map((ev) => (
                <tr key={ev.id} className="hover:bg-slate-800/40 transition-colors">
                  {/* ID */}
                  <td className="py-3 px-4 font-bold text-slate-300">
                    #{ev.id}
                  </td>

                  {/* Tipo de Evento */}
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-indigo-300 border border-slate-700 text-[11px]">
                      {ev.event_type}
                    </span>
                  </td>

                  {/* Intentos */}
                  <td className="py-3 px-4 tabular-nums text-slate-400">
                    {ev.retry_count} / 5
                  </td>

                  {/* Detalle del Error */}
                  <td className="py-3 px-4 max-w-xs truncate text-rose-400 font-sans text-xs" title={ev.error_detail || ""}>
                    {ev.error_detail || "Sin error registrado"}
                  </td>

                  {/* Fecha */}
                  <td className="py-3 px-4 text-slate-400">
                    {formatDate(ev.created_at)}
                  </td>

                  {/* Acciones */}
                  <td className="py-3 px-4 text-center">
                    <div className="flex items-center justify-center gap-2">
                      {/* Botón Inspeccionar Payload */}
                      <button
                        onClick={() => setInspectPayloadEvent(ev)}
                        className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-white"
                        title="Inspeccionar Payload JSON"
                      >
                        <Code2 className="h-4 w-4" />
                      </button>

                      {/* Botón Reintentar Evento */}
                      {ev.status === "DEAD_LETTER" ? (
                        <button
                          disabled={replaySingleMutation.isPending}
                          onClick={() => replaySingleMutation.mutate(ev.id)}
                          className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-slate-700 flex items-center gap-1 text-[11px] disabled:opacity-50"
                          title="Re-encolar a PENDING"
                        >
                          <RotateCcw className={`h-3 w-3 ${replaySingleMutation.isPending ? "animate-spin" : ""}`} />
                          Reintentar
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modal de Confirmación para Replay Masivo */}
      {showBatchModal ? (
        <div className="fixed inset-0 z-50 overflow-hidden bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-rose-400">
              <AlertOctagon className="h-6 w-6" />
              <h3 className="text-base font-bold text-white">Confirmar Replay Masivo DLQ</h3>
            </div>
            <p className="text-xs text-slate-300">
              Se reconmutarán atómicamente <span className="font-bold text-white">{deadLettersCount}</span> eventos de
              la Dead Letter Queue a estado <span className="font-mono text-emerald-400">PENDING</span> bajo SQLite{" "}
              <code className="bg-slate-950 px-1 rounded text-indigo-300">BEGIN IMMEDIATE</code>.
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setShowBatchModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300"
              >
                Cancelar
              </button>
              <button
                disabled={replayBatchMutation.isPending}
                onClick={() => replayBatchMutation.mutate()}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white flex items-center gap-1.5 shadow-sm"
              >
                {replayBatchMutation.isPending ? <RefreshCw className="h-4 w-4 animate-spin" /> : null}
                Confirmar Re-despacho
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Modal Inspector de Payload JSON */}
      {inspectPayloadEvent ? (
        <div className="fixed inset-0 z-50 overflow-hidden bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Code2 className="h-5 w-5 text-indigo-400" />
                <h3 className="text-sm font-bold text-white">Payload Evento #{inspectPayloadEvent.id}</h3>
              </div>
              <button
                onClick={() => setInspectPayloadEvent(null)}
                className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 font-mono text-xs text-slate-200 overflow-x-auto max-h-80">
              <pre>{JSON.stringify(JSON.parse(inspectPayloadEvent.payload || "{}"), null, 2)}</pre>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setInspectPayloadEvent(null)}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
