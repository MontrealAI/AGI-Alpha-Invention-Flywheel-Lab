"""Larger bounded exact cohorts using the unchanged qualified service contracts."""
from pathlib import Path
import time
from enterprise import services
from enterprise.checkers import audit_delivery


def prepare_workload(root, output_relative, per_service=96):
    if type(per_service) is not int or not 32 <= per_service <= 333:
        raise ValueError('EXACT_COHORT_32_TO_333_PER_SERVICE')
    started = time.process_time()
    root = Path(root).absolute()
    manifest = services.prepare_services(root, output_relative)
    for service_id in services.SERVICE_IDS:
        for index in range(32, per_service):
            order = services.synthetic_order(service_id, index)
            artifact = services.produce(service_id, order)
            checked = audit_delivery(service_id, order, artifact)
            if checked.get('accepted') is not True:
                raise ValueError('NEW_EXACT_WORKLOAD_NOT_ACCEPTED')
            base = Path(output_relative) / order['order_id']
            paths = {k: str(base / name) for k, name in [('input', 'input.json'), ('artifact', 'artifact.json'), ('receipt', 'acceptance.json')]}
            ih = services._write(root / paths['input'], order)
            ah = services._write(root / paths['artifact'], artifact)
            receipt = {**checked, 'input_sha256': ih, 'artifact_sha256': ah,
                       'checker_source_sha256': manifest['source_hashes']['enterprise/checkers.py'],
                       'execution': 'Actual deterministic tool execution on synthetic authorized inputs; no model inference call.'}
            rh = services._write(root / paths['receipt'], receipt)
            manifest['jobs'].append({'id': order['order_id'], 'service_id': service_id, 'accepted': True,
                                    **paths, 'input_sha256': ih, 'artifact_sha256': ah, 'receipt_sha256': rh})
    manifest['resource_receipt']['process_cpu_seconds'] = time.process_time() - started
    manifest['resource_receipt']['construction_cost'] = 'Current registered simulated setup envelope; exact synthetic cohort, not projected demand. Host model/token billing unavailable.'
    services.load_jobs(root, manifest)
    return manifest
