# Adversarial development record

The first normal and optimized test runs each executed 36 tests and failed one
assertion in `test_redundancy`: the test expected a 22-unit construction after
adding a supplier-Q-failure scenario and increasing the price cap. Both the
constructor and separately implemented oracle returned the ordinary P+R route at
17 units. Inspection confirmed that P+R does not depend on Q, so adding an
adapter, pooled Q reserve and redundant R would be unnecessary. The test
expectation was corrected to 17. The scenario was renamed
`higher_price_selects_existing_route`; no acceptance criterion, supplier capacity,
or search option was weakened. This is an authoring/test-expectation error, not
an empirical improvement of a frontier LLM. The final runs are separately
retained. No second language model or external institutional reviewer was used.

## Source-adjudication hardening

The initial finite critic interface consumed a self-reported `present` flag. Review identified that as an unnecessary trust assumption. The final version takes the actual presented-output item set independently and ignores a contrary flag from the critic. Two added tests bring the suite to 38. This improves the authored-label checker; it is not a natural-language source-authentication or semantic-comprehension result.

Hosted preparation runs 42128880244 and 42129174379 failed because the standard newtx dependency binhex.tex was absent. Diagnostic artifact 13462486729 identified texlive-plain-generic; the explicit dependency fixed compilation. Run 42129906875 then compiled the 23-page PDF and passed all 38 numerical tests; a reader test failed because it expected the literal phrase actual customer demand while the reader said real customer demand. Before further integration, main published a different same-title 28-page paper in PR266. This companion therefore uses its own directory, reader and source identity and does not modify the published edition, site, manifest or release. The old competing site installer and workflow were removed from this new package. No scientific thresholds or numerical outcomes changed.
