"""Run a source-only Python experiment without exposing host inputs or authority.

The evaluator stays outside this process. Setup failure is a refusal. This
backend is an opt-in Linux experiment, not a dependency of the Wasm runtime.
"""

import json
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
from time import perf_counter_ns

from bridge.instruments import strict_portable_json


class NativeRefused(ValueError):
    pass


class NativeUnavailable(NativeRefused):
    pass


# Loading this worker and installing its kernel policy happen before a candidate
# is decoded or executed. Bind only a system interpreter and runtime libraries.
WORKER = r'''
import ctypes
import errno
import json
import resource
import sys

ALLOWED = """
read write close fstat newfstatat statx lseek pread64 readv writev getdents64
openat access faccessat faccessat2 readlink readlinkat getcwd
mmap mremap mprotect munmap brk madvise futex sched_yield
rt_sigaction rt_sigprocmask rt_sigreturn sigaltstack clock_gettime gettimeofday
getpid gettid getuid geteuid getgid getegid getrandom exit exit_group
""".split()

memory, cpu, cap = map(int, sys.argv[1:])
resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
resource.setrlimit(resource.RLIMIT_FSIZE, (cap, cap))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

sec = ctypes.CDLL('libseccomp.so.2')
sec.seccomp_init.argtypes = [ctypes.c_uint32]
sec.seccomp_init.restype = ctypes.c_void_p
sec.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
sec.seccomp_syscall_resolve_name.restype = ctypes.c_int
sec.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
sec.seccomp_load.argtypes = [ctypes.c_void_p]
sec.seccomp_release.argtypes = [ctypes.c_void_p]

deny = 0x50000 | errno.EPERM
allow = 0x7fff0000
ctx = sec.seccomp_init(deny)
if not ctx:
    raise RuntimeError('SECCOMP_INIT')
for name in ALLOWED:
    number = sec.seccomp_syscall_resolve_name(name.encode('ascii'))
    if number >= 0 and sec.seccomp_rule_add(ctx, allow, number, 0) != 0:
        raise RuntimeError('SECCOMP_RULE')
if sec.seccomp_load(ctx) != 0:
    raise RuntimeError('SECCOMP_LOAD')
sec.seccomp_release(ctx)

print('FRONTIER_NATIVE_V1', file=sys.stderr, flush=True)
request = json.load(sys.stdin)
env = {'__name__': 'experiment'}
try:
    exec(compile(request['source'], '<experiment>', 'exec'), env)
    result = env['solve'](request['inputs'])
    print(json.dumps({'result': result}, allow_nan=False, separators=(',', ':')))
except Exception as error:
    print(json.dumps({'error': type(error).__name__ + ': ' + str(error)[:260]}))
'''


def command(memory, cpu, cap):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise NativeUnavailable('NATIVE_PLATFORM')
    unshare = shutil.which('unshare', path='/usr/bin:/bin')
    bubblewrap = shutil.which('bwrap', path='/usr/bin:/bin')
    interpreter = Path('/usr/bin/python3').resolve()
    stdlib = Path('/usr/lib') / interpreter.name
    libraries = Path('/lib/x86_64-linux-gnu')
    loader = Path('/lib64/ld-linux-x86-64.so.2')
    if not (unshare and bubblewrap and interpreter.is_file() and stdlib.is_dir()
            and libraries.is_dir() and loader.is_file()):
        raise NativeUnavailable('NATIVE_DEPENDENCIES')
    return [unshare, '--user', '--map-root-user', '--net', bubblewrap,
            '--unshare-pid', '--unshare-uts', '--unshare-ipc', '--clearenv',
            '--cap-drop', 'ALL', '--die-with-parent', '--new-session',
            '--ro-bind', str(interpreter), '/usr/bin/python3',
            '--ro-bind', str(stdlib), str(stdlib),
            '--ro-bind', str(libraries), str(libraries),
            '--ro-bind', str(loader), str(loader),
            '--dir', '/work', '--remount-ro', '/', '--chdir', '/work', '--',
            '/usr/bin/python3', '-I', '-B', '-S', '-c', WORKER,
            str(memory), str(cpu), str(cap)]


def run(source, inputs, *, cpu=3, memory=160 * 1024 * 1024, cap=48_000):
    if (type(cpu) is not int or not 1 <= cpu <= 30 or type(memory) is not int
            or not 48 * 1024 * 1024 <= memory <= 512 * 1024 * 1024
            or type(cap) is not int or not 1024 <= cap <= 128_000):
        raise NativeRefused('NATIVE_LIMIT')
    try:
        if type(source) is not str or not 1 <= len(source.encode('utf-8')) <= 20_000:
            raise NativeRefused('SOURCE_SIZE')
        body = json.dumps({'source': source, 'inputs': inputs}, ensure_ascii=False, allow_nan=False).encode()
    except NativeRefused:
        raise
    except (TypeError, ValueError, RecursionError) as error:
        raise NativeRefused('NATIVE_INPUT') from error
    if len(body) > 512_000:
        raise NativeRefused('NATIVE_INPUT_SIZE')
    start = perf_counter_ns()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            completed = subprocess.run(command(memory, cpu, cap), input=body, stdout=stdout,
                                       stderr=stderr, timeout=cpu + 4, cwd='/', env={}, check=False)
        except subprocess.TimeoutExpired as error:
            raise NativeRefused('NATIVE_WALL_LIMIT') from error
        except OSError as error:
            raise NativeUnavailable('NATIVE_START') from error
        stderr.seek(0)
        first = stderr.readline(48).strip()
        if first != b'FRONTIER_NATIVE_V1':
            raise NativeUnavailable('NATIVE_ISOLATION_REFUSED')
        if completed.returncode != 0:
            raise NativeRefused('NATIVE_PROCESS_LIMIT_OR_FAILURE')
        stdout.seek(0)
        result = stdout.read(cap + 1)
    try:
        parsed = strict_portable_json(result.decode('utf-8'))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise NativeRefused('NATIVE_OUTPUT') from error
    if type(parsed) is not dict or set(parsed) not in ({'result'}, {'error'}):
        raise NativeRefused('NATIVE_OUTPUT')
    if 'error' in parsed and (type(parsed['error']) is not str or len(parsed['error']) > 360):
        raise NativeRefused('NATIVE_OUTPUT')
    pending = [(parsed, 0)]
    while pending:
        value, depth = pending.pop()
        if depth > 48:
            raise NativeRefused('NATIVE_OUTPUT')
        if isinstance(value, list):
            pending.extend((item, depth+1) for item in value)
        elif isinstance(value, dict):
            pending.extend((item, depth+1) for item in value.values())
    try:
        json.dumps(parsed, ensure_ascii=False).encode('utf-8')
    except (ValueError, RecursionError) as error:
        raise NativeRefused('NATIVE_OUTPUT') from error
    return {**parsed, 'wall_ns': perf_counter_ns() - start}


def require_worker():
    if run('def solve(value):\n return value', 'ready').get('result') != 'ready':
        raise NativeUnavailable('NATIVE_STARTUP_CHECK')
