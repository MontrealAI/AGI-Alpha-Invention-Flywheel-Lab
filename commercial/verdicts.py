"""Independent evidence-scoped verdicts; invention never gates service profit."""


def verdicts(*, simulated_go, accepted_jobs, positive_service, observed_evidence=None,
             capability_evidence=None, blue_sky_evidence=None):
    if type(simulated_go) is not bool or type(positive_service) is not bool or type(accepted_jobs) is not int or accepted_jobs < 0:
        raise ValueError('EXPLICIT_VERDICT_INPUTS_REQUIRED')
    if simulated_go and (accepted_jobs == 0 or not positive_service):
        raise ValueError('SIMULATED_GO_REQUIRES_ACCEPTED_PROFITABLE_SERVICE')
    if capability_evidence is not None or blue_sky_evidence is not None:
        raise ValueError('CAPABILITY_OR_BLUE_SKY_AUTHORITY_NOT_INSTALLED')
    if observed_evidence is not None:
        raise ValueError('OBSERVED_AUTHORITY_NOT_INSTALLED; SIMULATION_CANNOT_UPGRADE')
    return {
        'profitable_autonomous_service': {'verdict': 'CONDITIONAL_SIMULATED_GO' if positive_service and accepted_jobs else 'NOT_ESTABLISHED',
                                         'scope': 'SIMULATED_ECONOMICS_OVER_EXECUTED_SERVICE',
                                         'explanation': 'Actual scoped artifacts with separate executable checks; positive economics only under disclosed resource-cost and demand conditions.'},
        'simulated_commercial_flywheel': {'verdict': 'CONDITIONAL_SIMULATED_GO' if simulated_go else 'NOT_ESTABLISHED',
                                         'scope': 'SIMULATED',
                                         'explanation': 'Repeated accepted collection, complete modeled cohort costs and native earned-only continuation; independent of invention.'},
        'observed_commercial_flywheel': {'verdict': 'NOT_ESTABLISHED', 'scope': 'OBSERVED',
                                        'explanation': 'No actual customers, collections or source-exact provider bills were observed.'},
        'capability_compounding_flywheel': {'verdict': 'NOT_ESTABLISHED', 'scope': 'CAPABILITY',
                                           'explanation': 'Existing invention paths are preserved; no fresh causal inheritance advantage is claimed by this commercial campaign.'},
        'blue_sky_enablement': {'verdict': 'NOT_ESTABLISHED', 'scope': 'BLUE_SKY',
                               'explanation': 'Ordinary useful service execution is not evidence of a new enabling instrument.'}}
