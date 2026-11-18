"""Independent conventional status query over the NASA GCN e-mail archive and packet clock."""

import re
import sqlite3
from datetime import datetime, timezone
from xml.dom import minidom

if __package__:
    from . import capture
else:
    import capture


def schedule(event, mode="issued"):
    reg = capture.manifest()
    xml_name, mail_name = event + ".xml_fmt", event + ".lvc"
    if mode not in {"issued", "mail_notice"}:
        raise ValueError("Use an issued or mail_notice clock.")
    mail = capture.original(mail_name, reg["originals"][mail_name]).decode("ascii")
    xml = capture.original(xml_name, reg["originals"][xml_name])
    # Join two recordings of the same issuer. The text product has a distinct GCN clock.
    docs = minidom.parseString(b"<archive>" + re.sub(rb"<\?xml[^?]*\?>", b"", xml) + b"</archive>")
    issue = {}
    for doc in docs.getElementsByTagName("voe:VOEvent"):
        fields = {p.getAttribute("name"): p.getAttribute("value") for p in doc.getElementsByTagName("Param")}
        serial = int(fields["Pkt_Ser_Num"])
        if (fields["GraceID"] != event or fields["OpenAlert"] != "1" or fields["internal"] != "0"
                or fields["HardwareInj"] != "0" or doc.getAttribute("role") != "observation"
                or fields["EventPage"] != f"https://gracedb.ligo.org/superevents/{event}/view/"
                or serial in issue):
            raise ValueError("Conflicting public identity in the official timestamp source.")
        issue[serial] = (doc.getElementsByTagName("Date")[0].firstChild.data,
                         doc.getElementsByTagName("ISOTime")[0].firstChild.data, fields["AlertType"])
    indexed = {int(r["serial"]): r for r in capture.roster(reg) if r["event"] == event}
    history = []
    for block in re.split(r"^/{6,}\s*$", mail, flags=re.MULTILINE):
        if not block.strip():
            continue
        fields = dict(re.findall(r"^([A-Z_]+):\s*([^\n]+?)\s*$", block, re.MULTILINE))
        if (fields["TRIGGER_NUM"] != event or ("EVENTPAGE_URL" in fields and
                fields["EVENTPAGE_URL"] != f"https://gracedb.ligo.org/superevents/{event}/view/")):
            raise ValueError("Conventional source identifies a different event.")
        kind = fields["NOTICE_TYPE"].removeprefix("LVC ").replace(" ", "")
        title = "GCN/LVC_RETRACTION NOTICE" if kind == "Retraction" else "GCN/LVC NOTICE"
        if fields["TITLE"] != title or kind not in {"Retraction", "Preliminary", "Initial", "Update", "EarlyWarning"}:
            raise ValueError("Unrecognized conventional status.")
        serial = int(fields["SEQUENCE_NUM"])
        issued, xml_trigger, xml_kind = issue[serial]
        day = re.search(r"\b\d{4}/\d{2}/\d{2}\b", fields["TRIGGER_DATE"])[0].replace("/", "-")
        trigger = day + "T" + re.search(r"\{([^}]+)\}", fields["TRIGGER_TIME"])[1] + "Z"
        if xml_kind != kind or capture.instant(trigger) != capture.instant(xml_trigger):
            raise ValueError("The conventional and machine records disagree.")
        if (capture.instant(indexed[serial]["trigger"]) != capture.instant(trigger)
                or indexed[serial]["kind"] != kind[:3]):
            raise ValueError("The conventional record disagrees with the NASA roster.")
        gcn_date = datetime.strptime(fields["NOTICE_DATE"], "%a %d %b %y %H:%M:%S UT").replace(tzinfo=timezone.utc)
        clock = gcn_date.isoformat().replace("+00:00", "Z") if mode == "mail_notice" else issued
        history.append({"serial": serial, "kind": kind, "issued_utc": issued, "notice_utc": gcn_date,
                        "time": capture.instant(clock)})
    serials = sorted(r["serial"] for r in history)
    if not serials or serials != list(range(1, max(indexed) + 1)) or set(serials) != set(issue):
        raise ValueError("Conventional and official packet populations differ.")
    return sorted(history, key=lambda r: r["serial"])


def query(history, cutoff):
    """Select the current conventional status in SQLite at an inclusive UTC cutoff."""
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE TABLE notice(serial INTEGER PRIMARY KEY, t TEXT NOT NULL, kind TEXT NOT NULL)")
        db.executemany("INSERT INTO notice VALUES (?, ?, ?)", (
            (r["serial"], r["time"].isoformat(timespec="microseconds"), r["kind"]) for r in history))
        decision = db.execute("""
            WITH eligible AS (SELECT * FROM notice WHERE t <= ?)
            SELECT CASE
                WHEN EXISTS (SELECT 1 FROM eligible old JOIN eligible new ON new.serial > old.serial
                             WHERE old.kind = 'Retraction' AND new.kind <> 'Retraction')
                    THEN 'contradictory'
                WHEN latest.kind = 'Retraction' THEN 'retracted' ELSE 'active'
            END FROM (SELECT * FROM eligible ORDER BY serial DESC LIMIT 1) latest
        """, (cutoff.isoformat(timespec="microseconds"),)).fetchone()
        return decision[0] if decision else "pending"
    finally:
        db.close()


def decide(event, cutoff):
    return query(schedule(event), cutoff)
