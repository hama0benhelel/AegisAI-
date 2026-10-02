import re
import unicodedata

GATE_VERSION = "bounded-grammar-fr-en-v2"

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

POLITE_PREFIX = re.compile(
    r"^(?:please|can you|could you|"
    r"peux[- ]tu|pouvez[- ]vous|"
    r"s'il te plait|s'il vous plait)\s+"
)

PATTERNS = {
    "q_and_a": [
        # Ex.: Affiche la consommation / Montre les dernières mesures
        r"(?:affiche|afficher|montre|montrer|consulte|consulter)\s+"
        r"(?:(?:la|le|les|une|un|des)\s+)?"
        r"(?:(?:derniere|dernier|dernieres|derniers)\s+)?"
        r"(?:consommation|mesures?|releves?|valeurs?)"
        r"(?:\s+horaires?)?"
        r"(?:\s+(?:d'eau|d'energie|en eau|en energie))?",

        # Ex.: Show the latest water reading
        r"(?:show|display|read)\s+"
        r"(?:the\s+)?(?:(?:latest|last|hourly)\s+)?"
        r"(?:(?:water|energy)\s+)?"
        r"(?:readings?|measurements?|consumption)",
    ],
    "anomaly_follow_up": [
        r"(?:explique|expliquer)\s+(?:cette|la)\s+(?:analyse|anomalie)",
        r"(?:explain|describe)\s+(?:this|the)\s+(?:analysis|anomaly)",
        r"pourquoi\s+cette\s+anomalie(?:\s+a ete detectee)?",
        r"why\s+was\s+this\s+anomaly\s+detected",
    ],
    "recommendation_request": [
        r"(?:analyse|analyser)\s+(?:la\s+)?consommation"
        r"(?:\s+(?:d'eau|d'energie|en eau|en energie))?",

        r"(?:analyze|analyse)\s+(?:the\s+)?"
        r"(?:(?:water|energy)\s+)?consumption",

        r"(?:recommande|recommander)\s+(?:une\s+)?inspection"
        r"(?:\s+si necessaire)?",

        r"recommend\s+(?:an?\s+)?inspection(?:\s+if needed)?",
    ],
}


def normalize(message):
    text = unicodedata.normalize("NFKC", message).casefold()
    text = text.replace("’", "'")
    text = "".join(
        ch for ch in text if unicodedata.category(ch) != "Cf"
    )
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )
    return " ".join(text.split())


def rejection(reason, intent=None):
    return {"decision": "reject", "intent": intent, "reason": reason}


def classify(message):
    text = normalize(message)

    if any(re.search(pattern, text) for pattern in SUSPICIOUS):
        return rejection("suspicious_instruction")

    if re.search(WRITE_REQUEST, text):
        return rejection(
            "write_action_not_available_in_chat", "action_plan_update"
        )

    if re.search(r"\b(configure|configuration|parametrage)\b", text):
        return rejection("intent_not_enabled", "configuration")

    if re.search(r"\b(navigue|navigate|navigation)\b", text):
        return rejection("intent_not_enabled", "navigation")

    # Remove only supported polite prefixes and final punctuation.
    candidate = text.rstrip(" .?!")
    for _ in range(3):
        updated = POLITE_PREFIX.sub("", candidate, count=1)
        if updated == candidate:
            break
        candidate = updated

    for intent, patterns in PATTERNS.items():
        if any(re.fullmatch(pattern, candidate) for pattern in patterns):
            return {"decision": "allow", "intent": intent, "reason": None}

    return rejection("out_of_scope_or_unrecognized")
