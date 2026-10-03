import React, { useRef, useState } from "react";

const date = value => new Date(value).toLocaleString("fr-FR");

export default function Audit({
  api, session, busy, setBusy, onExpired,
}) {
  const [events, setEvents] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [eventType, setEventType] = useState("all");
  const [result, setResult] = useState("all");
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
      const data = await api("/security/audit?limit=100", {
        token: session.token,
      });
      setEvents(data.items);
      setLoaded(true);
      setLoadedAt(new Date().toISOString());
    } catch (err) {
      if (err.status === 401) onExpired();
      else {
        if (err.status === 403) {
          setEvents([]);
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
        <h2>Accès réservé</h2>
        <p>Le journal d’audit est réservé aux administrateurs de votre organisation.</p>
      </section>
    );
  }

  const types = [...new Set(events.map(event => event.event_type))].sort();
  const query = search.trim().toLowerCase();

  const visible = events.filter(event => {
    const status = Number(event.status_code);
    const typeMatch = eventType === "all" || event.event_type === eventType;
    const resultMatch =
      result === "all" ||
      (result === "success" && status >= 200 && status < 300) ||
      (result === "4xx" && status >= 400 && status < 500) ||
      (result === "5xx" && status >= 500 && status < 600);

    const searchMatch = !query || [
      event.trace_id, event.user_id, event.route, event.event_type,
    ].some(value => String(value ?? "").toLowerCase().includes(query));

    return typeMatch && resultMatch && searchMatch;
  });

  return (
    <div className="analysis-page">
      <section className="panel analysis-card">
        <div className="panel-header">
          <div>
            <h2>Journal d’audit de votre organisation</h2>
            <p className="muted">
              Les filtres portent sur les 100 événements les plus récents
              retournés par l’API.
            </p>
          </div>
          <button disabled={busy} onClick={load}>
            {busy ? "Chargement…" : loaded ? "Actualiser le journal" : "Charger le journal"}
          </button>
        </div>

        {loadedAt && (
          <p className="muted">Dernier chargement : {date(loadedAt)}</p>
        )}
        {error && <p className="error" role="alert">{error}</p>}

        <div className="notice">
          Un événement métier et la requête HTTP correspondante peuvent
          partager le même Trace ID. Ce sont deux entrées distinctes.
        </div>

        {loaded && (
          <>
            <div className="audit-filters">
              <label>Événement
                <select value={eventType} disabled={busy}
                  onChange={event => setEventType(event.target.value)}>
                  <option value="all">Tous les événements</option>
                  {types.map(type => <option key={type} value={type}>{type}</option>)}
                  {eventType !== "all" && !types.includes(eventType) && (
                    <option value={eventType}>{eventType} — absent de cet extrait</option>
                  )}
                </select>
              </label>

              <label>Résultat HTTP
                <select value={result} disabled={busy}
                  onChange={event => setResult(event.target.value)}>
                  <option value="all">Tous les résultats</option>
                  <option value="success">2xx — succès</option>
                  <option value="4xx">4xx — requête refusée ou invalide</option>
                  <option value="5xx">5xx — erreur serveur</option>
                </select>
              </label>

              <label>Rechercher dans cet extrait
                <input value={search} maxLength={200}
                  placeholder="Trace ID, utilisateur, route ou événement"
                  onChange={event => setSearch(event.target.value)} />
              </label>
            </div>

            <p role="status">
              {visible.length} événement(s) affiché(s) sur {events.length} chargé(s).
            </p>

            <div className="table-wrap">
              <table>
                <thead><tr>
                  <th>Date</th><th>Événement</th><th>HTTP</th>
                  <th>Requête</th><th>Utilisateur / Trace ID</th>
                </tr></thead>
                <tbody>
                  {visible.map(event => (
                    <tr key={event.id}>
                      <td>{date(event.occurred_at)}</td>
                      <td>{event.event_type}</td>
                      <td><span className="badge">{event.status_code}</span></td>
                      <td>{event.method} {event.route}</td>
                      <td className="analysis-id">
                        <div>Utilisateur : {event.user_id || "Non associé"}</div>
                        <div>Trace : {event.trace_id}</div>
                      </td>
                    </tr>
                  ))}
                  {!visible.length && (
                    <tr><td colSpan={5}>
                      Aucun événement correspondant dans cet extrait.
                    </td></tr>
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
