# Explicit local schema output

HARNESS can request a bounded JSON Schema from an explicitly enabled local
compatible-chat or Ollama model. This is separate from ordinary `json_mode`:
valid JSON alone does not establish the expected action or expression structure.
The capability is off unless the operator declares `json_schema: true` for the
exact installed model/server combination. It is not inferred from a model name,
a discovery response or OpenAI API compatibility.

```json
{
  "local_only": true,
  "providers": {
    "local-llama": {
      "kind": "openai",
      "base_url": "http://127.0.0.1:8080/v1",
      "output_limit_field": "max_tokens",
      "models": {
        "installed-model-id": {
          "input_per_million": 0,
          "output_per_million": 0,
          "max_output_tokens": 4096,
          "input_token_overhead": 4096,
          "json_mode": true,
          "json_schema": true
        }
      }
    }
  }
}
```

This example declares no API token charge; hardware and operation costs remain
separate. Start and qualify the selected local server independently. No server
or model is installed by this option, and another local program's network
behavior is outside this adapter's guarantee.

Pass an ordinary schema object in `data["json_schema"]` to `Runtime.generate(data)`,
alongside the existing provider, model, prompt,
run ID and output limit. `required_capabilities: ["json_schema"]` is also
available for explicit routing. A schema request does not need `json_mode: true`.

```python
result = runtime.generate({
    "provider": "local-llama", "model": "installed-model-id",
    "run_id": "explicit-schema-attempt", "prompt": "Return a short summary.",
    "max_output_tokens": 256,
    "json_schema": {
        "type": "object",
        "properties": {"summary": {"type": "string", "minLength": 1}},
        "required": ["summary"], "additionalProperties": False
    }
})
```

## Wire contract and source evidence

For a loopback `openai` provider HARNESS sends:

```json
{"response_format":{"type":"json_schema","json_schema":{"name":"harness_output","strict":true,"schema":{"type":"string"}}}}
```

This is the nested wrapper parsed by llama.cpp **b12242**:
[server parser](https://github.com/ggml-org/llama.cpp/blob/b12242/tools/server/server-common.cpp)
and [server format tests](https://github.com/ggml-org/llama.cpp/blob/b12242/tools/server/tests/unit/test_chat_completion.py).
The metadata `name` and `strict` do not substitute for local validation.
The [pinned grammar guide](https://github.com/ggml-org/llama.cpp/blob/b12242/grammars/README.md)
warns that unsupported features may be ignored. HARNESS therefore accepts an
explicit subset and rejects unknown keywords instead of stripping them.

For local `ollama`, the same schema is sent directly as `format`, as documented
in [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
That documentation explicitly excludes Ollama cloud. HARNESS refuses schema
capability configuration for remote endpoints and other protocol kinds.
Protocol support and synthetic tests do not establish live model reliability.

## Supported schema subset

- Scalar types: string, number, integer, boolean and null.
- Objects with declared `properties`, `required` fields and an explicit
  `additionalProperties: false` or supported value schema.
- Arrays with an `items` schema and optional `minItems` / `maxItems`.
- String `minLength` / `maxLength`; integer `minimum` / `maximum`.
- `const`, `enum`, standalone `anyOf`, and bounded `title` / `description`.
- Acyclic references of the exact form `#/$defs/name` to named root definitions.
  References have no constraint siblings. Remote, nested-pointer and recursive
  references are refused. The pinned
  [schema parser](https://github.com/ggml-org/llama.cpp/blob/b12242/common/json-schema.cpp)
  and [converter tests](https://github.com/ggml-org/llama.cpp/blob/b12242/tests/test-json-schema-to-grammar.cpp)
  provide the implementation evidence; the generic workflow schema must also
  pass the separately recorded no-inference converter qualification.

Schemas are capped at 256 KiB, 8,192 JSON nodes, 48 raw nesting levels,
128 definitions and 64 reference hops. Array/string limits are capped at
4,096 items / 65,536 characters. Completed values have a separate bounded
validation budget. These are parser resource bounds, not business or mission
limits. The pinned llama.cpp guide describes the schema as an output grammar,
not prompt content. HARNESS leaves the prompt unchanged. Its generic request
estimate nevertheless includes schema bytes conservatively; this estimate is
not observed input-token usage. An explicit `context_window` can therefore
refuse a large schema conservatively. Provider-reported usage, when available,
supplies the actual token counts used for the returned accounting.

Empty schemas, unconstrained additional properties, patterns, formats,
`minProperties`, conditionals, recursion and other undeclared keywords are
rejected. `number` does not accept numeric bounds because the pinned grammar
does not implement them; semantic numeric checks remain necessary.

## Acceptance and failure behavior

HARNESS parses the completed response as finite JSON with no duplicate keys and
validates it against the accepted schema. A valid result includes
`structured_output.mode`, `validated` and `schema_sha256`. This establishes only
structural conformance. Tool authorization, valid field names, expression
semantics, resource limits, independent tests and expected outputs remain the
responsibility of the workflow and evaluator.

Schema requests make at most one attempt even when ordinary requests are
configured for retries. There is no retry without the schema, protocol switch,
provider fallback or API billing activation. An unsupported capability or
invalid schema fails before provider dispatch and budget reservation. A failed
completed response is rejected with `SCHEMA_RESPONSE`; already consumed usage
remains accounted. Streaming fragments are held until full schema validation.
Native function declarations cannot be combined with this capability.

Offline contract checks:

```sh
python -B -m unittest discover -s tests -p 'test_output_schema.py' -v
```

These tests use synthetic senders and do not authenticate or invoke a model.
