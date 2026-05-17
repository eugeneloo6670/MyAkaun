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

const VIEWS = {
  ledger:   { label: "Ledger",        component: Ledger },
  record:   { label: "Record entry",  component: RecordForm },
  creditors:{ label: "Creditors",     component: Creditors },
  monthend: { label: "Month-end",     component: MonthEnd },
  kanban:   { label: "Audit trail",   component: KanbanTrail },
  auditlog: { label: "Audit log",     component: AuditLog },
  periods:  { label: "Periods",       component: Periods },
}

export default function Shell() {
  const [activeView, setActiveView] = useState("ledger")
  const [selectedEntry, setSelectedEntry] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const View = VIEWS[activeView]?.component || Ledger
  const refresh = () => setRefreshKey(k => k + 1)

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "180px 1fr 260px",
      gridTemplateRows: "1fr auto",
      height: "100vh",
      overflow: "hidden",
      fontFamily: "var(--font-sans)",
    }}>
      {/* Left nav */}
      <Sidebar activeView={activeView} setActiveView={setActiveView} />

      {/* Main content */}
      <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <View
          key={refreshKey}
          onSelectEntry={setSelectedEntry}
          selectedEntry={selectedEntry}
          onRefresh={refresh}
        />
        {/* Hermes chat bar — always visible at bottom of main panel */}
        <HermesChatBar />
      </div>

      {/* Right detail panel */}
      <RightPanel
        entry={selectedEntry}
        onClose={() => setSelectedEntry(null)}
        onRefresh={refresh}
      />
    </div>
  )
}
