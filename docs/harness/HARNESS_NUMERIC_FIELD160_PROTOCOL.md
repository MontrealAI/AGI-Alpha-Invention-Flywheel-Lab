# HARNESS160 — frozen diagnostic for undeclared numeric references (pre-code)

Source base: `61bd5fad57d373c2e806171bccc4cac8047e03ae` (current published main on 2026-11-14). Branch: `experiment/harness-numeric-field-feedback160-20261114`.

## Observed failure and purpose

The existing historical Qwen3-1.7B local single-builder run in `products/alpha-genesis-harness/evidence/live-local-workflows-v0.3-equality-fixed.json` remains **FAIL** (three model calls exhausted; numeric literal 2 supplied as undeclared `{"field":"2"}`; not an observed repair). The independent bounded instrument evaluator currently reports only `Input field root was not declared.` for this mistake. That error is technically correct but omits the distinction between a value literal and an input reference. A competent person reading the actual JSON could fix it; this limited improvement should make the same correction understandable in the model's deterministic feedback without weakening verification.

## Frozen hypothesis, tests and strong ordinary control

**No automatic mutation:** Preserve the evaluator and declaration semantics. When and only when an undeclared `field` reference is a safe, short JSON-numeric token (e.g., `2`, `-3`, `1.5`, `2e3`), the evaluator refuses it and provides a bounded, source-independent explanation: numeric constants are raw JSON numbers and `{"field":...}` is only for declared inputs. It must not echo arbitrary untrusted input names or leak source data. Non-numeric unknown fields preserve the original generic error and rejection. Declared string field names such as `"2"` still resolve as before; valid constant expressions behave identically.

**Pre-registered cases:** (1) historic `{"field":"2"}` fails, message explains literal; (2) matched ordinary/competent corrected `2` passes 34 at x=17; (3) declared `"2"` works; (4) short signed fractional/exponential numbers refuse with same class; (5) nonnumeric unknown name retains old generic error; (6) hostile long and control-character reference retains bounded generic error; (7) nested binding path with numeric undeclared name fails, without bypass; (8) original legitimate nested input path works; (9) operation bound and `__proto__` prohibitions unchanged. Existing full Python product test suite remains a regression gate. The expected improvement is **error specificity, not model behavioral success**. Frozen past local-model and hosted results must never be relabeled, and no new paid inference or downloaded model is permitted.

**Strong alternative:** Existing generic error plus competent human JSON inspection and ordinary repair; this improvement cannot claim new algorithmic capability, a cost advantage, or that a different model will revise correctly. A frozen synthetic mock model receiving the more explicit feedback may serve only as engineering contract evidence, not a new real-model confirmation.

## Boundaries and acceptance

Change only `products/alpha-genesis-harness/bridge/instruments.py` and a distinct HARNESS160 test file, plus this protocol and an operator-facing compact report if warranted. Do not change acceptance, auto-rewrite bad model output, budget, provider routes, independent verification, rights, commerce, `Account`, `JournalAccount`, HMAC, signed queues, release guards or historical evidence. Source-bound focused and full product checks must run at candidate exact head; archive and normal protected release qualification remain separate. PR330/339's G1 verification ownership is untouched. No credentials, model downloads, paid APIs, spending, outreach, transactions or deployment.

Stop on any semantic regression; preserve failures. If all checks pass, retain a draft additive PR for normal independent qualification and owner-safe integration. A code/test pass does not resolve local-model failure, commercial buyer demand, actual cost, original-account migration or the US$3B trailing-365 profit objective. The larger Blue Sky mission continues separately.

Decision tree: **accept diagnostic as supporting engineering** if all nine cases pass and no evaluator behavior relaxes; otherwise reject/revise. Do not select cases after observing the result.
