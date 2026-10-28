"""Curated read-only data. Its trust anchor is code, never a user-provided digest."""
import hashlib
import json
from pathlib import Path

VERSION = "curated-consumption-advice-v1"
EXPECTED_SHA256 = "683e7c408115a86e4ce0027e658c4706abbc96c49e93d4a957f9929fc3dceee0"
CATALOG_PATH = Path(__file__).parent / "knowledge" / "consumption_advice_v1.json"
TIP_IDS = {
    "water": ("water-shower", "water-dishes"),
    "energy": ("energy-lighting", "energy-eco"),
    "gas": ("gas-hot-water", "gas-heating"),
}
SOURCE_URLS = {
    "ademe-water": "https://agirpourlatransition.ademe.fr/particuliers/economiser/eau/conseils-economie-eau-maison",
    "ademe-energy": "https://agirpourlatransition.ademe.fr/particuliers/economiser/energie/20-solutions-reduire-consommation-electricite",
    "ademe-heating": "https://agirpourlatransition.ademe.fr/particuliers/amenager-maison/chauffer/bons-gestes-chauffage-plus-economique",
}

class KnowledgeIntegrityError(Exception):
    pass


def load_catalog():
    try:
        raw = CATALOG_PATH.read_bytes()
        if len(raw) > 16000 or hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256:
            raise KnowledgeIntegrityError()
        data = json.loads(raw)
        if set(data) != {"version", "reviewed_at", "sources", "tips"} or data["version"] != VERSION:
            raise KnowledgeIntegrityError()
        if set(data["sources"]) != set(SOURCE_URLS):
            raise KnowledgeIntegrityError()
        for source_id, url in SOURCE_URLS.items():
            source = data["sources"][source_id]
            if set(source) != {"title", "publisher", "url"} or source["url"] != url or source["publisher"] != "ADEME":
                raise KnowledgeIntegrityError()
        ids = {tip["id"] for tip in data["tips"]}
        if len(data["tips"]) != 6 or ids != {item for items in TIP_IDS.values() for item in items}:
            raise KnowledgeIntegrityError()
        for tip in data["tips"]:
            if set(tip) != {"id", "resource", "title", "condition", "text", "source_id"}:
                raise KnowledgeIntegrityError()
            if tip["id"] not in TIP_IDS[tip["resource"]] or tip["source_id"] not in SOURCE_URLS:
                raise KnowledgeIntegrityError()
            if any(not isinstance(tip[k], str) or not 1 <= len(tip[k]) <= 500 for k in tip):
                raise KnowledgeIntegrityError()
        return data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise KnowledgeIntegrityError() from exc


def guidance(resource):
    catalog = load_catalog()
    if resource not in TIP_IDS:
        raise ValueError("Unsupported resource")
    by_id = {tip["id"]: tip for tip in catalog["tips"]}
    tips = [by_id[item] for item in TIP_IDS[resource]]
    source_ids = sorted({tip["source_id"] for tip in tips})
    return tips, [{"source_id": item, **catalog["sources"][item], "reviewed_at": catalog["reviewed_at"]} for item in source_ids]
