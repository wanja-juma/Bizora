import { useEffect, useState } from "react";

import { api } from "../services/api";
import "./OwnerDashboard.css";

function initialDates() {
  const parts = new Intl.DateTimeFormat("en", {
    timeZone: "Africa/Nairobi",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());

  const getPart = (type) =>
    parts.find((part) => part.type === type).value;

  const year = getPart("year");
  const month = getPart("month");
  const day = getPart("day");

  return {
    start_date: `${year}-${month}-01`,
    end_date: `${year}-${month}-${day}`,
  };
}

function money(minor) {
  return new Intl.NumberFormat("en-KE", {
    style: "currency",
    currency: "KES",
  }).format(minor / 100);
}

function fetchSummary(token, dates, signal) {
  const query = new URLSearchParams(dates);

  return api(`/reports/summary?${query}`, {
    token,
    signal,
  });
}

export default function OwnerDashboard({
  token,
  onSessionExpired,
}) {
  const [dates, setDates] = useState(initialDates);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      try {
        const data = await fetchSummary(
          token,
          initialDates(),
          controller.signal
        );

        setReport(data);
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

    load();

    return () => controller.abort();
  }, [token, onSessionExpired]);

  async function updateReport(event) {
    event.preventDefault();

    if (dates.start_date > dates.end_date) {
      setError("Start date must not be after end date.");
      return;
    }

    setBusy(true);
    setError("");

    try {
      const data = await fetchSummary(token, dates);
      setReport(data);
    } catch (err) {
      setError(err.message);

      if (err.status === 401) {
        onSessionExpired(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  const cards = report
    ? [
        ["Completed sales", report.completed_sales],
        ["Units sold", report.units_sold],
        ["Sales revenue", money(report.revenue_minor)],
        ["Cost of goods sold", money(report.cost_of_goods_minor)],
        ["Gross profit", money(report.gross_profit_minor)],
        ["Operating expenses", money(report.expenses_minor)],
        ["Estimated profit", money(report.estimated_profit_minor)],
      ]
    : [];

  return (
    <section className="owner-dashboard">
      <h2>Business dashboard</h2>

      <form
        className="report-filter"
        onSubmit={updateReport}
      >
        <label>
          Start date
          <input
            type="date"
            required
            disabled={loading || busy}
            value={dates.start_date}
            onChange={(event) =>
              setDates((previous) => ({
                ...previous,
                start_date: event.target.value,
              }))
            }
          />
        </label>

        <label>
          End date
          <input
            type="date"
            required
            disabled={loading || busy}
            value={dates.end_date}
            onChange={(event) =>
              setDates((previous) => ({
                ...previous,
                end_date: event.target.value,
              }))
            }
          />
        </label>

        <button
          type="submit"
          disabled={loading || busy}
        >
          {busy ? "Updating..." : "Update report"}
        </button>
      </form>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {loading && <p role="status">Loading dashboard...</p>}

      {report && (
        <>
          <p>
            Showing {report.start_date} to {report.end_date}
            {" "}(Nairobi time).
          </p>

          <div className="report-cards">
            {cards.map(([label, value]) => (
              <article key={label}>
                <h3>{label}</h3>
                <strong>{value}</strong>
              </article>
            ))}
          </div>

          <p className="description">
            Estimated profit is sales revenue minus saved product
            costs and recorded operating expenses. Cancelled sales
            are excluded.
          </p>

          <h3>
            Current low-stock variants: {report.low_stock_count}
          </h3>

          <p>
            Stock alerts show current quantities, independent of
            the selected report dates.
          </p>

          {report.low_stock_variants.length === 0 ? (
            <p>No low-stock variants found for active products.</p>
          ) : (
            <>
              <p>Showing up to 10, starting with the lowest stock.</p>

              <ul className="dashboard-stock-list">
                {report.low_stock_variants.map((variant) => (
                  <li key={variant.id}>
                    <strong>{variant.product_name}</strong>
                    <p>{variant.sku}</p>
                    <p>
                      Available: {variant.stock} · Warning level:{" "}
                      {variant.low_stock_threshold}
                    </p>
                  </li>
                ))}
              </ul>
            </>
          )}

          <small>
            Updated:{" "}
            {new Date(report.generated_at).toLocaleString()}
            . Click Update report after changing sales,
            expenses, or stock.
          </small>
        </>
      )}
    </section>
  );
}