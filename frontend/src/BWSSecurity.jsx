import React, { useEffect, useRef, useState } from "react";
import { Icon, Empty, Message, date, number } from "./ui.jsx";

export default function BWSSecurity({ api, session, mode, active, busy, setBusy, onExpired }) {
  const [rows, setRows] = useState([]);
  const [tenant, setTenant] = useState("");
  const [trace, setTrace] = useState("");
  const [problem, setProblem] = useState("");
  const [loaded, setLoaded] = useState(false);
  const inFlight = useRef(false);
  const llm = mode === "llm";
  async function load(event) {
    event?.preventDefault();
    if (inFlight.current) return;
    const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if ([tenant.trim(), trace.trim()].some(value => value && !uuid.test(value))) { setProblem("Les filtres organisation et trace doivent être des UUID valides."); return; }
    inFlight.current = true; setBusy(true); setProblem("");
    try {
      const query = new URLSearchParams({ limit: "100" });
      if (tenant.trim()) query.set("tenant_id", tenant.trim());
      if (trace.trim()) query.set("trace_id", trace.trim());
      const data = await api(`/bws/security/${llm ? "llm-calls" : "audit"}?${query}`, { token: session.token });
      setRows(data.items); setLoaded(true);
    } catch (error) { if (error.status === 401) onExpired(); else setProblem(error.message); }
    finally { inFlight.current = false; setBusy(false); }
  }
  useEffect(() => { if (active) load(); }, [active, session.token]);
  const suspicious = rows.filter(row => row.event_type === "prompt_injection_suspected").length;
  const denied = rows.filter(row => row.status_code === 401 || row.status_code === 403).length;
  const tokens = rows.reduce((sum, row) => sum + (row.total_tokens ?? 0), 0);
  return <div className="page-stack"><div className="security-note"><Icon name="shield" size={24} /><div><strong>Supervision BWS · métadonnées uniquement</strong><p>Cet espace ne donne accès ni aux consommations des clients, ni au contenu des prompts ou des réponses LLM.</p></div></div>
    <form className="panel security-filters" onSubmit={load}><label>Organisation — UUID facultatif<input value={tenant} onChange={e => setTenant(e.target.value)} placeholder="Toutes les organisations" disabled={busy} /></label><label>Trace — UUID facultatif<input value={trace} onChange={e => setTrace(e.target.value)} placeholder="Retrouver une requête" disabled={busy} /></label><button disabled={busy}><Icon name="search" size={17} /> Rechercher</button></form>
    {problem && <Message danger>{problem}</Message>}
    <div className="security-stats"><article><span>Lignes retournées</span><strong>{loaded ? rows.length : "—"}</strong></article><article><span>{llm ? "Tokens connus dans ces lignes" : "Tentatives suspectes dans ces lignes"}</span><strong>{loaded ? number(llm ? tokens : suspicious) : "—"}</strong></article><article><span>{llm ? "Appels de secours dans ces lignes" : "Réponses 401 / 403 dans ces lignes"}</span><strong>{loaded ? (llm ? rows.filter(row => row.status === "fallback").length : denied) : "—"}</strong></article></div>
    <section className="panel"><div className="panel-heading"><div><h2>{llm ? "Journal des appels LLM" : "Événements de sécurité"}</h2><p>100 lignes maximum. Les indicateurs portent sur les résultats affichés, sans mesure globale du risque.</p></div><button className="secondary" disabled={busy} onClick={() => load()}><Icon name="refresh" size={16} /> Actualiser</button></div><div className="table-wrap"><table><thead><tr><th>Date</th><th>{llm ? "Opération / modèle" : "Événement"}</th><th>{llm ? "Statut" : "HTTP"}</th><th>{llm ? "Tokens" : "Route"}</th><th>Organisation et trace</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td>{date(row.created_at || row.occurred_at)}</td><td><strong>{llm ? row.operation : row.event_type}</strong>{llm && <small className="cell-note">{row.model}</small>}</td><td><span className={`status-tag ${(!llm && row.status_code >= 400) || (llm && row.status === "fallback") ? "pending" : "executed"}`}>{llm ? row.status : row.status_code}</span></td><td>{llm ? (row.total_tokens ?? "Non communiqué") : row.route}</td><td><details><summary>Références</summary><p>Organisation : <code>{row.tenant_id || "Anonyme"}</code></p><p>Utilisateur : <code>{row.user_id || "Non identifié"}</code></p><p>Trace : <code>{row.trace_id}</code></p>{llm && <p>Motif : {row.reason || "—"}</p>}</details></td></tr>)}</tbody></table></div>{loaded && !rows.length && <Empty icon="search" title="Aucun résultat">Aucun événement ne correspond aux filtres appliqués.</Empty>}</section>
  </div>;
}
