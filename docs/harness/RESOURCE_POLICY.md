# Execution resources are not simulated business costs

This policy applies only to the downloaded-release operation, not every historical campaign or repository workflow.

For future downloaded-release operations, measured CPU is telemetry, not a pass/fail budget. The former 2,400 CPU-second threshold remains an explicitly historical reference only. Prior receipts retain their original verdicts; this policy does not turn an incomplete old run into a completed one.

The fixed six-command run/resume/audit/package/audit/audit protocol and all source, privacy, financial, and audit checks remain. Commands do not retry automatically. The standard `ubuntu-latest` job uses GitHub's six-hour hosted-job ceiling; its command window subtracts elapsed setup/download time and a five-minute shutdown/receipt reserve. That finite deadline protects against hangs, not unprofitable simulation outcomes.

CPU (including waited children) and wall time remain recorded. A command failure, deadline interruption, changed source, changed balances, rejected audit, or private archive still fails. Historical and realistically modeled business costs are not rewritten; measured billing and unknown billing remain distinct.

Standard GitHub-hosted compute in public repositories is free under GitHub's policy, not because of a ChatGPT subscription. Larger runners and account storage can have separate charges; this change enables neither. References: [GitHub billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [hosted runner limits](https://docs.github.com/en/actions/reference/limits).
