"""Check administrator-enforced GitHub protection before FRONTIER production work."""

import argparse
import json
import os
import re
import sys
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPOSITORY = 'MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
ENVIRONMENTS = {'frontier-omega-alpha-provision', 'frontier-intelligence-intake'}
API = 'https://api.github.com/repos/' + REPOSITORY
LIMIT = 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(path):
    headers = {'User-Agent': 'frontier-omega-alpha-release-gate', 'Accept': 'application/vnd.github+json'}
    if token := os.environ.get('GH_TOKEN'):
        headers['Authorization'] = 'Bearer ' + token
    with build_opener(NoRedirect()).open(Request(API + path, headers=headers), timeout=15) as response:
        raw = response.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('Oversized GitHub governance response')
    return json.loads(raw)


def qualify(environment, commit, read=fetch):
    if environment not in ENVIRONMENTS or re.fullmatch(r'[0-9a-f]{40}', commit) is None:
        raise ValueError('Use the approved environment and a full GitHub commit')
    branch = read('/branches/main')
    if branch['commit']['sha'] != commit:
        raise ValueError('The operation must use the current main commit')
    if branch['protected'] is not True:
        raise ValueError('GitHub does not report main as protected')
    rules = read('/rules/branches/main')
    if not any(row['type'] == 'pull_request'
               and row['parameters'].get('required_approving_review_count', 0) >= 1
               and row['parameters'].get('require_last_push_approval') is True for row in rules):
        raise ValueError('A main ruleset must enforce independent review of the latest push')
    if not any(row['type'] == 'required_status_checks'
               and row['parameters'].get('strict_required_status_checks_policy') is True
               and row['parameters'].get('required_status_checks') for row in rules):
        raise ValueError('A main ruleset must enforce status checks on up-to-date code')

    path = '/environments/' + environment
    settings = read(path)
    if settings['name'] != environment or not any(
            row['type'] == 'required_reviewers' and row.get('prevent_self_review') is True
            and row.get('reviewers') for row in settings['protection_rules']):
        raise ValueError('The production environment must require separate reviewer approval')
    policy = settings['deployment_branch_policy']
    if not policy or policy.get('custom_branch_policies') is not True:
        raise ValueError('Limit this environment to the exact main branch')
    branches = read(path + '/deployment-branch-policies')
    if (branches['total_count'] != 1
            or [(row['name'], row.get('type')) for row in branches['branch_policies']] != [('main', 'branch')]):
        raise ValueError('Use exactly one deployment policy of type branch for main')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', required=True, choices=sorted(ENVIRONMENTS))
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    try:
        qualify(args.environment, args.commit)
    except ValueError as exc:
        # Remote bodies and credential material are excluded from workflow logs.
        if type(exc) is ValueError and str(exc).startswith((
                'Use ', 'The operation', 'GitHub does', 'A main', 'The production', 'Limit ', 'Oversized ')):
            print(str(exc), file=sys.stderr)
        else:
            print('GitHub governance could not be verified.', file=sys.stderr)
        return 1
    except (OSError, KeyError, TypeError):
        print('GitHub governance could not be verified.', file=sys.stderr)
        return 1
    print('GitHub reports required main and environment protections. Separate release approval still applies.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
