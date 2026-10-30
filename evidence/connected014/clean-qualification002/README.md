# Source002 clean distribution qualification

Source commit `ffc1f2e14e88e11f75d5087ab0f7c4e60512431e`, source SHA256 `3d985299bf6cfaf546b712ebd9e878e875aaf730ffdb32023637aafc5504a38d`, passed a fresh untouched clean-distribution engineering smoke retry. All 116 source files match their immutable committed bytes.

The first attempt is preserved in [FAILURE001.json](FAILURE001.json): a baseline result lost only its runner-added `case` field, causing package refusal after an earlier audit passed. Its origin is unresolved; no failed record or frozen source was repaired. A separate untouched retry using exactly the same source passed all five commands. This is an engineering reproduction retry on exposed smoke seeds, not fresh commercial confirmation.

- Successful retry: 19.600 wall seconds; 28.352 child CPU seconds.
- Public key-free package: 845820 bytes; SHA256 `0be5a675d0e83823f806138c69da2095c4d7b90093fbab6c016ca001d6f3480c`.
- Exact preinstalled dependencies checked; fresh dependency installation remains separate.
- Same-account completed resume preserved native financial records. Public exports support audit/reproduction, not account takeover.

See [successful qualification](retry001/QUALIFICATION.json), [committed-source binding](retry001/SOURCE_BINDING.json) and [key-free package](retry001/connected014-keyfree.zip). Earlier source001 proof remains separate and unchanged.
