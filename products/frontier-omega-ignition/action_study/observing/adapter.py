"""Adjudicate the LVK issuer's state of a shadow queue entry at one UTC cutoff."""

from datetime import timedelta
import re
from xml.etree import ElementTree as ET

if __package__:
    from . import capture
else:
    import capture


AUTHORITY = "LIGO Scientific Collaboration, Virgo Collaboration, and KAGRA Collaboration"
TYPES = {
    "EarlyWarning": ("163", "Ear"), "Preliminary": ("150", "Pre"),
    "Initial": ("151", "Ini"), "Update": ("152", "Upd"), "Retraction": ("164", "Ret"),
}
VOEVENT = "{http://www.ivoa.net/xml/VOEvent/v2.0}VOEvent"
WINDOW = timedelta(days=7)


class EvidenceError(ValueError):
    def __init__(self, state, message):
        super().__init__(message)
        self.state = state


def disposition(state, reason, evidence=(), finding=None):
    return {"state": state, "finding": finding, "evidence": list(evidence), "reason": reason}


def packets(source):
    """Preserve each document from its declaration through the root closing tag."""
    pattern = rb"<\?xml\s[^?]+\?>.*?</voe:VOEvent>"
    matches = list(re.finditer(pattern, source, re.DOTALL))
    if not matches or re.sub(pattern, b"", source, flags=re.DOTALL).strip():
        raise EvidenceError("incomplete", "The archive has missing or malformed packet boundaries.")
    return [m.group() for m in matches]


def decode(raw, event, source):
    doc = ET.fromstring(raw)
    fields = {p.get("name"): p.get("value") for p in doc.findall("What/Param")}
    if len(fields) != len(doc.findall("What/Param")):
        raise EvidenceError("contradictory", "Two parameters claim the same field in one packet.")
    if (doc.tag != VOEVENT or doc.get("version") != "2.0" or doc.get("role") != "observation"
            or doc.findtext("Who/Author/contactName") != AUTHORITY or fields.get("internal") != "0"
            or fields.get("OpenAlert") != "1" or fields.get("HardwareInj") != "0"):
        raise EvidenceError("incomplete", "The source does not establish a public LVK observation notice.")
    if fields.get("GraceID") != event or fields.get("EventPage") != (
            f"https://gracedb.ligo.org/superevents/{event}/view/"):
        raise EvidenceError("contradictory", "The official event identity disagrees with the mission.")
    kind = fields.get("AlertType")
    if kind not in TYPES or fields.get("Packet_Type") != TYPES[kind][0]:
        raise EvidenceError("contradictory", "The typed notice and GCN packet code disagree.")
    serial = int(fields["Pkt_Ser_Num"])
    record_id = doc.get("ivorn")
    if serial < 1 or record_id != f"ivo://gwnet/LVC#{event}-{serial}-{kind}":
        raise EvidenceError("contradictory", "The notice identifier disagrees with its serial or status.")
    issued = doc.findtext("Who/Date")
    trigger = doc.findtext("WhereWhen/ObsDataLocation/ObservationLocation/AstroCoords/Time/TimeInstant/ISOTime")
    capture.instant(issued)
    capture.instant(trigger)
    return {"record_id": record_id, "event": event, "serial": serial, "notice_type": kind,
            "event_utc": trigger, "issued_utc": issued, "publication_utc": None,
            "operator_received_utc": None, "retrieved_utc": source["retrieved_utc"],
            "source_url": source["url"], "publisher": "LVK via NASA GCN Classic",
            "sha256": capture.digest(raw), "archive_sha256": source["sha256"],
            "unit": "UTC", "meaning": "LVK public candidate status in a VOEvent; Who/Date is issue time."}


def history(event, raw, meta, index_rows):
    if meta["url"] != f"https://gcn.gsfc.nasa.gov/notices_l/{event}.xml_fmt":
        raise EvidenceError("contradictory", "The acquisition route does not match the registered event.")
    records = sorted((decode(p, event, meta) for p in packets(raw)), key=lambda r: r["serial"])
    indexed = {int(r["serial"]): r for r in index_rows if r["event"] == event}
    if not indexed:
        raise EvidenceError("incomplete", "The independent archive index lacks the event.")
    if len({r["serial"] for r in records}) != len(records):
        raise EvidenceError("contradictory", "More than one packet claims a revision.")
    if [r["serial"] for r in records] != list(range(1, max(indexed) + 1)):
        raise EvidenceError("incomplete", "An original revision is absent from the indexed history.")
    previous_time = None
    for rec in records:
        expected = indexed.get(rec["serial"])
        if expected is None:
            raise EvidenceError("incomplete", "The archive index cannot qualify this revision.")
        if (expected["kind"] != TYPES[rec["notice_type"]][1]
                or capture.instant(expected["trigger"]) != capture.instant(rec["event_utc"])):
            raise EvidenceError("contradictory", "The roster disagrees with the original revision.")
        when = capture.instant(rec["issued_utc"])
        if previous_time and when < previous_time:
            raise EvidenceError("contradictory", "The revision sequence has regressing issue times.")
        previous_time = when
    return records


def at_cutoff(records, cutoff, clock, route):
    first = capture.instant(records[0]["issued_utc"])
    if cutoff < first:
        return disposition("pending", "The first registered packet had not been issued by this cutoff.")
    if cutoff > first + WINDOW:
        return disposition("incomplete", "The cutoff exceeds the registered seven-day decision horizon.")
    eligible = [r for r in records if capture.instant(r["issued_utc"]) <= cutoff]
    if route == "first_notice":
        if clock == "received":
            return disposition("incomplete", "The archive has no observer receipt for the first notice.", eligible[:1])
        return disposition("incomplete", "The first notice alone cannot qualify the current lifecycle.", eligible[:1])
    if clock == "received":
        return disposition("incomplete", "Public records do not establish delivery to an observer by this cutoff.", eligible)
    kinds = [r["notice_type"] for r in eligible]
    if "Retraction" in kinds and any(k != "Retraction" for k in kinds[kinds.index("Retraction") + 1:]):
        return disposition("contradictory", "A later non-retraction cannot reinstate a withdrawn entry.", eligible)
    finding = "retracted" if kinds[-1] == "Retraction" else "active"
    return disposition("observed", "The complete indexed issue-time prefix qualifies this archival status.",
                       eligible, finding)


def inspect_source(scope, route):
    if not isinstance(scope, dict) or set(scope) != {"event", "clock", "as_of"}:
        raise ValueError("A mission must specify event, clock and as_of.")
    event, clock = scope["event"], scope["clock"]
    if not isinstance(event, str) or not capture.EVENT.fullmatch(event):
        raise ValueError("Use a public LVK superevent identifier.")
    if route not in {"first_notice", "status_history"} or clock not in {"issued", "received"}:
        raise ValueError("Use a registered clock and evidence route.")
    cutoff = capture.instant(scope["as_of"])
    try:
        reg = capture.manifest()
        name = event + ".xml_fmt"
        if name not in reg["originals"]:
            return disposition("unavailable", "This superevent has no authorized archived source in the recipient.")
        meta = reg["originals"][name]
        raw = capture.original(name, meta)
        if route == "first_notice":
            # The restricted arm gets only revision one, even though the archive supplied a batch.
            first = decode(packets(raw)[0], event, meta)
            if first["serial"] != 1 or meta["url"] != f"https://gcn.gsfc.nasa.gov/notices_l/{event}.xml_fmt":
                return disposition("incomplete", "An authoritative first revision is missing.")
            return at_cutoff([first], cutoff, clock, route)
        records = history(event, raw, meta, capture.roster(reg))
        return at_cutoff(records, cutoff, clock, route)
    except EvidenceError as exc:
        return disposition(exc.state, str(exc))
    except FileNotFoundError:
        return disposition("unavailable", "An authorized original or the roster is unavailable.")
    except (OSError, EOFError, ValueError, KeyError, TypeError, ET.ParseError):
        return disposition("incomplete", "The archived source bytes, fields or timestamps failed qualification.")


def example_scope():
    return {"event": "S240420aw", "as_of": "2024-04-20T05:06:23Z", "clock": "issued"}
