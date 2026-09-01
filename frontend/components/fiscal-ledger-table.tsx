"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchLedger } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { formatCurrency, formatDate, getDocumentTypeLabel } from "@/lib/formatters";
import { InvoiceListItem } from "@/types/api";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  FileCode,
  FileText,
  Filter,
  Search,
  X,
} from "lucide-react";

export function FiscalLedgerTable() {
  const [page, setPage] = useState(1);
  const [docType, setDocType] = useState<string>("");
  const [issuerQuery, setIssuerQuery] = useState<string>("");
  const [cdrStatus, setCdrStatus] = useState<string>("");
  const [hasSpot, setHasSpot] = useState<boolean | undefined>(undefined);
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceListItem | null>(null);

  const filters = {
    page,
    page_size: 20,
    document_type: docType || undefined,
    issuer_id: issuerQuery || undefined,
    cdr_status: cdrStatus || undefined,
    has_spot: hasSpot,
  };

  const { data, isLoading, isError, error } = useQuery({
    queryKey: queryKeys.ledger.list(filters),
    queryFn: () => fetchLedger(filters),
    placeholderData: (prev) => prev,
  });

  const items = data?.items ?? [];
  const pagination = data?.pagination;
  const summary = data?.summary;

  return (
    <div className="space-y-4">
      {/* Barra de Filtros Multifacética */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3 flex-1">
          {/* Búsqueda por RUC o Emisor */}
          <div className="relative min-w-[220px] flex-1 max-w-sm">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Buscar RUC o Proveedor..."
              value={issuerQuery}
              onChange={(e) => {
                setIssuerQuery(e.target.value);
                setPage(1);
              }}
              className="w-full pl-9 pr-3 py-1.5 text-sm rounded-lg bg-slate-950 border border-slate-800 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Filtro por Tipo de Comprobante */}
          <select
            value={docType}
            onChange={(e) => {
              setDocType(e.target.value);
              setPage(1);
            }}
            className="px-3 py-1.5 text-sm rounded-lg bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="">Todos los Comprobantes</option>
            <option value="01">01 - Factura Electrónica</option>
            <option value="03">03 - Boleta de Venta</option>
            <option value="07">07 - Nota de Crédito</option>
            <option value="08">08 - Nota de Débito</option>
          </select>

          {/* Filtro por Estado CDR */}
          <select
            value={cdrStatus}
            onChange={(e) => {
              setCdrStatus(e.target.value);
              setPage(1);
            }}
            className="px-3 py-1.5 text-sm rounded-lg bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="">Todos los Estados SUNAT</option>
            <option value="ACCEPTED">Aceptado (CDR OK)</option>
            <option value="REJECTED">Rechazado SUNAT</option>
          </select>

          {/* Switch Solo Detracciones SPOT */}
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={hasSpot === true}
              onChange={(e) => {
                setHasSpot(e.target.checked ? true : undefined);
                setPage(1);
              }}
              className="rounded bg-slate-950 border-slate-800 text-indigo-600 focus:ring-0 h-4 w-4"
            />
            Solo con Detracción SPOT
          </label>
        </div>

        {/* Resumen Contador */}
        <div className="text-xs text-slate-400 font-mono">
          Total: <span className="text-white font-bold">{pagination?.total_records ?? 0}</span> registros
        </div>
      </div>

      {/* Tabla Principal */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm" role="table" aria-label="Libro Contable de Comprobantes">
            <thead className="bg-slate-950/70 border-b border-slate-800 text-xs font-semibold uppercase tracking-wider text-slate-400">
              <tr>
                <th className="py-3 px-4">Comprobante</th>
                <th className="py-3 px-4">Emisor (RUC / Razón Social)</th>
                <th className="py-3 px-4">Fecha</th>
                <th className="py-3 px-4 text-right">Subtotal</th>
                <th className="py-3 px-4 text-right">IGV</th>
                <th className="py-3 px-4 text-right">SPOT</th>
                <th className="py-3 px-4 text-right">Total</th>
                <th className="py-3 px-4 text-center">CDR SUNAT</th>
                <th className="py-3 px-4 text-center">Detalle</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
              {isLoading ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-500 font-sans">
                    Cargando comprobantes contables...
                  </td>
                </tr>
              ) : isError ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-rose-400 font-sans">
                    Error al cargar datos: {error instanceof Error ? error.message : "Error desconocido"}
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-500 font-sans">
                    No se encontraron comprobantes fiscales que coincidan con los filtros.
                  </td>
                </tr>
              ) : (
                items.map((item) => {
                  const isAccepted = item.cdr_status === "ACCEPTED";
                  const isRejected = item.cdr_status === "REJECTED";
                  const hasDetraction = item.detraction_amount && item.detraction_amount !== "0.00";

                  return (
                    <tr
                      key={item.id}
                      onClick={() => setSelectedInvoice(item)}
                      className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                    >
                      {/* Comprobante y Tipo */}
                      <td className="py-3 px-4">
                        <div className="font-bold text-white tracking-tight">
                          {item.invoice_number || "S/N"}
                        </div>
                        <div className="text-[11px] text-slate-500 font-sans">
                          {getDocumentTypeLabel(item.document_type)}
                        </div>
                      </td>

                      {/* Emisor */}
                      <td className="py-3 px-4">
                        <div className="text-slate-300 font-sans truncate max-w-[200px]" title={item.issuer_name || ""}>
                          {item.issuer_name || "Sin Razón Social"}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          {item.issuer_id || "-"}
                        </div>
                      </td>

                      {/* Fecha */}
                      <td className="py-3 px-4 text-slate-400">
                        {formatDate(item.issue_date || item.received_date)}
                      </td>

                      {/* Subtotal */}
                      <td className="py-3 px-4 text-right tabular-nums text-slate-300">
                        {formatCurrency(item.subtotal, item.currency || "PEN")}
                      </td>

                      {/* IGV */}
                      <td className="py-3 px-4 text-right tabular-nums text-slate-400">
                        {formatCurrency(item.tax_amount, item.currency || "PEN")}
                      </td>

                      {/* SPOT */}
                      <td className="py-3 px-4 text-right tabular-nums">
                        {hasDetraction ? (
                          <span className="text-amber-400 font-medium" title={`Tasa: ${item.detraction_rate || 0}%`}>
                            {formatCurrency(item.detraction_amount, "PEN")}
                          </span>
                        ) : (
                          <span className="text-slate-600">-</span>
                        )}
                      </td>

                      {/* Total */}
                      <td className="py-3 px-4 text-right tabular-nums font-bold text-white">
                        {formatCurrency(item.total_amount, item.currency || "PEN")}
                      </td>

                      {/* CDR SUNAT */}
                      <td className="py-3 px-4 text-center">
                        {isAccepted ? (
                          <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-sans">
                            Aceptado
                          </span>
                        ) : isRejected ? (
                          <span className="px-2 py-0.5 rounded-full text-[10px] bg-rose-950 text-rose-400 border border-rose-800 font-sans">
                            Rechazado
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[10px] bg-slate-800 text-slate-400 font-sans">
                            Pendiente
                          </span>
                        )}
                      </td>

                      {/* Acciones */}
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedInvoice(item);
                          }}
                          className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-slate-200"
                          title="Ver Ficha y XML UBL"
                        >
                          <FileText className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Resumen Contable Dinámico Inferior */}
        {summary ? (
          <div className="bg-slate-950/80 border-t border-slate-800 p-4 grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
            <div>
              <span className="text-slate-500 uppercase tracking-wider text-[10px] block">Subtotal (PEN)</span>
              <span className="font-mono font-bold text-slate-200 tabular-nums">
                {formatCurrency(summary.total_subtotal_pen, "PEN")}
              </span>
            </div>
            <div>
              <span className="text-slate-500 uppercase tracking-wider text-[10px] block">IGV Total (PEN)</span>
              <span className="font-mono font-bold text-slate-200 tabular-nums">
                {formatCurrency(summary.total_tax_pen, "PEN")}
              </span>
            </div>
            <div>
              <span className="text-slate-500 uppercase tracking-wider text-[10px] block">Detracciones SPOT</span>
              <span className="font-mono font-bold text-amber-400 tabular-nums">
                {formatCurrency(summary.total_detractions_pen, "PEN")}
              </span>
            </div>
            <div>
              <span className="text-slate-500 uppercase tracking-wider text-[10px] block">Total General (PEN)</span>
              <span className="font-mono font-bold text-emerald-400 tabular-nums">
                {formatCurrency(summary.total_amount_pen, "PEN")}
              </span>
            </div>
            <div>
              <span className="text-slate-500 uppercase tracking-wider text-[10px] block">Total USD</span>
              <span className="font-mono font-bold text-indigo-400 tabular-nums">
                {formatCurrency(summary.total_amount_usd, "USD")}
              </span>
            </div>
          </div>
        ) : null}

        {/* Paginación */}
        {pagination && pagination.total_pages > 1 ? (
          <div className="bg-slate-950/40 border-t border-slate-800 px-4 py-3 flex items-center justify-between">
            <span className="text-xs text-slate-400">
              Página <span className="text-white font-bold">{pagination.current_page}</span> de{" "}
              <span className="text-white font-bold">{pagination.total_pages}</span>
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={!pagination.has_prev}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="p-1.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-800"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                disabled={!pagination.has_next}
                onClick={() => setPage((p) => p + 1)}
                className="p-1.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-800"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        ) : null}
      </div>

      {/* Drawer Lateral para Ficha de Comprobante e Inspector UBL 2.1 */}
      {selectedInvoice ? (
        <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm flex justify-end">
          <div className="w-full max-w-xl bg-slate-900 border-l border-slate-800 h-full p-6 overflow-y-auto shadow-2xl space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div>
                <h2 className="text-lg font-bold text-white tracking-tight">
                  {selectedInvoice.invoice_number || "Comprobante"}
                </h2>
                <p className="text-xs text-slate-400">
                  {getDocumentTypeLabel(selectedInvoice.document_type)} • {selectedInvoice.issuer_name}
                </p>
              </div>
              <button
                onClick={() => setSelectedInvoice(null)}
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Desglose Fiscal */}
            <div className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Desglose Fiscal UBL 2.1</h3>
              <div className="grid grid-cols-2 gap-3 text-xs bg-slate-950 p-4 rounded-lg border border-slate-800">
                <div>
                  <span className="text-slate-500 block">RUC Emisor:</span>
                  <span className="font-mono text-white">{selectedInvoice.issuer_id || "-"}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Moneda:</span>
                  <span className="font-mono text-white">{selectedInvoice.currency || "PEN"}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Subtotal (Base Imponible):</span>
                  <span className="font-mono text-white">{formatCurrency(selectedInvoice.subtotal, selectedInvoice.currency || "PEN")}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">IGV (18%):</span>
                  <span className="font-mono text-white">{formatCurrency(selectedInvoice.tax_amount, selectedInvoice.currency || "PEN")}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Detracción SPOT:</span>
                  <span className="font-mono text-amber-400">
                    {formatCurrency(selectedInvoice.detraction_amount, "PEN")} (Tasa: {selectedInvoice.detraction_rate || 0}%)
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">Importe Total:</span>
                  <span className="font-mono font-bold text-emerald-400">
                    {formatCurrency(selectedInvoice.total_amount, selectedInvoice.currency || "PEN")}
                  </span>
                </div>
              </div>
            </div>

            {/* Metadatos de Auditoría e Inmutabilidad */}
            <div className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Auditoría e Inmutabilidad</h3>
              <div className="text-xs bg-slate-950 p-4 rounded-lg border border-slate-800 space-y-2 font-mono">
                <div>
                  <span className="text-slate-500 block">Hash SHA-256 del Adjunto:</span>
                  <span className="text-slate-300 break-all text-[11px]">{selectedInvoice.attachment_hash || "Sin hash"}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Archivo UBL Original:</span>
                  <span className="text-indigo-400">{selectedInvoice.attachment_filename || "Sin adjunto"}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Buzón de Ingesta:</span>
                  <span className="text-slate-300">{selectedInvoice.mailbox_account}</span>
                </div>
              </div>
            </div>

            {/* Visor Sanitizado UBL 2.1 */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Estructura XML UBL 2.1</h3>
                <span className="text-[11px] text-emerald-400 flex items-center gap-1 font-mono">
                  <FileCode className="h-3.5 w-3.5" /> XXE-Protected
                </span>
              </div>
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto max-h-60">
                <pre>{`<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
  <ID>${selectedInvoice.invoice_number || ""}</ID>
  <IssueDate>${selectedInvoice.issue_date || ""}</IssueDate>
  <DocumentCurrencyCode>${selectedInvoice.currency || "PEN"}</DocumentCurrencyCode>
  <AccountingSupplierParty>
    <CustomerAssignedAccountID>${selectedInvoice.issuer_id || ""}</CustomerAssignedAccountID>
    <PartyLegalEntity>
      <RegistrationName>${selectedInvoice.issuer_name || ""}</RegistrationName>
    </PartyLegalEntity>
  </AccountingSupplierParty>
  <LegalMonetaryTotal>
    <LineExtensionAmount currencyID="${selectedInvoice.currency || "PEN"}">${selectedInvoice.subtotal || "0.00"}</LineExtensionAmount>
    <TaxInclusiveAmount currencyID="${selectedInvoice.currency || "PEN"}">${selectedInvoice.total_amount || "0.00"}</TaxInclusiveAmount>
    <PayableAmount currencyID="${selectedInvoice.currency || "PEN"}">${selectedInvoice.total_amount || "0.00"}</PayableAmount>
  </LegalMonetaryTotal>
</Invoice>`}</pre>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
