"""Lossless browser transport for the inspection archive.

Sorting observation text together lets HTTP compression share recurring phrases
across reports without changing record order or the manifest's logical hash.
"""

from copy import deepcopy


FORMAT = "observations-v1"
BROWSER_DATASET_URL = "/data/violations_browser.v1.json"


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
    for record in packed:
        for violation in record["inspection"]["violations"]:
            if "observation" in violation:
                violation["observation"] = indexes[violation["observation"]]
    return {"format": FORMAT, "observations": observations, "records": packed}


def unpack_dataset(payload: list | dict) -> list:
    if isinstance(payload, list):
        return payload
    if (
        not isinstance(payload, dict)
        or payload.get("format") != FORMAT
        or not isinstance(payload.get("records"), list)
        or not isinstance(payload.get("observations"), list)
        or not all(isinstance(text, str) for text in payload["observations"])
    ):
        raise ValueError("Unsupported browser dataset format")
    records = deepcopy(payload["records"])
    observations = payload["observations"]
    for record in records:
        for violation in record["inspection"]["violations"]:
            if "observation" not in violation:
                continue
            index = violation["observation"]
            if type(index) is not int or not 0 <= index < len(observations):
                raise ValueError("Invalid observation reference")
            violation["observation"] = observations[index]
    return records
