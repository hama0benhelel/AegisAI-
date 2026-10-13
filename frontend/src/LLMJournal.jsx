import React, { useRef, useState } from "react";

const number = value => value == null
  ? "Non communiqué"
  : Number(value).toLocaleString("fr-FR");

const statuses = {
  started: "Sans résultat final enregistré",
  success: "Réponse LLM utilisée",
  fallback: "Réponse de secours",
};

export default function LLMJournal({
  api, session, busy, setBusy, onExpired,
}) {
  const [calls, setCalls] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [loadedAt, setLoadedAt] = useState(null);
  const inFlight = useRef(false);
  const authorized = session.user.role === "tenant_admin";

  async function load() {
    if (!authorized || busy || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");

    try {
      const data = await api("/security/llm-calls?limit=100", {
        token: session.token,
      });
      setCalls(data.items);
      setLoaded(true);
      setLoadedAt(new Date().toLocaleString("fr-FR"));
    } catch (err) {
      if (err.status === 401) onExpired();
      else {
        if (err.status === 403) {
          setCalls([]);
          setLoaded(false);
          setLoadedAt(null);
        }
        setError(err.message);
      }
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  if (!authorized) {
    return (
      <section className="panel analysis-card">
        <h2>Accès réservé aux administrateurs</h2>
      </section>
    );
  }

  const reported = calls.filter(call => call.total_tokens != null);
  const tokens = reported.reduce((sum, call) => sum + call.total_tokens, 0);
  const query = search.trim().toLowerCase();
  const visible = calls.filter(call =>
    (filter === "all" || call.status === filter) &&
    (!query || [call.trace_id, call.model, call.operation, call.reason]
      .some(value => String(value ?? "").toLowerCase().includes(query)))
  );

  return (
    <div className="analysis-page">
      <section className="panel analysis-card">
        <div className="panel-header">
          <div>
            <h2>Journal des appels LLM</h2>
            <p className="muted">
              Jusqu’à 100 appels réservés récemment pour votre organisation.
            </p>
          </div>
          <button disabled={busy} onClick={load}>
            {busy ? "Chargement…" : loaded ? "Actualiser" : "Charger le journal"}
          </button>
        </div>

        {error && <p className="error" role="alert">{error}</p>}
        {loadedAt && <p className="muted">Dernier chargement : {loadedAt}</p>}

        <div className="notice">
          Les refus avant réservation, dont le quota local, ne figurent pas
          dans cette liste. Un appel sans résultat final peut être en cours
          ou avoir été interrompu.
        </div>

        {loaded && (
          <>
            <div className="stats">
              <article>
                <span>Appels dans l’extrait</span>
                <strong>{calls.length}</strong>
              </article>
              <article>
                <span>Tokens connus dans l’extrait</span>
                <strong>{reported.length ? number(tokens) : "Non communiqué"}</strong>
                <small>{reported.length}/{calls.length} appels avec total communiqué</small>
              </article>
              <article>
                <span>Réponses de secours dans l’extrait</span>
                <strong>{calls.filter(call => call.status === "fallback").length}</strong>
              </article>
            </div>

            <p className="muted">
              Ces chiffres portent sur l’extrait chargé, avant filtrage.
              Les valeurs inconnues ne sont pas comptées comme zéro.
              Il ne s’agit pas d’une facture ni d’un total mensuel.
            </p>

            <div className="audit-filters">
              <label>Résultat
                <select value={filter}
                  onChange={event => setFilter(event.target.value)}>
                  <option value="all">Tous</option>
                  {Object.entries(statuses).map(([value, label]) =>
                    <option key={value} value={value}>{label}</option>
                  )}
                </select>
              </label>
              <label>Rechercher
                <input value={search} maxLength={200}
                  placeholder="Trace ID, modèle, opération ou motif"
                  onChange={event => setSearch(event.target.value)} />
              </label>
            </div>

            <p role="status">{visible.length} appel(s) affiché(s).</p>

            <div className="table-wrap">
              <table>
                <thead><tr>
                  <th>Date / modèle</th>
                  <th>Opération / résultat</th>
                  <th>Tokens</th>
                  <th>Durée</th>
                  <th>Traçabilité</th>
                </tr></thead>
                <tbody>
                  {visible.map(call => (
                    <tr key={call.id}>
                      <td>
                        <div>{new Date(call.created_at).toLocaleString("fr-FR")}</div>
                        <div>{call.provider} · {call.model}</div>
                      </td>
                      <td>
                        <div>{call.operation}</div>
                        <span className="badge">
                          {statuses[call.status] || call.status}
                        </span>
                        {call.reason && <div>{call.reason}</div>}
                      </td>
                      <td>
                        <div>Entrée : {number(call.prompt_tokens)}</div>
                        <div>Sortie : {number(call.completion_tokens)}</div>
                        <div>Total : {number(call.total_tokens)}</div>
                      </td>
                      <td>
                        {call.duration_ms == null
                          ? "Non communiquée"
                          : `${number(call.duration_ms)} ms`}
                      </td>
                      <td className="analysis-id">
                        <div>Trace : {call.trace_id}</div>
                        <div>Appel : {call.id}</div>
                        <div>Utilisateur : {call.user_id}</div>
                        <div>Prompt : {call.prompt_version}</div>
                      </td>
                    </tr>
                  ))}
                  {!visible.length && (
                    <tr><td colSpan={5}>Aucun appel correspondant dans cet extrait.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
