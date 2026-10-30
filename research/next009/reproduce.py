"""Execute campaign 009 again from an extracted package, without Git or network.

This is an exposed reproduction driver, never a confirmation or new admission.
Run it under an explicitly allocated external resource supervisor. Every stage
is substantive execution; archive/hash checks are preparation, not the result.
"""
import argparse
import copy
from fractions import Fraction
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import resource
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEPENDENCIES = {"numpy": "2.3.5", "scipy": "1.17.0", "cryptography": "50.0.2"}
PINS = {
    "research/next009/restore_evidence.py": "80a83387114ba12b0ef48299e07bb9f522fe51bd5f60adb66265a1da558ea0ef",
    "inventions/measurement009/compiler.py": "98892085340baf1b58762e46bc83d46b5290c7b3198171782b407e9c0a783c0d",
    "inventions/measurement009/model.py": "ac8977f0e90a5608147659f7265f533891091d94e7f2fec194416db8d5508df6",
    "inventions/measurement009/run.py": "e7754220f4ba8a4f743656964593a124474e6e6874a88bdc9e2722c089f98389",
    "inventions/measurement009/numeric_edition.py": "34a847e1944b3bed8bcc69221b94ac7d24f8b19f04a029c893afd8926775a13e",
    "inventions/measurement009/inputs/Net1.inp": "607510a01287d60d27b280a39df31a001363175a438a5de1b39e749cec6ddbc8",
    "inventions/measurement009/inputs/Net3.inp": "ea3e825c4fef0b5cba47fb06301bc85253f18b6364dc96c44d9fb492c40faa52",
    "inventions/measurement009/inputs/libepanet22.so": "3a49fa2eb1aecdf4d7a83c9a26667bacc418d285ed1d3a45becec52e7556d73f",
    "verification/next009/verify.py": "08bd61de297e491115c48d0a6eca482dc1c40f42966daf646e4cd2737cf68a76",
    "verification/next009/protocol.json": "5e80370c23a9486489334a9b7e17cd2f612d5db5dab77bd2e546313aa7282351",
    "verification/next009/runtime_driver.py": "ba187008a23ba81b3a9632970bd4a9e90c3ef19f102244235ba72c63c3aabab9",
    "verification/next009/CONFIRMATION_FREEZE.json": "bfa8014d638d64a434c87a952b54cf586bf79419b08ab529518a041b435d88b4",
    "verification/next009/verify_net3.py": "80b96c6f5b35ab539baa207cca9ab252d4b66733c2286f5ab694d9b3cd4438eb",
    "verification/next009/verify_net3_numeric.py": "bdb4f4f59101f2deadb5e7d3802017b3906b3d6804350be56ee9545be7cd01e7",
    "verification/next009/numeric_edition_checker.py": "2a8cec4a863e6102d3a3c1b610e193f2156c2000225cfd44a9f284c9ec74ac64",
    "verification/next009/audit_commerce.py": "f8804d678604e32a72a29e549c09046aec090117648473b467f56f27b2735ae9",
    "research/next009/commerce/run.py": "df84c57489ad39f86a1a988e3811aa076f6ee969b23eeeeff90dc086ac2731f2",
    "research/next009/commerce/policy.json": "9fcaf341da5d6fe7c5412c004a045f69e4317e1f312d6a0cc05c2bdb6f9f565d",
    "research/next009/commerce/source_docket.json": "40456241d16c0fcb1291f2a4b79c75bc0aae87671dd70f2c0c8571f287a8d1a6",
    "research/next009/PARENT_FREEZE.json": "4f68155fc87819c5a4bbfe5fecb8508304219c00643a8b688775b245a7a46ac7",
}
CONSTRUCTION = "evidence/next009/construction/networks-v2/artifacts"
PRIMARY = "evidence/next009/verification/primary-confirmation/artifacts"
NUMERIC = "evidence/next009/numeric-edition/construction-v1/artifacts"
NUMERIC_CHECK = "evidence/next009/numeric-edition/verification-v1/artifacts"
COMMERCE = "evidence/next009/commerce/net1-primary-final-v1/artifacts"
SUCCESSOR_FREEZE_SHA = "18fcf172156ea18ccb5c343844e160779884b3d44f8a04cfd1dae7ce7b99cb30"
TIME_FIELDS = ("wall_seconds", "process_cpu_seconds")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY:" + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("NONFINITE_JSON:" + value)))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical(value) + b"\n")


def package_path(relative, directory=False):
    if type(relative) is not str:
        raise ValueError("PACKAGE_PATH_STRING_REQUIRED")
    rel = PurePosixPath(relative)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise ValueError("PACKAGE_RELATIVE_PATH_REQUIRED")
    path = ROOT.joinpath(*rel.parts)
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError("PACKAGE_SYMLINK_REFUSED:" + relative)
    if not (path.is_dir() if directory else path.is_file()):
        raise FileNotFoundError(path)
    return path


def without_times(value):
    result = copy.deepcopy(value)
    for key in TIME_FIELDS:
        result.pop(key, None)
    return result


def plan_semantics(value):
    result = copy.deepcopy(value)
    result["construction_cost"] = without_times(result["construction_cost"])
    return result


class Replay:
    def __init__(self, args):
        self.args = args
        self.output = Path(args.output).absolute()
        if self.output.exists() or any(p.is_symlink() for p in [self.output, *self.output.parents]):
            raise FileExistsError("FRESH_UNSYMLINKED_OUTPUT_REQUIRED:" + str(self.output))
        self.output.mkdir(parents=True)
        self.start = time.monotonic()
        self.cpu = time.process_time()
        self.child = resource.getrusage(resource.RUSAGE_CHILDREN)
        self.comparisons, self.commands, self.identities = [], [], {}
        self.report = {
            "schema": "agi-alpha/next009-clean-extraction-reproduction/v1",
            "decision": "RUNNING", "through": args.through,
            "exposure": "EXPOSED_REPRODUCTION_NO_NEW_CONFIRMATION",
            "new_protected_cases": 0, "claim_alpha_spent": 0,
            "qualified_earned_funding": 0, "live_commerce": "NOT_RUN",
            "source_root": str(ROOT), "git_metadata_present": (ROOT / ".git").exists(),
            "network_used_by_reproducer": False,
            "scope": "Reexecute the published numerical-model service, controls, preserved failure, derivative edition, conditional simulated commerce and research-funded successor. No field, novelty, demand, complete-cost or earned-funded claim is added.",
            "commands": self.commands, "comparisons": self.comparisons,
        }

    def remember(self, path, expected=None):
        path = Path(path)
        actual = sha(path)
        if expected is not None and actual != expected:
            raise ValueError("SOURCE_IDENTITY_MISMATCH:" + str(path))
        self.identities[str(path)] = actual
        return actual

    def equal(self, label, observed, expected, ignored=()):
        left, right = canonical(observed), canonical(expected)
        row = {"check": label, "passed": left == right,
               "observed_semantic_sha256": hashlib.sha256(left).hexdigest(),
               "expected_semantic_sha256": hashlib.sha256(right).hexdigest(),
               "excluded_only": list(ignored)}
        self.comparisons.append(row)
        if left != right:
            write(self.output / "disagreements" / (label + ".json"),
                  {"observed": observed, "expected": expected, "comparison": row})
            raise ValueError("SEMANTIC_REPLAY_DISAGREEMENT:" + label)

    def identical(self, label, observed, expected):
        self.remember(expected)
        self.equal(label, {"sha256": sha(observed), "bytes": Path(observed).stat().st_size},
                   {"sha256": sha(expected), "bytes": Path(expected).stat().st_size})

    def command(self, name, module, arguments, expected_failure=None):
        command = [sys.executable, "-m", module, *map(str, arguments)]
        log = self.output / "logs"
        log.mkdir(exist_ok=True)
        start, cpu = time.monotonic(), time.process_time()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTHONHASHSEED"] = "0"
        env["OPENBLAS_NUM_THREADS"] = "1"
        env["OMP_NUM_THREADS"] = "1"
        print(json.dumps({"stage": name, "state": "running"}), flush=True)
        with (log / (name + ".stdout.log")).open("xb") as stdout, (log / (name + ".stderr.log")).open("xb") as stderr:
            completed = subprocess.run(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr, check=False)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        row = {"name": name, "command": command, "exit_code": completed.returncode,
               "wall_seconds": time.monotonic() - start, "driver_cpu_seconds": time.process_time() - cpu,
               "waited_child_cpu_seconds": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
               "expected_failure": expected_failure,
               "stdout_sha256": sha(log / (name + ".stdout.log")),
               "stderr_sha256": sha(log / (name + ".stderr.log"))}
        if expected_failure is None:
            row["passed"] = completed.returncode == 0
        else:
            error = (log / (name + ".stderr.log")).read_text(errors="replace")
            row["passed"] = completed.returncode == 1 and error.rstrip().endswith("ValueError: " + expected_failure)
        self.commands.append(row)
        write(log / (name + ".receipt.json"), row)
        print(json.dumps({"stage": name, "state": "passed" if row["passed"] else "failed",
                          "exit_code": completed.returncode, "waited_cpu_seconds": row["waited_child_cpu_seconds"]}), flush=True)
        if not row["passed"]:
            raise RuntimeError("REPLAY_STAGE_FAILED:" + name)

    def prepare(self):
        if self.args.require_clean and self.report["git_metadata_present"]:
            raise ValueError("CLEAN_EXTRACTION_REQUIRED_NO_GIT_DIRECTORY")
        if platform.system() != "Linux" or platform.machine() != "x86_64" or platform.python_implementation() != "CPython" or sys.version_info[:2] != (3, 12):
            raise ValueError("QUALIFIED_REPLAY_PLATFORM_IS_CPYTHON_3_12_LINUX_X86_64")
        versions = {name: importlib.metadata.version(name) for name in DEPENDENCIES}
        self.equal("pinned_dependency_versions", versions, DEPENDENCIES)
        self.report["environment"] = {"python": sys.version, "platform": platform.platform(), "dependencies": versions}
        for relative, expected in PINS.items():
            self.remember(package_path(relative), expected)
        for path in [Path(__file__), ROOT / "research/next009/requirements.txt"]:
            self.remember(path)
        from research.next009.restore_evidence import restore
        manifests = sorted((ROOT / "evidence/next009/archives").glob("*.manifest.json"))
        required = {"construction-r1.manifest.json", "primary-verification-r1.manifest.json",
                    "numeric-edition-r1.manifest.json", "commerce-r1.manifest.json"}
        if not required <= {p.name for p in manifests}:
            raise ValueError("REQUIRED_PUBLIC_ARCHIVES_MISSING")
        restored = []
        for manifest in manifests:
            self.remember(manifest)
            self.remember(manifest.parent / read(manifest)["archive"])
            restored.append(restore(manifest, ROOT))
        write(self.output / "ARCHIVE_RESTORATION.json", restored)
        self.report["archive_restoration"] = restored
        freeze = read(ROOT / "verification/next009/CONFIRMATION_FREEZE.json")
        for key, field in [("corpus", "corpus_raw_sha256"), ("plan", "artifact_sha256"),
                           ("protocol", "protocol_sha256"), ("candidate", "candidate_source_sha256"),
                           ("verifier", "verifier_source_sha256"), ("runtime_driver", "runtime_driver_sha256")]:
            self.remember(package_path(freeze["paths"][key]), freeze[field])
        self.parent = read(ROOT / "research/next009/PARENT_FREEZE.json")
        self.remember(ROOT / PRIMARY / "ACCEPTANCE.json", self.parent["receipt"])
        for module in ["inventions.measurement009.run", "verification.next009.verify",
                       "research.next009.commerce.run", "flywheel.retention", "vendor.alpha_claim.protected_exchange"]:
            spec = importlib.util.find_spec(module)
            if spec is None or spec.origin is None or not Path(spec.origin).resolve().is_relative_to(ROOT):
                raise ValueError("INHERITED_LOCAL_MODULE_REFUSED:" + module)
            self.remember(spec.origin)
        if self.args.through == "successor":
            self.prepare_successor()

    def prepare_successor(self):
        manifest = Path(self.args.successor_manifest)
        if not manifest.is_absolute():
            manifest = ROOT / manifest
        self.remember(manifest)
        data = read(manifest)
        if data.get("schema") != "agi-alpha/next009-successor-replay-inputs/v1":
            raise ValueError("SUCCESSOR_REPLAY_MANIFEST_SCHEMA")
        required = {"network", "raw_corpus", "corpus", "numeric_receipt", "simulation_receipt", "plans",
                    "acceptance", "exposed_case_truths", "comparison"}
        if set(data["paths"]) != required or data.get("freeze_sha256") != SUCCESSOR_FREEZE_SHA:
            raise ValueError("COMPLETE_SUCCESSOR_REPLAY_INPUTS_REQUIRED")
        for name, expected in data["files"].items():
            self.remember(package_path(name), expected)
        paths = {key: package_path(value, directory=(key == "plans")) for key, value in data["paths"].items()}
        required_files = {str(path.relative_to(ROOT)) for key, path in paths.items() if key != "plans"}
        plan_names = ["old_zero_drift_plan.json"] + ["drift_" + d + "_" + arm + ".json"
            for d in ("0", "1", "5", "10", "25") for arm in ("retained", "equal-content-ordinary-reuse", "reset-full-toolbox")]
        required_files.update(str((paths["plans"] / name).relative_to(ROOT)) for name in plan_names)
        required_files.add(str((paths["plans"] / "RETRIEVAL.json").relative_to(ROOT)))
        if not required_files <= set(data["files"]):
            raise ValueError("UNPINNED_SUCCESSOR_REPLAY_INPUT")
        raw = paths["network"].read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if blob != data["network_git_blob_sha1"] or blob != "6645947b161a90a18f312539d4ff5ac3aee12c4a":
            raise ValueError("PINNED_NET2_BLOB_REQUIRED")
        frozen = ROOT / "verification/next009/SUCCESSOR_FREEZE.json"
        self.remember(frozen, SUCCESSOR_FREEZE_SHA)
        for relative, expected in read(frozen)["files"].items():
            self.remember(package_path(relative), expected)
        self.remember(package_path("research/next009/construct_successor.py"))
        self.successor_paths, self.successor_plan_names = paths, plan_names

    def construction(self):
        fresh = self.output / "construction"
        self.command("reconstruct-net1-net3", "inventions.measurement009.run",
                     ["--output", fresh, "--networks", "Net1", "Net3"])
        for network in ("Net1", "Net3"):
            published = ROOT / CONSTRUCTION / network
            self.identical(network + "_native_corpus", fresh / network / "model/corpus.json", published / "model/corpus.json")
            self.equal(network + "_simulation_receipt", without_times(read(fresh / network / "model/simulation_receipt.json")),
                       without_times(read(published / "model/simulation_receipt.json")), TIME_FIELDS)
            for name in ("no_reference", "generated", "ordinary_greedy", "ordinary_exact"):
                self.equal(network + "_" + name + "_plan", plan_semantics(read(fresh / network / (name + "_plan.json"))),
                           plan_semantics(read(published / (name + "_plan.json"))), ["construction_cost.wall_seconds", "construction_cost.process_cpu_seconds"])
            for name in ("development_replay.json", "uncalibrated_two_truth_witness.json", "example_diagnosis.json"):
                self.equal(network + "_" + name.replace(".json", ""), read(fresh / network / name), read(published / name))

    def primary(self):
        original = ROOT / PRIMARY
        seed = read(original / "EXPOSED_CONFIRMATION_CASES.json")["seed"]
        output = self.output / "net1-exposed-replay"
        self.command("net1-independent-exposed-replay", "verification.next009.verify", [
            "--corpus", self.output / "construction/Net1/model/corpus.json",
            "--plan", ROOT / CONSTRUCTION / "Net1/generated_plan.json",
            "--protocol", ROOT / "verification/next009/protocol.json",
            "--candidate", ROOT / "inventions/measurement009/compiler.py",
            "--output", output, "--development-seed", seed])
        actual, expected = read(output / "ACCEPTANCE.json"), read(original / "ACCEPTANCE.json")
        expected["exposure"] = "EXPOSED_DEVELOPMENT"
        expected["protected_cases_executed"] = expected["protected_cases_passed"] = 0
        expected["development_cases_executed"] = expected["cases_executed"]
        self.equal("net1_acceptance_exposed_replay", without_times(actual), without_times(expected),
                   [*TIME_FIELDS, "confirmation/exposure fields changed explicitly to exposed reproduction"])
        self.equal("net1_all_original_case_truths", read(output / "DEVELOPMENT_CASES.json"), read(original / "EXPOSED_CONFIRMATION_CASES.json"))

    def raw_net3_failure(self):
        corpus_path = self.output / "construction/Net3/model/corpus.json"
        output = self.output / "raw-net3-rejected"
        self.command("preserve-raw-net3-range-failure", "verification.next009.verify_net3", [
            "--corpus", corpus_path, "--plan", ROOT / CONSTRUCTION / "Net3/generated_plan.json",
            "--protocol", ROOT / "verification/next009/protocol.json", "--output", output],
            expected_failure="TRACE_PERCENT_RANGE")
        if (output / "NET3_FEASIBILITY.json").exists():
            raise ValueError("RAW_NET3_MUST_REMAIN_UNQUALIFIED")
        corpus = read(corpus_path)
        witnesses = []
        for i, rows in enumerate(corpus["signal"]):
            for t, row in enumerate(rows):
                for k, value in enumerate(row):
                    if not 0 <= Fraction(str(value)) <= 100:
                        witnesses.append({"source": corpus["sources"][i], "source_index": i,
                            "time_seconds": corpus["times_seconds"][t], "time_index": t,
                            "sensor": corpus["nodes"][k], "sensor_index": k, "value": str(value)})
        published = read(ROOT / "verification/next009/NET3_RANGE_FAILURE.json")
        self.equal("raw_net3_all_range_witnesses", witnesses, published["all_range_witnesses"])
        write(output / "REPRODUCED_RANGE_FAILURE.json", {
            "decision": "ORIGINAL_RAW_NET3_REMAINS_UNQUALIFIED_UNDER_FROZEN_CONTRACT",
            "full_coordinate_denominator": len(corpus["sources"]) * len(corpus["nodes"]) * len(corpus["times_seconds"]),
            "range_failure_count": len(witnesses), "all_range_witnesses": witnesses,
            "source_corpus_sha256": sha(corpus_path), "clipping_or_checker_change": False})

    def numerical_edition(self):
        output = self.output / "net3-numeric-construction"
        self.command("net3-uniform-numeric-edition", "inventions.measurement009.numeric_edition", [
            "--raw-corpus", self.output / "construction/Net3/model/corpus.json", "--output", output, "--compile-plan"])
        for name in ("raw_corpus.json", "corpus.json", "NUMERIC_RECEIPT.json"):
            self.identical("numeric_net3_" + name.replace(".json", ""), output / name, ROOT / NUMERIC / name)
        for name in ("generated_plan", "ordinary_greedy_plan", "ordinary_exact_plan"):
            self.equal("numeric_net3_" + name, plan_semantics(read(output / (name + ".json"))),
                       plan_semantics(read(ROOT / NUMERIC / (name + ".json"))), ["construction_cost.wall_seconds", "construction_cost.process_cpu_seconds"])
        verified = self.output / "net3-numeric-feasibility"
        self.command("net3-full-derivative-feasibility", "verification.next009.verify_net3_numeric", [
            "--corpus", output / "corpus.json", "--plan", ROOT / NUMERIC / "generated_plan.json",
            "--protocol", ROOT / "verification/next009/protocol.json",
            "--raw-corpus", output / "raw_corpus.json", "--numeric-receipt", output / "NUMERIC_RECEIPT.json",
            "--adapter-source", ROOT / "inventions/measurement009/numeric_edition.py", "--output", verified])
        self.equal("numeric_net3_full_feasibility", without_times(read(verified / "NET3_NUMERIC_FEASIBILITY.json")),
                   without_times(read(ROOT / NUMERIC_CHECK / "NET3_NUMERIC_FEASIBILITY.json")), TIME_FIELDS)

    def commerce(self):
        output = self.output / "commerce"
        self.command("source-bound-commerce", "research.next009.commerce.run", [
            "--artifact", ROOT / CONSTRUCTION / "Net1/generated_plan.json", "--receipt", ROOT / PRIMARY / "ACCEPTANCE.json",
            "--verifier-source", ROOT / "verification/next009/verify.py", "--protocol", ROOT / "verification/next009/protocol.json",
            "--expected-artifact-sha256", self.parent["plan"], "--expected-receipt-sha256", self.parent["receipt"],
            "--expected-verifier-sha256", self.parent["verifier"], "--expected-protocol-sha256", self.parent["protocol"],
            "--output", output])
        actual, expected = read(output / "COMMERCIAL.json"), read(ROOT / COMMERCE / "COMMERCIAL.json")
        for value in (actual, expected):
            for key in (*TIME_FIELDS, "peak_rss_kib"):
                value["resources"].pop(key)
        self.equal("complete_conditional_commercial_result", actual, expected,
                   ["resources.wall_seconds", "resources.process_cpu_seconds", "resources.peak_rss_kib"])
        # The independent audit has intentionally fixed evidence paths. Build a
        # byte-bound view containing the NEW report and the exact original inputs.
        view = self.output / "commerce-audit-view"
        for relative in ["research/next009/commerce/policy.json", "research/next009/commerce/run.py",
                         CONSTRUCTION + "/Net1/generated_plan.json", PRIMARY + "/ACCEPTANCE.json",
                         "verification/next009/verify.py", "verification/next009/protocol.json"]:
            destination = view / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
            self.identical("audit_view_" + relative.replace("/", "_"), destination, ROOT / relative)
        destination = view / COMMERCE / "COMMERCIAL.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output / "COMMERCIAL.json", destination)
        self.command("independent-fresh-commerce-audit", "verification.next009.audit_commerce", [
            "--root", view, "--output", self.output / "commerce-independent-audit"])
        if read(self.output / "commerce-independent-audit/AUDIT.json")["passed"] is not True:
            raise ValueError("FRESH_COMMERCE_INDEPENDENT_AUDIT_FAILED")

    def successor(self):
        paths = self.successor_paths
        output = self.output / "successor-construction"
        self.command("reconstruct-net2-successor", "research.next009.construct_successor", ["--root", ROOT, "--output", output])
        for actual, key in [(output / "raw/corpus.json", "raw_corpus"), (output / "numeric/corpus.json", "corpus"),
                            (output / "numeric/NUMERIC_RECEIPT.json", "numeric_receipt")]:
            self.identical("successor_" + key, actual, paths[key])
        self.equal("successor_simulation_receipt", without_times(read(output / "raw/simulation_receipt.json")),
                   without_times(read(paths["simulation_receipt"])), TIME_FIELDS)
        for name in self.successor_plan_names:
            self.equal("successor_" + name[:-5], plan_semantics(read(output / "plans" / name)),
                       plan_semantics(read(paths["plans"] / name)), ["construction_cost.wall_seconds", "construction_cost.process_cpu_seconds"])
        actual, expected = read(output / "plans/SUCCESSOR.json"), read(paths["comparison"])
        for value in (actual, expected):
            for row in value["rows"]:
                row.pop("plan_sha256")
                row["whole_path_cost"] = without_times(row["whole_path_cost"])
        self.equal("successor_all_arms_cost_scopes_and_controls", actual, expected,
                   ["rows[].plan_sha256: timing-dependent plan bytes already semantically compared", "rows[].whole_path_cost.wall_seconds", "rows[].whole_path_cost.process_cpu_seconds"])
        self.equal("successor_actual_retention_retrieval", read(output / "plans/RETRIEVAL.json"), read(paths["plans"] / "RETRIEVAL.json"))
        seed = read(paths["exposed_case_truths"])["seed"]
        verified = self.output / "successor-exposed-replay"
        self.command("successor-independent-exposed-replay", "verification.next009.verify_successor", [
            "--root", ROOT, "--raw-corpus", output / "raw/corpus.json", "--corpus", output / "numeric/corpus.json",
            "--numeric-receipt", output / "numeric/NUMERIC_RECEIPT.json", "--network", paths["network"],
            "--simulation-receipt", output / "raw/simulation_receipt.json", "--plans", output / "plans",
            "--protocol", ROOT / "verification/next009/successor_protocol.json",
            "--freeze", ROOT / "verification/next009/SUCCESSOR_FREEZE.json",
            "--expected-freeze-sha256", SUCCESSOR_FREEZE_SHA, "--output", verified, "--replay-seed", seed])
        actual, expected = read(verified / "ACCEPTANCE.json"), read(paths["acceptance"])
        if actual["case_generation_mode"] != "EXPOSED_REPRODUCTION_NO_NEW_CONFIRMATION" or actual["new_protected_latent_worlds"] != 0:
            raise ValueError("SUCCESSOR_REPLAY_MUST_NOT_CREATE_NEW_CONFIRMATION")
        for value in (actual, expected):
            for key in (*TIME_FIELDS, "exposure", "case_generation_mode", "new_protected_latent_worlds"):
                value.pop(key)
            value["source_binding"].pop("simulation_receipt_sha256")
            for level in value["all_drift_levels"]:
                for arm in level["arms"]:
                    arm.pop("plan_sha256")
        self.equal("successor_all_pairs_levels_arms_and_runtime", actual, expected,
                   [*TIME_FIELDS, "exposure and fresh-case counts explicitly relabeled as replay",
                    "source_binding.simulation_receipt_sha256: timing-only change separately checked",
                    "all_drift_levels[].arms[].plan_sha256: timing-only changes separately checked"])
        self.equal("successor_all_original_case_truths", read(verified / "EXPOSED_CASE_TRUTHS.json"), read(paths["exposed_case_truths"]))

    def finish(self, error=None):
        changed = [path for path, expected in self.identities.items() if not Path(path).is_file() or sha(path) != expected]
        child = resource.getrusage(resource.RUSAGE_CHILDREN)
        self.report["source_identities"] = self.identities
        self.report["source_files_changed_during_replay"] = changed
        self.report["resources"] = {"wall_seconds": time.monotonic() - self.start,
            "driver_cpu_seconds": time.process_time() - self.cpu,
            "waited_child_cpu_seconds": child.ru_utime + child.ru_stime - self.child.ru_utime - self.child.ru_stime,
            "complete_monetary_cost": None,
            "scope": "Measured driver and waited children; external campaign supervisor/ledger remains the resource authority. No CPU-to-money conversion."}
        if error is not None or changed:
            self.report["decision"] = "REPRODUCTION_FAILED_OR_INCOMPLETE"
            self.report["error"] = {"type": type(error).__name__ if error else "SourceIdentityChanged", "message": str(error) if error else str(changed)}
        elif self.args.preflight:
            self.report["decision"] = "PREFLIGHT_PASSED_NO_EXECUTION_CLAIM"
        else:
            self.report["decision"] = "COMPLETE_EXPOSED_REPRODUCTION_PASSED" if self.args.through == "successor" else "PARTIAL_REPRODUCTION_THROUGH_COMMERCE_PASSED"
        write(self.output / "REPRODUCTION.json", self.report)
        print(json.dumps({"decision": self.report["decision"], "output": str(self.output),
                          "comparisons": len(self.comparisons), "executed_stages": len(self.commands),
                          "new_protected_cases": 0}), flush=True)
        return error is None and not changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New output directory; existing output is refused.")
    parser.add_argument("--through", choices=("commerce", "successor"), default="successor",
                        help="Default includes the full successor. 'commerce' explicitly reports only partial reproduction.")
    parser.add_argument("--successor-manifest", default="research/next009/REPLAY_INPUTS.json")
    parser.add_argument("--require-clean", action="store_true", help="Require a source extraction without .git metadata.")
    parser.add_argument("--preflight", action="store_true", help="Only validate dependencies, restore archives and check source/input bindings; no execution claim.")
    args = parser.parse_args()
    replay = Replay(args)
    error = None
    try:
        replay.prepare()
        if not args.preflight:
            replay.construction()
            replay.primary()
            replay.raw_net3_failure()
            replay.numerical_edition()
            replay.commerce()
            if args.through == "successor":
                replay.successor()
    except Exception as caught:
        error = caught
    return 0 if replay.finish(error) else 1


if __name__ == "__main__":
    raise SystemExit(main())
