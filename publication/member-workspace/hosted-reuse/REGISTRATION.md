# Same-contract workshop reuse replay

Run the original vertical qualification from hosted job 139358308706 in an isolated checkout. The historical experiment and its FAIL verdict remain the reference. This is a local replay on a different Linux host with a tested runtime guard and a frozen source snapshot.

- Historical reviewed revision `504a4c86dae6568e7b50eb09f371c515e5398063` and exact product tree `c7fc43f31762992a59acd28d554a3448591ca50e`.
- Isolated corrected revision `fca798fd830c1e1e81ddb8e3359ab08675faf2fe`. Changes are limited to `bridge/workshop.py` and `bridge/workflows.py`.
- Historical runtime archive `909eef25cd53e6601c8a07c866d8dbb2983e74177088d55182137a8fb8255d62` and b12242 server binary `fe211d00c4754aa67aaa492d2c755ab0f6ef60bf30eee3c0c74a3496189cde17`.
- Historical 4B GGUF `2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e`, 2,497,280,736 bytes. The separately pinned upstream Apache 2 license is `832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e`.

Use the unchanged `qualify_workshop.py` vertical driver, two CPU threads, 16,384-token context, seed 315 and temperature zero. Keep the fixed model aliases, per-request limits, transport, independent development and final case sets and portable replay conditions. Neither private observations nor expected values enter the model prompt. The retained predecessor must independently pass the fresh development cases under the same public contract. The runtime may refuse a proposed replacement without suppressing the model's real recorded completion. Then the existing final verifier and export gate run.

A successful local run needs four original vertical cases complete, matching source identities and a real completion from the pinned model on each. All four portable exports must replay. The two foundry instruments must have identical bytes. Record all failing cases, stale samples and issued model calls. This comparison begins after a prior hosted result and does not establish blinding or change the prior decision. Reproducing the hosted environment requires its own source-reviewed exact build and replay.
