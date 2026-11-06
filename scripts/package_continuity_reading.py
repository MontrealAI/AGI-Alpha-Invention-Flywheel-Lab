#!/usr/bin/env python3
"""Package and check the CONTINUITY Ω reading companion using the standard library.

Assemble et contrôle le compagnon de lecture CONTINUITÉ Ω avec la bibliothèque standard.
This is presentation qualification, not a new audit or authenticity guarantee.
Il s’agit d’un contrôle de présentation, sans nouvel audit ni garantie d’authenticité.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import zipfile


VERSION = "1.0.1"
TAG = "continuity-omega-reading-v1.0.1"
ASSET = "CONTINUITY_OMEGA_BILINGUAL_COMPANION.zip"
SOURCE_COMMIT = "17bb5ee4678e59df5c8c271a435426b686210e4f"
PAPER = "docs/continuity-omega-paper/"
PAPER_MANIFEST = PAPER + "PUBLICATION.json"
PAPER_EDITION = "1.1.1"
PAPER_MANIFEST_SHA256 = "ae291ff6971ead62de9b4bac0fa724f2b593ffa052abb0893a6e56e50f2cd910"
PRESENTER = "scripts/continuity_passport.py"
PACKAGER = "scripts/package_continuity_reading.py"
LANGUAGES = ("en", "fr")
CASES = (
    "nominal", "tampered_source", "overbooked", "correlated_outage",
    "unqualified", "late", "buyer_declines", "uneconomic",
    "unapproved_sharing", "no_order_source", "missing_from_restored", "extra_restored",
)
PASS_CASES = frozenset(("nominal", "missing_from_restored", "extra_restored"))
EXAMPLES = ("nominal", "overbooked")
CORE_PINS = {
    "continuity_omega/__init__.py": "b7de658c6d80c49338fc65f066461a59688fa26acf61569930ee1dd553d53a14",
    "continuity_omega/__main__.py": "79ee6f134c5c5193377cf9b189cbdcc3e2095e49ba9cec310114441c15a917c4",
    "continuity_omega/checker.py": "860e4725f61ef7489ca89d210a42447f48d9ef4f27ea002b631ad9c81fe1d277",
    "continuity_omega/cli.py": "d665f47e19e4c4b4391f54196cefa4004478af7b601a0ed7ff23e4abe3cdfb1d",
    "continuity_omega/demo.py": "4fe75e34c600efe11cd5477afc18a2de09e51dc173a017f5f8e63a6da9b5e576",
    "continuity_omega/engine.py": "8629ded8485ec16166fd16bb31eb96bddd7c64896a562e9ccd45a7d7c70fcf62",
    "tests/test_continuity_omega.py": "c94754ce00f90e0314f519186b8557021f9b2adc91a7c12b70b356d0a57eca5b",
}
GUIDES = (
    "README.md", "README.fr.md", "QUICKSTART.md", "QUICKSTART.fr.md",
    "REAL_PILOT.md", "REAL_PILOT.fr.md", "OUTPUTS.md", "OUTPUTS.fr.md",
    "READING_RELEASE.md",
)
PAPER_FILES = (
    ".gitignore", "CITATION.cff", "CITATION.fr.cff", "CLAIMS.fr.json", "CLAIMS.json",
    "CONTINUITY_OMEGA.pdf", "CONTINUITY_OMEGA.tex", "CONTINUITY_OMEGA_FR.pdf",
    "CONTINUITY_OMEGA_FR.tex", "EVIDENCE.fr.md", "EVIDENCE.md", "README.fr.md",
    "README.md", "RELEASE_NOTES.md", "REVIEW.fr.md", "REVIEW.md", "SOURCE_MAP.fr.md",
    "SOURCE_MAP.md", "TRANSLATION.md", "build.py", "check_translations.py",
    "counterexamples.py", "evidence/COUNTEREXAMPLES.json", "evidence/POOLING.json",
    "evidence/QA.json", "evidence/REPRODUCTION.json", "evidence/TRANSLATION_QA.json",
    "package.py", "pooling_example.py", "reproduce.py", "verify.py",
)
SOURCE_PATHS = tuple(sorted(
    set(CORE_PINS)
    | {PRESENTER, PACKAGER, "tests/test_continuity_passport.py", PAPER_MANIFEST}
    | {"docs/continuity-omega/" + name for name in GUIDES}
    | {PAPER + name for name in PAPER_FILES}
))
SCOPE_EN = (
    "Offline bilingual presentation of recorded synthetic evidence. Package checks establish "
    "content consistency and the specified rendering behavior, not origin authenticity, a fresh "
    "audit, checker correctness, field recovery, customer acceptance or commercial qualification."
)
SCOPE_FR = (
    "Présentation bilingue hors ligne de preuves synthétiques consignées. Les contrôles du paquet "
    "établissent la cohérence des contenus et le comportement de présentation indiqué, sans "
    "authentifier leur origine ni établir un nouvel audit, la correction du vérificateur, une "
    "reprise réelle, l’acceptation par un client ou une qualification commerciale."
)


class PackageError(Exception):
    def __init__(self, en: str, fr: str, detail: str = "") -> None:
        super().__init__(en)
        self.en, self.fr, self.detail = en, fr, detail


def require(condition: bool, en: str, fr: str, detail: str = "") -> None:
    if not condition:
        raise PackageError(en, fr, detail)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": sha256(data)}


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def read_json(data: bytes, label: str) -> dict:
    def pairs(items: list) -> dict:
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key", "Clé JSON dupliquée", label + ": " + key)
            result[key] = value
        return result

    def constant(value: str) -> None:
        raise PackageError("Non-finite JSON value", "Valeur JSON non finie", label + ": " + value)

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError) as error:
        raise PackageError("Malformed JSON", "JSON mal formé", label) from error
    require(isinstance(value, dict), "JSON object required", "Objet JSON requis", label)
    return value


def relative_name(name: str) -> str:
    require(isinstance(name, str) and bool(name) and "\\" not in name and "\x00" not in name,
            "Unsafe package path", "Chemin de paquet non sûr", str(name))
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name
            and all(part not in (".", "..") for part in path.parts),
            "Unsafe package path", "Chemin de paquet non sûr", name)
    return name


def no_symlinks(path: Path) -> Path:
    absolute = path.absolute()
    require(".." not in absolute.parts, "Parent traversal is not allowed",
            "Les segments parents ne sont pas autorisés", str(path))
    for component in (absolute, *absolute.parents):
        require(not component.is_symlink(), "Symbolic links are not allowed",
                "Les liens symboliques ne sont pas autorisés", str(component))
    return absolute


def regular_bytes(root: Path, name: str) -> bytes:
    target = no_symlinks(root / relative_name(name))
    require(target.is_file(), "Required regular file is missing",
            "Fichier ordinaire requis absent", name)
    return target.read_bytes()


def validate_source(files: dict[str, bytes]) -> None:
    require(set(SOURCE_PATHS) <= set(files), "Incomplete source allowlist",
            "Liste explicite de sources incomplète")
    for name, expected in CORE_PINS.items():
        require(sha256(files[name]) == expected, "Frozen prototype or original test changed",
                "Prototype figé ou test original modifié", name)
    require(sha256(files[PAPER_MANIFEST]) == PAPER_MANIFEST_SHA256,
            "Immutable paper manifest changed", "Manifeste immuable de l’article modifié")
    publication = read_json(files[PAPER_MANIFEST], PAPER_MANIFEST)
    require(publication.get("edition") == PAPER_EDITION
            and publication.get("schema") == "continuity-omega-paper/publication/v2"
            and set(publication.get("files", {})) == set(PAPER_FILES),
            "Unexpected paper inventory", "Inventaire de l’article inattendu")
    for name, expected in publication["files"].items():
        require(sha256(files[PAPER + relative_name(name)]) == expected,
                "Paper file differs from its immutable manifest",
                "Un fichier de l’article diffère de son manifeste immuable", name)
    for language in LANGUAGES:
        pdf = publication["languages"][language]
        require(identity(files[PAPER + pdf["pdf"]]) == {
            "bytes": pdf["pdf_bytes"], "sha256": pdf["pdf_sha256"]},
            "Paper PDF identity differs", "L’identité du PDF de l’article diffère", language)


def raw_names(case: str) -> tuple[str, ...]:
    if case in PASS_CASES:
        return ("INPUT.json", "HANDOFF.json", "PASSPORT.json", "AUDIT.json")
    return ("INPUT.json", "REJECTION.json")


def package_paths() -> set[str]:
    paths = set(SOURCE_PATHS) | {"START_HERE.md", "CHECKS.json"}
    for case in EXAMPLES:
        paths.update("examples/" + case + "/" + name for name in raw_names(case))
        paths.update(f"examples/{case}/PASSPORT.{language}.md" for language in LANGUAGES)
    return paths


def materialize(root: Path, files: dict[str, bytes]) -> None:
    for name, data in sorted(files.items()):
        target = root / relative_name(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)


def python(root: Path, *arguments: str) -> subprocess.CompletedProcess:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1",
                       PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-B", *arguments], cwd=root, env=environment,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def diagnostics(result: subprocess.CompletedProcess) -> str:
    return (result.stdout + result.stderr).decode("utf-8", errors="replace")[-3000:]


def render(root: Path, directory: Path, language: str) -> bytes:
    result = python(root, str(root / PRESENTER), "--in-dir", str(directory), "--language", language)
    require(result.returncode == 0 and bool(result.stdout), "Presentation failed",
            "Échec de la présentation", diagnostics(result))
    result.stdout.decode("utf-8")
    return result.stdout


def exercise(source: dict[str, bytes]) -> tuple[dict[str, bytes], dict]:
    examples = {}
    checks = {
        "schema": "continuity-omega-reading/checks/v1",
        "scope_en": SCOPE_EN, "scope_fr": SCOPE_FR,
        "paper_manifest_sha256": PAPER_MANIFEST_SHA256,
        "tests": {}, "synthetic_cases": [],
        "totals": {"cases": 12, "renderings": 24, "stored_synthetic_passes": 3,
                   "stored_refusals": 9, "retained_examples": 2},
    }
    with tempfile.TemporaryDirectory(prefix="continuity-reading-build-") as temporary:
        workspace = Path(temporary)
        root = workspace / "source"
        root.mkdir()
        materialize(root, source)
        for test in ("test_continuity_omega.py", "test_continuity_passport.py"):
            result = python(root, "-m", "unittest", "discover", "-s", "tests", "-p", test, "-v")
            match = re.search(rb"Ran (\d+) tests? in ", result.stderr)
            require(result.returncode == 0 and match is not None,
                    "Bundled test suite failed", "Échec d’une suite de tests incluse",
                    test + "\n" + diagnostics(result))
            count = int(match.group(1))
            require(count == 29 if test == "test_continuity_omega.py" else count > 0,
                    "Unexpected test count", "Nombre de tests inattendu", test)
            checks["tests"][test] = {"tests": count, "exit_code": 0}
        for case in CASES:
            generated = workspace / "generated" / case
            result = python(root, "-m", "continuity_omega", "demo", "--case", case, "--out", str(generated))
            expected_code = 0 if case in PASS_CASES else 2
            require(result.returncode == expected_code, "Unexpected synthetic demo exit code",
                    "Code de sortie synthétique inattendu", case + "\n" + diagnostics(result))
            expected_names = set(raw_names(case)) | ({"PASSPORT.md"} if case in PASS_CASES else set())
            require(generated.is_dir() and {p.name for p in generated.iterdir()} == expected_names,
                    "Unexpected synthetic output inventory", "Inventaire de sorties synthétiques inattendu", case)
            raw = {name: regular_bytes(generated, name) for name in raw_names(case)}
            verdict_file = "AUDIT.json" if case in PASS_CASES else "REJECTION.json"
            verdict = read_json(raw[verdict_file], case + "/" + verdict_file).get("verdict")
            expected_verdict = "PASS_SYNTHETIC_ONLY" if case in PASS_CASES else "REJECTED_BEFORE_HANDOFF"
            require(verdict == expected_verdict, "Unexpected recorded verdict",
                    "Verdict consigné inattendu", case)
            inputs = workspace / "presentation-inputs" / case
            inputs.mkdir(parents=True)
            materialize(inputs, raw)
            row = {"case": case, "cli_exit_code": result.returncode,
                   "stored_verdict": verdict, "raw_files": {name: identity(data) for name, data in raw.items()},
                   "renderings": {}}
            if case in EXAMPLES:
                examples.update({f"examples/{case}/{name}": data for name, data in raw.items()})
            for language in LANGUAGES:
                report = render(root, inputs, language)
                row["renderings"][language] = identity(report)
                if case in EXAMPLES:
                    examples[f"examples/{case}/PASSPORT.{language}.md"] = report
            require(all(regular_bytes(inputs, name) == data for name, data in raw.items()),
                    "Presentation changed stored records", "La présentation a modifié les données consignées", case)
            checks["synthetic_cases"].append(row)
    return examples, checks


def start_here() -> bytes:
    return f"""# CONTINUITY Ω / CONTINUITÉ Ω — Reading companion / Compagnon de lecture

**Companion / Compagnon {VERSION}** · **Paper / Article {PAPER_EDITION}**

## English — CONTINUITY Ω: read the record; understand its limits

This archive provides the offline English and French reading paths, the unchanged synthetic
prototype, and the complete immutable paper edition {PAPER_EDITION}. It is a separate reading release;
it does not replace or revise the paper release. Start with a human-readable example:

| Reading path / Parcours de lecture | English | Français |
|---|---|---|
| Nominal synthetic case / Cas synthétique nominal | [Recorded passport](examples/nominal/PASSPORT.en.md) | [Passeport consigné](examples/nominal/PASSPORT.fr.md) |
| Overbooked synthetic case / Cas synthétique de capacité déjà réservée | [Recorded refusal](examples/overbooked/PASSPORT.en.md) | [Refus consigné](examples/overbooked/PASSPORT.fr.md) |
| Prototype | [Overview](docs/continuity-omega/README.md) | [Vue d’ensemble](docs/continuity-omega/README.fr.md) |
| Run and read / Exécuter et lire | [Quick start](docs/continuity-omega/QUICKSTART.md) | [Démarrage rapide](docs/continuity-omega/QUICKSTART.fr.md) |
| Output meanings / Signification des sorties | [Reading outputs](docs/continuity-omega/OUTPUTS.md) | [Lire les sorties](docs/continuity-omega/OUTPUTS.fr.md) |
| Real pilot proposal / Proposition de pilote réel | [Conditions and limits](docs/continuity-omega/REAL_PILOT.md) | [Conditions et limites](docs/continuity-omega/REAL_PILOT.fr.md) |
| Research paper / Article de recherche | [English PDF](docs/continuity-omega-paper/CONTINUITY_OMEGA.pdf) | [PDF français](docs/continuity-omega-paper/CONTINUITY_OMEGA_FR.pdf) |
| Evidence and weaknesses / Preuves et faiblesses | [Complete evidence guide](docs/continuity-omega-paper/EVIDENCE.md) | [Guide complet des preuves](docs/continuity-omega-paper/EVIDENCE.fr.md) |

### Run the downloaded presentation

Extract the ZIP into a new directory. From that extracted directory, use Python 3.10 or later;
the following commands require only its standard library, with no network, package installation
or API key:

```bash
python3 -B scripts/package_continuity_reading.py --check .
python3 -B scripts/continuity_passport.py --in-dir examples/nominal --language en
python3 -B scripts/continuity_passport.py --in-dir examples/overbooked --language en
```

The package check matches the complete inventory, byte counts and hashes, then runs the
extracted presenter four times: both examples in both languages. It compares each result
byte for byte with its packaged Markdown. **It does not rerun the audit.** The presenter’s
exit code `0` means it rendered supported records, including a recorded failure or refusal;
it does not mean the underlying exercise passed. Exit code `2` means presentation was refused.

Keep the extracted archive unchanged when checking it. To save another report with `--out`,
choose a new absolute filename in an existing directory outside the extracted archive and
outside its input directory. Generate new demo results outside the archive as well.

### What this archive includes—and establishes

`MANIFEST.json` lists every packaged file except itself, with SHA-256 and byte count.
`CHECKS.json` records build-time execution of the original 29 tests, the included focused
presentation suite, all 12 synthetic cases and 24 language renders. The native synthetic
decisions are three passes and nine refusals. Only two representative raw JSON sets and their
four readable reports are retained; the legacy English-only `PASSPORT.md` is not packaged.
The JSON keys, schema identifiers, source filenames and machine verdicts remain unchanged.

The explicit source boundary is six `continuity_omega/` files, the two scripts in `scripts/`,
the two included test files, the nine guides in `docs/continuity-omega/`, and all 31 files
listed by the immutable paper’s `PUBLICATION.json`, plus that manifest. Generated contents
are this guide, `CHECKS.json`, `MANIFEST.json` and the two `examples/` directories. Website
pages, social artwork and unrelated repository components are outside this archive.
Paper sources are included for completeness; rebuilding the paper has separate documented
toolchain requirements and is not part of this standard-library reading check.

{SCOPE_EN}

The historical checker’s known weaknesses and source-authenticity limits remain. A local
hash manifest can detect inconsistent bytes; it cannot authenticate its own source.
See [bilingual release notes](docs/continuity-omega/READING_RELEASE.md) for the release boundary.

## Français — CONTINUITÉ Ω : lire les données consignées et comprendre leurs limites

Cette archive réunit les parcours de lecture hors ligne en français et en anglais, le prototype
synthétique inchangé et l’édition immuable {PAPER_EDITION} de l’article au complet. Il s’agit d’une
publication de lecture distincte : elle ne remplace ni ne révise la publication de l’article.
Le tableau ci-dessus donne accès aux deux exemples lisibles, aux guides et aux PDF dans
chaque langue. Les identifiants techniques conservent leur forme d’origine.

### Exécuter la présentation téléchargée

Extrayez le ZIP dans un nouveau répertoire. Depuis ce répertoire, utilisez Python 3.10 ou
une version ultérieure. Les commandes suivantes ne nécessitent que sa bibliothèque standard,
sans réseau, installation de paquets ni clé d’API :

```bash
python3 -B scripts/package_continuity_reading.py --check .
python3 -B scripts/continuity_passport.py --in-dir examples/nominal --language fr
python3 -B scripts/continuity_passport.py --in-dir examples/overbooked --language fr
```

Le contrôle du paquet compare l’inventaire complet, les tailles en octets et les empreintes,
puis exécute le présentateur extrait quatre fois : les deux exemples dans les deux langues.
Il compare chaque résultat, octet par octet, au Markdown inclus. **Il ne relance pas l’audit.**
Le code de sortie `0` du présentateur signifie que des données prises en charge ont été
présentées, y compris un échec ou un refus consigné ; il ne signifie pas que l’exercice
sous-jacent a réussi. Le code `2` signifie que la présentation a été refusée.

Conservez le contenu extrait intact pour le contrôler. Pour enregistrer un autre rapport
avec `--out`, choisissez un nouveau nom de fichier absolu dans un répertoire existant,
à l’extérieur de l’archive extraite et du répertoire d’entrée. Enregistrez également les
nouveaux résultats de démonstration à l’extérieur de l’archive.

### Contenu de l’archive et portée des contrôles

`MANIFEST.json` énumère chaque fichier inclus sauf lui-même, avec son empreinte SHA-256 et
sa taille en octets. `CHECKS.json` consigne l’exécution, lors de l’assemblage, des 29 tests
originaux, de la suite ciblée de présentation incluse, des 12 cas synthétiques et de leurs
24 présentations linguistiques. Les décisions synthétiques d’origine comprennent trois
réussites et neuf refus. Seuls deux jeux représentatifs de fichiers JSON bruts et leurs
quatre rapports lisibles sont conservés ; l’ancien `PASSPORT.md` unilingue anglais est exclu.
Les clés JSON, identifiants de schéma, noms de fichiers sources et verdicts machine sont inchangés.

La liste explicite des sources comprend les six fichiers de `continuity_omega/`, les deux
scripts de `scripts/`, les deux fichiers de tests inclus, les neuf guides de
`docs/continuity-omega/` et les 31 fichiers du manifeste immuable `PUBLICATION.json` de
l’article, ainsi que ce manifeste. Le contenu généré comprend ce guide, `CHECKS.json`,
`MANIFEST.json` et les deux répertoires `examples/`. Les pages du site, les visuels sociaux
et les autres composants du dépôt ne font pas partie de cette archive. Les sources de
l’article sont incluses au complet ; leur compilation exige les outils documentés séparément
et ne fait pas partie de ce contrôle de lecture avec la bibliothèque standard.

{SCOPE_FR}

Les faiblesses connues du vérificateur historique et les limites d’authenticité des sources
demeurent. Un manifeste local d’empreintes peut détecter des incohérences entre les octets ;
il ne peut pas authentifier sa propre origine. Consultez les
[notes de publication bilingues](docs/continuity-omega/READING_RELEASE.md) pour la portée de cette édition.
""".encode("utf-8")


def manifest_header() -> dict:
    return {"schema": "continuity-omega-reading/manifest/v1", "edition": VERSION,
            "release_tag": TAG, "languages": list(LANGUAGES), "paper_edition": PAPER_EDITION,
            "unchanged_core_source_commit": SOURCE_COMMIT,
            "paper_manifest_sha256": PAPER_MANIFEST_SHA256,
            "scope_en": SCOPE_EN, "scope_fr": SCOPE_FR}


def exact_tree(root: Path, expected: set[str]) -> None:
    parents = {str(parent) for name in expected for parent in PurePosixPath(name).parents
               if str(parent) != "."}
    found = set()

    def visit(folder: Path) -> None:
        for entry in os.scandir(folder):
            name = Path(entry.path).relative_to(root).as_posix()
            require(not entry.is_symlink(), "Symbolic link in extracted package",
                    "Lien symbolique dans le paquet extrait", name)
            if entry.is_dir(follow_symlinks=False):
                require(name in parents, "Unknown directory in extracted package",
                        "Répertoire inconnu dans le paquet extrait", name)
                visit(Path(entry.path))
            else:
                require(entry.is_file(follow_symlinks=False) and name in expected,
                        "Unknown or non-regular file in extracted package",
                        "Fichier inconnu ou non ordinaire dans le paquet extrait", name)
                found.add(name)
    visit(root)
    require(found == expected, "Missing packaged files", "Fichiers du paquet absents",
            ", ".join(sorted(expected - found)))


def check(extracted: Path) -> dict:
    root = no_symlinks(extracted)
    require(root.is_dir(), "Extracted directory is missing", "Répertoire extrait absent")
    expected = package_paths()
    exact_tree(root, expected | {"MANIFEST.json"})
    manifest_data = regular_bytes(root, "MANIFEST.json")
    manifest = read_json(manifest_data, "MANIFEST.json")
    require(set(manifest) == set(manifest_header()) | {"files"}
            and all(manifest.get(key) == value for key, value in manifest_header().items())
            and isinstance(manifest.get("files"), dict)
            and set(manifest["files"]) == expected,
            "Unexpected companion manifest", "Manifeste du compagnon inattendu")
    files = {name: regular_bytes(root, name) for name in sorted(expected)}
    for name, data in files.items():
        require(manifest["files"][name] == identity(data), "Packaged file hash or size differs",
                "L’empreinte ou la taille d’un fichier du paquet diffère", name)
    validate_source(files)
    require(files["START_HERE.md"] == start_here(), "Unexpected start guide",
            "Guide d’entrée inattendu")
    checks = read_json(files["CHECKS.json"], "CHECKS.json")
    rows = checks.get("synthetic_cases")
    require(checks.get("schema") == "continuity-omega-reading/checks/v1"
            and checks.get("totals") == {"cases": 12, "renderings": 24,
                "stored_synthetic_passes": 3, "stored_refusals": 9, "retained_examples": 2}
            and checks.get("scope_en") == SCOPE_EN and checks.get("scope_fr") == SCOPE_FR
            and checks.get("paper_manifest_sha256") == PAPER_MANIFEST_SHA256
            and isinstance(rows, list) and all(isinstance(row, dict) for row in rows)
            and [row.get("case") for row in rows] == list(CASES),
            "Unexpected build-time check summary", "Résumé des contrôles d’assemblage inattendu")
    for row in rows:
        case = row["case"]
        require(row.get("cli_exit_code") == (0 if case in PASS_CASES else 2)
                and row.get("stored_verdict") == ("PASS_SYNTHETIC_ONLY" if case in PASS_CASES else "REJECTED_BEFORE_HANDOFF")
                and isinstance(row.get("raw_files"), dict) and set(row["raw_files"]) == set(raw_names(case))
                and isinstance(row.get("renderings"), dict) and set(row["renderings"]) == set(LANGUAGES),
                "Unexpected recorded case summary", "Résumé de cas consigné inattendu", case)
        if case in EXAMPLES:
            require(all(row["raw_files"][name] == identity(files[f"examples/{case}/{name}"])
                        for name in raw_names(case))
                    and all(row["renderings"][language] == identity(files[f"examples/{case}/PASSPORT.{language}.md"])
                            for language in LANGUAGES),
                    "Example differs from its build summary", "L’exemple diffère du résumé d’assemblage", case)
    rendered = []
    for case in EXAMPLES:
        for language in LANGUAGES:
            name = f"examples/{case}/PASSPORT.{language}.md"
            actual = render(root, root / "examples" / case, language)
            require(actual == files[name], "Extracted presentation differs from packaged report",
                    "La présentation extraite diffère du rapport inclus", name)
            rendered.append(name)
    exact_tree(root, expected | {"MANIFEST.json"})
    require(regular_bytes(root, "MANIFEST.json") == manifest_data
            and all(regular_bytes(root, name) == data for name, data in files.items()),
            "Presentation changed package contents", "La présentation a modifié le contenu du paquet")
    return {"status": "CHECKED_PRESENTATION_ONLY", "edition": VERSION,
            "files": len(expected) + 1, "rendered_reports": len(rendered), "reports": rendered,
            "manifest_sha256": sha256(manifest_data), "scope_en": SCOPE_EN, "scope_fr": SCOPE_FR}


def package(output: Path) -> dict:
    require(output.is_absolute(), "Output directory must be absolute",
            "Le répertoire de sortie doit être absolu")
    root = no_symlinks(Path(__file__).absolute().parents[1])
    output = no_symlinks(output)
    require(not output.exists() and output.parent.is_dir(),
            "Output must be a new directory with an existing parent",
            "La sortie doit être un nouveau répertoire dont le parent existe")
    require(not output.is_relative_to(root), "Output must be outside the source tree",
            "La sortie doit être à l’extérieur des sources")
    source = {name: regular_bytes(root, name) for name in SOURCE_PATHS}
    validate_source(source)
    examples, checks = exercise(source)
    files = {**source, **examples, "START_HERE.md": start_here(), "CHECKS.json": json_bytes(checks)}
    require(set(files) == package_paths(), "Unknown generated package path",
            "Chemin généré inconnu dans le paquet")
    files["MANIFEST.json"] = json_bytes({**manifest_header(),
        "files": {name: identity(data) for name, data in sorted(files.items())}})
    output.mkdir()
    archive = output / ASSET
    with archive.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as bundle:
            for name, data in sorted(files.items()):
                entry = zipfile.ZipInfo(relative_name(name), date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = (stat.S_IFREG | 0o644) << 16
                entry.compress_type = zipfile.ZIP_STORED
                bundle.writestr(entry, data)
    with zipfile.ZipFile(archive) as bundle:
        require(bundle.namelist() == sorted(files) and bundle.testzip() is None
                and all(bundle.read(name) == data for name, data in files.items()),
                "Written archive differs from qualified contents",
                "L’archive écrite diffère du contenu qualifié")
    result = {"status": "PACKAGED_PRESENTATION_ONLY", "edition": VERSION,
              "asset": ASSET, **identity(archive.read_bytes()), "files": len(files),
              "synthetic_cases": 12, "build_renderings": 24,
              "scope_en": SCOPE_EN, "scope_fr": SCOPE_FR}
    (output / "PACKAGE_RESULT.json").write_bytes(json_bytes(result))
    return result


class CompanionParser(argparse.ArgumentParser):
    """Keep help and actionable argument refusals available in both languages."""

    def format_usage(self) -> str:
        return super().format_usage().replace("usage:", "Usage / Utilisation :", 1)

    def format_help(self) -> str:
        return super().format_help().replace("usage:", "Usage / Utilisation :", 1)

    def error(self, message: str) -> None:
        detail = ""
        if message.startswith("unrecognized arguments: "):
            en, fr = "Unknown arguments", "Arguments inconnus"
            detail = message.split(": ", 1)[1]
        elif "expected one argument" in message:
            en, fr = "The selected option requires one path", "L’option choisie exige un chemin"
        elif "not allowed with argument" in message or message.startswith("one of the arguments"):
            en = "Choose exactly one of --output NEW_ABSOLUTE_DIR or --check EXTRACTED_DIR"
            fr = "Choisissez exactement --output NEW_ABSOLUTE_DIR ou --check EXTRACTED_DIR"
        else:
            en, fr = "Invalid command", "Commande invalide"
        self.print_usage(sys.stderr)
        print(json_bytes({"status": "REFUSED", "message_en": en + ". Use --help for guidance.",
                          "message_fr": fr + ". Consultez --help pour les instructions.",
                          "detail": detail}).decode("utf-8"), end="", file=sys.stderr)
        self.exit(2)


def main() -> int:
    parser = CompanionParser(add_help=False, allow_abbrev=False, description=(
        "Build or check the offline bilingual CONTINUITY Ω reading companion. / "
        "Assembler ou contrôler le compagnon de lecture bilingue CONTINUITÉ Ω hors ligne."))
    parser._optionals.title = "Options / Options"
    parser.add_argument("-h", "--help", action="help",
                        help="Show help and exit / Afficher l’aide et quitter")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, metavar="NEW_ABSOLUTE_DIR",
                       help="Build a new archive / Assembler une nouvelle archive")
    group.add_argument("--check", type=Path, metavar="EXTRACTED_DIR",
                       help="Check hashes and four presentations / Contrôler les empreintes et quatre présentations")
    arguments = parser.parse_args()
    try:
        result = package(arguments.output) if arguments.output is not None else check(arguments.check)
    except PackageError as error:
        print(json_bytes({"status": "REFUSED", "message_en": error.en,
                          "message_fr": error.fr, "detail": error.detail}).decode("utf-8"), end="", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(json_bytes({"status": "REFUSED", "message_en": "Could not complete the package operation",
                          "message_fr": "Impossible de terminer l’opération sur le paquet",
                          "detail": str(error)}).decode("utf-8"), end="", file=sys.stderr)
        return 2
    print(json_bytes(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
