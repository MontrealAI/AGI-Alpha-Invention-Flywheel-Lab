# External continuous benchmark bridge

This prospective extension tests the boundary left by the finite line/fault study. It uses the independently specified ARCH-COMP2025 adaptive-cruise-control benchmark, pinned at `7ed57810ab679ed6c757d330cb9647a52c2e579d`. The exact original neural controller, continuous plant equations, initial box, five-second horizon and 0.1-second sample-and-hold are fixed before outcomes. Source input SHA-256 values appear in the preregistration and are checked at runtime.

Primary sources are the [benchmark repository](https://github.com/verivital/ARCH-COMP2025/tree/7ed57810ab679ed6c757d330cb9647a52c2e579d/benchmarks/ACC), its `Specifications.txt` and `dynamicsACC.m`, and [the category report, section3.1](https://coogan.ece.gatech.edu/papers/pdf/lopez2025archcompainncs.pdf). The initial positions are lead[90,110] and ego[10,11], initial velocities lead[32,32.2] and ego[30,30.2], with zero initial acceleration states. The safe-distance margin is relative position minus10 minus1.4times ego velocity. The plant includes acceleration lag and a quadratic drag term, so the finite line-game certificate cannot simply be reused as a physical proof.

The implementation performs32fixed point trajectories with the original supplied neural network, then repeats them with an independently expressed scalar network and ODE under a second numerical integrator. Numerical agreement checks implementation consistency, not universal safety. A separate directed-Decimal interval/Picard enclosure attempts all-initial-set verification of the original network; a negative lower enclosure bound means abstention, not an actual unsafe trajectory. Both the full initial box and a prospectively fixed16-box refinement are attempted, without outcome-dependent tuning.

A conventional constant braking command admits an independent exact-rational safe-distance argument in the supplied ODE. This is a useful analytic comparator, **not** proof that replacing the original neural controller preserves the full ACC purpose: speed tracking, comfort, unmodeled physical effects and actual deployment remain unqualified. A controller that meets the formal safety benchmark by braking can still fail the intended productive outcome. No private certificate grants device-control authority.

[CommonRoad SafeACC](https://github.com/CommonRoad/safe-acc/tree/dbba852cde06435b3c870bb660ccb135ca6d21ed), pinned at `dbba852cde06435b3c870bb660ccb135ca6d21ed`, supplies a strong existing fail-safe/nominal-controller architecture. Its source is GPL3. Complete execution is currently blocked by missing CommonRoad, native drivability and QP dependencies, and its own models/scenarios do not automatically equal ARCH. This run never relabels our fallback or point comparison as SafeACC execution, a baseline victory or reproduction of competition results.

After parent source freeze, retrieve the public benchmark transiently and run:

```bash
git clone https://github.com/verivital/ARCH-COMP2025.git /tmp/ARCH-COMP2025
git -C /tmp/ARCH-COMP2025 checkout 7ed57810ab679ed6c757d330cb9647a52c2e579d
python experiments/public_portfolio_20261102/purpose/continuous/bridge.py --benchmark /tmp/ARCH-COMP2025 --output /tmp/purpose-continuous
```

The benchmark repository exposes no explicit license in the checked tree. External MATLAB source, model weights and data are not republished here; source links, identities and original implementation suffice for the public evidence. Commercial rights, physical validity, market demand and full lifecycle economics remain separate requirements. Actual model/host billing is unknown; no paid API, transaction, outreach or device operation is performed by this experiment.
