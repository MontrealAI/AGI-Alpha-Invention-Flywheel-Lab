"""Owner-invoked observation of a single live direct Stripe charge, with no financial writes."""
import base64
import http.client
import os
import re
import ssl

from .store import StateError, digest, strict_json

VERSION = "2026-10-28.endive"
MINOR_UNITS = {"CAD": 2, "USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}
BINDING_KEY = "ignition_offer_sha256"


def _identifier(value, prefix):
    if not isinstance(value, str) or not re.fullmatch(prefix + r"_[A-Za-z0-9]{1,128}", value):
        raise StateError("Invalid private Stripe object reference.")
    return value


def parties(request):
    """Use privately confirmed expected IDs from the owner and counterparty before offering."""
    if not isinstance(request, dict) or set(request) not in ({"merchant", "customer"}, {"merchant", "customer", "charge"}):
        raise StateError("Supply the expected merchant and customer; reconciliation also requires the charge.")
    return digest(["stripe-direct-parties/1", _identifier(request["merchant"], "acct"),
                   _identifier(request["customer"], "cus")])


def minor_amount(price, currency):
    if currency not in MINOR_UNITS:
        raise StateError("This direct-charge adapter supports CAD, USD, EUR, GBP and JPY.")
    whole, _, fraction = price.partition(".")
    digits = MINOR_UNITS[currency]
    fraction = fraction.rstrip("0")
    if len(fraction) > digits or not re.fullmatch("[0-9]+", whole) or (fraction and not fraction.isascii()):
        raise StateError("The offer amount is not exact in this currency's minor unit.")
    amount = int(whole) * 10**digits + int(fraction.ljust(digits, "0") or 0)
    if amount <= 0:
        raise StateError("A positive offer amount is required.")
    return amount


def _read_json(connection, path, authorization):
    try:
        connection.request("GET", path, headers={"Authorization": authorization, "Stripe-Version": VERSION})
        response = connection.getresponse()
        if response.status != 200:
            raise StateError(f"Stripe read returned HTTP {response.status}. No settlement recorded.")
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise StateError("Stripe object exceeded the read limit.")
        request_id = _identifier(response.getheader("Request-Id"), "req")
        obj = strict_json(raw)
        if not isinstance(obj, dict):
            raise ValueError()
    except (ValueError, OSError, http.client.HTTPException) as exc:
        if isinstance(exc, StateError):
            raise
        raise StateError("Could not verify the Stripe response. No settlement recorded.") from None
    return obj, digest(request_id)


def observe(request, key_fd, authorize_read):
    """No ambient key, redirection, alternate origin, Connect override, SDK hooks or mutation."""
    parties(request)
    charge_id = _identifier(request.get("charge"), "ch")
    if type(key_fd) is not int or key_fd < 0:
        raise StateError("Provide the live read-restricted key on an explicitly selected file descriptor.")
    authorize_read()
    # Never accept a key through a command argument, request document, model or service endpoint.
    with os.fdopen(os.dup(key_fd), "rb") as key_stream:
        key = key_stream.readline(513).rstrip(b"\r\n")
    if not re.fullmatch(rb"rk_live_[A-Za-z0-9]{8,496}", key):
        raise StateError("A restricted live-mode key is required.")
    authorization = "Basic " + base64.b64encode(key + b":").decode("ascii")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs()
    conn = http.client.HTTPSConnection("api.stripe.com", timeout=20, context=context)
    try:
        authorize_read()
        account, account_trace = _read_json(conn, "/v1/account", authorization)
        if account.get("object") != "account" or account.get("id") != request["merchant"]:
            raise StateError("The authenticated Stripe merchant differs from the enrolled merchant.")
        authorize_read()
        # One server-side expansion binds the available transaction to the same charge response.
        charge, charge_trace = _read_json(conn, "/v1/charges/" + charge_id + "?expand%5B%5D=balance_transaction",
                                          authorization)
    finally:
        conn.close()
    return charge, [account_trace, charge_trace]


def reconcile_charge(charge, request, offer):
    """Validate a direct, single-currency receipt and remove all provider and customer identifiers."""
    terms = offer["event"]["details"]
    if parties(request) != terms.get("stripe_parties_sha256"):
        raise StateError("Stripe merchant and customer differ from the accepted offer.")
    expected_amount = minor_amount(terms["amount"], terms["currency"])
    expected = {"id": _identifier(request.get("charge"), "ch"), "object": "charge", "customer": request["customer"],
                "status": "succeeded", "currency": terms["currency"].lower(), "livemode": True,
                "captured": True, "paid": True, "disputed": False, "refunded": False,
                "amount": expected_amount, "amount_captured": expected_amount, "amount_refunded": 0,
                "transfer_data": None, "on_behalf_of": None, "source_transfer": None, "application_fee": None,
                "application_fee_amount": None}
    if not isinstance(charge, dict) or any(k not in charge or type(charge[k]) is not type(v) or charge[k] != v
                                           for k, v in expected.items()):
        raise StateError("Charge must be a matching live direct payment, fully captured, unrefunded and undisputed.")
    if not isinstance(charge.get("metadata"), dict) or charge["metadata"].get(BINDING_KEY) != offer["sha256"]:
        raise StateError("Charge lacks the binding for this exact offer, recipient and mission.")
    tx = charge.get("balance_transaction")
    if not isinstance(tx, dict):
        raise StateError("Stripe did not return the expanded balance transaction.")
    tx_id = _identifier(tx.get("id"), "txn")
    required = {"object": "balance_transaction", "status": "available", "type": "charge", "balance_type": "payments",
                "source": charge["id"], "currency": charge["currency"], "amount": expected_amount, "exchange_rate": None}
    if any(k not in tx or type(tx[k]) is not type(v) or tx[k] != v for k, v in required.items()):
        raise StateError("No corresponding available same-currency direct charge in the merchant payments balance.")
    fee, net = tx.get("fee"), tx.get("net")
    if type(fee) is not int or type(net) is not int or fee < 0 or net <= 0 or net + fee != expected_amount:
        raise StateError("Provider fee or available net does not reconcile to gross.")
    return {"provider": "stripe", "scope": "Available in the authenticated merchant's Stripe payments balance",
            "currency": terms["currency"], "minor_unit_digits": MINOR_UNITS[terms["currency"]],
            "gross_minor": expected_amount, "provider_fee_minor": fee, "available_net_minor": net,
            "charge_fingerprint": digest(["stripe-direct-charge/1", request["merchant"], charge["id"]]),
            "balance_transaction_fingerprint": digest(["stripe-balance-transaction/1", request["merchant"], tx_id]),
            "bank_payout_verified": False, "later_reversals_monitored": False}
