"use client";

import { useState } from "react";
import { Header } from "@/components/header";
import { HeroKPISection } from "@/components/hero-kpi-section";
import { FiscalLedgerTable } from "@/components/fiscal-ledger-table";
import { DLQManagementConsole } from "@/components/dlq-management-console";
import { TelemetryView } from "@/components/telemetry-view";
import { ReportsExportHub } from "@/components/reports-export-hub";

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<"ledger" | "dlq" | "telemetry" | "reports">("ledger");

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 selection:bg-indigo-500 selection:text-white">
      {/* Barra de Navegación & Telemetría */}
      <Header activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Sección de Indicadores Clave en Vivo (KPI Cards) */}
        <HeroKPISection />

        {/* Contenido según Pestaña Activa */}
        {activeTab === "ledger" && <FiscalLedgerTable />}
        {activeTab === "dlq" && <DLQManagementConsole />}
        {activeTab === "telemetry" && <TelemetryView />}
        {activeTab === "reports" && <ReportsExportHub />}
      </main>

      {/* Footer Institucional */}
      <footer className="border-t border-slate-900 bg-slate-950 py-4 text-center text-xs text-slate-600 font-mono">
        CajaClara Enterprise • Sistema Contable UBL 2.1 & Transactional Outbox • SQLite WAL Mode
      </footer>
    </div>
  );
}
