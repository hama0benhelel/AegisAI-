import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import Analyses from "./Analyses.jsx";
import Workflow from "./Workflow.jsx";
import Audit from "./Audit.jsx";
import Chat from "./Chat.jsx";

async function api(path, { token, body, withMeta = false } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    let message = `Erreur HTTP ${response.status}`;
    if (response.status === 401) message = "Identifiants invalides ou session expirée.";
    else if (response.status === 429) {
      message = `Trop de tentatives. Réessayez dans ${response.headers.get("Retry-After") || 60} secondes.`;
    } else if (typeof data?.detail === "string") {
      message = data.detail;
    }
    const error = new Error(message);
    error.status = response.status;
    error.detail = data?.detail;
    error.traceId = response.headers.get("X-Trace-ID");
    throw error;
  }
  return withMeta ? {
    data,
    status: response.status,
    traceId: response.headers.get("X-Trace-ID"),
  } : data;
}

function App() {
  const [session, setSession] = useState(null);
  const [page, setPage] = useState("readings");
  const [readings, setReadings] = useState([]);
  const [resource, setResource] = useState("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function signIn(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    setBusy(true);
    setError("");

    try {
      const auth = await api("/auth/login", {
        body: {
          email: String(fields.get("email")).trim().toLowerCase(),
          password: String(fields.get("password")),
        },
      });
      form.reset();
      const user = await api("/auth/me", { token: auth.access_token });
      const measures = await api("/readings", { token: auth.access_token });
      setReadings(measures.items);
      setResource("all");
      setPage("readings");
      setSession({ token: auth.access_token, user });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function refreshReadings() {
    setBusy(true);
    setError("");
    try {
      const data = await api("/readings", { token: session.token });
      setReadings(data.items);
    } catch (err) {
      if (err.status === 401) {
        setSession(null);
        setReadings([]);
      }
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function signOut() {
    setSession(null);
    setReadings([]);
    setError("");
  }

  if (!session) {
    return (
      <main className="login-layout">
        <section className="intro">
          <div className="brand"><span className="shield">A</span> AegisAI</div>
          <p className="eyebrow">SECURE AI AGENT PLATFORM FOR IOT</p>
          <h1>Vos données.<br />Vos décisions.<br /><span>Des accès maîtrisés.</span></h1>
          <p className="intro-copy">
            Analysez les consommations et gardez le contrôle des actions
            grâce aux permissions, à la validation humaine et à la traçabilité.
          </p>
          <div className="demo-label">Environnement de démonstration · Données synthétiques</div>
        </section>

        <section className="login-card">
          <p className="eyebrow">ESPACE UTILISATEUR</p>
          <h2>Connexion</h2>
          <p className="muted">Utilisez un compte créé dans votre environnement AegisAI.</p>
          <form onSubmit={signIn}>
            <label>Email
              <input name="email" type="email" required autoComplete="username"
                placeholder="admin.a@example.test" disabled={busy} />
            </label>
            <label>Mot de passe
              <input name="password" type="password" required maxLength={128}
                autoComplete="current-password" disabled={busy} />
            </label>
            {error && <p className="error" role="alert">{error}</p>}
            <button disabled={busy}>{busy ? "Connexion…" : "Se connecter →"}</button>
          </form>
        </section>
      </main>
    );
  }

  const sensors = new Set(readings.map(row => row.sensor_id)).size;
  const visible = readings.filter(
    row => resource === "all" || row.resource === resource
  );
  const latest = readings.length
    ? readings.reduce((a, b) => new Date(a.measured_at) > new Date(b.measured_at) ? a : b)
    : null;
  const date = value => new Date(value).toLocaleString("fr-FR");

  return (
    <div className="workspace">
      <aside className="sidebar">
        <div className="brand"><span className="shield">A</span> AegisAI</div>
        <p className="eyebrow">SUPERVISION IOT</p>
        <nav className="app-nav" aria-label="Navigation principale">
          <button className={page === "readings" ? "nav-active" : "secondary"}
            disabled={busy} onClick={() => setPage("readings")}>
            Vue des mesures
          </button>
          <button className={page === "analyses" ? "nav-active" : "secondary"}
            disabled={busy} onClick={() => setPage("analyses")}>
            Analyses
          </button>
          <button className={page === "workflow" ? "nav-active" : "secondary"}
            disabled={busy} onClick={() => setPage("workflow")}>
            Propositions et tâches
          </button>
          {session.user.role === "tenant_admin" && (
            <button className={page === "audit" ? "nav-active" : "secondary"}
              disabled={busy} onClick={() => setPage("audit")}>
              Journal d’audit
            </button>
          )}
          <button className={page === "chat" ? "nav-active" : "secondary"}
            disabled={busy} onClick={() => setPage("chat")}>
            Assistant
          </button>
        </nav>
        <div className="sidebar-bottom">
          <span className="badge">{session.user.role}</span>
          <p>{session.user.email}</p>
          <button className="secondary" onClick={signOut} disabled={busy}>Déconnexion</button>
        </div>
      </aside>

      <main className="content">
        <header>
          <div>
            <p className="eyebrow">ESPACE DE VOTRE ORGANISATION</p>
            <h1>{page === "readings" ? "Vue des mesures"
              : page === "analyses" ? "Analyses"
              : page === "workflow" ? "Propositions et tâches"
              : page === "audit" ? "Journal d’audit" : "Assistant"}</h1>
            <p className="muted">Consommations et historique accessibles à votre compte.</p>
          </div>
          <button className="secondary" disabled={busy}
            style={{ display: page === "readings" ? undefined : "none" }}
            onClick={refreshReadings}>
            {busy ? "Chargement…" : "Actualiser"}
          </button>
        </header>

        <div className="notice">
          Données synthétiques de démonstration — les dates correspondent aux mesures enregistrées.
        </div>
        {error && <p className="error" role="alert">{error}</p>}

        {page === "chat" ? (
          <Chat
            key={session.user.id}
            api={api}
            session={session}
            readings={readings}
            busy={busy}
            setBusy={setBusy}
            onExpired={() => {
              signOut();
              setError("Session expirée. Reconnectez-vous.");
            }}
          />
        ) : page === "audit" ? (
          <Audit
            key={session.user.id}
            api={api}
            session={session}
            busy={busy}
            setBusy={setBusy}
            onExpired={() => {
              signOut();
              setError("Session expirée. Reconnectez-vous.");
            }}
          />
        ) : page === "workflow" ? (
          <Workflow
            key={session.user.id}
            api={api}
            session={session}
            busy={busy}
            setBusy={setBusy}
            onExpired={() => {
              signOut();
              setError("Session expirée. Reconnectez-vous.");
            }}
          />
        ) : page === "analyses" ? (
          <Analyses
            key={session.user.id}
            api={api}
            session={session}
            readings={readings}
            busy={busy}
            setBusy={setBusy}
            onExpired={() => {
              signOut();
              setError("Session expirée. Reconnectez-vous.");
            }}
          />
        ) : (
          <>
        <section className="stats">
          <article><span>Capteurs dans les résultats</span><strong>{sensors}</strong></article>
          <article><span>Mesures chargées</span><strong>{readings.length}</strong></article>
          <article><span>Dernière mesure disponible</span>
            <strong className="date-value">{latest ? date(latest.measured_at) : "Aucune"}</strong>
          </article>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div><h2>Historique des consommations</h2>
              <p className="muted">Jusqu’à 100 mesures récentes retournées par l’API.</p>
            </div>
            <label className="filter">Ressource
              <select value={resource} onChange={e => setResource(e.target.value)}>
                <option value="all">Toutes</option>
                <option value="water">Eau</option>
                <option value="energy">Énergie</option>
              </select>
            </label>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Capteur</th><th>Ressource</th><th>Valeur</th><th>Date</th></tr></thead>
              <tbody>
                {visible.map(row => (
                  <tr key={row.id}>
                    <td>{row.sensor_id}</td>
                    <td><span className={`resource ${row.resource}`}>
                      {row.resource === "water" ? "Eau" : "Énergie"}
                    </span></td>
                    <td>{Number(row.value).toLocaleString("fr-FR")} {row.unit}</td>
                    <td>{date(row.measured_at)}</td>
                  </tr>
                ))}
                {!visible.length && <tr><td colSpan={4}>Aucune mesure disponible.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
          </>
        )}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
