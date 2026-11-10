# Exact released-byte owner handoff in CI

These steps follow the successful published-archive operation in the release job. They use the same final commit, product tree and archive digest. Keep publication credentials confined to download/upload steps; do not expose them to product tests, model execution, reconciliation or browser rendering.

## Prepare the release assets

The local-model job supplies a flat `HOSTED-LOCAL-QUALIFICATION.json` plus an untouched `LOCAL-MODEL-EVIDENCE_SOURCEPREFIX.zip`. That ZIP contains the complete allowlisted model evidence directory, including its nested arm outputs and root manifest. Never pass a directory to `gh release create` or flatten nested evidence members.

After publishing the customer archive, checksums, browser/platform receipts, model manifest and model evidence ZIP, download **all** assets of this source-specific release:

```sh
tag="alpha-genesis-harness-v0.2.0-rc-${SOURCE_SHA:0:12}"
gh release download "$tag" --dir "$RUNNER_TEMP/harness-published"
```

`GH_TOKEN` and `GH_REPO` belong only to this publication step. The exact downloaded customer ZIP then runs through `qualify_archive.py` into `$RUNNER_TEMP/harness-published-operation` as already required by the workflow.

## Reconcile and assemble without publication credentials

Run the following from the repository root, after the published operation succeeds. `SOURCE_SHA`, `ARCHIVE_NAME`, `ARCHIVE_SHA` and `RUNNER_TEMP` are trusted workflow values. The source checkout must still be the final source.

```sh
test "$(git rev-parse HEAD)" = "$SOURCE_SHA"
product_tree=$(git rev-parse "$SOURCE_SHA:products/alpha-genesis-harness")
model_archive="$RUNNER_TEMP/harness-published/LOCAL-MODEL-EVIDENCE_${SOURCE_SHA:0:12}.zip"
python -B products/alpha-genesis-harness/scripts/reconcile_release_evidence.py \
  --archive "$RUNNER_TEMP/harness-published/$ARCHIVE_NAME" \
  --expected-sha256 "$ARCHIVE_SHA" \
  --source-sha "$SOURCE_SHA" \
  --source-product-tree "$product_tree" \
  --operation-receipt "$RUNNER_TEMP/harness-published-operation/QUALIFICATION.json" \
  --asset-dir "$RUNNER_TEMP/harness-published" \
  --live-receipt "$RUNNER_TEMP/harness-published/HOSTED-LOCAL-QUALIFICATION.json" \
  --model-evidence-archive "$model_archive" \
  --output "$RUNNER_TEMP/harness-final-evidence"
python -B products/alpha-genesis-harness/scripts/owner_handoff.py \
  --source-sha "$SOURCE_SHA" \
  --release-url "https://github.com/$GITHUB_REPOSITORY/releases/tag/alpha-genesis-harness-v0.2.0-rc-${SOURCE_SHA:0:12}" \
  --asset-dir "$RUNNER_TEMP/harness-published" \
  --customer-zip "$RUNNER_TEMP/harness-published/$ARCHIVE_NAME" \
  --expected-sha256 "$ARCHIVE_SHA" \
  --operation-receipt "$RUNNER_TEMP/harness-published-operation/QUALIFICATION.json" \
  --matrix "$RUNNER_TEMP/harness-final-evidence/QUALIFICATION-MATRIX.json" \
  --model-evidence-archive "$model_archive" \
  --output "$RUNNER_TEMP/harness-owner" > "$RUNNER_TEMP/harness-owner-assembly.json"
```

The generated matrix is prospective until these commands actually run. It never turns fixture tests into live model access, native sandbox probes into authenticated Codex, or a technically valid archive into commercial approval. Actual local-model qualifications require a final-source, unchanged-source manifest whose evidence ZIP inventory validates; partial failures remain visible.

## Render the owner report

Install the pinned `tests/visual/package-lock.json` development dependency in the release runner, which is separate from the qualification runner. Keep the owner ZIP immutable after assembly; visual receipts and screenshots remain beside it.

```sh
mkdir -p "$RUNNER_TEMP/harness-owner-visual-deps"
cp products/alpha-genesis-harness/tests/visual/package*.json "$RUNNER_TEMP/harness-owner-visual-deps/"
npm ci --prefix "$RUNNER_TEMP/harness-owner-visual-deps" --ignore-scripts --no-audit --no-fund
owner_directory=$(python -c 'import json,os; from pathlib import Path; print(json.loads((Path(os.environ["RUNNER_TEMP"])/"harness-owner-assembly.json").read_text())["owner_directory"])')
NODE_PATH="$RUNNER_TEMP/harness-owner-visual-deps/node_modules" \
  node products/alpha-genesis-harness/scripts/verify_owner_handoff.cjs \
  "$owner_directory" "$RUNNER_TEMP/harness-owner-visual" "$SOURCE_SHA"
```

This produces `OWNER-VISUAL-VERIFICATION.json` and desktop/mobile screenshots. Only an observed successful render qualifies the report's graphical checks.

## Publish owner artifacts separately

In a new step with `GH_TOKEN` and `GH_REPO`, upload only files. Preserve exact paths returned by the assembler; do not upload the expanded owner directory as if it were the customer product.

```sh
tag="alpha-genesis-harness-v0.2.0-rc-${SOURCE_SHA:0:12}"
owner_zip=$(python -c 'import json,os; from pathlib import Path; print(json.loads((Path(os.environ["RUNNER_TEMP"])/"harness-owner-assembly.json").read_text())["owner_zip"])')
owner_receipt="${owner_zip%.zip}.receipt.json"
gh release upload "$tag" \
  "$owner_zip" "$owner_zip.sha256" "$owner_receipt" \
  "$RUNNER_TEMP/harness-final-evidence/QUALIFICATION-MATRIX.json" \
  "$RUNNER_TEMP/harness-final-evidence/QUALIFICATION-MATRIX.md" \
  "$RUNNER_TEMP/harness-final-evidence/RECONCILIATION.json" \
  "$RUNNER_TEMP/harness-owner-visual/OWNER-VISUAL-VERIFICATION.json" \
  "$RUNNER_TEMP/harness-owner-visual/HARNESS-OWNER-desktop.png" \
  "$RUNNER_TEMP/harness-owner-visual/HARNESS-OWNER-mobile.png"
```

Do not use `--clobber`. Preserve `$RUNNER_TEMP/harness-final-evidence`, `$RUNNER_TEMP/harness-owner-assembly.json`, `$RUNNER_TEMP/harness-owner-visual` and the source-specific owner ZIP/checksum/receipt as workflow artifacts with `if: always()`, including failure diagnostics when available. No Squarespace operation is performed.
