import re
import unicodedata

GATE_VERSION = "rules-fr-en-v1"

TAXONOMY = {
    "q_and_a",
    "configuration",
    "navigation",
    "anomaly_follow_up",
    "recommendation_request",
    "action_plan_update",
}

SUSPICIOUS = [
    r"\b(ignore|oublie|oubliez|ignorer|disregard)\b.{0,80}\b(instructions|rules|regles)\b",
    r"\b(system prompt|prompt systeme|jwt_secret|app_db_password)\b",
    r"\b(you are now|tu es maintenant)\b",
    r"\b(bypass|contourne)\b.{0,60}\b(approval|approbation|validation|security|securite)\b",
]

WRITE_REQUEST = (
    r"\b(execute|executer|approuve|approuver|approve|delete|"
    r"supprime|supprimer|active|activate)\b"
)


def normalize(message):
    text = unicodedata.normalize("NFKC", message).casefold()
    text = "".join(
        ch for ch in text if unicodedata.category(ch) != "Cf"
    )
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )
    return " ".join(text.split())


def classify(message):
    text = normalize(message)

    if any(re.search(pattern, text) for pattern in SUSPICIOUS):
        return {
            "decision": "reject",
            "intent": None,
            "reason": "suspicious_instruction",
        }

    if re.search(WRITE_REQUEST, text):
        return {
            "decision": "reject",
            "intent": "action_plan_update",
            "reason": "write_action_not_available_in_chat",
        }

    if re.search(r"\b(configure|configuration|parametrage)\b", text):
        return {
            "decision": "reject",
            "intent": "configuration",
            "reason": "intent_not_enabled",
        }

    if re.search(r"\b(navigue|navigate|navigation)\b", text):
        return {
            "decision": "reject",
            "intent": "navigation",
            "reason": "intent_not_enabled",
        }

    # Deliberately narrow grammar for the first demonstrator.
    if re.match(r"^(explique|explain)\b", text):
        intent = "anomaly_follow_up"
    elif re.match(r"^(analyse|analyze|recommande|recommend)\b", text):
        intent = "recommendation_request"
    elif re.match(r"^(affiche|show)\b", text):
        intent = "q_and_a"
    else:
        return {
            "decision": "reject",
            "intent": None,
            "reason": "out_of_scope_or_unrecognized",
        }

    return {"decision": "allow", "intent": intent, "reason": None}
