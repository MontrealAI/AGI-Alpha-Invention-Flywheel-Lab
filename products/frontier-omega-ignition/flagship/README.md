# Pairing Lab

Choose which self-hosted coding stacks merit a private pilot. The instrument compares 18 model/harness combinations on 100 published software issues, charges for unsuccessful attempts, locks a policy using 60 issues, and audits it on the other 40. Run it offline with Python 3.10+ and its standard library.

```sh
python3 pairing_lab.py --summary
python3 pairing_lab.py --budget 5000000 --width 2
python3 pairing_lab.py --model devstral --repository django__django --budget 2000000 --summary
python3 -B -m unittest discover -v
python3 qualify.py --check receipt.json
python3 repair_experiment.py
```

Remove `--summary` to inspect every audit issue, reported grade, stack and charged token count. Run `python3 package.py Pairing_Lab.zip` to rebuild the portable archive. Commands run in this directory or its extracted copy.

## The decision the evidence supports

The primary registered decision allowed an average of two million charged tokens per issue, with a 45% resolution floor. Calibration picked Qwen3-Coder-Next / Agentless for one attempt, and that stack plus GLM-4.7-Flash / AutoCodeRover when two attempts were permitted. With two attempts the full costs of **both** measured runs count on every issue. An issue counts once when either submitted patch passed the independent upstream grader. Pairing two archived runs is a retrospective counterfactual. It assumes access to an independent acceptance test capable of choosing a passing patch in future use.

| Registered audit | Resolved | Total charged tokens | Tokens per issue | Verdict |
|---|---:|---:|---:|---|
| Selected single, 2M cap | 16/40 | 878,663 | 21,967 | Below resolution floor |
| Selected pair, 2M cap | 18/40 | 14,642,768 | 366,069 | Meets both thresholds exactly on resolution |
| Best calibration single ignoring budget, Qwen / OpenHands | 23/40 | 387,113,098 | 9,677,827 | Exceeds 2M cap |
| Selected pair, 5M cap | 22/40 | 176,696,676 | 4,417,417 | Meets both thresholds |
| Devstral-only Django successor, 2M cap | 5/12 | 39,647,841 | 3,303,987 | Misses cost and resolution gates |

The two extra resolved issues in the primary historical comparison consumed 13,764,105 additional charged tokens. The 45% floor is an illustrative operator requirement. It was registered before the split was computed. A different requirement can reverse the decision. More favorable hindsight could have reached 19/40 under the primary cap, using the audit labels during selection. The tool displays this information bound separately.

Reproduction checks all seven registered arms against separately written SQLite. The relational implementation receives the same rights and reproduces every candidate's split-level outcomes. The seven arms overlap. The historical issues come from one known benchmark with one recorded grade per attempt. Dependence between tasks, public benchmark contamination, the choice of split, selective scoring in private environments and actual financing or deployment costs qualify the result. No customer has paid for this experiment. The uncapped incumbent makes the operational trade-off clear.

## Turn a historical result into a fresh, private pilot

1. Define locally authorized, previously unseen issue IDs, one per line in `tasks.txt`. Identify the independently maintained grading procedure you will actually use and record its SHA-256. The program does not launch models, execute submitted patches, send task information or change a repository.
2. Register the permitted configurations and evidence contract. Keep the printed commitment separately before collecting results. Supply your actual grader digest in place of the shell variable.

   ```sh
   python3 pilot.py register --tasks tasks.txt --grader-sha "$GRADER_SHA256" --out plan.json
   ```

3. Collect one independently graded observation per allowed task and selected configuration. Use CSV headings `task,model,harness,solved,tokens,grader_sha256,run_id`. Use the observed, nonnegative charged token count for **each** attempt, including a failed run. Preserve the underlying raw run and grading evidence privately. A single issue accepting both patches earns one resolution. Where an independent acceptance procedure cannot identify a correct patch, an apparent retrospective portfolio advantage cannot qualify a production workflow.
4. Audit the observations against the original commitment. Missing rows produce an incomplete result. The receiver rederives the eligible policy from the registered data and current code. Unknown, stale or empty plans, a grader mismatch, repeated run IDs and duplicate configurations fail validation. Use the same `--data` file on registration and audit when using a custom study. The output binds imported observations and the original plan. A reported digest cannot certify that the operator's grader executed truthfully.

   ```sh
   python3 pilot.py audit --plan plan.json --commitment "$PLAN_SHA256" --observations observations.csv
   ```

The fresh-task pilot workflow is exercised with synthetic observations in the tests. No private field pilot has been conducted. The failed held-out Django successor is a real reanalysis of the same published study. It provides evidence that reusing a working instrument does not guarantee a useful policy for another beneficiary.

## Data and reproducibility

Lu Zhao, Christopher M. Poskitt and David Lo released *Pairing Matters: Performance, Failures, and Efficiency in Lightweight Coding Agents*. Their Figshare v1 archive was issued October 22, 2026. The October 23 paper describes 1,800 originally graded runs. We redistribute only the five factual fields needed for this experiment under the authors' CC BY 4.0 data license. We renamed and selected fields, removed unrelated columns and serialized with LF. No patches, repository source, transcripts or authored annotations are included.

- [Original paper](https://arxiv.org/abs/2610.32131)
- [Versioned archive](https://doi.org/10.6084/m9.figshare.34744362.v1)
- [Pinned source CSV](https://github.com/lisazhao-gz/pairing-matters/blob/48444d3aa8383c90de0135c55138528c90eeb8e0/data/runs_100.csv)
- [Source license](https://github.com/lisazhao-gz/pairing-matters/blob/48444d3aa8383c90de0135c55138528c90eeb8e0/LICENSE) and [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- [Prior matched-harness study, September 17](https://arxiv.org/abs/2609.20804)
- [Contemporary study on selection under budget, November 16](https://arxiv.org/abs/2611.21515)

To recreate `runs.csv`, download the pinned raw file preserving its original bytes. Run `python3 project_data.py /path/to/runs_100.csv /path/to/derived.csv`. Upstream SHA-256 is `a3fafa234f5498b235de1a7d0c3fbdc6e10c2496465b078f359f1bd1dba595d1`. Projection SHA-256 is `c60d0b58ab109ba900e36465a0ffadaaeb4c8a2743abc744eb17f3f596842118`. Original charges sum prompt and completion tokens and count cached context at full weight. Unreported usage is unobserved. The source study used specific H100 serving and harness configuration settings including harness-specific limits. Our analysis has no new inference charges. Its complete labor, hardware, verification and opportunity costs are unmeasured.

October's release contributed inspectable paired measurements. Conventional relational tools already support the search, and similar empirical research predates the window. The archive enables this exact retrospective comparison. Evidence of a historical impossibility, production margin or a proprietary discovery advantage remains open.

A bundle exported from a **private workbench mission** also contains `mission-decision.json`. Run `python3 verify_decision.py` in its extracted directory to reproduce that specific decision with both the selector and independent SQL. The public base kit supplies the instrument and registered study without a private mission decision.
