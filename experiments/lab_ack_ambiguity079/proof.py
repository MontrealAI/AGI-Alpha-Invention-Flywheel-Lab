"""Offline finite ambiguity witness; no physical instrument, account or buyer."""
import argparse
import hashlib
import json
from pathlib import Path

WORLDS = {"not_executed": 0, "already_executed": 1}
ACTIONS = ("RETRY", "DECLARE_COMPLETED", "REFUSE")
OBSERVATION = "ACK_LOST"


def unobserved(action, prior):
    if action not in ACTIONS or prior not in (0, 1):
        raise ValueError("INVALID_ACTION_OR_PRIOR_EFFECT")
    if action == "RETRY":
        after, completed = prior + 1, prior == 0
    elif action == "DECLARE_COMPLETED":
        after, completed = prior, prior == 1
    else:
        after, completed = prior, False
    return {"effects": after, "safe": after <= 1, "completed_correctly": completed,
            "refused": action == "REFUSE"}


def observed_recovery(prior, instrument, stale=False, expired=False):
    if prior not in (0, 1) or instrument not in ("READBACK", "DURABLE_DEDUP"):
        raise ValueError("INVALID_STATE_OR_CAPABILITY")
    if instrument == "READBACK":
        reported = 0 if stale else prior
        effects = prior + (1 if reported == 0 else 0)
        provenance = "STALE" if stale else "EXACT"
    else:
        effects = prior + 1 if expired else max(prior, 1)
        provenance = "EXPIRED" if expired else "RETAINED"
    return {"effects": effects, "safe": effects == 1, "completed_correctly": effects == 1,
            "capability": instrument, "assumption": provenance}


def certificate():
    blind = {action: {world: unobserved(action, prior)
                      for world, prior in WORLDS.items()} for action in ACTIONS}
    supported = {capability: {world: observed_recovery(prior, capability)
                              for world, prior in WORLDS.items()}
                 for capability in ("READBACK", "DURABLE_DEDUP")}
    counterexamples = {
        "stale_readback": observed_recovery(1, "READBACK", stale=True),
        "expired_dedup": observed_recovery(1, "DURABLE_DEDUP", expired=True)
    }
    viable = [action for action, outcomes in blind.items()
              if all(record["safe"] and record["completed_correctly"] for record in outcomes.values())]
    if viable or not all(r["safe"] for r in blind["REFUSE"].values()):
        raise AssertionError("BLIND_CERTIFICATE_INVALID")
    if any(not r["safe"] or not r["completed_correctly"]
           for arm in supported.values() for r in arm.values()):
        raise AssertionError("CAPABILITY_CONTROL_INVALID")
    if any(r["safe"] for r in counterexamples.values()):
        raise AssertionError("STALE_OR_EXPIRED_COUNTEREXAMPLE_INVALID")
    return {
        "schema": "agi-alpha/lab-ack-ambiguity079/v1",
        "model": "ONE_NONIDEMPOTENT_EFFECT_SINGLE_LOST_ACK",
        "world_count": len(WORLDS), "policies": len(ACTIONS),
        "identical_public_observation": OBSERVATION, "blind_guaranteed_completion_policies": viable,
        "blind_actions": blind, "strong_ordinary_capability_controls": supported,
        "unsafe_unsupported_assumptions": counterexamples,
        "decision": "ABSTAIN_WHEN_UNOBSERVABLE_NONIDEMPOTENT",
        "claims": {"physical_actuation": False, "buyer_contracts": 0, "collected_revenue_usd": 0,
                   "native_account_run": False, "native_trailing365_profit_usd": None,
                   "target_3000000000_achieved": False},
        "scope": "Finite information/safety witness, not an instrument-specific correctness proof or market result."
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("NEW_OUTPUT_PATH_REQUIRED")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = certificate()
    registration = Path(__file__).parent / "PREREGISTRATION.md"
    result["preregistration_sha256"] = hashlib.sha256(registration.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["decision"], "source": result["preregistration_sha256"]}))


if __name__ == "__main__":
    main()
