import React, { useEffect, useRef, useState } from "react";
import { Icon, Empty, Message, date } from "./ui.jsx";

const statuses = { pending: "À confirmer", approved: "Approuvée", rejected: "Refusée", executed: "Tâche créée" };
export default function Actions({ api, session, active, busy, setBusy, onExpired, onAssistant }) {
  const [proposals, setProposals] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [comment, setComment] = useState("");
  const [problem, setProblem] = useState("");
  const [success, setSuccess] = useState("");
  const inFlight = useRef(false);
  const selected = proposals.find(item => item.id === selectedId);
  const owns = selected?.created_by === session.user.id;
  const client = session.user.role === "client";
  const canDecide = client ? owns : session.user.role === "tenant_admin";
  const canExecute = client ? owns && selected?.decided_by === session.user.id : ["operator", "tenant_admin"].includes(session.user.role);

  async function fetchLists() {
    const [p, t] = await Promise.all([api("/proposals", { token: session.token }), api("/tasks", { token: session.token })]);
    setProposals(p.items);
    setTasks(t.items);
  }
  async function refresh() {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setProblem("");
    try { await fetchLists(); } catch (error) { if (error.status === 401) onExpired(); else setProblem(error.message); }
    finally { inFlight.current = false; setBusy(false); }
  }
  useEffect(() => { if (active) refresh(); }, [active, session.token]);

  async function act(action) {
    if (!selected || busy || inFlight.current) return;
    inFlight.current = true; setBusy(true); setProblem(""); setSuccess("");
    try {
      if (action === "execute") {
        await api(`/proposals/${selected.id}/execute`, { token: session.token, body: {} });
        setSuccess("La tâche d’inspection a été créée. Aucun appareil n’a été commandé.");
      } else {
        await api(`/proposals/${selected.id}/decision`, { token: session.token, body: { decision: action, comment: comment.trim() || null } });
        setSuccess(action === "approve" ? "Proposition approuvée. La création de la tâche reste une étape distincte." : "Proposition refusée.");
      }
      setComment(""); await fetchLists();
    } catch (error) {
      if (error.status === 401) onExpired();
      else setProblem(error.status === 409 ? `${error.message}. Actualisez la liste avant de poursuivre.` : error.message);
    } finally { inFlight.current = false; setBusy(false); }
  }
  return <div className="page-stack"><div className="section-heading"><div><h2>Vous gardez la main</h2><p>Une proposition, votre approbation, puis une tâche d’inspection.</p></div><button className="secondary" disabled={busy} onClick={refresh}><Icon name="refresh" size={16} /> Actualiser</button></div>
    {problem && <Message danger>{problem}</Message>}{success && <Message>{success}</Message>}
    <div className="actions-layout"><section className="panel"><div className="panel-heading"><h2>Mes propositions</h2><span className="soft-tag">{proposals.length}</span></div>{!proposals.length ? <Empty icon="task" title="Aucune proposition pour le moment">Demandez une analyse à l’assistant. Lorsqu’une inspection est suggérée, vous pourrez préparer une proposition.<button className="secondary" disabled={busy} onClick={() => onAssistant()}>Ouvrir l’assistant</button></Empty> : <div className="proposal-list">{proposals.map(item => <button className={`proposal-item ${selectedId === item.id ? "selected" : ""}`} key={item.id} disabled={busy} onClick={() => { setSelectedId(item.id); setComment(""); setSuccess(""); }}><div><strong>{item.title}</strong><span>{item.sensor_id} · {date(item.created_at)}</span></div><span className={`status-tag ${item.status}`}>{statuses[item.status] || item.status}</span></button>)}</div>}</section>
    <section className="panel action-detail">{!selected ? <Empty icon="task" title="Sélectionnez une proposition">Consultez son contenu avant toute décision.</Empty> : <><span className={`status-tag ${selected.status}`}>{statuses[selected.status] || selected.status}</span><h2>{selected.title}</h2><dl className="detail-list"><div><dt>Compteur concerné</dt><dd>{selected.sensor_id}</dd></div><div><dt>Opération</dt><dd>Créer une tâche d’inspection</dd></div><div><dt>Préparée le</dt><dd>{date(selected.created_at)}</dd></div></dl><p className="subtle">Cette opération crée une tâche de suivi dans le démonstrateur. Elle ne commande aucun équipement IoT.</p>
      {selected.status === "pending" && canDecide && <div className="decision-box"><label htmlFor="decision-comment">Commentaire facultatif</label><textarea id="decision-comment" rows={3} maxLength={500} value={comment} disabled={busy} onChange={e => setComment(e.target.value)} /><div className="button-row"><button disabled={busy} onClick={() => act("approve")}><Icon name="check" size={17} /> Confirmer l’approbation</button><button className="secondary danger-text" disabled={busy} onClick={() => act("reject")}>Refuser</button></div></div>}
      {selected.status === "approved" && canExecute && <div className="decision-box"><p>Vous avez vérifié la proposition. Confirmez maintenant la création de la tâche.</p><button disabled={busy} onClick={() => act("execute")}>Confirmer la création de la tâche</button></div>}
      {selected.decision_comment && <blockquote>{selected.decision_comment}</blockquote>}
      {selected.status === "rejected" && <Message>Cette proposition a été refusée et ne peut pas être exécutée.</Message>}
      {selected.status === "executed" && <Message>Tâche créée. Retrouvez-la dans la liste ci-dessous.</Message>}
      {client && !owns && <p className="subtle">Cette proposition a été préparée par un autre utilisateur de votre organisation. Vous ne pouvez pas la confirmer.</p>}
    </>}</section></div>
    <section className="panel"><div className="panel-heading"><div><h2>Tâches d’inspection</h2><p>Tâches créées après approbation, sans suivi d’intervention physique.</p></div><span className="soft-tag">{tasks.length}</span></div>{!tasks.length ? <Empty icon="check" title="Aucune tâche créée">Les tâches approuvées apparaîtront ici.</Empty> : <div className="table-wrap"><table><thead><tr><th>Tâche</th><th>Compteur</th><th>Création</th><th>Référence</th></tr></thead><tbody>{tasks.map(task => <tr key={task.id}><td><strong>{task.title}</strong></td><td>{task.sensor_id}</td><td>{date(task.created_at)}</td><td><details><summary>Voir les références</summary><code>Tâche : {task.id}</code><br /><code>Proposition : {task.proposal_id}</code></details></td></tr>)}</tbody></table></div>}</section>
  </div>;
}
