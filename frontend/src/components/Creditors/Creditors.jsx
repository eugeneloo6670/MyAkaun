import { Fragment, useState, useEffect, useMemo } from 'react';
import api, { getCreditors, getEntries } from '../../api/client';
import styles from './Creditors.module.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BUCKETS = [
  { id: 'current', label: 'Current',   range: '0–30 d',    key: 'current' },
  { id: 'b30',     label: '31–60 d',   range: '31–60 d',   key: 'd30' },
  { id: 'b60',     label: '61–90 d',   range: '61–90 d',   key: 'd60' },
  { id: 'b90',     label: '90+ d',     range: '90+ d',     key: 'd90plus' },
];

const SORT_OPTIONS = [
  { id: 'balance_desc', label: 'Balance (high → low)' },
  { id: 'balance_asc',  label: 'Balance (low → high)' },
  { id: 'supplier',     label: 'Supplier name' },
  { id: 'oldest',       label: 'Oldest first' },
];

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

const fmtDate = (s) => (s ? s.slice(0, 10) : '—');

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Creditors({ onSelectSupplier, onSelectEntry, refreshTrigger }) {
  const [creditors, setCreditors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sort, setSort] = useState('balance_desc');
  const [expandedSupplier, setExpandedSupplier] = useState(null);
  const [supplierEntries, setSupplierEntries] = useState({});
  const [loadingSupplier, setLoadingSupplier] = useState(null);

  // -------------------------------------------------------------------------
  // Load creditors
  // -------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getCreditors()
      .then((res) => {
        if (cancelled) return;
        const data = Array.isArray(res.data) ? res.data : [];
        // Filter out fully-settled creditors (balance ≈ 0) for cleaner view
        setCreditors(data.filter((c) => Math.abs(Number(c.balance ?? 0)) > 0.005));
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.data?.detail || 'Failed to load creditors');
        setCreditors([]);
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [refreshTrigger]);

  // -------------------------------------------------------------------------
  // Drill-down: load entries for expanded supplier
  // -------------------------------------------------------------------------

  useEffect(() => {
    if (!expandedSupplier) return;
    if (supplierEntries[expandedSupplier]) return; // already loaded

    let cancelled = false;
    setLoadingSupplier(expandedSupplier);

    getEntries({ supplier: expandedSupplier })
      .then((res) => {
        if (cancelled) return;
        const list = Array.isArray(res.data) ? res.data : [];
        setSupplierEntries((prev) => ({ ...prev, [expandedSupplier]: list }));
      })
      .catch(() => {
        if (!cancelled) {
          setSupplierEntries((prev) => ({ ...prev, [expandedSupplier]: [] }));
        }
      })
      .finally(() => { if (!cancelled) setLoadingSupplier(null); });

    return () => { cancelled = true; };
  }, [expandedSupplier, supplierEntries]);

  // -------------------------------------------------------------------------
  // Derived
  // -------------------------------------------------------------------------

  const totals = useMemo(() => {
    const t = { total: 0, current: 0, d30: 0, d60: 0, d90plus: 0 };
    for (const c of creditors) {
      t.total   += Number(c.balance ?? 0);
      t.current += Number(c.aged?.current ?? 0);
      t.d30     += Number(c.aged?.d30 ?? 0);
      t.d60     += Number(c.aged?.d60 ?? 0);
      t.d90plus += Number(c.aged?.d90plus ?? 0);
    }
    return t;
  }, [creditors]);

  const sortedCreditors = useMemo(() => {
    const arr = [...creditors];
    switch (sort) {
      case 'balance_asc':
        return arr.sort((a, b) => Number(a.balance ?? 0) - Number(b.balance ?? 0));
      case 'supplier':
        return arr.sort((a, b) => (a.supplier || '').localeCompare(b.supplier || ''));
      case 'oldest':
        return arr.sort((a, b) =>
          Number(b.aged?.d90plus ?? 0) - Number(a.aged?.d90plus ?? 0)
        );
      case 'balance_desc':
      default:
        return arr.sort((a, b) => Number(b.balance ?? 0) - Number(a.balance ?? 0));
    }
  }, [creditors, sort]);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const toggleExpand = (supplier) => {
    setExpandedSupplier((curr) => (curr === supplier ? null : supplier));
  };

  const handlePay = (supplier, balance) => {
    if (onSelectSupplier) onSelectSupplier({ supplier, balance, action: 'pay' });
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className={styles.creditors}>
      <header className={styles.header}>
        <div className={styles.titleBlock}>
          <h2 className={styles.title}>Creditors</h2>
          <div className={styles.subtitle}>
            Outstanding balances by supplier — aged
          </div>
        </div>
        <div className={styles.headerActions}>
          <label className={styles.sortLabel}>
            Sort by
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              className={styles.input}
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.id} value={o.id}>{o.label}</option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {/* Aging summary */}
      <div className={styles.bucketRow}>
        <div className={`${styles.bucket} ${styles.bucketTotal}`}>
          <div className={styles.bucketLabel}>Total payable</div>
          <div className={styles.bucketValue}>{fmtMYR(totals.total)}</div>
          <div className={styles.bucketRange}>{creditors.length} suppliers</div>
        </div>
        {BUCKETS.map((b) => {
          const v = totals[b.key];
          const pct = totals.total > 0 ? (v / totals.total) * 100 : 0;
          const isOverdue = b.id === 'b60' || b.id === 'b90';
          return (
            <div
              key={b.id}
              className={`${styles.bucket} ${isOverdue ? styles.bucketOverdue : ''}`}
            >
              <div className={styles.bucketLabel}>{b.label}</div>
              <div className={styles.bucketValue}>{fmtMYR(v)}</div>
              <div className={styles.bucketBar}>
                <div
                  className={styles.bucketBarFill}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className={styles.bucketRange}>{pct.toFixed(1)}%</div>
            </div>
          );
        })}
      </div>

      {/* Supplier list */}
      <div className={styles.tableWrap}>
        {loading && <div className={styles.state}>Loading creditors…</div>}
        {error && <div className={`${styles.state} ${styles.stateError}`}>{error}</div>}
        {!loading && !error && creditors.length === 0 && (
          <div className={styles.state}>No outstanding creditors. 🎉</div>
        )}
        {!loading && !error && creditors.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.colExpand}></th>
                <th className={styles.colSupplier}>Supplier</th>
                <th className={styles.colAging}>0–30 d</th>
                <th className={styles.colAging}>31–60 d</th>
                <th className={styles.colAging}>61–90 d</th>
                <th className={styles.colAging}>90+ d</th>
                <th className={styles.colBalance}>Balance</th>
                <th className={styles.colAction}></th>
              </tr>
            </thead>
            <tbody>
              {sortedCreditors.map((c) => {
                const isExpanded = expandedSupplier === c.supplier;
                const balance = Number(c.balance ?? 0);
                const hasOverdue =
                  Number(c.aged?.d60 ?? 0) > 0 ||
                  Number(c.aged?.d90plus ?? 0) > 0;
                return (
                  <Fragment key={c.supplier}>
                    <tr
                      className={`${styles.row} ${isExpanded ? styles.rowExpanded : ''} ${hasOverdue ? styles.rowOverdue : ''}`}
                      onClick={() => toggleExpand(c.supplier)}
                    >
                      <td className={styles.colExpand}>
                        <span className={`${styles.chevron} ${isExpanded ? styles.chevronOpen : ''}`}>
                          ›
                        </span>
                      </td>
                      <td className={styles.colSupplier}>
                        <div className={styles.supplierName}>{c.supplier}</div>
                        {c.transaction_count !== undefined && (
                          <div className={styles.supplierMeta}>
                            {c.transaction_count} transactions
                          </div>
                        )}
                      </td>
                      <td className={styles.colAging}>{fmtMYR(c.aged?.current)}</td>
                      <td className={styles.colAging}>{fmtMYR(c.aged?.d30)}</td>
                      <td className={`${styles.colAging} ${Number(c.aged?.d60) > 0 ? styles.agingAmber : ''}`}>
                        {fmtMYR(c.aged?.d60)}
                      </td>
                      <td className={`${styles.colAging} ${Number(c.aged?.d90plus) > 0 ? styles.agingRed : ''}`}>
                        {fmtMYR(c.aged?.d90plus)}
                      </td>
                      <td className={styles.colBalance}>
                        <strong>{fmtMYR(balance)}</strong>
                      </td>
                      <td className={styles.colAction}>
                        <button
                          type="button"
                          className={styles.payBtn}
                          onClick={(e) => { e.stopPropagation(); handlePay(c.supplier, balance); }}
                          disabled={balance <= 0}
                        >
                          Pay
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className={styles.detailRow}>
                        <td colSpan={8} className={styles.detailCell}>
                          <SupplierDrawer
                            supplier={c.supplier}
                            entries={supplierEntries[c.supplier]}
                            loading={loadingSupplier === c.supplier}
                            onSelectEntry={onSelectEntry}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: Supplier drawer
// ---------------------------------------------------------------------------

function SupplierDrawer({ supplier, entries, loading, onSelectEntry }) {
  if (loading) {
    return <div className={styles.drawerState}>Loading {supplier} entries…</div>;
  }
  if (!entries || entries.length === 0) {
    return <div className={styles.drawerState}>No entries found for {supplier}.</div>;
  }

  return (
    <div className={styles.drawer}>
      <div className={styles.drawerHeading}>
        Recent activity — {supplier}
      </div>
      <table className={styles.drawerTable}>
        <thead>
          <tr>
            <th>TXN</th>
            <th>Date</th>
            <th>Type</th>
            <th>Reference</th>
            <th className={styles.drawerAmount}>Amount</th>
            <th>Doc</th>
          </tr>
        </thead>
        <tbody>
          {entries.slice(0, 10).map((e) => {
            const amt = Number(e.total ?? 0);
            return (
              <tr
                key={e.short_id}
                onClick={() => onSelectEntry && onSelectEntry(e)}
                className={styles.drawerRow}
              >
                <td><code className={styles.txnId}>{e.short_id}</code></td>
                <td>{fmtDate(e.date)}</td>
                <td>{e.type}</td>
                <td>{e.reference}</td>
                <td className={`${styles.drawerAmount} ${amt < 0 ? styles.amountNeg : ''}`}>
                  {fmtMYR(amt)}
                </td>
                <td>{e.doc_ref ? '🟢' : '🔴'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {entries.length > 10 && (
        <div className={styles.drawerMore}>
          + {entries.length - 10} more — view in Ledger
        </div>
      )}
    </div>
  );
}
