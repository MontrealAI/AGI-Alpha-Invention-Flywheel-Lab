#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""No-inference proof against exact official llama.cpp b12242 C++ source.

Downloads only the 50 hashed source/header files needed by the converter and
upstream grammar tests (2.77 MB); no models, credentials, WASI or model inference.
Requires Python 3.10+, gcc and g++. Syntax acceptance is not evaluator acceptance.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import urllib.request

UPSTREAM_COMMIT = "3b4d6ab3f79651935fba1dd93732f29022a7f5f5"
UPSTREAM_TAG = "b12242"
SOURCE_SHA256 = {
  "common/build-info.h": "184dab4cba9a945a5fac69b6818e4f593e34d5ca762357b8b30f7520a745f7ec",
  "common/common.cpp": "69d4aeea15fbc50302944714ebf80195259b0c500453db13e7c7a21a0606bdc7",
  "common/common.h": "f3e006ea692459002b60f405ca42fd73593dc87eb2827f9259012038d389314f",
  "common/fit.h": "1cd52eaff43f1db03ef2045dcb8cdb3f48194a5d94c95888607fe7df217874ef",
  "common/json-schema-to-grammar.cpp": "cb744e5dfa94f38d88900e3bc455cb21e6c6e4449f3e4b70f3283dc8a443ea81",
  "common/json-schema-to-grammar.h": "9e4d9f1d426bef42e1ebcb66c551fe3f2eae700a361e7e698f2e382d600432ca",
  "common/json-schema.cpp": "1d39f46e92345419da65504995a89b05ed083163968d799f0b3c3c1dced8c490",
  "common/json-schema.h": "57933a181ec0e84cbba1abea7fd898dc03e452d7de1a35795b787cee679d02af",
  "common/json.cpp": "d8c556445cef8e7c93b0857f6ca7ae7ebd8295f169403ac66641b72f6b0598f2",
  "common/json.h": "a352f31307f1be2bdb34c027b876f42a1c5d1ea775cc8e4f11d703b16c40d22f",
  "common/log.h": "e99f07f5b64288aaece28955ed9f97c2ed8dc9c0375af3e253fc5c682637a014",
  "common/sampling.h": "63faa4ccb76fd466d3b5d86b14bc84a890bafa1f972fc46f66230eeb3384ce29",
  "common/speculative.h": "1e30df3a472901844f000d2c77cb27e450d0eaf2028a8469116d79da23c7271b",
  "common/trie.cpp": "807cac6c6296ca294397360fbfdd5f19a65fb7c50a587c8b56094261eec5acb2",
  "common/trie.h": "391806c154f074d63e208f5a79d4d19df07592a645d860bb2c845525afda898e",
  "common/unicode.cpp": "191c00abab788e59e83e29fb877047fcbac1f4d6088c5e9962d38ac2e694686c",
  "common/unicode.h": "219b9257ac567a3e6bcf0f552c9a9ddc01d46a15eb4d2829ae5e069e643f0ec5",
  "ggml/include/ggml-alloc.h": "d114067f9099c4a0e2bbc0625c676d4894d9cf0ea27168ee072c7de0e71bb51d",
  "ggml/include/ggml-backend.h": "34464da4b46314c710cd634626578c6f2a6811431d41eddaf5e8aa77082fea2a",
  "ggml/include/ggml-cpp.h": "bc15ba002c68685df23faae42df0d2b3d58032011f88b649021ab92485862c72",
  "ggml/include/ggml-cpu.h": "316279e004cdeb8e6ef78599acb602bf79a8abdf897fed9fd1914808c1518c6e",
  "ggml/include/ggml-opt.h": "3586de1bc8a934b5c72339e2b6937b0641e8f149b512231e666f67de0736eea2",
  "ggml/include/ggml.h": "c9400b4ea60067c690fa08fcdf365e0b2b747bd815db84d26c562eda8e99ba25",
  "ggml/include/gguf.h": "e56714aab702e5ce62ee587a409643c08f7e93e8fbb77f48ef7cc85075f96fa4",
  "ggml/src/ggml-common.h": "0061131b615c5721fc88a78feeb22c1f8c450f1c2646a317d80796a653bf595c",
  "ggml/src/ggml-impl.h": "75465b01eba2b1ecae8634898508e71294fbff0f7f96ee9ad2caf5bae5b6c5fd",
  "ggml/src/ggml-quants.h": "d8ed2c13734cbbc5016011611b6acf14905a54a7d1a3b2c6c3389164dc068418",
  "ggml/src/ggml-threading.h": "9652729043ed91482392c1aa08af5d813190d0ace2e7982d2539d28240ab8d8b",
  "ggml/src/ggml-version.h.in": "2b6f26259bfc6768229c90b127fee770f60271e74f4513d7abecb5900fa0b112",
  "ggml/src/ggml.c": "82794919af32bc5eff08000f0024be25c2567afa6f26f6b7ba72d608ffa67618",
  "include/llama-cpp.h": "26175c5711004432b5678d6b14ce711a79388ff96eeff46dab3c9f8a3694521d",
  "include/llama.h": "a806cb05ff2f218945acefc0d5e49681f41d76af5d7ef7613d954fc18c81fe2a",
  "src/llama-arch.h": "186224d2b6fba0e3224f4d99ca20c2b04ba7876d3d0bf8038553d7507d17c5bb",
  "src/llama-ext.h": "f98f7dca2865b5e7b8ec0e92a439b4d1cee3bfe13268af0c13a38168c189f6b6",
  "src/llama-grammar.cpp": "f21bd5f6017c70d2ad7358f662fc105043b1188ebbd6a147bb1d0e9a124da8b5",
  "src/llama-grammar.h": "b148f8c43e9b38afa62db670db9de900df434903e79ff57d8b0038d84e6bf040",
  "src/llama-hparams.h": "de9d9cf71aeb691ffba5016a66e79df8c647fe358bf1805d98298b464454e010",
  "src/llama-impl.cpp": "abd5851762a157ae477588537e0cfe8dddfa1d2a2efb596d17efa4a19b45c769",
  "src/llama-impl.h": "dedb12aa993f81d95ba7927ade00ed4e5b171e9b906b02cf93243e8e4c03e1e6",
  "src/llama-mmap.h": "0fff03ce62bc51b1649833f6017fbd84dc0aac7fce3b38484439153fc13ba8f5",
  "src/llama-model-loader.h": "4eb5318f7b70333015386d612738f507153770e4e5635895b2c1d8355ff22103",
  "src/llama-sampler.h": "d39c6bfd6c966acde7bfaeb55f08c176b3d9078bc5e8e8de2eee504fc66c258b",
  "src/llama-vocab.cpp": "ac6fd43eca27c67a213a98e27b87e8ca1f26d8d82a63e79543a06ca64ef10a95",
  "src/llama-vocab.h": "b201040378716d004b2ded39165f92c1cffc129a361d8c6a42d8b4a1a2fd65f4",
  "src/unicode-data.cpp": "5c80b44db0958e673a1940e2a602a5eea2725916ff67bbaeb48ecc7634f84f29",
  "src/unicode-data.h": "370697e8379a9712acd423759c076972fa5f3ec690133a9c295cd87f39c63fd1",
  "src/unicode.cpp": "bac986de7abfc4f5701fd56993b2acfb33370cd5d4fc2ca19879e11f506bc6e8",
  "src/unicode.h": "f20178df3709554d1b2514e7ba7e087fe61067b3a4c87e4b11d8e409dddaa31f",
  "tests/test-json-schema-to-grammar.cpp": "ef5baa4c84435c3cb426f2a810473995b31398a7790c5a6bf18f8a17621bdd5e",
  "vendor/nlohmann/json.hpp": "08f19bbcc66ff3082f5caf58867b1232987dba98d82e2b29d870722fce42776b"
}
CONVERTER_CPP = '#include "json-schema-to-grammar.h"\n#include <fstream>\n#include <iostream>\n#include <stdexcept>\nint main(int argc, char **argv) {\n    try {\n        if (argc != 2) throw std::runtime_error("usage: schema-convert SCHEMA.json");\n        std::ifstream input(argv[1]);\n        if (!input) throw std::runtime_error("cannot open schema");\n        common_json schema = common_json::parse(std::string(std::istreambuf_iterator<char>(input), {}));\n        std::cout << json_schema_to_grammar(schema, true);\n        return 0;\n    } catch (const std::exception &err) {std::cerr << err.what() << "\\n"; return 1;}\n}\n'
MATCHER_CPP = '#include "llama-grammar.h"\n#include "unicode.h"\n#include <fstream>\n#include <iostream>\n#include <stdexcept>\nstatic std::string read(const char *path) {\n std::ifstream input(path); if (!input) throw std::runtime_error("cannot open input");\n return std::string(std::istreambuf_iterator<char>(input), {});\n}\nint main(int argc, char **argv) {\n try {\n  if (argc != 3) throw std::runtime_error("usage: grammar-match GRAMMAR.gbnf INPUT.json");\n  auto source = read(argv[1]); auto input = read(argv[2]);\n  auto grammar = llama_grammar_init_impl(nullptr, source.c_str(), "root", false, nullptr, 0, nullptr, 0);\n  if (!grammar) throw std::runtime_error("grammar parse failed");\n  bool accepted = false; size_t offset = 0;\n  for (auto cpt : unicode_cpts_from_utf8(input)) {\n   llama_grammar_accept(grammar, cpt); ++offset;\n   if (grammar->stacks.empty()) break;\n  }\n  for (const auto &stack : grammar->stacks) if (stack.empty()) accepted = true;\n  std::cout << "{\\"accepted\\":" << (accepted ? "true" : "false") << ",\\"codepoints_processed\\":" << offset << ",\\"grammar_rules\\":" << grammar->rules.size() << "}\\n";\n  llama_grammar_free_impl(grammar);\n  return accepted ? 0 : 2;\n } catch (const std::exception &e) {std::cerr << e.what() << "\\n"; return 1;}\n}\n'
CPP_SOURCES = (
    "common/json-schema-to-grammar.cpp", "common/json-schema.cpp", "common/json.cpp",
    "common/common.cpp", "common/unicode.cpp", "common/trie.cpp",
    "src/llama-grammar.cpp", "src/llama-vocab.cpp", "src/unicode.cpp",
    "src/unicode-data.cpp", "src/llama-impl.cpp",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(argv, *, cwd, log=None):
    start = time.monotonic()
    result = subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True)
    if log:
        log.write("$ " + " ".join(str(x) for x in argv) + "\n")
        log.write(result.stdout.decode(errors="replace"))
        log.write(result.stderr.decode(errors="replace"))
        log.flush()
    return result, time.monotonic() - start


def checked(argv, *, cwd, log):
    result, _ = execute(argv, cwd=cwd, log=log)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}); see {log.name}")


def provision_sources(source):
    def fetch(item):
        relative, expected = item
        target = source / relative
        if target.exists():
            if digest(target) != expected:
                raise ValueError(f"source hash mismatch: {relative}")
            return
        url = f"https://raw.githubusercontent.com/ggml-org/llama.cpp/{UPSTREAM_COMMIT}/{relative}"
        with urllib.request.urlopen(url, timeout=60) as response:
            body = response.read()
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError(f"download hash mismatch: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(fetch, SOURCE_SHA256.items()))


def build(source, out):
    # Source remains unmodified. Match the official configure_file substitutions;
    # archive builds have unknown build commit. Version strings cannot affect grammar.
    generated = out / "generated"
    generated.mkdir(exist_ok=True)
    text = (source / "ggml/src/ggml-version.h.in").read_text()
    (generated / "ggml-version.h").write_text(
        text.replace("@GGML_VERSION@", "0.29.0").replace("@GGML_BUILD_COMMIT@", "unknown"))
    (out / "schema-convert.cpp").write_text(CONVERTER_CPP)
    (out / "grammar-match.cpp").write_text(MATCHER_CPP)
    objects = out / "objects"
    objects.mkdir(exist_ok=True)
    flags = ["-std=c++17", "-O1", "-ffunction-sections", "-fdata-sections"]
    flags += ["-I" + str(source / d) for d in ("src", "common", "include", "ggml/include", "ggml/src", "vendor")]
    object_paths = []
    with (out / "build.log").open("w") as log:
        for filename in CPP_SOURCES:
            object_path = objects / (filename.replace("/", "_") + ".o")
            checked(["g++", *flags, "-c", source / filename, "-o", object_path], cwd=source, log=log)
            object_paths.append(object_path)
        ggml = objects / "ggml.o"
        checked(["gcc", "-std=c11", "-O1", "-ffunction-sections", "-fdata-sections", "-D_GNU_SOURCE",
                 "-I"+str(source/"ggml/include"), "-I"+str(source/"ggml/src"), "-I"+str(generated),
                 "-c", source/"ggml/src/ggml.c", "-o", ggml], cwd=source, log=log)
        object_paths.append(ggml)
        for tool in ("schema-convert", "grammar-match"):
            checked(["g++", *flags, out/(tool+".cpp"), *object_paths, "-Wl,--gc-sections", "-o", out/tool], cwd=source, log=log)
        checked(["g++", *flags, source/"tests/test-json-schema-to-grammar.cpp", *object_paths,
                 "-Wl,--gc-sections", "-o", out/"test-json-schema-to-grammar"], cwd=source, log=log)


def schema_ref_audit(schema):
    definitions = schema["$defs"]
    def refs(node):
        found = []
        if isinstance(node, dict):
            if "$ref" in node:
                found.append(node["$ref"])
            for value in node.values():
                found.extend(refs(value))
        elif isinstance(node, list):
            for value in node:
                found.extend(refs(value))
        return found
    references = refs(schema)
    if not all(ref.startswith("#/$defs/") and ref[8:] in definitions for ref in references):
        raise ValueError("schema has unresolved or nonlocal reference")
    graph = {key: {ref[8:] for ref in refs(value)} for key, value in definitions.items()}
    seen, visiting = set(), set()
    def visit(key):
        if key in visiting:
            raise ValueError("cyclic local definitions")
        if key in seen:
            return
        visiting.add(key)
        for child in graph[key]:
            visit(child)
        visiting.remove(key)
        seen.add(key)
    for key in graph:
        visit(key)
    return {"definitions": len(definitions), "local_references": len(references), "acyclic": True,
            "expression_definitions": sorted(key for key in definitions if key.startswith("expr"))}


def make_fixtures():
    def response(expression):
        return {"summary":"Construct generic result", "actions":[{"tool":"construct_instrument",
                "name":"probe.json", "spec":{"inputs":[],"outputs":{"result":expression}}}], "done":True}
    nested = {"op":"add", "args":[{"op":"mul","args":[2,3]},1]}
    def depth(n):
        value = True
        for _ in range(n):
            value = {"op":"not", "args":[value]}
        return value
    misplaced = response(nested)
    misplaced["actions"][0]["spec"]["misplaced"] = True
    return [
        ("valid_nested", True, "builder", response(nested)),
        ("valid_depth32", True, "builder", response(depth(32))),
        ("invalid_depth33", False, "builder", response(depth(33))),
        ("invalid_literal_wrapper", False, "builder", response({"op":"add","args":[1,{"literal":2}]})),
        ("invalid_root_key", False, "builder", misplaced),
        ("invalid_string_action", False, "builder", {"summary":"Bad","actions":["done:true"],"done":True}),
        ("unauthorized_tool", False, "construct-only", {"summary":"Try excluded tool","actions":[{"tool":"write_document","name":"x.txt","content":"x"}],"done":True}),
        ("critic_accept", True, "critic", {"verdict":"accept","feedback":"Valid generic fixture"}),
        ("critic_unknown_verdict", False, "critic", {"verdict":"yes","feedback":"Invalid verdict"}),
    ]


def qualify(generator, source, out):
    spec = importlib.util.spec_from_file_location("native_schema_proof_generator", generator)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    permissions = ("write_document", "write_dataset", "construct_instrument", "run_instrument", "read_artifact", "retrieve_source")
    schemas = {"builder":module.response_schema("builder", permissions),
               "critic":module.response_schema("critic"),
               "construct-only":module.response_schema("builder", ("construct_instrument",))}
    reference_audit = schema_ref_audit(schemas["builder"])
    conversions = []
    for name, schema in schemas.items():
        path = out/(name+"-schema.json")
        path.write_text(json.dumps(schema, separators=(",", ":")))
        result, elapsed = execute([out/"schema-convert", path], cwd=out)
        grammar = out/(name+".gbnf")
        grammar.write_bytes(result.stdout)
        (out/(name+"-convert.stderr")).write_bytes(result.stderr)
        conversions.append({"schema":name, "schema_sha256":digest(path), "exit_code":result.returncode,
                            "seconds":elapsed, "grammar_bytes":len(result.stdout), "grammar_sha256":digest(grammar),
                            "stderr":result.stderr.decode(errors="replace")})
        if result.returncode or result.stderr:
            raise RuntimeError(f"converter failed or warned for {name}")
    upstream, upstream_elapsed = execute([out/"test-json-schema-to-grammar"], cwd=out)
    (out/"upstream-test.stdout").write_bytes(upstream.stdout)
    (out/"upstream-test.stderr").write_bytes(upstream.stderr)
    if upstream.returncode:
        raise RuntimeError("upstream converter test failed")
    fixture_results = []
    for name, expected, grammar, value in make_fixtures():
        path = out/(name+".json")
        path.write_text(json.dumps(value, separators=(",", ":")))
        result, elapsed = execute([out/"grammar-match",out/(grammar+".gbnf"),path],cwd=out)
        fixture_results.append({"name":name,"expected":expected,"grammar":grammar,"returncode":result.returncode,
                                "seconds":elapsed,"result":json.loads(result.stdout),"stderr":result.stderr.decode(errors="replace"),
                                "passed":result.returncode==(0 if expected else 2)})
    report = {"scope":"Native C++ schema conversion and grammar matching, without models or inference; no WASI execution",
              "upstream_repository":"https://github.com/ggml-org/llama.cpp", "upstream_tag":UPSTREAM_TAG,
              "upstream_commit":UPSTREAM_COMMIT,"source_files":len(SOURCE_SHA256),
              "source_manifest_sha256":hashlib.sha256(json.dumps(SOURCE_SHA256,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
              "generator_sha256":digest(generator),"compiler":subprocess.check_output(["g++","--version"],text=True).splitlines()[0],
              "reference_audit":reference_audit,"conversions":conversions,
              "upstream_test":{"exit_code":upstream.returncode,"seconds":upstream_elapsed,
                               "case_lines":sum(line.startswith("- ") for line in upstream.stderr.decode().splitlines())},
              "fixtures":fixture_results,"passed":all(result["passed"] for result in fixture_results),
              "limits":["Grammar constrains syntax, not evaluator truth or authorization.",
                        "Local no-inference proof does not establish model generation quality, server behavior, cross-platform coverage or released-source qualification.",
                        "Object-key order follows schema insertion order in this pinned converter."]}
    (out/"native-converter-proof.json").write_text(json.dumps(report,indent=2)+"\n")
    if not report["passed"]:
        raise RuntimeError("grammar fixture failed; inspect native-converter-proof.json")
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-dir",type=Path,required=True)
    parser.add_argument("--source-dir",type=Path,help="Optional existing upstream tree; every required file is hash checked")
    parser.add_argument("--generator",type=Path,default=Path(__file__).resolve().parents[1]/"bridge/workflow_schemas.py")
    args=parser.parse_args()
    out=args.proof_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    source=(args.source_dir or out/"llama.cpp").resolve()
    provision_sources(source)
    build(source,out)
    report=qualify(args.generator.resolve(),source,out)
    print(json.dumps({"passed":report["passed"],"upstream_commit":UPSTREAM_COMMIT,"fixtures":len(report["fixtures"]),
                      "report":str(out/"native-converter-proof.json")}))


if __name__=="__main__":
    main()
