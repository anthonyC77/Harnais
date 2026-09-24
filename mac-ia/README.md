# mac-ia

Ce qui tourne sur le Mac Studio pour servir trois usages — **code**, **second
cerveau**, **chat VR vocal** — au-dessus de LM Studio.

Le plan complet est dans
`~/.claude/plans/je-veux-piloter-hermes-humble-raven.md`. Les cinq verrous du
montage réseau sont dans `oneiros/LIAISON_HERMES_MAC.md` — à lire **avant** de
diagnostiquer quoi que ce soit qui ressemble à une panne de liaison.

## La règle qui explique la forme du dépôt

**Tout est en stdlib, sauf `voice/`.**

Le Mac n'a pas de route par défaut : IPv4 vidée, IPv6 désactivé, DNS vide. C'est
voulu — c'est ce qui protège le corpus. Conséquence directe : `pip install` n'y
fonctionne pas. Un composant avec des dépendances ne pourrait donc pas y être
réparé sans rouvrir la machine, c'est-à-dire précisément le jour où on en a le
plus besoin.

Une seule brique a réellement besoin du réseau (`voice/`), donc **une seule
fenêtre d'installation** — procédure au §4.5 du plan, avec sa vérification de
refermeture. Le reste s'installe, se répare et se diagnostique hors ligne, pour
toujours.

## État

| Composant | État | Preuve |
|---|---|---|
| `router/` — résidence des modèles | **fait** | 3 bascules successives → 1 instance, sans suffixe |
| `bridge/` — Anthropic ↔ OpenAI | **fait** | 52/52 + 4 (battement), dont tool calling live en streaming *et* non-streaming |
| `agent_qwen.py` — Claude Code piloté par Qwen | **fait** | 15 tests hors ligne ; palier live à mesurer (durée du premier tour) |
| `brain/` — second cerveau | non commencé | bloqué en amont : vault, nom du sas, port 22 |
| `voice/` — chat VR vocal | non commencé | demande la fenêtre d'installation |

## router — un profil à la fois

```bash
python3 router/profiles.py status
python3 router/profiles.py switch code
python3 router/profiles.py serve        # HTTP sur 127.0.0.1:8080
```

Les clés de modèle dans `router/profiles.json` sont des **placeholders**.
Relevez les vraies avec `lms ls --json` avant la première bascule.

**Ce que le routeur achète.** `lms load` ne reprend pas une instance déjà
résidente : il en empile une seconde, la seconde prend le suffixe `…:2`, et
c'est la *première* qui garde le TTL. Une heure plus tard le TTL tombe,
l'instance au nom propre disparaît, et `model.default` ne correspond plus à
rien — sans que rien n'ait été touché (`LIAISON_HERMES_MAC.md` §4.5).

La procédure documentée décharge d'abord puis vérifie `lms ps`. Le routeur fait
ça, plus une chose que la procédure ne fait pas : il passe un `--identifier`
explicite. L'identifiant cesse d'être ce que le catalogue a bien voulu produire
et devient un nom **choisi**, par profil. Un `model.default: code` survit donc à
un re-téléchargement, une re-quantisation ou un renommage en amont.

La détection est gardée quand même : forcer l'identifiant rend la collision
bruyante au lieu de l'empêcher — si quelque chose tient déjà le nom, LM Studio
renvoie `code:2` et la bascule **échoue**, au lieu de réussir puis de pourrir
une heure plus tard.

**Couplage avec Hermes.** Hermes porte un `model.default` figé. Basculer sous
ses pieds lui renvoie `model not found`, pas une erreur réseau — c'est la
première chose à regarder quand il tombe sans raison. Le garde-fou lit
`~/.mac-ia/hermes.hold` ; **rien ne crée encore ce fichier**, c'est le point
d'accroche pour quand `hermes.cmd` sera mis à jour. D'ici là le garde est inerte
par construction, pas par accident.

**Sécurité.** `:1234` ne transporte que des tokens, d'où l'absence
d'authentification. `:8080` est différent : il charge des modèles arbitraires.
D'où le bind sur `127.0.0.1` par défaut, à atteindre par SSH quand le plan de
contrôle sera posé. Le serveur avertit sur stderr s'il est bindé ailleurs.

## bridge — un endpoint Anthropic devant un runtime OpenAI

```bash
python3 bridge/server.py                       # 0.0.0.0:1235 -> 127.0.0.1:1234/v1
python3 tests/test_bridge.py                   # blocs 1-4, aucun modèle requis
python3 tests/test_bridge.py --live            # + bloc 5, pile complète
python3 tests/test_bridge_server.py            # le battement, aucun modèle requis
```

**Le pont tourne sur le Mac, mais ce dépôt est sur le PC.** Le Mac n'a pas
Internet, il a le réseau local et SSH. Donc, depuis le PC, une copie à
chaque fois que `bridge/` change, puis un lancement à distance :

```bash
scp -r D:/HorusCoachIA/harnais/mac-ia/bridge anthonychassier@192.168.1.50:~/mac-ia/
ssh anthonychassier@192.168.1.50 "pkill -f bridge/server.py; cd ~/mac-ia && nohup python3 bridge/server.py > bridge.log 2>&1 < /dev/null &"
curl http://192.168.1.50:1235/health           # {"ok": true, ...}
```

Le `nohup … &` rend la main tout de suite et le pont survit à la fermeture du
terminal ; ses lignes vont dans `~/mac-ia/bridge.log` sur le Mac. Le `pkill`
arrête le pont précédent, sinon le port 1235 est pris.

**Le battement.** Pendant que le modèle relit le prompt puis réfléchit, LM
Studio n'émet rien qui se traduise en texte. Un client qui ne reçoit aucun
octet pendant cinq minutes coupe et relance (Claude Code), et la relance fait
la queue derrière la génération qu'il vient d'abandonner. Le pont ouvre donc
le message dès que LM Studio a accepté la requête, puis envoie un événement
`ping` toutes les 15 s de silence (`MAC_IA_KEEPALIVE`). Le format Anthropic
prévoit cet événement, les clients l'ignorent. `tests/test_bridge_server.py`
le couvre, sans modèle.

Puis, côté client :

```bash
ANTHROPIC_BASE_URL=http://192.168.1.50:1235
```

**Le problème.** LM Studio parle OpenAI (`/v1/chat/completions`). Le Claude
Agent SDK et le harnais Claude Code parlent Anthropic (`/v1/messages`). Deux
dialectes de la même idée ; il manquait le traducteur.

**Là où passe le travail.** Le non-streaming est une transformation de
dictionnaires. Le streaming, non : OpenAI émet des **deltas plats** sans début
ni fin, Anthropic exige des **blocs encadrés** — chaque contenu ouvert par
`content_block_start`, fermé par `content_block_stop`, avec le bon index. Le
pont doit donc *inventer* un cadrage qu'OpenAI n'envoie jamais. Un client qui
reçoit un delta pour un bloc dont on ne lui a pas annoncé l'ouverture perd le
contenu ou casse. C'est `StreamTranslator`, et c'est là qu'il faut des tests.

**Ce qu'il ne fait pas, exprès.** Pas d'authentification : il est sur le même
LAN de confiance que `:1234` et hérite de cette posture au lieu d'en inventer
une autre. Et il n'invente pas de capacités — `thinking`, `cache_control` et
`output_config` sont **jetés**, pas émulés. Un appelant qui en dépend les voit
manquer, plutôt que de recevoir une imitation crédible.

### Ce que les tests prouvent, et où ils disent de s'arrêter

Blocs 1–4 : traduction pure, aucun modèle, aucun réseau. Bloc 5 : la pile
entière, **sauté** et non échoué si elle n'est pas debout.

C'est là tout l'intérêt du découpage. Un échec en 1–4 est un bug **ici**. Un
échec en 5 avec 1–4 au vert est un bug dans l'**environnement** — runtime,
modèle, Context Length, KV quantisation — et il n'y a aucune raison de relire la
traduction.

## agent — Claude Code piloté par Qwen

```powershell
C:\Python311\python.exe agent_qwen.py                 # dans le projet courant
C:\Python311\python.exe agent_qwen.py -- --continue   # tout ce qui suit -- va à claude
python tests/test_agent_qwen.py                       # 15 tests, aucun Mac requis
```

**Ce que c'est.** Claude Code reste sur le PC : il lit, écrit, lance des
commandes dans le projet. Seule l'adresse du modèle change : `ANTHROPIC_BASE_URL`
pointe vers le pont, qui traduit vers LM Studio. Le stagiaire ne bouge pas, on
change le numéro du senior qu'il appelle.

**Ce que le lanceur vérifie avant d'ouvrir `claude`, et pourquoi.** Il n'y a
**aucune bascule automatique** : Mac éteint, la session plante au premier tour,
elle ne repasse pas chez Anthropic. Donc, dans l'ordre : le pont répond sur
`/health` (sinon diagnostic en une ligne et code 2, `claude` n'est pas lancé),
puis `brain` est résident (même chemin que `resumer.py` : HTTP, SSH seulement
si besoin). Le pont passe le nom de modèle **tel quel** à LM Studio, donc le
lanceur épingle `brain` sur tous les alias (`ANTHROPIC_MODEL`,
`ANTHROPIC_DEFAULT_*_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL`) — sans ça LM Studio
reçoit `claude-sonnet-…`. Il pose aussi un `ANTHROPIC_AUTH_TOKEN` factice :
le pont n'authentifie pas, et c'est ce qui empêche le jeton claude.ai de
partir sur le LAN. Une vraie `ANTHROPIC_API_KEY` du shell est retirée.

**Choisir Qwen ou Anthropic dans VS Code.** Deux profils de terminal au niveau
utilisateur (`%APPDATA%\Code\User\settings.json`,
`terminal.integrated.profiles.windows`) : « Claude · Anthropic » lance `claude`
nu, « Claude · Qwen (Mac) » lance `agent_qwen.py`. Menu « + » du terminal,
l'un ou l'autre, dans le dossier du projet ouvert. Deux terminaux, deux
numéros ; le panneau de l'extension Claude Code reste sur Anthropic, son seul
réglage d'environnement est global. Hors VS Code : `Lancer Qwen agent.bat`.

**Ce qu'il faut savoir avant de s'en servir.** `brain` réfléchit avant chaque
réponse et le prompt système de Claude Code fait plusieurs milliers de tokens
à relire à chaque tour : compter des minutes par tour, pas des secondes. Et
`brain` est chargé à 65 536 tokens de contexte alors que Claude Code compacte en
supposant 200k : sur une longue session, c'est LM Studio qui déborde, et la
troncature casse le tool calling (`LIAISON_HERMES_MAC.md` §5.2). Parade :
`/compact` tôt. Le pont jette `thinking`, `cache_control` et `output_config`,
c'est voulu ; le lanceur pose `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` et
`CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING` pour ne pas les envoyer. Enfin il
porte `CLAUDE_STREAM_IDLE_TIMEOUT_MS` et `API_TIMEOUT_MS` à 30 minutes : sans
ça, Claude Code coupe un tour muet au bout de 5 minutes et le relance, et la
relance fait la queue derrière la génération abandonnée (« will retry in
2m »). LM Studio ne sert qu'une requête à la fois par modèle : le chat web
(`qwen_web.py`) et une session Claude Code se font attendre l'un l'autre.

## Diagnostic

| Symptôme | Couche | La commande qui tranche |
|---|---|---|
| Hermes : `model not found`, sans rien avoir touché | profil basculé sous ses pieds | `python3 router/profiles.py status` |
| `model not found` une heure après le démarrage | double instance `…:2` (§4.5) | `lms ps --json` |
| Claude Code : `connexion refusée` vers `:1235` au premier tour | pont non lancé, ou Mac éteint | `agent_qwen.py` le dit avant d'ouvrir `claude` ; sinon `ping 192.168.1.50` |
| Claude Code : « Waiting for API response · will retry in 2m » | flux muet > 5 min (pont sans battement ou lanceur sans délais), ou modèle occupé par une autre requête | `curl` un `/v1/messages` minuscule : plus de 30 s pour un « OK », c'est la queue |
| Le chat web ou Claude Code rament sans raison | file de requêtes fantômes sur LM Studio (session coupée) | bouton « Couper la file » de `qwen_web.py`, ou `curl` minuscule sur `/v1/chat/completions` : plus d'une seconde pour un « OK », c'est la queue |
| Claude Code : `model not found` | `brain` non résident, ou profil basculé sous ses pieds | `python3 router/profiles.py status` |
| Le pont renvoie du texte au lieu d'un `tool_use` | traduction, ou modèle sans tool calling | `tests/test_bridge.py` bloc 4, puis `--live` |
| Le client attend indéfiniment en streaming | message jamais fermé | vérifier que `message_stop` est émis |
| `pip install` échoue sur le Mac | c'est normal — machine hors ligne | `route -n get default` |
