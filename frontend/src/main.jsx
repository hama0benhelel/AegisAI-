import React, { useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import Overview, { Meters } from "./Overview.jsx";
import Chat from "./Chat.jsx";
import Actions from "./Actions.jsx";
import BWSSecurity from "./BWSSecurity.jsx";
import { Icon, Message } from "./ui.jsx";

async function api(path, { token, body, withMeta = false } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch(`/api${path}`, { method: body === undefined ? "GET" : "POST", headers, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store" });
  } catch {
    throw new Error("Connexion au serveur interrompue. Vérifiez votre connexion avant de réessayer ; une opération peut déjà avoir été traitée.");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    let message = typeof data?.detail === "string" ? data.detail : `La demande n’a pas abouti (HTTP ${response.status}).`;
    if (response.status === 401) message = "Identifiants invalides ou session expirée. Reconnectez-vous.";
    if (response.status === 429) message = `Trop de demandes. Réessayez dans ${response.headers.get("Retry-After") || 60} secondes.`;
    if (response.status === 422) message = "Certains champs ne sont pas valides. Vérifiez votre demande.";
    const error = new Error(message);
    error.status = response.status; error.detail = data?.detail; error.traceId = response.headers.get("X-Trace-ID");
    throw error;
  }
  return withMeta ? { data, status: response.status, traceId: response.headers.get("X-Trace-ID") } : data;
}

const clientPages = [
  ["overview", "grid", "Vue d’ensemble", "Vos consommations à portée de main."],
  ["meters", "drop", "Mes compteurs", "Retrouvez les mesures enregistrées de vos équipements."],
  ["assistant", "chat", "Mon assistant", "Un espace pour poser vos questions et comprendre vos données."],
  ["actions", "task", "Mes actions", "Vérifiez les propositions et confirmez vos décisions."],
];
const bwsPages = [
  ["security", "shield", "Supervision sécurité", "Suivez les événements des différentes organisations."],
  ["llm", "chat", "Journal LLM", "Consultez l’usage des modèles sans accéder aux échanges."],
];

function App() {
  const [session, setSession] = useState(null);
  const [readings, setReadings] = useState([]);
  const [page, setPage] = useState("overview");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [launch, setLaunch] = useState(null);
  const loginInFlight = useRef(false);
  const bws = session?.user.role === "security_admin";

  function signOut(message = "") {
    setSession(null); setReadings([]); setLaunch(null); setMenuOpen(false); setProblem(message);
  }
  const expired = () => signOut("Votre session a expiré. Reconnectez-vous pour continuer.");

  async function signIn(event) {
    event.preventDefault();
    if (loginInFlight.current) return;
    const form = event.currentTarget;
    const fields = new FormData(form);
    loginInFlight.current = true; setBusy(true); setProblem("");
    try {
      const auth = await api("/auth/login", { body: { email: String(fields.get("email")).trim().toLowerCase(), password: String(fields.get("password")) } });
      form.reset();
      const user = await api("/auth/me", { token: auth.access_token });
      const measures = user.role === "security_admin" ? { items: [] } : await api("/readings", { token: auth.access_token });
      setReadings(measures.items); setPage(user.role === "security_admin" ? "security" : "overview");
      setSession({ user, token: auth.access_token });
    } catch (error) { setProblem(error.message); }
    finally { loginInFlight.current = false; setBusy(false); }
  }
  async function refresh() {
    if (busy || !session || bws) return;
    setBusy(true); setProblem("");
    try { setReadings((await api("/readings", { token: session.token })).items); }
    catch (error) { if (error.status === 401) expired(); else setProblem(error.message); }
    finally { setBusy(false); }
  }
  function openAssistant(sensor) {
    setLaunch({ id: Date.now(), sensor: sensor ? { resource: sensor.resource, sensor_id: sensor.sensor_id } : null });
    setPage("assistant"); setMenuOpen(false);
  }

  if (!session) return <main className="login-layout"><section className="login-story"><div className="brand"><span className="brand-mark"><Icon name="shield" size={24} /></span>Aegis<span>AI</span></div><div className="login-story-body"><span className="eyebrow">VOTRE ESPACE IOT</span><h1>Moins de chiffres.<br /><em>Plus de clarté.</em></h1><p>Comprenez vos consommations, échangez avec votre assistant et gardez le contrôle de vos décisions.</p><div className="login-resources"><span><Icon name="drop" />Eau</span><span><Icon name="bolt" />Électricité</span><span><Icon name="chat" />Assistant</span></div></div><p className="login-foot">AegisAI · Démonstrateur indépendant · Données synthétiques</p></section><section className="login-form-wrap"><div className="login-card"><span className="eyebrow">BIENVENUE</span><h2>Votre espace vous attend.</h2><p className="subtle">Connectez-vous avec le compte qui vous a été attribué.</p><form onSubmit={signIn}><label htmlFor="login-email">Adresse e-mail</label><input id="login-email" name="email" type="email" required autoComplete="username" maxLength={254} placeholder="client.a@example.test" disabled={busy} /><label htmlFor="login-password">Mot de passe</label><input id="login-password" name="password" type="password" required maxLength={128} autoComplete="current-password" disabled={busy} />{problem && <Message danger>{problem}</Message>}<button disabled={busy}>{busy ? "Connexion en cours…" : "Se connecter"}<Icon name="arrow" size={18} /></button></form><div className="login-security"><Icon name="shield" size={17} /><span>Accès personnel à votre organisation.</span></div></div></section></main>;

  const pages = bws ? bwsPages : clientPages;
  const current = pages.find(item => item[0] === page) || pages[0];
  const common = { api, session, busy, setBusy, onExpired: expired };
  return <div className="workspace"><aside className={`sidebar ${menuOpen ? "mobile-open" : ""}`}><div className="brand"><span className="brand-mark"><Icon name="shield" size={24} /></span>Aegis<span>AI</span></div><p className="nav-caption">{bws ? "ADMINISTRATION BWS" : "MON ESPACE"}</p><nav aria-label="Navigation principale">{pages.map(([id, icon, title]) => <button key={id} disabled={busy} aria-current={page === id ? "page" : undefined} className={`nav-link ${page === id ? "active" : ""}`} onClick={() => { setPage(id); setMenuOpen(false); }}><Icon name={icon} size={20} /><span>{title}</span>{page === id && <span className="active-dot" />}</button>)}</nav><div className="sidebar-tip"><Icon name="shield" size={23} /><strong>{bws ? "Un accès dédié à la sécurité" : "Vos décisions vous appartiennent"}</strong><p>{bws ? "La supervision est séparée des fonctions des clients." : "Les opérations passent par votre confirmation manuelle."}</p></div><div className="account-box"><span className="account-avatar">{bws ? "B" : session.user.email.slice(0, 1).toUpperCase()}</span><div><strong>{bws ? "Sécurité BWS" : "Mon compte"}</strong><small>{session.user.email}</small></div><button className="icon-button" aria-label="Se déconnecter" title="Se déconnecter" disabled={busy} onClick={() => signOut()}><Icon name="logout" size={19} /></button></div></aside>
    <main className="content"><header className="topbar"><div className="page-title"><button className="icon-button menu-button" aria-label="Afficher ou masquer le menu" aria-expanded={menuOpen} disabled={busy} onClick={() => setMenuOpen(!menuOpen)}><Icon name="menu" /></button><div><p className="breadcrumb">{bws ? "BWS / Sécurité" : "Mon espace / Consommations"}</p><h1>{current[2]}</h1><p className="page-description">{current[3]}</p></div></div>{!bws && ["overview", "meters"].includes(page) && <button className="secondary" disabled={busy} onClick={refresh}><Icon name="refresh" size={17} /><span>{busy ? "Chargement…" : "Actualiser"}</span></button>}</header>
      <div className="demo-notice"><span className="demo-dot" /><strong>Démonstration</strong><span>Données synthétiques. Les dates affichées sont celles des mesures enregistrées.</span></div>
      {problem && <Message danger>{problem}</Message>}
      {bws ? <><div hidden={page !== "security"}><BWSSecurity {...common} mode="audit" active={page === "security"} /></div><div hidden={page !== "llm"}><BWSSecurity {...common} mode="llm" active={page === "llm"} /></div></> : <>
        {page === "overview" && <Overview readings={readings} busy={busy} onAssistant={openAssistant} />}
        {page === "meters" && <Meters readings={readings} />}
        <div hidden={page !== "assistant"}><Chat {...common} readings={readings} launch={launch} onActions={() => setPage("actions")} /></div>
        <div hidden={page !== "actions"}><Actions {...common} active={page === "actions"} onAssistant={openAssistant} /></div>
      </>}
      <footer className="app-footer"><span>AegisAI · Secure AI Agent Platform for IoT</span><span>{bws ? "Supervision centralisée" : "Espace de votre organisation"}</span></footer>
    </main>
  </div>;
}
createRoot(document.getElementById("root")).render(<App />);
