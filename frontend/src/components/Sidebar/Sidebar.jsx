import { useEffect, useState } from 'react';
import { countEntries, countCreditors, countMissingDocs, getCurrentPeriod } from '../../api/client';
import styles from './Sidebar.module.css';

// ---------------------------------------------------------------------------
// Nav structure — view ids match Shell.jsx view router
// ---------------------------------------------------------------------------

const NAV_SECTIONS = [
  {
    heading: 'Entry',
    items: [
      { id: 'record', label: 'Record', icon: '✚' },
    ],
  },
  {
    heading: 'Ledger',
    items: [
      { id: 'ledger',    label: 'Entries',   icon: '☰', countKey: 'entries' },
      { id: 'creditors', label: 'Creditors', icon: '⌗', countKey: 'creditors' },
      { id: 'kanban',    label: 'Kanban',    icon: '▦' },
    ],
  },
  {
    heading: 'Period',
    items: [
      { id: 'month_end', label: 'Month-End', icon: '∑' },
      { id: 'periods',   label: 'Periods',   icon: '🔒' },
    ],
  },
  {
    heading: 'Audit',
    items: [
      {
        id: 'audit_log',
        label: 'Audit Log',
        icon: '◷',
        countKey: 'missing_docs',
        badgeKind: 'red',
      },
    ],
  },
];

const POLL_MS = 60_000;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Sidebar({
  activeView,
  onNavigate,
  currentUser = 'eugene',
  refreshTrigger,
}) {
  const [counts, setCounts] = useState({});
  const [currentPeriod, setCurrentPeriod] = useState(null);

  // Load counts on mount, when refresh trigger changes, and on poll interval.
  // Uses dedicated /count endpoints so the sidebar never pulls full lists just
  // to render badge numbers (previously fetched all entries + all creditors
  // every 60s and counted client-side).
  useEffect(() => {
    let cancelled = false;
    let timer;

    async function load() {
      try {
        const [entriesRes, creditorsRes, missingRes, periodRes] = await Promise.allSettled([
          countEntries(),
          countCreditors(),
          countMissingDocs(),
          getCurrentPeriod(),
        ]);
        if (cancelled) return;

        setCounts({
          entries:      entriesRes.status   === 'fulfilled' ? (entriesRes.value.data?.count   ?? 0) : 0,
          creditors:    creditorsRes.status === 'fulfilled' ? (creditorsRes.value.data?.count ?? 0) : 0,
          missing_docs: missingRes.status   === 'fulfilled' ? (missingRes.value.data?.count   ?? 0) : 0,
        });
        if (periodRes.status === 'fulfilled') {
          setCurrentPeriod(periodRes.value.data || null);
        }
      } catch {
        /* non-fatal */
      }
    }

    load();
    timer = setInterval(load, POLL_MS);
    return () => { cancelled = true; clearInterval(timer); };
  }, [refreshTrigger]);

  const handleClick = (id) => {
    if (onNavigate) onNavigate(id);
  };

  return (
    <nav className={styles.sidebar} aria-label="Primary">
      <div className={styles.brand}>
        <div className={styles.brandMark}>μ</div>
        <div className={styles.brandText}>
          <div className={styles.brandName}>AccountMaxxer</div>
          <div className={styles.brandTag}>AI Accounting</div>
        </div>
      </div>

      <div className={styles.sections}>
        {NAV_SECTIONS.map((section) => (
          <div key={section.heading} className={styles.section}>
            <div className={styles.heading}>{section.heading}</div>
            <ul className={styles.list}>
              {section.items.map((item) => {
                const count = item.countKey ? counts[item.countKey] : null;
                const showBadge = count !== null && count !== undefined && count > 0;
                const isActive = activeView === item.id;
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      className={`${styles.item} ${isActive ? styles.itemActive : ''}`}
                      onClick={() => handleClick(item.id)}
                      aria-current={isActive ? 'page' : undefined}
                    >
                      <span className={styles.icon} aria-hidden>{item.icon}</span>
                      <span className={styles.label}>{item.label}</span>
                      {showBadge && (
                        <span
                          className={`${styles.badge} ${
                            item.badgeKind === 'red' ? styles.badgeRed : styles.badgeNeutral
                          }`}
                        >
                          {count}
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      <div className={styles.footer}>
        {currentPeriod && (
          <div className={styles.periodChip}>
            <span className={styles.periodLabel}>Period</span>
            <span className={styles.periodValue}>
              {currentPeriod.month || '—'}
            </span>
            <span
              className={`${styles.periodStatus} ${
                currentPeriod.locked ? styles.periodLocked : styles.periodOpen
              }`}
            >
              {currentPeriod.locked ? 'Locked' : 'Open'}
            </span>
          </div>
        )}
        <div className={styles.user}>
          <div className={styles.userAvatar}>{currentUser.charAt(0).toUpperCase()}</div>
          <div className={styles.userMeta}>
            <div className={styles.userName}>{currentUser}</div>
            <div className={styles.userRole}>Recorder</div>
          </div>
        </div>
      </div>
    </nav>
  );
}
