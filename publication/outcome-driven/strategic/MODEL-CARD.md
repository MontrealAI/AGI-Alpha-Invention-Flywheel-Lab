# Strategic formalizer research checkpoint

## Model and intended scope

This local low-rank adapter classifies three structural properties of English and French natural-language briefs for a narrow, two-state zero-sum game with one paid, noisy observation. The properties are observation timing and privacy, unit compatibility, and numerical completeness. The retained exact solver verifies the payoff bounds after an independently reviewed interpretation authorizes a compatible game.

- Base model `HuggingFaceTB/SmolLM2-135M-Instruct`, revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`.
- Base weights SHA-256 `5af571cbf074e6d21a03528d2330792e532ca608f24ac70a143f6b369968ab8c`.
- Adapter SHA-256 `e2cd2721ce4d30115fe6fb0836a10ce2e4f60577ec2d5085064fe8c762aeb913`, 495,672 bytes.
- Base and adapter use Apache-2.0. The base weights remain a separate dependency. [Pinned source](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct/tree/12fd25f77366fa6b3b4b768ec3050bf629380bac)

The model emits three constrained tokens in a fixed order. Numerical values in approved inputs remain unchanged. The compiler checks types and requires agreement with an independently supplied semantic contract before computation.

## Actual fit

The experiment completed all **48 AdamW updates**, changing **122,880 of 122,880** trainable low-rank parameters. It processed 86,106 unpadded tokens. The fit used three CPU threads on an AMD EPYC 9V74 host, taking 141.74 wall seconds and 385.36 process CPU seconds. Peak process memory was 1,579,503,616 bytes. Teacher-forced loss on the fixed training slice fell from 1.640 to 0.857 and disjoint-template development loss from 1.765 to 1.051. The training receipt binds input, code, base and checkpoint bytes. [Fit receipt](TRAINING-RESULT.json) · [Fixed plan](PRE-REGISTRATION.json)

## Qualification boundaries

**Experimental checkpoint. NO-GO for specialist deployment.** The primary route achieved 5/16 complete outcomes and the strongest unadapted matched route achieved 3/16. Adaptation yielded a 12.5 percentage-point gain in this panel, alongside six false solver proposals. The required minimum was 80% whole-outcome agreement, zero false proposals, at least two independently certified supported cases, and at least 10 percentage points of improvement. Both compatible games produced exact certificates under independent interpretation review. The independent authority blocked every false proposal. The included-Codex assisted control separately scored 16/16. [Independent assessment](CONFIRMATION-RESULT.json) · [Assisted assessment](ASSISTED-RESULT.json)

Source case descriptions and numerical inputs are synthetic. Held prose and exact semantics were separately authored. The assessment uses a shared administrative environment. The test score covers only the declared finite game and input boundary. Use the independent outcome gate, numerical authority and exact solver checks for a concrete application. French and English results apply to the tested cases in each language.

Energy and the complete operating cost were unobserved. The direct included-Codex control uses different compute. The study reports both direct model interpretation and conclusions after applying the exact data-presence tool.
