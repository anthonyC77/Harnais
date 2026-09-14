#!/usr/bin/env python3
"""
Envoie un fichier texte à Qwen (profil `brain`) hébergé par LM Studio sur le Mac.

    python resumer.py fichier.txt                          # résumé, mot de passe demandé si besoin
    python resumer.py fichier.txt --mdp MOTDEPASSE
    python resumer.py fichier.txt --consigne "Transforme ces notes en un exemple de skill Claude Code (SKILL.md)"
    python resumer.py fichier.txt --consigne-fichier consigne.txt --sortie skill.md

Ce que fait le script, dans l'ordre :
  1. HTTP : si `brain` est déjà résident sur le Mac, pas de SSH, pas de mot de passe.
     Sinon SSH (mot de passe) : démarre le serveur LM Studio s'il dort, décharge tout et
     charge `qwen3.8-27b-mlx` sous l'identifiant `brain`.
  2. HTTP direct PC -> Mac (port 1234, dialecte OpenAI) : consigne + texte, récupère la réponse.
  3. Affiche la réponse et l'écrit à côté du fichier source (`<fichier>.<sortie>.txt`, ou --sortie).

Dépendance : pip install paramiko
Les constantes ci-dessous sont celles de router/profiles.json et de LIAISON_HERMES_MAC.md.
"""
import argparse
import getpass
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MAC_IP = "192.168.1.50"
MAC_USER = "anthonychassier"         # compte principal du Mac, celui qui fait tourner LM Studio
PORT = 1234
MODELE_CLE = "qwen3.8-27b-mlx"
IDENTIFIANT = "brain"
CONTEXTE = 65536
# Le profil brain réfléchit toujours et cette réflexion se paie en tokens avant le résumé.
MAX_TOKENS = 16384
TIMEOUT_HTTP = 900

CONSIGNE_DEFAUT = (
    "Fais un résumé synthétique du texte ci-dessous, en français : les idées essentielles, "
    "sans paraphrase, 10 à 15 lignes maximum, en puces si le contenu s'y prête."
)

# lms n'est pas dans le PATH d'un shell SSH non interactif : mêmes candidats que verifier-brain.sh.
TROUVER_LMS = (
    'for c in "$HOME/.lmstudio/bin/lms" "$HOME/.cache/lm-studio/bin/lms"; do '
    '[ -x "$c" ] && { echo "$c"; break; }; done'
)


def ssh_ouvrir(mot_de_passe):
    try:
        import paramiko
    except ImportError:
        sys.exit("paramiko manquant :  pip install paramiko")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(MAC_IP, username=MAC_USER, password=mot_de_passe, timeout=15,
                       look_for_keys=False, allow_agent=False)
    except Exception as exc:  # noqa: BLE001 — on veut le message brut de paramiko
        sys.exit(f"SSH {MAC_USER}@{MAC_IP} refusé : {exc}\n"
                 "Vérifier : Partage > Session à distance activé sur le Mac, MAC_USER en tête du script.")
    return client


def ssh_run(client, commande, timeout=600):
    _, out, err = client.exec_command(commande, timeout=timeout)
    sortie = out.read().decode(errors="replace") + err.read().decode(errors="replace")
    return out.channel.recv_exit_status(), sortie.strip()


def serveur_debout():
    try:
        urllib.request.urlopen(f"http://{MAC_IP}:{PORT}/v1/models", timeout=5)
        return True
    except (urllib.error.URLError, OSError):
        return False


def brain_resident():
    """Vrai si l'identifiant `brain` est chargé, vu depuis le PC — évite le SSH quand tout est déjà en place."""
    try:
        with urllib.request.urlopen(f"http://{MAC_IP}:{PORT}/api/v0/models", timeout=5) as rep:
            modeles = json.load(rep).get("data", [])
    except (urllib.error.URLError, OSError, ValueError):
        return False
    return any(m.get("id") == IDENTIFIANT and m.get("state") == "loaded" for m in modeles)


def preparer_mac(client):
    code, lms = ssh_run(client, TROUVER_LMS, timeout=15)
    if code != 0 or not lms:
        sys.exit("lms introuvable sur le Mac. Ouvrir LM Studio une fois, puis : ~/.lmstudio/bin/lms bootstrap")
    print(f"[mac] lms : {lms}")

    if not serveur_debout():
        print("[mac] serveur LM Studio absent, démarrage sur 0.0.0.0 ...")
        ssh_run(client, f'"{lms}" server start --bind 0.0.0.0', timeout=60)
        for _ in range(10):
            time.sleep(2)
            if serveur_debout():
                break
        else:
            sys.exit(f"le serveur ne répond toujours pas sur {MAC_IP}:{PORT}.\n"
                     "Sur le Mac :  lsof -nP -iTCP:1234 -sTCP:LISTEN   (bind 127.0.0.1 = pas exposé) ; pare-feu macOS.")
    print("[mac] serveur joignable.")

    _, ps = ssh_run(client, f'"{lms}" ps', timeout=30)
    lignes = ps.splitlines()
    resident = any(IDENTIFIANT in l for l in lignes)
    doublon = any(f"{IDENTIFIANT}:" in l for l in lignes)
    if resident and not doublon:
        print(f"[mac] '{IDENTIFIANT}' déjà résident.")
        return

    # Toujours unload --all d'abord : c'est le geste de §4.5 (double instance `:2` qui garde le TTL).
    print(f"[mac] chargement de {MODELE_CLE} -> '{IDENTIFIANT}' (contexte {CONTEXTE}), une à deux minutes ...")
    code, sortie = ssh_run(
        client,
        f'"{lms}" unload --all >/dev/null 2>&1; '
        f'"{lms}" load "{MODELE_CLE}" --identifier "{IDENTIFIANT}" --context-length {CONTEXTE} -y',
        timeout=600,
    )
    if code != 0:
        sys.exit(f"lms load a échoué :\n{sortie}")
    print(f"[mac] '{IDENTIFIANT}' chargé.")


def resumer(texte, consigne=CONSIGNE_DEFAUT):
    corps = json.dumps({
        "model": IDENTIFIANT,
        "messages": [{"role": "user", "content": consigne + "\n\n" + texte}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"http://{MAC_IP}:{PORT}/v1/chat/completions", data=corps,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_HTTP) as rep:
            data = json.load(rep)
    except urllib.error.HTTPError as exc:
        sys.exit(f"HTTP {exc.code} : {exc.read().decode(errors='replace')[:500]}")
    msg = data["choices"][0]["message"]
    contenu = (msg.get("content") or "").strip()
    if not contenu:
        sys.exit("réponse vide : la réflexion a mangé tout le budget. Augmenter MAX_TOKENS.")
    return contenu


def main(argv):
    ap = argparse.ArgumentParser(description="Envoie un fichier texte au profil brain (Qwen sur le Mac).")
    ap.add_argument("fichier", help="fichier texte à traiter")
    ap.add_argument("--mdp", help="mot de passe SSH du Mac (sinon demandé sans écho, et seulement si nécessaire)")
    ap.add_argument("--consigne", help="ce qu'on demande au modèle (défaut : un résumé synthétique)")
    ap.add_argument("--consigne-fichier", help="fichier contenant la consigne (pour une consigne longue)")
    ap.add_argument("--sortie", help="fichier de sortie (défaut : <fichier>.resume.txt ou <fichier>.reponse.txt)")
    args = ap.parse_args(argv[1:])

    fichier = Path(args.fichier)
    if not fichier.is_file():
        sys.exit(f"fichier introuvable : {fichier}")
    if args.consigne_fichier:
        consigne = Path(args.consigne_fichier).read_text(encoding="utf-8").strip()
    else:
        consigne = args.consigne or CONSIGNE_DEFAUT
    suffixe = ".resume.txt" if consigne == CONSIGNE_DEFAUT else ".reponse.txt"
    sortie = Path(args.sortie) if args.sortie else fichier.with_suffix(fichier.suffix + suffixe)

    texte = fichier.read_text(encoding="utf-8", errors="replace")
    print(f"[pc] {fichier.name} : {len(texte.split())} mots")

    if brain_resident():
        print(f"[pc] '{IDENTIFIANT}' déjà résident sur le Mac, pas de SSH.")
    else:
        mot_de_passe = args.mdp or getpass.getpass(f"mot de passe SSH de {MAC_USER}@{MAC_IP} : ")
        client = ssh_ouvrir(mot_de_passe)
        try:
            preparer_mac(client)
        finally:
            client.close()

    print("[pc] envoi à Qwen, patience (le modèle réfléchit avant de répondre, compter plusieurs minutes) ...")
    debut = time.time()
    reponse = resumer(texte, consigne)
    print(f"[pc] réponse en {time.time() - debut:.0f} s\n")

    print(reponse)
    sortie.write_text(reponse + "\n", encoding="utf-8")
    print(f"\n[pc] écrit dans {sortie}")


if __name__ == "__main__":
    main(sys.argv)
