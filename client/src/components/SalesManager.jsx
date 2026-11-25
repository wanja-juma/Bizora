import { useEffect, useRef, useState } from "react";

import { api } from "../services/api";
import "./SalesManager.css";

function money(minor) {
  return new Intl.NumberFormat("en-KE", {
    style: "currency",
    currency: "KES",
  }).format(minor / 100);
}

export default function SalesManager({ token, user, onSessionExpired }) {
  const [variants, setVariants] = useState([]);
  const [sales, setSales] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [payment, setPayment] = useState("cash");
  const [cart, setCart] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const pendingRequest = useRef(null);

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      try {
        const [variantData, saleData] = await Promise.all([
          api("/sales/variants", {
            token,
            signal: controller.signal,
          }),
          api("/sales", {
            token,
            signal: controller.signal,
          }),
        ]);

        setVariants(variantData);
        setSales(saleData);
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

  async function refreshData() {
    const [variantData, saleData] = await Promise.all([
      api("/sales/variants", { token }),
      api("/sales", { token }),
    ]);

    setVariants(variantData);
    setSales(saleData);
  }

  async function refresh() {
    setBusy(true);
    setError("");

    try {
      await refreshData();
    } catch (err) {
      setError(err.message);

      if (err.status === 401) {
        onSessionExpired(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  function addToSale(event) {
    event.preventDefault();
    setError("");
    setNotice("");

    const variant = variants.find((item) => item.id === Number(selectedId));
    const amount = Number(quantity);

    if (!variant || !Number.isInteger(amount) || amount < 1) {
      setError("Select a variant and enter a whole quantity.");
      return;
    }

    const existing = cart.find((item) => item.variant_id === variant.id);
    const nextQuantity = (existing?.quantity || 0) + amount;

    if (nextQuantity > variant.stock) {
      setError(`Only ${variant.stock} units are available.`);
      return;
    }

    const line = {
      variant_id: variant.id,
      sku: variant.sku,
      product_name: variant.product_name,
      price_minor: variant.price_minor,
      quantity: nextQuantity,
    };

    setCart((previous) =>
      existing
        ? previous.map((item) => (item.variant_id === variant.id ? line : item))
        : [...previous, line],
    );

    setSelectedId("");
    setQuantity("1");
  }

  async function recordSale() {
    if (cart.length === 0) return;

    setBusy(true);
    setError("");
    setNotice("");

    const body = {
      payment_method: payment,
      items: cart
        .map((item) => ({
          variant_id: item.variant_id,
          quantity: item.quantity,
        }))
        .sort((a, b) => a.variant_id - b.variant_id),
    };

    const signature = JSON.stringify(body);

    if (pendingRequest.current?.signature !== signature) {
      pendingRequest.current = {
        signature,
        id: crypto.randomUUID(),
      };
    }

    try {
      const saved = await api("/sales", {
        method: "POST",
        token,
        body: {
          ...body,
          request_id: pendingRequest.current.id,
        },
      });

      pendingRequest.current = null;
      setCart([]);
      setNotice(
        `Sale #${saved.id} recorded. Total: ${money(saved.total_minor)}`,
      );

      setSales((previous) =>
        [saved, ...previous.filter((sale) => sale.id !== saved.id)].slice(
          0,
          50,
        ),
      );

      try {
        await refreshData();
      } catch (err) {
        if (err.status === 401) throw err;

        setError(
          "The sale was saved, but the lists could not refresh. " +
            "Click Refresh.",
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

  const estimatedTotal = cart.reduce(
    (total, item) => total + item.quantity * item.price_minor,
    0,
  );

  if (loading) {
    return <p role="status">Loading sales...</p>;
  }

  async function cancelSale(event, saleId) {
    event.preventDefault();

    const form = event.currentTarget;
    const reason = String(new FormData(form).get("reason") || "").trim();

    if (!reason) {
      setError("Enter a cancellation reason.");
      return;
    }

    setBusy(true);
    setError("");
    setNotice("");

    try {
      const saved = await api(`/sales/${saleId}/cancel`, {
        method: "POST",
        token,
        body: { reason },
      });

      setSales((previous) =>
        previous.map((sale) => (sale.id === saved.id ? saved : sale)),
      );

      setNotice(`Sale #${saved.id} is cancelled. Its stock has been restored.`);

      try {
        await refreshData();
      } catch (err) {
        if (err.status === 401) throw err;

        setError(
          "Cancellation succeeded, but the lists could not " +
            "refresh. Click Refresh.",
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

  return (
    <section className="sales-section">
      <h2>Record a sale</h2>

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

      <button type="button" disabled={busy} onClick={refresh}>
        Refresh
      </button>

      <fieldset className="sales-fields" disabled={busy}>
        <legend>Sale details</legend>

        <form className="auth-form" onSubmit={addToSale}>
          <label htmlFor="sale-variant">Product variant</label>
          <select
            id="sale-variant"
            required
            value={selectedId}
            onChange={(event) => setSelectedId(event.target.value)}
          >
            <option value="">Select a variant</option>

            {variants.map((variant) => (
              <option
                key={variant.id}
                value={variant.id}
                disabled={variant.stock === 0}
              >
                {variant.product_name} — {variant.sku} — {variant.stock}{" "}
                available — {money(variant.price_minor)}
              </option>
            ))}
          </select>

          <label htmlFor="sale-quantity">Quantity</label>
          <input
            id="sale-quantity"
            type="number"
            required
            min="1"
            max="1000000"
            step="1"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
          />

          <button type="submit">Add to sale</button>
        </form>

        {cart.length === 0 ? (
          <p>No items added yet.</p>
        ) : (
          <ul className="sale-cart">
            {cart.map((item) => (
              <li key={item.variant_id}>
                <strong>{item.product_name}</strong>
                <p>{item.sku}</p>
                <p>
                  {item.quantity} × {money(item.price_minor)} ={" "}
                  {money(item.quantity * item.price_minor)}
                </p>

                <button
                  type="button"
                  onClick={() =>
                    setCart((previous) =>
                      previous.filter(
                        (line) => line.variant_id !== item.variant_id,
                      ),
                    )
                  }
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}

        <p>
          <strong>Estimated total: {money(estimatedTotal)}</strong>
        </p>
        <small>The server confirms current prices and stock when saving.</small>

        <label className="payment-label" htmlFor="sale-payment">
          Payment method
        </label>
        <select
          id="sale-payment"
          value={payment}
          onChange={(event) => setPayment(event.target.value)}
        >
          <option value="cash">Cash</option>
          <option value="mpesa">M-Pesa</option>
          <option value="card">Card</option>
        </select>

        <button
          className="record-sale-button"
          type="button"
          disabled={cart.length === 0}
          onClick={recordSale}
        >
          {busy ? "Saving..." : "Record completed sale"}
        </button>
      </fieldset>

      <h3>
        {user.role === "owner" ? "Latest 50 sales" : "Your latest 50 sales"}
      </h3>

      {sales.length === 0 ? (
        <p>No sales recorded yet.</p>
      ) : (
        <div className="sales-history">
          {sales.map((sale) => (
            <article key={sale.id}>
              <h4>Sale #{sale.id}</h4>
              <p>
                Role: {user?.role || "missing"} | Status:{" "}
                {sale.status || "missing"}
              </p>
              <p>
                <strong>
                  Status:{" "}
                  {sale.status === "cancelled" ? "Cancelled" : "Completed"}
                </strong>
              </p>
              <p>
                {money(sale.total_minor)} · {sale.payment_method.toUpperCase()}
              </p>

              <ul>
                {sale.items.map((item) => (
                  <li key={item.variant_id}>
                    {item.sku} × {item.quantity} — {money(item.subtotal_minor)}
                  </li>
                ))}
              </ul>

              <small>
                {sale.recorded_by} ·{" "}
                {new Date(sale.created_at).toLocaleString()}
              </small>
              {sale.status === "cancelled" && (
                <div className="cancellation-details">
                  <p>Reason: {sale.cancellation_reason}</p>
                  <small>
                    Cancelled by {sale.cancelled_by} ·{" "}
                    {sale.cancelled_at
                      ? new Date(sale.cancelled_at).toLocaleString()
                      : ""}
                  </small>
                </div>
              )}

              {user.role === "owner" && sale.status === "completed" && (
                <form
                  className="auth-form cancel-sale-form"
                  onSubmit={(event) => cancelSale(event, sale.id)}
                >
                  <label htmlFor={`cancel-reason-${sale.id}`}>
                    Cancellation reason
                  </label>

                  <input
                    id={`cancel-reason-${sale.id}`}
                    name="reason"
                    required
                    maxLength={255}
                    disabled={busy}
                    placeholder="For example: duplicate sale entry"
                  />

                  <small>
                    Cancelling restores every item in this sale to stock. Handle
                    any payment refund separately.
                  </small>

                  <button type="submit" disabled={busy}>
                    Cancel sale and restore stock
                  </button>
                </form>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
