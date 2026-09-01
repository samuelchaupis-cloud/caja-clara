export const queryKeys = {
  ledger: {
    all: () => ["ledger"] as const,
    lists: () => [...queryKeys.ledger.all(), "list"] as const,
    list: (filters: Record<string, unknown>) => [...queryKeys.ledger.lists(), filters] as const,
    detail: (id: number | string) => [...queryKeys.ledger.all(), "detail", id] as const,
  },
  dlq: {
    all: () => ["dlq"] as const,
    lists: () => [...queryKeys.dlq.all(), "list"] as const,
    list: (status: string, eventType?: string) =>
      [...queryKeys.dlq.lists(), { status, eventType }] as const,
    detail: (id: number) => [...queryKeys.dlq.all(), "detail", id] as const,
  },
  telemetry: {
    all: () => ["telemetry"] as const,
    live: () => [...queryKeys.telemetry.all(), "live"] as const,
  },
};
