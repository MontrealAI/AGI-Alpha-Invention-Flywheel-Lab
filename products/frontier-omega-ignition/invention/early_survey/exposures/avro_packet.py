"""Read the single-record, null-codec ZTF Avro container used by this study."""
import io
import json
import struct


def record(data):
    stream = io.BytesIO(data)

    def take(n):
        if n < 0 or n > len(data):
            raise ValueError("invalid Avro length")
        raw = stream.read(n)
        if len(raw) != n:
            raise ValueError("incomplete Avro value")
        return raw

    def integer():
        n = 0
        for shift in range(0, 70, 7):
            b = take(1)[0]
            n |= (b & 127) << shift
            if b < 128:
                return (n >> 1) ^ -(n & 1)
        raise ValueError("invalid Avro integer")

    def blob():
        return take(integer())

    def items():
        while (n := integer()) != 0:
            if n < 0:
                n = -n
                integer()  # encoded byte count
            if n > len(data):
                raise ValueError("invalid Avro block count")
            yield from range(n)

    if take(4) != b"Obj\1":
        raise ValueError("invalid Avro header")
    metadata = {}
    for _ in items():
        key = blob().decode()
        metadata[key] = blob()
    sync = take(16)
    if metadata.get("avro.codec", b"null") != b"null" or integer() != 1:
        raise ValueError("expected one uncompressed ZTF record")
    block_size = integer()
    block_start = stream.tell()
    types = {}

    def read(node, namespace=""):
        if isinstance(node, list):
            branch = integer()
            if not 0 <= branch < len(node):
                raise ValueError("invalid Avro union")
            return read(node[branch], namespace)
        if isinstance(node, dict):
            kind = node["type"]
            if kind == "record":
                ns = node.get("namespace", namespace)
                name = node["name"]
                qualified = name if "." in name else (ns + "." + name if ns else name)
                types[qualified] = node
                return {f["name"]: read(f["type"], qualified.rpartition(".")[0]) for f in node["fields"]}
            if kind == "array":
                return [read(node["items"], namespace) for _ in items()]
            return read(kind, namespace)
        if node in ("int", "long"):
            return integer()
        if node in ("float", "double"):
            return struct.unpack("<f" if node == "float" else "<d", take(4 if node == "float" else 8))[0]
        if node == "null":
            return None
        if node == "bytes":
            return blob()
        if node == "string":
            return blob().decode()
        return read(types[node if "." in node else namespace + "." + node], namespace)

    value = read(json.loads(metadata["avro.schema"]))
    if stream.tell() - block_start != block_size or take(16) != sync or stream.read(1):
        raise ValueError("invalid Avro block extent or trailing input")
    return value
