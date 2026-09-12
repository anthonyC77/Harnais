# Un harnais pour deux produits — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner au harnais les deux contrats (événements, verdicts), les trois scripts (`juge_local`, `plier_evenements`, `deplier_runs`), y rapatrier `mac-ia/`, sortir Ruche en dépôt frère et lui apprendre `?eval=`.

**Architecture:** Le harnais possède les contrats et l'outil qui mesure ; les produits possèdent leurs étalons ; Ruche ne possède que le rendu. Un seul objet (le run), deux projections (événements pour voir, résumé pour juger), et un script stdlib du harnais dans chaque sens, testé aller-retour. Le juge est un modèle local hors système, appelé en dialecte OpenAI, et sa panne n'est jamais un `pass: false`.

**Tech Stack:** Python 3.9 stdlib (`unittest`, `urllib`, `http.server`), JSON Schema 2020-12 lu par `jsonschema_lite.py` (Python) et Ajv 8 (vitest, Ruche), TypeScript 5 / Vite 5 / vitest 2 côté Ruche.

**Spec:** `harnais/docs/superpowers/specs/2026-09-12-harnais-partage-design.md`

## Global Constraints

- **Stdlib uniquement** dans `harnais/eval/*.py` et `harnais/mac-ia/` : aucune dépendance pip. Python cible : **3.9** (pas de `X | None` hors annotations différées, pas de `match`).
- **Tests** : `unittest`, dans `eval/tests/test_eval.py`. **Aucun test ne parle au Mac.** Un test qui a besoin d'un serveur en fabrique un (`http.server`) sur `127.0.0.1`.
- **Sous Windows**, tout `subprocess.run` échangeant du texte passe `encoding="utf-8"` ; tout script lu sur stdin fait `sys.stdin.reconfigure(encoding="utf-8")`.
- Commentaires, libellés, messages d'erreur : **en français**, ton du dépôt (phrases courtes, un « pourquoi » par bloc non évident).
- `run_contract.schema.json` **ne change pas**. Version d'événements : `contract_version: 1`, `v: 1`. Contrat de run : `"1.0"`.
- Le juge ne reçoit **jamais** `task.expected` ni la sortie attendue ; il reçoit rubrique, entrée, sortie, statut, et les outils (nom, `ok`) sans leurs sorties.
- Trois interdits : pas de noyau du harnais dans coachingia ; pas de fusion de dépôts ; aucune éval ne lit les spans.
- Quatre dépôts, quatre `git` : `harnais/`, `oneiros/`, `coachingia/`, `ruche/` (créé ici). `oneiros` et `coachingia` portent du travail non commité qui n'est pas le nôtre : **toujours committer avec un pathspec explicite**, jamais `git add -A` dans ces deux-là.
- Fin de chaque message de commit : `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- Racine de travail : `D:/HorusCoachIA` (le classeur). Les chemins ci-dessous sont relatifs à cette racine sauf mention.

## État des lieux vérifié le 12 septembre (ce que le plan corrige par rapport à la spec)

- `harnais/eval/jsonschema_lite.py` ne connaît ni `$ref` ni `const`. Le schéma d'événements a 17 genres et une enveloppe commune : sans `$ref` il ferait 600 lignes. → Tâche 6 l'étend (deux mots-clés, ~15 lignes).
- `ruche/public/demo-run.jsonl` finit par `agent.end`, pas `run.end`. → Tâche 5 inverse les deux derniers événements dans `make-demo-trace.mjs`.
- Apparier `tool.start`/`tool.end` « du même actor, par ordre » se trompe sur la démo : trois `tool.start` refusés par un hook ne reviennent jamais et voleraient les `tool.end` suivants. → L'appariement se fait par `(actor, tool, args)`, FIFO. C'est le seul écart à la table de §5.2.
- `test_judge_cmd_contract` échoue déjà sous Windows : `subprocess.run(text=True)` encode en cp1252 et un `≈` dans `runs_tasks.jsonl` plante l'échange. → Tâche 1 passe `encoding="utf-8"`.
- `oneiros/CLAUDE.md` et `oneiros/oneiros/LIAISON_HERMES_MAC.md` **ne citent pas** `mac-ia/` (grep vérifié). → Tâche 3 ne les touche pas.
- La suite `test_eval.py` ne tourne pas telle quelle dans `harnais/` (pas de `tasks_golden.jsonl`, pas de `policy/`). → Les nouveaux tests prennent l'étalon du projet s'il existe, sinon celui de `modele/eval/`. La vérification finale se fait dans `oneiros/` après `installer --forcer`.
- `coachingia/web/ruche/` n'est pas suivi par git, `node_modules` absent ; `tools/hook-emit.sh` n'y est déjà plus (il reste dans `notes/ruche/`, l'archive).
- Ajv 8 en ESM : `import { Ajv2020 } from 'ajv/dist/2020.js'`, `new Ajv2020({ strict: false })`, `ajv.addSchema(root, 'ev')`, `ajv.getSchema('ev#/$defs/header')` — vérifié sous Node 22.

## Carte des fichiers

| Fichier | Rôle | Tâche |
|---|---|---|
| `harnais/eval/run_tasks_eval.py` | panne du juge par cas, `judge_errors`, utf-8 | 1 |
| `harnais/eval/juge_local.py` | `--judge-cmd` vers LM Studio, extraction du dernier JSON | 2 |
| `harnais/mac-ia/**` | déplacé depuis `oneiros/mac-ia/` | 3 |
| `ruche/**` | déplacé depuis `coachingia/web/ruche/`, dépôt neuf | 4 |
| `ruche/src/core/events.ts`, `tools/make-demo-trace.mjs`, `public/demo-run.jsonl` | `policy` alignée, `run.end` en dernier | 5 |
| `harnais/eval/fixtures/demo.events.jsonl` | copie de la démo alignée | 5 |
| `harnais/eval/jsonschema_lite.py` | `$ref` local, `const` | 6 |
| `harnais/eval/schemas/run_events.schema.json` | le contrat d'événements | 7 |
| `harnais/eval/schemas/verdicts.schema.json` | une ligne de verdict | 7 |
| `harnais/eval/plier_evenements.py` | `verifier_evenements()`, `charger()` (7) puis `plier()` + CLI (9) | 7, 9 |
| `ruche/test/contrat.test.ts` | concordance `events.ts` ↔ schéma, démo validée | 8 |
| `harnais/eval/deplier_runs.py` | `deplier()` + CLI | 10 |
| `harnais/harnais.py`, `harnais/LISEZ-MOI.md` | NOYAU + « ce qui est à qui » | 11 |
| `ruche/src/core/verdicts.ts`, `ui/panels.ts`, `main.ts`, `index.html`, `style.css`, `test/verdicts.test.ts` | `?eval=`, glisser-déposer | 12 |
| `ruche/README.md`, `coachingia/docs/ruche-et-le-harnais.md` | documentation | 13 |
| `harnais/eval/tests/test_eval.py` | tous les tests Python | 1, 2, 6, 7, 9, 10 |

---

### Task 1: Une panne du juge sur un cas ne jette pas la campagne

**Files:**
- Modify: `harnais/eval/run_tasks_eval.py` (fonctions `run_judge_cmd`, `summarize`, boucle de `main`)
- Test: `harnais/eval/tests/test_eval.py`

**Interfaces:**
- Consumes: rien de nouveau.
- Produces: chaque ligne de `rows` porte `judge_error: bool` ; `metrics.judge_errors: int` ; code 2 uniquement si `--judge-cmd` est demandé et qu'aucun cas n'a reçu de verdict. Les tâches 2 et 11 s'appuient dessus.

- [ ] **Step 1: Ajouter les chemins d'étalon et la classe de test**

En tête de `harnais/eval/tests/test_eval.py`, remplacer les quatre premières lignes de code par :

```python
"""Tests unitaires des oracles — stdlib, sans réseau. `python3 -m unittest discover -s eval/tests`"""
import http.server, json, os, shutil, socket, subprocess, sys, tempfile, threading, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); EVAL = os.path.dirname(HERE); PROJECT = os.path.dirname(EVAL)
sys.path.insert(0, EVAL)
import run_eval, run_tasks_eval, jsonschema_lite, check_tool_schemas  # noqa: E402


def _etalon(nom):
    """Un étalon du projet (tasks_golden, policy) — ou celui du modèle, quand la suite tourne dans le harnais lui-même."""
    chemin = os.path.join(EVAL, nom)
    return chemin if os.path.exists(chemin) else os.path.join(PROJECT, "modele", "eval", nom)


GOLDEN = _etalon("tasks_golden.jsonl")
POLICY = _etalon(os.path.join("policy", "agents.json"))
RUNS = os.path.join(EVAL, "fixtures", "runs_tasks.jsonl")
```

Dans `TasksOracle.setUpClass`, remplacer les deux lignes `cls.policies = …` et `cls.golden = …` par :

```python
        cls.policies = run_tasks_eval.load_json(POLICY)
        cls.golden = {t["id"]: t for t in run_tasks_eval.load_jsonl(GOLDEN)}
```

Dans `TasksOracle.test_cli_with_judge_file` et `TasksOracle.test_judge_cmd_contract`, insérer `"--golden", GOLDEN, "--policy", POLICY,` juste après `"--runs", os.path.join(EVAL, "fixtures", "runs_tasks.jsonl"),` — sans quoi ces deux tests ne tournent que dans un projet posé.

Ajouter, après la classe `TasksOracle` :

```python
class JugeParCas(unittest.TestCase):
    """Une panne du juge sur un cas ne jette pas les autres ; une panne sur tous rend « rien mesuré »."""
    JUGE = ("import sys, json\n"
            "sys.stdin.reconfigure(encoding='utf-8')\n"   # même piège Windows que run_judge_cmd : un juge lit de l'utf-8
            "d = json.load(sys.stdin)\n"
            "if d['task']['id'] in sys.argv[1:]: sys.exit(3)\n"
            "print(json.dumps({'pass': True, 'reason': 'ok'}))\n")

    def campagne(self, *cas_en_panne):
        with tempfile.TemporaryDirectory() as d:
            juge = os.path.join(d, "juge.py")
            with open(juge, "w", encoding="utf-8") as f:
                f.write(self.JUGE)
            # sans guillemets : les chemins sont sans espace, et cmd.exe digère mal deux paires de guillemets
            cmd = " ".join([sys.executable, juge, *cas_en_panne])
            code = run_tasks_eval.main(["--runs", RUNS, "--golden", GOLDEN, "--policy", POLICY,
                                       "--baseline", os.path.join(d, "absent.json"),
                                       "--judge-cmd", cmd, "--runs-dir", d, "--quiet"])
            rapports = [f for f in os.listdir(d) if f.endswith(".json")]
            rapport = json.load(open(os.path.join(d, rapports[0]), encoding="utf-8")) if rapports else None
            return code, rapport

    def test_panne_sur_un_cas(self):
        code, r = self.campagne("T-03")
        self.assertEqual(code, 0)
        t03 = next(x for x in r["rows"] if x["id"] == "T-03")
        self.assertIsNone(t03["judge_pass"]); self.assertTrue(t03["judge_error"]); self.assertIn("juge en panne", t03["judge_reason"])
        self.assertEqual(r["metrics"]["judge_errors"], 1); self.assertEqual(r["metrics"]["n_judged"], 9)

    def test_panne_sur_tous_les_cas_rend_rien_mesure(self):
        code, r = self.campagne(*[f"T-{i:02d}" for i in range(1, 11)])
        self.assertEqual(code, 2); self.assertIsNone(r)

    def test_un_accent_dans_le_run_ne_casse_pas_le_juge(self):
        code, r = self.campagne()
        self.assertEqual(code, 0); self.assertEqual(r["metrics"]["judge_errors"], 0); self.assertEqual(r["metrics"]["n_judged"], 10)
```

- [ ] **Step 2: Lancer les tests, les voir échouer**

Run: `cd D:/HorusCoachIA/harnais && python3 -m unittest discover -s eval/tests -k JugeParCas -v`
Expected: 3 échecs — `test_panne_sur_un_cas` reçoit `2` au lieu de `0` ; `test_un_accent…` reçoit `2` (le `≈` en cp1252) ; `test_panne_sur_tous…` passe déjà par accident (code 2) — c'est attendu, il protège la suite.

- [ ] **Step 3: Corriger `run_tasks_eval.py`**

`run_judge_cmd` :

```python
def run_judge_cmd(cmd, task, run):
    payload = json.dumps({"task": task, "run": run, "rubric": task.get("judge", {}).get("rubric", "")}, ensure_ascii=False)
    # encoding explicite : sous Windows, text=True prend la page de code locale et un « ≈ » dans un run suffit à planter l'échange
    proc = subprocess.run(cmd, input=payload, capture_output=True, encoding="utf-8", shell=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"juge en erreur ({proc.returncode}) : {proc.stderr.strip()[:200]}")
    verdict = json.loads(proc.stdout)
    return {"pass": bool(verdict["pass"]), "reason": verdict.get("reason", "")}
```

Dans `summarize`, après la ligne `"judge_rate": rate(rows, "judge_pass"),` ajouter :

```python
        "judge_errors": sum(1 for r in rows if r.get("judge_error")),
```

Dans la boucle de `main`, remplacer le bloc `judge_pass, judge_reason = None, ""` … `return 2` par :

```python
        judge_pass, judge_reason, judge_error = None, "", False
        try:
            if a.judge_cmd and run is not None:
                v = run_judge_cmd(a.judge_cmd, task, run)
                judge_pass, judge_reason = v["pass"], v["reason"]
            elif task["id"] in judge_file:
                judge_pass = bool(judge_file[task["id"]]["pass"])
                judge_reason = judge_file[task["id"]].get("reason", "")
        except (RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as e:
            # Une panne du juge n'est jamais un pass: false — une coupure n'est pas une régression.
            # Le cas reste sans verdict, la campagne continue, le rapport compte la panne.
            judge_error, judge_reason = True, f"juge en panne : {e}"
            print(f"[{task['id']}] {judge_reason}", file=sys.stderr)
```

Dans le `rows.append({...})`, après `"judge_reason": judge_reason,` ajouter `"judge_error": judge_error,`.

Après `summary = summarize(rows)` insérer :

```python
    if a.judge_cmd and summary["judge_errors"] and summary["n_judged"] == 0:
        print(f"juge demandé, aucun verdict reçu ({summary['judge_errors']} panne(s)) : rien mesuré", file=sys.stderr)
        return 2
```

Dans l'affichage non `--quiet`, après la ligne `print(f"n={summary['n']}  jugées=…")` ajouter :

```python
        if summary["judge_errors"]:
            print(f"  juge en panne sur {summary['judge_errors']} cas (judge_pass: null, jamais false)")
```

Dans la docstring, remplacer `2 = erreur d'exécution.` par `2 = erreur d'exécution, ou juge demandé sans aucun verdict reçu.`

- [ ] **Step 4: Lancer les tests, les voir passer**

Run: `cd D:/HorusCoachIA/harnais && python3 -m unittest discover -s eval/tests -k JugeParCas -k TasksOracle -v`
Expected: `JugeParCas` 3 OK ; `TasksOracle` 8 OK dont `test_judge_cmd_contract` qui passait en échec sous Windows.

- [ ] **Step 5: Commit (harnais)**

```bash
cd D:/HorusCoachIA/harnais
git add eval/run_tasks_eval.py eval/tests/test_eval.py
git commit -m "Le juge en panne sur un cas ne jette plus la campagne

judge_pass: null et judge_reason portent la panne, le rapport compte
judge_errors, la campagne ne sort en 2 que si aucun cas n'a de verdict.
Au passage, l'echange avec --judge-cmd passe en utf-8 : sous Windows un
caractere hors cp1252 dans un run faisait tomber toute la campagne.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: `juge_local.py` — le juge hors système

**Files:**
- Create: `harnais/eval/juge_local.py`
- Test: `harnais/eval/tests/test_eval.py`

**Interfaces:**
- Consumes: le contrat `--judge-cmd` de `run_tasks_eval.py` : `{"task", "run", "rubric"}` sur stdin.
- Produces: `{"pass": bool, "reason": str}` sur stdout, code 0 ; code 2 + message stderr sinon. Variables `HARNAIS_JUGE_URL` (défaut `http://192.168.1.50:1234/v1`), `HARNAIS_JUGE_MODELE` (`brain`), `HARNAIS_JUGE_TIMEOUT` (`120`). Fonctions importables : `composer(payload) -> str`, `extraire_json(texte) -> dict | None`.

- [ ] **Step 1: Écrire les tests (faux LM Studio en `http.server`)**

Ajouter à `test_eval.py`, après `JugeParCas` :

```python
class _FauxLmStudio(http.server.BaseHTTPRequestHandler):
    """LM Studio de poche : renvoie `reponse`, note chaque requête dans `recues`."""
    reponse = ""
    finish = "stop"
    recues = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        type(self).recues.append(json.loads(self.rfile.read(n).decode("utf-8")))
        corps = json.dumps({"choices": [{"message": {"role": "assistant", "content": type(self).reponse},
                                         "finish_reason": type(self).finish}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        pass


class JugeLocal(unittest.TestCase):
    """juge_local.py respecte le contrat --judge-cmd, et ne voit jamais la sortie attendue."""
    JUGE = os.path.join(EVAL, "juge_local.py")
    PAYLOAD = {"task": {"id": "T-01", "expected": {"output": {"must_contain": ["SORTIE-ATTENDUE-SECRETE"]}}},
               "run": {"input": {"message": "Combien coûte un badge ?"}, "output": {"text": "20 € TTC"}, "status": "completed",
                       "tool_calls": [{"tool": "rechercher_documents", "input": {"query": "badge"},
                                       "output": {"results": [{"text": "SORTIE-VOLUMINEUSE"}]}, "ok": True}]},
               "rubric": "le prix est exact et sourcé"}

    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.HTTPServer(("127.0.0.1", 0), _FauxLmStudio)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close()

    def juger(self, url=None):
        env = dict(os.environ, HARNAIS_JUGE_URL=url or self.url, HARNAIS_JUGE_TIMEOUT="5")
        return subprocess.run([sys.executable, self.JUGE], input=json.dumps(self.PAYLOAD, ensure_ascii=False),
                              capture_output=True, encoding="utf-8", env=env)

    def test_extrait_le_dernier_json_apres_la_reflexion(self):
        _FauxLmStudio.reponse = "<think>Je compare {\"pass\": true} au prix…</think>\nVerdict : {\"pass\": false, \"reason\": \"source absente\"}"
        p = self.juger()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout), {"pass": False, "reason": "source absente"})

    def test_sans_json_code_2_jamais_pass_false(self):
        _FauxLmStudio.reponse = "Je ne sais pas trop, la réponse me paraît correcte."
        p = self.juger()
        self.assertEqual(p.returncode, 2); self.assertEqual(p.stdout.strip(), ""); self.assertIn("aucun JSON", p.stderr)

    def test_max_tokens_avant_le_json(self):
        _FauxLmStudio.reponse, _FauxLmStudio.finish = "<think>je réfléchis encore", "length"
        try:
            p = self.juger()
            self.assertEqual(p.returncode, 2); self.assertIn("max_tokens", p.stderr)
        finally:
            _FauxLmStudio.finish = "stop"

    def test_mac_injoignable_code_2(self):
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()  # un port que personne n'écoute
        p = self.juger(url=f"http://127.0.0.1:{port}/v1")
        self.assertEqual(p.returncode, 2); self.assertEqual(p.stdout.strip(), ""); self.assertIn("injoignable", p.stderr)

    def test_verdict_sans_raison_code_2(self):
        _FauxLmStudio.reponse = "{\"pass\": true, \"reason\": \"\"}"
        p = self.juger()
        self.assertEqual(p.returncode, 2); self.assertIn("sans raison", p.stderr)

    def test_ne_transmet_jamais_la_sortie_attendue(self):
        _FauxLmStudio.reponse = "{\"pass\": true, \"reason\": \"ok\"}"
        _FauxLmStudio.recues.clear()
        self.assertEqual(self.juger().returncode, 0)
        requete = _FauxLmStudio.recues[-1]
        prompt = json.dumps(requete, ensure_ascii=False)
        self.assertNotIn("SORTIE-ATTENDUE-SECRETE", prompt); self.assertNotIn("expected", prompt)
        self.assertNotIn("SORTIE-VOLUMINEUSE", prompt)          # les sorties d'outils ne voyagent pas non plus
        self.assertIn("le prix est exact", prompt); self.assertIn("20 € TTC", prompt)
        self.assertEqual(requete["model"], "brain"); self.assertEqual(requete["messages"][0]["role"], "system")
```

- [ ] **Step 2: Lancer, voir échouer**

Run: `cd D:/HorusCoachIA/harnais && python3 -m unittest discover -s eval/tests -k JugeLocal -v`
Expected: 6 erreurs/échecs (`juge_local.py` n'existe pas : `FileNotFoundError` ou code 2 sans le bon message).

- [ ] **Step 3: Écrire `harnais/eval/juge_local.py`**

```python
#!/usr/bin/env python3
"""Le juge hors système : un modèle local sur le Mac, appelé en dialecte OpenAI.

Implémente le contrat --judge-cmd de run_tasks_eval.py :
    stdin  : {"task": <golden>, "run": <run>, "rubric": str}
    stdout : {"pass": bool, "reason": str}, code 0
    sinon  : code 2, message sur stderr — jamais un pass: false pour une panne.

Pourquoi ce modèle est un bon juge : l'éval ne passe jamais par un agent du
système évalué. Qwen sur une machine hors ligne, qui ne partage ni code ni
prompt avec oneiros ou coachingia, est extérieur par construction.

Ce que le juge reçoit : la rubrique, l'entrée, la sortie, le statut, les outils
appelés (nom, ok). Ce qu'il ne reçoit jamais : la sortie attendue — sinon il
compare au lieu de juger — ni les sorties volumineuses des outils.

    python3 eval/run_tasks_eval.py --runs eval/fixtures/runs_tasks.jsonl \\
        --judge-cmd "python3 eval/juge_local.py"

Configuration par variables d'environnement :
    HARNAIS_JUGE_URL      http://192.168.1.50:1234/v1   LM Studio, dialecte OpenAI
    HARNAIS_JUGE_MODELE   brain                          l'identifiant forcé par le routeur
    HARNAIS_JUGE_TIMEOUT  120                            secondes — le profil brain réfléchit

Le juge ne bascule jamais de profil lui-même : `mac-ia/router/profiles.py switch brain`.
"""
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("HARNAIS_JUGE_URL", "http://192.168.1.50:1234/v1")
MODELE = os.environ.get("HARNAIS_JUGE_MODELE", "brain")
TIMEOUT = float(os.environ.get("HARNAIS_JUGE_TIMEOUT", "120"))

SYSTEME = (
    "Tu es le juge d'une évaluation. On te donne une rubrique, la demande faite à un assistant, "
    "sa réponse, son statut et la liste des outils qu'il a appelés. Décide si la réponse satisfait "
    "la rubrique. Réponds uniquement par un objet JSON de la forme "
    "{\"pass\": true ou false, \"reason\": \"une raison courte et vérifiable\"}. Rien d'autre après le JSON."
)


def composer(payload):
    """Le message utilisateur. Ni `task.expected`, ni les sorties d'outils : le juge juge, il ne compare pas."""
    run = payload.get("run", {})
    outils = [{"tool": c.get("tool"), "ok": c.get("ok")} for c in run.get("tool_calls", [])]
    return "\n".join([
        "RUBRIQUE :", payload.get("rubric", "") or "(aucune rubrique : juge la pertinence et l'exactitude)",
        "", "DEMANDE :", run.get("input", {}).get("message", ""),
        "", "RÉPONSE :", run.get("output", {}).get("text", ""),
        "", "STATUT :", str(run.get("status", "")),
        "", "OUTILS APPELÉS (nom, ok) :", json.dumps(outils, ensure_ascii=False),
    ])


def extraire_json(texte):
    """Le dernier objet JSON portant `pass` — un modèle à réflexion parle avant de répondre."""
    dec = json.JSONDecoder()
    for i in range(len(texte) - 1, -1, -1):
        if texte[i] != "{":
            continue
        try:
            obj, _ = dec.raw_decode(texte[i:])
        except ValueError:
            continue
        if isinstance(obj, dict) and "pass" in obj:
            return obj
    return None


def appeler(messages):
    corps = json.dumps({"model": MODELE, "messages": messages, "temperature": 0, "stream": False}).encode("utf-8")
    req = urllib.request.Request(f"{URL.rstrip('/')}/chat/completions", data=corps,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        payload = json.load(sys.stdin)
    except ValueError as e:
        print(f"entrée illisible : {e}", file=sys.stderr)
        return 2
    messages = [{"role": "system", "content": SYSTEME}, {"role": "user", "content": composer(payload)}]
    try:
        reponse = appeler(messages)
    except (urllib.error.URLError, OSError, ValueError) as e:   # refus de connexion, timeout (socket.timeout est un OSError), corps non JSON
        print(f"juge injoignable ({URL}) : {e}", file=sys.stderr)
        return 2
    try:
        choix = reponse["choices"][0]
        texte = choix["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        print(f"réponse inattendue : {json.dumps(reponse)[:200]}", file=sys.stderr)
        return 2
    verdict = extraire_json(texte)
    if verdict is None:
        motif = "max_tokens atteint avant le JSON" if choix.get("finish_reason") == "length" else "aucun JSON dans la réponse"
        print(f"{motif} : {texte[-200:]!r}", file=sys.stderr)
        return 2
    raison = str(verdict.get("reason", "")).strip()
    if not raison:
        print("verdict sans raison : un verdict sans explication ne se conteste pas", file=sys.stderr)
        return 2
    print(json.dumps({"pass": bool(verdict["pass"]), "reason": raison}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Lancer, voir passer**

Run: `cd D:/HorusCoachIA/harnais && python3 -m unittest discover -s eval/tests -k JugeLocal -v`
Expected: 6 OK.

- [ ] **Step 5: Commit (harnais)**

```bash
cd D:/HorusCoachIA/harnais
git add eval/juge_local.py eval/tests/test_eval.py
git commit -m "Un juge hors systeme : Qwen sur le Mac, en dialecte OpenAI

juge_local.py implemente --judge-cmd, extrait le dernier JSON d'une
reponse avec reflexion, sort en 2 sur toute panne, et ne recoit jamais
la sortie attendue. Teste contre un faux LM Studio en http.server.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**Palier 2 (à la main, hors tests, Mac allumé, profil `brain` résident) :**
`cd D:/HorusCoachIA/oneiros && python3 eval/run_tasks_eval.py --runs eval/fixtures/runs_tasks.jsonl --judge-cmd "python3 ../harnais/eval/juge_local.py"` — franchi quand le rapport dans `eval/runs/tasks/` porte `judge_rate` et `agreement` non nuls. (Le `juge_local.py` d'oneiros n'est posé qu'à la tâche 11 ; d'ici là, le chemin relatif vers le harnais suffit.)

---

### Task 3: Déplacer `mac-ia/` d'oneiros vers le harnais

**Files:**
- Move: `oneiros/mac-ia/**` (10 fichiers suivis) → `harnais/mac-ia/**`
- Modify: `harnais/LISEZ-MOI.md` (section « Ce qui est à qui »)

**Interfaces:**
- Produces: `harnais/mac-ia/router/profiles.py`, `harnais/mac-ia/bridge/server.py`, `harnais/mac-ia/tests/test_bridge.py` aux mêmes chemins relatifs qu'avant. Le code ne change pas.

- [ ] **Step 1: Vérifier l'état de départ**

Run: `cd D:/HorusCoachIA/oneiros/mac-ia && python3 tests/test_bridge.py | tail -3`
Expected: `48/48 checks passed`.

Run: `cd D:/HorusCoachIA && git -C oneiros ls-files mac-ia | wc -l && grep -rn "mac-ia" oneiros/CLAUDE.md oneiros/oneiros/*.md ; echo "grep=$?"`
Expected: `10`, aucune ligne de grep, `grep=1`. (Si une ligne apparaît, la corriger en `../harnais/mac-ia/` à l'étape 3.)

- [ ] **Step 2: Copier, nettoyer, retirer**

```bash
cd D:/HorusCoachIA
cp -r oneiros/mac-ia harnais/mac-ia
find harnais/mac-ia -name __pycache__ -type d -prune -exec rm -rf {} +
git -C oneiros rm -r -q mac-ia
rm -rf oneiros/mac-ia          # les __pycache__ non suivis restent sinon
ls oneiros/mac-ia 2>&1 | head -1   # attendu : No such file or directory
```

- [ ] **Step 3: Les tests passent depuis le nouveau chemin**

Run: `cd D:/HorusCoachIA/harnais/mac-ia && python3 tests/test_bridge.py | tail -3`
Expected: `48/48 checks passed`.

- [ ] **Step 4: Dire où c'est dans `harnais/LISEZ-MOI.md`**

Dans le bloc « Ce qui est à qui », après la ligne `eval/fixtures/      de quoi faire tourner la CI sans serveur → le noyau`, ajouter :

```
mac-ia/             routeur, pont Anthropic→OpenAI, brain : le LLM local
                    → infrastructure : se lance d'ici, ne se pose nulle part
```

Et après le bloc, un paragraphe :

```markdown
`mac-ia/` n'entre pas dans le noyau : c'est ce qu'on lance, pas ce qu'on
copie. Trois usages, une couture chacune — les agents Claude Code du harnais
et le `claude -p` de coachingia posent `ANTHROPIC_BASE_URL=http://192.168.1.50:1235`
vers le pont ; le juge des évals (`eval/juge_local.py`) parle à LM Studio en
`:1234` sans intermédiaire. `python3 mac-ia/router/profiles.py status` dit quel
profil est résident. Voir `mac-ia/README.md`.
```

- [ ] **Step 5: Commit des deux côtés, chacun citant l'autre**

```bash
cd D:/HorusCoachIA/harnais
git add mac-ia LISEZ-MOI.md
git commit -m "Accueillir mac-ia depuis oneiros : le LLM local est de l'infrastructure

Dix fichiers, code inchange, test_bridge.py 48/48 depuis le nouveau
chemin. L'historique reste dans oneiros (commit de retrait du meme jour).
mac-ia n'entre pas dans NOYAU : il se lance, il ne se pose pas.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
cd ../oneiros
git commit -m "Retirer mac-ia : il vit desormais dans ../harnais/mac-ia

Le routeur, le pont et le brain servent oneiros et coachingia de la meme
facon ; ils appartiennent a l'outillage. Commit d'accueil dans harnais du
meme jour. Le code n'a pas change.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" -- mac-ia
```

Run: `git -C oneiros status --short | grep mac-ia ; echo "reste=$?"`
Expected: `reste=1` (rien de mac-ia ne traîne dans l'index d'oneiros).

---

### Task 4: `ruche/` — dépôt frère

**Files:**
- Move: `coachingia/web/ruche/**` → `ruche/**`
- Create: `ruche/.gitignore`

**Interfaces:**
- Produces: `D:/HorusCoachIA/ruche` avec `npm test` vert (7 tests) et un premier commit. Les tâches 5, 8, 12, 13 y travaillent.

- [ ] **Step 1: Déplacer et initialiser**

```bash
cd D:/HorusCoachIA
mv coachingia/web/ruche ruche
rmdir coachingia/web 2>/dev/null || true      # ne supprime que si vide ; web/prototype existe, il restera
printf 'node_modules/\ndist/\npublic/runs/\n' > ruche/.gitignore
cd ruche && npm install
```

Expected : `npm install` termine sans erreur ; `ls node_modules | wc -l` > 0.

- [ ] **Step 2: La suite existante passe**

Run: `cd D:/HorusCoachIA/ruche && npm test`
Expected: `7 passed` (rejeu ×3, détecteurs ×4).

Run: `cd D:/HorusCoachIA/ruche && npx tsc --noEmit ; echo "tsc=$?"`
Expected: `tsc=0`.

- [ ] **Step 3: Premier commit**

```bash
cd D:/HorusCoachIA/ruche
git init -b main
git add -A
git commit -m "Ruche devient un depot frere : le lecteur 3D, rien d'autre

Sorti de coachingia/web/ruche (non suivi par git, aucun historique perdu).
Ruche lit le contrat du harnais ; chaque producteur l'ecrit. Elle ne plie
pas, ne juge pas, ne lit ni ~/.claude/projects ni les spans.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

Run: `git -C D:/HorusCoachIA/ruche ls-files | grep -c node_modules`
Expected: `0`.

---

### Task 5: Aligner la `policy` de Ruche sur le contrat de run, et `run.end` en dernier

**Files:**
- Modify: `ruche/src/core/events.ts` (interfaces `Quotas`, `RunPolicy`, nouvelle `Identity`)
- Modify: `ruche/tools/make-demo-trace.mjs` (`POLICY()`, ordre des deux derniers événements)
- Modify: `ruche/src/main.ts:66` et `:80`, `ruche/test/replay.test.ts:20`
- Regenerate: `ruche/public/demo-run.jsonl`
- Create: `harnais/eval/fixtures/demo.events.jsonl` (copie)

**Interfaces:**
- Produces: en-tête et `run.start.policy` de la forme `{agent, allowed_tools, quotas: {max_calls, max_calls_par_agent?, max_tokens, max_wall_clock_ms, max_eur}, identity: {principal, si_role?}}`. `run.end` est le dernier événement. La tâche 7 valide `demo.events.jsonl` contre le schéma ; la tâche 9 le plie.

- [ ] **Step 1: `events.ts` — la forme du contrat de run**

Remplacer les interfaces `Quotas` et `RunPolicy` par :

```ts
/** Les quotas du contrat de run (harnais/eval/schemas/run_contract.schema.json) ;
 *  `max_calls_par_agent` est le seul champ en plus, lu par les détecteurs (R5). */
export interface Quotas {
  max_calls: number;
  max_calls_par_agent?: number;
  max_tokens: number;
  max_wall_clock_ms: number;
  max_eur: number;
}

export interface Identity {
  principal: string;
  si_role?: string;
}

/** La même forme que `policy` du contrat de run : c'est ce qui permet à
 *  plier_evenements.py de la recopier sans l'inventer. */
export interface RunPolicy {
  agent: string;
  allowed_tools: string[];
  quotas: Quotas;
  identity: Identity;
}
```

- [ ] **Step 2: `main.ts` et `replay.test.ts` — un fichier déplié n'a pas `max_calls_par_agent`**

`ruche/src/main.ts`, dans `monter`, remplacer la première ligne du bloc « 1 · les détecteurs » et la ligne `const maxCalls = …` par :

```ts
  /* 1 · les détecteurs — dérivés, recalculables, fusionnés dans le flux.
     Un run déplié depuis le contrat de run n'a pas de quota par agent : le quota global fait foi. */
  const maxCalls = run.policy.quotas.max_calls_par_agent ?? run.policy.quotas.max_calls;
  const flags = detect(run.events, DEFAULT_RULES(maxCalls));
```

et supprimer l'ancienne ligne `const maxCalls = run.policy.quotas.max_calls_par_agent;` du bloc « 3 · la scène ».

`ruche/test/replay.test.ts`, ligne du `detect` :

```ts
const flags = detect(run.events, DEFAULT_RULES(run.policy.quotas.max_calls_par_agent ?? run.policy.quotas.max_calls));
```

- [ ] **Step 3: `make-demo-trace.mjs` — la politique et la fin du run**

Remplacer `function POLICY() { … }` par :

```js
function POLICY() {
  return {
    agent: 'harnais-dev',
    allowed_tools: ['Read', 'Edit', 'Write', 'Bash'],
    quotas: { max_calls: 36, max_calls_par_agent: 6, max_tokens: 80000, max_wall_clock_ms: 300000, max_eur: 0.3 },
    identity: { principal: 'anthony', si_role: 'dev' },
  };
}
```

Remplacer le bloc de clôture (les deux derniers `ev(...)`) par — `run.end` ferme le fichier, c'est une règle du contrat :

```js
ev('agent.end', 'orchestrateur', { status: 'completed' }, 10);
ev('run.end', 'orchestrateur', {
  status: 'completed',
  totals: { ...cum, eur: +cum.eur.toFixed(4), wall_clock_ms: t + 400, human_interventions: 1 },
}, 400);
```

Ajouter dans l'en-tête de commentaire du fichier, après « Aucun `flag`. … » :

```js
 *
 * Le premier événement est `run.start`, le dernier `run.end`, `seq` part de 0
 * sans trou : c'est ce que harnais/eval/schemas/run_events.schema.json impose.
```

- [ ] **Step 4: Régénérer, typer, tester**

```bash
cd D:/HorusCoachIA/ruche
npm run trace:demo
npx tsc --noEmit ; echo "tsc=$?"
npm test
```

Expected: `public/demo-run.jsonl — 85 événements, 68.2 s, 13 appels, 0.2120 €` ; `tsc=0` ; `7 passed`.

Run: `tail -1 public/demo-run.jsonl | cut -c1-120 && head -1 public/demo-run.jsonl | grep -c '"identity"'`
Expected: la dernière ligne contient `"kind":"run.end"` ; `1`.

- [ ] **Step 5: La fixture du harnais**

```bash
cp D:/HorusCoachIA/ruche/public/demo-run.jsonl D:/HorusCoachIA/harnais/eval/fixtures/demo.events.jsonl
```

- [ ] **Step 6: Commits (ruche, puis harnais)**

```bash
cd D:/HorusCoachIA/ruche
git add src/core/events.ts src/main.ts test/replay.test.ts tools/make-demo-trace.mjs public/demo-run.jsonl
git commit -m "Aligner la policy sur le contrat de run du harnais

RunPolicy prend agent, allowed_tools, quotas (max_calls + max_calls_par_agent),
identity — la forme que plier_evenements.py recopie sans l'inventer. La demo
finit desormais par run.end. Un run sans quota par agent prend le quota global.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
cd ../harnais
git add eval/fixtures/demo.events.jsonl
git commit -m "Fixture : la demo de Ruche, en evenements

Copie de ruche/public/demo-run.jsonl (T-07, 85 evenements). C'est ce que
le schema d'evenements doit accepter et ce que plier_evenements.py plie.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: `jsonschema_lite.py` — `$ref` local et `const`

**Files:**
- Modify: `harnais/eval/jsonschema_lite.py`
- Test: `harnais/eval/tests/test_eval.py`

**Interfaces:**
- Produces: `validate(instance, schema, path="$", root=None)` — `root` est le document où résoudre `#/…` ; par défaut, `schema` lui-même. Mots-clés ajoutés : `$ref` (uniquement `#/a/b/c`, chaînable), `const`. La tâche 7 s'en sert pour `$defs/env/*` et `kind: {const}`.

- [ ] **Step 1: Les tests**

Ajouter à `test_eval.py`, après `ToolIsAType` :

```python
class SchemaLite(unittest.TestCase):
    """Les deux mots-clés ajoutés pour le contrat d'événements : $ref local et const."""
    SCHEMA = {"$defs": {"cout": {"type": "object", "properties": {"calls": {"type": "integer"}}},
                        "env": {"cout": {"$ref": "#/$defs/cout"}}},
              "type": "object", "properties": {"kind": {"const": "run.end"}, "cost": {"$ref": "#/$defs/env/cout"}}}

    def test_ref_chaine_resolue_depuis_la_racine(self):
        self.assertEqual(jsonschema_lite.validate({"kind": "run.end", "cost": {"calls": 1}}, self.SCHEMA), [])
        errs = jsonschema_lite.validate({"kind": "run.end", "cost": {"calls": "x"}}, self.SCHEMA)
        self.assertEqual(len(errs), 1); self.assertTrue(errs[0].startswith("$.cost.calls"))

    def test_const(self):
        errs = jsonschema_lite.validate({"kind": "run.start"}, self.SCHEMA)
        self.assertEqual(len(errs), 1); self.assertIn("run.end", errs[0])

    def test_ref_non_local_refuse(self):
        with self.assertRaises(ValueError):
            jsonschema_lite.validate({}, {"$ref": "http://ailleurs/schema.json"})
```

- [ ] **Step 2: Lancer, voir échouer**

Run: `cd D:/HorusCoachIA/harnais && python3 -m unittest discover -s eval/tests -k SchemaLite -v`
Expected: 3 échecs (`$ref` et `const` ignorés → aucune erreur remontée ; pas de `ValueError`).

- [ ] **Step 3: Étendre le validateur**

Dans la docstring, remplacer `enum, minimum/maximum, minLength.` par `enum, const, minimum/maximum, minLength, $ref local (#/…).`

Ajouter avant `validate` :

```python
def _resoudre(ref, root):
    """Un pointeur JSON local (#/$defs/x). Rien d'autre : pas de réseau, pas de fichier."""
    if not ref.startswith("#/"):
        raise ValueError(f"$ref non local, non pris en charge : {ref}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node
```

Remplacer le début de `validate` par :

```python
def validate(instance, schema, path="$", root=None):
    errors = []
    if not isinstance(schema, dict):
        return errors
    if root is None:
        root = schema
    while "$ref" in schema:
        schema = _resoudre(schema["$ref"], root)
    t = schema.get("type")
```

Après le bloc `enum`, ajouter :

```python
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: attendu {schema['const']!r}, reçu {instance!r}")
```

Et passer `root` aux trois appels récursifs : `validate(val, props[key], f"{path}.{key}", root)`, `validate(val, schema["additionalProperties"], f"{path}.{key}", root)`, `validate(val, schema["items"], f"{path}[{i}]", root)`.

- [ ] **Step 4: Lancer, voir passer — et rien de cassé autour**

Run: `cd D:/HorusCoachIA/harnais && python3 -m unittest discover -s eval/tests -k SchemaLite -k TasksOracle -k JugeParCas -v`
Expected: tout OK.

- [ ] **Step 5: Commit (harnais)**

```bash
cd D:/HorusCoachIA/harnais
git add eval/jsonschema_lite.py eval/tests/test_eval.py
git commit -m "jsonschema_lite : \$ref local et const

Le contrat d'evenements a dix-sept genres et une enveloppe commune ;
sans \$ref il ferait six cents lignes. Pointeurs locaux uniquement.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Les deux contrats, et `verifier_evenements()`

**Files:**
- Create: `harnais/eval/schemas/run_events.schema.json`
- Create: `harnais/eval/schemas/verdicts.schema.json`
- Create: `harnais/eval/plier_evenements.py` (première moitié : chargement et vérification ; `plier()` arrive en tâche 9)
- Test: `harnais/eval/tests/test_eval.py`

**Interfaces:**
- Consumes: `jsonschema_lite.validate(instance, schema, path, root)` (tâche 6) ; `eval/fixtures/demo.events.jsonl` (tâche 5).
- Produces:
  - `charger_schema(nom) -> dict` — lit `eval/schemas/<nom>`.
  - `verifier_evenements(entete, evenements, schema, nom="<événements>") -> None` — lève `ValueError` (message préfixé par `nom`) si : pas d'en-tête, en-tête hors schéma, événement de genre inconnu ou hors schéma, `seq` non contigu depuis 0, `run` ≠ `run_id`, premier ≠ `run.start`, dernier ≠ `run.end`.
  - `charger(chemin, schema) -> (entete, evenements)` — lit un `.events.jsonl`, appelle `verifier_evenements`.
  - Schéma : `$defs.header` (l'en-tête), `$defs.kinds.<kind>` (un objet fermé par genre), `$defs.policy`, `$defs.cost`, `$defs.env.*` ; racine = `oneOf` des 17 genres (pour Ajv ; `jsonschema_lite` ignore `oneOf`, d'où la validation par `$defs.kinds[kind]` côté Python).

- [ ] **Step 1: Écrire les tests**

Ajouter à `test_eval.py` (après `SchemaLite`) et compléter la ligne d'import : `import run_eval, run_tasks_eval, jsonschema_lite, check_tool_schemas, plier_evenements  # noqa: E402`

```python
class Evenements(unittest.TestCase):
    """Le contrat d'événements accepte la démo de Ruche et refuse ce que le JSON Schema ne sait pas dire."""
    FIXTURE = os.path.join(EVAL, "fixtures", "demo.events.jsonl")

    @classmethod
    def setUpClass(cls):
        cls.schema = plier_evenements.charger_schema("run_events.schema.json")
        cls.entete, cls.evenements = plier_evenements.charger(cls.FIXTURE, cls.schema)

    def test_la_demo_de_ruche_passe_le_schema(self):
        self.assertEqual(self.entete["task_id"], "T-07"); self.assertEqual(len(self.evenements), 85)
        self.assertEqual(self.evenements[-1]["kind"], "run.end")

    def test_les_dix_sept_genres_sont_la(self):
        self.assertEqual(len(self.schema["$defs"]["kinds"]), 17)
        self.assertEqual(len(self.schema["oneOf"]), 17)

    def test_la_policy_a_la_forme_du_contrat_de_run(self):
        contrat = run_tasks_eval.load_json(os.path.join(EVAL, "schemas", "run_contract.schema.json"))
        pol_run, pol_ev = contrat["properties"]["policy"], self.schema["$defs"]["policy"]
        self.assertEqual(sorted(pol_run["required"]), sorted(pol_ev["required"]))
        self.assertEqual(sorted(pol_run["properties"]["quotas"]["required"]), sorted(pol_ev["properties"]["quotas"]["required"]))
        self.assertIn("max_calls_par_agent", pol_ev["properties"]["quotas"]["properties"])

    def refuse(self, entete, evenements, motif):
        with self.assertRaises(ValueError) as cm:
            plier_evenements.verifier_evenements(entete, evenements, self.schema, nom="demo")
        self.assertIn(motif, str(cm.exception)); self.assertIn("demo", str(cm.exception))

    def test_refuse_un_trou_dans_seq(self):
        self.refuse(self.entete, [e for e in self.evenements if e["seq"] != 3], "seq")

    def test_refuse_un_fichier_sans_entete(self):
        self.refuse(self.evenements[0], self.evenements[1:], "en-tête")

    def test_refuse_un_fichier_sans_run_end(self):
        self.refuse(self.entete, self.evenements[:-1], "run.end")

    def test_refuse_un_genre_inconnu(self):
        evs = json.loads(json.dumps(self.evenements)); evs[5]["kind"] = "tool.retry"
        self.refuse(self.entete, evs, "genre inconnu")

    def test_refuse_un_champ_hors_contrat(self):
        evs = json.loads(json.dumps(self.evenements)); evs[5]["prompt"] = "le contenu voyage par ref, pas ici"
        self.refuse(self.entete, evs, "propriété inconnue")

    def test_refuse_un_run_id_qui_ne_correspond_pas(self):
        evs = json.loads(json.dumps(self.evenements)); evs[5]["run"] = "autre"
        self.refuse(self.entete, evs, "run_id")

    def test_les_verdicts_passent_leur_schema(self):
        schema = plier_evenements.charger_schema("verdicts.schema.json")
        for v in run_tasks_eval.load_jsonl(os.path.join(EVAL, "fixtures", "judge.jsonl")):
            self.assertEqual(jsonschema_lite.validate(v, schema), [], v)
        self.assertTrue(jsonschema_lite.validate({"task_id": "T-01", "pass": True, "reason": ""}, schema))
        self.assertTrue(jsonschema_lite.validate({"task_id": "T-01", "pass": True}, schema))
```

- [ ] **Step 2: Lancer, voir échouer**

Run: `cd D:/HorusCoachIA/harnais && python3 -m unittest discover -s eval/tests -k Evenements -v`
Expected: `ImportError: No module named plier_evenements` (ou erreurs de `setUpClass`).

- [ ] **Step 3: `run_events.schema.json`**

Écrire `harnais/eval/schemas/run_events.schema.json` — c'est la **source** du contrat, `events.ts` en est le miroir :

```json
{
 "$schema": "https://json-schema.org/draft/2020-12/schema",
 "$id": "horus/run-events/1",
 "title": "Contrat de run en événements",
 "description": "Un fichier .events.jsonl : une ligne d'en-tête ($defs/header), puis une ligne par événement. Chaque événement est l'un des dix-sept genres de $defs/kinds — la racine est leur oneOf. Ce que le schéma ne sait pas dire vit dans verifier_evenements() de plier_evenements.py : seq contigu depuis 0, run.start en tête, run.end en queue, run égal à run_id. Miroir TypeScript : ruche/src/core/events.ts, vérifié par ruche/test/contrat.test.ts.",
 "$defs": {
  "status": {"type": "string", "enum": ["completed", "refused", "clarification", "failed", "cancelled", "quota_exceeded"]},
  "origin": {"type": "string", "enum": ["observed", "derived", "human"], "description": "observé (jamais recalculé), dérivé (recalculable : les drapeaux), ou geste humain"},
  "severity": {"type": "string", "enum": ["low", "medium", "high"]},
  "cost": {
   "type": "object", "additionalProperties": false,
   "properties": {
    "calls": {"type": "integer", "minimum": 0},
    "tok_in": {"type": "integer", "minimum": 0},
    "tok_out": {"type": "integer", "minimum": 0},
    "eur": {"type": "number", "minimum": 0}
   }
  },
  "policy": {
   "type": "object",
   "description": "La même forme que policy du contrat de run (run_contract.schema.json). quotas accepte en plus max_calls_par_agent, lu par les détecteurs de Ruche.",
   "required": ["agent", "allowed_tools", "quotas", "identity"],
   "properties": {
    "agent": {"type": "string"},
    "allowed_tools": {"type": "array", "items": {"type": "string"}},
    "quotas": {
     "type": "object",
     "required": ["max_calls", "max_tokens", "max_wall_clock_ms", "max_eur"],
     "properties": {
      "max_calls": {"type": "integer", "minimum": 0},
      "max_calls_par_agent": {"type": "integer", "minimum": 0},
      "max_tokens": {"type": "integer", "minimum": 0},
      "max_wall_clock_ms": {"type": "integer", "minimum": 0},
      "max_eur": {"type": "number", "minimum": 0}
     }
    },
    "identity": {
     "type": "object",
     "required": ["principal"],
     "properties": {"principal": {"type": "string"}, "si_role": {"type": "string"}}
    }
   }
  },
  "agent": {
   "type": "object", "additionalProperties": false,
   "required": ["id", "role", "depth"],
   "properties": {
    "id": {"type": "string", "minLength": 1},
    "role": {"type": "string"},
    "depth": {"type": "integer", "minimum": -1, "description": "-1 pour l'humain"}
   }
  },
  "header": {
   "type": "object", "additionalProperties": false,
   "required": ["contract_version", "run_id", "task_id", "agents", "policy"],
   "properties": {
    "contract_version": {"type": "integer", "enum": [1]},
    "run_id": {"type": "string", "minLength": 1},
    "task_id": {"type": "string", "minLength": 1, "description": "le cas du golden set, ou le nom de la tâche"},
    "agents": {"type": "array", "items": {"$ref": "#/$defs/agent"}},
    "policy": {"$ref": "#/$defs/policy"}
   }
  },
  "env": {
   "v": {"type": "integer", "enum": [1]},
   "seq": {"type": "integer", "minimum": 0, "description": "ordre logique : part de 0, avance de 1 par ligne, sans trou"},
   "t": {"type": "number", "minimum": 0, "description": "horloge vécue, ms depuis le début du run"},
   "run": {"type": "string", "minLength": 1},
   "actor": {"type": "string", "minLength": 1},
   "origin": {"$ref": "#/$defs/origin"},
   "ref": {"type": "string", "minLength": 1, "description": "empreinte du contenu volumineux, stocké hors journal"},
   "cost": {"$ref": "#/$defs/cost"}
  },
  "kinds": {
   "run.start": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "task", "title", "policy"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "run.start"},
     "task": {"type": "string", "minLength": 1},
     "title": {"type": "string"},
     "policy": {"$ref": "#/$defs/policy"}
    }
   },
   "run.end": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "status", "totals"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "run.end"},
     "status": {"$ref": "#/$defs/status"},
     "totals": {
      "type": "object", "additionalProperties": false,
      "required": ["calls", "tok_in", "tok_out", "eur", "wall_clock_ms", "human_interventions"],
      "properties": {
       "calls": {"type": "integer", "minimum": 0},
       "tok_in": {"type": "integer", "minimum": 0},
       "tok_out": {"type": "integer", "minimum": 0},
       "eur": {"type": "number", "minimum": 0},
       "wall_clock_ms": {"type": "integer", "minimum": 0},
       "human_interventions": {"type": "integer", "minimum": 0}
      }
     }
    }
   },
   "agent.spawn": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "role", "parent", "depth"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "agent.spawn"},
     "role": {"type": "string"},
     "parent": {"type": ["string", "null"]},
     "depth": {"type": "integer", "minimum": -1}
    }
   },
   "agent.end": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "status"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "agent.end"},
     "status": {"$ref": "#/$defs/status"}
    }
   },
   "agent.stop.attempt": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "agent.stop.attempt"}
    }
   },
   "think.start": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "summary"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "think.start"},
     "summary": {"type": "string"}
    }
   },
   "think.end": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "summary"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "think.end"},
     "summary": {"type": "string"}
    }
   },
   "tool.start": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "tool", "args"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "tool.start"},
     "tool": {"type": "string", "minLength": 1},
     "args": {"type": "string"}
    }
   },
   "tool.end": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "tool", "args", "ok", "ms"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "tool.end"},
     "tool": {"type": "string", "minLength": 1},
     "args": {"type": "string"},
     "ok": {"type": "boolean"},
     "ms": {"type": "integer", "minimum": 0},
     "out": {"type": "string"}
    }
   },
   "hook.allow": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "hook", "event", "exit", "reason"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "hook.allow"},
     "hook": {"type": "string"},
     "event": {"type": "string"},
     "exit": {"type": "integer"},
     "reason": {"type": "string"}
    }
   },
   "hook.deny": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "hook", "event", "exit", "reason"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "hook.deny"},
     "hook": {"type": "string"},
     "event": {"type": "string"},
     "exit": {"type": "integer"},
     "reason": {"type": "string"},
     "tool": {"type": "string"}
    }
   },
   "wait.start": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "on"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "wait.start"},
     "on": {"type": "string"}
    }
   },
   "wait.end": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "on"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "wait.end"},
     "on": {"type": "string"}
    }
   },
   "msg": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "to", "text"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "msg"},
     "to": {"type": "string", "minLength": 1},
     "text": {"type": "string"}
    }
   },
   "human": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "to", "text"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "human"},
     "to": {"type": "string", "minLength": 1},
     "text": {"type": "string"}
    }
   },
   "flag": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "rule", "severity", "why", "evidence", "hand"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "flag"},
     "rule": {"type": "string"},
     "severity": {"$ref": "#/$defs/severity"},
     "why": {"type": "string"},
     "evidence": {"type": "array", "items": {"type": "integer", "minimum": 0}},
     "hand": {"type": "boolean"}
    }
   },
   "flag.clear": {
    "type": "object", "additionalProperties": false,
    "required": ["v", "seq", "t", "run", "actor", "origin", "kind", "reason"],
    "properties": {
     "v": {"$ref": "#/$defs/env/v"}, "seq": {"$ref": "#/$defs/env/seq"}, "t": {"$ref": "#/$defs/env/t"}, "run": {"$ref": "#/$defs/env/run"}, "actor": {"$ref": "#/$defs/env/actor"}, "origin": {"$ref": "#/$defs/env/origin"}, "ref": {"$ref": "#/$defs/env/ref"}, "cost": {"$ref": "#/$defs/env/cost"},
     "kind": {"const": "flag.clear"},
     "reason": {"type": "string"}
    }
   }
  }
 },
 "oneOf": [
  {"$ref": "#/$defs/kinds/run.start"}, {"$ref": "#/$defs/kinds/run.end"},
  {"$ref": "#/$defs/kinds/agent.spawn"}, {"$ref": "#/$defs/kinds/agent.end"}, {"$ref": "#/$defs/kinds/agent.stop.attempt"},
  {"$ref": "#/$defs/kinds/think.start"}, {"$ref": "#/$defs/kinds/think.end"},
  {"$ref": "#/$defs/kinds/tool.start"}, {"$ref": "#/$defs/kinds/tool.end"},
  {"$ref": "#/$defs/kinds/hook.allow"}, {"$ref": "#/$defs/kinds/hook.deny"},
  {"$ref": "#/$defs/kinds/wait.start"}, {"$ref": "#/$defs/kinds/wait.end"},
  {"$ref": "#/$defs/kinds/msg"}, {"$ref": "#/$defs/kinds/human"},
  {"$ref": "#/$defs/kinds/flag"}, {"$ref": "#/$defs/kinds/flag.clear"}
 ]
}
```

- [ ] **Step 4: `verdicts.schema.json`**

```json
{
 "$schema": "https://json-schema.org/draft/2020-12/schema",
 "$id": "horus/verdicts/1",
 "title": "Une ligne de verdict",
 "description": "Un fichier verdicts.jsonl : une ligne par cas jugé. C'est le format de --judge-file dans run_tasks_eval.py et le seul que Ruche accepte en ?eval=. reason est obligatoire et non vide : un verdict sans explication ne se conteste pas (modele/rules/evals.md). Le verdict.json de coachingia s'y projette de son côté.",
 "type": "object",
 "additionalProperties": false,
 "required": ["task_id", "pass", "reason"],
 "properties": {
  "task_id": {"type": "string", "minLength": 1, "description": "le cas du golden set"},
  "pass": {"type": "boolean"},
  "reason": {"type": "string", "minLength": 1}
 }
}
```

- [ ] **Step 5: `plier_evenements.py`, première moitié**

```python
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
```

- [ ] **Step 6: Lancer, voir passer**

Run: `cd D:/HorusCoachIA/harnais && python3 -m unittest discover -s eval/tests -k Evenements -v`
Expected: 10 OK. Si `test_la_demo_de_ruche_passe_le_schema` échoue en `setUpClass` avec une « propriété inconnue », c'est que la démo porte un champ que `events.ts` ne déclare pas : le message dit lequel ; corriger le générateur (tâche 5), pas le schéma.

- [ ] **Step 7: Commit (harnais)**

```bash
cd D:/HorusCoachIA/harnais
git add eval/schemas/run_events.schema.json eval/schemas/verdicts.schema.json eval/plier_evenements.py eval/tests/test_eval.py
git commit -m "Deux contrats : le run en evenements, et une ligne de verdict

run_events.schema.json fige les dix-sept genres d'events.ts ; le schema
devient la source, events.ts le miroir. verdicts.schema.json fige le
format de judge.jsonl. verifier_evenements() porte ce que le JSON Schema
ne sait pas dire : seq contigu, run.start en tete, run.end en queue.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: `ruche/test/contrat.test.ts` — `events.ts` et le schéma disent la même chose

**Files:**
- Create: `ruche/test/contrat.test.ts`
- Modify: `ruche/package.json` (devDependency `ajv`)

**Interfaces:**
- Consumes: `../harnais/eval/schemas/run_events.schema.json` (tâche 7), `public/demo-run.jsonl` (tâche 5), `parseJsonl` de `src/core/sources.ts`.
- Produces: un test sauté avec message si le harnais n'est pas à côté.

- [ ] **Step 1: Installer Ajv et écrire le test**

```bash
cd D:/HorusCoachIA/ruche && npm install -D ajv@8
```

`ruche/test/contrat.test.ts` :

```ts
/**
 * LE TEST DE CONCORDANCE
 *
 * Le schéma du harnais est la source du contrat d'événements ; events.ts en
 * est le miroir. Ce test échoue si la liste des `kind` diffère dans un sens
 * ou dans l'autre, ou si la démo ne passe pas le schéma.
 *
 * Le harnais est un dépôt frère : s'il n'est pas à côté, le test est SAUTÉ
 * avec un message, pas en échec — Ruche doit rester clonable seule.
 */

import { existsSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { Ajv2020 } from 'ajv/dist/2020.js';
import { parseJsonl } from '../src/core/sources.js';

/** Chemin relatif au dépôt frère. Une constante, pas une découverte. */
const SCHEMA = '../harnais/eval/schemas/run_events.schema.json';
const present = existsSync(SCHEMA);
if (!present) console.warn(`harnais absent (${SCHEMA}) : test de concordance sauté`);

/** Les genres déclarés par events.ts — lus dans la source, les types n'existent pas à l'exécution. */
function kindsDeEventsTs(): string[] {
  const src = readFileSync('src/core/events.ts', 'utf8');
  return [...src.matchAll(/\{ kind: '([a-z.]+)'/g)].map(m => m[1]!).sort();
}

describe.skipIf(!present)('concordance avec le harnais', () => {
  const schema = JSON.parse(readFileSync(SCHEMA, 'utf8')) as {
    $defs: { kinds: Record<string, unknown> };
  };
  const ajv = new Ajv2020({ strict: false, allErrors: true });
  ajv.addSchema(schema, 'ev');
  const validerEvenement = ajv.getSchema('ev')!;
  const validerEntete = ajv.getSchema('ev#/$defs/header')!;

  it('events.ts et le schéma déclarent les mêmes genres', () => {
    expect(kindsDeEventsTs()).toEqual(Object.keys(schema.$defs.kinds).sort());
  });

  it('la démo passe le schéma, en-tête et événements', () => {
    const texte = readFileSync('public/demo-run.jsonl', 'utf8');
    const { events, ...entete } = parseJsonl(texte);
    expect(validerEntete(entete), ajv.errorsText(validerEntete.errors)).toBe(true);
    for (const e of events) {
      expect(validerEvenement(e), `seq ${e.seq} (${e.kind}) : ${ajv.errorsText(validerEvenement.errors)}`).toBe(true);
    }
  });

  it('la policy de la démo a la forme du contrat de run', () => {
    const run = parseJsonl(readFileSync('public/demo-run.jsonl', 'utf8'));
    expect(run.policy.identity.principal).toBeTruthy();
    expect(run.policy.allowed_tools.length).toBeGreaterThan(0);
    expect(run.policy.quotas.max_calls).toBeGreaterThanOrEqual(run.policy.quotas.max_calls_par_agent ?? 0);
  });
});
```

- [ ] **Step 2: Lancer, voir passer (et voir le saut)**

Run: `cd D:/HorusCoachIA/ruche && npm test`
Expected: `10 passed` (7 + 3).

Run: `cd D:/HorusCoachIA/ruche && mv ../harnais/eval/schemas/run_events.schema.json /tmp/rs.json && npm test ; mv /tmp/rs.json ../harnais/eval/schemas/run_events.schema.json`
Expected: `7 passed | 3 skipped`, et la ligne `harnais absent (…) : test de concordance sauté` dans la sortie. Vérifier que le schéma est bien revenu : `ls ../harnais/eval/schemas/`.

Run: `npx tsc --noEmit ; echo "tsc=$?"` → `tsc=0`.

- [ ] **Step 3: Commit (ruche)**

```bash
cd D:/HorusCoachIA/ruche
git add test/contrat.test.ts package.json package-lock.json
git commit -m "Test de concordance : events.ts est le miroir du schema du harnais

Les kind des deux cotes doivent etre les memes, et la demo doit passer
le schema (Ajv). Saute avec un message si ../harnais n'est pas la :
Ruche reste clonable seule.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: `plier_evenements.py` — événements → runs résumés

**Files:**
- Modify: `harnais/eval/plier_evenements.py` (ajout de `plier()`, `plier_fichiers()`, `main()`)
- Test: `harnais/eval/tests/test_eval.py`

**Interfaces:**
- Consumes: `charger`, `charger_schema`, `verifier_evenements` (tâche 7) ; `jsonschema_lite.validate`.
- Produces:
  - `plier(entete, evenements) -> dict` — un run conforme au contrat `1.0`.
  - `plier_fichiers(chemins, schema_evenements, contrat) -> list[dict]` — lève `ValueError` sur le premier fichier refusé (message avec le nom).
  - `main(argv) -> int` — CLI `fichiers... [--out runs.jsonl]` ; sans `--out`, sur stdout. Code 2 et rien d'écrit si un fichier est refusé ou un run plié ne passe pas le contrat.
  - Appariement `tool.start`/`tool.end` par `(actor, tool, args)`, FIFO. Un `tool.start` orphelin → `{"tool", "input": {"args"}, "output": null, "ok": false}` sans `latency_ms`, à sa place dans l'ordre des débuts.

- [ ] **Step 1: Les tests — une attente écrite à la main**

Ajouter à `test_eval.py`, après `Evenements` :

```python
class Plier(unittest.TestCase):
    """plier(demo) est conforme au contrat de run, et dit ce que la démo montre."""
    ATTENDU = {
        "contract_version": "1.0", "run_id": "run_2026-09-11_T07_a3f91c", "task_id": "T-07", "status": "completed",
        "input": {"message": "Ajouter `docId` au contrat RechercherDocuments et faire repasser l'eval retrieval"},
        "output": {"text": ""}, "provenance": [], "human_interventions": 1,
        "cost": {"calls": 13, "tokens_in": 54500, "tokens_out": 3230, "eur": 0.212, "wall_clock_ms": 68220},
    }
    # (outil, ok, latency_ms) — les trois sans latence sont les tool.start refusés par guard-eval-files.sh
    OUTILS = [("Read", True, 120), ("Read", True, 130), ("Edit", True, 90), ("Bash", True, 4200), ("Bash", False, 6100),
              ("Write", False, None), ("Edit", False, None), ("Bash", False, None),
              ("Bash", False, 5200), ("Bash", True, 1800), ("Bash", True, 900), ("Bash", True, 5800), ("Bash", True, 300), ("Bash", True, 3100)]

    @classmethod
    def setUpClass(cls):
        cls.schema = plier_evenements.charger_schema("run_events.schema.json")
        cls.contrat = plier_evenements.charger_schema("run_contract.schema.json")
        cls.entete, cls.evenements = plier_evenements.charger(Evenements.FIXTURE, cls.schema)
        cls.run = plier_evenements.plier(cls.entete, cls.evenements)

    def test_conforme_au_contrat(self):
        self.assertEqual(jsonschema_lite.validate(self.run, self.contrat), [])

    def test_champ_a_champ(self):
        for k, v in self.ATTENDU.items():
            self.assertEqual(self.run[k], v, k)
        self.assertEqual(self.run["policy"], self.entete["policy"])
        self.assertNotIn("cancelled", self.run); self.assertNotIn("context_tokens", self.run["input"])

    def test_les_appels_d_outils_dans_l_ordre_des_debuts(self):
        self.assertEqual([(c["tool"], c["ok"], c.get("latency_ms")) for c in self.run["tool_calls"]], self.OUTILS)
        refuse = self.run["tool_calls"][5]
        self.assertEqual(refuse["input"], {"args": "eval/schemas/tools/rechercher_documents.schema.json"})
        self.assertIsNone(refuse["output"]); self.assertNotIn("latency_ms", refuse)
        self.assertEqual(self.run["tool_calls"][0]["output"], "24 lignes")

    def test_un_run_annule_porte_cancelled(self):
        evs = json.loads(json.dumps(self.evenements)); evs[-1]["status"] = "cancelled"
        r = plier_evenements.plier(self.entete, evs)
        self.assertEqual(r["status"], "cancelled"); self.assertTrue(r["cancelled"])

    def test_cli_ecrit_un_runs_jsonl_valide(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "runs.jsonl")
            self.assertEqual(plier_evenements.main([Evenements.FIXTURE, "--out", out]), 0)
            runs = run_tasks_eval.load_jsonl(out)
            self.assertEqual(len(runs), 1); self.assertEqual(runs[0]["task_id"], "T-07")

    def test_cli_refuse_sans_rien_ecrire(self):
        with tempfile.TemporaryDirectory() as d:
            tronque, out = os.path.join(d, "t.events.jsonl"), os.path.join(d, "runs.jsonl")
            lignes = open(Evenements.FIXTURE, encoding="utf-8").read().splitlines()
            open(tronque, "w", encoding="utf-8").write("\n".join(lignes[:-1]) + "\n")
            self.assertEqual(plier_evenements.main([Evenements.FIXTURE, tronque, "--out", out]), 2)
            self.assertFalse(os.path.exists(out))
```

- [ ] **Step 2: Lancer, voir échouer**

Run: `cd D:/HorusCoachIA/harnais && python3 -m unittest discover -s eval/tests -k Plier -v`
Expected: `AttributeError: module 'plier_evenements' has no attribute 'plier'`.

- [ ] **Step 3: Écrire `plier()` et le CLI**

Ajouter à la fin de `plier_evenements.py` :

```python
def plier(entete, evenements):
    """Un run résumé (contrat 1.0) depuis un run en événements — la table de correspondance de la spec §5.2.

    Les appels d'outils sont appariés par (actor, tool, args), dans l'ordre : apparier par acteur seul
    ferait qu'un tool.start jamais revenu (refusé par un hook) vole le tool.end suivant."""
    debut, fin = evenements[0], evenements[-1]
    appels, en_attente = [], {}
    for e in evenements:
        if e["kind"] == "tool.start":
            appel = {"tool": e["tool"], "input": {"args": e["args"]}, "output": None, "ok": False}
            appels.append(appel)
            en_attente.setdefault((e["actor"], e["tool"], e["args"]), []).append(appel)
        elif e["kind"] == "tool.end":
            file = en_attente.get((e["actor"], e["tool"], e["args"]), [])
            appel = file.pop(0) if file else None
            if appel is None:   # un tool.end sans tool.start : on le garde, c'est un fait
                appel = {"tool": e["tool"], "input": {"args": e["args"]}}
                appels.append(appel)
            appel.update({"output": e.get("out"), "ok": bool(e["ok"]), "latency_ms": int(e["ms"])})
    totaux = fin["totals"]
    run = {
        "contract_version": "1.0",
        "run_id": entete["run_id"],
        "task_id": entete["task_id"],
        "status": fin["status"],
        "input": {"message": debut["title"]},
        "output": {"text": ""},           # le texte final est du contenu : il voyage par ref, pas dans le journal
        "tool_calls": appels,
        "provenance": [],                  # non dérivable des événements
        "cost": {"calls": totaux["calls"], "tokens_in": totaux["tok_in"], "tokens_out": totaux["tok_out"],
                 "eur": totaux["eur"], "wall_clock_ms": totaux["wall_clock_ms"]},
        "policy": entete["policy"],
        "human_interventions": totaux["human_interventions"],
    }
    if run["status"] == "cancelled":
        run["cancelled"] = True
    return run


def plier_fichiers(chemins, schema_evenements, contrat):
    """Tous les fichiers, ou rien : un run plié qui ne passe pas le contrat n'est pas écrit."""
    runs = []
    for chemin in chemins:
        entete, evenements = charger(chemin, schema_evenements)
        run = plier(entete, evenements)
        erreurs = validate(run, contrat)
        if erreurs:
            raise ValueError(f"{chemin} : le run plié ne passe pas le contrat de run : " + "; ".join(erreurs[:5]))
        runs.append(run)
    return runs


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("fichiers", nargs="+", help="*.events.jsonl")
    p.add_argument("--out", help="runs.jsonl à écrire (défaut : stdout)")
    a = p.parse_args(argv)
    try:
        runs = plier_fichiers(a.fichiers, charger_schema("run_events.schema.json"), charger_schema("run_contract.schema.json"))
    except (OSError, ValueError, KeyError) as e:
        print(f"refusé — {e}", file=sys.stderr)
        return 2
    texte = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in runs)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(texte)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Lancer, voir passer**

Run: `cd D:/HorusCoachIA/harnais && python3 -m unittest discover -s eval/tests -k Plier -k Evenements -v`
Expected: 16 OK.

- [ ] **Step 5: Commit (harnais)**

```bash
cd D:/HorusCoachIA/harnais
git add eval/plier_evenements.py eval/tests/test_eval.py
git commit -m "plier_evenements : evenements -> runs resumes, juges par run_tasks_eval

Un run par fichier, conforme au contrat 1.0 ou rien n'est ecrit. Les
appels d'outils s'apparient par (actor, tool, args) : un tool.start
refuse par un hook devient un appel ok: false sans latence, a sa place.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10: `deplier_runs.py` — runs résumés → événements, et l'aller-retour

**Files:**
- Create: `harnais/eval/deplier_runs.py`
- Test: `harnais/eval/tests/test_eval.py`

**Interfaces:**
- Consumes: `plier_evenements.charger_schema`, `verifier_evenements`, `plier` ; `jsonschema_lite.validate`.
- Produces:
  - `deplier(run) -> (entete, evenements)` — la silhouette : en-tête, `run.start` (`t=0`, `ref="deplie:<run_id>"`), par appel un `tool.start`/`tool.end` séparés de `latency_ms`, `run.end` à `t = cost.wall_clock_ms`. `origin: "observed"` partout, un seul acteur `policy.agent`.
  - `main(argv) -> int` — CLI `runs.jsonl --out DIR` : un `DIR/<run_id>.events.jsonl` par run ; code 2 si un run d'entrée ne passe pas le contrat ou si une silhouette ne passe pas `verifier_evenements`.
  - Invariant testé : `plier(deplier(run))` conserve `run_id`, `task_id`, `status`, `tool_calls[].tool`, `tool_calls[].ok`, `cost`, `policy`, `human_interventions`.

- [ ] **Step 1: Les tests**

Compléter l'import : `import run_eval, run_tasks_eval, jsonschema_lite, check_tool_schemas, plier_evenements, deplier_runs  # noqa: E402`

Ajouter après `Plier` :

```python
class Deplier(unittest.TestCase):
    """deplier puis plier conserve les champs transportés — les deux scripts parlent du même objet."""
    TRANSPORTES = ("run_id", "task_id", "status", "cost", "policy", "human_interventions")

    @classmethod
    def setUpClass(cls):
        cls.schema = plier_evenements.charger_schema("run_events.schema.json")
        cls.runs = run_tasks_eval.load_jsonl(RUNS)

    def test_aller_retour_sur_les_dix_runs(self):
        self.assertEqual(len(self.runs), 10)
        for run in self.runs:
            entete, evs = deplier_runs.deplier(run)
            plier_evenements.verifier_evenements(entete, evs, self.schema, nom=run["run_id"])
            retour = plier_evenements.plier(entete, evs)
            for k in self.TRANSPORTES:
                self.assertEqual(retour[k], run[k], f"{run['run_id']}.{k}")
            self.assertEqual([c["tool"] for c in retour["tool_calls"]], [c["tool"] for c in run["tool_calls"]])
            self.assertEqual([c["ok"] for c in retour["tool_calls"]], [c["ok"] for c in run["tool_calls"]])

    def test_la_silhouette_se_dit(self):
        entete, evs = deplier_runs.deplier(self.runs[0])
        self.assertEqual(evs[0]["ref"], "deplie:run-t-01-001"); self.assertEqual(evs[0]["t"], 0)
        self.assertEqual(evs[-1]["t"], self.runs[0]["cost"]["wall_clock_ms"])
        self.assertEqual(entete["agents"], [{"id": "assistant-acces", "role": "assistant-acces", "depth": 0}])
        self.assertTrue(all(e["origin"] == "observed" for e in evs))

    def test_cli_un_fichier_par_run(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(deplier_runs.main([RUNS, "--out", d]), 0)
            fichiers = sorted(os.listdir(d))
            self.assertEqual(len(fichiers), 10); self.assertIn("run-t-01-001.events.jsonl", fichiers)
            plier_evenements.charger(os.path.join(d, fichiers[0]), self.schema)

    def test_cli_refuse_un_run_hors_contrat(self):
        with tempfile.TemporaryDirectory() as d:
            mauvais = os.path.join(d, "r.jsonl")
            open(mauvais, "w", encoding="utf-8").write(json.dumps({"run_id": "x"}) + "\n")
            self.assertEqual(deplier_runs.main([mauvais, "--out", os.path.join(d, "out")]), 2)
```

- [ ] **Step 2: Lancer, voir échouer**

Run: `cd D:/HorusCoachIA/harnais && python3 -m unittest discover -s eval/tests -k Deplier -v`
Expected: `ImportError: No module named deplier_runs`.

- [ ] **Step 3: Écrire `deplier_runs.py`**

```python
#!/usr/bin/env python3
"""Déplie des runs résumés en événements : pour regarder dans Ruche ce que les oracles ont jugé.

Entrée : un runs.jsonl conforme à eval/schemas/run_contract.schema.json.
Sortie : un <run_id>.events.jsonl par run, conforme à eval/schemas/run_events.schema.json.

    python3 eval/deplier_runs.py eval/fixtures/runs_tasks.jsonl --out runs/
    # puis dans Ruche : ?run=…/run-t-03-001.events.jsonl&eval=…/judge.jsonl

Ce n'est pas une trace, c'est une silhouette : un seul acteur, run.start à
t = 0, une paire tool.start / tool.end par appel séparée de latency_ms,
run.end à t = cost.wall_clock_ms. Le fichier le dit : run.start porte
ref = "deplie:<run_id>". L'invariant testé : plier(deplier(run)) rend les
champs transportés (run_id, task_id, status, outils et ok, cost, policy,
human_interventions).

Stdlib uniquement.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from jsonschema_lite import validate  # noqa: E402
from plier_evenements import charger_schema, verifier_evenements  # noqa: E402


def deplier(run):
    """(en-tête, événements) — la silhouette d'un run résumé."""
    run_id, agent = run["run_id"], run["policy"]["agent"]
    entete = {"run_id": run_id, "task_id": run["task_id"], "contract_version": 1,
              "agents": [{"id": agent, "role": agent, "depth": 0}], "policy": run["policy"]}
    evenements = []
    horloge = [0]

    def emettre(kind, **champs):
        e = {"v": 1, "seq": len(evenements), "t": horloge[0], "run": run_id, "actor": agent, "origin": "observed", "kind": kind}
        e.update(champs)
        evenements.append(e)

    emettre("run.start", ref=f"deplie:{run_id}", task=run["task_id"], title=run["input"]["message"], policy=run["policy"])
    for appel in run["tool_calls"]:
        args = json.dumps(appel["input"], ensure_ascii=False, sort_keys=True)
        emettre("tool.start", tool=appel["tool"], args=args)
        latence = int(appel.get("latency_ms", 0))
        horloge[0] += latence
        fin = {"tool": appel["tool"], "args": args, "ok": bool(appel["ok"]), "ms": latence}
        if appel["output"] is not None:
            fin["out"] = json.dumps(appel["output"], ensure_ascii=False, sort_keys=True)
        emettre("tool.end", **fin)
    cout = run["cost"]
    horloge[0] = cout["wall_clock_ms"]
    emettre("run.end", status=run["status"],
            totals={"calls": cout["calls"], "tok_in": cout["tokens_in"], "tok_out": cout["tokens_out"],
                    "eur": cout["eur"], "wall_clock_ms": cout["wall_clock_ms"],
                    "human_interventions": run["human_interventions"]})
    return entete, evenements


def nom_de_fichier(run_id):
    return re.sub(r"[^A-Za-z0-9._-]", "_", run_id) + ".events.jsonl"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("runs", help="runs.jsonl au format du contrat de run")
    p.add_argument("--out", required=True, help="dossier de sortie, un .events.jsonl par run")
    a = p.parse_args(argv)
    contrat, schema = charger_schema("run_contract.schema.json"), charger_schema("run_events.schema.json")
    try:
        with open(a.runs, encoding="utf-8") as f:
            runs = [json.loads(l) for l in f if l.strip()]
        fichiers = []
        for i, run in enumerate(runs):
            erreurs = validate(run, contrat)
            if erreurs:
                raise ValueError(f"{a.runs} ligne {i + 1} : hors contrat de run : " + "; ".join(erreurs[:5]))
            entete, evenements = deplier(run)
            verifier_evenements(entete, evenements, schema, nom=run["run_id"])
            fichiers.append((nom_de_fichier(run["run_id"]), [entete] + evenements))
    except (OSError, ValueError, KeyError) as e:
        print(f"refusé — {e}", file=sys.stderr)
        return 2
    os.makedirs(a.out, exist_ok=True)
    for nom, lignes in fichiers:
        with open(os.path.join(a.out, nom), "w", encoding="utf-8") as f:
            f.write("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lignes))
    print(f"{len(fichiers)} run(s) dépliés dans {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Lancer, voir passer**

Run: `cd D:/HorusCoachIA/harnais && python3 -m unittest discover -s eval/tests -k Deplier -v`
Expected: 4 OK.

- [ ] **Step 5: Commit (harnais)**

```bash
cd D:/HorusCoachIA/harnais
git add eval/deplier_runs.py eval/tests/test_eval.py
git commit -m "deplier_runs : runs resumes -> evenements, pour les regarder dans Ruche

Une silhouette, pas une trace : un acteur, run.start a t=0, une paire
tool.start/tool.end par appel, run.end a wall_clock_ms. L'aller-retour
plier(deplier(run)) est teste sur les dix runs de fixtures.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 11: `harnais.py` — le noyau gagne trois scripts et deux schémas ; pose dans oneiros

**Files:**
- Modify: `harnais/harnais.py:41-56` (liste `NOYAU`)
- Modify: `harnais/LISEZ-MOI.md` (section « Ce qui est à qui »)
- Effet dans `oneiros/eval/**` via `installer --forcer`

**Interfaces:**
- Produces: `oneiros/eval/{juge_local,plier_evenements,deplier_runs}.py`, `oneiros/eval/schemas/{run_events,verdicts}.schema.json`, `oneiros/eval/fixtures/demo.events.jsonl` ; `harnais.py verifier --projet ../oneiros` → 0.

- [ ] **Step 1: `NOYAU`**

Dans `harnais/harnais.py`, après la ligne `("eval/width_report.py", "eval/width_report.py"),` ajouter :

```python
    ("eval/juge_local.py", "eval/juge_local.py"),
    ("eval/plier_evenements.py", "eval/plier_evenements.py"),
    ("eval/deplier_runs.py", "eval/deplier_runs.py"),
```

et après `("eval/schemas/run_contract.schema.json", "eval/schemas/run_contract.schema.json"),` :

```python
    ("eval/schemas/run_events.schema.json", "eval/schemas/run_events.schema.json"),
    ("eval/schemas/verdicts.schema.json", "eval/schemas/verdicts.schema.json"),
```

(`eval/fixtures` est déjà un dossier du noyau : `demo.events.jsonl` suit.)

- [ ] **Step 2: `LISEZ-MOI.md`**

Dans « Ce qui est à qui », remplacer la ligne `eval/schemas/run_contract.schema.json                 → le noyau` par :

```
eval/schemas/run_contract.schema.json   le run RÉSUMÉ, pour juger       → le noyau
eval/schemas/run_events.schema.json     le run en ÉVÉNEMENTS, pour voir  → le noyau
eval/schemas/verdicts.schema.json       une ligne de verdict par cas     → le noyau
eval/plier_evenements.py  eval/deplier_runs.py   d'une projection à l'autre → le noyau
eval/juge_local.py        le juge hors système : Qwen sur le Mac         → le noyau
```

- [ ] **Step 3: Poser, tester dans oneiros, mesurer la dérive**

```bash
cd D:/HorusCoachIA/harnais
python3 harnais.py installer --projet ../oneiros --hooks sh --forcer
python3 harnais.py verifier --projet ../oneiros ; echo "verifier=$?"
cd ../oneiros && python3 -m unittest discover -s eval/tests 2>&1 | tail -4
```

Expected: `verifier=0` ; la suite oneiros : `Ran 49 tests` (17 d'avant + 3 JugeParCas + 6 JugeLocal + 3 SchemaLite + 10 Evenements + 6 Plier + 4 Deplier) et **`OK (skipped=1)`** — zéro échec, y compris `test_judge_cmd_contract` qui échouait avant.

Run: `git -C D:/HorusCoachIA/oneiros status --short eval`
Expected: uniquement des `M`/`??` sous `eval/` (scripts, schémas, fixture, test).

- [ ] **Step 4: Commits (harnais, puis oneiros avec pathspec)**

```bash
cd D:/HorusCoachIA/harnais
git add harnais.py LISEZ-MOI.md
git commit -m "Le noyau gagne trois scripts et deux schemas

juge_local, plier_evenements, deplier_runs, run_events et verdicts se
posent par installer et se mesurent par verifier. mac-ia n'y entre pas.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
cd ../oneiros
git add eval
git commit -m "Poser le harnais du 12 septembre : juge local, contrats d'evenements et de verdicts

harnais.py installer --forcer ; verifier sort en 0 ; la suite eval passe,
y compris test_judge_cmd_contract qui tombait sous Windows (cp1252).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" -- eval
```

**Palier 3 franchi quand** : `verifier=0`, `python3 harnais/mac-ia/tests/test_bridge.py` → 48/48, `npm test` dans `ruche/` → 10 passed.

---

### Task 12: Ruche — `?eval=`, le glisser-déposer des verdicts

**Files:**
- Create: `ruche/src/core/verdicts.ts`
- Modify: `ruche/src/ui/panels.ts` (ajout `renderVerdict`)
- Modify: `ruche/src/main.ts` (imports, `verdicts`, `runCourant`, `appliquerVerdict`, `deposer`, amorçage)
- Modify: `ruche/index.html:13` (badge `#verdict`)
- Modify: `ruche/src/style.css` (classes `.verdict`, `.pass`, `.fail`)
- Create: `ruche/test/verdicts.test.ts`

**Interfaces:**
- Consumes: `RunFile`, `RunEvent` d'`events.ts` ; `parseJsonl`.
- Produces: `parseVerdicts(text: string): Verdict[]` (lève sur `task_id` absent, `pass` non booléen, `reason` vide), `verdictFor(verdicts, taskId): Verdict | null`, `taskOf(run: RunFile): string` (le `task` de `run.start`, sinon `task_id` de l'en-tête), `loadVerdicts(url): Promise<Verdict[]>`, `renderVerdict(badge, task, v)`.

- [ ] **Step 1: Le test**

`ruche/test/verdicts.test.ts` :

```ts
/**
 * Les verdicts colorent le bon run — et un verdict orphelin n'est pas une erreur.
 * Format : harnais/eval/schemas/verdicts.schema.json, une ligne par cas.
 */

import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { parseJsonl } from '../src/core/sources.js';
import { parseVerdicts, taskOf, verdictFor } from '../src/core/verdicts.js';

const run = parseJsonl(readFileSync('public/demo-run.jsonl', 'utf8'));
const verdicts = parseVerdicts([
  '{"task_id": "T-07", "pass": false, "reason": "le schéma a été écrit à la main avant d\'être régénéré"}',
  '{"task_id": "T-99", "pass": true, "reason": "orphelin : aucun run ne porte ce cas"}',
].join('\n'));

describe('verdicts', () => {
  it('le run prend le verdict dont le task_id est le task de son run.start', () => {
    expect(taskOf(run)).toBe('T-07');
    const v = verdictFor(verdicts, taskOf(run));
    expect(v?.pass).toBe(false);
    expect(v?.reason).toContain('écrit à la main');
  });

  it('un verdict orphelin ne dérange personne, un run sans verdict reste neutre', () => {
    expect(verdicts).toHaveLength(2);
    expect(verdictFor(verdicts, 'T-01')).toBeNull();
  });

  it('un verdict sans raison, ou sans pass booléen, est refusé', () => {
    expect(() => parseVerdicts('{"task_id": "T-01", "pass": true, "reason": ""}')).toThrow(/raison/);
    expect(() => parseVerdicts('{"task_id": "T-01", "pass": "oui", "reason": "x"}')).toThrow(/booléen/);
    expect(() => parseVerdicts('{"pass": true, "reason": "x"}')).toThrow(/task_id/);
  });
});
```

- [ ] **Step 2: Lancer, voir échouer**

Run: `cd D:/HorusCoachIA/ruche && npm test`
Expected: `verdicts.test.ts` échoue à l'import (`Cannot find module '../src/core/verdicts.js'`).

- [ ] **Step 3: `src/core/verdicts.ts`**

```ts
/**
 * LES VERDICTS
 *
 * Une ligne par cas, au format harnais/eval/schemas/verdicts.schema.json :
 *   {"task_id": "T-03", "pass": false, "reason": "…"}
 *
 * Ruche ne juge pas : elle colore. Le run dont le `task` de `run.start` est
 * un `task_id` prend la couleur du verdict, et montre `reason` au survol.
 * Un verdict sans run, ou un run sans verdict, reste neutre.
 */

import type { RunEvent, RunFile } from './events.js';

export interface Verdict {
  task_id: string;
  pass: boolean;
  reason: string;
}

export function parseVerdicts(text: string): Verdict[] {
  const out: Verdict[] = [];
  const lines = text.split('\n').filter(l => l.trim().length > 0);
  lines.forEach((l, i) => {
    const v = JSON.parse(l) as Partial<Verdict>;
    if (typeof v.task_id !== 'string' || v.task_id.length === 0) throw new Error(`verdict ${i + 1} : task_id manquant`);
    if (typeof v.pass !== 'boolean') throw new Error(`verdict ${i + 1} : pass doit être un booléen`);
    if (typeof v.reason !== 'string' || v.reason.trim().length === 0) {
      throw new Error(`verdict ${i + 1} : sans raison — un verdict sans explication ne se conteste pas`);
    }
    out.push({ task_id: v.task_id, pass: v.pass, reason: v.reason });
  });
  return out;
}

/** Le cas d'un run : le `task` de son run.start, sinon le task_id de l'en-tête. */
export function taskOf(run: RunFile): string {
  const start = run.events.find((e): e is Extract<RunEvent, { kind: 'run.start' }> => e.kind === 'run.start');
  return start?.task ?? run.task_id;
}

export function verdictFor(verdicts: readonly Verdict[], taskId: string): Verdict | null {
  return verdicts.find(v => v.task_id === taskId) ?? null;
}

export async function loadVerdicts(url: string): Promise<Verdict[]> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} : ${res.status}`);
  return parseVerdicts(await res.text());
}
```

- [ ] **Step 4: Le badge — `panels.ts`, `index.html`, `style.css`**

`ruche/src/ui/panels.ts`, ajouter l'import et la fonction :

```ts
import type { Verdict } from '../core/verdicts.js';

/** Le verdict du run courant : couleur sur le badge et sur le titre, raison au survol. */
export function renderVerdict(badge: HTMLElement, task: HTMLElement, v: Verdict | null): void {
  badge.classList.remove('pass', 'fail');
  task.classList.remove('pass', 'fail');
  if (!v) { badge.hidden = true; badge.textContent = ''; badge.title = ''; return; }
  const cls = v.pass ? 'pass' : 'fail';
  badge.hidden = false;
  badge.textContent = v.pass ? '✔ juge : réussi' : '✘ juge : échec';
  badge.title = v.reason;
  badge.classList.add(cls);
  task.classList.add(cls);
}
```

`ruche/index.html`, après `<span id="task" class="task"></span>` :

```html
      <span id="verdict" class="verdict" hidden></span>
```

et l'attribut du sélecteur de fichier : `accept=".jsonl,.json"` reste — les `.verdicts.jsonl` passent.

`ruche/src/style.css`, après la règle `.src{…}` :

```css
.verdict{font-family:var(--mono);font-size:11px;padding:2px 8px;border:1px solid var(--line);border-radius:4px;cursor:help;white-space:nowrap}
.verdict.pass,.task.pass{color:#6fd39a;border-color:#6fd39a}
.verdict.fail,.task.fail{color:var(--bad);border-color:var(--bad)}
```

- [ ] **Step 5: `main.ts` — charger, appliquer, déposer**

Imports, après `import { renderAgents, renderAlert, renderLog } from './ui/panels.js';` (remplacer cette ligne) :

```ts
import { renderAgents, renderAlert, renderLog, renderVerdict } from './ui/panels.js';
import { loadVerdicts, parseVerdicts, taskOf, verdictFor } from './core/verdicts.js';
import type { Verdict } from './core/verdicts.js';
```

Dans le commentaire d'en-tête, compléter la liste des sources :

```ts
 *   - ?run=<chemin>        un fichier .events.jsonl (exporter-run, ou deplier_runs.py du harnais)
 *   - ?eval=<chemin>       un verdicts.jsonl : le run prend la couleur de son verdict
 *   - un .jsonl déposé     glisser-déposer, ou le bouton « Ouvrir un run » ;
 *                          un *.verdicts.jsonl déposé s'applique au run courant
 *   - rien                 le run de démonstration
```

Après `let demonter: (() => void) | null = null;` :

```ts
/** Les verdicts (?eval= ou déposés) et le run qu'ils colorent. Ruche ne juge pas, elle montre. */
let verdicts: Verdict[] = [];
let runCourant: RunFile | null = null;

function appliquerVerdict(): void {
  renderVerdict($('verdict'), $('task'), runCourant ? verdictFor(verdicts, taskOf(runCourant)) : null);
}
```

Dans `monter`, juste après `demonter?.();` : `runCourant = run;` — et juste après le `refresh();` final (avant `demonter = () => {`) : `appliquerVerdict();`.

Remplacer les deux gestionnaires de fichiers (drop et picker) par :

```ts
/** Un fichier déposé : des verdicts s'il se termine en .verdicts.jsonl, un run sinon. */
function deposer(f: File): void {
  f.text().then(t => {
    if (!f.name.endsWith('.verdicts.jsonl')) { depuisTexte(t, f.name); return; }
    try {
      verdicts = parseVerdicts(t);
      appliquerVerdict();
    } catch (err: unknown) {
      afficherErreur(`${f.name} illisible : ${String(err)}`);
    }
  });
}

/* glisser-déposer sur toute la page, plus un bouton pour ceux qui ne devinent pas */
addEventListener('dragover', e => { e.preventDefault(); document.body.classList.add('drop'); });
addEventListener('dragleave', () => document.body.classList.remove('drop'));
addEventListener('drop', e => {
  e.preventDefault();
  document.body.classList.remove('drop');
  const f = e.dataTransfer?.files?.[0];
  if (f) deposer(f);
});

const picker = document.getElementById('file');
if (picker instanceof HTMLInputElement) {
  picker.addEventListener('change', () => {
    const f = picker.files?.[0];
    if (f) deposer(f);
  });
}
```

Remplacer les deux dernières lignes (`const demande = …` et `void depuisUrl(…)`) par :

```ts
const params = new URLSearchParams(location.search);
void (async () => {
  await depuisUrl(params.get('run') ?? '/demo-run.jsonl');
  const evalUrl = params.get('eval');
  if (!evalUrl) return;
  try {
    verdicts = await loadVerdicts(evalUrl);
    appliquerVerdict();
  } catch (err: unknown) {
    afficherErreur(`${evalUrl} illisible : ${String(err)}`);
  }
})();
```

- [ ] **Step 6: Typer, tester**

```bash
cd D:/HorusCoachIA/ruche
npx tsc --noEmit ; echo "tsc=$?"
npm test
```

Expected: `tsc=0` ; `13 passed`.

- [ ] **Step 7: Commit (ruche)**

```bash
cd D:/HorusCoachIA/ruche
git add src/core/verdicts.ts src/ui/panels.ts src/main.ts index.html src/style.css test/verdicts.test.ts
git commit -m "?eval= : le run prend la couleur de son verdict

verdicts.jsonl au format du harnais, par URL ou glisser-depose d'un
*.verdicts.jsonl. Le run dont run.start.task est un task_id se colore,
la raison s'affiche au survol. Un verdict orphelin n'est pas une erreur.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 13: Documentation, et le palier 4 à l'œil

**Files:**
- Modify: `ruche/README.md`
- Modify: `coachingia/docs/ruche-et-le-harnais.md` (§3)

- [ ] **Step 1: `ruche/README.md`**

Remplacer le bloc « **Sur une vraie session**, depuis la racine du dépôt : … » jusqu'à la ligne `glisser-déposer sur la page (bouton « Ouvrir un run… » pour les mêmes effets).` par :

````markdown
**Sur une vraie session**, depuis la racine de `coachingia` (dépôt frère) :

```powershell
dotnet run --project src/CoachingIA.Cli -- exporter-run --out ..\ruche\public\runs
```

puis `http://localhost:5173/?run=runs/<identifiant>.events.jsonl`, ou simplement
le glisser-déposer sur la page (bouton « Ouvrir un run… » pour les mêmes effets).

**Les évals dans la ruche.** Un `verdicts.jsonl` (une ligne
`{"task_id", "pass", "reason"}` par cas, format `harnais/eval/schemas/verdicts.schema.json`)
colore le run dont le `task` correspond ; la raison s'affiche au survol du badge.

```
?run=runs/run-t-03-001.events.jsonl&eval=runs/judge.jsonl
```

ou un fichier `*.verdicts.jsonl` glissé sur la page. Pour voir les runs des
oracles du harnais sans attendre une session réelle :

```bash
python3 ../harnais/eval/deplier_runs.py ../harnais/eval/fixtures/runs_tasks.jsonl --out public/runs
cp ../harnais/eval/fixtures/judge.jsonl public/runs/judge.verdicts.jsonl
```
````

Dans « ## 1 · `src/core/events.ts` — le contrat », après le tableau, ajouter :

```markdown
**Le schéma est la source, ce fichier est le miroir.** Le contrat vit dans
`harnais/eval/schemas/run_events.schema.json` ; `test/contrat.test.ts` échoue
si la liste des `kind` diffère dans un sens ou dans l'autre, ou si la démo ne
passe pas le schéma. Sans le harnais à côté, le test est sauté avec un message.
La `policy` de l'en-tête a la forme de celle du contrat de run : c'est ce qui
permet à `harnais/eval/plier_evenements.py` de la recopier sans l'inventer.
```

Dans « ### Le contrat en double » (section 7), remplacer le paragraphe par :

```markdown
`harnais/eval/schemas/run_events.schema.json` (la source), `src/core/events.ts`
(ici) et `Transcripts/RunEvent.cs` (côté C#) décrivent la même chose. Deux
définitions dérivent toujours ; trois, à coup sûr. Deux tests s'y opposent :
`test/contrat.test.ts` compare `events.ts` au schéma, `RunExportTests` compare
le C# à `events.ts`. C'est le même geste que « un outil est un type », appliqué
à l'événement.
```

Dans « Le principe », remplacer `Le projet, c'est le journal d'événements. La 3D n'en est qu'un lecteur.` par `Le projet, c'est le journal d'événements — un contrat du harnais. La 3D n'en est qu'un lecteur ; chaque producteur (coachingia, oneiros, deplier_runs.py) l'écrit, Ruche ne fait que lire.`

- [ ] **Step 2: `coachingia/docs/ruche-et-le-harnais.md` §3**

Remplacer, dans « ## 3. Ce que Ruche devient : une amputation, pas un import », la phrase d'ouverture et le bloc d'arborescence par :

````markdown
Ruche n'a pas de « moitié basse » à perdre : elle lit le contrat du harnais, et
chaque producteur l'écrit. Depuis le 12 septembre elle est un dépôt frère,
`HorusCoachIA/ruche/`, et n'est plus sous `web/` (voir
`harnais/docs/superpowers/specs/2026-09-12-harnais-partage-design.md`).

```
HorusCoachIA/
  harnais/eval/schemas/run_events.schema.json   ← LE CONTRAT (source)
  harnais/eval/schemas/verdicts.schema.json     ← une ligne de verdict par cas
  harnais/eval/plier_evenements.py              ← événements → runs résumés, pour juger
  harnais/eval/deplier_runs.py                  ← runs résumés → événements, pour voir
  ruche/                                        ← le lecteur, dépôt à lui seul
    src/core/events.ts                          ← MIROIR du schéma, vérifié par test/contrat.test.ts
    src/core/verdicts.ts                        ← ?eval=, la couleur d'un verdict
    tools/make-demo-trace.mjs                   ← la démo, pour les tests
  coachingia/
    _horus/                                     ← quarantaine (§2.1)
    src/CoachingIA.Harness.Core/Transcripts/RunExporter.cs  ← LE CHAÎNON MANQUANT, écrit contre run_events.schema.json
    web/prototype/graphe.html                   ← existant, autre sujet, ne pas toucher
```
````

Et dans le paragraphe « **Le contrat en double.** … » de la même section, remplacer la première phrase par : `**Le contrat en trois.** Le schéma du harnais (source), \`events.ts\` (TypeScript) et \`RunEvent\` (C#) vont décrire la même chose.` — le reste du paragraphe (les trois issues) reste.

Ce fichier n'est pas suivi par git dans coachingia et le dépôt porte une réorganisation non commitée : **on l'édite, on ne le commite pas** — c'est au propriétaire du dépôt.

- [ ] **Step 3: Commit (ruche)**

```bash
cd D:/HorusCoachIA/ruche
git add README.md
git commit -m "README : Ruche lit le contrat du harnais, ?eval= et deplier_runs

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Palier 4, à l'œil**

```bash
cd D:/HorusCoachIA/ruche
python3 ../harnais/eval/deplier_runs.py ../harnais/eval/fixtures/runs_tasks.jsonl --out public/runs
cp ../harnais/eval/fixtures/judge.jsonl public/runs/judge.verdicts.jsonl
npm run dev
```

Ouvrir `http://localhost:5173/?run=runs/run-t-03-001.events.jsonl&eval=runs/judge.verdicts.jsonl`.
*Franchi quand* : le run s'ouvre (un acteur `assistant-acces`, une barre d'outil), le badge est **rouge « ✘ juge : échec »** et le survol montre « la source de la raison n'est pas indiquée ». Puis `?run=runs/run-t-01-001.events.jsonl&eval=…` : badge vert. Puis glisser `public/runs/judge.verdicts.jsonl` sur la démo T-07 : aucun badge (verdict orphelin, run sans verdict — neutre, pas d'erreur). Faire les dix : chaque `run-t-XX-001.events.jsonl` s'ouvre sans message d'erreur.

- [ ] **Step 5: État final des quatre dépôts**

```bash
cd D:/HorusCoachIA
git -C harnais status --short          # attendu : seulement ?? docs/ (spec + plan, à committer avec ce plan)
git -C ruche status --short            # attendu : vide (public/runs/ est ignoré)
git -C oneiros status --short          # attendu : les 4 fichiers modifiés du propriétaire, rien sous eval/ ni mac-ia/
git -C coachingia status --short | grep -v "^R\|^RM\|^ M .github\|^ M claude"   # attendu : ?? docs/ruche-et-le-harnais.md seulement ; plus de web/ruche
python3 harnais/harnais.py verifier --projet oneiros ; echo "verifier=$?"       # 0
```

Puis committer la spec et ce plan dans le harnais :

```bash
cd D:/HorusCoachIA/harnais
git add docs
git commit -m "Spec et plan : un harnais pour deux produits

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Hors plan, et pourquoi

- **Palier 1** (zéro code) : poser `ANTHROPIC_BASE_URL=http://192.168.1.50:1235` et lancer `coachingia evaluer --juge` — c'est une manipulation, pas une tâche de ce plan. *Franchi quand* le rapport de coachingia porte un avis du juge de réécriture et LM Studio montre l'appel.
- **Palier 5** (`RunExporter.cs` écrit contre `run_events.schema.json`) : côté coachingia, palier B de son document.
- **La projection `verdict.json` → `verdicts.jsonl`** : côté coachingia, quand quelqu'un voudra voir sa campagne dans Ruche. Le format est fixé ici.
- **Le runner d'oneiros** qui émettrait des événements : lot L3+ de `TASKS.md`.
- **`test_eval.py` entièrement vert dans `harnais/` lui-même** : `RetrievalOracle.test_cli_from_file_offline` et `ToolIsAType` demandent `golden_set.jsonl` et `src/Horus.Tools/` qu'un projet possède et que le harnais n'a pas. La règle reste : la suite se vérifie dans le projet posé (oneiros), `-k` sert au développement.
