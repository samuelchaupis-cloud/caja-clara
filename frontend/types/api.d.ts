export interface InvoiceListItem {
  id: number;
  message_id: string;
  mailbox_account: string;
  sender_email: string;
  received_date: string;
  document_type?: string | null;
  issuer_id?: string | null;
  issuer_name?: string | null;
  invoice_number?: string | null;
  issue_date?: string | null;
  currency?: string | null;
  subtotal?: string | null;
  tax_amount?: string | null;
  total_amount?: string | null;
  detraction_amount?: string | null;
  detraction_rate?: string | null;
  cdr_status?: string | null;
  attachment_filename?: string | null;
  attachment_hash?: string | null;
  status: string;
  created_at: string;
}

export interface LedgerSummary {
  total_subtotal_pen: string;
  total_tax_pen: string;
  total_amount_pen: string;
  total_detractions_pen: string;
  total_amount_usd: string;
}

export interface PaginationMeta {
  total_records: number;
  current_page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface LedgerPaginationResponse {
  items: InvoiceListItem[];
  pagination: PaginationMeta;
  summary: LedgerSummary;
}

export interface OutboxEvent {
  id: number;
  event_type: string;
  payload: string;
  status: string;
  retry_count: number;
  created_at: string;
  next_retry_at?: string | null;
  processed_at?: string | null;
  error_detail?: string | null;
}

export interface DLQEventListResponse {
  events: OutboxEvent[];
  total_dead_letters: number;
  total_pending: number;
}

export interface DLQReplayResponse {
  status: string;
  event_id: number;
  new_status: string;
}

export interface DLQBatchReplayResponse {
  status: string;
  replayed_count: number;
}

export interface LiveTelemetryResponse {
  timestamp: string;
  process: {
    rss_memory_bytes: number;
    rss_memory_human: string;
    db_size_bytes: number;
    db_size_human: string;
  };
  invoices: {
    total_processed: number;
    total_errors: number;
    by_document_type: Record<string, number>;
    by_status: Record<string, number>;
  };
  outbox_dlq: {
    pending_depth: number;
    delivered_depth: number;
    dead_letter_depth: number;
    retries_total: number;
  };
  replication: {
    status: string;
    storage_provider: string;
    lag_seconds: number;
    sync_errors_total: number;
    is_healthy: boolean;
  };
  mailboxes: Array<{
    account: string;
    status: string;
    is_active: boolean;
    total_extracted: number;
  }>;
}
