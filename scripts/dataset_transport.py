"""Lossless browser transport for the inspection archive.

Sorting observation text together lets HTTP compression share recurring phrases
across reports without changing record order or the manifest's logical hash.
"""

from copy import deepcopy
import json


FORMAT = "observations-establishments-v2"
BROWSER_DATASET_URL = "/data/violations_browser.v2.json"


def pack_dataset(records: list) -> dict:
    packed = deepcopy(records)
    texts = {
        violation["observation"]
        for record in packed
        for violation in record["inspection"]["violations"]
        if "observation" in violation
    }
    if not all(isinstance(text, str) for text in texts):
        raise ValueError("Observation text must be a string")
    observations = sorted(texts)
    indexes = {text: index for index, text in enumerate(observations)}
    establishments = []
    establishment_indexes = {}
    for record in packed:
        if "establishment" in record:
            establishment = record["establishment"]
            if not isinstance(establishment, dict):
                raise ValueError("Establishment must be an object")
            identity = json.dumps(establishment, sort_keys=True)
            if identity not in establishment_indexes:
                establishment_indexes[identity] = len(establishments)
                establishments.append(establishment)
            record["establishment"] = establishment_indexes[identity]
        for violation in record["inspection"]["violations"]:
            if "observation" in violation:
                violation["observation"] = indexes[violation["observation"]]
    return {"format": FORMAT, "observations": observations,
            "establishments": establishments, "records": packed}


def unpack_dataset(payload: list | dict) -> list:
    if isinstance(payload, list):
        return payload
    if (
        not isinstance(payload, dict)
        or payload.get("format") not in ("observations-v1", FORMAT)
        or not isinstance(payload.get("records"), list)
        or not isinstance(payload.get("observations"), list)
        or not all(isinstance(text, str) for text in payload["observations"])
    ):
        raise ValueError("Unsupported browser dataset format")
    records = deepcopy(payload["records"])
    observations = payload["observations"]
    establishments = payload.get("establishments")
    if payload["format"] == FORMAT and (
        not isinstance(establishments, list)
        or not all(isinstance(item, dict) for item in establishments)
    ):
        raise ValueError("Invalid establishment table")
    for record in records:
        if payload["format"] == FORMAT and "establishment" in record:
            index = record["establishment"]
            if type(index) is not int or not 0 <= index < len(establishments):
                raise ValueError("Invalid establishment reference")
            record["establishment"] = deepcopy(establishments[index])
        for violation in record["inspection"]["violations"]:
            if "observation" not in violation:
                continue
            index = violation["observation"]
            if type(index) is not int or not 0 <= index < len(observations):
                raise ValueError("Invalid observation reference")
            violation["observation"] = observations[index]
    return records
