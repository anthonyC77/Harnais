# La boucle d'apprentissage — conception

14 septembre 2026. Fait suite à `D:\HorusCoachIA\RéduireCoutToken.txt` (notes
du 10 septembre) et à `2026-09-12-harnais-partage-design.md`.

## 1. Le constat

Une session Claude Code à 200 $ paie surtout de la **redécouverte** : relire le
dépôt, retrouver les conventions, reconstruire l'état du projet, refaire un
raisonnement déjà fait ailleurs. Réduire le coût d'un trajet — cache, contexte
plus court, modèle plus léger — ne change rien au trajet suivant. Ce que le
harnais ne possède pas, c'est une boucle qui reprend chaque run et le réécrit
sous une forme plus durable et moins chère :

> observer → extraire → classer → promouvoir → vérifier → déprécier

et des signaux qui disent si le système apprend, au lieu d'une facture qui ne
mesure qu'un volume.

> Louez l'intelligence, possédez vos apprentissages.

## 2. Ce qui existe et qu'on ne réécrit pas

- Les oracles du harnais : stdlib pure, codes de sortie 0/1/2, un fichier
  `json` + `md` par cycle (`width_report.py`), validation par
  `jsonschema_lite.py`.
- Un juge hors système : `eval/juge_local.py` parle à Qwen sur le Mac
  (`192.168.1.50:1234`), et `mac-ia/resumer.py` porte le client HTTP.
- Un lecteur défensif des transcripts Claude Code :
  `oneiros/oneiros/src/oneiros/sessions/reader.py` — garde les entrées
  d'outils, saute leurs résultats et les sidechains, ne lève jamais.
- Le transcript porte `message.usage` à chaque tour d'assistant (`input`,
  `cache_creation`, `cache_read`, `output`, `thinking`). **Le coût d'une
  session se calcule sans LLM.**
- La frontière noyau / étalon de `harnais.py` : `NOYAU` se pose, `AU_PROJET`
  ne s'écrase jamais.
- `indexation/SKILL.md` : « un sommaire, pas une encyclopédie ».

## 3. Décisions

1. La boucle vit dans **`harnais/`**, dans le noyau. oneiros, coachingia et les
   chantiers la reçoivent par `harnais.py installer`. oneiros garde sa mémoire
   bornée et son E7 comme implémentation produit ; rien ici n'en dépend.
2. La source observée en premier : **les sessions Claude Code**
   (`~/.claude/projects/<projet>/*.jsonl`). C'est là que part la facture. Les
   runs produit (`run_contract.schema.json`) viendront par un second
   adaptateur, plus tard.
3. **Proposition, humain promeut.** La boucle dépose des candidats datés dans
   une file ; rien n'entre dans `docs/`, `skills/`, `test_hooks.py` ou les
   gardes sans un geste humain. Une mauvaise règle mémorisée industrialise
   l'erreur.
4. Le jugement (« est-ce récurrent, stable, réutilisable ? ») est fait par
   **Qwen local**. Les six signaux restent **déterministes**.

## 4. Architecture

```
session Claude Code ──(Stop, SessionEnd)──▶ .claude/apprentissage/passations/<session>.md
        │                                              ▲ (SessionStart relit la dernière, ≤ 60 lignes)
        ▼
~/.claude/projects/<projet>/*.jsonl
        ├─▶ eval/mesurer_sessions.py   (0 LLM) ─▶ eval/apprentissage/semaine-YYYY-Www.{json,md}
        └─▶ eval/extraire_candidats.py (Qwen)  ─▶ .claude/apprentissage/candidats.jsonl
                                                            │
                                     /capitaliser (humain) : 4 questions, promeut / rejette / épisode
                                                            ▼
                          note · doc (+INDEX.md) · skill · test (test_hooks.py) · hook · code
```

Trois frontières, toutes déjà dans le harnais :

- **Noyau / étalon.** Scripts, schéma, consigne, skill, hooks → `NOYAU`.
  `prix.json`, `seuils.json`, `corrections.txt`, `commandes-test.txt`,
  `candidats.jsonl`, passations et semaines mesurées → `AU_PROJET`. Une grille
  de prix change avec le fournisseur ; un seuil est une décision du projet.
- **L'évaluation ne passe jamais par un agent du système évalué.** Qwen sur le
  Mac, jamais Claude.
- **Ce que je ne rends pas impossible, je ne l'ai pas décidé.** Les scripts
  n'écrivent que sous `.claude/apprentissage/` et `eval/apprentissage/`. La
  promotion est un geste humain dans un skill `disable-model-invocation: true`.

Écarté : index FTS, RAG, promotion automatique, cristallisation en code — elle
arrive d'elle-même quand un candidat `procedure` est promu `code`.

## 5. Les six signaux (`eval/mesurer_sessions.py`, 0 LLM)

Par session, puis agrégés par semaine ISO, avec le delta sur la semaine
précédente. Ce qui est un proxy est dit proxy.

| # | Signal | Calcul | Source |
|---|---|---|---|
| 1 | Coût par résultat accepté | Σ tokens × `prix.json` ÷ résultats acceptés | `message.usage` |
| 2 | Temps jusqu'au résultat fiable | dernier résultat accepté − premier message utilisateur | `timestamp` |
| 3 | Corrections répétées | messages utilisateur courts commençant par un terme de `corrections.txt`, plus ceux qui suivent un `tool_result` en erreur | lexique (proxy) |
| 4 | Taux d'escalade humaine | (`AskUserQuestion` + refus de permission) ÷ tours | `tool_use.name`, attachments |
| 5 | Part couverte par des tests | sessions avec une commande de `commandes-test.txt` ÷ sessions avec Edit/Write | entrées Bash |
| 6 | Taux de redécouverte | fichiers Read/Grep/Glob déjà lus dans ≥ 2 sessions antérieures du projet ÷ fichiers lus ; annexe : top 10 | `tool_use.input` |

**Résultat accepté** : un `git commit` dans les entrées Bash, *ou*
`résultat accepté : oui` dans la passation de la session — la passation prime,
parce que seul l'humain sait ce qui a été réellement accepté.

Codes de sortie : `0` mesuré ; `1` au moins un signal s'est dégradé au-delà de
`seuils.json` — ce n'est pas une panne, c'est « si les métriques ne bougent
pas, le système n'apprend rien » rendu exécutable ; `2` transcript illisible
ou grille de prix absente.

La même passe signale les candidats `promu` dont `valide_jusqua` est passée ou
dont `promu_vers` n'existe plus : ils passent `deprecie`. C'est l'étape six,
celle qu'on oublie.

## 6. Les candidats (`eval/extraire_candidats.py`, Qwen)

**Entrée** : un *digest* par session, pas le transcript — messages utilisateur
intégraux, réponses assistant tronquées à 600 caractères, entrées d'outils
sans résultats, la passation si elle existe. Quelques milliers de tokens.

**Consigne** (`eval/apprentissage/consigne-extraction.md`, noyau) : les quatre
tests de la mémoire opérationnelle — découvrable, vérifiée (pourquoi, quand),
applicable (action, choix, vérification, permission), dépréciable — en
questions fermées. Sortie JSON forcée, `temperature 0`, `max_tokens` bridé,
**un digest par appel** : un budget partagé avec la réflexion rend une réponse
vide (`finish_reason: length`, vu le 13 septembre).

**Un candidat** (`eval/schemas/candidat.schema.json`, `additionalProperties:
false`) :

```json
{"id": "c-2026-W38-007", "session": "48fffefb…", "date": "2026-09-14",
 "type": "fait | regle | procedure | invariant | episode",
 "enonce": "Sans jq, les trois gardes sh sortent en code 0",
 "preuve": "test_hooks.py 15/28 KO puis diagnostic CRLF",
 "recurrence": 2,
 "niveau_propose": "note | doc | skill | test | hook | code",
 "applicable": "action | choix | verification | permission",
 "verifiable_par": "python claude/hooks/test_hooks.py",
 "confiance": 0.8,
 "statut": "propose"}
```

`episode` est la sortie utile pour ce qui n'est vrai qu'une fois : le reste
est mémoire épisodique seulement.

**Dédoublonnage** sans LLM : un énoncé proche d'un candidat existant
incrémente `recurrence` au lieu d'ajouter. Ce compteur répond à « si deux fois,
examen pour promotion ». Une ligne invalide va dans `candidats.rejetes.jsonl`
avec sa raison, jamais perdue en silence.

**Cycle de vie** : `propose` → `promu` (`promu_vers`, `valide_jusqua`) |
`rejete` (`motif`) | `episode` ; puis `deprecie` par `mesurer_sessions.py`.

**Quand** : à la main ou par tâche de nuit — jamais en hook de fin de session,
Qwen prend plusieurs minutes par passe. Mac éteint ⇒ code 2, pas un vert.

## 7. La passation, en deux couches

Un hook ne peut pas demander au modèle d'écrire — sauf par le code 2, le
mécanisme déjà utilisé par `gate-tests.sh`.

- **Couche mécanique**, hook `SessionEnd`, 0 LLM : depuis `transcript_path`,
  fichiers modifiés, commandes de test/build lancées et leur sortie ok/ko,
  coût, `résultat accepté` déduit des commits. Écrit
  `.claude/apprentissage/passations/<session>.md`. Existe toujours, même
  quand la session est fermée brutalement.
- **Couche narrative**, hook `Stop` : si la session a fait ≥ 1 Edit/Write et
  qu'aucune section « Narrative » n'a été écrite depuis ≥ 20 appels d'outils,
  `exit 2` et la consigne en stderr — objectif, état actuel, décisions prises,
  risques restants, prochaines actions, résultat accepté oui/non. Le modèle
  l'écrit, s'arrête à nouveau, le hook sort 0. `stop_hook_active` ⇒ 0.
- Hook `SessionStart` : `additionalContext` = la dernière passation du projet
  (≤ 60 lignes) et « ne relis pas ce qui y est établi ». Coexiste avec
  `session_start_memory.py` d'oneiros.

Les trois hooks en `sh` et `ps1`, avec des sondes dans `test_hooks.py`.

## 8. `/capitaliser`, la revue hebdomadaire

`claude/skills/capitaliser/SKILL.md`, `disable-model-invocation: true`, dans
le style de `etat` :

1. `python eval/mesurer_sessions.py --projet <p>` ; les six signaux et le
   delta. Un code 1 se voit avant tout le reste.
2. Les quatre questions, chacune alimentée par un fichier : *qu'avons-nous
   redécouvert* ← top 10 du signal 6 et candidats `fait` ; *quelles corrections
   se sont répétées* ← `recurrence ≥ 2` ; *que faut-il promouvoir* ← `propose`
   par niveau ; *que faut-il supprimer* ← `deprecie`.
3. Porte humaine **par candidat** : promeut vers `<chemin>`, rejette `<motif>`,
   ou épisode.
4. Le modèle écrit la cible — fragment `docs/` plus sa ligne dans `INDEX.md`,
   `SKILL.md`, sonde dans `test_hooks.py` — et met à jour `statut`,
   `promu_vers`, `valide_jusqua` dans le même geste.
5. Une seule modification de hook ou de garde par cycle.
6. Arrêt : ce qui a été promu, ce qui reste `propose`, la prochaine revue.

## 9. Vérification

- `python -m unittest discover -s eval/tests` : les 17 tests existants plus
  `test_apprentissage.py` sur des transcripts synthétiques aux valeurs connues.
- `python claude/hooks/test_hooks.py` : les 28 sondes plus celles des trois
  hooks, dans les deux langages.
- `harnais.py installer --projet ../oneiros --forcer` puis `verifier` ⇒ 0 ; le
  modèle d'étalon n'est pas posé, l'étalon local n'est pas écrasé.
- Sur les vraies données : `mesurer_sessions.py --projet d--HorusCoachIA`
  retrouve le coût de la session du 12–13 septembre à ±10 % ;
  `extraire_candidats.py` sur cette session produit au moins « CRLF casse les
  gardes sh », dont on connaît la réponse.
- Les hooks en vrai : éditer, laisser s'arrêter, la Narrative est écrite ;
  relancer, la passation est dans le contexte ; fermer, la couche mécanique
  est dans le fichier.
