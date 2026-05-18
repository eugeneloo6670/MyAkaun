import { useState, useEffect, useMemo, useCallback } from 'react';
import api, { getSupplierMemory, getEntries, getCreditors, getPeriodStatus, createEntry } from '../../api/client';
import styles from './RecordForm.module.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ENTRY_TYPES = [
  { id: 'purchase', label: 'Purchase' },
  { id: 'credit_note', label: 'Credit Note' },
  { id: 'return', label: 'Return' },
  { id: 'payment', label: 'Payment' },
];

const GL_CODES = [
  { code: '5100', name: 'Cost of Goods Sold' },
  { code: '5200', name: 'Utilities' },
  { code: '5300', name: 'Repairs & Maintenance' },
  { code: '5400', name: 'Office Supplies' },
  { code: '5500', name: 'Transport & Logistics' },
  { code: '5600', name: 'Professional Fees' },
  { code: '5700', name: 'Rental & Lease' },
  { code: '5800', name: 'Other Expenses' },
];

const SST_RATES = [0, 6, 8, 10];

const CURRENCIES = ['INR', 'USD', 'SGD', 'CNY', 'EUR'];

const PAYMENT_METHODS = [
  { id: 'cheque', label: 'Cheque' },
  { id: 'bank_transfer', label: 'Bank transfer' },
  { id: 'cash', label: 'Cash' },
];

const DISCOUNT_GL = '4200';
const AP_GL = '2100';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const today = () => new Date().toISOString().slice(0, 10);

const fmtMYR = (n) => {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return new Intl.NumberFormat('en-MY', {
    style: 'currency',
    currency: 'MYR',
    minimumFractionDigits: 2,
  }).format(n);
};

const periodKey = (dateStr) => (dateStr ? dateStr.slice(0, 7) : '');

const emptyForm = (type) => ({
  type,
  date: today(),
  supplier: '',
  reference: '',
  doc_ref: '',
  gl_code: '',
  amount: '',
  sst_rate: 0,
  fx_enabled: false,
  fx_currency: 'INR',
  fx_original: '',
  fx_rate: '',
  linked_txn: '',
  reason: '',
  amount_paid: '',
  payment_method: 'cheque',
});

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RecordForm({ currentUser = 'eugene', onRecorded, prefill }) {
  const [form, setForm] = useState(() => {
    // If prefill says "pay this supplier", start in payment mode with supplier filled
    if (prefill?.action === 'pay' && prefill.supplier) {
      return { ...emptyForm('payment'), supplier: prefill.supplier };
    }
    return emptyForm('purchase');
  });
  const [suppliers, setSuppliers] = useState([]);
  const [supplierMemory, setSupplierMemory] = useState({}); // supplier -> { last_gl, last_currency }
  const [supplierBalance, setSupplierBalance] = useState(null);
  const [linkableEntries, setLinkableEntries] = useState([]);
  const [periodLocked, setPeriodLocked] = useState(false);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const t = form.type;
  const isReversal = t === 'credit_note' || t === 'return';
  const isPayment = t === 'payment';
  const isPurchase = t === 'purchase';

  // -------------------------------------------------------------------------
  // Data fetching
  // -------------------------------------------------------------------------

  // Load supplier list + memory on mount
  useEffect(() => {
    let cancelled = false;
    getSupplierMemory()
      .then((res) => {
        if (cancelled) return;
        const list = res.data || [];
        setSuppliers(list.map((s) => s.supplier));
        const mem = {};
        list.forEach((s) => {
          // last_gl is stored as "5100|Cost of Goods Sold" — split on pipe
          const [glCode] = (s.last_gl || '').split('|');
          mem[s.supplier] = {
            last_gl: glCode || '',
            last_currency: s.last_ccy || 'MYR',
          };
        });
        setSupplierMemory(mem);
      })
      .catch(() => { /* non-fatal; user can still type */ });
    return () => { cancelled = true; };
  }, []);

  // Period lock check when date changes
  useEffect(() => {
    if (!form.date) return;
    let cancelled = false;
    const p = periodKey(form.date);
    getPeriodStatus(p)
      .then((res) => {
        if (!cancelled) setPeriodLocked(Boolean(res.data?.locked));
      })
      .catch(() => { if (!cancelled) setPeriodLocked(false); });
    return () => { cancelled = true; };
  }, [form.date]);

  // Supplier balance when type=payment + supplier picked
  useEffect(() => {
    if (!isPayment || !form.supplier) {
      setSupplierBalance(null);
      return;
    }
    let cancelled = false;
    // Backend doesn't support ?supplier=X filter on creditors — fetch all, filter client-side
    getCreditors()
      .then((res) => {
        if (cancelled) return;
        const list = Array.isArray(res.data) ? res.data : [];
        const found = list.find((c) => c.supplier === form.supplier);
        setSupplierBalance(found ? Number(found.balance) : 0);
      })
      .catch(() => { if (!cancelled) setSupplierBalance(null); });
    return () => { cancelled = true; };
  }, [isPayment, form.supplier]);

  // Linkable entries when type=credit_note/return + supplier picked
  useEffect(() => {
    if (!isReversal || !form.supplier) {
      setLinkableEntries([]);
      return;
    }
    let cancelled = false;
    getEntries({ supplier: form.supplier, type: 'purchase' })
      .then((res) => {
        if (!cancelled) setLinkableEntries(res.data || []);
      })
      .catch(() => { if (!cancelled) setLinkableEntries([]); });
    return () => { cancelled = true; };
  }, [isReversal, form.supplier]);

  // Auto-fill GL + currency from supplier memory on supplier change
  useEffect(() => {
    if (!form.supplier || !supplierMemory[form.supplier]) return;
    const mem = supplierMemory[form.supplier];
    setForm((f) => ({
      ...f,
      gl_code: f.gl_code || mem.last_gl || '',
      fx_currency: mem.last_currency || f.fx_currency,
    }));
  }, [form.supplier, supplierMemory]);

  // Auto-fill GL + SST + currency from linked transaction
  useEffect(() => {
    if (!isReversal || !form.linked_txn) return;
    const linked = linkableEntries.find((e) => e.short_id === form.linked_txn);
    if (!linked) return;
    setForm((f) => ({
      ...f,
      gl_code: linked.gl_code || f.gl_code,
      sst_rate: linked.sst_rate ?? f.sst_rate,
      fx_enabled: Boolean(linked.orig_ccy && linked.orig_ccy !== 'MYR') || f.fx_enabled,
      fx_currency: (linked.orig_ccy && linked.orig_ccy !== 'MYR') ? linked.orig_ccy : f.fx_currency,
    }));
  }, [form.linked_txn, linkableEntries, isReversal]);

  // -------------------------------------------------------------------------
  // Derived values
  // -------------------------------------------------------------------------

  const fxMyrEquivalent = useMemo(() => {
    if (!form.fx_enabled) return null;
    const o = parseFloat(form.fx_original);
    const r = parseFloat(form.fx_rate);
    if (isNaN(o) || isNaN(r)) return null;
    return o * r;
  }, [form.fx_enabled, form.fx_original, form.fx_rate]);

  const effectiveAmount = useMemo(() => {
    if (form.fx_enabled && fxMyrEquivalent !== null) return fxMyrEquivalent;
    const a = parseFloat(form.amount);
    return isNaN(a) ? null : a;
  }, [form.fx_enabled, fxMyrEquivalent, form.amount]);

  const paymentDiscount = useMemo(() => {
    if (!isPayment || supplierBalance === null) return null;
    const paid = parseFloat(form.amount_paid);
    if (isNaN(paid)) return null;
    const diff = supplierBalance - paid;
    return { discount: diff > 0 ? diff : 0, overpayment: diff < 0 ? -diff : 0 };
  }, [isPayment, supplierBalance, form.amount_paid]);

  // -------------------------------------------------------------------------
  // Validation
  // -------------------------------------------------------------------------

  const validate = useCallback(() => {
    const e = {};
    if (!form.date) e.date = 'Required';
    if (!form.supplier?.trim()) e.supplier = 'Required';
    if (!form.reference?.trim()) e.reference = 'Required';

    if (isPurchase || isReversal) {
      if (!form.gl_code) e.gl_code = 'Required';
      if (!form.fx_enabled && (!form.amount || parseFloat(form.amount) <= 0)) {
        e.amount = 'Must be positive';
      }
      if (form.fx_enabled) {
        if (!form.fx_original || parseFloat(form.fx_original) <= 0) {
          e.fx_original = 'Required';
        }
        if (!form.fx_rate || parseFloat(form.fx_rate) <= 0) {
          e.fx_rate = 'Required';
        }
      }
    }

    if (isReversal && !form.linked_txn) {
      e.linked_txn = 'Must link to original purchase';
    }

    if (isPayment) {
      if (!form.amount_paid || parseFloat(form.amount_paid) <= 0) {
        e.amount_paid = 'Must be positive';
      }
      // Settlement discount requires supporting doc per handoff
      if (paymentDiscount?.discount > 0 && !form.doc_ref?.trim()) {
        e.doc_ref = 'Required when settlement discount applies';
      }
    }

    return e;
  }, [form, isPurchase, isReversal, isPayment, paymentDiscount]);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const update = (patch) => setForm((f) => ({ ...f, ...patch }));

  const switchType = (newType) => {
    // Preserve date + supplier; reset type-specific fields
    setForm((f) => ({
      ...emptyForm(newType),
      date: f.date,
      supplier: f.supplier,
    }));
    setErrors({});
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    const v = validate();
    setErrors(v);
    if (Object.keys(v).length > 0 || periodLocked) return;

    setSubmitting(true);
    try {
      const payload = buildPayload(form, {
        currentUser,
        effectiveAmount,
        fxMyrEquivalent,
        paymentDiscount,
        supplierBalance,
      });
      const res = await createEntry(payload);
      const txn = res.data?.short_id || 'TXN-??????';
      setToast({ kind: 'success', msg: `Recorded ${txn}` });
      setForm((f) => emptyForm(f.type));
      if (onRecorded) onRecorded(res.data);
    } catch (err) {
      setToast({
        kind: 'error',
        msg: err?.response?.data?.detail || 'Failed to record entry',
      });
    } finally {
      setSubmitting(false);
      setTimeout(() => setToast(null), 4000);
    }
  };

  const handleCancel = () => {
    setForm((f) => emptyForm(f.type));
    setErrors({});
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      {/* Type selector */}
      <div className={styles.typeRow} role="tablist" aria-label="Entry type">
        {ENTRY_TYPES.map((et) => (
          <button
            key={et.id}
            type="button"
            role="tab"
            aria-selected={t === et.id}
            className={`${styles.typeBtn} ${t === et.id ? styles.typeBtnActive : ''}`}
            onClick={() => switchType(et.id)}
          >
            {et.label}
          </button>
        ))}
      </div>

      {periodLocked && (
        <div className={styles.lockBanner}>
          🔒 Period {periodKey(form.date)} is locked — entries cannot be recorded.
        </div>
      )}

      {/* Common fields */}
      <div className={styles.grid}>
        <Field label="Date" error={errors.date}>
          <input
            type="date"
            value={form.date}
            onChange={(e) => update({ date: e.target.value })}
            className={styles.input}
            disabled={periodLocked}
          />
        </Field>

        <Field label="Supplier" error={errors.supplier}>
          <input
            type="text"
            list="supplier-list"
            value={form.supplier}
            onChange={(e) => update({ supplier: e.target.value })}
            placeholder="Type or pick a supplier"
            className={styles.input}
            disabled={periodLocked}
          />
          <datalist id="supplier-list">
            {suppliers.map((s) => <option key={s} value={s} />)}
          </datalist>
        </Field>

        <Field
          label={referenceLabel(t)}
          error={errors.reference}
          className={styles.fullRow}
        >
          <input
            type="text"
            value={form.reference}
            onChange={(e) => update({ reference: e.target.value })}
            className={styles.input}
            disabled={periodLocked}
          />
        </Field>

        <Field
          label="Document reference"
          error={errors.doc_ref}
          hint={docRefHint(t, paymentDiscount)}
          className={styles.fullRow}
        >
          <div className={styles.docRefRow}>
            <input
              type="text"
              value={form.doc_ref}
              onChange={(e) => update({ doc_ref: e.target.value })}
              className={styles.input}
              placeholder="Invoice / CN no. on file"
              disabled={periodLocked}
            />
            <span className={form.doc_ref ? styles.flagOk : styles.flagMissing}>
              {form.doc_ref ? '🟢 filed' : '🔴 missing'}
            </span>
          </div>
        </Field>
      </div>

      {/* Type-specific block */}
      <div className={styles.typeBlock}>
        {isReversal && (
          <Field label="Links to TXN" error={errors.linked_txn} className={styles.fullRow}>
            <select
              value={form.linked_txn}
              onChange={(e) => update({ linked_txn: e.target.value })}
              className={styles.input}
              disabled={periodLocked || !form.supplier}
            >
              <option value="">— select original purchase —</option>
              {linkableEntries.map((e) => (
                <option key={e.short_id} value={e.short_id}>
                  {e.short_id} · {e.date} · {fmtMYR(e.total)} · {e.reference}
                </option>
              ))}
            </select>
            {!form.supplier && (
              <div className={styles.hint}>Pick a supplier first to see their purchases.</div>
            )}
          </Field>
        )}

        {(isPurchase || isReversal) && (
          <>
            <div className={styles.grid}>
              <Field label="GL category" error={errors.gl_code}>
                <select
                  value={form.gl_code}
                  onChange={(e) => update({ gl_code: e.target.value })}
                  className={styles.input}
                  disabled={periodLocked}
                >
                  <option value="">— pick GL —</option>
                  {GL_CODES.map((g) => (
                    <option key={g.code} value={g.code}>
                      {g.code} {g.name}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="SST %">
                <select
                  value={form.sst_rate}
                  onChange={(e) => update({ sst_rate: Number(e.target.value) })}
                  className={styles.input}
                  disabled={periodLocked}
                >
                  {SST_RATES.map((r) => <option key={r} value={r}>{r}%</option>)}
                </select>
              </Field>

              {!form.fx_enabled && (
                <Field label="Amount (MYR)" error={errors.amount} className={styles.fullRow}>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.amount}
                    onChange={(e) => update({ amount: e.target.value })}
                    className={styles.input}
                    disabled={periodLocked}
                  />
                </Field>
              )}
            </div>

            <label className={styles.fxToggle}>
              <input
                type="checkbox"
                checked={form.fx_enabled}
                onChange={(e) => update({ fx_enabled: e.target.checked })}
                disabled={periodLocked}
              />
              Foreign currency
            </label>

            {form.fx_enabled && (
              <div className={styles.fxBlock}>
                <Field label="Currency">
                  <select
                    value={form.fx_currency}
                    onChange={(e) => update({ fx_currency: e.target.value })}
                    className={styles.input}
                    disabled={periodLocked}
                  >
                    {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </Field>
                <Field label="Original amount" error={errors.fx_original}>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.fx_original}
                    onChange={(e) => update({ fx_original: e.target.value })}
                    className={styles.input}
                    disabled={periodLocked}
                  />
                </Field>
                <Field label="FX rate" error={errors.fx_rate}>
                  <input
                    type="number"
                    step="0.000001"
                    min="0"
                    value={form.fx_rate}
                    onChange={(e) => update({ fx_rate: e.target.value })}
                    className={styles.input}
                    placeholder="e.g. 0.04182"
                    disabled={periodLocked}
                  />
                </Field>
                <Field label="MYR equivalent">
                  <div className={styles.readonlyBox}>
                    {fmtMYR(fxMyrEquivalent)}
                  </div>
                </Field>
              </div>
            )}
          </>
        )}

        {isPayment && (
          <>
            <Field label="Current balance" className={styles.fullRow}>
              <div className={styles.balanceBox}>
                {form.supplier
                  ? (supplierBalance === null
                      ? 'Loading…'
                      : fmtMYR(supplierBalance))
                  : 'Pick a supplier to see balance.'}
              </div>
            </Field>

            <div className={styles.grid}>
              <Field label="Amount paid (MYR)" error={errors.amount_paid}>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.amount_paid}
                  onChange={(e) => update({ amount_paid: e.target.value })}
                  className={styles.input}
                  disabled={periodLocked}
                />
              </Field>

              <Field label="Payment method">
                <select
                  value={form.payment_method}
                  onChange={(e) => update({ payment_method: e.target.value })}
                  className={styles.input}
                  disabled={periodLocked}
                >
                  {PAYMENT_METHODS.map((p) => (
                    <option key={p.id} value={p.id}>{p.label}</option>
                  ))}
                </select>
              </Field>
            </div>

            {paymentDiscount?.discount > 0 && (
              <div className={styles.discountNotice}>
                Settlement discount: <strong>{fmtMYR(paymentDiscount.discount)}</strong>
                {' '}→ posted to GL {DISCOUNT_GL} Discount Received (income).
              </div>
            )}
            {paymentDiscount?.overpayment > 0 && (
              <div className={styles.overpayNotice}>
                ⚠ Overpayment of <strong>{fmtMYR(paymentDiscount.overpayment)}</strong> — confirm before posting.
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <div className={styles.footer}>
        <div className={styles.recordedBy}>
          Recorded by: <strong>{currentUser}</strong>
        </div>
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.cancelBtn}
            onClick={handleCancel}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            className={styles.recordBtn}
            disabled={submitting || periodLocked}
          >
            {submitting ? 'Recording…' : 'Record entry'}
          </button>
        </div>
      </div>

      <div className={styles.hermesHint}>
        Hermes will review this entry against MPERS rules and supplier history.
      </div>

      {toast && (
        <div className={`${styles.toast} ${styles[`toast_${toast.kind}`]}`}>
          {toast.msg}
        </div>
      )}
    </form>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Field({ label, error, hint, className = '', children }) {
  return (
    <div className={`${styles.field} ${className}`}>
      <label className={styles.label}>{label}</label>
      {children}
      {hint && !error && <div className={styles.hint}>{hint}</div>}
      {error && <div className={styles.error}>{error}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

function referenceLabel(type) {
  switch (type) {
    case 'purchase': return 'Invoice number';
    case 'credit_note': return 'Credit note number';
    case 'return': return 'Return note number';
    case 'payment': return 'Cheque / transaction reference';
    default: return 'Reference';
  }
}

function docRefHint(type, paymentDiscount) {
  if (type === 'payment' && paymentDiscount?.discount > 0) {
    return 'Settlement discount requires supplier written confirmation.';
  }
  return 'Optional but missing-doc count surfaces in metrics.';
}

function buildPayload(form, ctx) {
  const { currentUser, effectiveAmount, fxMyrEquivalent, paymentDiscount, supplierBalance } = ctx;

  // GL name lookup
  const glRecord = GL_CODES.find((g) => g.code === form.gl_code);
  const glName = glRecord ? glRecord.name : '';

  // Map UI types → backend types.
  // Backend supports: purchase | return | payment.
  // "Credit Note" in the UI maps to backend type="return" (functionally identical reversal).
  const backendType = (form.type === 'credit_note') ? 'return' : form.type;

  const base = {
    date: form.date,
    type: backendType,
    supplier: form.supplier.trim(),
    reference: form.reference.trim(),
    doc_ref: form.doc_ref.trim() || null,
    recorded_by: currentUser,
    sst_rate: 0,
    sst_amount: 0,
    amount: 0,
    total: 0,
    orig_ccy: 'MYR',
  };

  if (form.type === 'purchase' || form.type === 'credit_note' || form.type === 'return') {
    base.gl_code = form.gl_code;
    base.gl_name = glName;
    base.sst_rate = Number(form.sst_rate) || 0;

    // Determine the gross MYR figure
    const grossMYR = (form.fx_enabled && fxMyrEquivalent !== null)
      ? fxMyrEquivalent
      : (parseFloat(form.amount) || 0);

    // amount = net (excl SST), sst_amount = derived, total = gross
    // SST is calculated on the net amount: gross = net + (net * rate/100) ⇒ net = gross / (1 + rate/100)
    const rate = base.sst_rate / 100;
    const net = rate > 0 ? grossMYR / (1 + rate) : grossMYR;
    const sst = grossMYR - net;

    base.amount = Number(net.toFixed(2));
    base.sst_amount = Number(sst.toFixed(2));
    base.total = Number(grossMYR.toFixed(2));

    if (form.fx_enabled) {
      base.orig_ccy = form.fx_currency;
      base.orig_amount = parseFloat(form.fx_original);
      base.fx_rate = parseFloat(form.fx_rate);
    }

    // For credit notes / returns: store as negative; link to original
    if (form.type !== 'purchase') {
      base.linked_to = form.linked_txn;
      base.amount = -Math.abs(base.amount);
      base.sst_amount = -Math.abs(base.sst_amount);
      base.total = -Math.abs(base.total);
      if (base.orig_amount) base.orig_amount = -Math.abs(base.orig_amount);
    }
  }

  if (form.type === 'payment') {
    base.gl_code = '2100';
    base.gl_name = 'Accounts Payable';
    base.paid = parseFloat(form.amount_paid);
    base.balance_owed = supplierBalance ?? 0;
    base.total = base.paid;  // total = amount of cash out
    base.amount = base.paid;
    if (paymentDiscount?.discount > 0) {
      base.discount_received = paymentDiscount.discount;
    }
    // Payment method goes into description since backend has no dedicated field
    if (form.payment_method) {
      base.description = `Payment via ${form.payment_method.replace('_', ' ')}`;
    }
  }

  return base;
}
