import { useEffect, useState } from "react";
import "./App.css";

function App() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function checkConnection() {
      try {
        const response = await fetch("/api/health", {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(
            `Connection check failed (${response.status}).`
          );
        }

        const data = await response.json();

        setHealth(data);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(
            `${err.message} Make sure the Flask server is running.`
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    checkConnection();

    return () => controller.abort();
  }, []);

  return (
    <main className="setup-page">
      <section className="setup-card">
        <p className="eyebrow">BUSINESS MANAGEMENT</p>

        <h1>Welcome to Bizora</h1>

        <p className="description">
          Manage your products, stock, sales, and expenses
          in one place.
        </p>

        <div className="connection-status" aria-live="polite">
          {loading && <p>Checking the connection...</p>}

          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}

          {!loading && !error && health && (
            <>
              <p className="success">{health.message}</p>
              <p>Database: {health.database}</p>
            </>
          )}
        </div>
      </section>
    </main>
  );
}

export default App;
