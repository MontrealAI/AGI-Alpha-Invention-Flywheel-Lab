#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -eu
harness_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if command -v python3 >/dev/null 2>&1; then
    exec python3 "$harness_dir/launch.py" "$@"
fi
printf '%s\n' 'Install Python 3.10+ to connect models. Open START-HERE.html for the offline demo.' 'Installez Python 3.10+ pour connecter des modèles. Ouvrez START-HERE.html pour la démonstration hors ligne.' >&2
exit 1
