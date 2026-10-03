import React, { useRef, useState } from "react";

const labels = {
  pending: "En attente",
  approved: "Approuvée",
  rejected: "Rejetée",
  executed: "Tâche créée",
};
const date = value => value
  ? new Date(value).toLocaleString("fr-FR")
  : "—";

export default function Workflow({
  api, session, busy, setBusy, onExpired,
}) {
  const [proposals, setProposals] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState("");
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const inFlight = useRef(false);

  const admin = session.user.role === "tenant_admin";
  const canExecute = ["operator", "tenant_admin"].includes(session.user.role);
  const selected = proposals.find(item => item.id === selectedId);

  async function refresh() {
    const [proposalData, taskData] = await Promise.all([
      api("/proposals", { token: session.token }),
      api("/tasks", { token: session.token }),
    ]);
    setProposals(proposalData.items);
    setTasks(taskData.items);
    setLoaded(true);
  }

  async function perform(operation) {
    if (inFlight.current || busy) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await operation();
    } catch (err) {
      if (err.status === 401) onExpired();
      else setError(err.message);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  function choose(id) {
    setSelectedId(id);
    setComment("");
    setError("");
    setMessage("");
  }

  async function refreshAfterChange() {
    try {
      await refresh();
    } catch (err) {
      if (err.status === 401) throw err;
      setError(
        "Action enregistrée, mais actualisation impossible. Rechargez les listes."
      );
    }
  }

  function decide(decision) {
    if (!admin || selected?.status !== "pending") return;
    const id = selected.id;
    perform(async () => {
      const updated = await api(`/proposals/${id}/decision`, {
        token: session.token,
        body: { decision, comment: comment.trim() || null },
      });
      setProposals(items => items.map(item => item.id === id ? updated : item));
      setComment("");
      setMessage(decision === "approve"
        ? "Approbation enregistrée. La tâche peut maintenant être créée."
        : "Rejet enregistré. Cette proposition ne peut pas être exécutée.");
      await refreshAfterChange();
    });
  }

  function execute() {
    if (!canExecute || selected?.status !== "approved") return;
    const id = selected.id;
    perform(async () => {
      const data = await api(`/proposals/${id}/execute`, {
        token: session.token,
        body: {},
      });
      setProposals(items => items.map(item =>
        item.id === id ? { ...item, status: "executed" } : item
      ));
      setTasks(items => [
        data.task,
        ...items.filter(item => item.id !== data.task.id),
      ]);
      setMessage(
        `${data.already_executed ? "Tâche existante retrouvée" : "Tâche créée"} : ${data.task.id}`
      );
      await refreshAfterChange();
    });
  }

  return (
    <div className="analysis-page">
      <section className="panel analysis-card">
        <div className="panel-header">
          <div>
            <h2>Propositions de votre organisation</h2>
            <p className="muted">
              Jusqu’à 100 propositions et 100 tâches récentes.
            </p>
          </div>
          <button disabled={busy} onClick={() => perform(refresh)}>
            {busy ? "Traitement…" : loaded ? "Actualiser les listes" : "Charger les listes"}
          </button>
        </div>

        {!loaded ? (
          <p>Chargez les listes pour consulter les propositions accessibles.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr>
                <th>Capteur</th><th>Proposition</th><th>Statut</th>
                <th>Créée le</th><th>Détail</th>
              </tr></thead>
              <tbody>
                {proposals.map(item => (
                  <tr key={item.id}>
                    <td>{item.sensor_id}</td>
                    <td>{item.title}</td>
                    <td><span className="badge">
                      {labels[item.status] || item.status}
                    </span></td>
                    <td>{date(item.created_at)}</td>
                    <td>
                      <button className="secondary" disabled={busy}
                        onClick={() => choose(item.id)}
                        aria-label={`Consulter la proposition ${item.id}`}>
                        Consulter
                      </button>
                    </td>
                  </tr>
                ))}
                {!proposals.length && (
                  <tr><td colSpan={5}>Aucune proposition disponible.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {error && <p className="error" role="alert">{error}</p>}
      {message && <p className="notice analysis-id" role="status">{message}</p>}

      {selected && (
        <section className="panel analysis-card">
          <p className="eyebrow">PROPOSITION SÉLECTIONNÉE</p>
          <h2>{selected.title}</h2>
          <p><strong>Capteur :</strong> {selected.sensor_id}</p>
          <p><strong>Statut :</strong> {labels[selected.status] || selected.status}</p>
          <p className="analysis-id">Proposition : {selected.id}</p>
          {selected.analysis_id && (
            <p className="analysis-id">Analyse source : {selected.analysis_id}</p>
          )}
          <p>Créée le {date(selected.created_at)}</p>

          {selected.decided_at && (
            <>
              <p>Décision enregistrée le {date(selected.decided_at)}</p>
              <p>Commentaire : {selected.decision_comment || "Aucun"}</p>
            </>
          )}

          {selected.status === "pending" && (
            admin ? (
              <div className="analysis-form">
                <label>Commentaire de décision — facultatif
                  <textarea rows={3} maxLength={500} value={comment}
                    disabled={busy}
                    onChange={event => setComment(event.target.value)} />
                </label>
                <p className="muted">
                  Vérifiez le contenu avant de confirmer.
                  La décision ne peut pas être modifiée dans ce workflow.
                </p>
                <div className="workflow-actions">
                  <button disabled={busy} onClick={() => decide("approve")}>
                    Confirmer l’approbation
                  </button>
                  <button className="secondary" disabled={busy}
                    onClick={() => decide("reject")}>
                    Confirmer le rejet
                  </button>
                </div>
              </div>
            ) : (
              <p className="notice">
                En attente de la décision d’un administrateur de votre organisation.
              </p>
            )
          )}

          {selected.status === "approved" && (
            canExecute ? (
              <div>
                <p>
                  Cette action crée une tâche d’inspection enregistrée.
                  Elle ne commande aucun équipement.
                </p>
                <button disabled={busy} onClick={execute}>
                  Confirmer la création de la tâche
                </button>
              </div>
            ) : (
              <p>La création de la tâche est réservée aux opérateurs et administrateurs.</p>
            )
          )}

          {selected.status === "rejected" && (
            <p>Proposition rejetée : aucune exécution autorisée.</p>
          )}
          {selected.status === "executed" && (
            <p>La tâche a été créée. Consultez la liste ci-dessous.</p>
          )}
        </section>
      )}

      {loaded && (
        <section className="panel analysis-card">
          <h2>Tâches d’inspection enregistrées</h2>
          <p className="muted">
            La présence d’une tâche signifie qu’elle a été créée,
            pas que l’inspection a été réalisée.
          </p>
          <div className="table-wrap">
            <table>
              <thead><tr>
                <th>Capteur</th><th>Tâche</th><th>Date</th>
                <th>ID tâche / proposition</th>
              </tr></thead>
              <tbody>
                {tasks.map(task => (
                  <tr key={task.id}>
                    <td>{task.sensor_id}</td>
                    <td>{task.title}</td>
                    <td>{date(task.created_at)}</td>
                    <td className="analysis-id">
                      <div>Tâche : {task.id}</div>
                      <div>Proposition : {task.proposal_id}</div>
                    </td>
                  </tr>
                ))}
                {!tasks.length && (
                  <tr><td colSpan={4}>Aucune tâche disponible.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
