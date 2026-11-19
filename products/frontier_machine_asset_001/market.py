"""FRONTIER Ω — machine asset marketplace, privately operated by MONTREAL.AI.

No live payments without explicit operator provisioning. All writes are local.
A non-public experimental transformer is the only installed executor: market
admission and genuine economic value are NOT established by this component.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
import uuid

from gate import Refused, checked_request, run, strict_json, canonical
from payment_receipts import (
    ADDRESS_RE, B58_RE, ETH_TOKEN, SOL_MINT, PaymentRejected,
    JsonRpc, positive_units, verify_over_rpc,
)

PRODUCT_ID = "frontier-omega-contract-transform-v0"
SCHEMA = "montreal.ai/frontier-assets/v0"
MAX_BODY = 262_144
QUOTE_SECONDS = 1800
CLAIM_GRACE_SECONDS = 86400
LIVE_ENABLE_STRING = "ENABLE_EXPLICIT_AGIALPHA_MAINNET_COLLECTION"


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _private_path(path):
    p = Path(path).expanduser().absolute()
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return p


def _validate_payer(chain, payer):
    if chain == "ethereum":
        if type(payer) is not str or not ADDRESS_RE.fullmatch(payer):
            raise PaymentRejected("INVALID_ETHEREUM_PAYER")
    elif chain == "solana":
        if type(payer) is not str or not B58_RE.fullmatch(payer):
            raise PaymentRejected("INVALID_SOLANA_PAYER")
    else:
        raise PaymentRejected("UNSUPPORTED_PAYMENT_NETWORK")


@dataclass(frozen=True)
class Merchant:
    # These are approved public *receiving* addresses, never private keys.
    eth_treasury: str = ""
    sol_treasury_owner: str = ""
    sol_treasury_token_account: str = ""
    eth_price_units: str = ""
    sol_price_units: str = ""
    eth_rpc: str = ""
    sol_rpc: str = ""

    @classmethod
    def from_env(cls):
        return cls(
            eth_treasury=os.getenv("FO_ETH_TREASURY", ""),
            sol_treasury_owner=os.getenv("FO_SOL_TREASURY_OWNER", ""),
            sol_treasury_token_account=os.getenv("FO_SOL_TREASURY_TOKEN_ACCOUNT", ""),
            eth_price_units=os.getenv("FO_ETH_PRICE_RAW", ""),
            sol_price_units=os.getenv("FO_SOL_PRICE_RAW", ""),
            eth_rpc=os.getenv("FO_ETH_RPC", ""),
            sol_rpc=os.getenv("FO_SOL_RPC", ""),
        )

    def for_chain(self, chain):
        if chain == "ethereum":
            if not (ADDRESS_RE.fullmatch(self.eth_treasury or "")
                    and self.eth_rpc and positive_units(self.eth_price_units) >= 10**15):
                raise PaymentRejected("ETHEREUM_MERCHANT_NOT_QUALIFIED")
            JsonRpc(self.eth_rpc)
            return self.eth_treasury, "", int(self.eth_price_units)
        if chain == "solana":
            if not (B58_RE.fullmatch(self.sol_treasury_owner or "")
                    and B58_RE.fullmatch(self.sol_treasury_token_account or "")
                    and self.sol_rpc and positive_units(self.sol_price_units) > 0):
                raise PaymentRejected("SOLANA_MERCHANT_NOT_QUALIFIED")
            JsonRpc(self.sol_rpc)
            return self.sol_treasury_token_account, self.sol_treasury_owner, int(self.sol_price_units)
        raise PaymentRejected("UNSUPPORTED_PAYMENT_NETWORK")


class Market:
    def __init__(self, database, merchant=None, *, live=False, verifier=None):
        if live and verifier is not None:
            raise ValueError("LIVE_VERIFIER_MUST_BE_OPERATOR_RPC")
        self.database = _private_path(database)
        self.merchant = merchant or Merchant()
        self.live = bool(live)
        self._test_verifier = verifier
        self.mode = "LIVE_RPC" if self.live else "OFFLINE_TEST_ONLY"
        self._init_db()

    def _db(self):
        c = sqlite3.connect(str(self.database), timeout=8, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=8000")
        return c

    def _init_db(self):
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS orders(
                    order_id TEXT PRIMARY KEY,
                    token_digest TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    request_sha TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    payer TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    recipient_owner TEXT NOT NULL,
                    amount_units TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    state TEXT NOT NULL CHECK(state IN
                      ('QUOTED', 'PAID', 'TEST_VERIFIED', 'DELIVERED')),
                    event_id TEXT UNIQUE,
                    proof_json TEXT,
                    delivery_json TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS unique_eth_amount
                ON orders(amount_units) WHERE chain='ethereum';
                CREATE TABLE IF NOT EXISTS settlements(
                    event_id TEXT PRIMARY KEY,
                    order_id TEXT UNIQUE NOT NULL REFERENCES orders(order_id),
                    mode TEXT NOT NULL,
                    receipt_json TEXT NOT NULL
                );
            """)
            try:
                os.chmod(self.database, 0o600)
            except OSError:
                pass

    def catalog(self):
        return {
            "schema": SCHEMA,
            "publisher": "MONTREAL.AI",
            "asset_id": PRODUCT_ID,
            "description": "Bounded source-record transformation and separate local acceptance checking",
            "research_only": True,
            "competitor_superiority": "NOT_ESTABLISHED",
            "commercial_demand": "NOT_ESTABLISHED",
            "payment_mode": self.mode,
            "accepted_tokens": {
                "ethereum": {"contract": ETH_TOKEN, "chain_id": 1, "decimals": 18},
                "solana": {"mint": SOL_MINT, "network": "mainnet-beta",
                           "decimals": "read_from_finalized_chain"},
            },
            "quotes_enabled": self.live or self._test_verifier is not None,
        }

    def issue(self, asset_id, request, chain, payer, *, now=None):
        if not (self.live or self._test_verifier is not None):
            raise PaymentRejected("PAYMENT_MODE_DISABLED")
        if asset_id != PRODUCT_ID:
            raise PaymentRejected("UNKNOWN_ASSET")
        checked_request(request)
        if len(canonical(request)) > MAX_BODY:
            raise PaymentRejected("REQUEST_TOO_LARGE")
        _validate_payer(chain, payer)
        recipient, owner, price = self.merchant.for_chain(chain)
        created = int(time.time()) if now is None else now
        if type(created) is not int or created <= 0:
            raise PaymentRejected("INVALID_QUOTE_TIME")
        # Each EVM quote's exact raw token amount uniquely identifies the
        # intended order transfer. Quote collisions are refused by SQLite.
        dust = secrets.randbits(48) if chain == "ethereum" else 0
        amount = str(price + dust)
        order_id = uuid.uuid4().hex
        nonce = secrets.token_hex(16)
        access_token = secrets.token_urlsafe(32)
        row = (
            order_id, sha(access_token), PRODUCT_ID,
            canonical(request).decode("utf-8"),
            hashlib.sha256(canonical(request)).hexdigest(),
            chain, payer, recipient, owner, amount, nonce,
            created, created + QUOTE_SECONDS, "QUOTED",
        )
        with self._db() as db:
            db.execute("""
                INSERT INTO orders(
                    order_id,token_digest,asset_id,request_json,request_sha,
                    chain,payer,recipient,recipient_owner,amount_units,nonce,
                    created_at,expires_at,state
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, row)
        return {
            "order_id": order_id, "access_secret": access_token,
            "asset_id": PRODUCT_ID,
            "chain": chain, "token": ETH_TOKEN if chain == "ethereum" else SOL_MINT,
            "payer": payer, "recipient": recipient,
            "recipient_owner": owner if chain == "solana" else None,
            "amount_units": amount, "created_at": created,
            "expires_at": created + QUOTE_SECONDS,
            "order_memo": ("FRONTIER-OMEGA:" + order_id + ":" + nonce) if chain == "solana" else None,
            "erc20_exact_amount_binding": chain == "ethereum",
            "payment_evidence_mode": self.mode,
            "commercial_evidence": "NOT_ESTABLISHED",
            "note": "Not a USD quote; price is raw $AGIALPHA units. No automatic token/fiat conversion.",
        }

    def _authorized(self, db, order_id, access_secret):
        if type(order_id) is not str or type(access_secret) is not str:
            raise PaymentRejected("INVALID_ORDER_ACCESS")
        row = db.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if row is None or not secrets.compare_digest(row["token_digest"], sha(access_secret)):
            raise PaymentRejected("ORDER_ACCESS_REFUSED")
        return dict(row)

    def _payment_quote(self, row, tx_ref):
        return {
            "order_id": row["order_id"], "nonce": row["nonce"],
            "chain": row["chain"], "payer": row["payer"],
            "recipient": row["recipient"], "recipient_owner": row["recipient_owner"],
            "amount_units": row["amount_units"], "created_at": row["created_at"],
            "expires_at": row["expires_at"], "tx_ref": tx_ref,
            "unique_amount_bound": row["chain"] == "ethereum",
        }

    def claim(self, order_id, access_secret, tx_ref, *, now=None):
        if not (self.live or self._test_verifier is not None):
            raise PaymentRejected("PAYMENT_MODE_DISABLED")
        current = int(time.time()) if now is None else now
        with self._db() as db:
            row = self._authorized(db, order_id, access_secret)
        if row["state"] != "QUOTED":
            if row["state"] in ("PAID", "TEST_VERIFIED", "DELIVERED") and row["proof_json"]:
                return json.loads(row["proof_json"])
            raise PaymentRejected("ORDER_NOT_PAYABLE")
        if type(current) is not int or current > row["expires_at"] + CLAIM_GRACE_SECONDS:
            raise PaymentRejected("CLAIM_WINDOW_CLOSED")
        quote = self._payment_quote(row, tx_ref)
        if self.live:
            verified = verify_over_rpc(
                quote, ethereum_rpc=self.merchant.eth_rpc, solana_rpc=self.merchant.sol_rpc
            )
            state = "PAID"
            mode = "LIVE_RPC"
        else:
            verified = self._test_verifier(quote)
            state = "TEST_VERIFIED"
            mode = "TEST_FIXTURE_NOT_REVENUE"
        if (type(verified) is not dict or type(verified.get("event_id")) is not str
                or verified.get("chain") != row["chain"]
                or verified.get("amount_units") != row["amount_units"]
                or verified.get("recipient", "").lower() != row["recipient"].lower()
                or verified.get("finality") != "finalized"):
            raise PaymentRejected("VERIFIER_RESULT_INCOMPLETE")
        # Serialized state transition prevents double-claim and cross-order replay.
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            fresh = self._authorized(db, order_id, access_secret)
            if fresh["state"] != "QUOTED":
                db.execute("ROLLBACK")
                raise PaymentRejected("PAYMENT_RACE_REFUSED")
            try:
                db.execute(
                    "INSERT INTO settlements(event_id,order_id,mode,receipt_json) VALUES(?,?,?,?)",
                    (verified["event_id"], order_id, mode, json.dumps(verified, sort_keys=True)),
                )
                receipt = {
                    "order_id": order_id, "state": state, "chain": row["chain"],
                    "token": ETH_TOKEN if row["chain"] == "ethereum" else SOL_MINT,
                    "event_id": verified["event_id"],
                    "evidence": verified, "mode": mode,
                    "company_revenue": "UNRECONCILED_ONCHAIN_TRANSFER" if self.live
                                        else "SIMULATED_ZERO",
                    "note": "Chain settlement is not automatically fiat revenue or realized profit.",
                }
                db.execute(
                    "UPDATE orders SET state=?,event_id=?,proof_json=? WHERE order_id=?",
                    (state, verified["event_id"], json.dumps(receipt, sort_keys=True), order_id),
                )
                db.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                db.execute("ROLLBACK")
                raise PaymentRejected("TRANSFER_ALREADY_CLAIMED") from exc
        return receipt

    def deliver(self, order_id, access_secret):
        # No second delivery charge; repeated requests return the same stored bytes.
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._authorized(db, order_id, access_secret)
            if row["state"] == "DELIVERED" and row["delivery_json"]:
                return json.loads(row["delivery_json"])
            if row["state"] not in ("PAID", "TEST_VERIFIED"):
                db.execute("ROLLBACK")
                raise PaymentRejected("SETTLED_PAYMENT_REQUIRED")
            request = strict_json(row["request_json"])
            result = run(request)
            if not result["receipt"]["accepted"]:
                db.execute("ROLLBACK")
                raise PaymentRejected("ARTIFACT_VERIFICATION_FAILED")
            final = {
                "order_id": order_id, "asset_id": PRODUCT_ID,
                "delivery": result["delivery"], "acceptance": result["receipt"],
                "payment_evidence": json.loads(row["proof_json"]),
                "economic_status": ("AWAITING_ACCOUNTING_AND_REFUND_REVIEW" if self.live
                                    else "TEST_ONLY_NO_REAL_REVENUE"),
            }
            db.execute(
                "UPDATE orders SET state='DELIVERED',delivery_json=? WHERE order_id=?",
                (json.dumps(final, ensure_ascii=False, sort_keys=True), order_id),
            )
            db.execute("COMMIT")
            return final

    def status(self, order_id, access_secret):
        with self._db() as db:
            row = self._authorized(db, order_id, access_secret)
            return {"order_id": order_id, "state": row["state"],
                    "payment_mode": self.mode,
                    "event_id": row["event_id"],
                    "real_revenue_established": False}


def make_handler(market):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def respond(self, status, payload):
            raw = canonical(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == "/v1/catalog":
                return self.respond(200, market.catalog())
            if self.path == "/healthz":
                return self.respond(200, {
                    "ok": True, "schema": SCHEMA, "payment_mode": market.mode})
            return self.respond(404, {"error": "NOT_FOUND"})

        def do_POST(self):
            if self.path not in ("/v1/quote", "/v1/claim", "/v1/deliver", "/v1/status"):
                return self.respond(404, {"error": "NOT_FOUND"})
            if self.headers.get_content_type() != "application/json":
                return self.respond(415, {"error": "JSON_REQUIRED"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_BODY:
                    return self.respond(413, {"error": "REQUEST_SIZE"})
                payload = strict_json(self.rfile.read(length).decode("utf-8"))
                if type(payload) is not dict:
                    raise PaymentRejected("JSON_OBJECT_REQUIRED")
                if self.path == "/v1/quote":
                    result = market.issue(payload.get("asset_id"), payload.get("request"),
                                          payload.get("chain"), payload.get("payer"))
                elif self.path == "/v1/claim":
                    result = market.claim(payload.get("order_id"), payload.get("access_secret"),
                                          payload.get("tx_ref"))
                elif self.path == "/v1/deliver":
                    result = market.deliver(payload.get("order_id"), payload.get("access_secret"))
                else:
                    result = market.status(payload.get("order_id"), payload.get("access_secret"))
                return self.respond(200, result)
            except (PaymentRejected, Refused, ValueError, TypeError,
                    sqlite3.Error, UnicodeError) as exc:
                return self.respond(422, {"error": str(exc)})
    return Handler


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--state", required=True, help="private local SQLite file")
    p.add_argument("--serve", action="store_true")
    p.add_argument("--port", type=int, default=8790)
    args = p.parse_args()
    live = os.getenv("FO_ENABLE_LIVE_PAYMENT", "") == LIVE_ENABLE_STRING
    if not live:
        print("OFFLINE: live payment claims and sale quotes disabled", flush=True)
    market = Market(args.state, Merchant.from_env(), live=live)
    if args.serve:
        if not 1024 <= args.port <= 65535:
            p.error("port 1024..65535")
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(market))
        print("loopback only", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    else:
        print(json.dumps(market.catalog(), sort_keys=True))


if __name__ == "__main__":
    main()
