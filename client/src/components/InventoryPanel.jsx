import { useEffect, useRef, useState } from "react";

import { api } from "../services/api";
import "./InventoryPanel.css";

const emptyVariant = {
  sku: "",
  size: "",
  color: "",
  low_stock_threshold: "5",
};

const emptyMovement = {
  variant_id: "",
  kind: "receipt",
  quantity_change: "",
  reason: "",
};

export default function InventoryPanel({
  product,
  token,
  isOwner,
  onSessionExpired,
}) {
  const [variants, setVariants] = useState([]);
  const [variantForm, setVariantForm] = useState(emptyVariant);
  const [movementForm, setMovementForm] = useState(emptyMovement);
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Preserve the ID if an unchanged submission is retried.
  const pendingRequest = useRef(null);

  const productId = product.id;

  useEffect(() => {
    const controller = new AbortController();

    async function loadVariants() {
      try {
        const data = await api(
          `/products/${productId}/variants`,
          {
            token,
            signal: controller.signal,
          }
        );

        setVariants(data);
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

    loadVariants();

    return () => controller.abort();
  }, [productId, token, onSessionExpired]);

  async function refreshVariants() {
    const data = await api(
      `/products/${productId}/variants`,
      { token }
    );

    setVariants(data);
  }

  async function runAction(action) {
    setBusy(true);
    setError("");
    setNotice("");

    try {
      await action();
    } catch (err) {
      setError(err.message);

      if (err.status === 401) {
        onSessionExpired(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  function changeVariant(event) {
    const { name, value } = event.target;

    setVariantForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  }

  function changeMovement(event) {
    const { name, value } = event.target;

    setMovementForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  }

  function createVariant(event) {
    event.preventDefault();

    runAction(async () => {
      const saved = await api(
        `/products/${productId}/variants`,
        {
          method: "POST",
          token,
          body: {
            ...variantForm,
            low_stock_threshold: Number(
              variantForm.low_stock_threshold
            ),
          },
        }
      );

      setVariants((previous) => [...previous, saved]);
      setVariantForm(emptyVariant);
      setNotice("Variant created. Record a receipt to add stock.");
    });
  }

  function saveMovement(event) {
    event.preventDefault();

    runAction(async () => {
      const payload = {
        kind: movementForm.kind,
        quantity_change: Number(movementForm.quantity_change),
        reason: movementForm.reason,
      };

      const signature = JSON.stringify({
        variant_id: movementForm.variant_id,
        ...payload,
      });

      if (pendingRequest.current?.signature !== signature) {
        pendingRequest.current = {
          signature,
          id: crypto.randomUUID(),
        };
      }

      await api(
        `/variants/${movementForm.variant_id}/movements`,
        {
          method: "POST",
          token,
          body: {
            ...payload,
            request_id: pendingRequest.current.id,
          },
        }
      );

      pendingRequest.current = null;
      setMovementForm(emptyMovement);
      setHistory(null);
      setNotice("Stock change saved successfully.");

      try {
        await refreshVariants();
      } catch (err) {
        if (err.status === 401) throw err;

        setError(
          "The stock change was saved, but the list could not " +
          "refresh. Click Refresh stock."
        );
      }
    });
  }

  function showHistory(variant) {
    runAction(async () => {
      const movements = await api(
        `/variants/${variant.id}/movements`,
        { token }
      );

      setHistory({
        sku: variant.sku,
        movements,
      });
    });
  }

  return (
    <details className="inventory-panel">
      <summary>Variants and inventory</summary>

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

      <button
        type="button"
        disabled={busy}
        onClick={() => runAction(refreshVariants)}
      >
        Refresh stock
      </button>

      {loading ? (
        <p role="status">Loading inventory...</p>
      ) : variants.length === 0 ? (
        <p>No variants have been created yet.</p>
      ) : (
        <ul className="variant-list">
          {variants.map((variant) => (
            <li key={variant.id}>
              <strong>{variant.sku}</strong>

              <p>
                Size: {variant.size || "Standard"} · Colour:{" "}
                {variant.color || "Standard"}
              </p>

              <p>
                Available: <strong>{variant.stock}</strong>
              </p>

              {variant.is_low_stock && (
                <p className="low-stock">
                  {variant.stock === 0
                    ? "Out of stock"
                    : "Low stock"}
                </p>
              )}

              {isOwner && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => showHistory(variant)}
                >
                  View history
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {isOwner && product.is_active && (
        <>
          <h4>Add a variant</h4>

          <form className="auth-form" onSubmit={createVariant}>
            <label>
              SKU
              <input
                name="sku"
                required
                maxLength={60}
                placeholder="SNEAKER-BLK-38"
                value={variantForm.sku}
                onChange={changeVariant}
              />
            </label>

            <label>
              Size (optional)
              <input
                name="size"
                maxLength={30}
                placeholder="38"
                value={variantForm.size}
                onChange={changeVariant}
              />
            </label>

            <label>
              Colour (optional)
              <input
                name="color"
                maxLength={50}
                placeholder="Black"
                value={variantForm.color}
                onChange={changeVariant}
              />
            </label>

            <label>
              Low-stock threshold
              <input
                name="low_stock_threshold"
                type="number"
                min="0"
                max="1000000"
                step="1"
                required
                value={variantForm.low_stock_threshold}
                onChange={changeVariant}
              />
            </label>

            <button type="submit" disabled={busy}>
              Create variant
            </button>
          </form>

          {variants.length > 0 && (
            <>
              <h4>Record a stock change</h4>

              <form
                className="auth-form"
                onSubmit={saveMovement}
              >
                <label>
                  Variant
                  <select
                    name="variant_id"
                    required
                    value={movementForm.variant_id}
                    onChange={changeMovement}
                  >
                    <option value="">Select a variant</option>
                    {variants.map((variant) => (
                      <option
                        key={variant.id}
                        value={variant.id}
                      >
                        {variant.sku} — {variant.stock} available
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  Movement type
                  <select
                    name="kind"
                    value={movementForm.kind}
                    onChange={changeMovement}
                  >
                    <option value="receipt">
                      Stock received
                    </option>
                    <option value="adjustment">
                      Stock correction
                    </option>
                  </select>
                </label>

                <label>
                  Quantity change
                  <input
                    name="quantity_change"
                    type="number"
                    min={
                      movementForm.kind === "receipt"
                        ? "1"
                        : "-1000000"
                    }
                    max="1000000"
                    step="1"
                    required
                    value={movementForm.quantity_change}
                    onChange={changeMovement}
                  />
                </label>

                <small>
                  Enter 10 to add ten units, or -2 to remove
                  two units in a correction. Zero is not allowed.
                </small>

                <label>
                  Reason
                  <input
                    name="reason"
                    required
                    maxLength={255}
                    placeholder="Opening stock, delivery, damage..."
                    value={movementForm.reason}
                    onChange={changeMovement}
                  />
                </label>

                <button type="submit" disabled={busy}>
                  Save stock change
                </button>
              </form>
            </>
          )}
        </>
      )}

      {isOwner && !product.is_active && (
        <p>Reactivate this product to add variants or change stock.</p>
      )}

      {isOwner && history && (
        <section className="stock-history">
          <h4>Latest 50 movements: {history.sku}</h4>

          {history.movements.length === 0 ? (
            <p>No stock movements yet.</p>
          ) : (
            <ol>
              {history.movements.map((movement) => (
                <li key={movement.id}>
                  <strong>
                    {movement.quantity_change > 0 ? "+" : ""}
                    {movement.quantity_change}
                  </strong>
                  {" "}— {movement.kind}
                  <p>{movement.reason}</p>
                  <p>Balance: {movement.balance_after}</p>
                  <small>
                    {movement.recorded_by} ·{" "}
                    {new Date(
                      movement.created_at
                    ).toLocaleString()}
                  </small>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </details>
  );
}