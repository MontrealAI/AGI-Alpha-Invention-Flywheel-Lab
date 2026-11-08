# Offline citation098 — independently replay exact public evidence without the producer

**Scope:** a supporting source-integrity instrument. No issuer signature, legal judgment, buyer acceptance, real sale, account migration, full CSS/browser visibility or US$3B profit is certified.

The independent reviewer needs **their own lawful local copy of the exact HTML bytes observed on 8 November 2026** for both registered public pages, and a key-free `packet` object taken from the original public `REGULATORY_CITATION097_RESULT.json` artifact (PR #300). GitHub artifacts publish hashes and quoted-claim summaries, **not raw government HTML**; the original bytes are not reconstructible from SHA-256. A newer page from the same URL is *not* an acceptable replacement if its hash differs. An independent party with no exact byte archive must report `NOT_EXECUTED`, not pass.

## Private caller inputs (not added to Git)
Use a caller-controlled absolute directory containing **exactly** these two files: `tbs-directive-2025.html` (69,865 bytes), `ssc-challenge-2026.html` (63,094 bytes). They must match the immutable externally pinned SHA-256 in [PROTOCOL.md](PROTOCOL.md). They need not be shared with GitHub or this research branch. Obtain the prior `packet` from the existing key-free public report rather than rewriting quotes or selecting new documents. For example, if the previous observation JSON is available locally at `/private/OBSERVATION.json`, extract its packet without copying any page text:

```sh
python3 - <<'PY'
import json
from pathlib import Path
observed = json.loads(Path('/private/OBSERVATION.json').read_text())
Path('/private/PACKET.json').write_text(json.dumps(observed['packet'], sort_keys=True))
PY
python3 -m research.regulatory_portable_audit098 verify \
  --sources-dir /private/exact-original-html \
  --packet /private/PACKET.json \
  --output /private/new-REPLAY-RESULT.json
```

Exit 0 means all source bytes match the **independently pinned historical public-observation SHA-256 and sizes**, and all three frozen mechanical citations/packet fields replay against those bytes. Exit 1 means **refused** with a minimal, key-free JSON receipt, not evidence of an invalid government document. No network request, key, account, private data upload, paid API, or mutation of the source files occurs. The receipt never contains source text, caller path or signing material and refuses output overwrite. Keep the raw pages and observation packet in appropriately permitted caller custody; do not commit, upload or redisclose them through this workflow.

The source of public trust pins is the *previously completed exact-page hosted observation* recorded on PR #300, not a self-asserted hash inside the producer's packet. A dishonest producer cannot change those precommitted pins through its supplied packet. **This is not source-origin cryptographic authentication.** A compromised GitHub record, misidentified public page or changed live source remains outside this narrow proof.

## Exact CI scope
The dedicated workflow `regulatory-portable-audit098` runs R0–R5 synthetic pages **only**, plus unchanged C/H/N controls; it must explicitly report `actual_original_source_replay=NOT_EXECUTED`. It never downloads the historical official HTML or calls the source `observe` operation, and its success must not be represented as real-source replay. R6/R7 remain categorical requirements. Older failed real workflow and unrelated chemistry failures remain failed. All P0 original-owner account and source custody restrictions still apply.

## Commercial gate
The primary competing complete workflow remains a qualified specialist using competent conventional search and document tools; independent paid acceptance and full costs are unknown. Do not bid, deploy or recognize profit from this packet. The Blue Sky program's three candidate arrangements and no-deploy are unchanged. This witness would be useful only if it makes a larger rights-cleared, independently accepted workflow more reliable than strong existing methods.
