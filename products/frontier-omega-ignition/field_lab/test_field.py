import copy
import json
from pathlib import Path
import tempfile
import unittest

import capture
import field
from protocol import accepted, decode, FIXTURE_TOKENIZER, HERE, NATIVE_TOKENIZER, read_workload, validate_authority
from verify import parse_wire, verify, verify_public


class FieldQualification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = HERE / "workload.json"
        self.w, self.digest = read_workload(self.work)
        self.nominal = decode((HERE / "evidence/nominal-field.json").read_bytes())
        self.adverse = decode((HERE / "evidence/adverse-field.json").read_bytes())

    def write(self, data, name="test.json"):
        path = Path(self.temp.name) / name
        path.write_text(json.dumps(data))
        return path

    def test_registered_public_receipts_rebuild_all_eight_load_decisions(self):
        rows = verify_public(self.work,HERE / "PUBLIC.json")
        self.assertEqual(len(rows),8)
        for row in rows:
            good = row["target"] == "nominal"
            self.assertEqual(row["requests"],6)
            self.assertEqual(row["attempts"],6 if good else 7)
            self.assertEqual(row["transport_complete"],6 if good else 3)
            self.assertEqual(row["first_attempt_failures"],0 if good else 4)
            self.assertEqual(row["quality_accepted"],6 if good else 2)
            self.assertEqual(row["decision"],"accept-registered-replay" if good else "withhold")

    def test_fixture_replays_both_transports_without_network_authority(self):
        output = Path(self.temp.name) / "fresh"
        observation = field.fixtures(self.work,output)
        rows = verify_public(self.work,output / "PUBLIC.json")
        self.assertEqual(rows,observation["arms"])
        self.assertEqual([r["quality_accepted"] for r in rows],[6,6,6,6,2,2,2,2])
        self.assertEqual(observation["field_decision"],"defer")

    def test_cannot_silently_replace_trace_or_decision(self):
        def drop(x):
            x["loads"][0]["turns"].pop()
        def flip(x):
            x["metrics"][0]["decision"] = "accept-production"
        def wall(x):
            x["loads"][0]["turns"][0]["attempts"][0]["events"][0][0] = -1
        def identity(x):
            x["loads"][0]["turns"][0]["attempts"][0]["request_sha256"] = "f"*64
        def substitute(x):
            entry = next(iter(x["tokenizations"].values()))
            entry[0] += 1
        def price(x):
            x["cost"]["all_in_cost"] = 0
        def remove_retry(x):
            x["loads"][0]["turns"][2]["attempts"].pop()
        for mutate in (drop,flip,wall,identity,substitute,price,remove_retry):
            with self.subTest(mutate=mutate.__name__):
                data = copy.deepcopy(self.adverse)
                mutate(data)
                with self.assertRaises(ValueError):
                    verify(self.work,self.write(data))

    def test_source_and_workload_are_frozen(self):
        data = copy.deepcopy(self.nominal)
        data["source"]["capture.py"] = "0"*64
        with self.assertRaisesRegex(ValueError,"source"):
            verify(self.work,self.write(data))
        changed = json.loads(self.work.read_bytes())
        changed["thresholds"]["p90_turn_ms"] += 1
        with self.assertRaisesRegex(ValueError,"workload"):
            verify(self.write(changed),HERE / "evidence/nominal-field.json")

    def authority(self):
        return {"schema":1,"scope":"public-synthetic-pilot","target":"test-only-loopback",
                "base_url":"http://127.0.0.1:1234","model":"test-only-tokenizer-adapter",
                "model_sha256":"b"*64,"runtime_sha256":"c"*64,"hardware":"unit-test",
                "configuration":"synthetic native protocol","workload_sha256":self.digest,
                "max_concurrency":3,"max_attempts":24,"tokenizer":NATIVE_TOKENIZER,
                "locally_owned_no_forwarding":True}

    def test_authority_excludes_unowned_targets_changed_purpose_and_unfunded_replay(self):
        a = self.authority()
        self.assertEqual(validate_authority(a,self.w,self.digest),1234)
        for url in ("http://localhost:1234","https://127.0.0.1:1234","http://127.0.0.1:1234/",
                    "http://127.0.0.1:1234@elsewhere.test","http://127.0.0.1:1234/other","http://2130706433:1234"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_authority(dict(a,base_url=url),self.w,self.digest)
        for edit in ({"max_concurrency":2},{"max_attempts":23},{"model_sha256":"missing"},
                     {"locally_owned_no_forwarding":False},{"tokenizer":FIXTURE_TOKENIZER},{"scope":"fixture"}):
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                validate_authority(dict(a,**edit),self.w,self.digest)
        with self.assertRaises(ValueError):
            validate_authority(dict(a,workload_sha256="f"*64),self.w,"f"*64)

    def test_json_quality_requires_actual_values_and_correct_numeric_types(self):
        self.assertTrue(accepted('{"n":1.00,"v":[2]}',{"v":[2.0],"n":1}))
        for output in ('{"n":1.00000000000000001,"v":[2]}','{"n":true,"v":[2]}','{"n":1,"n":1,"v":[2]}','{"n":1,"v":[2],"extra":0}',
                       '{"n":1,"v":[null]}','{"n":NaN,"v":[2]}','text {"n":1,"v":[2]}'):
            with self.subTest(output=output):
                self.assertFalse(accepted(output,{"v":[2],"n":1}))

    def test_incomplete_generation_identity_and_stop_are_checked_by_both_readers(self):
        a = copy.deepcopy(self.nominal["loads"][0]["turns"][0]["attempts"][0])
        model = self.nominal["target"]["model"]
        self.assertTrue(capture.read_events(a,model)[2])
        for mode in ("length","empty","different-id","tool","missing-terminal","error-frame"):
            changed = copy.deepcopy(a)
            events = changed["events"]
            if mode == "missing-terminal":
                events.pop()
            else:
                for i,event in enumerate(events[:-1]):
                    data = json.loads(event[1])
                    if mode=="length" and data["choices"][0]["finish_reason"]:
                        data["choices"][0]["finish_reason"] = "length"
                    if mode=="empty":
                        data["choices"][0]["delta"]["content"] = ""
                    if mode=="different-id":
                        data["id"] = str(i)
                    if mode=="tool":
                        data["choices"][0]["delta"]["tool_calls"] = []
                    if mode=="error-frame":
                        data["error"] = {"message":"failed"}
                    event[1] = json.dumps(data)
            with self.subTest(mode=mode):
                self.assertFalse(capture.read_events(changed,model)[2])
                self.assertFalse(parse_wire(changed,model)[2])

    def test_missing_tokenizer_evidence_cannot_admit_performance(self):
        a = self.authority()
        a["model"] = self.nominal["target"]["model"]
        stats = field.summary(self.w,a,1,self.nominal["loads"][0]["turns"],{})
        self.assertEqual(stats["quality_accepted"],6)
        self.assertIsNone(stats["p10_delivered_tokens_per_turn_second"])
        self.assertEqual(stats["decision"],"withhold")

    def test_live_adapter_uses_verifiable_post_run_native_ids(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading

        class NativeStub(BaseHTTPRequestHandler):
            def log_message(self,*_):
                pass

            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(200)
                if self.path=="/tokenize":
                    if (req["add_special"],req["parse_special"]) != (False,False):
                        raise ValueError("wrong visible-text tokenization")
                    self.send_header("Content-Type","application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"tokens":[123,456]}).encode())
                else:
                    self.send_header("Content-Type","text/event-stream")
                    self.end_headers()
                    for frame in ({"choices":[{"index":0,"delta":{"content":'{"status":"defer"}'},"finish_reason":"stop"}]},
                                  {"choices":[],"usage":{"prompt_tokens":25,"completion_tokens":6}}):
                        frame["model"] = req["model"]
                        self.wfile.write(("data: "+json.dumps(frame)+"\n\n").encode())
                    self.wfile.write(b"data: [DONE]\n\n")
        serv = ThreadingHTTPServer(("127.0.0.1",0),NativeStub)
        thread = threading.Thread(target=serv.serve_forever,kwargs={"poll_interval":0.01},daemon=True)
        thread.start()
        try:
            auth = dict(self.authority(),base_url=f"http://127.0.0.1:{serv.server_port}")
            raw = field.run(self.w,self.digest,auth,"field")
            answers = verify(self.work,self.write(raw),self.write(auth,"authority.json"))
            self.assertEqual([row["quality_accepted"] for row in answers],[2,2])
            self.assertEqual(raw["cost"]["tokenizer_http_queries"],1)
            self.assertEqual(raw["cost"]["usage_complete_attempts"],12)
            self.assertEqual(raw["cost"]["reported_completion_tokens_on_those_attempts"],72)
            self.assertEqual(list(raw["tokenizations"].values()),[[123,456]])
            raw["tokenizations"][next(iter(raw["tokenizations"]))]=[999,456]
            with self.assertRaisesRegex(ValueError,"tokenizer did not reproduce"):
                verify(self.work,self.write(raw),self.write(auth,"authority.json"))
        finally:
            serv.shutdown()
            serv.server_close()
            thread.join()


if __name__=="__main__":
    unittest.main()
