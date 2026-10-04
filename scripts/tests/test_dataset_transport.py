import gzip
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dataset_transport import pack_dataset, unpack_dataset


def test_round_trip_preserves_observations_missing_fields_and_order():
    records = [{"id": "second", "inspection": {"violations": [
        {"observation": "Z café\n\"quoted\"", "critical": True},
        {"observation": ""},
        {"desc": "Legacy record without observation"},
    ]}}, {"id": "first", "inspection": {"violations": [
        {"observation": "Z café\n\"quoted\""},
        {"observation": "A repeated phrase"},
    ]}}]
    original = deepcopy(records)
    packed = pack_dataset(records)
    assert packed["observations"] == ["", "A repeated phrase", "Z café\n\"quoted\""]
    assert unpack_dataset(json.loads(json.dumps(packed))) == original
    assert records == original
    assert isinstance(packed["records"][0]["inspection"]["violations"][0]["observation"], int)


def test_full_archive_round_trip_and_compression():
    path = Path(__file__).resolve().parents[2] / "data/violations_latest.json"
    records = json.loads(path.read_text())
    packed = pack_dataset(records)
    assert unpack_dataset(packed) == records
    compact = lambda data: json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    assert len(gzip.compress(compact(packed))) < len(gzip.compress(compact(records)))


def test_empty_archive_and_legacy_array():
    assert unpack_dataset(pack_dataset([])) == []
    records = [{"id": "legacy"}]
    assert unpack_dataset(records) is records


@pytest.mark.parametrize("reference", [-1, 1, 0.5, True, "0", None])
def test_rejects_invalid_observation_references(reference):
    payload = {"format": "observations-v1", "observations": ["text"], "records": [
        {"inspection": {"violations": [{"observation": reference}]}}
    ]}
    with pytest.raises(ValueError, match="Invalid observation reference"):
        unpack_dataset(payload)


@pytest.mark.parametrize("payload", [None, {}, {"format": "future"}, {
    "format": "observations-v1", "observations": [None], "records": []
}])
def test_rejects_invalid_format(payload):
    with pytest.raises(ValueError, match="Unsupported browser dataset format"):
        unpack_dataset(payload)
