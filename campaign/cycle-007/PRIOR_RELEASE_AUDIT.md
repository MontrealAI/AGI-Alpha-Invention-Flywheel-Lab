# Separate identity closure of the previous release

The previous local post-publication driver remains **OVERRUN_NOT_QUALIFIED**.
Its four-CPU-second allowance was exceeded and no original `IDENTITY.json`
existed. The thirteen original audit-branch files are copied byte-for-byte at
`evidence/cycle-007/prior-release-identity/originals/`; their Git blob identities
and source revision `524d03aa5ada7d237313e0c77f45d1e1bf254ffc` are recorded in
`ORIGINAL_PROVENANCE.json`. Neither that branch nor the historical release was
changed.

The new cycle007 allocation reserves 120 CPU seconds and 150 wall seconds for
this separate identity check, with a 4 GiB address-space bound. The allowance
accounts for hashing approximately 217 MB of published assets, decompressing
and checking every payload, and reading nested retained runtime evidence. It
does not inherit the exhausted cycle006 allocation. The unchanged resource V3
wrapper is reused as a scoped subledger; its compiled 5,400-CPU technical cap is
not permission to use that capacity. The enclosing cycle007 allocation controls
total authority.

All thirteen actual public release assets downloaded from their published URLs:
216,893,436 bytes, 26.956 seconds wall, 2.663 process CPU seconds. The new offline
audit completed in 2.907 wrapper wall seconds, 2.896 waited-child CPU seconds and
0.046 supervisor CPU seconds, with no surviving descendants. The audit process
reported peak RSS of 288,920 KiB. Combined observed download and audit CPU was
5.605 seconds; these measurements do not include all actor inference, network
service, CI or monetary costs.

The new identity receipt passes all thirteen independently obtained GitHub asset
digests and the published checksum list. The source ZIP is still
`34ed52fd1a962292b85053ab74449dbe21182ae0c49da95f177519c7e736430c`, 109,215,139
bytes. Its qualified old archive parser checks all 6,364 payloads and the full
6,363-source reproduction closure; candidate and reproduction freezes are
unchanged. The separately released paper editions match the source archive.
The original ordinary- and validated-extraction CI runtime reports retain their
scientific failures, zero actual revenue and zero commercial earned funds.

New receipt: `evidence/cycle-007/prior-release-identity/run/artifacts/IDENTITY.json`
SHA-256 `1e82aa55bd68b517a5341df1325d06e8c34bb90fdbf6b9d40ff46a18ea77c70e`.
New V3 resource receipt SHA-256
`4015dde97d37776250a5c7a7772df70e7092a74f18e2e4dc54f85ed30f414fb9`.

This is a newly qualified identity audit. It inspects the already published CI
runtime evidence and executes no predictor experiment. It does not retroactively
qualify the failed local receipt or change the previous scientific and economic
decisions. It is a small verification closure, not the new campaign's
consequential enabling result.

Reproduce after downloading the exact assets listed in
`campaign/cycle-007/PRIOR_RELEASE_IDENTITY_SPEC.json` to a fresh directory:

```sh
python verification/prior_release_identity007.py \
  --spec campaign/cycle-007/PRIOR_RELEASE_IDENTITY_SPEC.json \
  --downloads /absolute/path/to/downloaded/assets \
  --output /tmp/cycle007-prior-release-identity-NEW
```
