"""Export a repeating wall-time schedule as explicit UTC iCalendar events."""

import argparse
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
import uuid
from zoneinfo import ZoneInfo


def utc_instant(naive, zone, disambiguation=None):
    if naive.tzinfo is not None:
        raise ValueError('Expected a wall clock without an embedded offset')
    candidates = {}
    for fold in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=fold)
        instant = aware.astimezone(timezone.utc)
        if instant.astimezone(zone).replace(tzinfo=None) == naive:
            candidates[fold] = instant
    instants = sorted(set(candidates.values()))
    if not instants:
        raise ValueError(f'Nonexistent local time: {naive} in {zone.key}')
    if len(instants) > 1:
        if disambiguation not in candidates:
            raise ValueError(f'Ambiguous local time: {naive} in {zone.key}; choose fold explicitly')
        return candidates[disambiguation]
    return instants[0]


def escape_text(value):
    return value.replace('\\', '\\\\').replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def emit_line(value):
    lines = []
    current = bytearray()
    for char in value:
        encoded = char.encode('utf-8')
        if len(current) + len(encoded) > 75:
            lines.append(bytes(current))
            current = bytearray(b' ')
        current.extend(encoded)
    lines.append(bytes(current))
    return b'\r\n'.join(lines)


def stamp(value):
    return value.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def compile_calendar(first, through, start_time, interval_days, minutes, zone, title, build_time, fold=None):
    if first > through or interval_days < 1 or minutes < 1:
        raise ValueError('Require a nonempty date range and positive interval and duration')
    if build_time.tzinfo is None:
        raise ValueError('Expected timestamp with an explicit offset')
    if not title.strip() or any(ord(char) < 32 and char not in '\r\n\t' for char in title):
        raise ValueError('Missing or invalid calendar summary')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Frontier Eval//Local wall-time calendar//EN', 'CALSCALE:GREGORIAN']
    for step in range(0, (through - first).days + 1, interval_days):
        day = first + timedelta(days=step)
        local = datetime.combine(day, start_time)
        utc = utc_instant(local, zone, fold)
        end = utc + timedelta(minutes=minutes)
        identity = uuid.uuid5(uuid.NAMESPACE_URL, f'frontier-local/{zone.key}/{local.isoformat()}/{title}')
        lines.extend(['BEGIN:VEVENT', f'UID:{identity}@frontier.local', f'DTSTAMP:{stamp(build_time)}',
                      f'DTSTART:{stamp(utc)}', f'DTEND:{stamp(end)}', f'SUMMARY:{escape_text(title)}', 'END:VEVENT'])
    lines.append('END:VCALENDAR')
    return b'\r\n'.join(map(emit_line, lines)) + b'\r\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first', type=date.fromisoformat, required=True)
    parser.add_argument('--through', type=date.fromisoformat, required=True)
    parser.add_argument('--time', type=time.fromisoformat, required=True)
    parser.add_argument('--timezone', type=ZoneInfo, required=True)
    parser.add_argument('--minutes', type=int, required=True)
    parser.add_argument('--interval-days', type=int, default=7)
    parser.add_argument('--fold', type=int, choices=(0, 1))
    parser.add_argument('--summary', required=True)
    parser.add_argument('--stamp', type=datetime.fromisoformat)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    calendar = compile_calendar(a.first, a.through, a.time, a.interval_days, a.minutes, a.timezone, a.summary,
                                a.stamp or datetime.now(timezone.utc), a.fold)
    a.output.write_bytes(calendar)


if __name__ == '__main__':
    main()
