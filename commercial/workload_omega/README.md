# 🌌♾️ WORKLOAD Ω — Verified AI-Workload Optimization (Shadow Research)

**EN:** Reduce the cost of an identical AI workload only after beneficiary-labelled quality, latency and cost survive paired training and untouched holdout comparisons. **FR :** Réduire le coût d'une charge de travail d'IA uniquement lorsque la qualité évaluée par le bénéficiaire, la latence et les coûts passent des comparaisons appariées sur les jeux d'entraînement et de validation réservée.

This is an additive, zero-network and zero-payment **commercial candidate**, not an admitted Blue Sky frontier invention and not deployed HARNESS model routing. It uses ordinary deterministic software and owner-provided measurements. It cannot by itself authenticate providers' bills, acceptance criteria or independent holdout construction. Source [preregistration](PROTOCOL.md) precedes the implementation.

## Execute / Exécuter

```sh
python3 -m unittest discover -s tests -p 'test_workload_omega.py' -v
python3 -m commercial.workload_omega.engine commercial/workload_omega/sample.json
```

All sample cases and fees are **synthetic**. The sample is intentionally not commercial evidence. Run locally with an explicitly authorized non-sensitive JSON cohort. Input format is illustrated by [sample.json](sample.json); integer cost unit is **microUSD**, so 1,000,000 microUSD = US$1. Preserve exact paired case identity and per-arm external acceptance judgments. Each case appears in only one cohort and is evaluated once per arm. Set a prospective latency ceiling, minimum sample counts, and minimum observed acceptance (basis points).

The engine selects the lowest measured *eligible* cost on training cases, freezes that selection, and then qualifies it on holdout. Its conservative zero-regression filter and empirical maximum latency rule are intentionally restrictive but do not provide statistical assurance. **No holdout-based second chance.** Reported gross savings and monthly margins are modeled from entered prices, volumes and costs. A positive model is not a sales contract, revenue, complete cost audit or permission to route traffic.

### Interpretation / Interprétation

- `HOLD_TRAINING`, `HOLD_HOLDOUT`, `HOLD_ECONOMICS`: refusal; do not deploy / refus de déploiement.
- `ENGINEERING_ONLY`: synthetic paired experiment only / essai technique synthétique uniquement.
- `SHADOW_CANDIDATE`: externally claimed measurement still unauthenticated / mesure non authentifiée; still **no deployment authority**.
- `NOT_MODELED` means economics are unknown, **not free** / économies inconnues, non gratuites.

The engine never produces `first_dollar_proven = true`, `live_deployment_authorized = true` or `second_distinct_asset_proven = true` from an observation file. To cross those gates requires outside-account evidence, accepted delivery, actual cleared payment, and a second independently valuable capability with matched ordinary-reuse and no-retention controls.

## Next authorized evidence gates / Prochaines étapes

1. Obtain an authorized buyer-owned representative workload and independent quality acceptance, with strict confidentiality and right to use the data. Do not commit customer inputs publicly.
2. Compare against current direct supplier choices and competent existing routers/optimizers on fresh matched inputs. Record full inference, integration, verification, monitoring, support, and acquisition costs as actually billed.
3. Run a no-impact shadow evaluation and independently audit savings. Qualify a reversible canary deployment only after separate operational and contractual authority.
4. Offer recurring value capture on actual accepted savings; reconcile real merchant settlement and recurring margin without using model estimates as cash.
5. Reuse retained mechanisms in a distinct outcome-producing second asset and run an equal-content ordinary-reuse control and no-retention control. If they tie, record **ordinary reuse**, not invention advantage.

**Boundary:** no tokens, checkout, paid model calls, account changes, customer outreach, deployment, or native-ledger transactions. Public code is inspectable, not a customer-ready product. **Limite :** aucun paiement, appel de modèle payant, contact client ni déploiement.
