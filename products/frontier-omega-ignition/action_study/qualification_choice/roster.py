"""Read only the first two columns of the pinned public Princeton roster.

The file has a single row group. Each of its first two flat UTF-8 columns has
one Snappy-compressed PLAIN dictionary page and one RLE_DICTIONARY data page.
The reader validates these conditions, the page counts and the distinct roster.
"""
from hashlib import sha256
from pathlib import Path
import argparse
import json
import struct
from urllib.parse import urlencode

HF = "https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/resolve/c104f840cc67f8b6eec6f759ebc8b2693d585d4a/"
URL = HF + "data/test-00000-of-00001.parquet"
LIMIT = 65_536


class Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError("Invalid or truncated roster stream")
        value = self.data[self.pos:self.pos + n]
        self.pos += n
        return value

    def integer(self):
        n = 0
        for shift in range(0, 64, 7):
            b = self.take(1)[0]
            n |= (b & 127) << shift
            if b < 128:
                return n
        raise ValueError("Oversized integer")

    def signed(self):
        n = self.integer()
        return (n >> 1) ^ -(n & 1)

    def fields(self):
        result = {}
        field = 0
        while True:
            flag = self.take(1)[0]
            if flag == 0:
                return result
            field = field + (flag >> 4) if flag >> 4 else self.signed()
            kind = flag & 15
            if kind in (1, 2):
                value = kind == 1
            elif kind in (4, 5, 6):
                value = self.signed()
            elif kind == 8:
                value = self.take(self.integer())
            elif kind == 9:
                spec = self.take(1)[0]
                n = self.integer() if spec >> 4 == 15 else spec >> 4
                if n > 128:
                    raise ValueError("Unexpected field list")
                element = spec & 15
                if element in (4, 5, 6):
                    value = [self.signed() for _ in range(n)]
                elif element == 8:
                    value = [self.take(self.integer()) for _ in range(n)]
                elif element == 12:
                    value = [self.fields() for _ in range(n)]
                else:
                    raise ValueError("Unexpected list type")
            elif kind == 12:
                value = self.fields()
            else:
                raise ValueError(f"Unexpected Thrift field {field}, type {kind}, at {self.pos}")
            if field in result:
                raise ValueError("Duplicate header field")
            result[field] = value


def unsnappy(data, size):
    r = Reader(data)
    if r.integer() != size or size > LIMIT:
        raise ValueError("Invalid Snappy length")
    out = bytearray()
    while r.pos < len(data):
        tag = r.take(1)[0]
        opcode = tag & 3
        if opcode == 0:
            size_tag = tag >> 2
            length = size_tag + 1 if size_tag < 60 else int.from_bytes(r.take(size_tag - 59), "little") + 1
            out.extend(r.take(length))
        else:
            if opcode == 1:
                length = 4 + ((tag >> 2) & 7)
                offset = ((tag & 224) << 3) | r.take(1)[0]
            else:
                length = 1 + (tag >> 2)
                offset = int.from_bytes(r.take(2 if opcode == 2 else 4), "little")
            if not 0 < offset <= len(out):
                raise ValueError("Invalid Snappy reference")
            for _ in range(length):
                out.append(out[-offset])
        if len(out) > size:
            raise ValueError("Snappy length exceeded")
    if len(out) != size:
        raise ValueError("Snappy length mismatch")
    return bytes(out)


def hybrid(data, width, count):
    reader = Reader(data)
    out = []
    while len(out) < count:
        header = reader.integer()
        if header == 0:
            raise ValueError("Empty RLE section")
        section_size = (header >> 1) * (8 if header & 1 else 1)
        if section_size > count + 7 - len(out):
            raise ValueError("Excess roster values")
        if header & 1:
            groups = header >> 1
            buffer = int.from_bytes(reader.take(groups * width), "little")
            for _ in range(groups * 8):
                out.append(buffer & ((1 << width) - 1))
                buffer >>= width
        else:
            value = int.from_bytes(reader.take((width + 7) // 8), "little")
            out.extend([value] * (header >> 1))
        if len(out) > count + 7:
            raise ValueError("Excess roster values")
    if reader.pos != len(data):
        raise ValueError("Unused RLE data")
    return out[:count]


def decode_prefix(prefix):
    if sha256(prefix).hexdigest() != "f064f0991046c73421084dbc4750a7901cd928f65479c0ade9f56a4c0d3d46d1":
        raise ValueError("Pinned Princeton roster projection changed")
    reader = Reader(prefix)
    if reader.take(4) != b"PAR1":
        raise ValueError("Invalid Parquet magic")
    columns = []
    for _ in range(2):
        if columns:
            metadata = reader.fields()[3]
            if metadata[3] != [b"repo"] or metadata[1] != 6 or metadata[5] != 500:
                raise ValueError("Unexpected intervening column metadata")
        header = reader.fields()
        if header[1] != 2 or header[7][2] != 0:
            raise ValueError("Expected PLAIN dictionary")
        dictionary = Reader(unsnappy(reader.take(header[3]), header[2]))
        words = [dictionary.take(int.from_bytes(dictionary.take(4), "little")).decode("utf8")
                 for _ in range(header[7][1])]
        if dictionary.pos != len(dictionary.data):
            raise ValueError("Unexpected trailing dictionary bytes")
        header = reader.fields()
        if header[1] != 0 or header[5][1] != 500 or header[5][2] not in (2, 8):
            raise ValueError("Expected the pinned 500 dictionary-encoded values")
        values = Reader(unsnappy(reader.take(header[3]), header[2]))
        def_size = struct.unpack("<I", values.take(4))[0]
        if hybrid(values.take(def_size), 1, 500) != [1] * 500:
            raise ValueError("Roster has a missing value")
        width = values.take(1)[0]
        indexes = hybrid(values.take(len(values.data) - values.pos), width, 500)
        columns.append([words[ix] for ix in indexes])
    if reader.pos != len(prefix):
        raise ValueError("Unexpected third-column data")
    repo, ids = columns
    roster = dict(zip(ids, repo))
    if len(roster) != 500 or any(key.rsplit("-", 1)[0] != name.replace("/", "__") for key, name in roster.items()):
        raise ValueError("Duplicate or incoherent official identifiers")
    return roster


def capture(destination):
    if __package__:
        from .acquire import acquire, save
    else:
        from acquire import acquire, save
    readme, schema_receipt = acquire(HF + "README.md")
    schema = readme.decode("utf8")
    start = schema.index("features:")
    fields = schema[start:].split("- name: ")
    if not (fields[1].startswith("repo\n") and fields[2].startswith("instance_id\n")):
        raise ValueError("Official schema no longer declares repo and instance_id first")
    ranges = []
    def read(start, end):
        query = urlencode({"download": "true", "projection": f"first2-{start}-{end}"})
        data, receipt = acquire(URL + "?" + query, (start, end))
        ranges.append(receipt)
        if receipt["content_range"] != f"bytes {start}-{end}/2096679":
            raise ValueError("Unexpected roster length or range")
        return data
    prefix = bytearray(read(0, 3))
    for page_type in (2, 0, "repo_metadata", 2, 0):
        start = len(prefix)
        # These four pinned headers precede the body of an approved roster page.
        header_bytes = bytearray()
        for _ in range(40):
            offset = start + len(header_bytes)
            header_bytes.extend(read(offset, offset + 15))
            head = Reader(header_bytes)
            try:
                header = head.fields()
            except ValueError as exc:
                if "truncated roster" in str(exc):
                    continue
                raise
            break
        else:
            raise ValueError("Oversized roster page header")
        if page_type == "repo_metadata":
            if header[3][3] != [b"repo"] or header[3][1] != 6 or header[3][5] != 500:
                raise ValueError("Invalid metadata between permitted columns")
            prefix.extend(header_bytes[:head.pos])
            continue
        if header[1] != page_type or not 0 < header[3] <= LIMIT:
            raise ValueError("Unexpected roster page boundary")
        page_size = head.pos + header[3]
        if page_size < len(header_bytes):
            raise ValueError("Header lookahead exceeds approved page")
        prefix.extend(header_bytes)
        if page_size > len(header_bytes):
            prefix.extend(read(start + len(header_bytes), start + page_size - 1))
    roster = decode_prefix(prefix)
    destination.mkdir(exist_ok=True, parents=True)
    (destination / "roster.parquet-prefix").write_bytes(prefix)
    save(destination / "roster-receipt.json", {"url": URL, "sha256": sha256(prefix).hexdigest(),
             "schema": schema_receipt, "columns": ["repo", "instance_id"], "ranges": ranges})
    print(len(roster), "original rows;", len(prefix), "unique roster bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    capture(parser.parse_args().destination)
