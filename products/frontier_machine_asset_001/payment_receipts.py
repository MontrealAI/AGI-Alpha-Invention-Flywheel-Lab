"""FRONTIER Ω: read-only $AGIALPHA mainnet payment evidence.

Cryptographic chains supply settlement facts through *operator-controlled* RPCs.
No signing, funds movement, merchant onboarding, or live payment activation.
Parser-only fixtures are never external financial evidence.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ETH_TOKEN = "0xA61a3B3a130a9c20768EEBF97E21515A6046a1fA"
SOL_MINT = "tWKHzXd5PRmxTF5cMfJkm2Ua3TcjwNNoSRUqx6Apump"
ETH_CHAIN_ID = "0x1"
SOL_GENESIS = "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d"
SPL_TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
B58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,90}$")


class PaymentRejected(ValueError):
    pass


def must(condition, reason):
    if not condition:
        raise PaymentRejected(reason)


def positive_units(value):
    must(type(value) is str and re.fullmatch(r"[1-9][0-9]{0,77}", value) is not None,
         "INVALID_RAW_TOKEN_AMOUNT")
    units = int(value)
    must(0 < units < 2**256, "TOKEN_AMOUNT_OUT_OF_RANGE")
    return units


def hex_quantity(value):
    must(type(value) is str and re.fullmatch(r"0x(?:0|[1-9a-fA-F][0-9a-fA-F]*)", value),
         "INVALID_RPC_HEX_QUANTITY")
    return int(value, 16)


def time_window(quote, chain_time):
    must(type(chain_time) is int, "NO_CHAIN_BLOCK_TIME")
    must(type(quote.get("created_at")) is int and type(quote.get("expires_at")) is int,
         "INVALID_QUOTE_TIME")
    must(quote["created_at"] <= chain_time <= quote["expires_at"], "PAYMENT_OUTSIDE_QUOTE_WINDOW")


def _address(topic):
    must(type(topic) is str and HASH_RE.fullmatch(topic), "MALFORMED_LOG_TOPIC")
    must(topic[2:26].lower() == "0" * 24, "NONCANONICAL_ADDRESS_TOPIC")
    return "0x" + topic[-40:].lower()


def ethereum_evidence(quote, receipt, transaction, included_block, finalized_block, chain_id):
    """Validate one final ERC-20 Transfer. Exact per-order raw amount binds a quote.

    quote['amount_units'] is cryptographically randomized at issue time with
    48-bit dust, and its exact value is unique among issued Ethereum quotes.
    Never accept arbitrary >= prices: that would permit cross-order replay.
    """
    must(chain_id == ETH_CHAIN_ID and quote.get("chain") == "ethereum", "WRONG_ETHEREUM_NETWORK")
    must(type(receipt) is dict and type(transaction) is dict, "MISSING_ETHEREUM_TRANSACTION")
    tx_hash = quote.get("tx_ref")
    must(type(tx_hash) is str and HASH_RE.fullmatch(tx_hash), "INVALID_ETHEREUM_HASH")
    must(str(receipt.get("transactionHash", "")).lower() == tx_hash.lower(), "ETHEREUM_RECEIPT_HASH")
    must(str(transaction.get("hash", "")).lower() == tx_hash.lower(), "ETHEREUM_TRANSACTION_HASH")
    must(receipt.get("status") == "0x1", "FAILED_ETHEREUM_TRANSACTION")
    must(type(quote.get("recipient")) is str and ADDRESS_RE.fullmatch(quote["recipient"]),
         "INVALID_ETHEREUM_RECIPIENT")
    must(type(quote.get("payer")) is str and ADDRESS_RE.fullmatch(quote["payer"]),
         "INVALID_ETHEREUM_PAYER")
    must(str(transaction.get("from", "")).lower() == quote["payer"].lower(), "WRONG_ETHEREUM_SENDER")
    must(quote.get("unique_amount_bound") is True, "UNBOUND_ETHEREUM_ORDER")
    must(type(included_block) is dict and type(finalized_block) is dict, "MISSING_FINALITY_PROOF")
    included = hex_quantity(receipt.get("blockNumber"))
    must(included == hex_quantity(included_block.get("number")), "MISMATCHED_INCLUDED_BLOCK")
    must(included <= hex_quantity(finalized_block.get("number")), "ETHEREUM_NOT_FINALIZED")
    must(str(receipt.get("blockHash", "")).lower() == str(included_block.get("hash", "")).lower()
         and type(receipt.get("blockHash")) is str
         and HASH_RE.fullmatch(receipt["blockHash"]), "ETHEREUM_NONCANONICAL_BLOCK")
    must(str(transaction.get("blockHash", "")).lower() == receipt["blockHash"].lower(),
         "ETHEREUM_TX_BLOCK_MISMATCH")
    time_window(quote, hex_quantity(included_block.get("timestamp")))
    want = positive_units(quote.get("amount_units"))
    eligible = []
    for log in receipt.get("logs", []):
        if type(log) is not dict or log.get("removed") is True:
            continue
        if str(log.get("address", "")).lower() != ETH_TOKEN.lower():
            continue
        topics = log.get("topics")
        if type(topics) is not list or len(topics) != 3:
            continue
        if str(topics[0]).lower() != TRANSFER_TOPIC:
            continue
        if _address(topics[1]) != quote["payer"].lower():
            continue
        if _address(topics[2]) != quote["recipient"].lower():
            continue
        data = log.get("data")
        must(type(data) is str and HASH_RE.fullmatch(data), "MALFORMED_TRANSFER_AMOUNT")
        if int(data, 16) != want:
            continue
        ix = hex_quantity(log.get("logIndex"))
        must(str(log.get("transactionHash", "")).lower() == tx_hash.lower(),
             "LOG_TRANSACTION_MISMATCH")
        eligible.append(ix)
    must(len(eligible) == 1, "NO_UNAMBIGUOUS_ETHEREUM_PAYMENT")
    event_id = "ethereum:1:" + tx_hash.lower() + ":" + str(eligible[0])
    return {"event_id": event_id, "chain": "ethereum", "token": ETH_TOKEN,
            "amount_units": str(want), "tx_ref": tx_hash.lower(),
            "block_number": included, "finality": "finalized",
            "recipient": quote["recipient"].lower(), "source": "operator_rpc"}


def _parsed_info(value, type_name):
    must(type(value) is dict, "MISSING_SOLANA_ACCOUNT")
    must(value.get("owner") == SPL_TOKEN, "WRONG_SOLANA_TOKEN_PROGRAM")
    data = value.get("data")
    must(type(data) is dict and data.get("program") == "spl-token", "UNPARSED_SOLANA_ACCOUNT")
    parsed = data.get("parsed", {})
    must(type(parsed) is dict and parsed.get("type") == type_name, "WRONG_SOLANA_ACCOUNT_TYPE")
    info = parsed.get("info")
    must(type(info) is dict, "INVALID_SOLANA_ACCOUNT_INFO")
    return info


def _key(key):
    if type(key) is str:
        return key
    return key.get("pubkey") if type(key) is dict else None


def _raw_balance(b):
    must(type(b) is dict and type(b.get("uiTokenAmount")) is dict, "INVALID_SOLANA_BALANCE")
    amount = b["uiTokenAmount"].get("amount")
    must(type(amount) is str and re.fullmatch(r"(?:0|[1-9][0-9]*)", amount),
         "INVALID_SOLANA_RAW_BALANCE")
    return int(amount)


def solana_evidence(quote, tx, mint_account, treasury_account, genesis_hash):
    """Strict finalized transferChecked + unique order memo + treasury credit.

    Unsupported token programs and unparsed nested calls are refused, not
    guessed. Solana mint decimals are read from finalized on-chain data.
    """
    must(genesis_hash == SOL_GENESIS and quote.get("chain") == "solana",
         "WRONG_SOLANA_NETWORK")
    must(type(tx) is dict and type(tx.get("meta")) is dict
         and tx["meta"].get("err") is None, "FAILED_OR_MISSING_SOLANA_TX")
    sig = quote.get("tx_ref")
    must(type(sig) is str and B58_RE.fullmatch(sig), "INVALID_SOLANA_SIGNATURE")
    transaction = tx.get("transaction")
    must(type(transaction) is dict and type(transaction.get("signatures")) is list and bool(transaction["signatures"]) and transaction["signatures"][0] == sig,
         "MISMATCHED_SOLANA_SIGNATURE")
    must(type(tx.get("slot")) is int and tx["slot"] > 0, "INVALID_SOLANA_SLOT")
    time_window(quote, tx.get("blockTime"))
    owner = quote.get("recipient_owner")
    token_account = quote.get("recipient")
    payer = quote.get("payer")
    for value in (owner, token_account, payer):
        must(type(value) is str and B58_RE.fullmatch(value), "INVALID_SOLANA_ADDRESS")
    mint = _parsed_info(mint_account, "mint")
    recipient = _parsed_info(treasury_account, "account")
    must(recipient.get("mint") == SOL_MINT and recipient.get("owner") == owner,
         "SOLANA_TREASURY_OWNERSHIP")
    decimals = mint.get("decimals")
    must(type(decimals) is int and 0 <= decimals <= 18, "INVALID_SOLANA_DECIMALS")
    must(recipient.get("tokenAmount", {}).get("decimals") == decimals,
         "SOLANA_DECIMALS_MISMATCH")
    message = transaction.get("message", {})
    keys = message.get("accountKeys", [])
    must(type(keys) is list and len(keys) > 0, "MISSING_SOLANA_KEYS")
    resolved = [_key(k) for k in keys]
    must(token_account in resolved, "DESTINATION_NOT_IN_SOLANA_TRANSACTION")
    dest_index = resolved.index(token_account)
    must(any(type(k) is dict and k.get("pubkey") == payer and k.get("signer") is True
             for k in keys), "PAYER_DID_NOT_SIGN_SOLANA_TRANSACTION")
    instructions = message.get("instructions", [])
    must(type(instructions) is list, "UNPARSED_SOLANA_INSTRUCTIONS")
    must(type(quote.get("order_id")) is str and type(quote.get("nonce")) is str,
         "INVALID_SOLANA_ORDER_REFERENCE")
    expected_memo = "FRONTIER-OMEGA:" + quote["order_id"] + ":" + quote["nonce"]
    memos = [i.get("parsed") for i in instructions if type(i) is dict
             and i.get("program") == "spl-memo"]
    must(memos.count(expected_memo) == 1, "MISSING_UNIQUE_ORDER_MEMO")
    must(len(memos) == 1, "EXTRA_SOLANA_MEMO")
    # Refuse inner instructions for the paid destination; initially require
    # a direct, parsed transferChecked for a simple, verifiable purchase.
    meta = tx["meta"]
    if meta.get("innerInstructions"):
        raise PaymentRejected("SOLANA_INNER_INSTRUCTIONS_REQUIRE_SEPARATE_AUDIT")
    transfers = []
    for instruction in instructions:
        if type(instruction) is not dict:
            continue
        parsed = instruction.get("parsed")
        if type(parsed) is not dict:
            continue
        info = parsed.get("info", {})
        if (instruction.get("program") == "spl-token"
                and type(info) is dict and info.get("destination") == token_account):
            must(parsed.get("type") == "transferChecked", "SOLANA_UNCHECKED_TRANSFER")
            must(info.get("mint") == SOL_MINT and info.get("authority") == payer
                 and info.get("source") != token_account, "WRONG_SOLANA_TOKEN_OR_PAYER")
            amount = info.get("tokenAmount", {}).get("amount")
            must(type(amount) is str and re.fullmatch(r"[1-9][0-9]*", amount),
                 "INVALID_SOLANA_TRANSFER_AMOUNT")
            transfers.append((int(amount), info.get("source")))
    must(len(transfers) == 1, "NO_UNAMBIGUOUS_SOLANA_TRANSFER")
    required_units = positive_units(quote.get("amount_units"))
    must(required_units <= 2**64 - 1, "SOLANA_TOKEN_AMOUNT_EXCEEDS_U64")
    must(transfers[0][0] == required_units,
         "WRONG_SOLANA_PAYMENT_AMOUNT")
    source = transfers[0][1]
    must(source in resolved and source != token_account, "UNKNOWN_SOLANA_SOURCE_ACCOUNT")
    from_index = resolved.index(source)
    before = [b for b in meta.get("preTokenBalances", [])
              if b.get("accountIndex") == dest_index and b.get("mint") == SOL_MINT]
    after = [b for b in meta.get("postTokenBalances", [])
             if b.get("accountIndex") == dest_index and b.get("mint") == SOL_MINT]
    source_before = [b for b in meta.get("preTokenBalances", [])
                     if b.get("accountIndex") == from_index and b.get("mint") == SOL_MINT]
    must(len(after) == 1 and len(before) <= 1 and len(source_before) == 1,
         "SOLANA_BALANCE_EVIDENCE_MISSING")
    must(after[0].get("owner") == owner and after[0].get("programId") == SPL_TOKEN,
         "SOLANA_DESTINATION_BALANCE_WRONG")
    must(source_before[0].get("owner") == payer and source_before[0].get("programId") == SPL_TOKEN,
         "SOLANA_SOURCE_OWNER_WRONG")
    must(after[0]["uiTokenAmount"].get("decimals") == decimals,
         "SOLANA_POST_BALANCE_DECIMALS")
    pre = _raw_balance(before[0]) if before else 0
    delta = _raw_balance(after[0]) - pre
    must(delta == transfers[0][0], "SOLANA_RECEIVED_BALANCE_MISMATCH")
    return {"event_id": "solana:" + sig, "chain": "solana", "token": SOL_MINT,
            "amount_units": str(delta), "tx_ref": sig, "slot": tx["slot"],
            "finality": "finalized", "recipient": token_account, "source": "operator_rpc"}


class JsonRpc:
    """Read-only HTTPS JSON-RPC. Never accepts a client-supplied endpoint."""
    def __init__(self, endpoint):
        u = urlsplit(endpoint)
        must(u.scheme == "https" and bool(u.hostname) and not u.username and
             not u.password and not u.fragment, "TRUSTED_HTTPS_RPC_REQUIRED")
        self.endpoint = endpoint

    def call(self, method, params):
        payload = json.dumps({"jsonrpc": "2.0", "id": 1,
                              "method": method, "params": params}).encode()
        req = urllib.request.Request(self.endpoint, data=payload,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                raw = response.read(4_000_001)
                must(len(raw) <= 4_000_000, "RPC_RESPONSE_TOO_LARGE")
            result = json.loads(raw)
        except (urllib.error.URLError, TimeoutError, OSError,
                json.JSONDecodeError) as exc:
            raise PaymentRejected("RPC_UNAVAILABLE_OR_UNPARSEABLE") from exc
        must(type(result) is dict and result.get("id") == 1 and
             result.get("jsonrpc") == "2.0" and "error" not in result,
             "RPC_RESPONSE_ERROR")
        return result.get("result")


def verify_over_rpc(quote, ethereum_rpc=None, solana_rpc=None):
    """Owner-initiated, server-only RPC evidence; no untrusted client snapshots."""
    if quote.get("chain") == "ethereum":
        must(bool(ethereum_rpc), "ETHEREUM_RPC_NOT_CONFIGURED")
        rpc = JsonRpc(ethereum_rpc)
        chain = rpc.call("eth_chainId", [])
        must(chain == ETH_CHAIN_ID, "WRONG_ETHEREUM_NETWORK")
        tx = rpc.call("eth_getTransactionByHash", [quote["tx_ref"]])
        receipt = rpc.call("eth_getTransactionReceipt", [quote["tx_ref"]])
        must(type(receipt) is dict, "NO_ETHEREUM_RECEIPT")
        included = rpc.call("eth_getBlockByNumber", [receipt.get("blockNumber"), False])
        finalized = rpc.call("eth_getBlockByNumber", ["finalized", False])
        return ethereum_evidence(quote, receipt, tx, included, finalized, chain)
    if quote.get("chain") == "solana":
        must(bool(solana_rpc), "SOLANA_RPC_NOT_CONFIGURED")
        rpc = JsonRpc(solana_rpc)
        genesis = rpc.call("getGenesisHash", [])
        must(genesis == SOL_GENESIS, "WRONG_SOLANA_NETWORK")
        tx = rpc.call("getTransaction", [
            quote["tx_ref"], {"encoding": "jsonParsed", "commitment": "finalized",
                              "maxSupportedTransactionVersion": 1}])
        mint = rpc.call("getAccountInfo", [
            SOL_MINT, {"encoding": "jsonParsed", "commitment": "finalized"}])
        recipient = rpc.call("getAccountInfo", [
            quote["recipient"], {"encoding": "jsonParsed", "commitment": "finalized"}])
        return solana_evidence(quote, tx, mint.get("value") if type(mint) is dict else None,
                               recipient.get("value") if type(recipient) is dict else None, genesis)
    raise PaymentRejected("UNSUPPORTED_PAYMENT_NETWORK")
