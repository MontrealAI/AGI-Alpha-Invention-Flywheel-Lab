"""Execute a small source-bound technical-service portfolio on public evidence."""
import argparse
import ast
import copy
import difflib
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'campaign/commercial-010/service/executed-002/manifest.json'
ONBOARDING = 'campaign/commercial-010/onboarding/executed-001/RESULT.json'
POLICY = 'campaign/commercial-010/POLICY.json'
SOURCES = [MANIFEST, ONBOARDING, POLICY, 'commercial/service.py',
           'commercial/service_verifier.py', 'commercial/onboarding.py',
           'vendor/alpha_claim/protected_exchange.py', 'campaign/commercial-010/ALLOCATION.json']


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(value if isinstance(value, bytes) else canonical(value))


def bound(root, name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError('RELATIVE_EVIDENCE_REQUIRED')
    source = Path(root) / p
    if source.is_symlink() or any(x.is_symlink() for x in source.parents):
        raise ValueError('REGULAR_EVIDENCE_REQUIRED')
    return source.read_bytes()


def receipt_expression(raw):
    nodes = []
    for node in ast.walk(ast.parse(raw)):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == 'receipt_path':
                    nodes.append(value)
    if len(nodes) != 1:
        raise ValueError('ONE_DRIVER_RECEIPT_EXPRESSION_REQUIRED')
    expression = ast.Expression(nodes[0])
    allowed = (ast.Expression, ast.Call, ast.Name, ast.Load, ast.Constant, ast.Subscript, ast.BinOp, ast.Div)
    if any(not isinstance(x, allowed) for x in ast.walk(expression)):
        raise ValueError('UNSUPPORTED_RECEIPT_EXPRESSION')
    if any(isinstance(x, ast.Call) and (not isinstance(x.func, ast.Name) or x.func.id != 'str' or x.keywords or len(x.args) != 1) for x in ast.walk(expression)):
        raise ValueError('NO_ARBITRARY_GENERATED_CODE')
    if any(isinstance(x, ast.Name) and x.id not in {'str', 'result', 'output'} for x in ast.walk(expression)):
        raise ValueError('UNSUPPORTED_RECEIPT_IDENTIFIER')
    return compile(ast.fix_missing_locations(expression), '<source-bound-receipt-expression>', 'eval')


def evaluate_receipt(raw, result, output):
    return eval(receipt_expression(raw), {'__builtins__': {'str': str}}, {'result': result, 'output': Path(output)})


def statements(root):
    m = json.loads(bound(root, MANIFEST))
    o = json.loads(bound(root, ONBOARDING))
    p = json.loads(bound(root, POLICY))
    rows = 0
    for job in m['jobs']:
        order = json.loads(bound(root, job['input']))
        rows += len(order['invoices']) + len(order['payments'])
    return [
        ('source_scope', 'What input data are qualified?', 'Authored public synthetic USD receivables and payment records only; this qualification does not represent live customer records.', [MANIFEST, 'commercial/service.py']),
        ('cohort_outcome', 'What was actually produced and checked?', f"The executed engineering cohort supplied {rows} source records across {len(m['jobs'])} orders: {m['accepted_count']} accepted packages and {m['rejected_count']} rejected jobs. This is not a population accuracy estimate.", [MANIFEST]),
        ('matching_contract', 'What is the delivered outcome?', 'Delivery contains row-level reconciliation JSON and a CSV exception schedule. It does not edit bank records, file taxes, attest accounts or move funds.', ['commercial/service.py']),
        ('ambiguity_policy', 'How is ambiguous evidence handled?', 'Ambiguous matches remain in an exception schedule; a strict-completeness order is rejected when required rows remain unresolved rather than inventing an allocation.', ['commercial/service.py', 'commercial/service_verifier.py']),
        ('onboarding', 'Can input preparation run autonomously?', f"The CSV pipeline executed {len(o['jobs'])} synthetic exports: {o['canonical_identity_matches']} canonical prepared-order identities, {o['input_rejected']} input rejections and {o['independent_service_accepted']} independent service acceptances. Customer attention and the complete host bill were not measured.", [ONBOARDING, 'commercial/onboarding.py']),
        ('independent_acceptance', 'Who checks acceptance?', 'A separately implemented checker recomputes row partitions, exact cents, references and customer isolation. Builder and checker share the host and agent family; this is not external certification.', ['commercial/service_verifier.py']),
        ('commerce_scope', 'Are the demonstrated commercial payments real?', 'Customers, orders, payment protection, settlement and earned funds in the commercial model are SIMULATED. The service cohort reports zero actual customers and zero actual collections.', [MANIFEST, POLICY, 'vendor/alpha_claim/protected_exchange.py']),
        ('host_costs', 'Are exact model bills available?', 'Host token billing and the exact routed model version are unavailable. Monetary conclusions require disclosed complete-resource cost envelopes; process CPU is not a complete monetary bill.', [MANIFEST, 'campaign/commercial-010/ALLOCATION.json']),
        ('intervention', 'Was a human reviewer inserted into this workflow?', 'No human intervention is recorded for the source service orders. The autonomous comparison does not impose hypothetical human staffing; this statement is limited to the declared workflow.', [MANIFEST]),
        ('pricing', 'What does strategic pricing establish?', 'The pricing policy seeks expected collected complete-cost profit and sustainable cash under declared buyer and competitor assumptions. Its tested prices are not observed market optima or a universal equilibrium certificate.', [POLICY]),
        ('cash_protection', 'How are earnings distinguished from capital?', 'The pinned native exchange separates seed liquidity, restricted custody, principal reserves and unrestricted earned funds, and admits continuation investment through its earned-funding gate. Seed capital may still back reserves.', ['vendor/alpha_claim/protected_exchange.py']),
        ('permissions', 'What operating permissions are in scope?', 'The declared operation authorizes public or synthetic inputs and simulated commerce. It grants no new spending, paid provider calls, real outreach, real payment execution or credential access.', ['campaign/commercial-010/ALLOCATION.json']),
    ]


def build_packet(root):
    return {'schema': 'agi-alpha/portfolio011-evidence-packet/v1', 'scope': 'PUBLIC_REPO_EVIDENCE',
            'claims': [{'id': ident, 'question': q, 'answer': a,
                        'evidence': [{'path': n, 'sha256': sha(bound(root, n))} for n in paths]}
                       for ident, q, a, paths in statements(root)],
            'source_hashes': {n: sha(bound(root, n)) for n in SOURCES},
            'limits': 'A bounded 12-question technical evidence response, not a complete enterprise RFP, legal commitment, security attestation or observed sale.'}


def render_packet(packet):
    lines = ['# Technical response and evidence packet', '',
             'Scope: public source-backed engineering evidence; customer behavior and commercial payments remain simulated.', '']
    for c in packet['claims']:
        lines.extend([f"## {c['question']}", '', c['answer'], '',
                      'Evidence: ' + ', '.join(f"`{x['path']}` (SHA256 `{x['sha256']}`)" for x in c['evidence']), ''])
    lines.extend([packet['limits'], ''])
    return '\n'.join(lines).encode()


def verify_packet(root, packet, rendered):
    from commercial.portfolio_services_check import verify_packet as independent_verify
    return independent_verify(root, packet, rendered)


def run_native_regression(root, output, before, after):
    from experiments.resource006_v3 import run
    limits = {'wall_seconds': 5, 'cpu_seconds': 1, 'memory_bytes': 134217728, 'output_bytes': 20000, 'storage_bytes': 100000}
    checks = []
    for name, command, expected in [('success', [sys.executable, '-c', 'print("actual-supervised-command")'], 'complete'),
                                     ('failure', [sys.executable, '-c', 'raise SystemExit(7)'], 'failed')]:
        destination = output / ('native-' + name)
        result = run(command, destination, output / 'native-resources.json', 'portfolio011-' + name, limits, cwd=root)
        if result['receipt']['state'] != expected or 'receipt_path' in result:
            raise ValueError('UNEXPECTED_NATIVE_SUPERVISOR_CONTRACT')
        try:
            evaluate_receipt(before, result, destination)
        except KeyError as e:
            old = {'rejected': True, 'exception': type(e).__name__, 'detail': str(e)}
        else:
            raise ValueError('REAL_PRE_REPAIR_FAILURE_NOT_REPRODUCED')
        actual = evaluate_receipt(after, result, destination)
        if actual != str(destination / 'RECEIPT.json') or not Path(actual).is_file():
            raise ValueError('PATCH_FAILED_REAL_SUPERVISOR_RESULT')
        checks.append({'case': name, 'native_state': expected, 'before': old,
                       'after': {'accepted': True, 'receipt_file': str(Path(actual).relative_to(root)),
                                 'receipt_sha256': sha(Path(actual).read_bytes())},
                       'native_result_keys': sorted(result)})
    return {'accepted': True, 'checks': checks, 'scope': 'Actual native success and failure subprocesses, not mocked provider receipts.'}


def execute(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if not output.is_relative_to(root):
        raise ValueError('PUBLIC_REPO_OUTPUT_REQUIRED')
    output.mkdir(parents=True, exist_ok=False)
    started, cpu = time.monotonic(), time.process_time()
    producer_source = Path(__file__).read_bytes()
    checker_source = bound(root, 'commercial/portfolio_services_check.py')
    write(output / 'PRODUCER_SOURCE.py.txt', producer_source)
    write(output / 'CHECKER_SOURCE.py.txt', checker_source)
    from commercial.service import canonical as service_canonical, deliver
    from commercial.service_verifier import audit_delivery
    before = bound(root, 'historical/commercial-010/attempt-v2/run_commercial010.py')
    after = bound(root, 'run_commercial010.py')
    patch = ''.join(difflib.unified_diff(before.decode().splitlines(True), after.decode().splitlines(True), fromfile='a/run_commercial010.py', tofile='b/run_commercial010.py')).encode()
    if not patch:
        raise ValueError('REAL_PATCH_REQUIRED')
    write(output / 'software_patch/source_before.py.txt', before)
    write(output / 'software_patch/source_after.py.txt', after)
    write(output / 'software_patch/delivery.patch', patch)
    regression = run_native_regression(root, output / 'software_patch', before, after)
    write(output / 'software_patch/ACCEPTANCE.json', regression)
    packet = build_packet(root)
    rendered = render_packet(packet)
    accepted = verify_packet(root, packet, rendered)
    write(output / 'rfp_response/packet.json', packet)
    write(output / 'rfp_response/RESPONSE.md', rendered)
    write(output / 'rfp_response/ACCEPTANCE.json', accepted)
    bad = copy.deepcopy(packet)
    bad['claims'][6]['answer'] = 'We have observed one billion USD revenue and are SOC2 certified.'
    try:
        verify_packet(root, bad, render_packet(bad))
    except ValueError as e:
        probe = {'rejected': True, 'reason': str(e), 'claim': bad['claims'][6]}
    else:
        raise ValueError('PLANTED_FALSE_CLAIM_ACCEPTED')
    write(output / 'rfp_response/REJECTED_UNSUPPORTED_CLAIM.json', probe)
    example = {'scope': 'SYNTHETIC_PUBLIC_WORKLOAD', 'currency': 'USD', 'order_id': 'guide-example', 'require_complete': True,
               'invoices': [{'id': 'invoice-1', 'customer': 'example-customer', 'amount_cents': 12345}],
               'payments': [{'id': 'payment-1', 'customer': 'example-customer', 'amount_cents': 12345, 'invoice_refs': ['invoice-1']}]}
    write(output / 'technical_docs/minimal-input.json', service_canonical(example))
    deliver(example, output / 'technical_docs/worked-example')
    report = json.loads((output / 'technical_docs/worked-example/reconciliation.json').read_bytes())
    check = audit_delivery(example, report)
    if check['accepted'] is not True:
        raise ValueError('DOCUMENTATION_EXAMPLE_FAILED')
    guide = ('# Operating guide for the bounded reconciliation workflow\n\n'
             'This guide covers the implemented public synthetic-input service. It is not an instruction to connect customer accounts or move funds.\n\n'
             '## Input and output contract\n\nUse explicit USD integer cents, unique invoice/payment IDs and customer identities. Include invoice references when known. A strict-completeness order rejects unresolved rows; an exception-schedule order preserves ambiguity for follow-up. Delivery contains reconciliation.json and exceptions.csv.\n\n'
             '## Tested worked example\n\nThe accompanying minimal-input.json supplies one invoice and one exactly referenced payment for 12345 cents. The actual produced worked-example/reconciliation.json was independently checked; all rows are conserved.\n\n'
             '## Run source-bound engineering checks\n\n```sh\npython -m unittest discover -s tests -p "test_service*010.py" -v\npython -m unittest discover -s tests -p "test_onboarding010.py" -v\n```\n\n'
             'The release reproduction guide provides the frozen CLI and clean-package commands. Use a new output directory; preserve original failures and source identities.\n\n'
             '## Operational limits\n\nAuthored public synthetic records only. No account attestation, tax filing, fraud certification or real payment execution. Exact host inference billing and customer attention costs are unmeasured. The independently checked example does not establish quality on all future customer records.\n\n'
             '## Source-backed capability answers\n\n' + rendered.decode())
    write(output / 'technical_docs/OPERATING_GUIDE.md', guide.encode())
    write(output / 'technical_docs/ACCEPTANCE.json', {'accepted': True, 'worked_example': check,
                                                    'rendered_evidence_packet_sha256': sha(rendered),
                                                    'scope': 'Runnable one-row example plus source-bound operator documentation.'})
    service_rows = []
    def descriptor(ident, directory, first, repeat, cost, limitations):
        paths = sorted(p for p in (output / directory).rglob('*') if p.is_file() and not p.name.endswith('.lock'))
        receipt = output / directory / 'ACCEPTANCE.json'
        service_rows.append({'id': ident, 'portfolio_id': ident, 'accepted': True,
                             'artifacts': [{'path': str(p.relative_to(root)), 'sha256': sha(p.read_bytes())} for p in paths],
                             'acceptance_receipt': {'path': str(receipt.relative_to(root)), 'sha256': sha(receipt.read_bytes())},
                             'human_first_cost_usd_interval': first, 'human_repeat_cost_usd_interval': repeat,
                             'agent_operating_cost_usd_interval': cost, 'agent_onboarding_cost_usd_interval': [.01, 2],
                             'scope_limits': limitations, 'cost_evidence': 'Assumed narrow matched-work envelopes; not measured human timing or exact host inference bill.'})
    descriptor('software_bugfix', 'software_patch', [8, 30], [7, 25], [.1, 3], 'One real supervisor reporting defect and actual success/failure regression checks; not a full $841 software project.')
    descriptor('technical_docs', 'technical_docs', [15, 90], [12, 80], [.2, 5], 'One bounded operating guide and independently checked example; not comprehensive API migration documentation.')
    descriptor('rfp_response', 'rfp_response', [20, 120], [16, 110], [.25, 6], 'A twelve-question public evidence packet; not a complete 33-hour enterprise proposal or authorized customer quote.')
    m = json.loads(bound(root, MANIFEST))
    service_rows.append({'id': 'reconciliation', 'portfolio_id': 'reconciliation', 'accepted': True,
                         'artifacts': [{'path': MANIFEST, 'sha256': sha(bound(root, MANIFEST))}],
                         'acceptance_receipt': {'path': 'campaign/commercial-010/audit/service-source-002.json', 'sha256': sha(bound(root, 'campaign/commercial-010/audit/service-source-002.json'))},
                         'human_first_cost_usd_interval': [17.375, 278], 'human_repeat_cost_usd_interval': [15.203125, 243.25],
                         'agent_operating_cost_usd_interval': [5, 30], 'agent_onboarding_cost_usd_interval': [.01, 2],
                         'accepted_artifacts': m['accepted_count'], 'rejected_jobs': m['rejected_count'],
                         'scope_limits': 'Existing 19-order, 19000-record authored synthetic qualification; no real customer demand or population accuracy.',
                         'cost_evidence': 'Conditional envelopes and human task-time scenarios; exact bills unknown.'})
    result = {'schema': 'agi-alpha/portfolio011-executed-services/v1', 'scope': 'PUBLIC_SYNTHETIC_TECHNICAL_WORK_ONLY',
              'rows': service_rows, 'sourcefiles': {n: sha(bound(root, n)) for n in SOURCES},
              'producer_source_sha256': sha(producer_source), 'independent_checker_source_sha256': sha(checker_source),
              'source_snapshots': [{'path': str((output / n).relative_to(root)), 'sha256': sha(raw)}
                                   for n, raw in [('PRODUCER_SOURCE.py.txt', producer_source), ('CHECKER_SOURCE.py.txt', checker_source)]],
              'human_intervention_seconds': 0, 'actual_customers': 0, 'actual_collections_usd': 0,
              'host_model_version': None, 'host_token_billing': 'UNKNOWN',
              'work_cpu_seconds': time.process_time() - cpu, 'work_wall_seconds': time.monotonic() - started,
              'economic_interpretation': 'Actual bounded service artifacts; buyer behavior, prices, repeat demand and scaled future production remain conditional simulation inputs.',
              'independence': 'Separate reconciliation and technical-packet checker implementations by another agent; shared host/model family, not external certification.'}
    write(output / 'EXECUTED_SERVICES.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.root, args.output), indent=2))
