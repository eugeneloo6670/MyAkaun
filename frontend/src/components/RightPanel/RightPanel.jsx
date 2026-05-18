import { useEffect, useState, useMemo } from 'react';
import api, { getAuditLog, getEntries } from '../../api/client';
import styles from './RightPanel.module.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const fmtMYR = (n) => {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return new Intl.NumberFormat('en-MY', {
    style: 'currency',
    currency: 'MYR',
    minimumFractionDigits: 2,
  }).format(n);
};

const fmtFX = (amount, currency) => {
  if (amount === null || amount === undefined || isNaN(amount)) return '—';
  const n = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2 }).format(amount);
  return `${currency} ${n}`;
};

const fmtDateTime = (s) => {
  if (!s) return '—';
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return d.toLocaleString('en-MY', {
    year: 'numeric', month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
};

const fmtDate = (s) => (s ? s.slice(0, 10) : '—');

const typeLabel = (t) => {
  switch (t) {
    case 'purchase':    return 'Purchase';
    case 'credit_note': return 'Credit Note';
    case 'return':      return 'Return';
    case 'payment':     return 'Payment';
    default:            return t || '—';
  }
};

const auditActionLabel = (action) => {
  switch (action) {
    case 'CREATE':      return 'Created';
    case 'DELETE':      return 'Deleted';
    case 'LOCK':        return 'Period locked';
    case 'UNLOCK':      return 'Period unlocked';
    case 'UPDATE':      return 'Updated';
    case 'LINK':        return 'Linked';
    default:            return action || '—';
  }
};

const auditClass = (action, styles) => {
  switch (action) {
    case 'CREATE':      return styles.auditCreate;
    case 'DELETE':      return styles.auditDelete;
    case 'LOCK':        return styles.auditLock;
    case 'UNLOCK':      return styles.auditUnlock;
    default:            return styles.auditNeutral;
  }
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RightPanel({ entry, onClose, onDelete }) {
  const [auditTrail, setAuditTrail] = useState([]);
  const [linkedEntries, setLinkedEntries] = useState([]);
  const [loadingAudit, setLoadingAudit] = useState(false);

  // Load audit trail + linked entries for the entry
  useEffect(() => {
    if (!entry?.short_id) {
      setAuditTrail([]);
      setLinkedEntries([]);
      return;
    }

    let cancelled = false;
    setLoadingAudit(true);

    Promise.allSettled([
      getAuditLog({ short_id: entry.short_id }),
      // Linked entries: find any entry that links TO this one, OR the one this entry links TO
      getEntries({ linked_to: entry.short_id }),
    ]).then(([auditRes, linkedRes]) => {
      if (cancelled) return;
      if (auditRes.status === 'fulfilled') {
        const data = auditRes.value.data;
        setAuditTrail(Array.isArray(data) ? data : []);
      } else {
        setAuditTrail([]);
      }
      if (linkedRes.status === 'fulfilled') {
        const data = linkedRes.value.data;
        setLinkedEntries(Array.isArray(data) ? data : []);
      } else {
        setLinkedEntries([]);
      }
    }).finally(() => {
      if (!cancelled) setLoadingAudit(false);
    });

    return () => { cancelled = true; };
  }, [entry?.short_id]);

  // -------------------------------------------------------------------------
  // Empty state
  // -------------------------------------------------------------------------

  if (!entry) {
    return (
      <aside className={styles.panel}>
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>◷</div>
          <div className={styles.emptyTitle}>No entry selected</div>
          <div className={styles.emptyText}>
            Click any row in the ledger to view its full detail and audit trail here.
          </div>
        </div>
      </aside>
    );
  }

  const amount = Number(entry.total ?? 0);
  const isNegative = amount < 0;
  const hasFX = Boolean(entry.orig_ccy && entry.orig_ccy !== 'MYR');

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <aside className={styles.panel} aria-label="Entry detail">
      <header className={styles.header}>
        <div>
          <div className={styles.txnId}>{entry.short_id}</div>
          <div className={styles.entryType}>{typeLabel(entry.type)}</div>
        </div>
        {onClose && (
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close">
            ×
          </button>
        )}
      </header>

      {/* Doc status alert */}
      {!entry.doc_ref && (
        <div className={styles.docAlert}>
          🔴 No supporting document on file. This entry is flagged in audit reports.
        </div>
      )}

      {/* Amount */}
      <div className={styles.amountBlock}>
        <div className={styles.amountLabel}>Amount</div>
        <div className={`${styles.amountValue} ${isNegative ? styles.amountNeg : ''}`}>
          {fmtMYR(amount)}
        </div>
        {hasFX && (
          <div className={styles.fxDetail}>
            <div>
              <span className={styles.fxLabel}>Original</span>
              <span className={styles.fxValue}>
                {fmtFX(entry.orig_amount, entry.orig_ccy)}
              </span>
            </div>
            <div>
              <span className={styles.fxLabel}>FX rate</span>
              <span className={styles.fxValue}>{entry.fx_rate}</span>
            </div>
          </div>
        )}
      </div>

      {/* Field list */}
      <dl className={styles.fields}>
        <FieldRow label="Date">{fmtDate(entry.date)}</FieldRow>
        <FieldRow label="Supplier">{entry.supplier || '—'}</FieldRow>
        <FieldRow label="Reference">{entry.reference || '—'}</FieldRow>
        <FieldRow label="GL category">
          <code className={styles.code}>{entry.gl_code || '—'}</code>
        </FieldRow>
        {entry.sst_rate !== undefined && entry.sst_rate !== null && (
          <FieldRow label="SST">{entry.sst_rate}%</FieldRow>
        )}
        {entry.payment_method && (
          <FieldRow label="Method">{entry.payment_method.replace('_', ' ')}</FieldRow>
        )}
        {entry.discount_received > 0 && (
          <FieldRow label="Discount taken">
            <span className={styles.discountChip}>
              {fmtMYR(entry.discount_received)} → GL 4200
            </span>
          </FieldRow>
        )}
        <FieldRow label="Document">
          {entry.doc_ref
            ? <span className={styles.flagOk}>🟢 {entry.doc_ref}</span>
            : <span className={styles.flagMissing}>🔴 Missing</span>
          }
        </FieldRow>
        <FieldRow label="Recorded by">
          <div className={styles.userRow}>
            <span className={styles.userChip}>
              {(entry.recorded_by || '?').charAt(0).toUpperCase()}
            </span>
            <span>{entry.recorded_by || '—'}</span>
          </div>
        </FieldRow>
      </dl>

      {/* Linked transactions */}
      {linkedEntries.length > 0 && (
        <section className={styles.section}>
          <div className={styles.sectionTitle}>Linked transactions</div>
          <div className={styles.linkChips}>
            {linkedEntries.map((l) => (
              <div key={l.short_id} className={styles.linkChip}>
                <code className={styles.code}>{l.short_id}</code>
                <span className={styles.linkType}>{typeLabel(l.type)}</span>
                <span className={styles.linkAmount}>
                  {fmtMYR(Number(l.total ?? 0))}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Audit trail */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>Audit trail</div>
        {loadingAudit && <div className={styles.muted}>Loading…</div>}
        {!loadingAudit && auditTrail.length === 0 && (
          <div className={styles.muted}>No audit events found.</div>
        )}
        {!loadingAudit && auditTrail.length > 0 && (
          <ol className={styles.timeline}>
            {auditTrail.map((evt, idx) => (
              <li key={evt.id || idx} className={styles.timelineItem}>
                <span className={`${styles.timelineDot} ${auditClass(evt.action, styles)}`} />
                <div className={styles.timelineContent}>
                  <div className={styles.timelineAction}>
                    {auditActionLabel(evt.action)}
                  </div>
                  <div className={styles.timelineMeta}>
                    {fmtDateTime(evt.timestamp)}
                    {evt.user_name && <> · {evt.user_name}</>}
                  </div>
                  {evt.description && (
                    <div className={styles.timelineNote}>{evt.description}</div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* Actions */}
      {onDelete && (
        <div className={styles.actionFooter}>
          <button
            type="button"
            className={styles.deleteBtn}
            onClick={() => onDelete(entry)}
          >
            Void entry
          </button>
          <div className={styles.actionHint}>
            Voiding creates a reversing entry. Original record is retained for audit.
          </div>
        </div>
      )}
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function FieldRow({ label, children }) {
  return (
    <>
      <dt className={styles.fieldLabel}>{label}</dt>
      <dd className={styles.fieldValue}>{children}</dd>
    </>
  );
}
