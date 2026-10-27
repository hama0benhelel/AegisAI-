from datetime import timedelta
from decimal import Decimal
from fastapi import HTTPException

RULE_VERSION = "hourly-baseline-v1"
MULTIPLIER = Decimal("2")


def analyze(resource, rows):
    if len(rows) != 24:
        raise HTTPException(422, "24 mesures horaires sont nécessaires")

    expected_unit = "m3" if resource == "water" else "kWh"
    if any(row["unit"] != expected_unit for row in rows):
        raise HTTPException(422, "Unités incohérentes")

    for previous, current in zip(rows, rows[1:]):
        if current["measured_at"] - previous["measured_at"] != timedelta(hours=1):
            raise HTTPException(422, "La série doit contenir 24 heures consécutives")

    baseline = sum(row["value"] for row in rows[:-1]) / Decimal(23)
    if baseline <= 0:
        raise HTTPException(422, "Référence nulle: règle non applicable")

    latest = rows[-1]
    threshold = baseline * MULTIPLIER
    anomalous = latest["value"] > threshold

    suggestion = None
    if anomalous:
        suggestion = {
            "action_type": "create_inspection_task",
            "sensor_id": latest["sensor_id"],
            "title": f"Vérifier la consommation du capteur {latest['sensor_id']}",
        }

    return {
        "agent": resource,
        "rule_version": RULE_VERSION,
        "sensor_id": latest["sensor_id"],
        "data_as_of": latest["measured_at"].isoformat(),
        "measurement_kind": "consumption_per_hour",
        "unit": expected_unit,
        "sample_count": len(rows),
        "baseline_mean": float(baseline),
        "latest_value": float(latest["value"]),
        "threshold_multiplier": float(MULTIPLIER),
        "threshold_value": float(threshold),
        "ratio_to_baseline": float(latest["value"] / baseline),
        "classification": "high_consumption" if anomalous else "normal",
        "confidence_probability": None,
        "interpretation": (
            "La dernière heure dépasse deux fois la moyenne des 23 précédentes."
            if anomalous else
            "La dernière heure ne dépasse pas le seuil de cette règle."
        ),
        "limitations": [
            "Règle non calibrée sur des données industrielles.",
            "Aucune cause racine confirmée.",
            "Résultat valable à la date des données, pas une mesure en temps réel.",
        ],
        "sources": [
            {
                "reading_id": str(row["id"]),
                "measured_at": row["measured_at"].isoformat(),
                "value": float(row["value"]),
                "unit": row["unit"],
                "interval_seconds": row["interval_seconds"],
                "data_source": row["data_source"],
            }
            for row in rows
        ],
        "suggested_proposal": suggestion,
    }
