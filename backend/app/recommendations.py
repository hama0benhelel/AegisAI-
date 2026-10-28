"""General resource guidance, without LLM generation or operational write access."""
from decimal import Decimal
from fastapi import HTTPException
from app.db import connect, set_tenant
from app.knowledge_base import VERSION, guidance

LIMITATIONS = [
    "Conseils généraux sélectionnés selon la ressource, sans connaissance de vos équipements ni de votre logement.",
    "La mesure sert de repère ; elle ne confirme ni cause de surconsommation ni fuite.",
    "Aucune économie chiffrée, aucun diagnostic et aucun score de confiance calibré ne sont disponibles.",
    "Aucun appareil n’est commandé ; toute opération métier garde son workflow de confirmation.",
]


def advice_for(user, sensor_id, resource):
    if user["role"] not in {"client", "viewer", "operator", "tenant_admin"}:
        raise HTTPException(403, "Permissions insuffisantes")
    units = {"water": "m3", "energy": "kWh", "gas": "m3"}
    if resource not in units:
        raise HTTPException(422, "Ressource non prise en charge")
    with connect() as conn:
        set_tenant(conn, user["tenant_id"])
        row = conn.execute(
            """SELECT id, sensor_id, resource, value, unit, measured_at,
                      data_source, interval_seconds
               FROM bws_ai.readings
               WHERE tenant_id = %s AND sensor_id = %s AND resource = %s
                 AND interval_seconds = 3600 AND measured_at <= now()
               ORDER BY measured_at DESC, id DESC LIMIT 1""",
            (user["tenant_id"], sensor_id, resource),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Aucune mesure horaire accessible")
    value = Decimal(str(row["value"]))
    if not value.is_finite() or value < 0 or row["unit"] != units[resource]:
        raise HTTPException(422, "Mesure incohérente")
    tips, knowledge_sources = guidance(resource)
    amount = format(value, "f").replace(".", ",")
    text = (
        f"Repère pour {row['sensor_id']} : dernière mesure horaire de {amount} "
        f"{row['unit']}, le {row['measured_at'].isoformat()}. "
        "Voici des conseils généraux à adapter à vos usages ; cette mesure seule ne permet pas de diagnostiquer un gaspillage."
    )
    return {
        "answer": text, "recommendations": tips, "knowledge_sources": knowledge_sources,
        "knowledge_version": VERSION, "knowledge_scope": "general_resource_guidance",
        "sensor_id": row["sensor_id"], "resource": row["resource"],
        "data_as_of": row["measured_at"].isoformat(), "limitations": LIMITATIONS,
        "needs_confirmation": False, "analysis_created": False, "proposal_created": False,
        "task_created": False, "reliability_percentage": None,
        "sources": [{"reading_id": str(row["id"]), "sensor_id": row["sensor_id"],
                     "value": float(value), "unit": row["unit"],
                     "measured_at": row["measured_at"].isoformat(),
                     "data_source": row["data_source"], "interval_seconds": row["interval_seconds"]}],
    }
