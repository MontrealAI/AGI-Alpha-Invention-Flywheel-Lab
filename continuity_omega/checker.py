"""Public verification entry point. No constructor code is used by the checker."""
from ._replay_v1 import audit as _replay_audit
from .verification import checked_audit

def audit(case, handoff, passport, *, expected_case_sha256=None):
    return checked_audit(case, handoff, passport, core=_replay_audit,
                         expected_case_sha256=expected_case_sha256)
