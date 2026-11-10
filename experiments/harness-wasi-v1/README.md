# WASI interpreter baseline experiment: attempt003

**Attempt003 is prospectively registered, not executed.** Attempt001 at public95
failed in build-launcher plumbing. Attempt002 at public663 completed that build,
then exhausted the unchanged 2e9 fuel allocation during CPython compilation.
The worker recorded OUT_OF_FUEL before a separate Tokio-thread abort (-6).
No capability checks or baseline cases qualified; no models or candidate source ran.

[Attempt001 history](evidence/attempt001/SUMMARY.json) and
[attempt002 inspected history](evidence/attempt002/SUMMARY.json) remain failures.
The attempt002 inspector recomputed the exact archive hash. Its retained
INSPECTED JSON files are decoded, sanitized diagnostic values, **not original ZIP
member bytes**; the wrapper hash must not be assigned to reconstructed members.

This new attempt keeps the source48 interpreter, 64 cases, dependency pins, fuel,
CPU/wall/epoch/memory/stack/output limits and read-only capability boundary.
It prepares trusted stdlib caches and explicitly closes runtime resources.
Two small trusted output lifecycle probes must pass before any CPython guest.
The repair hypotheses still require a fresh public, reviewed execution.

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
The first failed attempt recorded 232.72 seconds wall time and 651.16 seconds
child CPU for the supervisor through its failure; build disk/peak memory and the
guest startup budgets remain unmeasured. The WASI SDK carries its own Clang and
sysroot. The official helper builds native build-Python and configures WASIp1.
The configured launcher remains disabled by `--host-runner false`.

Attempt001 used upstream `make-host`, which first completed `make all` then
unconditionally invoked `python.sh --version`. That second command returned1
because the launcher deliberately executes `false`. Attempt002 corrected that build plumbing by executing the
same first command directly: `make --jobs cpu_count all` in
`cross-build/wasm32-wasip1`. It omits the automatic launcher, without adding any
guest capability. The helper's optional `SOURCE_DATE_EPOCH` lookup finds no Git
checkout in the extracted source under RUNNER_TEMP; this correction does not
claim universally byte-identical builds in arbitrary checkout layouts.
Attempt003 retains that correction. Its existing 64 cases, download pins,
capability/resource acceptance and envelopes remain unchanged; its new cache and
lifecycle prerequisites add checks. Guest capacity and enforcement still require
actual qualification.

The exact already-built native CPython3.15.2 prepares checked-hash stdlib caches
before the read-only preopen. It must report cache tag `cpython-315`, bytecode
magic `520e0d0a`, optimization0 and checked-hash header flags3. Every staged .py
must equal its pinned public source. Only stdlib __pycache__ files are added;
the baseline, guest driver and any future candidate are excluded from host
compilation. Python -B forbids cache writes but still reads existing caches.

Selection excludes directories named test, tests, idle_test and __pycache__, plus
upstream's bad_coding|badsyntax|site-packages pattern. These fixture exclusions are
explicit and listed, never silently treated as successfully compiled. Each
selected file must compile successfully. The manifest records source and cache
hashes, compiler identity and sizes; staging snapshots prove source preservation.
Cache preparation cost is recorded as a normal trusted-build command.

After execution, the worker stops and joins its epoch timer, captures fuel and
explicitly closes Store, Linker, Module, unconsumed WasiConfig, Engine and Config.
Callback references remain alive through those closes. One shared lock protects
combined stdout/stderr capacity accounting, writes and the final snapshot; the
64KiB combined cap and overflow refusal remain unchanged. The native async output
implementation exposes no joined-drain API here: supported close calls are a
prospective repair, not proof that every background task has drained.
Two trusted Wasm probes write exact stdout/stderr and then respectively return or
trap. Both must report successful closes **and ordinary process exit**. The same
exit/cleanup requirement applies to completed capability, resource and baseline
workers; the intentionally killed watchdog probe remains the declared exception.
Neither a written receipt nor an expected trap can hide a host abort.

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
