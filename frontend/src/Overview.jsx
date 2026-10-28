import React, { useState } from "react";
import { Icon, Empty, resourceInfo, resources, sensorKind, sensorKinds, SensorOptions, number, date } from "./ui.jsx";

export function sensorGroups(readings) {
  const groups = new Map();
  for (const row of readings) {
    if (row.value === null || row.value === undefined || row.value === "" || Number(row.value) < 0 || !Number.isFinite(Number(row.value)) || !Number.isFinite(new Date(row.measured_at).getTime())) continue;
    const key = JSON.stringify([row.resource, row.sensor_id, row.unit]);
    if (!groups.has(key)) groups.set(key, { key, resource: row.resource, sensor_id: row.sensor_id, unit: row.unit, rows: [] });
    groups.get(key).rows.push(row);
  }
  return [...groups.values()].map(group => ({ ...group, rows: group.rows.sort((a, b) => new Date(a.measured_at) - new Date(b.measured_at)) }))
    .sort((a, b) => {
      const order = { simulation: 0, initial: 1, other: 2 };
      return order[sensorKind(a)] - order[sensorKind(b)] || a.resource.localeCompare(b.resource) || a.sensor_id.localeCompare(b.sensor_id);
    });
}
function Curve({ group, compact = false }) {
  const points = group.rows.slice(-24);
  if (points.length < 2) return <p className="subtle">Pas assez de mesures pour tracer une courbe.</p>;
  const start = new Date(points[0].measured_at).getTime();
  const end = new Date(points.at(-1).measured_at).getTime();
  if (start === end) return <p className="subtle">Mesures sans période distincte.</p>;
  const max = Math.max(...points.map(row => Number(row.value)));
  const scale = max > 0 ? max : 1;
  const width = 600, height = compact ? 90 : 200;
  const coords = points.map(row => [14 + (new Date(row.measured_at) - start) / (end - start) * (width - 28), height - 14 - Number(row.value) / scale * (height - 30)]);
  const stroke = resourceInfo(group.resource).color;
  return <div className={compact ? "curve compact" : "curve"}>
    {!compact && <div className="curve-scale"><span>{number(max)} {group.unit}</span><span>Mesures enregistrées</span></div>}
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Évolution des mesures de ${group.sensor_id}`}>
      {!compact && [0.25, 0.5, 0.75, 1].map(n => <line key={n} x1="14" y1={(height - 20) * n} x2={width - 14} y2={(height - 20) * n} stroke="#e8eeed" strokeDasharray="4 5" />)}
      <polyline points={coords.map(p => p.join(",")).join(" ")} stroke={stroke} strokeWidth={compact ? 3 : 2.5} fill="none" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
      {coords.map(([x, y], index) => <circle key={points[index].id} cx={x} cy={y} r={compact ? 2 : 3.5} fill={stroke}><title>{date(points[index].measured_at)} : {number(points[index].value)} {group.unit}</title></circle>)}
    </svg>
    {!compact && <div className="curve-scale"><span>{date(points[0].measured_at)}</span><span>{date(points.at(-1).measured_at)}</span></div>}
  </div>;
}
function MeterFilters({ groups, resource, setResource, kind, setKind, id }) {
  return <div className="meter-filters">
    <div className="resource-filters" role="group" aria-label="Filtrer par ressource">
      <button className={resource === "all" ? "selected" : ""} aria-pressed={resource === "all"} onClick={() => setResource("all")}>Tout <span>{groups.length}</span></button>
      {Object.entries(resources).filter(([key]) => groups.some(group => group.resource === key)).map(([key, info]) =>
        <button key={key} className={resource === key ? `selected ${key}` : key} aria-pressed={resource === key} onClick={() => setResource(key)}><Icon name={info.icon} size={16} />{info.label}<span>{groups.filter(group => group.resource === key).length}</span></button>
      )}
    </div>
    <div className="kind-filter"><label htmlFor={id}>Groupe de compteurs</label><select id={id} value={kind} onChange={event => setKind(event.target.value)}>
      <option value="all">Tous les compteurs chargés</option>
      {Object.entries(sensorKinds).filter(([key]) => groups.some(group => sensorKind(group) === key)).map(([key, info]) => <option key={key} value={key}>{info.label}</option>)}
    </select></div>
  </div>;
}
function filterGroups(groups, resource, kind) {
  return groups.filter(group => (resource === "all" || group.resource === resource) && (kind === "all" || sensorKind(group) === kind));
}
function GroupBadge({ sensor }) {
  const kind = sensorKind(sensor);
  return <span className={`dataset-tag ${kind}`} title={sensorKinds[kind].description}>{sensorKinds[kind].short}</span>;
}
export default function Overview({ readings, onAssistant, busy }) {
  const groups = sensorGroups(readings);
  const [selected, setSelected] = useState("");
  const [resource, setResource] = useState("all");
  const [kind, setKind] = useState("all");
  const visible = filterGroups(groups, resource, kind);
  const group = visible.find(item => item.key === selected) || visible[0];
  return <div className="page-stack">
    <section className="welcome-panel"><div><span className="eyebrow">VOTRE ESPACE CONSOMMATION</span><h2>Comprendre vos usages.<br /><span>Décider en toute confiance.</span></h2><p>Eau, électricité, gaz : retrouvez les compteurs présents dans vos mesures et échangez avec votre assistant.</p><button onClick={() => onAssistant()} disabled={busy}>Parler à mon assistant <Icon name="arrow" size={17} /></button></div><div className="welcome-art" aria-hidden="true"><div className="art-ring ring-one" /><div className="art-ring ring-two" /><div className="art-center"><Icon name="shield" size={48} /></div><span className="art-node node-water"><Icon name="drop" size={27} /></span><span className="art-node node-energy"><Icon name="bolt" size={27} /></span><span className="art-node node-gas"><Icon name="flame" size={27} /></span></div></section>
    <div className="section-heading"><div><h2>Mes consommations</h2><p>Dernière valeur chargée par compteur. Les ressources restent séparées, même lorsqu’elles ont la même unité.</p></div><span className="soft-tag">{visible.length} / {groups.length} compteurs chargés</span></div>
    {!!groups.length && <MeterFilters groups={groups} resource={resource} setResource={setResource} kind={kind} setKind={setKind} id="overview-kind" />}
    {!visible.length && <Empty title={groups.length ? "Aucun compteur pour ces filtres" : "Vos mesures apparaîtront ici"}>{groups.length ? "Choisissez une autre ressource ou un autre groupe de compteurs." : "Aucune mesure n’a été retournée pour votre compte."}</Empty>}
    <section className="meter-grid">{visible.map(item => { const info = resourceInfo(item.resource), latest = item.rows.at(-1); return <article className={`meter-card ${item.resource}`} key={item.key} aria-label={`${info.label} · ${item.sensor_id}`}><div className="meter-top"><span className="resource-icon"><Icon name={info.icon} size={23} /></span><span className={`resource-tag ${item.resource}`}>{info.label}</span></div><GroupBadge sensor={item} /><h3>{item.sensor_id}</h3><p className="meter-value">{number(latest.value)} <span>{latest.unit}</span></p><p className="subtle">Mesure du {date(latest.measured_at)}</p><Curve group={item} compact /><button className="text-button" disabled={busy} onClick={() => onAssistant(item)}>Consulter avec l’assistant <Icon name="arrow" size={16} /></button></article>; })}</section>
    {group && <section className="panel"><div className="panel-heading"><div><span className="eyebrow">HISTORIQUE</span><h2>L’évolution de vos mesures</h2></div><label className="sr-only" htmlFor="trend-sensor">Compteur du graphique</label><select id="trend-sensor" value={group.key} onChange={event => setSelected(event.target.value)}><SensorOptions sensors={visible} valueOf={item => item.key} /></select></div><div className="chart-body"><Curve group={group} /><p className="subtle chart-note">Jusqu’à 24 points issus des résultats chargés, en Africa/Tunis. Ces mesures ne constituent pas un suivi en temps réel.</p></div></section>}
    <p className="subtle dataset-explanation"><strong>Simulation horaire :</strong> mesures synthétiques générées pour les heures terminées. <strong>Démo initiale :</strong> jeu fixe de test, dont les dates peuvent être anciennes. L’affichage est limité aux mesures retournées par le serveur.</p>
  </div>;
}
export function Meters({ readings }) {
  const [filter, setFilter] = useState("all");
  const [resource, setResource] = useState("all");
  const [kind, setKind] = useState("all");
  const groups = sensorGroups(readings);
  const choices = filterGroups(groups, resource, kind);
  const selected = choices.some(group => group.key === filter) ? filter : "all";
  const keys = new Set(choices.map(group => group.key));
  const visible = readings.filter(row => {
    const key = JSON.stringify([row.resource, row.sensor_id, row.unit]);
    return keys.has(key) && (selected === "all" || key === selected);
  });
  return <div className="page-stack"><MeterFilters groups={groups} resource={resource} setResource={setResource} kind={kind} setKind={setKind} id="meters-kind" /><section className="panel"><div className="panel-heading"><div><h2>Historique des compteurs</h2><p>{visible.length} mesure(s) affichée(s), sur un maximum de 100 résultats. Dates en Africa/Tunis.</p></div><label className="sr-only" htmlFor="meter-filter">Filtrer par compteur</label><select id="meter-filter" value={selected} onChange={e => setFilter(e.target.value)}><option value="all">Tous les compteurs filtrés</option><SensorOptions sensors={choices} valueOf={item => item.key} /></select></div><div className="table-wrap"><table><thead><tr><th>Compteur</th><th>Ressource</th><th>Valeur enregistrée</th><th>Date de mesure</th></tr></thead><tbody>{visible.map(row => <tr key={row.id}><td><strong>{row.sensor_id}</strong><span className="cell-note">{sensorKinds[sensorKind(row)].label}</span></td><td><span className={`resource-tag ${row.resource}`}>{resourceInfo(row.resource).label}</span></td><td>{number(row.value)} <span className="subtle">{row.unit}</span></td><td>{date(row.measured_at)}</td></tr>)}</tbody></table></div>{!visible.length && <Empty title="Aucune mesure">Essayez un autre filtre ou actualisez les résultats.</Empty>}</section></div>;
}
