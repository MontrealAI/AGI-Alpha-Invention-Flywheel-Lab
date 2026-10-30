# Connected acquisition lead preflight

The connected engine exposes and caches a day's channel slots before buying that
day's financed pilot contract. A zero-day pilot lead cannot honor that ordering.
The prior configuration validator accepted both zero lead and a missing pilot;
COUNTEREXAMPLES.before.json and BEFORE.log preserve these narrow configuration
failures without opening a financial account or running commerce.

The connected preflight now applies the existing complete typed channel-contract
validator, requires the pilot contract, and requires its lead to be at least one
day. These checks precede output creation, setup expense and Account construction.
Standalone ChannelBook zero-lead support, channel/audit semantics, costs and the
default two-day pilot lead remain unchanged.

The 31 focused tests include zero/positive leads, missing pilot, Boolean/string/
negative malformed leads, complete contract validation and precommit refusal.
Original source-abc configs still pass unchanged: central and weak-channel pilot
lead two days, delayed/high-cost lead six days, covering all eight registered
historical tasks. The historical receipt binds the earlier independently verified
freeze; it neither changes that history nor qualifies a new current-source run.
