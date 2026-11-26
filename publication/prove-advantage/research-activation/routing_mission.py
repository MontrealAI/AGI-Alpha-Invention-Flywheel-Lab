"""Run the registered routing study through the existing local HARNESS journal."""

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import monotonic

from router_ceiling import SOURCE_REVISION, SOURCE_URL, case_aligned_ceiling, matched_panels


ROOT = Path(__file__).resolve().parents[3]
DATASET = 'frozen-matched-routing-outcomes'
ARTIFACT = 'routing-ceiling.json'
TABLE_SCHEMA = {'outcomes': {'panel': 'TEXT', 'case_id': 'TEXT', 'arm': 'TEXT', 'accepted': 'INTEGER'}}
SQL = '''WITH arm_totals AS (
    SELECT panel, arm, SUM(accepted) AS wins FROM outcomes GROUP BY panel, arm
), best AS (
    SELECT panel, MAX(wins) AS fixed_wins FROM arm_totals GROUP BY panel
), case_outcomes AS (
    SELECT panel, case_id, MAX(accepted) AS possible_win FROM outcomes GROUP BY panel, case_id
), possible AS (
    SELECT panel, COUNT(*) AS cases, SUM(possible_win) AS oracle FROM case_outcomes GROUP BY panel
)
SELECT possible.panel, cases, fixed_wins, oracle, oracle - fixed_wins AS headroom
FROM possible JOIN best ON possible.panel = best.panel ORDER BY possible.panel'''


def operate():
    from bridge.universal_missions import UniversalMissionService
    from bridge.workflow_demo import FixtureRuntime

    started = monotonic()
    panels = matched_panels()
    rows = [{'panel': panel, 'case_id': case, 'arm': arm, 'accepted': int(outcome[case])}
            for panel, (case_ids, arms) in panels.items() for arm, outcome in arms.items() for case in case_ids]
    cohorts = {panel: case_aligned_ceiling(*spec) for panel, spec in panels.items()}
    fields = ('cases', 'best_fixed_accepted', 'oracle_accepted', 'oracle_gain_cases')
    expected = [[panel, *(cohort[field] for field in fields)] for panel, cohort in sorted(cohorts.items())]
    proposal = {
        'summary': 'Measure the largest possible acceptance gain from selecting among the frozen answer sets.',
        'done': True,
        'actions': [
            {'tool': 'construct_table', 'name': ARTIFACT, 'schema': TABLE_SCHEMA, 'sql': SQL},
            {'tool': 'run_table', 'name': ARTIFACT, 'input': {'dataset': DATASET}},
        ],
    }
    spec = {'ambition': 'Determine whether frozen answer portfolios contain case-level quality headroom for routing.',
            'language': 'en', 'provider': 'fixture', 'model': 'operator-authored-routing-study',
            'expires_at': (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            'max_turns': 1, 'max_actions': 2, 'max_output_tokens': 1024, 'local_only': True,
            'tools': ['construct_table', 'run_table'],
            'requirements': {'approved_tables': {DATASET: {'outcomes': rows}}}}
    with TemporaryDirectory(prefix='frontier-routing-') as workspace:
        service = UniversalMissionService(FixtureRuntime([proposal]), Path(workspace))
        try:
            opened = service.submit(spec)
            view = service.step(opened['id'])
            executions = [event['detail']['outcome'] for event in view['events'] if event['kind'] == 'tool_completed'
                          and event['detail'].get('tool') == 'run_table']
            if view['status'] != 'needs_review' or len(executions) != 1 or executions[0].get('rows') != expected:
                raise RuntimeError('HARNESS did not return the registered result against the conventional replay.')
        finally:
            service.close()
    output = executions[0]
    return {'schema': 'frontier/routeability-ceiling-v1', 'source_revision': SOURCE_REVISION,
            'source_url': SOURCE_URL, 'cohorts': cohorts, 'paid_requests': 0, 'matched_complete_cost_available': False,
            'harness': {'status': view['status'], 'qualification': view['qualification'], 'actions': view['actions'],
                        'mode': 'OPERATOR_AUTHORED_TRANSPORT_NO_MODEL_INFERENCE', 'rows': output['rows'],
                        'artifact_sha256': output['artifact_sha256'], 'input_sha256': output['input_sha256'],
                        'evaluator_sha256': output['evaluator_sha256'], 'outcomes': len(rows)},
            'local_wall_seconds': round(monotonic() - started, 6)}


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT / 'products/alpha-genesis-harness'))
    print(json.dumps(operate(), indent=2))
