#!/usr/bin/env sh
# SPDX-License-Identifier: Apache-2.0
set -eu
cd "$(dirname "$0")"
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    echo "FRONTIER requires Python 3.11 or newer. Install it from https://www.python.org/downloads/"
    echo "FRONTIER requiert Python 3.11 ou plus récent."
    exit 1
fi
exec python3 bridge/server.py --pages-missions --pairing-guide "$@"
