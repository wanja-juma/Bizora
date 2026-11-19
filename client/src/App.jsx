import { useCallback, useEffect, useState } from "react";

import CatalogManager from "./components/CatalogManager";
import { api } from "./services/api";
import "./App.css";

const emptyStaff = {
  name: "",
  email: "",
  password: "",
};

function App() {
  const [token, setToken] = useState(
    () => sessionStorage.getItem("bizora_token") || "",
  );
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const [loginForm, setLoginForm] = useState({
    email: "",
    password: "",
  });
  const [staffForm, setStaffForm] = useState(emptyStaff);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadSession() {
      try {
        if (!token) {
          setUser(null);
          return;
        }

        const profile = await api("/auth/me", {
          token,
          signal: controller.signal,
        });

        setUser(profile);
      } catch (err) {
        if (err.name === "AbortError") return;

        setUser(null);
        setError(err.message);

        if (err.status === 401) {
          sessionStorage.removeItem("bizora_token");
          setToken("");
        }
      } finally {
        if (!controller.signal.aborted) {
          setChecking(false);
        }
      }
    }

    loadSession();

    return () => controller.abort();
  }, [token]);

  function clearSession(message = "") {
    sessionStorage.removeItem("bizora_token");
    setToken("");
    setUser(null);
    setStaffForm(emptyStaff);
    setNotice(message);
  }

  async function handleLogin(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");

    try {
      const data = await api("/auth/login", {
        method: "POST",
        body: loginForm,
      });

      sessionStorage.setItem("bizora_token", data.access_token);

      setChecking(true);
      setToken(data.access_token);
      setLoginForm({ email: "", password: "" });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleLogout() {
    setBusy(true);
    setError("");
    setNotice("");

    try {
      await api("/auth/logout", {
        method: "POST",
        token,
      });

      clearSession("You have logged out successfully.");
    } catch (err) {
      if (err.status === 401) {
        clearSession();
      }

      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateStaff(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");

    try {
      const data = await api("/auth/staff", {
        method: "POST",
        token,
        body: staffForm,
      });

      setStaffForm(emptyStaff);
      setNotice(data.message);
    } catch (err) {
      if (err.status === 401) {
        clearSession();
      }

      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const handleSessionExpired = useCallback((message) => {
    sessionStorage.removeItem("bizora_token");
    setToken("");
    setUser(null);
    setStaffForm(emptyStaff);
    setNotice("");
    setError(message);
  }, []);

  return (
    <main className="setup-page">
      <section className="setup-card">
        <p className="eyebrow">BIZORA</p>

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

        {checking ? (
          <p role="status">Checking your session...</p>
        ) : !user ? (
          <>
            <h1>Welcome back</h1>
            <p className="description">Log in to manage your business.</p>

            <form className="auth-form" onSubmit={handleLogin}>
              <label htmlFor="login-email">Email</label>
              <input
                id="login-email"
                type="email"
                autoComplete="username"
                required
                maxLength={254}
                value={loginForm.email}
                onChange={(event) =>
                  setLoginForm({
                    ...loginForm,
                    email: event.target.value,
                  })
                }
              />

              <label htmlFor="login-password">Password</label>
              <input
                id="login-password"
                type="password"
                autoComplete="current-password"
                required
                maxLength={128}
                value={loginForm.password}
                onChange={(event) =>
                  setLoginForm({
                    ...loginForm,
                    password: event.target.value,
                  })
                }
              />

              <button type="submit" disabled={busy}>
                {busy ? "Logging in..." : "Log in"}
              </button>
            </form>
          </>
        ) : (
          <>
            <h1>Hello, {user.name}</h1>

            <p className="description">
              Signed in as <strong>{user.role}</strong>
              <br />
              {user.email}
            </p>

            <button
              type="button"
              className="logout-button"
              onClick={handleLogout}
              disabled={busy}
            >
              Log out
            </button>

            {user.role === "owner" ? (
              <section className="staff-section">
                <h2>Create a staff account</h2>

                <form className="auth-form" onSubmit={handleCreateStaff}>
                  <label htmlFor="staff-name">Full name</label>
                  <input
                    id="staff-name"
                    autoComplete="off"
                    required
                    maxLength={100}
                    value={staffForm.name}
                    onChange={(event) =>
                      setStaffForm({
                        ...staffForm,
                        name: event.target.value,
                      })
                    }
                  />

                  <label htmlFor="staff-email">Email</label>
                  <input
                    id="staff-email"
                    type="email"
                    autoComplete="off"
                    required
                    maxLength={254}
                    value={staffForm.email}
                    onChange={(event) =>
                      setStaffForm({
                        ...staffForm,
                        email: event.target.value,
                      })
                    }
                  />

                  <label htmlFor="staff-password">Password</label>
                  <input
                    id="staff-password"
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={12}
                    maxLength={128}
                    value={staffForm.password}
                    onChange={(event) =>
                      setStaffForm({
                        ...staffForm,
                        password: event.target.value,
                      })
                    }
                  />

                  <small>Use at least 12 characters.</small>

                  <button type="submit" disabled={busy}>
                    {busy ? "Please wait..." : "Create staff"}
                  </button>
                </form>
              </section>
            ) : (
              <p className="description">
                Your staff workspace is ready. Sales and inventory features will
                appear here as we build them.
              </p>
            )}
          </>
        )}
        {!checking && user && token && (
  <CatalogManager
    token={token}
    user={user}
    onSessionExpired={handleSessionExpired}
  />
)}
      </section>
    </main>
  );
}

export default App;
