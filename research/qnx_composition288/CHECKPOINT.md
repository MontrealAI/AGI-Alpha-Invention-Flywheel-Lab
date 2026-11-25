# QNX composition 288 — 2026-11-25

## Decision

Independent source analysis, not a native financial operation or target execution. Main observed b35f937fcb77199334e267360e9a0c9e438a74ad. No competing account, production deployment, outreach, entry, paid API, purchases, or new credentials. Source/finance ownership remains untouched. Whole-episode resources and billing unknown.

Compare three different arrangements plus no entry:
* Embedded portability and integration: [QNX sponsor](https://qnx.software/en/press-release/2026/qnx-launches-global-developer-hackathon) and [rules](https://qnx.devpost.com/rules), $50k prize pool, deadline Dec 15 14:00 EST, eligible entities subject to full rules. Noncommercial SDK not a commercial license. Strong complete incumbent: official ports and qnx-porter. Choose investigation of composition rather than duplicate generic port agent.
* Geothermal fault inference: [GEMS](https://www.drivendata.org/competitions/306/), $300k prize pool, Dec 3 22:00 UTC, expert labels revised in final round, gated competition data and eligibility not established. Strong alternative: sponsor reference model and geophysical experts. No entry.
* Temporal biomedical reasoning: [NIH](https://www.nih.gov/challenges/its-about-time-temporal-reasoning-biomedical-knowledge-graphs-challenge), $1m pool across two phases, phase one Jan 15 2027. Existing temporal graph approaches and clinical expertise; eligibility and accessible evaluation inputs unestablished. No entry.
* No-deploy is the chosen operating action. Prizes are competitive ceilings, not revenue or demand. No verified complete-cost offer, capacity, price acceptance, or customer.

## Actual analysis of strongest executable alternative

Pinned [qnx-porter CSV](https://github.com/thegoodengineers/qnx-porter/blob/b546eca2fb1177eae9721a69e749f3723cfbee61/results/ports.csv) Git blob 774fc8f27d639c6b83b8d5d31251f1e55a3bc4d6. Two text parsing implementations agreed on architecture aggregates. Later source revision differs from the PyPI README headline; use the pinned CSV. All 122 rows in 61 matched library/version pairs were retained. Results are a third-party report analysis, not independent QNX execution. Strict observed-test screen: built, positive test count, all reported tests pass, no reported unrunnable tests. This is not full acceptance, certification, complete test coverage or a preregistered scientific hypothesis.

| Architecture | Built/61 | Reported tests passed/total | Screen passes/61 |
|---|---:|---:|---:|
| x86_64 | 58 | 1563/1658 | 23 |
| aarch64le | 58 | 1546/1642 | 22 |

58 pairs build both architectures; 22 pass the strict screen on both, including 12 marked absent from the official catalogue in the source CSV. No independent catalogue completeness or currency claim. No model-written patches recorded. A broad autonomous port agent is therefore not an established residual.

A specific productive composition remains worth investigating: turn already built client and broker into an executable verified communication environment. [Paho report](https://github.com/thegoodengineers/qnx-porter/blob/b546eca2fb1177eae9721a69e749f3723cfbee61/ports/paho.mqtt.c/report.json) blob 33525202cc0dd6a26ef7e518c14701ab3ab947ff reports v1.3.16 built but tests not run because a broker is needed. [Mosquitto report](https://github.com/thegoodengineers/qnx-porter/blob/b546eca2fb1177eae9721a69e749f3723cfbee61/ports/mosquitto/report.json) blob 663664490bf48e707a5ff6a6d573c9a8da229db2 reports v2.1.2 built but zero tests. It needs cJSON and SDP OpenSSL for TLS. The [actual Paho upstream test definitions](https://github.com/eclipse-paho/paho.mqtt.c/blob/4a939ddb01eea581a32fd6f0adcfee51b91d2601/test/CMakeLists.txt) blob 32ccbf886b26a47d4b8e22d395e7bd8375f0f777 contain 279 distinct literal add_test declarations, conditional on build options, not 279 guaranteed runnable tests. Parsing the literal NAME/COMMAND blocks found:

| Explicit command variable set | Declarations |
|---|---:|
| MQTT_TEST_BROKER | 64 |
| MQTT_TEST_BROKER + MQTT_TEST_PROXY | 84 |
| MQTT_WS_TEST_BROKER | 6 |
| MQTT_WS_TEST_BROKER + MQTT_WS_TEST_PROXY | 37 |
| MQTT_SSL_HOSTNAME | 88 |

Broker alone is insufficient for full acceptance: source explicitly uses proxy, WebSocket and TLS settings; command variables are only lower bounds on dependencies. No target fixture is qualified. No invented tests or output. Initial upstream retrieval via eclipse/paho.mqtt.c failed; exact source was retrieved via eclipse-paho/paho.mqtt.c. Separately, [nng report](https://github.com/thegoodengineers/qnx-porter/blob/b546eca2fb1177eae9721a69e749f3723cfbee61/ports/nng/report.json) blob 427179e044404c828cb7b7696a92b04a9f155dfd reports 3/64 tests and 60 hangs on x86_64; root cause not established. Do not equate compilation with delivery.

Next concrete discriminator if licensed target access is already available: configure full fixture for a fixed Paho build from exact upstream source, reproduce CTest inventory, compare competent ordinary manual setup and reusable composition with identical SDK/target/test requirements, count all setup, test, correction and maintenance costs. No access to qualified QNX environment established in this run; do not register or acquire licenses under current permissions. No implementation, trial or performance advantage asserted.

## Engineering and ownership

[Prior main release](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45709821362) failed publication after engineering pass: gate error EXACT_MAIN_QUALIFICATION_FAILED:adaptive012.yml. Exact-head adaptive workflow [45709821596](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45709821596) was cancelled. Source adaptive012.yml has cancel-in-progress: true. Do not relabel as pass or infer numerical defect; no retry of superseded main. Current main [45715434890](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45715434890) was still qualifying at inspection, current adaptive check passed. Historical PR77 open at cd5281b0ae7b484572bfb35ccb7e51ef5b3be4b3. Original native-capital candidate branch still at 3981b182513abbba1c2ab1102f94732c453422fa. Separate public composition heads d1d4030db8c67e19cfe5d6eec0735f2c5900eaa0 and 7d75766401adede49afd2427be82eb0302934b80 do not establish actual local signer-owner checkpoint. Durable overnight022 handoff, matrix, report, feature and independent review read; preserve all prior failures and liabilities.

| Acceptance | Status |
|---|---|
| Source comparison and literal fixture dependency extraction | Achieved, exploratory |
| QNX fixture construction / target execution | Blocked, environment not established |
| Independent full delivery or economic gain | Unqualified |
| Financial migration / native same-account operations | Blocked, actual handoff unavailable |
| Commercial receipts, native trailing-365 profit | None new / null |
| $3B target | Unachieved |

No financial mutation or protected integration. This branch is evidence only, not a release.
