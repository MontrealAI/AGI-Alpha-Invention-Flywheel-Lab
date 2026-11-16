# Independent read-only review

A separate reviewer inspected both raw result files, supervisor receipts, exact frozen git source and runtime/model download records. It confirmed all recorded source hashes against git blobs, unchanged before/after hashes, nine dispatched requests versus five completed model responses, four approximately 600-second connection timeouts, and no accepted inherited or exported capability. The review did not run another model trial or write the trial code.

The model also made real semantic errors: the actor/critic path generated an undeclared reference, then formula text instead of required calculations; the single-model lab output lacked required validity/capacity behavior. Deadline and host-throughput effects prevent treating the outcome as a pure capability comparison. No strategy superiority is established.

The reviewer inspected the publication allowlist and found no credential or private-project payloads in these result/supervisor/model-download files. Private state, integrity material and runtime caches are excluded. Four protocol tests were independently rerun before inference; this is not independent reproduction of the model experiment.
