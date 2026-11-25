"""Inspect the bounded prefix of a version-3 little-endian GGUF object."""

import hashlib
import json
import math
import re
import struct


class PrefixIncomplete(ValueError):
    """The registered view ended before the full metadata and tensor index."""


SCALARS = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f",
           7: "B", 10: "Q", 11: "q", 12: "d"}
METADATA = re.compile(
    r"(?:general\.(?:architecture|alignment)|split\.count|"
    r"[\w-]+\.(?:block_count|context_length|embedding_length|"
    r"attention\.(?:head_count(?:_kv)?|key_length|value_length|sliding_window)))\Z"
)
LAYER = re.compile(r"blk\.(\d+)\.")
ALIGNMENT = 32


def raw_digest(raw):
    return hashlib.sha256(raw).hexdigest()


class Reader:
    def __init__(self, raw):
        self.raw = raw
        self.offset = 0

    def advance(self, length):
        offset = self.offset
        self.offset += length
        if length < 0 or self.offset > len(self.raw):
            raise PrefixIncomplete("metadata and tensor index need a longer prefix")
        return offset

    def get(self, fmt):
        length = struct.calcsize("<" + fmt)
        return struct.unpack_from("<" + fmt, self.raw, self.advance(length))[0]

    def string(self, decode):
        size = self.get("Q")
        if size > 10_000_000:
            raise ValueError("unsupported GGUF string length")
        location = self.advance(size)
        return self.raw[location:location + size].decode("utf-8") if decode else None

    def value(self, tag, decode, nesting=0):
        if tag in SCALARS:
            if decode:
                return self.get(SCALARS[tag])
            self.advance(struct.calcsize("<" + SCALARS[tag]))
            return None
        if tag == 8:
            return self.string(decode)
        if tag != 9 or nesting >= 3:
            raise ValueError("unsupported GGUF metadata type or nesting")
        subtype, count = self.get("I"), self.get("Q")
        if count > 1_000_000:
            raise ValueError("unsupported GGUF metadata array length")
        if subtype in SCALARS and not decode:
            self.advance(count * struct.calcsize("<" + SCALARS[subtype]))
        elif decode:
            return [self.value(subtype, True, nesting + 1) for _ in range(count)]
        else:
            for _ in range(count):
                self.value(subtype, False, nesting + 1)
        return None


def read_index(raw, complete_size):
    reader = Reader(raw)
    if reader.get("4s") != b"GGUF" or reader.get("I") != 3:
        raise ValueError("expected version-3 little-endian GGUF")
    tensors, fields = reader.get("Q"), reader.get("Q")
    if not 1 <= tensors <= 50_000 or not 1 <= fields <= 10_000:
        raise ValueError("unsupported number of tensors or metadata fields")
    metadata = {}
    seen = set()
    for _ in range(fields):
        name, tag = reader.string(True), reader.get("I")
        if name in seen:
            raise ValueError("ambiguous repeated GGUF metadata key")
        seen.add(name)
        keep = METADATA.fullmatch(name) is not None
        value = reader.value(tag, keep)
        if keep:
            metadata[name] = value
    if metadata.get("split.count", 1) != 1:
        raise ValueError("this acquisition requires an exact single-file GGUF object")
    index = []
    names = set()
    for _ in range(tensors):
        name, ndim = reader.string(True), reader.get("I")
        if not name or name in names or not 1 <= ndim <= 4:
            raise ValueError("invalid tensor name, duplication or dimension count")
        dimensions = [reader.get("Q") for _ in range(ndim)]
        if any(not 1 <= value <= 2 ** 32 for value in dimensions):
            raise ValueError("unsupported tensor shape")
        dtype, offset = reader.get("I"), reader.get("Q")
        index.append({"name": name, "dimensions": dimensions, "dtype": dtype, "offset": offset})
        names.add(name)
    alignment = metadata.get("general.alignment", ALIGNMENT)
    if type(alignment) is not int or alignment < 1 or alignment > 4096 or alignment & (alignment - 1):
        raise ValueError("unsupported tensor storage alignment")
    data_offset = (reader.offset + alignment - 1) // alignment * alignment
    available = complete_size - data_offset
    offsets = sorted(row["offset"] for row in index)
    if available <= 0 or offsets[0] != 0 or offsets[-1] >= available or len(set(offsets)) != len(offsets):
        raise ValueError("tensor offsets are inconsistent with the registry size")
    if any(offset % alignment != 0 for offset in offsets):
        raise ValueError("tensor offset violates declared alignment")
    return {"metadata": metadata, "tensors": index, "tensor_data_offset": data_offset}


def digest_index(index):
    stable = json.dumps(index, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return raw_digest(stable)


def summarize(index, complete_size):
    meta = index["metadata"]
    architecture = meta["general.architecture"]
    block_count = meta[architecture + ".block_count"]
    context = meta[architecture + ".context_length"]
    if type(block_count) is not int or not 1 <= block_count <= 2048 or type(context) is not int or context < 1:
        raise ValueError("unsupported declared architecture dimensions")
    payload = complete_size - index["tensor_data_offset"]
    weights = {"global": 0}
    tensors = sorted(index["tensors"], key=lambda row: row["offset"])
    for tensor, following in zip(tensors, tensors[1:] + [{"offset": payload}], strict=True):
        match = LAYER.match(tensor["name"])
        key = match[1] if match else "global"
        weights[key] = weights.get(key, 0) + following["offset"] - tensor["offset"]
    if set(weights) != {"global"} | {str(i) for i in range(block_count)}:
        raise ValueError("named layer storage does not match the known block count")
    return {
        "architecture": architecture, "native_context_tokens": context, "block_count": block_count,
        "tensor_count": len(tensors), "tensor_index_sha256": digest_index(index),
        "tensor_data_offset": index["tensor_data_offset"], "tensor_storage_span_bytes": payload,
        "declared_parameter_elements": sum(math.prod(tensor["dimensions"]) for tensor in tensors),
        "layer_allocation_spans_bytes": weights,
        "storage_scope": "File spans from ordered offsets, including GGUF alignment. No allocation or weight payload was measured.",
    }
