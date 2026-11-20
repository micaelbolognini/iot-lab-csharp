"""Sparkplug payload as protobuf wire format (the subset in sparkplug_b.proto), without a protobuf dependency."""
import struct

INT32, INT64, DOUBLE, BOOLEAN, STRING = 3, 4, 10, 11, 12

_VALUE_FIELD = {INT32: 10, INT64: 11, DOUBLE: 13, BOOLEAN: 14, STRING: 15}
_FIELD_VALUE = {field: datatype for datatype, field in _VALUE_FIELD.items()}


def _varint(n):
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        out.append(byte | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _read_varint(data, pos):
    shift = result = 0
    while True:
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7


def _tag(field, wire):
    return _varint(field << 3 | wire)


def _varint_field(field, n):
    return _tag(field, 0) + _varint(n)


def _bytes_field(field, data):
    return _tag(field, 2) + _varint(len(data)) + data


def _encode_metric(metric):
    out = bytearray(_bytes_field(1, metric["name"].encode()))
    if "timestamp" in metric:
        out += _varint_field(3, metric["timestamp"])
    datatype = metric["datatype"]
    out += _varint_field(4, datatype)
    value = metric["value"]
    if value is None:
        out += _varint_field(7, 1)
    elif datatype == INT32:
        out += _varint_field(10, value & 0xFFFFFFFF)
    elif datatype == INT64:
        out += _varint_field(11, value & 0xFFFFFFFFFFFFFFFF)
    elif datatype == DOUBLE:
        out += _tag(13, 1) + struct.pack("<d", value)
    elif datatype == BOOLEAN:
        out += _varint_field(14, int(value))
    elif datatype == STRING:
        out += _bytes_field(15, value.encode())
    else:
        raise ValueError(f"unsupported datatype {datatype}")
    return bytes(out)


def encode(payload):
    out = bytearray()
    if "timestamp" in payload:
        out += _varint_field(1, payload["timestamp"])
    for metric in payload.get("metrics", []):
        out += _bytes_field(2, _encode_metric(metric))
    if "seq" in payload:
        out += _varint_field(3, payload["seq"])
    return bytes(out)


def _fields(data):
    pos = 0
    while pos < len(data):
        key, pos = _read_varint(data, pos)
        field, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = _read_varint(data, pos)
        elif wire == 1:
            value, pos = data[pos:pos + 8], pos + 8
        elif wire == 2:
            length, pos = _read_varint(data, pos)
            value, pos = data[pos:pos + length], pos + length
        elif wire == 5:
            value, pos = data[pos:pos + 4], pos + 4
        else:
            raise ValueError(f"unsupported wire type {wire}")
        yield field, wire, value


def _decode_metric(data):
    metric, value, datatype = {}, None, None
    for field, wire, raw in _fields(data):
        if field == 1:
            metric["name"] = raw.decode()
        elif field == 3:
            metric["timestamp"] = raw
        elif field == 4:
            datatype = raw
        elif field == 7:
            value = None
            metric["_null"] = bool(raw)
        elif field == 10:
            value = raw - (1 << 32) if raw >= 1 << 31 else raw
            datatype = datatype or INT32
        elif field == 11:
            value = raw - (1 << 64) if raw >= 1 << 63 else raw
            datatype = datatype or INT64
        elif field == 13:
            value = struct.unpack("<d", raw)[0]
        elif field == 14:
            value = bool(raw)
        elif field == 15:
            value = raw.decode()
    metric.pop("_null", None)
    metric["datatype"] = datatype
    metric["value"] = value
    return metric


def decode(data):
    payload = {}
    metrics = []
    for field, wire, raw in _fields(data):
        if field == 1:
            payload["timestamp"] = raw
        elif field == 2:
            metrics.append(_decode_metric(raw))
        elif field == 3:
            payload["seq"] = raw
    payload["metrics"] = metrics
    return payload
