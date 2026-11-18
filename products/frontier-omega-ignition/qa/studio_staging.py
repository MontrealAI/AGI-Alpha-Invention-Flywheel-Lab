"""Start a disposable HTTPS studio for the browser qualification. Loopback only."""
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from ignition.hosted import HostedService
from ignition.hosted_auth import Access


def main():
    # The same HTTP service runs under TLS here. Production uses an operator's
    # TLS terminator; its DNS, certificate, routing and supervision require a live smoke.
    with tempfile.TemporaryDirectory(prefix="ignition-private-staging-") as name:
        root = Path(name)
        os.chmod(root, 0o700)
        cert, key = root / "cert.pem", root / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-keyout", str(key), "-out", str(cert), "-days", "1",
                        "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        access = Access(root / "state", "staging")
        service = HostedService(access, "https://localhost", port=0)
        try:
            origin = f"https://localhost:{service.server_port}"
            service.origin = origin
            service.authority = f"localhost:{service.server_port}"
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            service.socket = context.wrap_socket(service.socket, server_side=True)
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            # Protocol over a private parent-child pipe. Never write this to CI logs.
            invites = [access.issue(f"first-use-{i}") for i in range(4)]
            print(json.dumps({"origin": origin, "invites": invites, "ca_pem": cert.read_text()}), flush=True)
            sys.stdin.readline()
            service.shutdown()
            thread.join()
        finally:
            service.server_close()


if __name__ == "__main__":
    main()
