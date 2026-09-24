#!/usr/bin/env python3
"""
Ouvre une session Claude Code pilotée par Qwen (profil `brain`, LM Studio sur le Mac).

    python agent_qwen.py                          # dans le projet courant
    python agent_qwen.py --projet D:/HorusCoachIA/oneiros
    python agent_qwen.py --mdp MOTDEPASSE          # si brain doit être chargé par SSH
    python agent_qwen.py -- --continue             # tout ce qui suit -- va à claude

Claude Code reste sur le PC : il lit, écrit, lance des commandes ici. Seule l'adresse
du modèle change : ANTHROPIC_BASE_URL pointe vers le pont (bridge/server.py, :1235
sur le Mac), qui traduit vers LM Studio (:1234). Il n'y a AUCUNE bascule automatique
vers Anthropic : Mac éteint, la session plante au premier tour. D'où l'ordre :

  1. le pont répond sur /health, sinon diagnostic et sortie 2 — claude n'est pas lancé ;
  2. `brain` est résident (même chemin que resumer.py : HTTP, puis SSH si besoin) ;
  3. l'environnement épingle `brain` sur tous les alias de modèle, car le pont passe
     le nom de modèle tel quel à LM Studio ;
  4. claude est lancé avec cet environnement, son code de sortie est le nôtre.
"""
from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resumer  # noqa: E402

PONT = f"http://{resumer.MAC_IP}:1235"
MODELE = resumer.IDENTIFIANT
# Le pont n'authentifie pas ; ce jeton factice prend la priorité sur la session claude.ai,
# pour que le vrai jeton ne parte jamais vers le LAN, et sans question au démarrage.
JETON_FACTICE = "mac-ia"
PROJET_DEFAUT = "D:/HorusCoachIA"


def pont_debout(base: str = PONT, timeout: float = 5) -> bool:
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=timeout) as rep:
            return rep.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def diagnostic_pont(pont_ok: bool, lmstudio_ok: bool) -> str:
    if pont_ok:
        return ""
    if lmstudio_ok:
        return (f"LM Studio répond sur {resumer.MAC_IP}:{resumer.PORT} mais pas le pont sur :1235.\n"
                f"Depuis le PC :  ssh {resumer.MAC_USER}@{resumer.MAC_IP} \"cd ~/mac-ia && nohup python3 bridge/server.py > bridge.log 2>&1 < /dev/null &\"")
    return (f"Rien ne répond sur {resumer.MAC_IP} : Mac éteint, LM Studio arrêté ou réseau.\n"
            f"Depuis ce PC :  ping {resumer.MAC_IP}   puis, sur le Mac :  lms server start --bind 0.0.0.0")


def environnement_qwen(base: dict) -> dict:
    env = dict(base)
    env.pop("ANTHROPIC_API_KEY", None)
    env.update({
        "ANTHROPIC_BASE_URL": PONT,
        "ANTHROPIC_AUTH_TOKEN": JETON_FACTICE,
        "ANTHROPIC_MODEL": MODELE,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": MODELE,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": MODELE,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": MODELE,
        "CLAUDE_CODE_SUBAGENT_MODEL": MODELE,
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        # brain relit tout le prompt puis réfléchit avant d'émettre : Claude Code coupe un flux muet
        # au bout de 5 min et relance, ce qui refait la queue derrière la génération abandonnée.
        "CLAUDE_STREAM_IDLE_TIMEOUT_MS": "1800000",
        "API_TIMEOUT_MS": "1800000",
        # Le pont jette thinking, cache_control et output_config : autant ne pas les envoyer.
        "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
        "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING": "1",
    })
    return env


def commande_claude(reste: list[str]) -> list[str]:
    return ["claude", *reste]


def arguments_claude(reste: list[str]) -> list[str]:
    """argparse laisse le `--` de séparation en tête du REMAINDER ; claude ne doit pas le voir."""
    return reste[1:] if reste[:1] == ["--"] else list(reste)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Session Claude Code pilotée par Qwen (brain, sur le Mac).")
    ap.add_argument("--projet", default=None, help=f"dossier où lancer claude (défaut : le dossier courant)")
    ap.add_argument("--mdp", help="mot de passe SSH du Mac (sinon demandé, et seulement si brain doit être chargé)")
    ap.add_argument("reste", nargs=argparse.REMAINDER, help="arguments passés à claude, après --")
    args = ap.parse_args(argv[1:])
    reste = arguments_claude(args.reste)

    projet = Path(args.projet) if args.projet else Path.cwd()
    if not projet.is_dir():
        print(f"[pc] projet introuvable : {projet}")
        return 2

    pont_ok = pont_debout()
    if not pont_ok:
        print("[pc] " + diagnostic_pont(False, resumer.serveur_debout()))
        return 2
    print(f"[pc] pont joignable : {PONT}")

    if resumer.brain_resident():
        print(f"[pc] '{MODELE}' déjà résident sur le Mac, pas de SSH.")
    else:
        mot_de_passe = args.mdp or getpass.getpass(f"mot de passe SSH de {resumer.MAC_USER}@{resumer.MAC_IP} : ")
        client = resumer.ssh_ouvrir(mot_de_passe)
        try:
            resumer.preparer_mac(client)
        finally:
            client.close()

    print(f"[pc] modèle : {MODELE} via {PONT}  |  projet : {projet}")
    print("[pc] Mac éteint = la session plante, pas de bascule vers Anthropic. Compter des minutes par tour.")
    print()
    try:
        return subprocess.call(commande_claude(reste), env=environnement_qwen(os.environ), cwd=str(projet))
    except FileNotFoundError:
        print("[pc] claude introuvable dans le PATH (attendu : C:/Users/<vous>/.local/bin/claude.exe)")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
