import { useState, useEffect, useMemo, useCallback } from 'react';
import { api } from '../../api/client';
import styles from './Ledger.module.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TYPE_OPTIONS = [
  { id: '',            label: 'All types' },
  { id: 'purchase',    label: 'Purchase' },
  { id: 'credit_note', label: 'Credit Note' },
  { id: 'return',      label: 'Return' },
  { id: 'payment',     label: 'Payment' },
];

const GL_OPTIONS = [
  { code: '',     label: 'All GL' },
  { code: '2100', label: '2100 Accounts Payable' },
  { code: '4200', label: '4200 Discount Received' },
  { code: '5100', label: '5100 COGS' },
  { code: '5200', label: '5200 Utilities' },
  { code: '5300', label: '5300 Repairs' },
  { code: '5400', label: '5400 Office Supplies' },
  { code: '5500', label: '5500 Transport' },
  { code: '5600', label: '5600 Professional Fees' },
  { code: '5700', label: '5700 Rental' },
  { code: '5800', label: '5800 Other' },
];

const DOC_FILTER_OPTIONS = [
  { id: '',        label: 'Any doc status' },
  { id: 'filed',   label: '🟢 Filed only' },
  { id: 'missing', label: '🔴 Missing only' },
];

const PAGE_SIZE = 50;

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

const fmtDate = (s) => {
  if (!s) return '—';
  // Accept ISO date or full timestamp; render as YYYY-MM-DD
  return s.slice(0, 10);
};

const typeLabel = (t) => {
  switch (t) {
    case 'purchase':    return 'Purchase';
    case 'credit_note': return 'Credit Note';
    case 'return':      return 'Return';
    case 'payment':     return 'Payment';
    default:            return t || '—';
  }
};

const typeBadgeClass = (t) => {
  switch (t) {
    case 'purchase':    return styles.badgePurchase;
    case 'credit_note': return styles.badgeCredit;
    case 'return':      return styles.badgeReturn;
    case 'payment':     return styles.badgePayment;
    default:            return styles.badgeNeutral;
  }
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Ledger({ onSelectEntry, refreshTrigger }) {
  const [filters, setFilters] = useState({
    type: '',
    gl_code: '',
    supplier: '',
    date_from: '',
    date_to: '',
    doc_status: '',
    search: '',
  });

  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [selectedId, setSelectedId] = useState(null);

  // -------------------------------------------------------------------------
  // Data fetch
  // -------------------------------------------------------------------------

  const loadEntries = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      };
      if (filters.type)       params.type       = filters.type;
      if (filters.gl_code)    params.gl_code    = filters.gl_code;
      if (filters.supplier)   params.supplier   = filters.supplier;
      if (filters.date_from)  params.date_from  = filters.date_from;
      if (filters.date_to)    params.date_to    = filters.date_to;
      if (filters.doc_status) params.doc_status = filters.doc_status;
      if (filters.search)     params.search     = filters.search;

      const res = await api.get('/api/entries', { params });
      // Backend may return { entries: [...], total: N } or just an array
      if (Array.isArray(res.data)) {
        setEntries(res.data);
        setTotal(res.data.length);
      } else {
        setEntries(res.data?.entries || []);
        setTotal(res.data?.total ?? (res.data?.entries?.length || 0));
      }
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to load entries');
      setEntries([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => { loadEntries(); }, [loadEntries, refreshTrigger]);

  // Reset page on filter change
  useEffect(() => { setPage(1); }, [
    filters.type, filters.gl_code, filters.supplier,
    filters.date_from, filters.date_to, filters.doc_status, filters.search,
  ]);

  // -------------------------------------------------------------------------
  // Derived
  // -------------------------------------------------------------------------

  const metrics = useMemo(() => {
    const m = {
      count: entries.length,
      totalDebit: 0,
      totalCredit: 0,
      missingDocs: 0,
    };
    for (const e of entries) {
      const amt = Number(e.amount_myr ?? e.amount ?? 0);
      if (amt >= 0) m.totalDebit += amt;
      else m.totalCredit += Math.abs(amt);
      if (!e.doc_ref) m.missingDocs++;
    }
    return m;
  }, [entries]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const setFilter = (key, value) =>
    setFilters((f) => ({ ...f, [key]: value }));

  const clearFilters = () => setFilters({
    type: '', gl_code: '', supplier: '',
    date_from: '', date_to: '', doc_status: '', search: '',
  });

  const handleRowClick = (entry) => {
    setSelectedId(entry.txn_id);
    if (onSelectEntry) onSelectEntry(entry);
  };

  const handleExport = () => {
    if (!entries.length) return;
    const headers = [
      'TXN ID', 'Date', 'Type', 'Supplier', 'Reference',
      'GL', 'Amount MYR', 'SST %', 'Doc Ref', 'Recorded By',
    ];
    const rows = entries.map((e) => [
      e.txn_id, fmtDate(e.date), typeLabel(e.type),
      e.supplier, e.reference, e.gl_code,
      e.amount_myr ?? e.amount, e.sst_rate ?? '',
      e.doc_ref || '', e.recorded_by || '',
    ]);
    const csv = [headers, ...rows]
      .map((r) => r.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(','))
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ledger-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className={styles.ledger}>
      <header className={styles.header}>
        <div className={styles.titleBlock}>
          <h2 className={styles.title}>Ledger</h2>
          <div className={styles.subtitle}>All recorded entries with full audit trail</div>
        </div>
        <button
          type="button"
          className={styles.exportBtn}
          onClick={handleExport}
          disabled={!entries.length}
        >
          ⤓ Export CSV
        </button>
      </header>

      {/* Filters */}
      <div className={styles.filters}>
        <input
          type="text"
          placeholder="Search supplier, reference, TXN…"
          value={filters.search}
          onChange={(e) => setFilter('search', e.target.value)}
          className={`${styles.input} ${styles.searchInput}`}
        />
        <select
          value={filters.type}
          onChange={(e) => setFilter('type', e.target.value)}
          className={styles.input}
        >
          {TYPE_OPTIONS.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
        </select>
        <select
          value={filters.gl_code}
          onChange={(e) => setFilter('gl_code', e.target.value)}
          className={styles.input}
        >
          {GL_OPTIONS.map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
        </select>
        <input
          type="date"
          value={filters.date_from}
          onChange={(e) => setFilter('date_from', e.target.value)}
          className={styles.input}
          aria-label="From date"
        />
        <input
          type="date"
          value={filters.date_to}
          onChange={(e) => setFilter('date_to', e.target.value)}
          className={styles.input}
          aria-label="To date"
        />
        <select
          value={filters.doc_status}
          onChange={(e) => setFilter('doc_status', e.target.value)}
          className={styles.input}
        >
          {DOC_FILTER_OPTIONS.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
        </select>
        <button
          type="button"
          className={styles.clearBtn}
          onClick={clearFilters}
        >
          Clear
        </button>
      </div>

      {/* Metrics */}
      <div className={styles.metrics}>
        <Metric label="Entries shown" value={metrics.count} />
        <Metric label="Total debit" value={fmtMYR(metrics.totalDebit)} />
        <Metric label="Total credit" value={fmtMYR(metrics.totalCredit)} />
        <Metric
          label="Missing docs"
          value={metrics.missingDocs}
          flag={metrics.missingDocs > 0 ? 'red' : null}
        />
      </div>

      {/* Table */}
      <div className={styles.tableWrap}>
        {loading && <div className={styles.state}>Loading entries…</div>}
        {error && <div className={`${styles.state} ${styles.stateError}`}>{error}</div>}
        {!loading && !error && entries.length === 0 && (
          <div className={styles.state}>No entries match the current filters.</div>
        )}
        {!loading && !error && entries.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.colTxn}>TXN ID</th>
                <th className={styles.colDate}>Date</th>
                <th className={styles.colType}>Type</th>
                <th className={styles.colSupplier}>Supplier</th>
                <th className={styles.colRef}>Reference</th>
                <th className={styles.colGl}>GL</th>
                <th className={styles.colAmount}>Amount (MYR)</th>
                <th className={styles.colDoc}>Doc</th>
                <th className={styles.colRecBy}>Recorded</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => {
                const amt = Number(e.amount_myr ?? e.amount ?? 0);
                const isNegative = amt < 0;
                const isSelected = selectedId === e.txn_id;
                return (
                  <tr
                    key={e.txn_id || `${e.date}-${e.reference}`}
                    className={`${styles.row} ${isSelected ? styles.rowSelected : ''}`}
                    onClick={() => handleRowClick(e)}
                  >
                    <td className={styles.colTxn}>
                      <code className={styles.txnId}>{e.txn_id}</code>
                    </td>
                    <td className={styles.colDate}>{fmtDate(e.date)}</td>
                    <td className={styles.colType}>
                      <span className={`${styles.badge} ${typeBadgeClass(e.type)}`}>
                        {typeLabel(e.type)}
                      </span>
                    </td>
                    <td className={styles.colSupplier}>{e.supplier || '—'}</td>
                    <td className={styles.colRef}>{e.reference || '—'}</td>
                    <td className={styles.colGl}>
                      <code className={styles.glCode}>{e.gl_code || '—'}</code>
                    </td>
                    <td className={`${styles.colAmount} ${isNegative ? styles.amountNeg : ''}`}>
                      {fmtMYR(amt)}
                      {e.fx_currency && (
                        <div className={styles.fxLine}>
                          {e.fx_original} {e.fx_currency} @ {e.fx_rate}
                        </div>
                      )}
                    </td>
                    <td className={styles.colDoc}>
                      <span
                        className={e.doc_ref ? styles.flagOk : styles.flagMissing}
                        title={e.doc_ref || 'No supporting document'}
                      >
                        {e.doc_ref ? '🟢' : '🔴'}
                      </span>
                    </td>
                    <td className={styles.colRecBy}>
                      <span className={styles.userChip}>
                        {(e.recorded_by || '?').charAt(0).toUpperCase()}
                      </span>
                      <span className={styles.userName}>{e.recorded_by || '—'}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button
            type="button"
            disabled={page === 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className={styles.pageBtn}
          >
            ← Prev
          </button>
          <span className={styles.pageInfo}>
            Page {page} of {totalPages} · {total} entries
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className={styles.pageBtn}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Metric({ label, value, flag }) {
  return (
    <div className={`${styles.metric} ${flag === 'red' ? styles.metricRed : ''}`}>
      <div className={styles.metricLabel}>{label}</div>
      <div className={styles.metricValue}>{value}</div>
    </div>
  );
}
