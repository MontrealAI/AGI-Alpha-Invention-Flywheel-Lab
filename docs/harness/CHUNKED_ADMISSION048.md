# Finite source-bound service admission 048

The primitive and coherent-packet generators accept a declared finite inventory
without the former 256 primitive, 128 packet and 1,000 total-record ceilings.
`prepare_services(..., jobs_per_service=N, chunk_size=W)` and
`prepare_complete_offer_services(..., jobs_per_service=N, packet_jobs=P,
packet_rows=R, chunk_size=W)` retain their existing native service manifests and
production/checking paths. The default window is 64 records; a positive integer
window controls an execution/memory batch, never the admissible total. Generation
still requires a finite integer count and the existing minimum primitive cohort.
Packet period, row, currency, identity, exact-money, artifact-byte, source and
private-account protections are unchanged. A packet requires 4 through 1,000 rows
per source kind, matching its existing synthetic-input contract.

`cohort_provenance.finite_admission` binds the executing source hashes, generation
seed commitment, primitive service order/count, eight existing complementary
bundles, packet count/row contract, exact total and ordered chunk hashes. Chunks
must cover the manifest exactly without omissions, repetition, reorder or count
changes. Unknown metadata fields and boolean substitutes for integer fields fail
canonical comparison. Existing manifests without this new declaration retain the
historical 1,000-record admission guard; their historical source is not rewritten.

`iter_checked_job_chunks(root, manifest)` reads and independently checks each
input, delivered artifact and acceptance receipt within the declared window.
`load_jobs` drains that iterator, rejects duplicate job identities, and validates
the source/admission again before returning authority to the existing account.
A partial iterator is only a checked chunk; it is not whole-manifest financial
authority or a successful complete admission audit.

`audit_admission(root, manifest, cohort_seed=registered_seed)` independently
reconstructs every primitive and packet source, checks each existing bundle's
exact admitted component lineage, and invokes the independent artifact checker.
The declared generation seed must match its commitment. The seed is supplied to
the auditor rather than added to the seller's manifest. A rehashed permutation
with internally consistent chunk metadata still fails this origin audit. Hash
metadata alone is not proof that a declared synthetic cohort was generated.

Run the finite regression and boundary experiment with:

```sh
python -m unittest tests.test_connected_chunked_admission048 -v
```

The declared boundary probe generates 300 records per primitive service, the
eight existing bundles and 129 four-row packets: 1,037 actual records, all
independently checked and regenerated. It reexecutes primitive index 299 and
packet index 128, settles those two useful artifacts through `JournalAccount`,
and independently audits the full native journal. With $100,000 synthetic
opening capital, $20 buyer-wallet funding, two $2 collections and $1.25 explicit
test costs, the probe reconciles $2.75 native margin, $100,002.75 cash, zero
payables and retained tail protection. These narrow engineering-probe costs and
voluntary scripted consents are not complete commercial cost/demand evidence.

A separate small native experiment proves identical service/input/output/receipt
hashes, native actions and financial summaries across windows 1 and 17. Mutation
checks cover missing chunks, totals, chunk/source/seed digests, reordered records,
duplicates, service-order changes, wrong declared generation origin, legacy
admission downgrade above 1,000 and invalid counts/windows/packet rows.

The manifest and accepted native registry remain materialized lists/dictionaries.
This removes the admission ceilings and avoids an unnecessary deep copy of all
primitive metadata; it does not provide a fully out-of-core account or validated
large-market aggregation. Canonical registration still selects its existing
inventory unless a separately qualified configuration change connects a larger
cohort. Actual resource use and these remaining integration/scaling constraints
remain measurable; neither inventory generation nor this two-sale probe proves
an account year, empirical demand or a profit milestone.
