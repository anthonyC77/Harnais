#!/usr/bin/env python3
"""Plie des runs en événements en runs résumés : ce qu'on a vu devient ce qu'on peut juger.

Entrée : un ou plusieurs fichiers *.events.jsonl conformes à
eval/schemas/run_events.schema.json (une ligne d'en-tête, puis une ligne par
événement). Sortie : un runs.jsonl conforme à eval/schemas/run_contract.schema.json,
un run par fichier, que run_tasks_eval.py peut juger.

    python3 eval/plier_evenements.py runs/*.events.jsonl --out runs.jsonl
    python3 eval/run_tasks_eval.py --runs runs.jsonl --judge-cmd "python3 eval/juge_local.py"

Ce que le script refuse (code 2, nom du fichier sur stderr) : pas d'en-tête,
pas de run.start en tête, pas de run.end en queue, un trou dans seq, un genre
ou un champ hors contrat. Un run plié qui ne passe pas le contrat de run n'est
pas écrit. Un tool.start jamais revenu n'est pas une erreur de format : c'est
un tool_calls[] avec ok: false et sans latency_ms.

Stdlib uniquement. Deux règles que le JSON Schema ne sait pas exprimer
(contiguïté de seq, ordre des lignes) vivent dans verifier_evenements().
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from jsonschema_lite import validate  # noqa: E402

SCHEMAS = os.path.join(HERE, "schemas")


def charger_schema(nom):
    with open(os.path.join(SCHEMAS, nom), encoding="utf-8") as f:
        return json.load(f)


def verifier_evenements(entete, evenements, schema, nom="<événements>"):
    """Ce que le schéma ne dit pas : un en-tête d'abord, seq contigu depuis 0, run.start en tête, run.end en queue.
    Lève ValueError, message préfixé du nom du fichier."""
    def refus(message):
        raise ValueError(f"{nom} : {message}")

    if not isinstance(entete, dict) or "kind" in entete or "run_id" not in entete:
        refus("première ligne sans en-tête (run_id, task_id, agents, policy)")
    erreurs = validate(entete, schema["$defs"]["header"], "en-tête", schema)
    if erreurs:
        refus("; ".join(erreurs[:5]))
    if not evenements:
        refus("aucun événement après l'en-tête")
    genres = schema["$defs"]["kinds"]
    for i, e in enumerate(evenements):
        ligne = i + 2
        genre = e.get("kind") if isinstance(e, dict) else None
        if genre not in genres:
            refus(f"ligne {ligne} : genre inconnu {genre!r}")
        erreurs = validate(e, genres[genre], f"ligne {ligne}", schema)
        if erreurs:
            refus("; ".join(erreurs[:5]))
        if e["seq"] != i:
            refus(f"ligne {ligne} : trou dans seq, attendu {i}, reçu {e['seq']}")
        if e["run"] != entete["run_id"]:
            refus(f"ligne {ligne} : run {e['run']!r} ne correspond pas au run_id de l'en-tête")
    if evenements[0]["kind"] != "run.start":
        refus("le premier événement n'est pas run.start")
    if evenements[-1]["kind"] != "run.end":
        refus("le dernier événement n'est pas run.end — fichier tronqué ?")


def charger(chemin, schema):
    """Un fichier .events.jsonl → (en-tête, événements), vérifié."""
    with open(chemin, encoding="utf-8") as f:
        lignes = [json.loads(l) for l in f if l.strip()]
    if not lignes:
        raise ValueError(f"{chemin} : fichier vide")
    verifier_evenements(lignes[0], lignes[1:], schema, nom=str(chemin))
    return lignes[0], lignes[1:]
