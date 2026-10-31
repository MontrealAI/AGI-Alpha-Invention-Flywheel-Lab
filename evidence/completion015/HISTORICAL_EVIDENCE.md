# Lossless historical evidence transport

This transport preserves 100 original completion015 and connected014 evidence records from commit
`7d75766401adede49afd2427be82eb0302934b80`, without changing any byte, verdict,
failed trace, resource receipt, or source identity. It is packaging, not fresh
financial qualification or a replacement for original private account state.

`HISTORICAL_EVIDENCE.json` maps every original repository path to its byte size,
SHA256, Git blob SHA1 and original Git mode. `HISTORICAL_EVIDENCE.zip` contains
those exact original paths. The completion015 source subtree is
`10da8de7b347fc72a5cd77ec51f16da6f87cefc6`; connected014 is
`e0349de7edb9d766094e2fadfa8ab998a18c5810`.

Verify from the repository root:

```
python scripts/package_completion015_evidence.py evidence/completion015/HISTORICAL_EVIDENCE.json
```

Restore into a **new separate directory**, never over an existing working tree:

```
python scripts/package_completion015_evidence.py evidence/completion015/HISTORICAL_EVIDENCE.json --extract /absolute/new/restored-evidence
```

Historical relative links can be resolved in that restored tree or by browsing
the same original path at the pinned source commit. Existing Markdown documents,
source, loose allocation/authority records, confirmation records and all
publication-binding/qualification records remain unchanged and unbundled.
The transport does not require Git history or a network connection to recover
these 100 records. It grants no permission to recover or overwrite live accounts.

The source archive's existing 10,000-file and 512 MiB guards are unchanged.
