import React, { useEffect, useRef, useState } from "react";
import { Icon, Message, number, date, resourceInfo } from "./ui.jsx";

const reasonText = {
  suspicious_instruction: "Cette demande a été refusée par les contrôles de sécurité.",
  out_of_scope_or_unrecognized: "Je n’ai pas reconnu cette formulation. Essayez une question sur votre consommation ou demandez de l’aide.",
  write_action_not_available_in_chat: "Cette opération passe par les boutons de confirmation ou la page Mes actions.",
  intent_not_enabled: "Cette fonctionnalité n’est pas encore disponible.",
};

export default function Chat({ api, session, readings, busy, setBusy, onExpired, launch, onActions }) {
  const [history, setHistory] = useState([]);
  const [message, setMessage] = useState("");
  const [selection, setSelection] = useState(null);
  const [problem, setProblem] = useState("");
  const [expired, setExpired] = useState(false);
  const [clock, setClock] = useState(Date.now());
  const conversation = useRef(null);
  const inFlight = useRef(false);
  const sequence = useRef(0);
  const bottom = useRef(null);
  const input = useRef(null);
  const consumedLaunch = useRef(null);
  const sensors = [...new Map(readings.map(row => [JSON.stringify([row.resource, row.sensor_id]), { resource: row.resource, sensor_id: row.sensor_id }])).values()];

  useEffect(() => { const timer = setInterval(() => setClock(Date.now()), 15000); return () => clearInterval(timer); }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ block: "nearest" }); }, [history, busy]);
  useEffect(() => {
    if (launch && consumedLaunch.current !== launch.id) {
      consumedLaunch.current = launch.id;
      setSelection(launch.sensor || null);
      setMessage(launch.sensor ? "Affiche la consommation" : "");
    }
  }, [launch]);

  const update = (id, changes) => setHistory(items => items.map(item => item.id === id ? { ...item, ...changes } : item));

  async function send(event) {
    event.preventDefault();
    if (busy || inFlight.current || !message.trim() || expired) return;
    const text = message.trim();
    const selected = selection;
    const id = ++sequence.current;
    inFlight.current = true;
    setBusy(true);
    setProblem("");
    setMessage("");
    setHistory(items => [...items, { id, question: text, pending: true }]);
    try {
      if (!conversation.current) {
        const created = await api("/chat/conversations", { token: session.token, body: {} });
        conversation.current = created.id;
      }
      const body = { message: text };
      if (selected) {
        if (selected.sensor_id) body.sensor_id = selected.sensor_id;
        if (selected.resource) body.resource = selected.resource;
        if (selected.analysis_id) body.analysis_id = selected.analysis_id;
      }
      const response = await api(`/chat/conversations/${conversation.current}/messages`, { token: session.token, body, withMeta: true });
      update(id, { pending: false, data: response.data, traceId: response.traceId });
      setSelection(null);
    } catch (error) {
      if (error.status === 401) onExpired();
      else {
        const detail = reasonText[error.detail?.reason] || error.message;
        update(id, { pending: false, error: detail, traceId: error.traceId });
        if (error.status === 409 && typeof error.detail === "string" && error.detail.includes("expirée")) setExpired(true);
      }
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  async function decide(item, decision) {
    const pending = item.data?.confirmation;
    if (!pending || item.resolution || busy || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    try {
      const response = await api(`/chat/confirmations/${pending.id}/decision`, { token: session.token, body: { decision }, withMeta: true });
      update(item.id, { resolution: response.data, confirmationError: null, decisionTraceId: response.traceId });
    } catch (error) {
      if (error.status === 401) onExpired();
      else update(item.id, { confirmationError: error.message, decisionTraceId: error.traceId });
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  function newConversation() {
    if (busy || inFlight.current) return;
    conversation.current = null;
    setHistory([]);
    setSelection(null);
    setMessage("");
    setProblem("");
    setExpired(false);
    input.current?.focus();
  }

  async function prepareProposal(item) {
    if (busy || inFlight.current || !item.resolution?.analysis_id) return;
    inFlight.current = true;
    setBusy(true);
    try {
      const proposal = await api(`/analyses/${item.resolution.analysis_id}/proposal`, { token: session.token, body: {} });
      update(item.id, { proposal, proposalError: null });
    } catch (error) {
      if (error.status === 401) onExpired();
      else update(item.id, { proposalError: error.message });
    } finally { inFlight.current = false; setBusy(false); }
  }

  return <section className="assistant-shell">
    <div className="assistant-toolbar"><div className="assistant-identity"><span className="assistant-avatar"><Icon name="chat" size={22} /></span><div><strong>Votre assistant AegisAI</strong><p>Consommations & analyses</p></div></div><button type="button" className="secondary compact-button" disabled={busy} onClick={newConversation}><Icon name="plus" size={17} /> Nouvelle conversation</button></div>
    <div className="conversation" role="log" aria-label="Conversation avec l’assistant" aria-live="polite" aria-relevant="additions text">
      {!history.length && <div className="chat-welcome"><span className="chat-welcome-mark"><Icon name="chat" size={34} /></span><span className="eyebrow">UN PEU DE CLARTÉ DANS VOS CONSOMMATIONS</span><h2>Bonjour, comment puis-je <br />vous aider ?</h2><p>Consultez un compteur, préparez une analyse ou demandez une explication.</p><div className="starter-grid">{[
        ["drop", "Ma consommation d’eau", "Quelle est ma consommation d’eau ?"],
        ["bolt", "Ma consommation électrique", "Quelle est ma consommation d’énergie ?"],
        ["chat", "Découvrir l’assistant", "Que peux-tu faire ?"],
      ].map(([icon, title, text]) => <button key={title} className="starter" disabled={busy} onClick={() => { setMessage(text); input.current?.focus(); }}><Icon name={icon} /><span>{title}</span><Icon name="arrow" size={16} /></button>)}</div></div>}
      {history.map(item => {
        const pending = item.data?.confirmation;
        const deadlinePassed = pending && new Date(pending.expires_at).getTime() <= clock;
        return <article className="exchange" key={item.id}>
          <div className="user-bubble"><span className="sr-only">Vous : </span>{item.question}</div>
          <div className="assistant-reply"><span className="reply-avatar" aria-hidden="true">A</span><div className="reply-body">
            <span className="reply-name">AegisAI</span>
            {item.pending ? <p className="thinking">Traitement de votre demande<span aria-hidden="true">…</span></p> : item.error ? <Message danger>{item.error}</Message> : <>
              <p className="answer-text">{item.data?.answer}</p>
              {item.data?.available_sensors?.length > 0 && <div className="choice-list">{item.data.available_sensors.map(sensor => <button className="secondary" key={`${sensor.resource}-${sensor.sensor_id}`} disabled={busy} onClick={() => { setSelection(sensor); setMessage(item.question); input.current?.focus(); }}><Icon name={resourceInfo(sensor.resource).icon} size={17} />{resourceInfo(sensor.resource).label} · {sensor.sensor_id}</button>)}</div>}
              {pending && <div className="confirmation-card"><div className="confirmation-title"><Icon name="shield" /><strong>Vérifiez avant d’enregistrer</strong></div><p>{resourceInfo(pending.resource).label} · <strong>{pending.sensor_id}</strong></p><div className="confirmation-metrics"><div><span>Dernière valeur</span><strong>{number(pending.preview.latest_value)} {pending.preview.unit}</strong></div><div><span>Seuil de la règle</span><strong>{number(pending.preview.threshold_value)} {pending.preview.unit}</strong></div></div><p>{pending.preview.interpretation}</p><p className="subtle">Données du {date(pending.preview.data_as_of)}. Confirmer enregistre cette analyse ; aucune tâche d’inspection n’est créée.</p>
                {item.resolution ? <div className="resolution" role="status"><Icon name="check" size={17} />{item.resolution.status === "confirmed" ? "Analyse enregistrée." : "Demande annulée, analyse non enregistrée."}</div> : <><p className="subtle">{deadlinePassed ? "Cette prévisualisation a expiré. Demandez une nouvelle analyse." : `À confirmer avant le ${date(pending.expires_at)}.`}</p><div className="button-row"><button disabled={busy || deadlinePassed} onClick={() => decide(item, "confirm")}><Icon name="check" size={17} /> Confirmer l’enregistrement</button><button className="secondary" disabled={busy || deadlinePassed} onClick={() => decide(item, "cancel")}>Annuler</button></div></>}
                {item.resolution?.status === "confirmed" && <button className="text-button" disabled={busy} onClick={() => { setSelection({ analysis_id: item.resolution.analysis_id }); setMessage("Explique cette analyse"); input.current?.focus(); }}>Comprendre cette analyse <Icon name="arrow" size={16} /></button>}
                {item.resolution?.status === "confirmed" && pending.preview.suggested_proposal && <div className="inspection-suggestion"><p><strong>Suggestion :</strong> {pending.preview.suggested_proposal.title}</p>{item.proposal ? <button className="secondary" disabled={busy} onClick={onActions}>Consulter la proposition dans Mes actions <Icon name="arrow" size={16} /></button> : <button className="secondary" disabled={busy} onClick={() => prepareProposal(item)}>Préparer une proposition d’inspection</button>}<p className="subtle">La proposition devra être approuvée avant la création d’une tâche.</p>{item.proposalError && <Message danger>{item.proposalError}</Message>}</div>}
                {item.confirmationError && <Message danger>{item.confirmationError}</Message>}
              </div>}
              {item.data?.limitations?.length > 0 && <details className="reply-details"><summary>Limites de cette analyse</summary><ul>{item.data.limitations.map(text => <li key={text}>{text}</li>)}</ul></details>}
              {item.data?.sources?.length > 0 && <details className="reply-details"><summary>{item.data.sources.length} source{item.data.sources.length > 1 ? "s" : ""} utilisée{item.data.sources.length > 1 ? "s" : ""}</summary><div className="source-list">{item.data.sources.map(source => <div key={source.reading_id}><strong>{number(source.value)} {source.unit}</strong><span>{date(source.measured_at)}</span><small>{source.data_source}</small></div>)}</div></details>}
              {item.data?.llm_status === "fallback" && <p className="subtle">Réponse de secours basée sur vos données.</p>}
            </>}
            {(item.traceId || item.decisionTraceId) && <details className="reply-details technical"><summary>Références de la demande</summary>{item.traceId && <p>Demande : <code>{item.traceId}</code></p>}{item.decisionTraceId && <p>Décision : <code>{item.decisionTraceId}</code></p>}</details>}
          </div></div>
        </article>;
      })}
      <div ref={bottom} />
    </div>
    <div className="composer-area">{problem && <Message danger>{problem}</Message>}{expired && <Message danger>Cette conversation a expiré. Ouvrez une nouvelle conversation pour continuer.</Message>}
      <div className="composer-context"><label htmlFor="chat-sensor">Compteur</label><select id="chat-sensor" disabled={busy} value={selection?.sensor_id ? JSON.stringify([selection.resource, selection.sensor_id]) : ""} onChange={e => setSelection(sensors.find(sensor => JSON.stringify([sensor.resource, sensor.sensor_id]) === e.target.value) || null)}><option value="">Automatique · selon votre demande</option>{sensors.map(sensor => <option key={`${sensor.resource}-${sensor.sensor_id}`} value={JSON.stringify([sensor.resource, sensor.sensor_id])}>{resourceInfo(sensor.resource).label} · {sensor.sensor_id}</option>)}</select>{selection?.analysis_id && <span className="soft-tag">Analyse sélectionnée</span>}</div>
      <form className="composer" onSubmit={send}><label className="sr-only" htmlFor="chat-message">Votre message</label><textarea id="chat-message" ref={input} rows={2} maxLength={1000} value={message} disabled={busy || expired} placeholder="Posez une question sur vos consommations…" onChange={e => setMessage(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); e.currentTarget.form.requestSubmit(); } }} /><button className="send-button" aria-label="Envoyer le message" disabled={busy || expired || !message.trim()}><Icon name="send" size={21} /></button></form>
      <div className="composer-foot"><span>Les opérations nécessitent votre confirmation manuelle.</span><span>{message.length}/1000</span></div><p className="local-history-note">Affichage conservé pendant cette session. Une nouvelle conversation ne supprime ni les analyses ni les demandes déjà préparées.</p>
    </div>
  </section>;
}
