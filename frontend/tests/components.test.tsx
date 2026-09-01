import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { formatCurrency, formatDate, getDocumentTypeLabel } from "@/lib/formatters";
import { HeroKPISection } from "@/components/hero-kpi-section";
import { ReportsExportHub } from "@/components/reports-export-hub";
import { FiscalLedgerTable } from "@/components/fiscal-ledger-table";
import { DLQManagementConsole } from "@/components/dlq-management-console";

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

function renderWithClient(ui: React.ReactElement) {
  const testClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={testClient}>
      {ui}
    </QueryClientProvider>
  );
}

describe("Utilidades de Formateo Contable Decimal (The Iron Law: Zero Floats)", () => {
  it("formatea moneda PEN con coma de miles y dos decimales exactos", () => {
    expect(formatCurrency("1482920.50", "PEN")).toBe("S/ 1,482,920.50");
    expect(formatCurrency("100.00", "PEN")).toBe("S/ 100.00");
    expect(formatCurrency("0.00", "PEN")).toBe("S/ 0.00");
    expect(formatCurrency(null, "PEN")).toBe("S/ 0.00");
  });

  it("formatea moneda USD con exactitud", () => {
    expect(formatCurrency("89450.00", "USD")).toBe("$ 89,450.00");
    expect(formatCurrency("12.50", "USD")).toBe("$ 12.50");
  });

  it("retorna etiquetas oficiales para tipos de comprobante de SUNAT", () => {
    expect(getDocumentTypeLabel("01")).toBe("Factura");
    expect(getDocumentTypeLabel("03")).toBe("Boleta");
    expect(getDocumentTypeLabel("07")).toBe("Nota de Crédito");
    expect(getDocumentTypeLabel("08")).toBe("Nota de Débito");
    expect(getDocumentTypeLabel("XX")).toBe("XX");
  });
});

describe("Componente ReportsExportHub", () => {
  it("renderiza botones de exportación accesibles para SIRE RCE y ERP CSV", () => {
    renderWithClient(<ReportsExportHub />);

    expect(screen.getByText("Centro de Exportación Fiscal & Contable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /descargar archivo sire rce/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /descargar csv contable/i })).toBeInTheDocument();
  });
});

describe("Componente HeroKPISection", () => {
  it("renderiza las cuatro tarjetas de KPIs fiscales", () => {
    renderWithClient(<HeroKPISection />);

    expect(screen.getByText(/total volumen \(pen\)/i)).toBeInTheDocument();
    expect(screen.getByText(/comprobantes/i)).toBeInTheDocument();
    expect(screen.getByText(/detracciones spot/i)).toBeInTheDocument();
    expect(screen.getByText(/aceptación sunat/i)).toBeInTheDocument();
  });
});

describe("Componente FiscalLedgerTable", () => {
  it("renderiza la tabla y los controles de filtrado", () => {
    renderWithClient(<FiscalLedgerTable />);

    expect(screen.getByPlaceholderText(/buscar ruc o proveedor/i)).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /libro contable de comprobantes/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/solo con detracción spot/i)).toBeInTheDocument();
  });
});

describe("Componente DLQManagementConsole", () => {
  it("renderiza la tabla de Dead Letter Queue", () => {
    renderWithClient(<DLQManagementConsole />);

    expect(screen.getByText(/dead letter queue \(transactional outbox\)/i)).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /consola de eventos dlq/i })).toBeInTheDocument();
  });
});
