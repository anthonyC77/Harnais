# Un harnais pour deux produits — conception

12 septembre 2026. Fait suite à `DECISION.md` (le classeur) et à
`coachingia/docs/ruche-et-le-harnais.md` (l'absorption de Ruche).

## 1. Le but

Le harnais doit servir **oneiros** et **coachingia** de la même façon, et
donner trois choses à celui qui les développe :

1. **Piloter le LLM local** — Qwen sur le Mac Studio — depuis n'importe quel
   endroit du harnais qui a besoin d'un modèle : les agents Claude Code, le
   `claude -p` de coachingia, le juge des évals.
2. **Tester le coach** sur ses propres sessions de travail, y compris celles
   produites en travaillant sur oneiros.
3. **Voir les évals** dans Ruche, le lecteur 3D, sans que Ruche dépende de
   l'un des deux produits.

Ce que le diagnostic a montré : chacun des trois souhaits a déjà sa couture.
Le pont `mac-ia` expose un endpoint Anthropic ; coachingia lit déjà toutes les
sessions de `~/.claude/projects` ; Ruche lit déjà un flux d'événements. Ce qui
manque tient en **deux déplacements, un schéma et trois scripts**. Le reste est
de la discipline déjà écrite.

## 2. Le principe, inchangé

> L'outil qui mesure est générique, l'étalon qu'il lit appartient à ce qu'il
> mesure.

Le harnais possède **les contrats** (ce qu'est un run, ce qu'est un
événement, ce qu'est un verdict), **l'outil qui mesure** (les oracles) et
**l'infrastructure de modèle local** (le routeur et le pont). Les produits
possèdent leurs étalons — golden sets, `evals/cas/`, `verdict.json` — et les
produisent eux-mêmes. Ruche possède le rendu, et rien d'autre.

Trois choses restent interdites, et cette conception n'en franchit aucune :

- Poser le noyau du harnais dans coachingia. Il n'y a là rien que ses oracles
  mesurent ; la décision du 12 septembre tient.
- Fusionner les dépôts. Le classeur a été choisi contre le monorepo, pour des
  raisons qui n'ont pas changé.
- Faire tirer un verdict d'éval depuis les spans d'observabilité. La ruche lit
  les internes, l'éval non. Le jour où une campagne lit le journal de spans, le
  juge a pris un rang.

## 3. L'arborescence cible

```
HorusCoachIA/
  harnais/                                   dépôt : l'outillage
    eval/
      schemas/run_contract.schema.json       le run RÉSUMÉ, pour juger         (existe)
      schemas/run_events.schema.json         le run en ÉVÉNEMENTS, pour voir    NOUVEAU
      schemas/verdicts.schema.json           une ligne de verdict par cas      NOUVEAU
      plier_evenements.py                    événements → runs résumés          NOUVEAU, stdlib
      deplier_runs.py                        runs résumés → événements          NOUVEAU, stdlib
      juge_local.py                          --judge-cmd qui appelle le Mac     NOUVEAU, stdlib
      tests/test_eval.py                     + les tests des trois scripts
    mac-ia/                                  routeur + pont + brain             DÉPLACÉ depuis oneiros/
    modele/                                  inchangé
    harnais.py                               NOYAU : + les trois scripts et les deux schémas
  ruche/                                     dépôt : le lecteur 3D              DÉPLACÉ depuis coachingia/web/ruche
  oneiros/                                   dépôt : moins mac-ia/
  coachingia/                                dépôt : moins web/ruche/
  notes/ruche/                               archive, ne bouge pas
```

Ce qui entre dans `NOYAU` (donc se pose dans un projet par `installer`) : les
trois scripts et les deux schémas. Ce qui n'y entre pas : `mac-ia/`, qui se
lance depuis le harnais et ne se copie nulle part — c'est de l'infrastructure,
pas de l'outillage de projet.

## 4. Les trois contrats

### 4.1 Le run résumé — `run_contract.schema.json`

Existe, version `1.0`, `additionalProperties: false`. C'est ce que lisent
`run_tasks_eval.py` et `width_report.py`. **Il ne change pas.**

### 4.2 Le run en événements — `run_events.schema.json`

Nouveau. C'est la traduction en JSON Schema des types `RunFile` et `RunEvent`
de `ruche/src/core/events.ts`. Le schéma devient la **source** ; `events.ts`
en devient le miroir, vérifié par un test.

**Un fichier = une ligne d'en-tête, puis une ligne par événement.** C'est la
forme que `parseJsonl` lit déjà dans Ruche.

L'en-tête :

| Champ | Type | Sens |
|---|---|---|
| `contract_version` | entier, `1` | version du contrat |
| `run_id` | chaîne | identifiant du run, repris par chaque événement dans `run` |
| `task_id` | chaîne | le cas du golden set, ou le nom de la tâche |
| `agents` | tableau de `{id, role, depth}` | les acteurs déclarés ; `depth` −1 pour l'humain |
| `policy` | objet | **la même forme que `policy` du contrat de run** (§4.1) : `agent`, `allowed_tools`, `quotas`, `identity` ; `quotas` accepte en plus `max_calls_par_agent`, que les détecteurs de Ruche utilisent |

Aligner la `policy` de l'en-tête sur celle du contrat de run est le seul
changement imposé à Ruche par cette spec : aujourd'hui son `RunPolicy` n'a
ni `identity` ni `max_calls`, et `demo-run.jsonl` non plus. C'est ce qui
permet à `plier_evenements.py` de recopier la `policy` sans l'inventer. Le
contrat de run ne ferme pas `quotas` aux champs inconnus, `max_calls_par_agent`
y passe donc tel quel.

Les événements. Enveloppe commune :

| Champ | Type | Sens |
|---|---|---|
| `v` | entier, `1` | version du contrat |
| `seq` | entier ≥ 0 | ordre logique : part de 0 et avance de 1 à chaque ligne, sans trou |
| `t` | nombre | horloge vécue, en millisecondes depuis le début du run |
| `run` | chaîne | identifiant du run |
| `actor` | chaîne | identifiant de l'agent qui émet |
| `origin` | `observed` \| `derived` \| `human` | observé, recalculable, ou geste humain |
| `ref` | chaîne, optionnel | empreinte du contenu volumineux, stocké hors journal |
| `cost` | objet partiel, optionnel | `calls`, `tok_in`, `tok_out`, `eur` |

Dix-sept genres (`kind`), repris tels quels d'`events.ts` : `run.start`,
`run.end`, `agent.spawn`, `agent.end`, `agent.stop.attempt`, `think.start`,
`think.end`, `tool.start`, `tool.end`, `hook.allow`, `hook.deny`,
`wait.start`, `wait.end`, `msg`, `human`, `flag`, `flag.clear`. Chaque genre
porte les champs qu'`events.ts` lui donne aujourd'hui ; la spec ne les
réinvente pas, elle les fige.

Deux règles portées par le schéma et non par la discipline :

- `seq` est contigu à partir de 0. Un trou rend le fichier invalide, pas
  « à trier » : c'est l'invariant qu'`assertWellFormed` vérifie déjà dans
  Ruche, et que le harnais vérifie désormais du même côté que les oracles.
- Le premier événement d'un run est `run.start`, le dernier `run.end`. Un
  fichier tronqué se voit.

Le JSON Schema ne sait exprimer ni la contiguïté de `seq` ni l'ordre des
lignes : ces deux règles vivent dans une fonction `verifier_evenements()` de
`plier_evenements.py`, appelée par les deux scripts et testée à part. Le
reste (champs, types, genres) passe par `jsonschema_lite.py`, comme les
autres contrats.

### 4.3 Les verdicts — `verdicts.schema.json`

Nouveau, mais le format existe déjà : c'est celui de
`eval/fixtures/judge.jsonl`.

```json
{"task_id": "T-03", "pass": false, "reason": "la source de la raison n'est pas indiquée"}
```

`task_id` identifie le cas ; `pass` est binaire ; `reason` est obligatoire et
non vide — un verdict sans explication ne se conteste pas, règle déjà écrite
dans `modele/rules/evals.md`. C'est le seul format que Ruche accepte en
`?eval=`. Le `verdict.json` de coachingia s'y projette en quelques lignes, du
côté de coachingia, quand il en aura l'usage.

## 5. Les composants

Pour chacun : ce qu'il fait, comment on s'en sert, de quoi il dépend.

### 5.1 `eval/juge_local.py` — le juge hors système

**Ce qu'il fait.** Implémente le contrat `--judge-cmd` de
`run_tasks_eval.py` : lit `{"task", "run", "rubric"}` sur stdin, écrit
`{"pass", "reason"}` sur stdout, code 0. Il appelle LM Studio sur le Mac,
directement en dialecte OpenAI (`/v1/chat/completions`), sans passer par le
pont : le juge n'a pas besoin du dialecte Anthropic, et un intermédiaire de
moins est une panne de moins.

**Pourquoi Qwen est le bon juge.** L'invariant du harnais dit que l'éval ne
passe jamais par un agent du système évalué. Un modèle sur une machine hors
ligne, qui ne partage ni code ni prompt avec oneiros ou coachingia, est
extérieur par construction.

**Comment on s'en sert.**

```
python3 eval/run_tasks_eval.py --runs eval/fixtures/runs_tasks.jsonl \
    --judge-cmd "python3 eval/juge_local.py"
```

**Configuration**, par variables d'environnement, avec défauts :

| Variable | Défaut | Sens |
|---|---|---|
| `HARNAIS_JUGE_URL` | `http://192.168.1.50:1234/v1` | LM Studio, dialecte OpenAI |
| `HARNAIS_JUGE_MODELE` | `brain` | l'identifiant forcé par le routeur, pas la clé du catalogue |
| `HARNAIS_JUGE_TIMEOUT` | `120` | secondes ; le profil `brain` réfléchit et ne se coupe pas |

**Le prompt.** Système : le rôle de juge, la consigne de répondre par un JSON
`{"pass": bool, "reason": str}` et rien d'autre. Utilisateur : la rubrique,
l'entrée du run, la sortie du run, les outils appelés (nom, `ok`, sans les
sorties volumineuses). Le juge ne reçoit **jamais** le golden complet — pas la
sortie attendue — sinon il compare au lieu de juger.

**Erreurs.** Le contrat `--judge-cmd` n'a que deux issues : un JSON valide
ou un code non nul. Sur Mac injoignable, timeout, réponse non JSON ou
`max_tokens` atteint avant le JSON : code 2, message sur stderr. Le modèle à
réflexion produit du texte avant le JSON : le script extrait le dernier objet
JSON de la réponse, et échoue si aucun n'est trouvé.

**Ce que la campagne en fait — et ce qui change dans `run_tasks_eval.py`.**
Aujourd'hui, un juge qui sort en code non nul interrompt toute la campagne
avec le code 2, « rien mesuré ». C'est honnête mais brutal : un seul timeout
sur dix cas jette les neuf autres. La spec demande la correction minimale :
l'erreur est attrapée **par cas**, le cas prend `judge_pass: null` et la
raison de la panne dans `judge_reason`, la ligne part sur stderr, et le
rapport porte un compteur `judge_errors`. La campagne ne sort en 2 que si le
juge a été demandé et qu'**aucun** cas n'a reçu de verdict. **Une panne du
juge n'est jamais un `pass: false`** : une coupure n'est pas une régression,
règle déjà écrite dans coachingia. Le script tolère déjà les verdicts absents
(un `--judge-file` ne couvre pas forcément chaque tâche) : le changement
tient dans le bloc `try` de la boucle et dans une ligne du rapport.

**Dépend de.** stdlib (`urllib`, `json`). Du Mac allumé, avec le profil
`brain` résident (`mac-ia/router/profiles.py status`).

### 5.2 `eval/plier_evenements.py` — événements → runs résumés

**Ce qu'il fait.** Lit un ou plusieurs fichiers `*.events.jsonl`, écrit un
`runs.jsonl` conforme à `run_contract.schema.json`, un run par fichier. C'est
la réduction qui permet de juger ce qu'on a vu.

**La correspondance**, fixée ici :

| Contrat de run | Source dans le fichier d'événements |
|---|---|
| `contract_version` | `"1.0"`, constante |
| `run_id` | en-tête `run_id` |
| `task_id` | en-tête `task_id` |
| `status` | `run.end.status` |
| `input.message` | `run.start.title` ; `context_tokens` absent si non porté |
| `output.text` | vide par défaut — le texte final est du contenu, il voyage par `ref`, pas dans le journal |
| `tool_calls[]` | une paire `tool.start` / `tool.end` du même `actor`, appariée par ordre ; `tool`, `ok`, `latency_ms` = `ms` ; `input` = `{"args": …}` ; `output` = `out` ou `null` |
| `cost` | `run.end.totals`, renommé (`tok_in` → `tokens_in`, etc.) |
| `policy` | en-tête `policy`, recopié tel quel — d'où l'alignement demandé en §4.2 |
| `human_interventions` | `run.end.totals.human_interventions` |
| `provenance` | `[]` — non dérivable des événements |
| `cancelled` | `true` si `status` vaut `cancelled` |

**Ce qu'il refuse.** Un fichier sans en-tête, sans `run.start` ou sans
`run.end`, ou dont `seq` a un trou : code 2, nom du fichier sur stderr, via
`verifier_evenements()` (§4.2). Un `tool.start` sans `tool.end` : la paire devient
un `tool_calls[]` avec `ok: false` et sans `latency_ms` — un outil jamais
revenu est un fait, pas une erreur de format.

**Comment on s'en sert.**

```
python3 eval/plier_evenements.py runs/*.events.jsonl --out runs.jsonl
python3 eval/run_tasks_eval.py --runs runs.jsonl --judge-cmd "python3 eval/juge_local.py"
```

**Dépend de.** stdlib, `jsonschema_lite.py` pour valider la sortie avant de
l'écrire. Un run plié qui ne passe pas le contrat n'est pas écrit.

### 5.3 `eval/deplier_runs.py` — runs résumés → événements

**Ce qu'il fait.** L'inverse, en moins riche : d'un `runs.jsonl` conforme au
contrat, produit un `*.events.jsonl` par run, pour regarder dans Ruche ce que
les oracles ont jugé — y compris les fixtures, sans attendre une session
réelle.

**La projection**, minimale et déterministe : l'en-tête (`run_id`,
`task_id`, `contract_version: 1`, `policy` recopiée, `agents` réduit à un
seul acteur `{id: policy.agent, role: policy.agent, depth: 0}`), puis
`run.start` (`t = 0`), puis pour chaque `tool_calls[i]` un `tool.start` et un
`tool.end` séparés de `latency_ms`, puis `run.end` à `t = cost.wall_clock_ms`.
`origin: observed` partout. Ce n'est pas une trace, c'est une silhouette ; le
fichier le dit dans un champ `ref` sur `run.start` valant `deplie:<run_id>`.

**L'invariant à tester.** `plier(deplier(runs)) == runs` sur les champs que
la projection transporte (`run_id`, `task_id`, `status`, `tool_calls[].tool`,
`tool_calls[].ok`, `cost`, `policy`, `human_interventions`). C'est le test qui
dit que les deux scripts parlent du même objet.

**Dépend de.** stdlib, `jsonschema_lite.py`.

### 5.4 `mac-ia/` — déplacé, pas réécrit

**Ce qui bouge.** Les dix fichiers suivis de `oneiros/mac-ia/` vont dans
`harnais/mac-ia/`, avec `git mv` côté oneiros puis ajout côté harnais.
L'historique reste dans oneiros ; le harnais reçoit l'état, et le commit de
chaque côté cite l'autre.

**Ce qui ne change pas.** Le code. La règle « tout est en stdlib » y est déjà
celle du harnais. Les tests (`tests/test_bridge.py`, blocs 1 à 4 hors ligne)
passent avant et après le déplacement — c'est le critère.

**Ce qui est corrigé au passage**, et seulement ça : les chemins dans les
documents. `oneiros/CLAUDE.md` et `oneiros/oneiros/LIAISON_HERMES_MAC.md`
pointent vers `mac-ia/` ; ils pointeront vers `../harnais/mac-ia/`. Le
`README.md` de mac-ia cite un plan sous `~/.claude/plans/` : inchangé.

**Comment on pilote Qwen, une fois posé.** Trois usages, une couture chacune :

| Usage | Couture | Ce qu'il y a à faire |
|---|---|---|
| Les agents Claude Code du harnais (codeur, testeur, relecteur) | `ANTHROPIC_BASE_URL=http://192.168.1.50:1235` vers le pont | poser la variable avant `claude` |
| `claude -p` dans coachingia (`evaluer --juge`, `PromptCritic`) | la même variable | rien d'autre : `ClaudeCli.cs` lance `claude -p`, qui la lit |
| Le juge des évals du harnais | `juge_local.py` vers `:1234` | §5.1 |

Le profil actif se bascule avec `python3 mac-ia/router/profiles.py switch
brain`. Le pont jette `thinking`, `cache_control` et `output_config` : un
agent qui en dépend les voit manquer, c'est voulu et documenté dans mac-ia.

### 5.5 `ruche/` — dépôt frère

**Ce qui bouge.** `coachingia/web/ruche/` (non suivi par git, donc sans
perte) devient `HorusCoachIA/ruche/`, dépôt à lui seul. `notes/ruche/` reste
en archive. Le `README.md` de Ruche et `ruche-et-le-harnais.md` §3 sont mis à
jour : Ruche ne perd plus « sa moitié basse » au profit de coachingia, elle
n'en a simplement pas — elle lit le contrat du harnais, et chaque producteur
l'écrit.

**Ce que Ruche gagne**, quatre choses et quatre seulement :

0. **La `policy` alignée** (§4.2) : `RunPolicy` dans `events.ts` prend la
   forme du contrat de run, `demo-run.jsonl` et `make-demo-trace.mjs`
   suivent. Les détecteurs continuent de lire `quotas.max_calls_par_agent`.
1. **Le test de concordance.** `test/contrat.test.ts` lit
   `../harnais/eval/schemas/run_events.schema.json` et échoue si la liste des
   `kind` d'`events.ts` diffère de celle du schéma, dans un sens ou dans
   l'autre, ou si `demo-run.jsonl` ne passe pas le schéma. Le chemin relatif vers le harnais est une constante en tête du
   test, et le test est **sauté avec un message**, pas en échec, si le harnais
   n'est pas à côté — Ruche doit rester clonable seule.
2. **`?eval=<chemin>`** à côté de `?run=<chemin>`. Un fichier au format
   `verdicts.schema.json`. Le run dont `run.start.task` correspond à un
   `task_id` prend la couleur du verdict ; `reason` s'affiche dans le panneau
   au survol. Un `task_id` sans run, ou un run sans verdict, reste neutre — un
   verdict orphelin n'est pas une erreur.
3. **Le glisser-déposer** d'un `.events.jsonl` et d'un `.verdicts.jsonl`,
   déjà prévu dans `ruche-et-le-harnais.md` §4.

**Ce que Ruche ne fait pas.** Elle ne plie pas, ne juge pas, ne lit ni
`~/.claude/projects` ni les spans. `tools/hook-emit.sh` est supprimé, comme
déjà décidé : la capture appartient aux producteurs.

### 5.6 `harnais.py` — trois lignes

`NOYAU` gagne `eval/plier_evenements.py`, `eval/deplier_runs.py`,
`eval/juge_local.py`, `eval/schemas/run_events.schema.json` et
`eval/schemas/verdicts.schema.json`. `verifier` mesurera donc leur dérive
dans oneiros comme pour le reste. `mac-ia/` n'entre pas dans `NOYAU`.

## 6. Le flux, de bout en bout

```
tes sessions Claude Code (~/.claude/projects)
        │  coachingia exporter-run            [à écrire côté coachingia, palier B de son doc]
        ▼
<session>.events.jsonl ─────────────────────────────▶  ruche  ?run=
        │
        │  harnais/eval/plier_evenements.py
        ▼
runs.jsonl (run_contract)
        │
        │  harnais/eval/run_tasks_eval.py --judge-cmd juge_local.py   ──▶  Qwen, Mac, :1234
        ▼
eval/runs/tasks/<label>.json  +  verdicts.jsonl ──────▶  ruche  ?eval=

oneiros (runner futur, lot L3+) ──émet directement──▶  <run>.events.jsonl  ──▶ même chaîne
harnais eval/fixtures/runs_tasks.jsonl ──deplier_runs.py──▶ *.events.jsonl ──▶ ruche, dès le palier 4
```

Un seul objet, deux projections : les événements pour voir, le résumé pour
juger. Le passage de l'un à l'autre est un script du harnais, testé dans les
deux sens.

**Où vivent les runs.** Dans le projet qui les a produits : `eval/runs/` pour
les oracles, le dossier de sortie choisi par `exporter-run` pour coachingia.
Ruche est pointée sur un fichier. Pas de dossier partagé : rien ne le demande
encore.

## 7. Les tests

Le harnais garde sa règle : stdlib, `unittest`, `eval/tests/test_eval.py`.

| Ce qui est prouvé | Comment |
|---|---|
| Le schéma d'événements accepte `ruche/public/demo-run.jsonl` (une fois sa `policy` alignée) | fixture copiée dans `eval/fixtures/demo.events.jsonl`, en-tête et événements validés par `jsonschema_lite` |
| `verifier_evenements()` refuse un trou dans `seq`, un fichier sans en-tête, sans `run.end` | trois cas négatifs |
| `plier` produit un run conforme au contrat | pliage de `demo.events.jsonl`, validation, comparaison champ à champ à une attente écrite à la main |
| `deplier` puis `plier` conserve les champs transportés | sur `runs_tasks.jsonl`, les dix runs |
| `juge_local` respecte le contrat `--judge-cmd` | un faux serveur HTTP `http.server` dans le test, qui renvoie du texte puis un JSON ; le script extrait le JSON ; puis un serveur qui coupe → code 2, jamais `pass: false` |
| Un juge en panne sur un cas ne jette pas la campagne | `run_tasks_eval.py` avec un `--judge-cmd` qui échoue sur T-03 seulement : code 0, `judge_pass: null` sur T-03, `judge_errors: 1`, neuf verdicts présents |
| Un juge en panne sur tous les cas rend « rien mesuré » | même chose avec une commande qui échoue toujours : code 2 |
| `juge_local` ne transmet pas la sortie attendue | le faux serveur enregistre le prompt reçu ; le test cherche `expected` et échoue s'il le trouve |
| `mac-ia` n'a pas cassé au déplacement | `python3 mac-ia/tests/test_bridge.py`, blocs 1 à 4 |
| `events.ts` et `run_events.schema.json` disent la même chose | `ruche/test/contrat.test.ts`, vitest |
| Les verdicts colorent le bon run | `ruche/test/verdicts.test.ts` : un run, deux verdicts dont un orphelin |

Aucun test ne parle au Mac. Le juge réel se vérifie à la main, une fois, sur
les fixtures : c'est le palier 2, et son critère est un rapport écrit dans
`eval/runs/tasks/`.

## 8. Les paliers

Chacun est franchi ou non, contre une commande. Du moins cher au plus cher.

**Palier 1 — zéro code.** `ANTHROPIC_BASE_URL` posé, `coachingia evaluer
--juge` lancé. *Franchi quand* : le rapport de coachingia porte un avis du
juge de réécriture et LM Studio montre l'appel dans ses logs.

**Palier 2 — le juge local.** `juge_local.py`, ses tests, et la panne par
cas dans `run_tasks_eval.py`. *Franchi quand* :
`run_tasks_eval.py --runs eval/fixtures/runs_tasks.jsonl --judge-cmd
"python3 eval/juge_local.py"` écrit un rapport avec `judge_rate` et
`agreement` non nuls.

**Palier 3 — les contrats et les déplacements.** `run_events.schema.json`,
`verdicts.schema.json`, `mac-ia/` dans le harnais, `ruche/` à la racine,
`contrat.test.ts`. *Franchi quand* : `harnais.py verifier --projet ../oneiros`
sort en 0 après réinstallation, `test_bridge.py` passe depuis son nouveau
chemin, `npm test` passe dans `ruche/`.

**Palier 4 — les évals dans la ruche, sur fixtures.** `deplier_runs.py`,
`plier_evenements.py`, `?eval=`. *Franchi quand* : les dix runs de
`runs_tasks.jsonl` s'ouvrent dans Ruche, colorés par les verdicts de
`judge.jsonl`, et T-03 est rouge avec sa raison au survol.

**Palier 5 — tes vraies sessions.** Hors de cette spec : c'est
`RunExporter.cs`, palier B de `ruche-et-le-harnais.md`, qui écrit désormais
contre `run_events.schema.json`.

## 9. Hors périmètre, et pourquoi

- **Le runner d'oneiros** qui émettrait des événements : lot L3+ de
  `TASKS.md`, non commencé. La spec lui donne un contrat à viser, rien de plus.
- **Un `harnais.py modele`** qui piloterait le routeur : `profiles.py` fait
  déjà `status`, `switch`, `serve`. Une commande de plus serait une copie.
- **Un dossier de runs partagé** entre projets : aucun consommateur ne le
  demande. Ruche prend un chemin.
- **La projection de `verdict.json` (coachingia) vers `verdicts.jsonl`** : elle
  se fait côté coachingia, quand quelqu'un voudra voir sa campagne dans Ruche.
  Le format est fixé ici pour qu'elle soit possible.
- **Un juge local pour coachingia** distinct de `claude -p` : inutile, la
  variable d'environnement suffit.

## 10. Les hypothèses prises

1. L'adresse du Mac est `192.168.1.50`, comme dans la documentation de
   mac-ia. Elle n'est qu'un défaut : tout se surcharge par variable
   d'environnement.
2. Le profil `brain` (Qwen 3.8, 27B) est le juge. Le profil `code` reste à
   Hermès et ne doit pas être basculé sous ses pieds — `hermes.hold` protège
   ce cas, et le juge ne bascule jamais de profil lui-même.
3. `events.ts` tel qu'il est au 12 septembre est la bonne définition. Si le
   chantier Ruche en cours la fait bouger, le schéma suit, et le test de
   concordance le dira.
