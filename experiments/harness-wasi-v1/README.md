# WASI interpreter baseline experiment v1

**Prepared, not executed.** Publish and review this preregistration before running
the pull-request workflow. There are no model calls or candidate-source execution in
this experiment. Frozen product source48 and its release are unchanged.

The enabling question is whether a separately isolated interpreter evaluator can
make future local-model source construction testable when official Codex
authorization/native sandbox prerequisites are unavailable. This is supporting
work for qualified GENESIS source improvement, not an improvement claim itself.
The comparator is the existing unchanged interpreter and its independent 64-case
host oracle. A supported ordinary WASI runtime is the proposed means; no claim of
inventing the sandbox is made.

## Declared isolation

The guest receives one explicit **read-only host directory** at `/sandbox`.
It contains only the pinned public Python standard library, trusted guest driver,
and exact baseline module. This is not a zero-filesystem claim. It preserves
`Path(__file__).read_bytes()` and the installed interpreter's source guard.
The guest receives neither checkout/home directories nor credentials, inherited
environment or stdio, socket descriptors, HTTP capability or a process bridge.
WASI clocks/randomness remain available. Bounded output callbacks return data
to the supervisor; output is untrusted and never printed to a terminal directly.

Negative tests add two declared public fixtures: an ordinary text file and a
deliberate symlink to a synthetic outside sentinel. Tests deny file creation,
overwrite, append, rename, delete, directory/symlink creation, absolute/traversal/
symlink escape, host environment inheritance, loopback networking and process
creation. The listener and sentinel are newly created test resources, not private
host data. Fixture/link removal occurs before the 64-case replay. Host snapshots
must show no guest mutation. All test files are writable to the host so denial
does not merely reflect host chmod restrictions.

The exact official Python binding is 50.0.1, whose preopen API is
`preopen_dir(path, guest_path, fs_mutable=True)`. Every call explicitly passes
`fs_mutable=False`; official v50 C code maps false to `FsPerms::ReadOnly`.
Removed `DirPerms`/`FilePerms` spelling is not used. Version, source hash and
signature drift cause refusal, never a mutable/default fallback.

Each disposable worker has memory, CPU, fuel, stack, output and elapsed-time
envelopes. The outer process watchdog includes Python package import, Wasm
compilation, instantiation and execution; epochs/fuel are additional controls.
Trusted small Wasm probes check fuel, epoch, memory and external cancellation;
the real WASI/Python route checks output capacity. A finite test does not prove
the absence of runtime bugs or microarchitectural side channels.

## Build requirements and operation

Standard public `ubuntu-latest`, Linux x86_64, host Python 3.12, GCC/`cc`, `make`,
ordinary CPython build dependencies supplied by that runner, and network access
to the three official pinned artifacts in [PROTOCOL.json](PROTOCOL.json).
No apt/sudo, new privilege, container, Rust compiler, model weights or GPU is used.
Downloads total about 230 MB compressed; extraction has a 4 GiB per-archive envelope.
Actual build disk/memory/time are unmeasured. The WASI SDK carries its own Clang
and sysroot. The upstream CPython helper builds native build-Python and WASIp1
Python; no upstream broad-preopen convenience launcher is executed.

The same driver stages the public stdlib and unchanged module, checks capability
and resource negatives, then invokes 64 cases in fresh worker processes. Expected
answers never enter the staging tree or guest argument. Case values are publicly
preregistered regressions, not unseen scientific confirmation. The host accepts
observed output using its own structural JSON relation and explicit arithmetic/
error expectations; guest PASS assertions and operation counts have no authority.

After preparation review, the coordinating owner publishes the branch and pull
request. That public source and preregistration precede the path-scoped PR job.
`.github/workflows/harness-wasi-v1.yml` checks out the exact PR head and requires
the frozen PROTOCOL.json SHA256 embedded in the workflow. It has no release
trigger or merge dependency and does not require merging unexecuted code first.
Every job has 360 minutes from its initial AGI_JOB_START_EPOCH marker and reserves
the final 300 seconds for receipts/upload. Per-call security limits are separate
from that actual platform window.

`RESULT.json` records stage, actual command exits, source hashes, downloads, boundary
results and each executed baseline case. Build failure retains the full log hash/
byte count and last 128 KiB excerpt. Only compact evidence is uploaded—no downloaded
SDK/runtime,build tree,venv,private files or model weights. No retry occurs inside
an invocation. PASS requires every registered check; source changes invalidate it.
Source construction and model trials require a later separately registered step.

## Primary provenance

- [CPython 3.15.2 official release and source SHA256](https://www.python.org/downloads/release/python-3152/)
- [Tagged WASI configuration:SDK 33 and WASIp1](https://github.com/python/cpython/blob/v3.15.2/Platforms/WASI/config.toml)
- [Official SDK 33 release](https://github.com/WebAssembly/wasi-sdk/releases/tag/wasi-sdk-33)
- [Official Python package metadata](https://pypi.org/pypi/wasmtime/50.0.1/json)
- [Tagged Python binding](https://github.com/bytecodealliance/wasmtime-py/blob/50.0.1/wasmtime/_wasi.py)
- [Native read-only mapping](https://github.com/bytecodealliance/wasmtime/blob/v50.0.0/crates/c-api/src/wasi.rs)
- [Wasmtime interruption limits](https://docs.rs/wasmtime/50.0.0/wasmtime/struct.Config.html#method.epoch_interruption)
- [Wasmtime sandbox security](https://docs.wasmtime.dev/security.html)

The known mechanism is capability-constrained execution plus host-owned
qualification. Its applicability condition is verified runtime enforcement and
unchanged baseline behavior. Success would enable a future isolated source test;
it would not establish model-authored improvement, economic superiority or satisfy
the existing Codex authentication/native-sandbox gate. Complete engineering,
compute, maintenance and opportunity costs remain unknown.
