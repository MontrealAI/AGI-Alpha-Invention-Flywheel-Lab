"""Invoke the pinned CPU release for this local, public-data experiment."""

import ctypes
import errno
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryFile
from time import monotonic


ROOT = Path(__file__).resolve().parent
MEASURE_CHILD = '''import subprocess, sys, time, resource
start = time.monotonic()
result = subprocess.run(sys.argv[1:], stdin=subprocess.DEVNULL)
usage = resource.getrusage(resource.RUSAGE_CHILDREN)
print(f"engine_wall_s={time.monotonic()-start:.3f} engine_cpu_s={usage.ru_utime+usage.ru_stime:.3f} engine_max_rss_kib={usage.ru_maxrss}", file=sys.stderr)
raise SystemExit(result.returncode)
'''


def run(engine, arguments):
    lib = ctypes.CDLL('libseccomp.so.2')
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_export_bpf.argtypes = [ctypes.c_void_p, ctypes.c_int]
    context = lib.seccomp_init(0x7FFF0000)
    if not context:
        raise RuntimeError('Could not install the local process filter.')
    try:
        for syscall in (b'socket', b'socketpair', b'connect', b'bind', b'listen', b'accept', b'accept4',
                        b'sendmsg', b'sendmmsg', b'sendto', b'io_uring_setup'):
            number = lib.seccomp_syscall_resolve_name(syscall)
            if number < 0 or lib.seccomp_rule_add(context, 0x00050000 | errno.EPERM, number, 0) != 0:
                raise RuntimeError('Could not restrict a network or asynchronous I/O syscall.')
        with TemporaryFile() as bpf:
            if lib.seccomp_export_bpf(context, bpf.fileno()) != 0:
                raise RuntimeError('Could not export the local process filter.')
            bpf.seek(0)
            bindings = [flag for path in ('/usr', '/lib', '/lib64', '/bin') for flag in ('--ro-bind', path, path)]
            results = ROOT / 'results'
            results.mkdir(mode=0o700, exist_ok=True)
            cmd = ['bwrap', '--clearenv', '--unshare-user', '--unshare-pid', '--cap-drop', 'ALL',
                   '--die-with-parent', '--setenv', 'PATH', '/usr/bin', '--setenv', 'LD_LIBRARY_PATH', '/engine',
                   '--setenv', 'HOME', '/tmp', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
                   *bindings, '--ro-bind', str(engine), '/engine', '--ro-bind', str(ROOT), '/work',
                   '--bind', str(results), '/work/results', '--chdir', '/work',
                   '--seccomp', str(bpf.fileno()), '--', '/usr/bin/python3', '-c', MEASURE_CHILD, *arguments]
            start = monotonic()
            result = subprocess.run(cmd, pass_fds=(bpf.fileno(),), stdin=subprocess.DEVNULL, check=False)
            print(f'outer_wall_s={monotonic()-start:.3f}', file=sys.stderr)
            return result.returncode
    finally:
        lib.seccomp_release(context)


if __name__ == '__main__':
    if sys.argv[1:] == ['probe']:
        raise SystemExit(run(Path('/usr/bin'), ['/usr/bin/python3', '-c', 'import os,socket,errno\n'
            'assert not os.path.exists("/workspace")\ntry: socket.socket()\nexcept OSError as e: assert e.errno==errno.EPERM\n'
            'else: raise RuntimeError("socket was available")\nprint("isolated mount and socket denial witnessed")']))
    executable = sys.argv[1]
    if executable not in {'llama-imatrix', 'llama-quantize', 'llama-completion', 'llama-cli'}:
        raise SystemExit('Choose a reviewed CLI from the pinned runtime.')
    engine = next((path.parent for path in (ROOT / 'runtime').rglob('llama-quantize') if path.is_file()), None)
    if engine is None:
        raise SystemExit('The pinned archive has not been unpacked.')
    raise SystemExit(run(engine, ['/engine/' + executable, *sys.argv[2:]]))
