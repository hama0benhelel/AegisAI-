from app.agent_events import observed_agent_call
import json
import math
import os
import ssl
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPSHandler, HTTPRedirectHandler, ProxyHandler,
    Request, build_opener,
)
from uuid import UUID

from fastapi import HTTPException

from app.consumption_rules import RULE_VERSION


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def invalid_response():
    return HTTPException(502, "Réponse invalide de l’agent énergie")


@observed_agent_call("energy")
def analyze_energy(rows, user, request):
    # Endpoint fixed by the application, never supplied by the user.
    base = os.environ.get("ENERGY_AGENT_URL", "")
    if base != "https://energy-agent:8443":
        raise HTTPException(503, "Agent énergie non configuré")

    trace_id = str(UUID(request.state.trace_id))
    tenant_id = str(user["tenant_id"])

    if not rows:
        raise HTTPException(422, "Série de mesures vide")

    payload = {
        "operation": "analyze_consumption",
        "resource": "energy",
        "tenant_id": tenant_id,
        "requested_by": str(user["id"]),
        "trace_id": trace_id,
        "sensor_id": rows[-1]["sensor_id"],
        "rows": [
            {
                "id": str(row["id"]),
                "sensor_id": row["sensor_id"],
                "value": str(row["value"]),
                "unit": row["unit"],
                "measured_at": row["measured_at"].isoformat(),
                "data_source": row["data_source"],
                "interval_seconds": row["interval_seconds"],
            }
            for row in rows
        ],
    }

    try:
        context = ssl.create_default_context(
            cafile=os.environ["AGENT_CA_FILE"]
        )
        context.load_cert_chain(
            os.environ["AGENT_CERT_FILE"],
            os.environ["AGENT_KEY_FILE"],
        )
        opener = build_opener(
            ProxyHandler({}),
            HTTPSHandler(context=context),
            NoRedirect(),
        )
        outgoing = Request(
            base + "/internal/analyze",
            data=json.dumps(payload, allow_nan=False).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with opener.open(outgoing, timeout=5) as response:
            if response.status != 200:
                raise invalid_response()
            raw = response.read(65537)
            if len(raw) > 65536:
                raise invalid_response()

    except HTTPError as error:
        if error.code == 422:
            raise HTTPException(
                422, "Série de mesures refusée par l’agent énergie"
            ) from None
        raise HTTPException(503, "Agent énergie indisponible") from None
    except (URLError, OSError, KeyError):
        raise HTTPException(503, "Connexion sécurisée à l’agent énergie indisponible") from None

    try:
        envelope = json.loads(raw)
        if set(envelope) != {"tenant_id", "trace_id", "result"}:
            raise ValueError()
        if envelope["tenant_id"] != tenant_id:
            raise ValueError()
        if envelope["trace_id"] != trace_id:
            raise ValueError()

        result = envelope["result"]
        expected_keys = {
            "agent", "rule_version", "sensor_id", "data_as_of",
            "measurement_kind", "unit", "sample_count",
            "baseline_mean", "latest_value", "threshold_multiplier",
            "threshold_value", "ratio_to_baseline", "classification",
            "confidence_probability", "interpretation", "limitations",
            "sources", "suggested_proposal",
        }
        if set(result) != expected_keys:
            raise ValueError()

        latest = rows[-1]
        if (
            result["agent"] != "energy"
            or result["rule_version"] != RULE_VERSION
            or result["sensor_id"] != latest["sensor_id"]
            or result["unit"] != "kWh"
            or result["measurement_kind"] != "consumption_per_hour"
            or result["sample_count"] != 24
            or result["confidence_probability"] is not None
            or datetime.fromisoformat(result["data_as_of"]) != latest["measured_at"]
        ):
            raise ValueError()

        baseline = float(sum(row["value"] for row in rows[:-1]) / 23)
        latest_value = float(latest["value"])
        if baseline <= 0:
            raise ValueError()

        expected_numbers = {
            "baseline_mean": baseline,
            "latest_value": latest_value,
            "threshold_multiplier": 2.0,
            "threshold_value": baseline * 2,
            "ratio_to_baseline": latest_value / baseline,
        }
        for key, expected in expected_numbers.items():
            value = result[key]
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not math.isclose(value, expected, rel_tol=1e-9, abs_tol=1e-9)
            ):
                raise ValueError()

        anomalous = latest_value > baseline * 2
        if result["classification"] != (
            "high_consumption" if anomalous else "normal"
        ):
            raise ValueError()

        sources = result["sources"]
        if not isinstance(sources, list) or len(sources) != len(rows):
            raise ValueError()

        for source, row in zip(sources, rows):
            expected = {
                "reading_id": str(row["id"]),
                "measured_at": row["measured_at"].isoformat(),
                "value": float(row["value"]),
                "unit": row["unit"],
                "interval_seconds": row["interval_seconds"],
                "data_source": row["data_source"],
            }
            if source != expected:
                raise ValueError()

        expected_proposal = {
            "action_type": "create_inspection_task",
            "sensor_id": latest["sensor_id"],
            "title": f"Vérifier la consommation du capteur {latest['sensor_id']}",
        } if anomalous else None
        if result["suggested_proposal"] != expected_proposal:
            raise ValueError()

        expected_interpretation = (
            "La dernière heure dépasse deux fois la moyenne des 23 précédentes."
            if anomalous else
            "La dernière heure ne dépasse pas le seuil de cette règle."
        )
        if result["interpretation"] != expected_interpretation:
            raise ValueError()
        if result["limitations"] != [
            "Règle non calibrée sur des données industrielles.",
            "Aucune cause racine confirmée.",
            "Résultat valable à la date des données, pas une mesure en temps réel.",
        ]:
            raise ValueError()

    except (ValueError, TypeError, KeyError, OverflowError):
        raise invalid_response() from None

    return result
