import { useEffect, useState } from "react";

import { api } from "../services/api";
import "./ExpenseManager.css";

const categories = [
  ["rent", "Rent"],
  ["utilities", "Utilities"],
  ["transport", "Transport"],
  ["packaging", "Packaging"],
  ["salaries", "Salaries"],
  ["maintenance", "Maintenance"],
  ["other", "Other"],
];

function emptyForm() {
  return {
    description: "",
    category: "",
    amount: "",
    date_paid: "",
    notes: "",
  };
}

function formatMoney(minor) {
  return new Intl.NumberFormat("en-KE", {
    style: "currency",
    currency: "KES",
  }).format(minor / 100);
}

export default function ExpenseManager({
  token,
  onSessionExpired,
}) {
  const [expenses, setExpenses] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadExpenses() {
      try {
        const data = await api("/expenses", {
          token,
          signal: controller.signal,
        });

        setExpenses(data);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err.message);

          if (err.status === 401) {
            onSessionExpired(err.message);
          }
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadExpenses();

    return () => controller.abort();
  }, [token, onSessionExpired]);

  function changeField(event) {
    const { name, value } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  }

  function resetForm() {
    setEditingId(null);
    setForm(emptyForm());
  }

  function editExpense(expense) {
    setEditingId(expense.id);
    setForm({
      description: expense.description,
      category: expense.category,
      amount: (expense.amount_minor / 100).toFixed(2),
      date_paid: expense.date_paid,
      notes: expense.notes,
    });
    setError("");
    setNotice("");
  }

  async function refreshExpenses() {
    setBusy(true);
    setError("");
    setNotice("");

    try {
      const data = await api("/expenses", { token });
      setExpenses(data);
    } catch (err) {
      setError(err.message);

      if (err.status === 401) {
        onSessionExpired(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  async function saveExpense(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");

    const wasEditing = editingId !== null;

    try {
      const saved = await api(
        wasEditing ? `/expenses/${editingId}` : "/expenses",
        {
          method: wasEditing ? "PUT" : "POST",
          token,
          body: {
            ...form,
            description: form.description.trim(),
            notes: form.notes.trim(),
          },
        }
      );

      setExpenses((previous) =>
        [
          saved,
          ...previous.filter(
            (expense) => expense.id !== saved.id
          ),
        ]
          .sort(
            (a, b) =>
              b.date_paid.localeCompare(a.date_paid) ||
              b.id - a.id
          )
          .slice(0, 100)
      );

      resetForm();

      setNotice(
        wasEditing
          ? "Expense updated successfully."
          : "Expense recorded successfully."
      );

      // Reload to match the backend's latest 100 records.
      try {
        const data = await api("/expenses", { token });
        setExpenses(data);
      } catch (err) {
        if (err.status === 401) throw err;

        setError(
          "The expense was saved, but history could not " +
          "refresh. Click Refresh expenses."
        );
      }
    } catch (err) {
      setError(err.message);

      if (err.status === 401) {
        onSessionExpired(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <p role="status">Loading expenses...</p>;
  }

  return (
    <section className="expenses-section">
      <h2>Business expenses</h2>

      <p className="description">
        Record operating costs such as rent, electricity,
        transport, and packaging.
      </p>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {notice && (
        <p className="success" role="status">
          {notice}
        </p>
      )}

      <h3>
        {editingId !== null ? "Edit expense" : "Add expense"}
      </h3>

      <form className="auth-form" onSubmit={saveExpense}>
        <fieldset disabled={busy}>
          <label htmlFor="expense-description">
            Description
          </label>
          <input
            id="expense-description"
            name="description"
            required
            maxLength={150}
            placeholder="For example: November shop rent"
            value={form.description}
            onChange={changeField}
          />

          <label htmlFor="expense-category">Category</label>
          <select
            id="expense-category"
            name="category"
            required
            value={form.category}
            onChange={changeField}
          >
            <option value="">Select a category</option>

            {categories.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <label htmlFor="expense-amount">Amount (KSh)</label>
          <input
            id="expense-amount"
            name="amount"
            type="number"
            required
            min="0.01"
            max="100000000"
            step="0.01"
            placeholder="10000.00"
            value={form.amount}
            onChange={changeField}
          />

          <label htmlFor="expense-date">Date paid</label>
          <input
            id="expense-date"
            name="date_paid"
            type="date"
            required
            value={form.date_paid}
            onChange={changeField}
          />

          <label htmlFor="expense-notes">
            Notes (optional)
          </label>
          <textarea
            id="expense-notes"
            name="notes"
            rows={3}
            maxLength={2000}
            placeholder="Additional payment details"
            value={form.notes}
            onChange={changeField}
          />

          <div className="expense-actions">
            <button type="submit">
              {busy
                ? "Saving..."
                : editingId !== null
                  ? "Save changes"
                  : "Record expense"}
            </button>

            {editingId !== null && (
              <button type="button" onClick={resetForm}>
                Cancel editing
              </button>
            )}
          </div>
        </fieldset>
      </form>

      <div className="expense-history-heading">
        <h3>Latest 100 expenses by date paid</h3>

        <button
          type="button"
          disabled={busy}
          onClick={refreshExpenses}
        >
          Refresh expenses
        </button>
      </div>

      {expenses.length === 0 ? (
        <p>No expenses to display.</p>
      ) : (
        <div className="expense-history">
          {expenses.map((expense) => (
            <article key={expense.id}>
              <h4>{expense.description}</h4>

              <p className="expense-amount">
                {formatMoney(expense.amount_minor)}
              </p>

              <p>
                Category:{" "}
                {categories.find(
                  ([value]) => value === expense.category
                )?.[1] || expense.category}
              </p>

              <p>Date paid: {expense.date_paid}</p>

              {expense.notes && <p>{expense.notes}</p>}

              <small>
                Recorded by {expense.recorded_by} ·{" "}
                {new Date(
                  expense.created_at
                ).toLocaleString()}
              </small>

              <button
                type="button"
                disabled={busy}
                onClick={() => editExpense(expense)}
              >
                Edit expense
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}