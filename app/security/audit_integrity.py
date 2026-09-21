
import hashlib
import json

def canonical_event(event: dict) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), default=str)

def event_hash(event: dict, previous_hash: str = "") -> str:
    payload = previous_hash + canonical_event(event)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
