"""Fetch pinned public benchmark; do not download private/user data."""
import hashlib
from pathlib import Path
from urllib.request import urlopen
URL='https://raw.githubusercontent.com/bstabler/TransportationNetworks/d1639b4ef218c17928ba573e806ddf8ba5e7ae6d/Anaheim/Anaheim_net.tntp'
RAW_SHA='99933b415e9500b13907829c37a43cfa9141714fad5af279081e28e5f9356f9a'
WORK_SHA='506b0866fa1a410e8ddda8380a3472b5f7fb5eb0812073b0e99d82211d290f66'
if __name__=='__main__':
    raw=urlopen(URL,timeout=60).read()
    assert hashlib.sha256(raw).hexdigest()==RAW_SHA,'upstream source differs'
    # Connector-to-file materialization added one terminal LF in the executed
    # study. Reproduce that harmless transformation explicitly, never hide it.
    local=raw+b'\n'
    assert hashlib.sha256(local).hexdigest()==WORK_SHA
    Path(__file__).with_name('Anaheim_net.tntp').write_bytes(local)
