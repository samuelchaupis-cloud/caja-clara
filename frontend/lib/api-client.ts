import {
  DLQBatchReplayResponse,
  DLQEventListResponse,
  DLQReplayResponse,
  LedgerPaginationResponse,
  LiveTelemetryResponse,
} from "@/types/api";

const PROXY_BASE = "/api/proxy/api/v1";

export async function fetchLedger(params: Record<string, string | number | boolean | undefined>): Promise<LedgerPaginationResponse> {
  const searchParams = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") {
      searchParams.append(k, String(v));
    }
  }

  const url = `${PROXY_BASE}/ledger?${searchParams.toString()}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    throw new Error(`Error al consultar ledger contable: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function fetchDLQEvents(status: string = "DEAD_LETTER"): Promise<DLQEventListResponse> {
  const url = `${PROXY_BASE}/dlq/events?status=${encodeURIComponent(status)}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    throw new Error(`Error al consultar eventos DLQ: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function replayDLQEvent(eventId: number): Promise<DLQReplayResponse> {
  const url = `${PROXY_BASE}/dlq/replay/${eventId}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorBody.detail || `Error al reintentar evento ${eventId}`);
  }
  return res.json();
}

export async function replayAllDLQEvents(eventType?: string): Promise<DLQBatchReplayResponse> {
  let url = `${PROXY_BASE}/dlq/replay-all`;
  if (eventType) {
    url += `?event_type=${encodeURIComponent(eventType)}`;
  }
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorBody.detail || "Error en re-encolado masivo");
  }
  return res.json();
}

export async function fetchLiveTelemetry(): Promise<LiveTelemetryResponse> {
  const url = `${PROXY_BASE}/telemetry/live`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    throw new Error(`Error al consultar telemetría: ${res.status} ${res.statusText}`);
  }
  return res.json();
}
