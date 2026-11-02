"""Current hosted-job window, independent of simulated business economics."""
from __future__ import annotations

import math
import os
import time

HOSTED_JOB_LIMIT_SECONDS = 6 * 60 * 60
RECEIPT_SHUTDOWN_RESERVE_SECONDS = 5 * 60
COMMAND_WINDOW_SECONDS = HOSTED_JOB_LIMIT_SECONDS - RECEIPT_SHUTDOWN_RESERVE_SECONDS
JOB_START_VARIABLE = 'AGI_JOB_START_EPOCH'


def command_budget(requested=None, *, environ=None, now=None):
    """Deduct prior setup/work; never extend GitHub's finite platform window.

    A standalone reproduction has no inferred GitHub or ChatGPT deadline.
    It may supply its own explicit finite engineering deadline. Neither mode
    grants resources or changes an experiment's financial/acceptance contract.
    """
    env = os.environ if environ is None else environ
    if requested is not None:
        if type(requested) is not int or requested < 1:
            raise ValueError('POSITIVE_FINITE_EXPLICIT_ALLOWANCE_REQUIRED')
        try: finite = math.isfinite(float(requested))
        except OverflowError: finite = False
        if not finite: raise ValueError('POSITIVE_FINITE_EXPLICIT_ALLOWANCE_REQUIRED')
    hosted = env.get('GITHUB_ACTIONS', '').lower() == 'true'
    if not hosted:
        return {'timeout_seconds': requested, 'platform_limit_seconds': None,
                'receipt_reserve_seconds': 0, 'elapsed_job_seconds': 0.0,
                'clock_source': 'standalone-no-platform-deadline',
                'requested_timeout_seconds': requested,
                'scope': 'No hosted or ChatGPT entitlement inferred; optional explicit local deadline only.'}
    if requested is not None and requested > COMMAND_WINDOW_SECONDS:
        raise ValueError('ALLOWANCE_EXCEEDS_HOSTED_PLATFORM_WINDOW')
    raw = env.get(JOB_START_VARIABLE)
    elapsed = 0.0
    source = 'github-job-first-step'
    if raw is None:
        raise ValueError('HOSTED_JOB_START_EPOCH_REQUIRED')
    else:
        if not isinstance(raw, str) or not raw.isascii() or not raw.isdecimal() or int(raw) <= 0:
            raise ValueError('VALID_HOSTED_JOB_START_EPOCH_REQUIRED')
        moment = time.time() if now is None else now
        if not isinstance(moment, (int, float)) or isinstance(moment, bool) or not math.isfinite(moment):
            raise ValueError('FINITE_HOSTED_JOB_CLOCK_REQUIRED')
        elapsed = moment - int(raw)
        if elapsed < 0:
            raise ValueError('HOSTED_JOB_CLOCK_REGRESSION')
        source = 'github-job-first-step'
    remaining = math.floor(COMMAND_WINDOW_SECONDS - elapsed)
    if remaining < 1:
        raise TimeoutError('HOSTED_PLATFORM_WINDOW_EXHAUSTED')
    granted = remaining if requested is None else min(requested, remaining)
    return {'timeout_seconds': granted, 'platform_limit_seconds': HOSTED_JOB_LIMIT_SECONDS,
            'receipt_reserve_seconds': RECEIPT_SHUTDOWN_RESERVE_SECONDS,
            'elapsed_job_seconds': elapsed, 'clock_source': source,
            'requested_timeout_seconds': requested,
            'scope': 'Engineering execution window only; not a business-scale or profit ceiling.'}
