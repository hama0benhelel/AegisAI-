import React, { useState } from "react";

const number = value => Number(value).toLocaleString("fr-FR");
const date = value => new Date(value).toLocaleString("fr-FR");

const statuses = {
  pending: "En attente d’approbation",
  approved: "Approuvée",
  rejected: "Rejetée",
  executed: "Exécutée",
};

export default function Analyses({
  api, session, readings, busy, setBusy, onExpired,
}) {
  const sensors = [...new Map(
    readings.map(row => [
      JSON.stringify([row.resource, row.sensor_id]),
      { resource: row.resource, sensor_id: row.sensor_id },
    ])
  ).values()];

  const [selection, setSelection] = useState("");
  const [analysisId, setAnalysisId] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [proposal, setProposal] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const canCreate = ["operator", "tenant_admin"].includes(session.user.role);

  async function perform(operation) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await operation();
    } catch (err) {
      if (err.status === 401) onExpired();
      else setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function showAnalysis(data) {
    setAnalysis(data);
    setAnalysisId(data.id);
    setProposal(null);
  }

  function launch(event) {
    event.preventDefault();
    const sensor = sensors.find(
      item => JSON.stringify([item.resource, item.sensor_id]) === selection
    );
    if (!sensor || !canCreate || busy) return;

    perform(async () => {
      setAnalysis(null);
      setProposal(null);
      const data = await api(`/agents/${sensor.resource}/analyze`, {
        token: session.token,
        body: { sensor_id: sensor.sensor_id },
      });
      showAnalysis(data);
      setMessage("Analyse enregistrée.");
    });
  }

  function load(event) {
    event.preventDefault();
    if (busy) return;
    const id = analysisId.trim();

    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
      setError("Saisissez un identifiant d’analyse UUID valide.");
      return;
    }

    perform(async () => {
      setAnalysis(null);
      setProposal(null);
      const data = await api(`/analyses/${encodeURIComponent(id)}`, {
        token: session.token,
      });
      showAnalysis(data);
    });
  }

  function createProposal() {
    if (!analysis || !canCreate || busy) return;
    perform(async () => {
      const data = await api(`/analyses/${analysis.id}/proposal`, {
        token: session.token,
        body: {},
      });
      setProposal(data.proposal);
      setMessage(data.already_exists
        ? "Proposition existante retrouvée : son statut est conservé."
        : "Proposition créée. Une approbation est requise avant exécution.");
    });
  }

  const result = analysis?.result;

  return (
    <div className="analysis-page">
      <section className="panel analysis-card">
        <h2>Analyser un compteur</h2>
        <p className="muted">
          Comparaison de la dernière consommation horaire à la moyenne des
          23 heures précédentes. Chaque lancement enregistre une analyse.
        </p>

        {canCreate ? (
          <form onSubmit={launch} className="analysis-form">
            <label>Compteur accessible
              <select required value={selection} disabled={busy}
                onChange={event => setSelection(event.target.value)}>
                <option value="">Choisir un compteur</option>
                {sensors.map(sensor => {
                  const key = JSON.stringify([sensor.resource, sensor.sensor_id]);
                  return (
                    <option key={key} value={key}>
                      {sensor.sensor_id} — {sensor.resource === "water" ? "Eau" : "Énergie"}
                    </option>
                  );
                })}
              </select>
            </label>
            <button disabled={busy || !selection}>
              {busy ? "Traitement…" : "Lancer et enregistrer l’analyse"}
            </button>
          </form>
        ) : (
          <p className="notice">
            Votre rôle permet de consulter une analyse existante.
            Le lancement est réservé aux opérateurs et administrateurs.
          </p>
        )}
      </section>

      <section className="panel analysis-card">
        <h2>Consulter une analyse enregistrée</h2>
        <form onSubmit={load} className="analysis-form">
          <label>Identifiant de l’analyse
            <input required value={analysisId} disabled={busy}
              placeholder="UUID de l’analyse" maxLength={36}
              onChange={event => setAnalysisId(event.target.value)} />
          </label>
          <button className="secondary" disabled={busy || !analysisId.trim()}>
            Consulter
          </button>
        </form>
      </section>

      {error && <p className="error" role="alert">{error}</p>}
      {message && <p className="notice" role="status">{message}</p>}

      {result && (
        <section className="panel analysis-card">
          <p className="eyebrow">RÉSULTAT ENREGISTRÉ</p>
          <h2>{result.sensor_id}</h2>
          <p>
            <span className="badge">
              {result.classification === "high_consumption"
                ? "Dépassement du seuil"
                : result.classification === "normal"
                  ? "Aucun dépassement du seuil"
                  : result.classification}
            </span>
          </p>
          <p>{result.interpretation}</p>
          <p className="muted">
            Données au {date(result.data_as_of)} · Règle {result.rule_version}
          </p>
          <p className="analysis-id">Analyse : {analysis.id}</p>

          <div className="stats">
            <article><span>Dernière heure</span>
              <strong>{number(result.latest_value)} {result.unit}</strong>
            </article>
            <article><span>Moyenne des 23 heures précédentes</span>
              <strong>{number(result.baseline_mean)} {result.unit}</strong>
            </article>
            <article><span>Seuil de dépassement</span>
              <strong>{number(result.threshold_value)} {result.unit}</strong>
            </article>
          </div>

          <p>
            Ratio à la moyenne : ×{number(result.ratio_to_baseline)}.
            Probabilité de confiance : non estimée par cette règle.
          </p>
          <ul>
            {result.limitations.map(item => <li key={item}>{item}</li>)}
          </ul>

          <details>
            <summary>Voir les {result.sources.length} mesures sources</summary>
            <div className="table-wrap">
              <table>
                <thead><tr>
                  <th>Date</th><th>Valeur</th><th>Source</th><th>ID mesure</th>
                </tr></thead>
                <tbody>
                  {result.sources.map(source => (
                    <tr key={source.reading_id}>
                      <td>{date(source.measured_at)}</td>
                      <td>{number(source.value)} {source.unit}</td>
                      <td>{source.data_source}</td>
                      <td className="analysis-id">{source.reading_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>

          <hr />
          <h3>Proposition d’inspection</h3>
          {result.suggested_proposal ? (
            <>
              <p>{result.suggested_proposal.title}</p>
              <p className="muted">
                La création prépare une proposition pour validation humaine.
              </p>
              {canCreate && (
                <button disabled={busy} onClick={createProposal}>
                  {proposal ? "Retrouver la proposition" : "Créer une proposition à valider"}
                </button>
              )}
              {proposal && (
                <div className="notice" role="status">
                  <p className="analysis-id">Proposition : {proposal.id}</p>
                  <p>Statut : {statuses[proposal.status] || proposal.status}</p>
                </div>
              )}
            </>
          ) : (
            <p>Aucune proposition générée par cette analyse.</p>
          )}
        </section>
      )}
    </div>
  );
}
