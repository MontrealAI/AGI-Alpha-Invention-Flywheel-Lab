import argparse
import hashlib
import json
from pathlib import Path
import shutil

from connected_enterprise.finance import JournalAccount, SOURCE_PATHS, audit_journal
from enterprise.services import SOURCE_PATHS as SERVICE_PATHS, prepare_services

ROOT = Path(__file__).resolve().parents[2]
COSTS = {'research': 500, 'construction': 1000, 'verification': 600,
         'unsuccessful_attempts': 200, 'orchestration_tools_host': 200}
OPENING = 100_000 * 1_000_000


def write_new(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write('\n')


def run(output):
    output = output.absolute()
    if not output.exists():
        output.mkdir(parents=True, mode=0o700)
        source = output / 'source'
        for name in sorted(set(SOURCE_PATHS) | set(SERVICE_PATHS)):
            destination = source / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        manifest = prepare_services(source, 'fixture_services')
        write_new(output / 'manifest.json', manifest)
        binding = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in Path(__file__).parent.iterdir() if p.suffix == '.py' or p.name == 'PROTOCOL.md'}
        write_new(output / 'research_source.json', binding)
    else:
        manifest = json.loads((output / 'manifest.json').read_text())
        binding = json.loads((output / 'research_source.json').read_text())
        for name, expected in binding.items():
            if hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest() != expected:
                raise ValueError('RESEARCH_SOURCE_CHANGED_RESUME_ORIGINAL_SOURCE')
    source = output / 'source'
    account_path = output / 'account.sqlite'
    with JournalAccount(source, manifest, account_path, opening=OPENING, working=0,
                        contract='superalpha-coded-fabric-9ed2a315-primary') as account:
        for hour, (name, dollars) in enumerate(COSTS.items()):
            receipt = account.spend(ident='research-' + name, kind='registered_research',
                amount=dollars * 1_000_000, day=hour,
                work={'category': name, 'research_source': binding,
                      'scope': 'AUTHORED_COST_ENVELOPE_NO_DELIVERY_ADMISSION'},
                expected_net=0, allow_seed=True)
            if receipt is None:
                raise ValueError('RESEARCH_NOT_FUNDED')
        record = account.export()
        audit = account.audit()
        summary = account.snapshot()['summary']
    independent = audit_journal(record, root=source, manifest=manifest)
    public = output / 'public'
    if public.exists():
        old = json.loads((public / 'NATIVE_RECORD.json').read_text())
        if old != record:
            raise ValueError('RESUME_CHANGED_NATIVE_HISTORY')
        return json.loads((public / 'FINANCE.json').read_text())
    public.mkdir()
    write_new(public / 'NATIVE_RECORD.json', record)
    write_new(public / 'AUDIT.json', audit)
    write_new(public / 'INDEPENDENT_REPLAY.json', independent)
    report = {'scope': 'FRESH_NATIVE_RESEARCH_ONLY_ACCOUNT_AUTHORED_COSTS',
        'starting_capital_usd': 100000, 'research_envelope_usd': COSTS,
        'summary_micro_usd': summary, 'audit_accepted': audit['accepted'],
        'independent_replay_accepted': independent['accepted'],
        'research_source_sha256': binding, 'native_source_sha256': record['connected_journal']['source']['sha256'],
        'declared_simulation_epoch': '2026-11-03T00:00:00Z', 'last_event_hour': 4,
        'complete_365_day_interval': False, 'native_trailing365_profit_usd': None,
        'actual_model_host_billing_usd': None, 'complete_actual_cost_profit_usd': None,
        'buyer_orders': 0, 'customer_collections_usd': 0, 'capital_injections_usd': 0,
        'production_catalog_admitted': False, 'milestone_achieved': False,
        'funding_decision': 'RETAIN_CASH_NO_QUALIFIED_OFFER_NO_EARNED_SUCCESSOR',
        'tax_treatment': 'No revenue or positive modeled profit; no tax credit booked. Future tax unknown.',
        'capital_treatment': 'No fixed asset purchases, depreciation, debt or financing assumed.',
        'obligations': 'Research envelopes prepaid; no sale, warranty, refund or supplier commitment opened.',
        'boundary': 'Existing synthetic service fixtures initialize the native engine only. No fixture is sold or relabeled as coded work.'}
    write_new(public / 'FINANCE.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({k: result[k] for k in ['scope', 'summary_micro_usd', 'audit_accepted', 'independent_replay_accepted']}))
