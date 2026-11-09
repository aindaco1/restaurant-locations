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
    assert packed["observations"] == [[0, ""], [0, "A repeated phrase"], [0, "Z café\n\"quoted\""]]
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
    assert len(gzip.compress(compact(packed))) <= 140_000


def test_repeated_establishments_preserve_values_without_aliasing():
    records = [{"establishment": {"name": "Café", "address": "One"},
                "inspection": {"violations": []}} for _ in range(2)]
    records.append({"establishment": {"name": "Café", "address": "Two"},
                    "inspection": {"violations": []}})
    packed = pack_dataset(records)
    assert len(packed["establishments"]) == 2
    decoded = unpack_dataset(packed)
    assert decoded == records
    decoded[0]["establishment"]["name"] = "Edited"
    assert decoded[1]["establishment"]["name"] == "Café"
    assert unpack_dataset(packed) == records


@pytest.mark.parametrize("reference", [-1, 1, 0.5, True, "0", None])
def test_rejects_invalid_establishment_references(reference):
    packed = pack_dataset([{"establishment": {"name": "Café"},
                            "inspection": {"violations": []}}])
    packed["records"][0]["establishment"] = reference
    with pytest.raises(ValueError, match="Invalid establishment reference"):
        unpack_dataset(packed)


@pytest.mark.parametrize("table", [None, {}, [None], [[]]])
def test_rejects_invalid_establishment_tables(table):
    packed = pack_dataset([])
    packed["establishments"] = table
    with pytest.raises(ValueError, match="Invalid establishment table"):
        unpack_dataset(packed)


def test_empty_archive_and_legacy_array():
    assert unpack_dataset(pack_dataset([])) == []
    records = [{"id": "legacy"}]
    assert unpack_dataset(records) is records


def test_prefixes_count_unicode_characters_and_preserve_exact_text():
    texts = ["😀 café\nfirst", "😀 café\nsecond", "😀 café", "", "é", "é"]
    records = [{"inspection": {"violations": [{"observation": text} for text in texts]}}]
    packed = pack_dataset(records)
    assert packed["format"] == "observations-prefixes-v3"
    assert [7, "second"] in packed["observations"]
    assert unpack_dataset(packed) == records


@pytest.mark.parametrize("entry", [None, "text", [], [0], [0, "text", "extra"],
                                   [-1, "x"], [1, "x"], [True, "x"], [0.5, "x"], [0, None]])
def test_rejects_invalid_observation_prefixes(entry):
    packed = pack_dataset([])
    packed["observations"] = [entry]
    with pytest.raises(ValueError, match="Invalid observation prefix"):
        unpack_dataset(packed)


def test_legacy_v2_still_decodes():
    payload = {"format": "observations-establishments-v2", "observations": ["text"],
               "establishments": [{"name": "Café"}], "records": [
                   {"establishment": 0, "inspection": {"violations": [{"observation": 0}]}}]}
    assert unpack_dataset(payload) == [{"establishment": {"name": "Café"},
                                       "inspection": {"violations": [{"observation": "text"}]}}]


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
