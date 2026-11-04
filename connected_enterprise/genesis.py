"""Opt-in GENESIS entry point; existing connected_enterprise defaults are unchanged."""
from genesis_enterprise.__main__ import main

if __name__ == '__main__':
    raise SystemExit(main())
