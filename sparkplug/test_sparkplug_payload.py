import shutil
import subprocess
from pathlib import Path

import pytest

from sparkplug_payload import BOOLEAN, DOUBLE, INT32, INT64, STRING, decode, encode

PROTO = Path(__file__).parent / "sparkplug_b.proto"

PAYLOAD = {
    "timestamp": 1700000000123,
    "seq": 7,
    "metrics": [
        {"name": "Temperatur", "timestamp": 1700000000100, "datatype": DOUBLE, "value": 21.5},
        {"name": "Status", "datatype": STRING, "value": "Running"},
        {"name": "Antal", "datatype": INT64, "value": 12345678901},
        {"name": "Kor", "datatype": BOOLEAN, "value": True},
        {"name": "Varvtal", "datatype": INT32, "value": 1500},
        {"name": "Saknas", "datatype": DOUBLE, "value": None},
    ],
}


def test_roundtrip_keeps_every_field():
    assert decode(encode(PAYLOAD)) == PAYLOAD


def test_metric_without_timestamp_stays_without():
    out = decode(encode({"timestamp": 1, "metrics": [{"name": "a", "datatype": STRING, "value": "x"}], "seq": 0}))
    assert "timestamp" not in out["metrics"][0]


def test_decode_skips_unknown_fields():
    data = encode(PAYLOAD) + bytes([0x5A, 0x03, 1, 2, 3])  # field 11 (uuid-like), length-delimited
    assert decode(data) == PAYLOAD


@pytest.mark.skipif(shutil.which("protoc") is None, reason="protoc is not installed")
def test_protoc_reads_what_we_write():
    out = subprocess.run(
        ["protoc", f"--proto_path={PROTO.parent}", "--decode=org.eclipse.tahu.protobuf.Payload", PROTO.name],
        input=encode(PAYLOAD), capture_output=True, check=True,
    ).stdout.decode()
    assert "seq: 7" in out
    assert 'name: "Temperatur"' in out and "double_value: 21.5" in out
    assert 'string_value: "Running"' in out
    assert "long_value: 12345678901" in out
    assert "boolean_value: true" in out
    assert "int_value: 1500" in out
    assert out.count("is_null: true") == 1


@pytest.mark.skipif(shutil.which("protoc") is None, reason="protoc is not installed")
def test_we_read_what_protoc_writes():
    text = (
        'timestamp: 1700000000123 seq: 3 '
        'metrics { name: "Kor" datatype: 11 boolean_value: false } '
        'metrics { name: "Antal" datatype: 4 long_value: 9 }'
    )
    data = subprocess.run(
        ["protoc", f"--proto_path={PROTO.parent}", "--encode=org.eclipse.tahu.protobuf.Payload", PROTO.name],
        input=text.encode(), capture_output=True, check=True,
    ).stdout
    assert decode(data) == {
        "timestamp": 1700000000123,
        "seq": 3,
        "metrics": [
            {"name": "Kor", "datatype": BOOLEAN, "value": False},
            {"name": "Antal", "datatype": INT64, "value": 9},
        ],
    }
