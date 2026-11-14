# Editable numerical Kelvin instrument

Supporting ALPHA GENESIS prototype: editable measurement design, raw observation contract, interval reconstruction, independent acceptance and explicit obstacle reopening. It uses a strong ordinary Kelvin/current-reversal method and a separately built direct-agent implementation. This is neither tomography nor physical/customer qualification. The broader GENESIS discovery foundry and improved-discovery claim remain unestablished. Instruments are examples, not the product boundary.

Read [the frozen protocol](PROTOCOL.md) and edit [the design input](DESIGN_INPUT.json). No instrument hardware is actuated.

Run from repository root (offline only):

```
python -m research.genesis097.cli compile --input campaign/genesis097/DESIGN_INPUT.json --output /tmp/editable-design.json
python -m research.genesis097.cli analyze --input your-observations.json --output /tmp/analysis.json
python -m unittest research.genesis097.test_instrument research.genesis097.test_direct -v
python -m research.genesis097.experiment --output /tmp/genesis097-result.json
```

The same forward observations are given to all three arms; the conventional and composition arms intentionally share the mature analysis kernel. Full successful development is not confirmation. A public source freeze and independent review precede the held-out numerical run. Do not interpret a numerical pass or control tie as a physical invention, actual commerce or profitability.
