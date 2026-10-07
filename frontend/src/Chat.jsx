import React, { useRef, useState } from "react";

const reasons = {
  suspicious_instruction: "Instruction potentiellement dangereuse détectée.",
  write_action_not_available_in_chat:
    "L’approbation et l’exécution passent par la page Propositions et tâches.",
  intent_not_enabled: "Cette fonctionnalité n’est pas activée dans l’assistant.",
  out_of_scope_or_unrecognized:
    "Demande hors périmètre ou formulation non reconnue. Essayez un exemple proposé.",
};

export default function Chat({
  api, session, readings, busy, setBusy, onExpired,
}) {
  const [message, setMessage] = useState("");
  const [sensorKey, setSensorKey] = useState("");
  const [analysisId, setAnalysisId] = useState("");
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const inFlight = useRef(false);

  const sensors = [...new Map(readings.map(row => [
    JSON.stringify([row.resource, row.sensor_id]),
    { resource: row.resource, sensor_id: row.sensor_id },
  ])).values()];

  function append(entry) {
    setHistory(items => [...items, entry].slice(-20));
  }

  async function send(event) {
    event.preventDefault();
    if (busy || inFlight.current || !message.trim()) return;

    const id = analysisId.trim();
    if (id && !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
      setError("L’identifiant d’analyse doit être un UUID valide ou rester vide.");
      return;
    }

    const sensor = sensors.find(
      item => JSON.stringify([item.resource, item.sensor_id]) === sensorKey
    );
    const body = { message: message.trim() };
    if (sensor) {
      body.resource = sensor.resource;
      body.sensor_id = sensor.sensor_id;
    }
    if (id) body.analysis_id = id;

    const question = body.message;
    const context = {
      sensor: sensor?.sensor_id,
      analysis: id || null,
    };

    inFlight.current = true;
    setBusy(true);
    setError("");

    try {
      const response = await api("/chat", {
        token: session.token,
        body,
        withMeta: true,
      });
      append({
        question, context,
        data: response.data,
        status: response.status,
        traceId: response.traceId,
      });
      setMessage("");
    } catch (err) {
      if (err.status === 401) {
        onExpired();
      } else {
        const reason = err.detail?.reason;
        append({
          question, context,
          status: err.status,
          traceId: err.traceId,
          error: reasons[reason] || err.message,
          reason,
          gateVersion: err.detail?.gate_version,
        });
      }
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  async function decideConfirmation(index, decision) {
    const entry = history[index];
    const pending = entry?.data?.confirmation;
    if (!pending || entry.resolution || busy || inFlight.current) return;

    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const response = await api(
        `/chat/confirmations/${pending.id}/decision`,
        {
          token: session.token,
          body: { decision },
          withMeta: true,
        }
      );
      setHistory(items => items.map((item, position) =>
        position === index
          ? {
              ...item,
              resolution: response.data,
              decisionTraceId: response.traceId,
              confirmationError: null,
            }
          : item
      ));
    } catch (err) {
      if (err.status === 401) onExpired();
      else {
        setHistory(items => items.map((item, position) =>
          position === index
            ? {
                ...item,
                confirmationError: err.message,
                decisionTraceId: err.traceId,
              }
            : item
        ));
      }
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  return (
    <div className="analysis-page">
      <section className="panel analysis-card">
        <h2>Assistant de consommation</h2>
        <p className="muted">
          Consultez une mesure, expliquez une analyse ou demandez une analyse
          de consommation. Chaque demande est traitée indépendamment.
        </p>
        <div className="notice">
          Une demande d’analyse prépare une prévisualisation. Son enregistrement
          nécessite votre confirmation. Les propositions et leur validation
          restent accessibles dans les pages dédiées.
        </div>

        <p>Exemples — cliquez pour remplir le message, puis envoyez :</p>
        <div className="workflow-actions">
          {[
            "Affiche la consommation",
            "Explique cette analyse",
            "Analyse la consommation",
          ].map(example => (
            <button key={example} type="button" className="secondary"
              disabled={busy} onClick={() => setMessage(example)}>
              {example}
            </button>
          ))}
        </div>

        <form onSubmit={send} className="analysis-form chat-form">
          <label>Compteur — pour consulter ou analyser sa consommation
            <select value={sensorKey} disabled={busy}
              onChange={event => setSensorKey(event.target.value)}>
              <option value="">Aucun compteur sélectionné</option>
              {sensors.map(sensor => {
                const key = JSON.stringify([sensor.resource, sensor.sensor_id]);
                return <option key={key} value={key}>
                  {sensor.sensor_id} — {sensor.resource === "water" ? "Eau" : "Énergie"}
                </option>;
              })}
            </select>
          </label>

          <label>ID analyse — uniquement pour expliquer une analyse existante
            <input value={analysisId} maxLength={36} disabled={busy}
              placeholder="Copiez l’ID depuis la page Analyses"
              onChange={event => setAnalysisId(event.target.value)} />
          </label>

          <label>Message
            <textarea required rows={4} maxLength={1000} value={message}
              disabled={busy}
              onChange={event => setMessage(event.target.value)} />
          </label>
          <span className="muted">{message.length}/1000 caractères</span>

          {error && <p className="error" role="alert">{error}</p>}
          <button disabled={busy || !message.trim()}>
            {busy ? "Traitement…" : "Envoyer la demande"}
          </button>
        </form>
      </section>

      <section className="panel analysis-card">
        <div className="panel-header">
          <h2>Échanges de cette session</h2>
          <button className="secondary" disabled={busy || !history.length}
            onClick={() => setHistory([])}>
            Effacer l’affichage
          </button>
        </div>
        <p className="muted">
          Les 20 derniers échanges sont conservés ici tant que cette page reste
          ouverte. Effacer l’affichage ne supprime pas les événements d’audit.
        </p>

        <div aria-live="polite">
          {!history.length && <p>Aucune demande envoyée.</p>}
          {history.map((item, index) => (
            <article className="chat-entry" key={index}>
              <h3>Vous</h3>
              <p className="chat-text">{item.question}</p>
              <p className="muted analysis-id">
                Compteur : {item.context.sensor || "non sélectionné"}
                {" · "}Analyse : {item.context.analysis || "non sélectionnée"}
              </p>

              <h3>{item.error ? "Demande non aboutie" : "Assistant"}</h3>
              {item.error ? (
                <p className="error">{item.error}</p>
              ) : (
                <>
                  {item.data.needs_clarification && (
                    <p className="badge">Précision nécessaire</p>
                  )}
                  <p className="chat-text">{item.data.answer}</p>
                  {item.data.needs_confirmation && (
                    <div className="notice">
                      <h4>Analyse à enregistrer</h4>
                      <p>
                        Compteur : {item.data.confirmation.sensor_id}
                        {" · "}Ressource : {item.data.confirmation.resource}
                      </p>
                      <p>
                        Données au : {new Date(
                          item.data.confirmation.preview.data_as_of
                        ).toLocaleString("fr-FR")}
                      </p>
                      <p>
                        Dernière valeur : {item.data.confirmation.preview.latest_value}
                        {" "}{item.data.confirmation.preview.unit}
                        {" · "}Seuil : {item.data.confirmation.preview.threshold_value}
                        {" "}{item.data.confirmation.preview.unit}
                      </p>
                      <p>{item.data.confirmation.preview.interpretation}</p>
                      <p>
                        Cette prévisualisation utilise les mesures capturées
                        au moment de la demande.
                        Confirmer enregistre l’analyse, sans créer de proposition.
                      </p>
                      <p>
                        Confirmation possible jusqu’au : {new Date(
                          item.data.confirmation.expires_at
                        ).toLocaleString("fr-FR")}
                      </p>
                      {!item.resolution ? (
                        <div className="workflow-actions">
                          <button disabled={busy}
                            onClick={() => decideConfirmation(index, "confirm")}>
                            Confirmer l’enregistrement
                          </button>
                          <button className="secondary" disabled={busy}
                            onClick={() => decideConfirmation(index, "cancel")}>
                            Annuler
                          </button>
                        </div>
                      ) : (
                        <p className="analysis-id" role="status">
                          {item.resolution.status === "confirmed"
                            ? `Analyse enregistrée : ${item.resolution.analysis_id}`
                            : "Demande annulée : aucune analyse enregistrée."}
                        </p>
                      )}
                      {item.confirmationError && (
                        <p className="error" role="alert">{item.confirmationError}</p>
                      )}
                      {item.decisionTraceId && (
                        <p className="analysis-id">
                          Trace de la décision : {item.decisionTraceId}
                        </p>
                      )}
                    </div>
                  )}
                  {item.data.analysis_id && (
                    <p className="analysis-id">Analyse : {item.data.analysis_id}</p>
                  )}
                  {item.data.suggested_proposal && (
                    <div className="notice">
                      <p>Suggestion : {item.data.suggested_proposal.title}</p>
                      <p>
                        Pour créer la proposition, ouvrez cette analyse par son ID
                        dans la page Analyses.
                      </p>
                    </div>
                  )}
                  {item.data.limitations?.length > 0 && (
                    <ul>{item.data.limitations.map(text => <li key={text}>{text}</li>)}</ul>
                  )}

                  {item.data.sources?.length > 0 && (
                    <details>
                      <summary>Sources utilisées ({item.data.sources.length})</summary>
                      <div className="table-wrap">
                        <table>
                          <thead><tr>
                            <th>Date</th><th>Valeur</th><th>Source</th><th>ID mesure</th>
                          </tr></thead>
                          <tbody>
                            {item.data.sources.map(source => (
                              <tr key={source.reading_id}>
                                <td>{new Date(source.measured_at).toLocaleString("fr-FR")}</td>
                                <td>{Number(source.value).toLocaleString("fr-FR")} {source.unit}</td>
                                <td>{source.data_source}</td>
                                <td className="analysis-id">{source.reading_id}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </details>
                  )}
                </>
              )}

              <details>
                <summary>Traçabilité de la demande</summary>
                <div className="analysis-id">
                  <p>HTTP : {item.status || "Réponse HTTP indisponible"}</p>
                  <p>Trace ID : {item.traceId || "Indisponible"}</p>
                  <p>Gate : {item.data?.gate_version || item.gateVersion || "Non communiqué"}</p>
                  {item.reason && <p>Motif : {item.reason}</p>}
                  {item.data && (
                    <>
                      <p>Intent : {item.data.intent}</p>
                      <p>Mode : {item.data.mode}</p>
                      <p>LLM utilisé : {item.data.llm_used ? "Oui" : "Non"}</p>
                    </>
                  )}
                </div>
              </details>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
