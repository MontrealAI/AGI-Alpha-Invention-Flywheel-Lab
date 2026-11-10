"""One disposable Wasmtime worker. Never imports the guest baseline in host Python."""
import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import resource
import threading
import time


def collect_output(output, overflow, lock, limit, stream, data):
    # stdout/stderr can arrive on distinct native threads. This whole capacity
    # decision and mutation is one shared critical section, not a GIL assumption.
    with lock:
        remaining = limit - sum(len(value) for value in output.values())
        if len(data) > remaining:
            output[stream].extend(data[:max(remaining, 0)])
            overflow.append(True)
            return -1
        output[stream].extend(data)
        return len(data)


def close_resources(named):
    """Supported deterministic closes; this does not promise a Tokio task drain."""
    closed, errors = [], []
    for name, value in named:
        if value is None:
            continue
        try:
            value.close()
            closed.append(name)
        except Exception as error:
            errors.append({'resource': name, 'type': type(error).__name__, 'message': str(error)[:512]})
    return {'complete': not errors, 'closed': closed, 'errors': errors,
            'scope': 'Supported close calls returned; no async drain guarantee. Ordinary process exit is required.'}


def lifecycle_wat(trap=False):
    # Trusted output-only probe, with no guest filesystem/environment operations.
    return r'''(module
      (import "wasi_snapshot_preview1" "fd_write" (func $write (param i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 16) "lifecycle-out\0a")
      (data (i32.const 32) "lifecycle-err\0a")
      (func (export "_start")
        i32.const 0 i32.const 16 i32.store
        i32.const 4 i32.const 14 i32.store
        i32.const 1 i32.const 0 i32.const 1 i32.const 48 call $write drop
        i32.const 0 i32.const 32 i32.store
        i32.const 2 i32.const 0 i32.const 1 i32.const 48 call $write drop
    ''' + ('unreachable' if trap else '') + '))'


def run(request):
    import wasmtime
    import wasmtime._wasi
    protocol = request['protocol']
    limits = protocol['guest_limits']
    if importlib.metadata.version('wasmtime') != '50.0.1':
        raise ValueError('Unregistered Wasmtime package version')
    if hashlib.sha256(Path(wasmtime._wasi.__file__).read_bytes()).hexdigest() != protocol['wasmtime_python_wasi_source_sha256']:
        raise ValueError('Wasmtime Python preopen implementation differs from reviewed source')
    signature = inspect.signature(wasmtime.WasiConfig.preopen_dir)
    if list(signature.parameters) != ['self', 'path', 'guest_path', 'fs_mutable'] or signature.parameters['fs_mutable'].default is not True:
        raise ValueError('Readonly preopen API differs; mutable/default fallback forbidden')
    # Limits constrain this disposable host worker as well as guest linear memory.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (limits['worker_address_space_bytes'],) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (limits['worker_cpu_seconds'],) * 2)
    config = wasmtime.Config()
    config.consume_fuel = True
    config.epoch_interruption = True
    config.wasm_threads = False
    config.wasm_memory64 = False
    config.wasm_multi_memory = False
    config.wasm_component_model = False
    config.max_wasm_stack = limits['wasm_stack_bytes']
    # Keep virtual address reservations bounded without disabling guard pages.
    config.memory_reservation = limits['linear_memory_bytes']
    config.memory_reservation_for_growth = 0
    config.memory_guard_size = 65536
    engine = wasmtime.Engine(config)
    store = wasmtime.Store(engine)
    store.set_limits(memory_size=limits['linear_memory_bytes'], table_elements=100000,
                     instances=1, memories=1, tables=1)
    mode = request['mode']
    store.set_fuel(10000 if mode == 'fuel' else (2**63 if mode in {'epoch', 'watchdog'} else limits['fuel']))
    store.set_epoch_deadline(1)
    stop = threading.Event()
    def interrupt():
        delay = 0.1 if mode == 'epoch' else (60 if mode == 'watchdog' else limits['epoch_seconds'])
        if not stop.wait(delay):
            engine.increment_epoch()
    timer = threading.Thread(target=interrupt, daemon=True)
    output = {'stdout': bytearray(), 'stderr': bytearray()}
    overflow = []
    output_lock = threading.Lock()
    callbacks = []
    wasi = linker = module = None
    def collect(stream):
        def write(data):
            return collect_output(output, overflow, output_lock, limits['output_bytes'], stream, data)
        return write
    timer.start()
    started = time.monotonic()
    result = {'mode': mode, 'outcome': 'ERROR'}
    try:
        if mode in {'fuel', 'epoch', 'memory', 'watchdog'}:
            code = '(module (func (export "run") (loop br 0)))'
            if mode == 'memory':
                pages = limits['linear_memory_bytes'] // 65536
                if not 2 <= pages < 65535:
                    raise ValueError('Memory probe requires a registered bound below the architectural limit')
                code = ('(module (memory 1) '
                        '(func (export "within") (result i32) i32.const %d memory.grow) '
                        '(func (export "beyond") (result i32) i32.const 1 memory.grow))') % (pages - 1)
            module = wasmtime.Module(engine, wasmtime.wat2wasm(code))
            instance = wasmtime.Instance(store, module, [])
            Path(request['progress']).write_text(json.dumps({'phase':'entering_wasm', 'mode':mode}))
            if mode == 'memory':
                value = {key:instance.exports(store)[key](store) for key in ('within', 'beyond')}
            else:
                value = instance.exports(store)['run'](store)
            result.update(outcome='RETURN', value=value)
        else:
            wasm = Path(request['wasm'])
            if hashlib.sha256(wasm.read_bytes()).hexdigest() != request['wasm_sha256']:
                raise ValueError('WASI interpreter bytes changed')
            wasi = wasmtime.WasiConfig()
            wasi.argv = ['/sandbox/python/bin/python3.15', '-I', '-S', '-B',
                         '/sandbox/guest_driver.py', json.dumps(request['guest'], separators=(',', ':'))]
            wasi.env = []
            callbacks.extend([collect('stdout'), collect('stderr')])
            wasi.stdout_custom = callbacks[0]
            wasi.stderr_custom = callbacks[1]
            # Exactly one preopen. This explicit argument is mandatory.
            wasi.preopen_dir(request['stage'], '/sandbox', fs_mutable=False)
            store.set_wasi(wasi)
            module = wasmtime.Module(engine, wasmtime.wat2wasm(lifecycle_wat(mode == 'lifecycle_trap'))
                                     if mode in {'lifecycle_return', 'lifecycle_trap'} else wasm.read_bytes())
            imports = [(item.module, item.name) for item in module.imports]
            if any(namespace != 'wasi_snapshot_preview1' for namespace, _ in imports):
                raise ValueError('Unexpected host import namespace')
            result['imports'] = imports
            linker = wasmtime.Linker(engine)
            linker.define_wasi()
            instance = linker.instantiate(store, module)
            Path(request['progress']).write_text(json.dumps({'phase':'entering_wasm', 'mode':mode}))
            instance.exports(store)['_start'](store)
            result['outcome'] = 'RETURN'
    except wasmtime.ExitTrap as error:
        result.update(outcome='EXIT', exit_code=error.code)
    except wasmtime.Trap as error:
        result.update(outcome='TRAP', trap_code=str(error.trap_code), message=str(error)[:2048])
    except Exception as error:
        result.update(outcome='ERROR', error_type=type(error).__name__, message=str(error)[:2048])
    finally:
        stop.set()
        timer.join()
        # Read accounting before closing Store. Every close runs while callback globals
        # and explicit callback references remain alive; no gc/sleep/os._exit shortcut.
        result['remaining_fuel'] = store.get_fuel()
        result['cleanup'] = close_resources([
            ('store', store), ('linker', linker), ('module', module),
            ('wasi', wasi), ('engine', engine), ('config', config)])
        if not result['cleanup']['complete']:
            result['outcome'] = 'ERROR'
            result['error_type'] = 'ResourceCleanupError'
    with output_lock:
        result.update(wall_seconds=time.monotonic() - started,
                      stdout=bytes(output['stdout']).decode('utf-8', errors='replace'),
                      stderr=bytes(output['stderr']).decode('utf-8', errors='replace'),
                      output_overflow=bool(overflow), peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('request', type=Path)
    parser.add_argument('result', type=Path)
    args = parser.parse_args()
    try:
        result = run(json.loads(args.request.read_text()))
    except Exception as error:
        result = {'outcome': 'ERROR', 'error_type': type(error).__name__, 'message': str(error)[:2048]}
    args.result.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
