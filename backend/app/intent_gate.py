import re

from app.intent_gate_v2 import (
    TAXONOMY,
    normalize,
    classify as classify_v2,
)

GATE_VERSION = "conversational-fr-en-gas-v4"

DIALOGUE = {
    "greeting": [
        r"(?:bonjour|bonsoir|salut|hello|hi|salam|asslema|aslema|ahla)"
        r"(?:\s+(?:aegisai|maallem|maalem))?",
    ],
    "thanks": [
        r"(?:merci|merci beaucoup|thanks|thank you|3aychek|y3aychek)",
    ],
    "help": [
        r"(?:aide|help)",
        r"que peux[- ]tu faire",
        r"comment peux[- ]tu m'aider",
        r"quelles sont tes fonctionnalites",
        r"what can you do",
        r"kifech tnajem t3aweni",
    ],
}

RESOURCE = r"(?:d'eau|d'energie|de gaz|electrique|en eau|en energie|en gaz)"

NATURAL = {
    "q_and_a": [
        r"(?:affiche|afficher|montre|montrer|consulte|consulter) (?:la |les )?(?:consommation|mesures?|releves?|valeurs?) (?:de gaz|en gaz)",
        r"(?:show|display|read) (?:the )?(?:(?:latest|last|hourly) )?gas (?:readings?|measurements?|consumption)",
        rf"quelle est (?:ma|la) consommation(?:\s+{RESOURCE})?",
        rf"(?:montre[- ]moi|donne[- ]moi) (?:ma|la) consommation(?:\s+{RESOURCE})?",
        r"quelle est la derniere mesure(?: disponible)?",
        r"(?:et\s+)?pour (?:l'eau|l'energie|le gaz|water|energy|gas)",
        r"what is my (?:water|energy|gas) consumption",
    ],
    "anomaly_follow_up": [
        r"aide[- ]moi a comprendre cette analyse",
        r"peux[- ]tu m'expliquer cette analyse",
        r"pourquoi ma consommation est[- ]elle elevee",
    ],
    "recommendation_request": [
        r"(?:analyze|analyse) (?:the )?gas consumption",
        rf"je voudrais analyser (?:ma|la) consommation(?:\s+{RESOURCE})?",
        rf"analyse (?:ma|la) consommation(?:\s+{RESOURCE})?",
        r"je voudrais une recommandation pour ce compteur",
        r"peux[- ]tu analyser ma consommation",
    ],
}


def allowed(intent, text, dialogue_act=None):
    result = {
        "decision": "allow",
        "intent": intent,
        "reason": None,
    }
    if dialogue_act:
        result["dialogue_act"] = dialogue_act

    water = bool(re.search(r"\b(?:eau|water)\b", text))
    energy = bool(re.search(r"\b(?:energie|energy|electrique)\b", text))

    gas = bool(re.search(r"\b(?:gaz|gas)\b", text))
    matched = [name for name, present in (("water", water), ("energy", energy), ("gas", gas)) if present]
    if len(matched) == 1:
        result["resource_hint"] = matched[0]
    return result


def classify(message):
    original = classify_v2(message)

    # Keep existing security and disabled-function decisions.
    if original["decision"] == "reject":
        if original["reason"] != "out_of_scope_or_unrecognized":
            return original
    else:
        return allowed(original["intent"], normalize(message))

    text = normalize(message).rstrip(" .?!")

    for act, patterns in DIALOGUE.items():
        if any(re.fullmatch(pattern, text) for pattern in patterns):
            return allowed("q_and_a", text, dialogue_act=act)

    candidate = re.sub(
        r"^(?:bonjour|bonsoir|salut|hello|salam)[ ,!:]+",
        "",
        text,
        count=1,
    )
    candidate = re.sub(
        r"^(?:s'il vous plait|s'il te plait|veuillez|please)[ ,:]+",
        "",
        candidate,
        count=1,
    )

    legacy = classify_v2(candidate)
    if legacy["decision"] == "allow":
        return allowed(legacy["intent"], candidate)
    if legacy["reason"] != "out_of_scope_or_unrecognized":
        return legacy

    for intent, patterns in NATURAL.items():
        if any(re.fullmatch(pattern, candidate) for pattern in patterns):
            return allowed(intent, candidate)

    return original
