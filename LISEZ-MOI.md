# harnais — la source unique

Ce dépôt est l'outillage : agents, gardes, skills de méthode, oracles
d'évaluation. Il a existé pendant un temps en trois exemplaires — dans
`OlfactoCoachingProject/harnais/`, dans `CoachingIA/` et dans `HermesAnt/` —
renommés d'une copie à l'autre mais par ailleurs **identiques**. Le contrat de
run, les contrats d'outils et la politique ne différaient que par un nom.

Trois copies ne sont pas un problème en soi. Trois copies dont on ne peut pas
mesurer la dérive en sont un.

## Poser le harnais

```powershell
python3 harnais.py installer --projet ..\coachingia --hooks ps1
python3 harnais.py verifier  --projet ..\coachingia
python3 harnais.py etat
```

`--hooks ps1` sur un poste sans `jq`, `--hooks sh` ailleurs. Ce n'est pas un
détail de confort : **sans `jq`, les trois gardes en shell sortent en code 0**,
c'est-à-dire qu'elles autorisent tout, en silence. C'est la raison pour laquelle
CoachingIA les a réécrites en PowerShell, et les deux versions vivent ici côte à
côte.

Codes de sortie : `0` rien n'a dérivé, `1` au moins un fichier du noyau diffère,
`2` erreur.

## Ce qui est à qui

```
claude/agents/      testeur, codeur, relecteur       → le noyau
claude/hooks/sh/    les trois gardes, shell + jq     → le noyau
claude/hooks/ps1/   les trois gardes, PowerShell     → le noyau
claude/hooks/test_hooks.py   28 sondes sur les gardes → le noyau
claude/skills/      cadrer, livrer, etat, noeuds, largeur, demo → le noyau
eval/*.py           les oracles, stdlib pure          → le noyau
eval/schemas/run_contract.schema.json                 → le noyau
eval/fixtures/      de quoi faire tourner la CI sans serveur → le noyau

modele/             ce qu'un projet copie UNE fois puis fait sien
  eval/golden_set.jsonl, tasks_golden.jsonl, baseline.json
  eval/guardrail_probes.jsonl, eval/policy/agents.json, eval/tasks/
  rules/            les règles par langage, à choisir et à réécrire

exemples/src/Horus.Tools/   « un outil est un type », en trois fichiers
```

**Le noyau se pose, le modèle se copie et s'oublie.** `installer` ne touche
jamais au modèle une fois qu'il est chez vous : ce sont des étalons, et un
étalon distribué depuis un dépôt partagé ne mesure plus rien. La troisième
colonne d'une tâche d'eval doit être signée par quelqu'un du métier — elle ne
peut pas arriver par `git pull`.

## Les deux invariants que ce harnais transporte

> Ce que je ne rends pas impossible, je ne l'ai pas décidé.

Le test des gardes : *une action dangereuse empêchée uniquement par le prompt
n'est pas empêchée.* Se vérifie sur un commit. `test_hooks.py` est l'endroit où
il se vérifie mécaniquement.

> L'évaluation ne passe jamais par un agent du système évalué.

L'eval vit dans son propre déploiement, ne voit que ce qu'un utilisateur
verrait, et si elle a besoin d'un accès privilégié, elle a pris un rang. Le
corollaire dur : la troisième colonne des tâches — « à quoi on reconnaît que
c'est juste » — n'est pas écrite par celui qui code.

Le détail du raisonnement est dans `LIVRABLE.md`.

---

## Qui prend le harnais, qui ne le prend pas

Le harnais ne s'impose pas : il se pose là où il a un référent.

| Projet | Prend | Pourquoi |
|---|---|---|
| **oneiros** | le noyau entier, gardes `sh` | c'est sa maison d'origine ; les oracles y ont un objet à mesurer |
| **coachingia** | **rien pour l'instant** | il n'a ni retrieval ni orchestrateur. Reposer `eval/*.py` à sa racine recréerait la collision `eval/` ↔ `evals/` soldée le 12 septembre, où quatre étapes de CI passaient au vert grâce à des fixtures. Ses agents, gardes et règles sont déjà adaptés — en PowerShell. Sa copie d'archive dort sous `_horus/`. |
| **notes** | rien | ce n'est pas du code |

La question à se poser avant de poser le harnais n'est pas « est-ce que ça
compile ? » mais **« y a-t-il ici quelque chose que cet oracle mesure ? »**. Un
oracle sans objet est un feu vert qui ne veut rien dire.

## Ce que la première pose a révélé

Deux des trois gardes d'oneiros — `guard-etalon.sh` et `guard-paths.sh` —
étaient en **CRLF**, et depuis le commit initial. Sous `sh`, la ligne
`PYTHONIOENCODING=utf-8; export PYTHONIOENCODING\r` interrompt le script : la
garde bloquait alors **tout**, y compris ce qu'elle devait laisser passer. Le
codeur ne pouvait pas écrire dans `src/`.

**15 sondes sur 28 le disaient depuis le début.** Converties en LF, il en reste
3 en échec, toutes nommées d'après des chemins Windows ou l'état réel de
l'utilisateur — à rejuger sur le poste, sous Windows, pas depuis un shell Linux.

C'est le même motif que la garde sans `jq`, et que la CI verte sur des
fixtures : **un garde-fou qui ne s'exécute pas ressemble beaucoup à un
garde-fou.** `.gitattributes` force désormais `*.sh eol=lf` et `*.ps1 eol=crlf`,
pour que ça ne revienne pas par un simple `git checkout` sur Windows.

Note au passage : `installer` a refusé d'écraser les deux fichiers, parce qu'ils
différaient de la source. C'est le comportement voulu — il a fallu `--forcer`.
Un installateur qui écrase sans demander ne vaut pas mieux qu'une copie.
