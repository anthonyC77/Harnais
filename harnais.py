#!/usr/bin/env python3
"""Installe le harnais dans un projet, et mesure ce qui a dérivé.

Pourquoi cet outil existe : le harnais a été copié dans trois dépôts, puis
renommé dans l'un d'eux, et personne ne savait plus lequel faisait foi. Les
trois copies étaient pourtant le même artefact — la divergence était un
chercher-remplacer. Une copie n'est pas un problème ; une copie dont on ne peut
pas mesurer la dérive en est un.

    python3 harnais.py installer --projet ../coachingia --hooks ps1
    python3 harnais.py verifier  --projet ../coachingia
    python3 harnais.py etat

Codes de sortie, mêmes que ceux des oracles :
    0  rien n'a dérivé
    1  au moins un fichier du noyau diffère
    2  erreur d'exécution (projet introuvable, pas de .harnais)

Stdlib uniquement, aucune dépendance réseau — même règle que les oracles qu'il
transporte.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent
MARQUEUR = ".harnais"

# ── Ce que le harnais possède ────────────────────────────────────────────────
# Tout le reste appartient au projet. La ligne de partage n'est pas technique,
# elle est morale : l'OUTIL qui mesure est générique, l'ÉTALON qu'il lit
# appartient à ce qu'il mesure. Un golden set partagé entre deux projets ne
# mesure plus ni l'un ni l'autre.
NOYAU: list[tuple[str, str]] = [
    # (source dans le harnais, destination dans le projet)
    ("claude/agents", ".claude/agents"),
    ("claude/skills", ".claude/skills"),
    ("claude/hooks/test_hooks.py", ".claude/hooks/test_hooks.py"),
    ("eval/run_eval.py", "eval/run_eval.py"),
    ("eval/run_tasks_eval.py", "eval/run_tasks_eval.py"),
    ("eval/check_nodes.py", "eval/check_nodes.py"),
    ("eval/check_tool_schemas.py", "eval/check_tool_schemas.py"),
    ("eval/gen_tool_schemas.py", "eval/gen_tool_schemas.py"),
    ("eval/jsonschema_lite.py", "eval/jsonschema_lite.py"),
    ("eval/width_report.py", "eval/width_report.py"),
    ("eval/juge_local.py", "eval/juge_local.py"),
    ("eval/plier_evenements.py", "eval/plier_evenements.py"),
    ("eval/deplier_runs.py", "eval/deplier_runs.py"),
    ("eval/tests/test_eval.py", "eval/tests/test_eval.py"),
    # La boucle d'apprentissage : les scripts, la consigne, le schéma — pas les mesures ni la file.
    ("eval/lire_transcripts.py", "eval/lire_transcripts.py"),
    ("eval/mesurer_sessions.py", "eval/mesurer_sessions.py"),
    ("eval/extraire_candidats.py", "eval/extraire_candidats.py"),
    ("eval/passation.py", "eval/passation.py"),
    ("eval/consigne-extraction.md", "eval/consigne-extraction.md"),
    ("eval/schemas/candidat.schema.json", "eval/schemas/candidat.schema.json"),
    ("eval/tests/test_apprentissage.py", "eval/tests/test_apprentissage.py"),
    ("eval/schemas/run_contract.schema.json", "eval/schemas/run_contract.schema.json"),
    ("eval/schemas/run_events.schema.json", "eval/schemas/run_events.schema.json"),
    ("eval/schemas/verdicts.schema.json", "eval/schemas/verdicts.schema.json"),
    ("eval/fixtures", "eval/fixtures"),
]

# Jamais écrasé par `installer`. Ce sont les étalons : ils se signent, ils ne
# se distribuent pas.
AU_PROJET = [
    "eval/golden_set.jsonl", "eval/tasks_golden.jsonl", "eval/baseline.json",
    "eval/guardrail_probes.jsonl", "eval/policy/agents.json", "eval/tasks/",
    ".claude/rules/", ".claude/settings.json",
    # La boucle d'apprentissage : la grille de prix, les seuils, les lexiques et les mesures
    # (modèle dans modele/eval/apprentissage/, à copier une fois) ; la file de candidats et
    # les passations (créées au premier run).
    "eval/apprentissage/", ".claude/apprentissage/",
]


def empreinte(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()[:16]


def fichiers_du_noyau() -> dict[str, Path]:
    """Chemin de destination → fichier source, à plat."""
    out: dict[str, Path] = {}
    for source, dest in NOYAU:
        src = RACINE / source
        if src.is_file():
            out[dest] = src
        elif src.is_dir():
            for f in sorted(src.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    out[f"{dest}/{f.relative_to(src).as_posix()}"] = f
    return out


def version_du_noyau() -> str:
    """Une empreinte du noyau entier : elle change dès qu'un fichier change."""
    h = hashlib.sha256()
    for dest, src in sorted(fichiers_du_noyau().items()):
        h.update(dest.encode())
        h.update(empreinte(src).encode())
    return h.hexdigest()[:12]


# ── installer ────────────────────────────────────────────────────────────────

def installer(projet: Path, hooks: str, forcer: bool) -> int:
    if not projet.is_dir():
        print(f"projet introuvable : {projet}", file=sys.stderr)
        return 2

    pose, gardes = [], []
    for dest, src in sorted(fichiers_du_noyau().items()):
        cible = projet / dest
        if cible.exists() and not forcer and empreinte(cible) != empreinte(src):
            gardes.append(dest)
            continue
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, cible)
        pose.append(dest)

    # Les hooks vont dans les deux langages, mais un seul est installé : le
    # poste décide. CoachingIA a réécrit les trois gardes en PowerShell parce
    # que `jq` n'est pas installé — et sans `jq` les versions shell sortaient
    # en code 0, c'est-à-dire qu'elles autorisaient tout, en silence.
    dossier_hooks = RACINE / "claude" / "hooks" / hooks
    if not dossier_hooks.is_dir():
        print(f"langage de hooks inconnu : {hooks} (sh ou ps1)", file=sys.stderr)
        return 2
    for f in sorted(dossier_hooks.iterdir()):
        if not f.is_file():
            continue
        cible = projet / ".claude" / "hooks" / f.name
        if cible.exists() and not forcer and empreinte(cible) != empreinte(f):
            gardes.append(f".claude/hooks/{f.name}")
            continue
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, cible)
        pose.append(f".claude/hooks/{f.name}")

    marque = {
        "version": version_du_noyau(),
        "hooks": hooks,
        "pose_le": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "fichiers": {d: empreinte(s) for d, s in sorted(fichiers_du_noyau().items())},
    }
    (projet / MARQUEUR).write_text(
        json.dumps(marque, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"harnais {marque['version']} posé dans {projet}  (hooks : {hooks})")
    print(f"  {len(pose)} fichier(s) écrit(s)")
    if gardes:
        print(f"  {len(gardes)} fichier(s) gardé(s), ils diffèrent localement "
              f"— `--forcer` pour écraser, `verifier` pour voir :")
        for g in gardes:
            print(f"      {g}")
    print("\n  Jamais touché — c'est votre étalon, il se signe :")
    for a in AU_PROJET:
        print(f"      {a}")
    return 0


# ── verifier ─────────────────────────────────────────────────────────────────

def verifier(projet: Path, bavard: bool = True) -> tuple[int, str]:
    marqueur = projet / MARQUEUR
    if not marqueur.is_file():
        if bavard:
            print(f"{projet} ne porte pas de harnais (pas de {MARQUEUR})", file=sys.stderr)
        return 2, "sans harnais"

    marque = json.loads(marqueur.read_text(encoding="utf-8"))
    actuel = fichiers_du_noyau()
    absents, modifies, obsoletes = [], [], []

    for dest, src in sorted(actuel.items()):
        cible = projet / dest
        if not cible.exists():
            absents.append(dest)
            continue
        vu = empreinte(cible)
        if vu != empreinte(src):
            # On distingue « le projet a touché sa copie » de « le noyau a
            # bougé depuis la pose ». Sans cette distinction on ne sait pas
            # qui doit bouger.
            (obsoletes if vu == marque["fichiers"].get(dest) else modifies).append(dest)

    if bavard:
        print(f"{projet}")
        print(f"  posé   : {marque['version']} le {marque['pose_le']} (hooks : {marque['hooks']})")
        print(f"  source : {version_du_noyau()}")
        for titre, liste in (("absent", absents), ("modifié sur place", modifies),
                             ("en retard sur la source", obsoletes)):
            for f in liste:
                print(f"    {titre:24} {f}")
        if not (absents or modifies or obsoletes):
            print("    conforme")

    etat = ("conforme" if not (absents or modifies or obsoletes)
            else f"{len(modifies)} modifié(s), {len(obsoletes)} en retard, {len(absents)} absent(s)")
    return (0 if etat == "conforme" else 1), etat


# ── etat ─────────────────────────────────────────────────────────────────────

def etat(classeur: Path) -> int:
    """Une ligne par projet du classeur. C'est la mesure qui manquait : on
    voyait trois copies, on ne voyait pas laquelle avait dérivé."""
    projets = sorted(d for d in classeur.iterdir()
                     if d.is_dir() and (d / MARQUEUR).is_file())
    if not projets:
        print(f"aucun projet porteur du harnais sous {classeur}")
        print(f"  posez-le avec : python3 harnais.py installer --projet <dossier>")
        return 0

    print(f"noyau : {version_du_noyau()}\n")
    pire = 0
    for p in projets:
        code, resume = verifier(p, bavard=False)
        marque = json.loads((p / MARQUEUR).read_text(encoding="utf-8"))
        drapeau = "  " if code == 0 else "! "
        print(f"{drapeau}{p.name:24} {marque['version']}  {marque['hooks']:4} {resume}")
        pire = max(pire, code)
    return pire


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sous = p.add_subparsers(dest="commande", required=True)

    i = sous.add_parser("installer", help="poser ou actualiser le harnais dans un projet")
    i.add_argument("--projet", required=True, type=Path)
    i.add_argument("--hooks", default="sh", choices=["sh", "ps1"],
                   help="langage des gardes : sh (jq requis) ou ps1 (Windows)")
    i.add_argument("--forcer", action="store_true",
                   help="écraser les fichiers du noyau modifiés sur place")

    v = sous.add_parser("verifier", help="dire ce qui a dérivé dans un projet")
    v.add_argument("--projet", required=True, type=Path)

    e = sous.add_parser("etat", help="l'état de tous les projets du classeur")
    e.add_argument("--classeur", type=Path, default=RACINE.parent)

    a = p.parse_args()
    if a.commande == "installer":
        return installer(a.projet.resolve(), a.hooks, a.forcer)
    if a.commande == "verifier":
        return verifier(a.projet.resolve())[0]
    return etat(a.classeur.resolve())


if __name__ == "__main__":
    sys.exit(main())
