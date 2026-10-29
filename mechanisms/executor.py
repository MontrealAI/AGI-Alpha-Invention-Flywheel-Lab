"""Fixed, bounded local-file effects for a validated confined strategy plan."""
import hashlib
import json
import os
from pathlib import Path
from .construct import validate, validate_task


def admit(task):
    nodes = validate_task(task)
    reserve = [p for p in nodes if nodes[p]['kind'] == 'reserve']
    commit = [p for p in nodes if nodes[p]['kind'] == 'commit']
    if len(reserve) != 1 or len(commit) != 1:
        raise ValueError('UNSUPPORTED_BROKER_EFFECT_CLASS: exactly one reservation and terminal publication')
    def ancestors(phase):
        pending, found = list(nodes[phase]['deps']), set()
        while pending:
            previous = pending.pop()
            if previous not in found:
                found.add(previous)
                pending.extend(nodes[previous]['deps'])
        return found
    if set(nodes) - {commit[0]} != ancestors(commit[0]) or any(reserve[0] not in ancestors(p) for p in nodes if p != reserve[0]):
        raise ValueError('UNSUPPORTED_BROKER_EFFECT_CLASS: reservation must precede all effects and publication must be terminal')
    return True


def execute(task, program, output, interrupt_at=None):
    validate(task, program)
    admit(task)
    if interrupt_at is not None and interrupt_at not in program['order']:
        raise ValueError('UNKNOWN_INTERRUPTION')
    output = Path(output)
    phases = {p['id']: p for p in task['phases']}
    trace, files, owned = [], {}, False
    for index, identity in enumerate(program['order']):
        phase = phases[identity]
        if phase['kind'] == 'reserve':
            if interrupt_at == identity:
                return {'state': 'UNMARKED', 'completed': False, 'directory_created': False,
                        'reserved': [], 'failure_at': identity, 'trace': [], 'interrupted_marker': False,
                        'partial_publication': False, 'complete_exists': False, 'files_sha256': {}}
            output.mkdir(parents=True, exist_ok=False)
            owned = True
            trace.append(identity)
            continue
        try:
            commit = phase['kind'] == 'commit'
            leaf = output / ('COMPLETE.json' if commit else 'phase-%03d.json' % index)
            pending = output / 'PENDING_COMPLETE.json' if commit and identity in program['atomic'] else leaf
            with pending.open('x') as stream:
                if interrupt_at == identity:
                    raise KeyboardInterrupt('actual exclusive-write interruption')
                json.dump({'phase': identity, 'kind': phase['kind'], 'task': task['id']}, stream, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            if commit and pending != leaf:
                os.link(pending, leaf)
            trace.append(identity)
        except BaseException as error:
            marked = owned and identity in program['protected']
            if marked:
                with (output / 'INTERRUPTED.json').open('x') as stream:
                    json.dump({'state': 'INCOMPLETE', 'failure_at': identity, 'reason': type(error).__name__}, stream)
            compensated = program.get('compensations', {}).get(identity, [])
            if compensated:
                with (output / 'COMPENSATIONS.json').open('x') as stream:
                    json.dump({'declared_local_reservations': compensated}, stream)
            files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
            return {'state': 'INCOMPLETE' if marked else 'UNMARKED', 'completed': False,
                    'directory_created': owned, 'reserved': [p for p in trace if phases[p]['kind'] == 'reserve'], 'failure_at': identity, 'trace': trace,
                    'interrupted_marker': marked, 'partial_publication': phase['kind'] == 'commit' and 'COMPLETE.json' in files,
                    'complete_exists': 'COMPLETE.json' in files, 'files_sha256': files, 'compensated': compensated,
                    'boundary': 'Trusted fixed local effects, no proposed paths/code/network; not host-crash durability'}
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    return {'state': 'COMPLETE', 'completed': True, 'directory_created': owned, 'reserved': [p for p in trace if phases[p]['kind'] == 'reserve'],
            'trace': trace, 'interrupted_marker': False, 'partial_publication': False,
            'complete_exists': 'COMPLETE.json' in files, 'files_sha256': files, 'compensated': []}
