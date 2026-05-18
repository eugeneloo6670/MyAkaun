import { useState } from "react"
import Sidebar from "./Sidebar"
import Ledger from "./Ledger"
import RecordForm from "./RecordForm"
import Creditors from "./Creditors"
import MonthEnd from "./MonthEnd"
import KanbanTrail from "./KanbanTrail"
import AuditLog from "./AuditLog"
import Periods from "./Periods"
import RightPanel from "./RightPanel"
import HermesChatBar from "./HermesChatBar"

// View id used by Sidebar must match the keys here.
const VIEWS = {
  record:    { label: "Record entry", component: RecordForm },
  ledger:    { label: "Ledger",       component: Ledger },
  creditors: { label: "Creditors",    component: Creditors },
  kanban:    { label: "Audit trail",  component: KanbanTrail },
  month_end: { label: "Month-end",    component: MonthEnd },
  periods:   { label: "Periods",      component: Periods },
  audit_log: { label: "Audit log",    component: AuditLog },
}

export default function Shell() {
  const [activeView, setActiveView] = useState("record")
  const [selectedEntry, setSelectedEntry] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [paymentPrefill, setPaymentPrefill] = useState(null)

  const refresh = () => setRefreshKey(k => k + 1)

  const handleNavigate = (viewId) => {
    setActiveView(viewId)
    // Leaving record view clears any pending payment prefill
    if (viewId !== "record") setPaymentPrefill(null)
  }

  const handleSelectSupplier = (ctx) => {
    // Creditors -> Pay flow: prefill RecordForm with payment type + supplier
    setPaymentPrefill(ctx)
    setActiveView("record")
  }

  const renderView = () => {
    switch (activeView) {
      case "record":
        return (
          <RecordForm
            key={refreshKey}
            onRecorded={() => { refresh(); setPaymentPrefill(null) }}
            prefill={paymentPrefill}
          />
        )
      case "ledger":
        return (
          <Ledger
            key={refreshKey}
            onSelectEntry={setSelectedEntry}
            refreshTrigger={refreshKey}
          />
        )
      case "creditors":
        return (
          <Creditors
            key={refreshKey}
            onSelectSupplier={handleSelectSupplier}
            onSelectEntry={setSelectedEntry}
            refreshTrigger={refreshKey}
          />
        )
      default: {
        const View = VIEWS[activeView]?.component
        if (!View) return null
        return <View key={refreshKey} />
      }
    }
  }

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "180px 1fr 280px",
      gridTemplateRows: "1fr",
      height: "100vh",
      overflow: "hidden",
      fontFamily: "var(--font-sans)",
    }}>
      <Sidebar
        activeView={activeView}
        onNavigate={handleNavigate}
        refreshTrigger={refreshKey}
      />

      <div style={{
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        minWidth: 0,
      }}>
        <div style={{ flex: 1, overflow: "auto", minHeight: 0 }}>
          {renderView()}
        </div>
        <HermesChatBar />
      </div>

      <RightPanel
        entry={selectedEntry}
        onClose={() => setSelectedEntry(null)}
      />
    </div>
  )
}
