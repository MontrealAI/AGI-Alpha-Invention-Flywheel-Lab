# One unfamiliar public model: ordinary specialist still wins

The locally registered first-eligible-file rule selected AALpy's
[`DotModels/Angluin_Mealy.dot`](https://github.com/DES-Lab/AALpy/blob/4c7b4a8746460fd84eaccb48d4891e5e0ac90883/DotModels/Angluin_Mealy.dot).
It is a four-state published teaching model with input strings `a` and `b`,
not an observed industrial or network protocol. Its exact file SHA256 is
`babe305cb27825a52279c60df167f1439cfd49a31c534bedc39f3de79cdf381c`.
The upstream commit and MIT license are identified in SPECIALIST_SOURCES.json;
no separate license notice was present in the selected file. The model file is
not redistributed here.

Both methods constructed the same adapter, passed the unchanged original
independent checker and executed the portable runner.

| Actual calls | Registered learner | AALpy L* plus bounded W-method |
|---|---:|---:|
| Learning |255|97|
| Independent checking |590|590|
| Portable smoke |1|1|
| Total |846|688|

The specialist uses **18.7% fewer total measured calls**. No whole-business,
installation-time, human-effort or real-world restoration advantage is measured.
An independent rerun exactly matched the result and selection bytes, confirmed
the same adapters and rejected changed registration before execution.

Selection was registered locally before parsing or querying and saved durably
before constructing the oracle. It was not publicly preregistered. The complete
screen covered **58 DOT files**, with four eligible under the stated rule;
lexicographic order selected this file, with no replacement after seeing results.
The **26 files in named Bluetooth, MQTT, TCP and TLS directories had no eligible
entry under that screen**. The two-to-three-input, at-most-five-state restriction
was a screening choice, not a general product or physical limitation. Exclusion
does not establish that those protocols are impossible or uneconomic to handle.

Both methods received only the same reset-and-query callable, the model's valid
four-state upper bound and 20,000-call learning/checking budgets. The examiner's
graph knowledge justified the simulator contract; no target table was supplied
to either learner. No acceptance condition, financial account or frozen primary
source changed. This is one unfamiliar public software-model result, not a
qualified consequential field gap, market evidence or Super Alpha.

From this directory, after the setup in README.md:

```sh
probe-env/bin/python public_case_probe.py --lab-root /path/to/qualified-lab-checkout --aalpy-root ./AALpy --registration PUBLIC_CASE_REGISTRATION.json --output PUBLIC_CASE_REPRODUCTION.json
```

The probe refuses existing output names. It writes a corresponding selection
receipt before querying. PUBLIC_CASE_REVIEW.json binds the exact probe, checker,
registration, model, result, selection and dependency-helper hashes. The tested
probe enforces its registration, checker and upstream source identities; its
dynamically loaded dependency helper is identified by the review receipt rather
than an additional runtime hash guard. Keep the qualified `aalpy_probe.py` helper
with this reproduction; do not silently substitute an edited helper.

The next required external evidence is a permitted unfamiliar buyer workflow,
its reset/query interface or another justified observation contract, an
independently specified acceptance target, and realistic operating/adoption
costs. Standard libraries and competent ordinary construction must receive the
same information. No such consequential field gap was qualified by this screen;
further invention claims remain withheld.
