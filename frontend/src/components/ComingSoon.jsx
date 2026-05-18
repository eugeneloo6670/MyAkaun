// Shared placeholder component for views not yet built.
// Used by MonthEnd, KanbanTrail, AuditLog, Periods.
export default function ComingSoon({ name, endpoint }) {
  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 40,
      gap: 12,
      color: 'var(--color-text-secondary)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
    }}>
      <div style={{ fontSize: 36, opacity: 0.3 }}>⏳</div>
      <h2 style={{
        margin: 0,
        fontSize: 18,
        fontWeight: 600,
        color: 'var(--color-text-primary)',
      }}>{name}</h2>
      <p style={{ margin: 0, fontSize: 13, textAlign: 'center', maxWidth: 320 }}>
        This view is queued for a future session. The backend endpoint{' '}
        <code style={{
          background: 'var(--color-background-secondary)',
          padding: '2px 6px',
          borderRadius: 3,
          fontSize: 12,
        }}>{endpoint}</code>{' '}
        is already available — only the UI is pending.
      </p>
    </div>
  )
}
