"""Bounded, lossy lesson memory and opt-in disposal of managed diagnostic logs.

The caller supplies the distilled lesson. This module does not infer one, execute
its text, certify an experiment, or alter financial/recovery/capability records.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

SCHEMA = 'agi-alpha/bounded-lessons/v1'
STATE, LOCK, NEXT = '.lessons.json', '.lessons.lock', '.lessons.next'
MAX_RAW = 8 * 1024 * 1024


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def load(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('NONFINITE_JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def normal_root(path):
    root = Path(path).expanduser().absolute()
    require('..' not in root.parts and root.is_dir(), 'EXISTING_NORMAL_WORKSPACE_REQUIRED')
    require(not any(p.is_symlink() for p in (root, *root.parents)), 'WORKSPACE_SYMLINK_REFUSED')
    return root


@contextmanager
def workspace(path):
    root = normal_root(path)
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    lock = None
    try:
        # A cleanup operation never initializes or searches an arbitrary directory.
        require(stat.S_ISREG(os.stat(STATE, dir_fd=directory, follow_symlinks=False).st_mode), 'INITIALIZED_WORKSPACE_REQUIRED')
        lock = os.open(LOCK, os.O_RDWR | os.O_NOFOLLOW, dir_fd=directory)
        info = os.fstat(lock)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'REGULAR_SINGLE_LINK_LOCK_REQUIRED')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield root, directory
    finally:
        if lock is not None:
            os.close(lock)
        os.close(directory)


def read_regular(directory, name, limit):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'REGULAR_SINGLE_LINK_FILE_REQUIRED')
        require(before.st_size <= limit, 'INPUT_SIZE_LIMIT')
        chunks, total = [], 0
        while True:
            chunk = os.read(fd, min(65536, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk); total += len(chunk)
            require(total <= limit, 'INPUT_SIZE_LIMIT')
        after = os.fstat(fd)
        require(identity(before) == identity(after) and total == before.st_size, 'FILE_CHANGED_DURING_READ')
        return b''.join(chunks), before
    finally:
        os.close(fd)


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)


def validate_lesson(lesson):
    fields = {'key': 80, 'scope': 160, 'trigger': 512, 'rule': 1024, 'check': 512}
    require(type(lesson) is dict and set(lesson) == set(fields) | {'priority'}, 'EXACT_LESSON_FIELDS_REQUIRED')
    for key, maximum in fields.items():
        require(type(lesson[key]) is str and 0 < len(lesson[key].encode()) <= maximum, 'BOUNDED_LESSON_TEXT_REQUIRED:' + key)
    require(re.fullmatch(r'[a-z][a-z0-9_.-]{0,79}', lesson['key']) is not None, 'LESSON_KEY_REQUIRED')
    require(type(lesson['priority']) is int and 0 <= lesson['priority'] <= 100, 'INTEGER_PRIORITY_REQUIRED')
    return hashlib.sha256(encoded([lesson['scope'], lesson['key']])).hexdigest()


def validate_state(state, root):
    require(type(state) is dict and set(state) == {'schema', 'workspace', 'max_bytes', 'max_lessons', 'lessons'}, 'EXACT_MEMORY_FIELDS_REQUIRED')
    require(state['schema'] == SCHEMA and state['workspace'] == hashlib.sha256(str(root).encode()).hexdigest(), 'WRONG_WORKSPACE_OR_SCHEMA')
    require(type(state['max_bytes']) is int and 4096 <= state['max_bytes'] <= 1048576, 'BOUNDED_MEMORY_BYTES_REQUIRED')
    require(type(state['max_lessons']) is int and 1 <= state['max_lessons'] <= 1024, 'BOUNDED_LESSON_COUNT_REQUIRED')
    rows = state['lessons']
    require(type(rows) is list and len(rows) <= state['max_lessons'], 'MEMORY_COUNT_LIMIT')
    seen = set()
    for row in rows:
        require(type(row) is dict and set(row) == {'id', 'lesson', 'occurrences', 'last_batch'}, 'EXACT_MEMORY_ENTRY_REQUIRED')
        require(row['id'] == validate_lesson(row['lesson']) and row['id'] not in seen, 'LESSON_IDENTITY_CONFLICT')
        require(type(row['occurrences']) is int and 1 <= row['occurrences'] <= 2147483647, 'BOUNDED_OCCURRENCE_COUNTER_REQUIRED')
        require(type(row['last_batch']) is str and re.fullmatch('[0-9a-f]{64}', row['last_batch']), 'BATCH_DIGEST_REQUIRED')
        seen.add(row['id'])
    require(len(encoded(state)) <= state['max_bytes'], 'MEMORY_BYTE_LIMIT')


def atomic_state(directory, state):
    raw = encoded(state)
    require(len(raw) <= state['max_bytes'], 'MEMORY_BYTE_LIMIT')
    # At most one staging copy; no append-only history or backup accumulation.
    try:
        read_regular(directory, NEXT, 1048576)
    except FileNotFoundError:
        pass
    else:
        os.unlink(NEXT, dir_fd=directory)
    fd = os.open(NEXT, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(NEXT, STATE, src_dir_fd=directory, dst_dir_fd=directory)
    os.fsync(directory)


def initialize(path, max_bytes=65536, max_lessons=128):
    root = Path(path).expanduser().absolute()
    require(not root.exists() and not root.is_symlink() and root.parent.is_dir() and '..' not in root.parts, 'NEW_WORKSPACE_REQUIRED')
    require(not any(p.is_symlink() for p in root.parents), 'WORKSPACE_SYMLINK_REFUSED')
    state = {'schema': SCHEMA, 'workspace': hashlib.sha256(str(root).encode()).hexdigest(),
             'max_bytes': max_bytes, 'max_lessons': max_lessons, 'lessons': []}
    validate_state(state, root)
    root.mkdir(mode=0o700)
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
        os.close(fd)
        atomic_state(directory, state)
    finally:
        os.close(directory)
    return {'workspace': str(root), 'max_bytes': max_bytes, 'max_lessons': max_lessons}


def learn_delete(path, lesson, files):
    """Durably retain a supplied lesson, then delete exact explicitly named raw logs.

    Only raw-*.log/stdout/stderr in a dedicated initialized workspace are eligible.
    No recursion, globbing, archives, JSON, source, account, keys or checkpoints.
    """
    lesson_id = validate_lesson(lesson)
    require(type(files) is list and 1 <= len(files) <= 16, 'BOUNDED_EXPLICIT_DIAGNOSTIC_LIST_REQUIRED')
    names = set()
    for item in files:
        require(type(item) is dict and set(item) == {'name', 'sha256'}, 'EXACT_DIAGNOSTIC_FIELDS_REQUIRED')
        name = item['name']
        require(type(name) is str and re.fullmatch(r'raw-[a-zA-Z0-9_.-]{1,80}\.(log|stdout|stderr)', name), 'ONLY_MANAGED_RAW_LOGS_CAN_BE_REMOVED')
        require(name not in names, 'DUPLICATE_DIAGNOSTIC')
        require(type(item['sha256']) is str and re.fullmatch('[0-9a-f]{64}', item['sha256']), 'EXPECTED_CONTENT_DIGEST_REQUIRED')
        names.add(name)
    batch = hashlib.sha256(encoded(sorted(files, key=lambda x: x['name']))).hexdigest()
    with workspace(path) as (root, directory):
        state = load(read_regular(directory, STATE, 1048576)[0])
        validate_state(state, root)
        old = next((x for x in state['lessons'] if x['id'] == lesson_id), None)
        require(old is None or encoded(old['lesson']) == encoded(lesson), 'LESSON_KEY_CONFLICT_USE_NEW_KEY_FOR_CHANGED_RULE')
        already_learned = old is not None and old['last_batch'] == batch
        pending = []
        for item in files:
            try:
                raw, info = read_regular(directory, item['name'], MAX_RAW)
            except FileNotFoundError:
                require(already_learned, 'MISSING_UNLEARNED_DIAGNOSTIC')
                continue
            require(hashlib.sha256(raw).hexdigest() == item['sha256'], 'DIAGNOSTIC_CONTENT_CHANGED')
            pending.append((item['name'], info))
        rows = [x for x in state['lessons'] if x['id'] != lesson_id]
        rows.append({'id': lesson_id, 'lesson': lesson,
                     'occurrences': min(2147483647, (old['occurrences'] if old else 0) + int(not already_learned)),
                     'last_batch': batch})
        state['lessons'] = rows
        evicted = 0
        # The new lesson is retained before deletion; oldest low-priority lessons leave first.
        while len(rows) > state['max_lessons'] or len(encoded(state)) > state['max_bytes']:
            require(len(rows) > 1, 'LESSON_TOO_LARGE_FOR_MEMORY')
            index = min(range(len(rows) - 1), key=lambda i: (rows[i]['lesson']['priority'], i))
            rows.pop(index); evicted += 1
        validate_state(state, root)
        atomic_state(directory, state)
        removed, byte_count = [], 0
        for name, before in pending:
            after = os.stat(name, dir_fd=directory, follow_symlinks=False)
            require(identity(before) == identity(after) and stat.S_ISREG(after.st_mode), 'DIAGNOSTIC_CHANGED_BEFORE_DELETE')
            os.unlink(name, dir_fd=directory)
            removed.append(name); byte_count += before.st_size
        os.fsync(directory)
        return {'scope': 'LOSSY_DIAGNOSTIC_LEARNING_ONLY', 'lesson_id': lesson_id,
                'lessons_retained': len(rows), 'memory_bytes': len(encoded(state)),
                'evicted_lessons': evicted, 'deleted_files': removed, 'deleted_bytes': byte_count,
                'exact_replay_available': False, 'financial_records_modified': False,
                'execution_authority': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init'); init.add_argument('--workspace', required=True)
    init.add_argument('--max-bytes', type=int, default=65536); init.add_argument('--max-lessons', type=int, default=128)
    clean = sub.add_parser('learn-delete'); clean.add_argument('--workspace', required=True)
    clean.add_argument('--request', required=True, help='Data-only JSON containing lesson and files with expected SHA-256.')
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            result = initialize(args.workspace, args.max_bytes, args.max_lessons)
        else:
            with open(args.request, 'rb') as stream:
                raw = stream.read(65537)
            require(len(raw) <= 65536, 'BOUNDED_REQUEST_REQUIRED')
            request = load(raw)
            require(type(request) is dict and set(request) == {'lesson', 'files'}, 'EXACT_REQUEST_REQUIRED')
            result = learn_delete(args.workspace, **request)
        print(json.dumps(result, sort_keys=True)); return 0
    except (ValueError, OSError, TypeError, KeyError, RecursionError) as error:
        print(type(error).__name__ + ': ' + str(error), file=__import__('sys').stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())
