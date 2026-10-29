"""Evidence-grounded criticism, independent reproduction and typed obligations.

The immutable specification belongs to the caller/verifier, never the candidate.
Reproduction is procedural separation on shared infrastructure, not certification.
Only reproduced defects in the supported effect semantics yield repair obligations.
"""
import copy
import hashlib
import json
import re


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _seal(record, field):
    record[field] = digest(record)
    return record


def _valid_seal(record, field):
    return isinstance(record, dict) and record.get(field) == digest({k: v for k, v in record.items() if k != field})


def _source_valid(identity):
    if isinstance(identity, str):
        return bool(re.fullmatch('[0-9a-f]{64}', identity))
    if isinstance(identity, dict):
        return any(_source_valid(v) for v in identity.values())
    return False


def _task_phases(task):
    phases = task.get('phases')
    if not isinstance(phases, list) or not phases:
        raise ValueError('MISSING_TYPED_PHASES')
    indexed = {}
    for phase in phases:
        if not isinstance(phase, dict) or not isinstance(phase.get('id'), str) or not phase['id']:
            raise ValueError('INVALID_PHASE')
        if phase['id'] in indexed or not isinstance(phase.get('deps'), list):
            raise ValueError('DUPLICATE_OR_UNTYPED_PHASE')
        indexed[phase['id']] = phase
    if any(d not in indexed for phase in phases for d in phase['deps']):
        raise ValueError('UNKNOWN_DEPENDENCY')
    return indexed


def _evaluate(task, execution, specification):
    phases = _task_phases(task)
    if not isinstance(execution, dict):
        return [], ['MISSING_EXECUTION_EVIDENCE']
    required = ('trace', 'state', 'completed', 'interrupted_marker')
    if any(k not in execution for k in required):
        return [], ['MISSING_EXECUTION_FIELDS']
    if not isinstance(execution['trace'], list) or any(p not in phases for p in execution['trace']):
        return [], ['UNKNOWN_TRACE_PHASE']
    if type(execution['completed']) is not bool or type(execution['interrupted_marker']) is not bool:
        return [], ['INVALID_OBSERVATION_TYPES']
    if execution['state'] not in ('COMPLETE', 'INCOMPLETE', 'UNMARKED', 'INTERRUPTED', 'FAILED'):
        return [], ['UNSUPPORTED_EXECUTION_STATE']
    failure = execution.get('failure_at', execution.get('failed_phase'))
    if execution.get('failure_at') is not None and execution.get('failed_phase') is not None and execution['failure_at'] != execution['failed_phase']:
        return [], ['CONFLICTING_FAILURE_LOCATIONS']
    if failure is not None and failure not in phases:
        return [], ['UNKNOWN_FAILURE_LOCATION']
    if execution['state'] == 'COMPLETE' and not execution['completed']:
        return [], ['CONFLICTING_TERMINAL_STATE']
    invariants = specification.get('invariants') if isinstance(specification, dict) else None
    if not isinstance(invariants, list) or not invariants:
        return [], ['MISSING_IMMUTABLE_SPECIFICATION']
    if any(not isinstance(i, dict) or not i.get('id') or not i.get('kind') for i in invariants):
        return [], ['INVALID_INVARIANT']
    if len({i['id'] for i in invariants}) != len(invariants):
        return [], ['CONFLICTING_INVARIANT_IDENTITIES']
    supported = {'mark_after_reservation', 'no_commit_on_failure', 'release_after_failure', 'required_effect_available'}
    if any(i['kind'] not in supported for i in invariants):
        return [], ['UNSUPPORTED_INVARIANT']
    if any(i.get('required_state', 'INCOMPLETE') != 'INCOMPLETE' for i in invariants):
        return [], ['CONFLICTING_FAILURE_REQUIREMENT']
    if failure is None:
        if execution['state'] != 'COMPLETE' or not execution['completed']:
            return [], ['MISSING_FAILURE_LOCATION']
        return [], []
    trace = execution['trace']
    reserved = execution.get('reserved', [])
    if not isinstance(reserved, list) or any(p not in phases or phases[p].get('kind') != 'reserve' for p in reserved):
        return [], ['INVALID_RESERVATION_WITNESS']
    custody = bool(reserved) or any(phases[p].get('kind') == 'reserve' for p in trace)
    explicit_custody = execution.get('directory_created', execution.get('reservation_created'))
    if explicit_custody is not None:
        if type(explicit_custody) is not bool or (explicit_custody is False and custody):
            return [], ['CONFLICTING_RESERVATION_WITNESS']
        custody = custody or explicit_custody
    if 'interrupted_exists' in execution and execution['interrupted_exists'] != execution['interrupted_marker']:
        return [], ['CONFLICTING_INTERRUPTION_WITNESS']
    if execution['interrupted_marker'] and execution['state'] == 'UNMARKED':
        return [], ['CONFLICTING_INTERRUPTION_STATE']
    if execution['completed'] and execution.get('complete_exists') is False:
        return [], ['CONFLICTING_COMPLETION_WITNESS']
    issues = []
    for invariant in invariants:
        selection = invariant.get('phase_ids', list(phases))
        if not isinstance(selection, list) or any(p not in phases for p in selection):
            return [], ['INVALID_INVARIANT_SCOPE']
        if failure not in selection:
            continue
        kind = invariant['kind']
        if kind == 'required_effect_available':
            effect = invariant.get('effect')
            observations = execution.get('effect_observations')
            if not isinstance(effect, str) or not effect or not isinstance(observations, list):
                return [], ['MISSING_EFFECT_MEASUREMENT']
            matching = [o for o in observations if isinstance(o, dict) and o.get('phase_id') == failure and o.get('effect') == effect]
            if len(matching) != 1 or type(matching[0].get('available')) is not bool:
                return [], ['MISSING_OR_CONFLICTING_EFFECT_MEASUREMENT']
            observation = matching[0]
            if not _source_valid(observation.get('input_sha256')):
                return [], ['MISSING_EFFECT_INPUT_IDENTITY']
            if observation['available'] is False:
                error = observation.get('error')
                if not isinstance(error, dict) or not isinstance(error.get('type'), str) or not error['type'] or not isinstance(error.get('message'), str) or not _source_valid(observation.get('input_sha256')):
                    return [], ['MISSING_EFFECT_FAILURE_EVIDENCE']
                issues.append({'invariant_id': invariant['id'], 'kind': kind, 'phase_ids': [failure],
                               'repairable': False, 'required_effect': effect,
                               'finding': 'A required effect is unavailable on the source-bound input under the declared runtime.',
                               'repair_boundary': 'The event-plan rewrite language cannot construct this missing operational capability.',
                               'effect_observation': copy.deepcopy(observation)})
        if kind == 'mark_after_reservation' and custody and not execution['interrupted_marker']:
            issues.append({'invariant_id': invariant['id'], 'kind': kind,
                           'phase_ids': [failure], 'repairable': True,
                           'finding': 'An interrupted effect under established reservation lacks its required incomplete marker.'})
        if kind == 'no_commit_on_failure':
            artifact = invariant.get('artifact')
            visible = execution['completed'] or execution.get('partial_publication') is True or execution.get('complete_exists') is True or execution.get('terminal_visible') is True
            if artifact:
                visible = visible or any(artifact in execution.get(key, {}) for key in ('present_files', 'files_sha256', 'artifacts'))
            if visible:
                affected = [failure] if phases[failure].get('kind') == 'commit' else [p for p in trace if phases[p].get('kind') == 'commit']
                repairable = len(affected) == 1 and affected[0] == failure
                issues.append({'invariant_id': invariant['id'], 'kind': kind,
                               'phase_ids': affected, 'repairable': repairable,
                               'finding': 'A failed execution exposes a successful or partial terminal publication.',
                               'repair_boundary': None if repairable else 'Failure is outside the publishing phase; atomic publication alone cannot satisfy this specification.'})
        if kind == 'release_after_failure':
            compensated = execution.get('compensated')
            if not isinstance(compensated, list):
                return [], ['MISSING_COMPENSATION_WITNESS']
            outstanding = sorted(set(reserved) - set(compensated))
            if outstanding:
                issues.append({'invariant_id': invariant['id'], 'kind': kind,
                               'phase_ids': [failure], 'resource_phase_ids': outstanding, 'repairable': True,
                               'finding': 'The interrupted execution leaves declared reservations uncompensated.'})
    return issues, []


def critique(task, candidate, execution, specification, source_identity):
    """Challenge observed claims against the supplied frozen semantic specification."""
    frozen = copy.deepcopy({'task': task, 'candidate': candidate, 'execution': execution,
                            'specification': specification, 'source_identity': source_identity})
    bindings = {name + '_sha256': digest(value) for name, value in frozen.items()}
    issues, gaps = _evaluate(task, execution, specification)
    if not _source_valid(source_identity):
        gaps.append('MISSING_EXACT_SOURCE_IDENTITY')
    if gaps:
        issues = [{'finding': 'Evidence cannot establish a supported consequential defect.', 'kind': None,
                   'phase_ids': [], 'repairable': False, 'gaps': gaps}]
    elif not issues:
        issues = [{'finding': 'No defect established for the observed run and declared invariants.',
                   'kind': None, 'phase_ids': [], 'repairable': False}]
    records = []
    for issue in issues:
        status = 'unresolved' if gaps else ('proposed' if issue['kind'] else 'no_defect')
        failure = execution.get('failure_at', execution.get('failed_phase')) if isinstance(execution, dict) else None
        stage = execution.get('interrupt_stage', 'during' if execution.get('partial_publication') else 'before') if isinstance(execution, dict) else None
        records.append(_seal({'schema': 'agi-alpha-evidence-criticism/v1', 'status': status,
                    'claim_challenged': issue.get('invariant_id'), 'issue': issue,
                    'evidence': frozen, 'bindings': bindings,
                    'reproduction': {'interrupt_at': failure, 'interrupt_stage': stage},
                    'expected_failure': issue['finding'] if issue['kind'] else None,
                    'severity': 'consequential' if issue['kind'] else 'undetermined',
                    'uncertainty': 'Single observed execution; a separate reproduction is required.'}, 'objection_sha256'))
    return records


def adjudicate(objection, reproducer):
    """Reproduce with copies of the frozen task/candidate; never modify the candidate."""
    result = {'schema': 'agi-alpha-criticism-adjudication/v1', 'objection': copy.deepcopy(objection),
              'status': 'unresolved', 'reason': None, 'independence': 'Separate reproducer; shared host/libraries, not external certification.'}
    if not _valid_seal(objection, 'objection_sha256'):
        result['reason'] = 'OBJECTION_IDENTITY_MISMATCH'
        return _seal(result, 'adjudication_sha256')
    frozen = objection['evidence']
    if any(objection['bindings'].get(k + '_sha256') != digest(v) for k, v in frozen.items()):
        result['reason'] = 'EVIDENCE_IDENTITY_MISMATCH'
        return _seal(result, 'adjudication_sha256')
    if objection['status'] == 'unresolved':
        result['reason'] = 'MISSING_OR_CONFLICTING_EVIDENCE'
        return _seal(result, 'adjudication_sha256')
    task, candidate = copy.deepcopy(frozen['task']), copy.deepcopy(frozen['candidate'])
    before = (digest(task), digest(candidate))
    try:
        reproduced = reproducer(task, candidate, objection['reproduction']['interrupt_at'])
        result['reproduced_execution'] = copy.deepcopy(reproduced)
        result['reproduced_execution_sha256'] = digest(reproduced)
    except Exception as error:
        result['reason'] = 'REPRODUCTION_UNAVAILABLE: ' + type(error).__name__ + ': ' + str(error)
        return _seal(result, 'adjudication_sha256')
    if before != (digest(task), digest(candidate)):
        result['reason'] = 'REPRODUCER_MODIFIED_FROZEN_INPUT'
        return _seal(result, 'adjudication_sha256')
    reproduced_failure = reproduced.get('failure_at', reproduced.get('failed_phase'))
    if reproduced_failure != objection['reproduction']['interrupt_at']:
        result['reason'] = 'REPRODUCTION_PROCEDURE_MISMATCH'
        return _seal(result, 'adjudication_sha256')
    if reproduced.get('interrupt_stage', objection['reproduction']['interrupt_stage']) != objection['reproduction']['interrupt_stage']:
        result['reason'] = 'REPRODUCTION_STAGE_MISMATCH'
        return _seal(result, 'adjudication_sha256')
    expected_candidate = objection['bindings']['candidate_sha256']
    if reproduced.get('candidate_sha256', expected_candidate) != expected_candidate:
        result['reason'] = 'STALE_CANDIDATE_REPRODUCTION'
        return _seal(result, 'adjudication_sha256')
    for name in ('task_sha256', 'specification_sha256', 'source_identity_sha256'):
        if reproduced.get(name, objection['bindings'][name]) != objection['bindings'][name]:
            result['reason'] = 'STALE_BOUND_REPRODUCTION: ' + name
            return _seal(result, 'adjudication_sha256')
    issues, gaps = _evaluate(frozen['task'], reproduced, frozen['specification'])
    original_effect = objection['issue'].get('effect_observation')
    if original_effect is not None and isinstance(reproduced.get('effect_observations'), list):
        same_effect = [o for o in reproduced['effect_observations'] if isinstance(o, dict) and
                       (o.get('phase_id'), o.get('effect')) == (original_effect['phase_id'], original_effect['effect'])]
        if same_effect and any(o.get('input_sha256') != original_effect['input_sha256'] for o in same_effect):
            result['reason'] = 'REPRODUCTION_EFFECT_INPUT_MISMATCH'
            return _seal(result, 'adjudication_sha256')
    if gaps:
        result['reason'] = 'UNRESOLVED_REPRODUCTION: ' + ','.join(gaps)
    elif objection['status'] == 'no_defect':
        result['status'] = 'no_defect' if not issues else 'unresolved'
        result['reason'] = 'NO_DEFECT_ESTABLISHED' if not issues else 'NO_DEFECT_OBSERVATION_DID_NOT_REPRODUCE'
    else:
        expected = objection['issue']
        matches = [i for i in issues if (i['kind'], i['invariant_id'], i['phase_ids']) ==
                   (expected['kind'], expected['invariant_id'], expected['phase_ids'])]
        result['status'] = 'established' if matches else 'refuted'
        result['reason'] = 'CONSEQUENTIAL_DEFECT_REPRODUCED' if matches else 'CLAIMED_DEFECT_NOT_REPRODUCED'
        if matches:
            result['established_issue'] = matches[0]
            result['next_action'] = 'derive_repair' if matches[0].get('repairable') else 'needs_instrument'
    return _seal(result, 'adjudication_sha256')


def derive(adjudication, task):
    """Turn only established, task-bound defects into supported repair obligations."""
    if not _valid_seal(adjudication, 'adjudication_sha256'):
        raise ValueError('ADJUDICATION_IDENTITY_MISMATCH')
    if adjudication.get('status') != 'established':
        return []
    objection = adjudication['objection']
    if digest(task) != objection['bindings']['task_sha256']:
        raise ValueError('STALE_TASK_APPLICABILITY')
    _task_phases(task)
    issue = adjudication['established_issue']
    if not issue.get('repairable'):
        raise ValueError('UNREPAIRABLE_IN_DECLARED_LANGUAGE')
    operators = {'mark_after_reservation': 'protect', 'no_commit_on_failure': 'atomic_publish',
                 'release_after_failure': 'compensate'}
    if issue['kind'] not in operators or not issue['phase_ids']:
        raise ValueError('UNSUPPORTED_REPAIR_OBLIGATION')
    obligation = {'kind': operators[issue['kind']], 'phase_ids': list(issue['phase_ids']), 'status': 'established',
                  'provenance': {'status': 'established', 'invariant_id': issue['invariant_id'],
                                 'adjudication_sha256': adjudication['adjudication_sha256'],
                                 'objection_sha256': objection['objection_sha256'],
                                 'source_identity_sha256': objection['bindings']['source_identity_sha256'],
                                 'candidate_sha256': objection['bindings']['candidate_sha256'],
                                 'specification_sha256': objection['bindings']['specification_sha256'],
                                 'original_witness_sha256': objection['bindings']['execution_sha256'],
                                 'reproduced_witness_sha256': adjudication['reproduced_execution_sha256']}}
    if 'resource_phase_ids' in issue:
        obligation['resource_phase_ids'] = issue['resource_phase_ids']
    return [obligation]


def instrument_spec(adjudication, task, available_effects):
    """Specify a missing instrument/measurement; this function builds no tool.

    Specifications cannot certify their own proposed measurements or weaken the
    original objective. An implementation and a fresh verifier receipt are still
    required, including when the missing effect is a dependency-removing method.
    """
    if not _valid_seal(adjudication, 'adjudication_sha256'):
        raise ValueError('ADJUDICATION_IDENTITY_MISMATCH')
    if not isinstance(available_effects, list) or len(available_effects) > 64 or any(not isinstance(e, str) or not e for e in available_effects) or len(set(available_effects)) != len(available_effects):
        raise ValueError('AVAILABLE_EFFECTS_SCHEMA')
    objection = adjudication['objection']
    if not _valid_seal(objection, 'objection_sha256') or digest(task) != objection['bindings']['task_sha256']:
        raise ValueError('STALE_TASK_OR_OBJECTION_APPLICABILITY')
    _task_phases(task)
    state = adjudication.get('status')
    if state not in ('established', 'unresolved'):
        return _seal({'schema': 'agi-alpha-missing-instrument-spec/v1', 'status': 'not_required',
                      'built': False, 'adjudication_status': state,
                      'adjudication_sha256': adjudication['adjudication_sha256']}, 'instrument_spec_sha256')
    if state == 'unresolved' and adjudication.get('reason') != 'MISSING_OR_CONFLICTING_EVIDENCE':
        return _seal({'schema': 'agi-alpha-missing-instrument-spec/v1', 'status': 'refused', 'built': False,
                      'reason': 'Resolve stale identity or reproduction procedure before proposing a new instrument.',
                      'adjudication_sha256': adjudication['adjudication_sha256']}, 'instrument_spec_sha256')
    issue = adjudication.get('established_issue', objection['issue'])
    operators = {'mark_after_reservation': 'protect', 'no_commit_on_failure': 'atomic_publish',
                 'release_after_failure': 'compensate'}
    direct = operators.get(issue.get('kind'))
    if state == 'established' and issue.get('repairable') and direct in available_effects:
        return _seal({'schema': 'agi-alpha-missing-instrument-spec/v1', 'status': 'direct_repair_available',
                      'built': False, 'repair_effect': direct,
                      'adjudication_sha256': adjudication['adjudication_sha256']}, 'instrument_spec_sha256')
    measurement = state == 'unresolved'
    required = issue.get('required_effect') or (direct if issue.get('repairable') else 'satisfy:' + str(issue.get('kind')))
    original = objection['evidence']
    requirements = ([{'kind': 'measure', 'evidence_gaps': copy.deepcopy(issue.get('gaps', [])),
                      'observable': 'The original source identity, execution trace, failure location and invariant-specific effect evidence.',
                      'acceptance_authority': 'Measurement is evidence only; the frozen verifier decides the unchanged claim.'}]
                    if measurement else [{'kind': 'provide_effect', 'effect': required,
                                          'phase_ids': list(issue['phase_ids']),
                                          'failure_boundary': issue.get('repair_boundary'),
                                          'input_sha256': issue.get('effect_observation', {}).get('input_sha256'),
                                          'allows_dependency_removal': True}])
    specification = {'schema': 'agi-alpha-missing-instrument-spec/v1', 'status': 'needs_instrument',
                     'instrument_kind': 'measurement' if measurement else 'operational_capability',
                     'built': False, 'verified': False, 'defect_established': state == 'established',
                     'adjudication_status': state, 'task_id': task['id'],
                     'requirements': requirements, 'available_effects': sorted(available_effects),
                     'available_effects_sha256': digest(sorted(available_effects)),
                     'missing_effects': [] if measurement else ([required] if required not in available_effects else []),
                     'preserved_objective': {'task_sha256': objection['bindings']['task_sha256'],
                                            'specification_sha256': objection['bindings']['specification_sha256'],
                                            'specification': copy.deepcopy(original['specification']),
                                            'may_change_judge': False, 'may_weaken_thresholds': False},
                     'bindings': copy.deepcopy(objection['bindings']) | {
                         'objection_sha256': objection['objection_sha256'],
                         'adjudication_sha256': adjudication['adjudication_sha256'],
                         'reproduced_witness_sha256': adjudication.get('reproduced_execution_sha256')},
                     'operational_falsifier': {
                         'procedure': 'Reexecute the frozen source-bound input and original failing operation with the constructed instrument, then run the unchanged independent specification on that operation and fresh applicable cases.',
                         'original_failure': copy.deepcopy(objection['reproduction']),
                         'reject_if': ['The original required outcome or any previously satisfied invariant fails.',
                                       'The supposedly removed dependency is still necessary in the declared environment.',
                                       'The evaluator, admitted input, acceptance threshold or source identity changes without a separately identified experiment.',
                                       'The instrument supplies a favorable measurement without reproducible source-bound observations.'],
                         'required_receipts': ['Exact constructed source and dependency hashes', 'Actual bounded execution and resource record',
                                               'Original unchanged-verifier result', 'Fresh-case result with exposure recorded'],
                         'claim_limit': 'A specification or proposed measurement is not a constructed or verified instrument.'},
                     'authority': 'No execution, access, spending or deployment authority is added.',
                     'origin': 'Executable projection of a witnessed gap into a supplied typed instrument-specification schema.'}
    return _seal(specification, 'instrument_spec_sha256')


def response(adjudication, task, available_effects):
    """Make the constructive continuation explicit when direct repair is absent."""
    specification = instrument_spec(adjudication, task, available_effects)
    if specification['status'] == 'direct_repair_available':
        return {'status': 'repair_obligations', 'obligations': derive(adjudication, task),
                'instrument_specification': None}
    return {'status': specification['status'], 'obligations': [],
            'instrument_specification': specification}
