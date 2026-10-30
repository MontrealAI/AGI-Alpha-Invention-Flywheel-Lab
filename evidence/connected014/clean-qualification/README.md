# Committed-source clean distribution qualification

Source commit `42238e4b39962d3d3cebce11bdf467a66c5e3436`, source SHA256 `3734ea91e36e302bd82272a3e452f5b0a14df06ff6759cde8064f0bb60090ba2`, passed the clean-distribution engineering smoke qualification. All 113 executing source files match their immutable committed bytes.

The qualifier built and extracted a source ZIP without `.git`, executed two smoke worlds, resumed the same private accounts without changing native financial records, independently audited them, exported a key-free package and audited its extracted public copy. All five commands returned zero.

- Wall: 18.151 seconds; child CPU: 26.184 seconds.
- Public package: 839385 bytes; SHA256 `74faa9181bb7cff1f7e99472764615b7830259d4c2828c07cd4f175980fd9012`.
- Pinned dependencies were already installed and their exact versions checked. Fresh dependency installation is a separate qualification.
- This is engineering reproduction, not fresh commercial confirmation. Public exports support audit/reproduction, not account takeover.

See [qualification](QUALIFICATION.json), [committed-source binding](SOURCE_BINDING.json) and [key-free public package](connected014-keyfree.zip). Original private recovery state stays outside this directory.
