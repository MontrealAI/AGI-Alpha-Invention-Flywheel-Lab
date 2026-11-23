# 🌌♾️ FRONTIER Ω ALPHA — Possibility Observatory

## Mission

**Characterize the accelerating frontier. Discover the newly possible. Challenge inherited constraints. Experiment. Verify. Learn.**

This additive, research-only component turns the existing public release checkpoint into a **Possibility Atlas** and a **human-review experiment queue**. It does not automatically invent valuable technology, access ChatGPT conversations, authorize experiments, or establish commercial return.

Its purpose is to retain blocked outcomes and reopen them when primary-source evidence changes. Always compare against the strongest legitimate complete alternative, including deterministic and compiled workflows. A new announcement is not proof that a previously impossible outcome is now attainable.

## Implemented interfaces

- **Source inventory:** the six GitHub release feeds in the existing research.scheduled.SOURCES registry (Lean 4, llama.cpp, vLLM, ROCm, Ollama and SciPy). This is a finite starting sample, **not** a frontier-wide census.
- **Blocked-purpose registry:** five bounded candidate outcomes with constraints, alternatives, rights restrictions, Missing Move questions and falsifiers. The inputs are in blocked-purposes.json.
- **Frontier Replay:** a published version change reopens its linked purpose **for review**, not for execution, automatic alert, or an improvement claim. First sightings and metadata-only changes are insufficient.
- **Finding intake:** an optional --approved-record accepts only explicitly reviewed public v2 normalized findings with GitHub-authenticated submission. Research-task origin is operator-declared, not automatically authenticated. Unrelated chats and task history are never imported.
- **Review-only queue:** the proposed experiments, strong comparators and falsifiers. No code execution is initiated by this queue.
- **Independent discovery audit:** optional external, independently labelled source/version events. If absent, coverage is *not assessed*. Even with controls, coverage applies only to the labelled set and is not an estimate of whole-frontier recall.
- **Bilingual reports:** English and French Markdown plus a machine-readable atlas, written to a newly created private output directory. No protected content or GitHub Pages files are changed.

## Reproduce

Run from products/frontier-omega-alpha with Python 3.11+ and the existing HARNESS source bridge.

    python3 -B -m unittest discover -s tests -p test_possibility_observatory.py -v

Given a verified public source checkpoint from frontier-omega-alpha-radar:

    python3 -m research.possibility_observatory \
      --observations /private/radar.json \
      --as-of 2026-11-23 \
      --output /private/atlas-20261123

Outputs: atlas.json, experiment-queue.json, atlas.en.md, atlas.fr.md. Input provenance includes SHA-256 hashes of the exact source checkpoint, blocked-purpose registry and any approved findings.

To include a separately owner-reviewed normalized finding, add --approved-record /private/record-<digest>.json. Use the output of the existing intelligence_bridge confirm-ledger procedure. Raw conversations and unreviewed private submissions are prohibited.

For an independently audited reference set, provide a JSON document of this form (illustrative format, not an executed audit):

    {
      "schema": "frontier-omega-alpha/independent-coverage-review-v1",
      "events": [
        {
          "id": "independently-reviewed-event",
          "source_key": "formal_verification",
          "tag": "v4.36.0",
          "evidence_url": "https://api.github.com/repos/leanprover/lean4/releases/tags/v4.36.0",
          "reviewer": "approved-independent-reviewer",
          "reviewed_at": "2026-11-23T00:00:00Z"
        }
      ]
    }

Pass this document as --audit /private/independent-controls.json. No audit percentage should be reported outside the precise set of reviewed controls.

## Daily scheduling

The new FRONTIER Ω ALPHA Possibility Observatory workflow runs regression tests when proposed in a PR.

It also contains a **read-only daily** job that compares the already registered public radar checkpoint with current official releases, produces the bilingual atlas and queues review candidates. It is **off by default**. Once reviewed, merged and expressly approved, the owner can enable it through repository variable FRONTIER_ALPHA_OBSERVATORY_ENABLED=true on protected main.

The job has contents:read privileges only. It uploads short-retention workflow artifacts; it never commits, opens PRs, calls paid OpenAI APIs, mutates ChatGPT tasks, publishes member research or provisions wallets. The existing protected publishing and GitHub administrator release gates remain completely separate.

GitHub cron uses UTC; this does not guarantee an exact Toronto hour and GitHub may delay a run. When sources are unavailable, report the failure rather than fabricating a change or using an obsolete checkpoint as new evidence.

The three-hour ChatGPT monitoring task continues independently and has **no automatic GitHub upload**. Its findings can be included only after the already approved manual, privacy-scoped submission and explicit record qualification.

## Scientific boundaries

| Evidence | Permitted decision |
| --- | --- |
| Publisher version changed | Reopen blocked purpose for investigation |
| Reviewed research record | Source-linked claim requiring independent qualification |
| Candidate tied with capable incumbent | No demonstrated technical advantage |
| Real beneficiary accepted a capability | Investigate benefit after full costs |
| Funds actually collected plus strong matched comparison | Evaluate realized incremental economic advantage |
| Retained S₁ assists a different S₂ | Test against ordinary reuse and equal-content controls before claiming inventor improvement |

The current compiler does not autonomously generate missing-move hypotheses; it exposes structured questions for qualified researchers. Construction, success on unseen cases, economic results, and causal invention improvements require additional evidence.

## Français — limites et confidentialité

L'Observatoire conserve cinq objectifs encore bloqués, lit six sources publiques identifiées et propose une revue lorsqu'une version publiée change réellement. Une nouvelle version ne prouve ni une nouvelle capacité ni un gain économique. Les sorties comprennent un atlas, une file d'expériences à examiner et des rapports bilingues.

L'audit indépendant exige des références étiquetées par un évaluateur. En l'absence de références, le rappel est **inconnu**. Même avec des contrôles, la couverture ne concerne que les événements évalués, pas toute la frontière scientifique.

Les conversations ChatGPT, fichiers privés, secrets et dossiers personnels ne sont jamais transférés automatiquement. La tâche de trois heures et son transfert manuel sous approbation ne sont pas modifiés. Aucun accès membre, publication chiffrée ou transaction n'est activé par ce module.

**FRONTIER Ω ALPHA is technological and scientific possibility discovery, not securities analysis or investment advice.**
