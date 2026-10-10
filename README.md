# Harnais

**En bref.** L'outillage commun à mes projets Claude Code : des agents (testeur, codeur, relecteur), des gardes qui bloquent les actions dangereuses, des skills de méthode et des oracles d'évaluation. Un script le pose dans un projet, puis signale toute dérive entre les copies.

Comme un harnais d'escalade : il ne grimpe pas à la place de l'agent, il l'empêche de tomber.

Écrit avec Claude Code. Détail complet du raisonnement : [LISEZ-MOI.md](LISEZ-MOI.md).

## Ce qu'il contient

| Dossier | Rôle |
|---|---|
| `claude/agents/` | testeur, codeur, relecteur |
| `claude/hooks/` | trois gardes, en shell et en PowerShell, vérifiées par 28 sondes (`test_hooks.py`) |
| `claude/skills/` | cadrer, livrer, état, capitaliser |
| `eval/` | oracles d'évaluation en Python standard, contrat de run, jeu d'essai pour la CI |
| `modele/` | ce qu'un projet copie une fois puis adapte : jeux d'évaluation, politiques, règles par langage |
| `mac-ia/` | l'infrastructure du modèle local, voir plus bas |

## Poser le harnais

```powershell
python3 harnais.py installer --projet ..\coachingia --hooks ps1
python3 harnais.py verifier  --projet ..\coachingia
python3 harnais.py etat
```

Codes de sortie : `0` rien n'a dérivé, `1` un fichier du noyau diffère, `2` erreur.

## Deux règles

- Une action dangereuse empêchée seulement par le prompt n'est pas empêchée. Chaque garde a ses sondes dans `test_hooks.py`.
- L'évaluation ne passe jamais par un agent du système évalué. Le juge tourne à part, sur un Qwen local, en dialecte OpenAI.

Ces sondes ont déjà servi. Dans Oneiros, deux gardes enregistrées avec des fins de ligne Windows bloquaient tout depuis le premier commit, et 15 sondes sur 28 le signalaient. Un `.gitattributes` empêche désormais que ça revienne.

## Le harnais apprend

À la fin de chaque session, des hooks écrivent une passation que la session suivante relit. Chaque semaine, `eval/mesurer_sessions.py` calcule six signaux sans LLM : coût par résultat accepté, temps jusqu'au résultat fiable, corrections répétées, taux d'escalade humaine, part couverte par des tests, taux de redécouverte. Il sort en code `1` si l'un d'eux se dégrade.

`eval/extraire_candidats.py` fait proposer à Qwen des leçons tirées des sessions. Rien n'est adopté sans un humain : la skill `/capitaliser` promeut ou rejette chaque candidat, sous forme de doc, de skill, de test, de hook ou de code.

## mac-ia : le modèle local

[mac-ia](mac-ia/README.md) regroupe ce qui tourne sur un Mac Studio sans accès Internet, au-dessus de LM Studio.

- `bridge/` : un point d'entrée Anthropic devant un runtime OpenAI, pour que Claude Code parle à Qwen. 52 tests sur 52, appels d'outils compris.
- `agent_qwen.py` : Claude Code piloté par Qwen. 15 tests hors ligne ; le temps du premier tour reste à mesurer.
- `router/` : un modèle résident par profil, avec un identifiant choisi plutôt que celui du catalogue.
- `qwen_web.py` : une interface de chat locale ; la dictée est transcrite sur le PC par Whisper.

L'état de chaque composant est tenu à jour dans [mac-ia/README.md](mac-ia/README.md).
