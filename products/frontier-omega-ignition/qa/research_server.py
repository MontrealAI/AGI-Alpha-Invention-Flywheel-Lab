"""Larger-context local llama.cpp launch for the research qualification protocol."""
import contextlib
import os
import socket
import subprocess

import qualify_live


@contextlib.contextmanager
def server(binary, weights, work, record):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    threads = str(record["hardware"]["threads"])
    config = ["--ctx-size", "12288", "--parallel", "1", "--threads", threads, "--threads-batch", threads,
              "--n-gpu-layers", "0", "--seed", "6144", "--temp", "0", "--no-repack",
              "--batch-size", "128", "--ubatch-size", "64", "--no-webui"]
    record["serving_configuration"] = config
    command = [str(binary), "-m", str(weights), "--host", "127.0.0.1", "--port", str(port),
               "--alias", qualify_live.MODEL_ALIAS, *config]
    env = {"PATH": os.defpath, "LD_LIBRARY_PATH": str(binary.parent), "HOME": str(work),
           "LANG": "C.UTF-8", "NO_PROXY": "127.0.0.1"}
    with (work / "server.log").open("wb") as log:
        proc = subprocess.Popen(command, cwd=work, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        try:
            qualify_live.wait_ready(proc, port)
            yield port
        finally:
            record["server_exit_before_shutdown"] = proc.poll()
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
