"""Adversarial offline fixtures: no real chain, balances, or funds."""
import copy
import unittest
from payment_receipts import (
    ETH_TOKEN, SOL_MINT, ETH_CHAIN_ID, SOL_GENESIS, SPL_TOKEN,
    TRANSFER_TOPIC, JsonRpc, PaymentRejected, ethereum_evidence,
    solana_evidence, verify_over_rpc
)

PAYER = "0x" + "bb" * 20
DEST = "0x" + "aa" * 20
TXHASH = "0x" + "cc" * 32
BLOCKHASH = "0x" + "dd" * 32
SOL_PAYER = "7" * 44
SOL_OWNER = "8" * 44
SOL_DEST = "9" * 44
SOL_SOURCE = "A" * 44
SOL_SIG = "B" * 88


def eth_fixture():
    amount = 10**18 + 3456789
    quote = {
        "chain": "ethereum", "payer": PAYER, "recipient": DEST,
        "tx_ref": TXHASH, "amount_units": str(amount),
        "created_at": 1700000000, "expires_at": 1700001000,
        "unique_amount_bound": True,
    }
    log = {
        "address": ETH_TOKEN, "topics": [
            TRANSFER_TOPIC,
            "0x" + "0" * 24 + PAYER[2:],
            "0x" + "0" * 24 + DEST[2:],
        ],
        "data": "0x" + format(amount, "064x"),
        "logIndex": "0x0", "removed": False, "transactionHash": TXHASH,
    }
    receipt = {
        "transactionHash": TXHASH, "status": "0x1", "blockHash": BLOCKHASH,
        "blockNumber": "0x64", "logs": [log],
    }
    transaction = {"hash": TXHASH, "from": PAYER, "blockHash": BLOCKHASH}
    block = {"number": "0x64", "hash": BLOCKHASH,
             "timestamp": hex(1700000060)}
    finalized = {"number": "0x65"}
    return quote, receipt, transaction, block, finalized


def sol_fixture():
    amount = 1000000
    quote = {
        "chain": "solana", "payer": SOL_PAYER, "recipient": SOL_DEST,
        "recipient_owner": SOL_OWNER, "tx_ref": SOL_SIG,
        "amount_units": str(amount), "order_id": "ord-001",
        "nonce": "abc012", "created_at": 1700000000,
        "expires_at": 1700001000,
    }
    transfer = {"program": "spl-token", "parsed": {
        "type": "transferChecked", "info": {
            "authority": SOL_PAYER, "source": SOL_SOURCE,
            "destination": SOL_DEST, "mint": SOL_MINT,
            "tokenAmount": {"amount": str(amount), "decimals": 6},
        },
    }}
    tx = {
        "slot": 123456, "blockTime": 1700000060,
        "transaction": {
            "signatures": [SOL_SIG], "message": {
                "accountKeys": [
                    {"pubkey": SOL_PAYER, "signer": True},
                    {"pubkey": SOL_DEST, "signer": False},
                    {"pubkey": SOL_SOURCE, "signer": False},
                ],
                "instructions": [
                    transfer, {"program": "spl-memo",
                               "parsed": "FRONTIER-OMEGA:ord-001:abc012"},
                ],
            },
        },
        "meta": {
            "err": None, "innerInstructions": [],
            "preTokenBalances": [
                {"accountIndex": 1, "mint": SOL_MINT, "owner": SOL_OWNER,
                 "programId": SPL_TOKEN,
                 "uiTokenAmount": {"amount": "3", "decimals": 6}},
                {"accountIndex": 2, "mint": SOL_MINT, "owner": SOL_PAYER,
                 "programId": SPL_TOKEN,
                 "uiTokenAmount": {"amount": "2000000", "decimals": 6}},
            ],
            "postTokenBalances": [
                {"accountIndex": 1, "mint": SOL_MINT, "owner": SOL_OWNER,
                 "programId": SPL_TOKEN,
                 "uiTokenAmount": {"amount": str(amount + 3), "decimals": 6}},
            ],
        },
    }
    mint = {
        "owner": SPL_TOKEN, "data": {
            "program": "spl-token",
            "parsed": {"type": "mint", "info": {"decimals": 6}},
        },
    }
    treasury = {
        "owner": SPL_TOKEN, "data": {
            "program": "spl-token",
            "parsed": {
                "type": "account",
                "info": {"owner": SOL_OWNER, "mint": SOL_MINT,
                         "tokenAmount": {"amount": "1000003", "decimals": 6}},
            },
        },
    }
    return quote, tx, mint, treasury


class EthereumProofTests(unittest.TestCase):
    def verify(self, data):
        return ethereum_evidence(*data, ETH_CHAIN_ID)

    def test_accept_final_unique_exact_transfer(self):
        proof = self.verify(eth_fixture())
        self.assertEqual(proof["chain"], "ethereum")
        self.assertEqual(proof["finality"], "finalized")
        self.assertTrue(proof["event_id"].endswith(":0"))

    def test_reject_wrong_token(self):
        a = list(copy.deepcopy(eth_fixture()))
        a[1]["logs"][0]["address"] = "0x" + "11" * 20
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_wrong_recipient(self):
        a = list(copy.deepcopy(eth_fixture()))
        a[0]["recipient"] = "0x" + "22" * 20
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_unbound_amount(self):
        a = list(copy.deepcopy(eth_fixture()))
        a[0]["unique_amount_bound"] = False
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_shortpayment(self):
        a = list(copy.deepcopy(eth_fixture()))
        a[0]["amount_units"] = str(int(a[0]["amount_units"]) + 1)
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_failed_transaction(self):
        a = list(copy.deepcopy(eth_fixture()))
        a[1]["status"] = "0x0"
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_unfinalized_block(self):
        a = list(copy.deepcopy(eth_fixture()))
        a[4]["number"] = "0x63"
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_reorg_mismatched_block(self):
        a = list(copy.deepcopy(eth_fixture()))
        a[3]["hash"] = "0x" + "ef" * 32
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_wrong_chain(self):
        with self.assertRaises(PaymentRejected):
            ethereum_evidence(*eth_fixture(), "0xaa36a7")

    def test_reject_older_transfer(self):
        a = list(copy.deepcopy(eth_fixture()))
        a[3]["timestamp"] = hex(1699999999)
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_duplicate_matching_logs(self):
        a = list(copy.deepcopy(eth_fixture()))
        a[1]["logs"].append({**a[1]["logs"][0], "logIndex": "0x1"})
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_no_rpc_in_offline_mode(self):
        quote = eth_fixture()[0]
        with self.assertRaises(PaymentRejected):
            verify_over_rpc(quote)


class SolanaProofTests(unittest.TestCase):
    def verify(self, args):
        return solana_evidence(*args, SOL_GENESIS)

    def test_accept_final_transfer_with_order_memo(self):
        proof = self.verify(sol_fixture())
        self.assertEqual(proof["chain"], "solana")
        self.assertEqual(proof["amount_units"], "1000000")
        self.assertEqual(proof["event_id"], "solana:" + SOL_SIG)

    def test_reject_wrong_mint(self):
        a = list(copy.deepcopy(sol_fixture()))
        a[3]["data"]["parsed"]["info"]["mint"] = "E" * 44
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_wrong_recipient_owner(self):
        a = list(copy.deepcopy(sol_fixture()))
        a[3]["data"]["parsed"]["info"]["owner"] = "E" * 44
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_no_memo(self):
        a = list(copy.deepcopy(sol_fixture()))
        a[1]["transaction"]["message"]["instructions"].pop()
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_different_memo(self):
        a = list(copy.deepcopy(sol_fixture()))
        a[1]["transaction"]["message"]["instructions"][1]["parsed"] += "-wrong"
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_bad_chain(self):
        with self.assertRaises(PaymentRejected):
            solana_evidence(*sol_fixture(), "devnet-genesis")

    def test_reject_wrong_transfer_amount(self):
        a = list(copy.deepcopy(sol_fixture()))
        a[1]["transaction"]["message"]["instructions"][0]["parsed"]["info"]["tokenAmount"]["amount"] = "99999"
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_net_balance_not_equal_transfer(self):
        a = list(copy.deepcopy(sol_fixture()))
        a[1]["meta"]["postTokenBalances"][0]["uiTokenAmount"]["amount"] = "900003"
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_nonfinal_failure(self):
        a = list(copy.deepcopy(sol_fixture()))
        a[1]["meta"]["err"] = {"InstructionError": [0, "Failed"]}
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_no_payer_signature(self):
        a = list(copy.deepcopy(sol_fixture()))
        a[1]["transaction"]["message"]["accountKeys"][0]["signer"] = False
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_untrusted_inner_cpi(self):
        a = list(copy.deepcopy(sol_fixture()))
        a[1]["meta"]["innerInstructions"] = [{"index": 0, "instructions": []}]
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_fake_token_program(self):
        a = list(copy.deepcopy(sol_fixture()))
        a[3]["owner"] = "E" * 44
        with self.assertRaises(PaymentRejected):
            self.verify(a)

    def test_reject_old_tx(self):
        a = list(copy.deepcopy(sol_fixture()))
        a[1]["blockTime"] = 1699999999
        with self.assertRaises(PaymentRejected):
            self.verify(a)


class RpcGuardTests(unittest.TestCase):
    def test_require_https(self):
        with self.assertRaises(PaymentRejected):
            JsonRpc("http://localhost:8899")

    def test_reject_url_credentials(self):
        with self.assertRaises(PaymentRejected):
            JsonRpc("https://user:secret@example.org/")

    def test_require_operator_config(self):
        quote = sol_fixture()[0]
        with self.assertRaises(PaymentRejected):
            verify_over_rpc(quote)


if __name__ == "__main__":
    unittest.main()
