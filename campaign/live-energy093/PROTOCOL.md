# Live energy093: prospective post-gate construction

Registered 2026-11-04 before Nov5 wind/load outcomes exist. This is an independently published forecast consumer, not an official Foretec entry, an original foundation model or a trading strategy. No external submission, registration, API key, payment or account operation.

## Why this task

Three alternatives were inspected: previously measured GFP assay selection is defeated by public-label lookup; passive-friction construction still lacks physical mixed-contact validation; live grid forecasting provides genuinely future outcomes with strong published competitors. Select the last for a finite prospective test. Existing forecasting and median ensembles are capable complete alternatives. A new valuable or profitable service is not presumed.

Public source: https://energybench.foretec.co/data/days/YYYY-MM-DD.json, CC BY4.0; code https://github.com/ujohn33/foretec-energy-bench, Apache2. The source already publishes classical, foundation, ensemble and operator forecasts. Preliminary aggregate standings and Nov2/Nov4 schema were inspected; therefore historical results are development diagnostics, never fresh evidence. Only wind/load for BE,NL,FR,DE,DK1,DK2 enter this test. Price data are ignored.

## Frozen executable comparison

Issue2026-11-04, delivery2026-11-05. Snapshot today once, retaining full source SHA256 and compact used inputs. Current market gate(11:00UTC) has passed: this is explicitly post-gate, inadmissible for day-ahead trading claims. All future actuals must be null or absent; otherwise stop. Finish and publish output before delivery starts at2026-11-04T23:00Z. Data from issue2026-11-03 are prohibited for fit because its delivery is not finished.

Fit on issue dates2026-10-20 through2026-11-02 as read now. Model members fixed: chronos2_cov,timesfm3_cov,t0_gamma_cov,tirex2_cov,timestral_cov,lgbm_prod. For each series use only complete96-point days with every member and finite actuals. Require at least7 such days; otherwise mark that series unavailable rather than substitute data. Each member must also have96 finite future predictions. Do not fill missing predictions from future outcomes.

Constructor: nonnegative convex weights summing to1, minimizing mean absolute training error plus0.02*mean(abs(training_actuals))*L1(weight-uniform). Fixed regularization, no tuning on future. Use SciPy HiGHS linear programming, independently check feasibility/objective arithmetic. It is a known conventional stacking method, not autonomous invention. Strong comparators: each fixed member, equal mean, equal median, published ens_hybrid, naive_weekly, and the member with lowest training MAE (ties lexical). Also retain every other available published point forecast, including timeh2o_cov, as a strong individual comparator. Include tso_cutoff where present as an operator comparator; tso_final only as a separately labeled later-information reference. Preserve every missing comparator.

Primary acceptance: after delivery, point MAE for every available series, normalized against naive_weekly on the identical observed timestamps; macro average of per-series ratios, all cases and losses reported. A superiority claim requires candidate ratio below both the selected incumbent and ens_hybrid, and wins on at least9/12 series, with all12 series available. One day cannot establish robust generalization or commercial superiority. Missing, revised or provisional actuals cannot silently become final; record each scoring snapshot and revision.

## Retained successor

Freeze this constructor/source and fit cache. Once issueNov6 forecasts are public, construct deliveryNov7 using only completed data available then (at most issueNov4, which contains the first trial’s Nov5 outcomes). Compare unchanged Nov4 weights with fresh refit and equal-content ordinary refit. This isolates new dated information from cached implementation; expected ordinary-refit equality is retained. Do not claim that later-than means enabled-by or that free reuse establishes a better inventor. Stop after these two delivery days are scored or report exact missing-source/authority blockers; do not keep selecting days until positive.

## Arrangement and costs

Possible buyer: a grid/asset forecaster requiring a better wind/load prediction. Proposed only: optional outcome-based fee capped by independently measured avoided forecast loss against a buyer-agreed incumbent; buyer may decline and can reuse open forecasts. No participant or valuation is asserted. Physical value per MW of error, complete operating/qualification/support costs, model/host billing, licensing burdens and real willingness to pay are unknown. Record actual network bytes, CPU/wall and storage. Do not equate free access with free production of the underlying forecasts. No reserve pooling, nominal wallet, transaction, revenue or profit is generated. $100k is only a reference; $3B trailing-year profit remains unachieved.

Paper use: Foundry v2 pp8–19 and22–26, retained calibrated instrument then fresh successor acceptance; OUT-REFLECT pp3–10, explicit temporal/source checks and independent scoring. These motivate engineering discipline, not a claimed reproduction or new theorem. Positive accuracy alone would not satisfy Blue Sky or commercial admission.

Pre-execution revision at2026-11-04T11:32Z: successor moved to issueNov6/deliveryNov7 so the first trial outcomes can causally inform it. Earlier local protocol hash a0807d8c506a0cbe4947d311a331c3bda05fc3f9b517e9d839959503dde153f4 preceded data fitting or forecast construction.
