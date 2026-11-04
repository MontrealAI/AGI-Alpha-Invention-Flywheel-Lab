"""Small final-publication source/receipt review; never imports candidate code.

Run only under the parent-assigned final review allocation. This performs no
numerical replay, no network access and no writes to the candidate repository.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import time

SOURCE = '2205bf896b6c72e109b56f6521207a90ff468bcc'
DATA = '5d5fb96d1421d5c1f5fd6cf8ea6c96fcfbd5b045'
CHECKER = 'dd2dc7438bd5740ea082b011da40762cd342666b35d7ccab4fb83bfa89fd1693'
CANDIDATE = '48cd04ae4bf6447d952c89e16c45d7ac2353bb3c105e3e6af9100f1fe5887ac1'
CONTROLLER = 'c613ffcd64bac059c099083e7c524f005803b5cf828be8300b648f54bdd29d8a'


def load(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    start = time.process_time()
    a.output.mkdir(parents=True, exist_ok=False)
    repo = a.base / 'lab'
    actual = a.base / 'nasa-public-2205-bound'
    report = load(actual / 'artifacts/REPORT.json')
    receipt = load(actual / 'RECEIPT.json')
    separate = load(actual / 'artifacts/separate-review/REPORT.json')
    phases = load(actual / 'artifacts/PHASES.json')
    tree = subprocess.check_output(
        ['git', 'ls-tree', '-r', '--full-tree', SOURCE], cwd=repo, text=True)
    expected = {x.split('\t', 1)[1]: x.split()[2] for x in tree.splitlines()}
    supplied = load(a.base / 'source2205-expected.json')
    helpers = [a.base / 'verification_recovery/check_nasa_coordinate_repair.py',
               repo / 'evidence/overnight-008/verifier-final-repair/check_nasa_coordinate_repair.py',
               actual / 'artifacts/downloaded-source/evidence/overnight-008/verifier-final-repair/check_nasa_coordinate_repair.py']
    checks = {
        'source_expected_tree_matches_local_public_git_object': expected == supplied,
        'source_tree_8588_files': len(expected) == 8588,
        'report_commit_pair': report['source_commit'] == SOURCE and report['data_commit'] == DATA,
        'actual_receipt_complete': receipt['state'] == 'complete' and receipt['exit_code'] == 0,
        'receipt_reports_no_surviving_descendants': receipt['descendant_survivors'] is False,
        'top_report_contains_actual_separate_report': report['separate_review'] == separate,
        'top_report_contains_actual_phase_record': report['phases'] == phases,
        'three_actual_phases_return_zero': [x['phase'] for x in phases] == ['restore', 'repair', 'separate-review'] and all(x['returncode'] == 0 for x in phases),
        'separate_30_checks_explicitly_true': len(separate['checks']) == 30 and all(x is True for x in separate['checks'].values()) and separate['all_checks_passed'] is True,
        'original_reviewer_public_and_downloaded_checker_bytes_match': all(sha(x) == CHECKER for x in helpers),
        'separate_report_binds_reviewed_checker_and_candidate': separate['verifier_source_sha256'] == CHECKER and separate['source_sha256'] == CANDIDATE,
        'candidate_source_identity': sha(repo / 'research/nasa008/coordinate-r2/repair.py') == CANDIDATE,
        'controller_snapshot_matches_reviewed_driver': sha(repo / 'verification/replay_nasa_public008.py') == CONTROLLER and sha(repo / 'evidence/overnight-008/nasa-public-2205/CONTROLLER.py.txt') == CONTROLLER,
        'staged_nasa_report_equals_actual_report': load(repo / 'evidence/overnight-008/nasa-public-2205/REPORT.json') == report,
        'actual_report_discloses_historical_receipts_are_only_inputs': report['restored']['historical_receipts_are_inputs_not_new_execution_receipts'] is True,
        'actual_report_reports_all_47_restored_and_source_unchanged': report['restored']['restored_original_files'] == 47 and report['restored']['all_original_hashes_match'] is True and report['source_bytes_unchanged'] is True,
    }
    economics = load(repo / 'campaign/overnight-008/economics/recovery/FINAL_COST_SNAPSHOT_EVENT28.json')
    checks['economic_snapshot_has_unknown_profit_zero_earned_funds_and_no_funding'] = (
        economics['complete_profit_USD'] is None and economics['qualified_simulated_commercial_earnings_microUSD'] == 0
        and economics['earned_successor_funding'] == 'DEFERRED_NO_QUALIFIED_EARNINGS')
    progress = load(repo / 'docs/overnight008-progress/SOURCE_SHA256.json')
    checks['progress_paper_is_frozen_100_input_edition'] = len(progress['files']) == 100 and progress['source_ref'] == '2b7a58e6e6593ae48da6f7f33865db94868c957f'
    verdicts = [
        {'link': 'Enabling capability', 'status': 'NOT ESTABLISHED', 'scope': 'Exact finite-model obstruction and coordinate/metric instruments execute. Newly attainable consequential activity is unproved.', 'mission_success_link_established': False},
        {'link': 'Technical advantage', 'status': 'NOT ESTABLISHED', 'scope': 'Strong ordinary methods tie or provide the capability; XCT target is refuted within its model; zero plane wins NASA primary MAE.', 'mission_success_link_established': False},
        {'link': 'Complete-cost profitability', 'status': 'NOT ESTABLISHED', 'scope': 'No same-cohort negative-to-positive crossing; participation and complete costs unknown.', 'mission_success_link_established': False},
        {'link': 'Investment attractiveness', 'status': 'NOT ESTABLISHED', 'scope': 'Incremental NPV versus free ordinary alternatives and non-entry is unknown.', 'mission_success_link_established': False},
        {'link': 'AGI ALPHA value capture', 'status': 'CONDITIONAL', 'scope': 'Scoped service fee is a scenario only; no buyer acceptance, calibrated positive demand or enforceable revenue established.', 'mission_success_link_established': False},
        {'link': 'Unrestricted simulated earnings', 'status': 'VERIFIED', 'scope': 'ZERO qualified commercial earned funds. Capital, refundable deposits and reserve release are not earnings.', 'qualified_funds_microUSD': 0, 'mission_success_link_established': False},
        {'link': 'Earned-funded successor construction', 'status': 'NOT ESTABLISHED', 'scope': 'Construction uses the original authorized allocation; earned investment is deferred.', 'mission_success_link_established': False},
        {'link': 'Fresh successor advantage', 'status': 'NOT ESTABLISHED', 'scope': 'Executed biological retention/retrieval ties ordinary equal-content reuse/reset; no matched discovery-policy or earned successor advantage.', 'mission_success_link_established': False},
    ]
    support_paths = [
        actual / 'artifacts/REPORT.json', actual / 'artifacts/PHASES.json', actual / 'RECEIPT.json',
        repo / 'verification/replay_nasa_public008.py', repo / 'scripts/restore_nasa_original008.py',
        repo / 'research/nasa008/coordinate-r2/repair.py', helpers[0],
        repo / 'campaign/overnight-008/economics/recovery/FINAL_COST_SNAPSHOT_EVENT28.json',
        repo / 'campaign/overnight-008/economics/recovery/run012/CUMULATIVE_COST_RESOURCE.json',
        repo / 'campaign/overnight-008/economics/recovery/run002/NO_EARNED_FUNDS.json',
        repo / 'research/eis008/paired-audit/DECISION.md',
        repo / 'research/eis008/paired-audit/GATE_UPDATE.json',
        repo / 'research/eis008/paired-audit/exact-r1/REPORT.json',
        repo / 'docs/overnight008-progress/SOURCE_SHA256.json',
        repo / 'docs/overnight008-progress/SOURCE_INPUTS.json',
    ]
    output = {
        'schema': 'agi-alpha/independent-final-publication-review008/v1',
        'recorded_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'reviewed_source': SOURCE, 'reviewed_data_commit': DATA,
        'reviewer_source_sha256': sha(Path(__file__)),
        'checks': checks, 'all_checks_passed': all(checks.values()),
        'mission': 'MISSION NOT COMPLETE', 'verdicts': verdicts,
        'actual_execution_reviewed': {'waited_cpu_seconds': receipt['waited_cpu_seconds'], 'outer_wall_seconds': receipt['wall_seconds'], 'phases': phases},
        'claim_boundaries': [
            'Current small review checks source/receipt linkage; it does not repeat registration, all47 hashes or numerical review.',
            'Original dd2dc checker independently rebuilds fixed saved fields, masks, affine coordinates and arithmetic; it does not independently optimize registration.',
            'Data5d5 tree identity relies on parent connector-verified expected tree. This reviewer did not retrieve the public data tree a second time.',
            'Caller-supplied expected trees are not their own public trust anchor. Reviewed public commit/tree identity remains necessary.',
            'Actual trusted reproduction is not arbitrary native sandbox qualification, protected scientific confirmation, physical uncertainty calibration or external certification.',
            'Historical receipts copied during restoration remain historical inputs; only new restore/repair/separate-review phases are current execution.',
            'Progress paper is an explicitly incomplete100-input historical source freeze. Late coordinate and828-record audit require a source-matched final supplement.',
            'No newly established consequential defect in the declared numeric reproduction call path. No broad discovery, new means, economic crossing or earned-funding claim is supported.',
        ],
        'next_input_gate': {
            'decision': 'DO NOT ADMIT A PHYSICAL MEASUREMENT INVENTION YET',
            'executable_action': 'Create a provenance table for one pilot processed fuel-cell row linking its exact raw condition folder, same stack/cell identifier, profile start/end timestamps and every spectral frequency acquisition time. Then identify independently repeated acquisitions of that same system and calibrated measurement/control uncertainty before specifying an ambiguity test.',
            'frozen_obligations': ['Keep all828 released records and exclusion inventory visible.', 'Different cell locations are not repeat measurements.', 'Do not pair the June17 example to the June13 spectrum by assumption.', 'No rounded-input collisions, learned distances or fitted residuals become physical equivalence/noise calibration.', 'Give ordinary site/time-conditioned and operando/LTV methods the same legitimate context.'],
            'pass_condition': 'Traceable raw-to-processed timing/site mapping plus independently justified same-system repeatability and useful fixed delivery obligation; only then freeze an intervention and complete comparator.',
            'failure_action': 'If current bytes cannot establish the mapping/repeatability, record the exact missing fields and remain NOT ADMITTED. Any additional bounded public range audit must fit remaining original resources; no spending or new access is implied.',
            'not_run_in_this_review': True,
        },
        'publication_actions': ['Publish current actual receipts/controller/closure with exact source identities, preserving earlier incomplete-archive failures.', 'Retain the original/progress paper freezes; link or build a final source-matched supplement covering late results and current economics.', 'Final status must use the latest source-bound execution, not09:01 pending text. Record exact-head CI independently; this review does not create or waive CI success.'],
        'inputs_sha256': {str(x.relative_to(a.base)): sha(x) for x in support_paths},
        'review_process_cpu_seconds': time.process_time() - start,
        'confirmation_alpha_spent': 0,
        'procedural_independence_only': True,
        'complete_monetary_cost': None,
    }
    (a.output / 'REPORT.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'all_checks_passed': output['all_checks_passed'], 'failed': [k for k, v in checks.items() if not v], 'mission': output['mission'], 'review_process_cpu_seconds': output['review_process_cpu_seconds']}))
    raise SystemExit(0 if output['all_checks_passed'] else 1)


if __name__ == '__main__':
    main()
