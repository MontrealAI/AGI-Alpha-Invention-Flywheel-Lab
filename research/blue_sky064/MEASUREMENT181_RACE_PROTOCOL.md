# Blue Sky 181 — preregistered unverified-input race review (18 November 2026)

## Source, owner and immutable prior evidence

Parent: Blue Sky 180 draft PR #467, exact head `2cef80e2c7454b72083687255bdc0f246755ed5c`. Original research owner controls integration; this dependent review does not rewrite PR #467 or its synthetic tests and 16/16 successful engineering workflows. The earlier #467 failed synthetic control remains a failure; #465's missing-dependency failure remains a failure. Main and canonical native account code are out of scope.

## Threat and fixed acceptance before implementation

The read-only `research/blue_sky064/measurement180.py::_regular_bytes` checks absolute path components and final file type via pathname, then independently reopens the path with `Path.read_bytes()`. An adversary with write access to a local unverified-input directory can replace the pathname between the checks and that read. A link substitution must never turn a previously checked input into accepted bytes from a different target. No key acquisition, physical sensor authentication or real buyer claim follows.

1. Preserve frozen scientific registration SHA256, loads 0.01/0.10 mm, +0.05 threshold and unchanged `observation178.assess`. No retuning scientific data.
2. Before repair, register and execute a deterministic synthetic path-swap control: start with a valid input file A; substitute a symlink to different valid file B immediately before the original `Path.read_bytes()`. The uncorrected parent may hash and accept B despite earlier no-symlink checks. Preserve its failing result.
3. Prospective repair must read through pinned OS file descriptors: walk each absolute parent with `O_DIRECTORY|O_NOFOLLOW`, open final file with `O_NOFOLLOW|O_NONBLOCK`, require a regular file with bounded size, and compare file metadata across complete bounded read. A filename swap after descriptor acquisition must not silently redirect that read. If swap happens before final open, fail closed. No unsupported portability claim.
4. Add a deterministic final-open swap control and unchanged positive, negative, inconclusive, malformed, oversized and CLI refusal controls. For genuine races test either rejection or byte identity with the originally opened regular file; do not accept swapped target B as the requested source.
5. Do not alter output schema, private filesystem/account ownership, scientific or economic verdicts. Existing conditional synthetic output remains `HOLD_NO_DEPLOY_UNVERIFIED_INPUT`; actual physical measurement, paying buyer, original finance signer and US$3B target remain unestablished.

## Qualification and stop rule

One preregistered adversarial schedule, one prospective implementation, the exact unchanged parent controls, and a clean extracted-source replay in standard public GitHub Actions. Preserve any initial failure and prospective repair separately. Do not rerun seeds until favorable or claim a source-only replay is a newly published released byte. No new spending, keys, outreach, account changes or physical experiment. Report either safe descriptor-bound input, a reproduced failure, or an unresolved case, and hand off to the original research integration owner.