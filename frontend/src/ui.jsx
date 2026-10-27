import React from "react";

const paths = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  drop: "M12 3C9 7 5 11 5 15a7 7 0 0 0 14 0c0-4-4-8-7-12z",
  bolt: "m13 2-9 12h7l-1 8 10-13h-7z",
  flame: "M12 3c2 5-2 6 1 9 2-1 3-3 3-4 6 7 4 13-4 13S1 14 7 8c0 4 2 5 3 5-2-5 2-6 2-10z",
  chat: "M21 11a9 9 0 0 1-9 9H5l-3 2V11a9 9 0 0 1 19 0z M7 11h.01 M12 11h.01 M17 11h.01",
  task: "M9 5H5v16h14V5h-4 M9 3h6v4H9z m-1 10 3 3 5-6",
  shield: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z m-4 9 3 3 5-6",
  refresh: "M20 7v5h-5 M4 17v-5h5 M6 6a8 8 0 0 1 14 6 M4 12a8 8 0 0 0 14 6",
  arrow: "M5 12h14 m-6-6 6 6-6 6",
  send: "m3 3 19 9-19 9 4-9z M7 12h15",
  plus: "M12 5v14 M5 12h14",
  logout: "M9 4H4v16h5 M9 12h12 m-5-5 5 5-5 5",
  menu: "M4 6h16 M4 12h16 M4 18h16",
  check: "m5 12 4 4L19 6",
  search: "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14z m5 12 6 6",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 7v5l3 2",
};
export function Icon({ name, size = 20 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.grid} /></svg>;
}
export const resources = {
  water: { label: "Eau", icon: "drop", color: "#1686af" },
  energy: { label: "Électricité", icon: "bolt", color: "#bb7b19" },
  gas: { label: "Gaz", icon: "flame", color: "#b65c42" },
};
export const resourceInfo = value => resources[value] || { label: value, icon: "grid", color: "#087f75" };
export const number = value => Number.isFinite(Number(value)) ? Number(value).toLocaleString("fr-FR", { maximumFractionDigits: 3 }) : "—";
export const date = value => value && Number.isFinite(new Date(value).getTime()) ? new Date(value).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "Non disponible";
export function Empty({ icon = "grid", title, children }) {
  return <div className="empty"><span className="empty-icon"><Icon name={icon} size={26} /></span><h3>{title}</h3><p>{children}</p></div>;
}
export function Message({ children, danger = false }) {
  return <div className={`message-banner ${danger ? "danger" : ""}`} role={danger ? "alert" : "status"}>{children}</div>;
}
