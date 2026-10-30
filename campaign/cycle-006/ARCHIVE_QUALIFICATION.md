# Qualification of the cycle-006 public archive

For the new cycle-006 edition, use the independent release checker with the ZIP
SHA-256 from the published `SHA256SUMS.txt` (obtain that digest independently of
the archive's internal manifest):

```sh
python verification/cycle006_archive_check.py \
  --archive DOWNLOAD.zip --expected-sha256 PUBLISHED_64_HEX_DIGEST \
  --output /tmp/alpha006-downloaded-qualification-NEW
```

This checks every payload before importing extracted source, invokes the pinned
actual validated extractor, and separately exercises ordinary extraction with
its original packaging metadata retained. Both trees run the complete unit and
verifier suites, the connected cycle-006 CLI and the paper identity check. The
checker verifies that execution did not alter original source payloads. Its
`--identity-only` option checks bytes only and explicitly reports that runtime
is unqualified. Reproduction uses the original outcomes after exposure; it does
not create a new protected scientific test or establish commercial success.
