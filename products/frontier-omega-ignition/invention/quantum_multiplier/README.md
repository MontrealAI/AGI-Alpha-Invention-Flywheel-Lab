# Reversible multiplication for a quantum decoder

**Competition decision — withhold.** This directory contains an executable, independently checked field multiplier. A stronger conventional comparison reduced its apparent 46-CNOT advantage to two gates in a follow-up construction. All five circuits tie on the two resources Google charges for a correct decoder. No contest entry or external acceptance occurred.

Google Quantum AI's October 2026 challenge asks for smaller quantum circuits with a public verifier. Its decoder uses a 12-bit finite field and an 840-qubit syndrome. We investigated whether reordering the linear work in one arithmetic kernel could produce a useful, reusable improvement. The competition scores an entire decoder by its width squared, Toffoli count and the overhead of decoding errors. The overall entry requires three distinct tasks. The November 20 milestone requires the leading overall score and a public notebook. [Official challenge](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/) · [Google's announcement](https://opensource.googleblog.com/2026/10/announcing-verifiable-quantum-circuit-compilation-competition-on-kaggle.html) · [Official method, §III.2](https://arxiv.org/html/2610.23832v2)

## Use the circuit

The delivered `multiplier.kmx` acts on three adjacent twelve-qubit registers. Bits are little-endian. It preserves the first two inputs and XORs their field product into the third register, regardless of its initial value. The modulus is x¹² + x⁶ + x⁴ + x + 1. There are no ancillary qubits, measurements or phases. The 558 instructions comprise 516 CNOTs and 42 Toffolis. The circuit SHA-256 is `edbba356d68a50dce0d31fed74f109c7caed89eea9cfdc898c349865a6f6ad19`.

From the extracted directory, with Python 3.10 or later, run any command below. The first three require only the standard library. The last adds an independent execution check with Google's published SDK when `kickmix==1.0.0` is installed in that interpreter.

```sh
python3 -IB verify_multiplier.py multiplier.kmx
python3 -IB truth_table.py multiplier.kmx
python3 -IB replay.py --output ./new-circuits
python3 -IB replay.py --kickmix
```

Omit `--output` to use a temporary directory. The reconstruction checks the supplied tensor hash, rebuilds all five circuits, checks the distributed bytes against the rebuild, and independently verifies the Boolean polynomial on every output wire. Because the gate set is phase-free and reversible, that algebraic check covers all 2³⁶ assignments across the three registers. Each circuit also faced a control with one Toffoli removed. A separately authored checker exhausts all 16,777,216 operand pairs with a zero target and proves that arbitrary target bits are carried through by the identity map. The SDK run independently exercised the delivered bytes on 256 cases.

The private mission CLI accepts `python3 -B -m ignition --state STATE start examples/quantum.json` from the IGNITION product directory. The verified mission can be viewed, paused, resumed and exported through the ordinary commands. Model calls and external actions are unnecessary. An exported recipient includes `REQUEST.json` with the threshold frozen in that revision. A fresh mission may choose a minimum improvement from 1 to 10,000 basis points. This changes only the requested CNOT comparison. The protocol retains its 500 basis-point threshold, and the commercial decision remains withhold.

## Which advantage survived

| Construction | CNOTs | Toffolis | Qubits |
| --- | ---: | ---: | ---: |
| Ordinary fixed-order rank-42 construction | 1,110 | 42 | 36 |
| Conventional all-start nearest-neighbor ordering and 2-opt | 594 | 42 | 36 |
| Registered variable-pivot construction | 548 | 42 | 36 |
| Stronger conventional scheduling across 144 pivot-order pairs | 518 | 42 | 36 |
| Variable pivots applied to that strongest conventional order, after the primary test | 516 | 42 | 36 |

The initially registered 5% CNOT threshold passed against the first scheduling control. The stronger comparison reversed that conclusion. Even the follow-up advantage was only 0.39%. We have no gate-by-gate comparison to the latest full incumbent decoder or a pure-human productivity trial. The named outside option is to keep the conventional circuit and decline entry on this result.

The prospectively written [primary protocol](PROTOCOL.md), [later sensitivity protocol](SENSITIVITY.md) and [verified recipient receipt](RECEIPT.json) distinguish each comparison. The sensitivity protocol's “548-bytecode gate count” refers to the primary circuit's 548 CNOTs. The primary circuit has 590 total instructions. The protocols were frozen and hashed locally during the execution session. Their later publication is not independent timestamp attestation.

## Economics, access and reuse

No payment, submission, prize or prize eligibility was observed. The ordinary unauthenticated Kaggle competition download for the DQI verifier returned HTTP 401 in this session. An authorized entrant can accept the official terms and retrieve the full metric and reference data. Entering a competition also requires authority over public notebook release and any resulting entrant obligations. The public papers establish the specification and the simulator, independently of access to that scoring environment. A material change to Toffolis, width or decoding error and an independent full-entry score would be necessary before this kernel could support a paid-prize claim.

The original primary compiler search consumed 0.069 process CPU seconds locally. The stronger control search consumed 4.271 process CPU seconds. These measurements exclude research, software construction, interpreter setup, verification, retries and other session costs. There were no separately purchased services. Monetary cost of included compute and development, and full cost to compete, remain unknown. The optional SDK integration first failed while comparing a returned array to an integer. Specifying integer output fixed the check. All 256 final SDK cases passed.

The compiler, verifier and emitted circuits can be reused for the stated polynomial and wire arrangement. The only third-party input included here is the unmodified numerical rank decomposition in `scheme42.txt` by Nasir Ali, from commit `55161390efc3e8604bab56f3f31e4abbf34c7764`. We ran its original algebraic generator and reproduced the 491 input bytes exactly, SHA-256 `19ee4259f4d20a779d2484b3dea635d2e0efd23fce39c859e70228f668e53093`. The upstream project distributes its code under Apache-2.0. This directory includes its license; newly emitted circuits derive from those attributed rank terms. [Upstream source](https://github.com/nasir26/vqcc-kaggle/blob/55161390efc3e8604bab56f3f31e4abbf34c7764/tasks/dqi/scheme42.py) · [Upstream rights and provenance](https://github.com/nasir26/vqcc-kaggle/blob/55161390efc3e8604bab56f3f31e4abbf34c7764/README.md) · [License](LICENSE.tensor)
