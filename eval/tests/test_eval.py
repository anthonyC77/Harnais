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


class RetrievalOracle(unittest.TestCase):
    def test_score_multi_doc_partial(self):
        item = {"id": "q", "expected_doc_ids": ["A", "B"], "must_contain": ["x"]}
        m = run_eval.score_one(item, [{"docId": "A", "score": 0.9, "text": "x"}, {"docId": "C", "score": 0.5}], 5)
        self.assertEqual(m["recall"], 0.5); self.assertEqual(m["all_hit"], 0.0); self.assertEqual(m["mrr"], 1.0); self.assertEqual(m["facts"], 1.0)

    def test_negative_uses_top_score(self):
        m = run_eval.score_one({"id": "q", "expected_doc_ids": [], "answerable": False}, [{"docId": "A", "score": 0.7}], 5)
        self.assertIsNone(m["recall"]); self.assertEqual(m["top_score"], 0.7)
        s = run_eval.summarize([m], neg_threshold=0.5); self.assertEqual(s["negative_ok"], 0.0)

    def test_compare_flags_only_drops_beyond_tolerance(self):
        regs = run_eval.compare({"recall": 0.80, "mrr": 0.99}, {"recall": 0.85, "mrr": 1.0}, 0.02)
        self.assertEqual([r["metric"] for r in regs], ["recall"])

    def test_cli_from_file_offline(self):
        with tempfile.TemporaryDirectory() as d:
            code = run_eval.main(["--from-file", os.path.join(EVAL, "fixtures", "results_retrieval.jsonl"), "--runs-dir", d, "--quiet"])
            self.assertIn(code, (0, 1)); self.assertEqual(len(os.listdir(d)), 1)

    def test_cli_missing_file_is_exit_2(self):
        self.assertEqual(run_eval.main(["--from-file", "/nonexistent.jsonl", "--quiet"]), 2)


class TasksOracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract, cls.tools = run_tasks_eval.load_schemas(os.path.join(EVAL, "schemas"))
        cls.policies = run_tasks_eval.load_json(POLICY)
        cls.golden = {t["id"]: t for t in run_tasks_eval.load_jsonl(GOLDEN)}
        cls.runs = {r["task_id"]: r for r in run_tasks_eval.load_jsonl(os.path.join(EVAL, "fixtures", "runs_tasks.jsonl"))}

    def failed(self, tid, run=None):
        A, _ = run_tasks_eval.check_task(self.golden[tid], run or self.runs[tid], self.contract, self.tools, self.policies)
        return [a["name"] for a in A if not a["ok"]]

    def test_good_run_passes(self):
        self.assertEqual(self.failed("T-01"), [])

    def test_missing_provenance_fails(self):
        self.assertIn("provenance_cites:DOC-PROC-REFABRICATION-BADGE", self.failed("T-03"))

    def test_side_effect_without_idempotency_key_fails(self):
        self.assertIn("idempotency_key[0]:creer_demande_badge", self.failed("T-06"))

    def test_tool_outside_allowlist_is_caught(self):
        run = dict(self.runs["T-01"]); run["tool_calls"] = [{"tool": "supprimer_compte", "input": {}, "output": {}, "ok": True}]
        self.assertIn("policy_allowlist", self.failed("T-01", run))

    def test_removed_property_breaks_tool_io(self):
        run = json.loads(json.dumps(self.runs["T-01"])); run["tool_calls"][0]["input"].pop("query")
        self.assertTrue(any(n.startswith("tool_io_valid[0]") for n in self.failed("T-01", run)))

    def test_contract_rejects_unknown_field(self):
        run = dict(self.runs["T-01"]); run["internal_spans"] = []
        self.assertIn("contract_valid", self.failed("T-01", run))

    def test_kappa_and_agreement(self):
        self.assertEqual(run_tasks_eval.kappa([(True, True), (False, False)]), 1.0)
        self.assertEqual(run_tasks_eval.kappa([(True, False), (False, True)]), -1.0)

    def test_cli_with_judge_file(self):
        with tempfile.TemporaryDirectory() as d:
            code = run_tasks_eval.main(["--runs", os.path.join(EVAL, "fixtures", "runs_tasks.jsonl"), "--golden", GOLDEN, "--policy", POLICY, "--judge-file", os.path.join(EVAL, "fixtures", "judge.jsonl"), "--runs-dir", d, "--quiet"])
            self.assertIn(code, (0, 1))
            out = json.load(open(os.path.join(d, os.listdir(d)[0]), encoding="utf-8"))
            self.assertEqual(out["metrics"]["n_judged"], 10); self.assertIsNotNone(out["metrics"]["agreement"])

    def test_judge_cmd_contract(self):
        cmd = f"{sys.executable} -c \"import sys,json; d=json.load(sys.stdin); print(json.dumps({{'pass': 'rubric' in d, 'reason': 'ok'}}))\""
        with tempfile.TemporaryDirectory() as d:
            self.assertIn(run_tasks_eval.main(["--runs", os.path.join(EVAL, "fixtures", "runs_tasks.jsonl"), "--golden", GOLDEN, "--policy", POLICY, "--judge-cmd", cmd, "--runs-dir", d, "--quiet"]), (0, 1))


class JugeParCas(unittest.TestCase):
    """Une panne du juge sur un cas ne jette pas les autres ; une panne sur tous rend « rien mesuré »."""
    JUGE = ("import sys, json\n"
            "sys.stdin.reconfigure(encoding='utf-8')\n"
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


class _FauxLmStudio(http.server.BaseHTTPRequestHandler):
    """LM Studio de poche : renvoie `reponse`, note chaque requête dans `recues`."""
    reponse = ""
    finish_val = "stop"
    recues = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        type(self).recues.append(json.loads(self.rfile.read(n).decode("utf-8")))
        corps = json.dumps({"choices": [{"message": {"role": "assistant", "content": type(self).reponse},
                                         "finish_reason": type(self).finish_val}]}).encode("utf-8")
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
        _FauxLmStudio.reponse, _FauxLmStudio.finish_val = "<think>je réfléchis encore", "length"
        try:
            p = self.juger()
            self.assertEqual(p.returncode, 2); self.assertIn("max_tokens", p.stderr)
        finally:
            _FauxLmStudio.finish_val = "stop"

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


class ToolIsAType(unittest.TestCase):
    def test_schema_drift_detected_when_type_changes(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "src", "Horus.Tools", "Contracts"); shutil.copytree(os.path.join(PROJECT, "src", "Horus.Tools", "Contracts"), src)
            sch = os.path.join(d, "schemas"); shutil.copytree(os.path.join(EVAL, "schemas", "tools"), sch)
            cs = os.path.join(src, "RechercherDocuments.cs"); txt = open(cs, encoding="utf-8").read()
            open(cs, "w", encoding="utf-8").write(txt.replace("int K = 5", "int K = 7"))
            problems, _ = check_tool_schemas.check(sch, os.path.join(EVAL, "tasks_golden.jsonl"), src, False)
            # x-source est relatif au projet : la source ne bouge pas là, mais la régénération diverge
            self.assertTrue(any(p["kind"] == "drift" for p in problems))

    def test_golden_references_must_exist(self):
        self.assertTrue(jsonschema_lite.property_exists(self.schema("rechercher_documents")["output"], "results.doc_id"))
        self.assertFalse(jsonschema_lite.property_exists(self.schema("rechercher_documents")["input"], "page"))

    def schema(self, name):
        return json.load(open(os.path.join(EVAL, "schemas", "tools", f"{name}.schema.json"), encoding="utf-8"))


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


@unittest.skipUnless(shutil.which("jq") and shutil.which("sh"), "sh + jq requis")
class Guardrails(unittest.TestCase):
    def hook(self, script, args, payload):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=PROJECT)
        return subprocess.run(["sh", os.path.join(PROJECT, ".claude", "hooks", script), *args], input=json.dumps(payload), capture_output=True, text=True, env=env, cwd=PROJECT).returncode

    def test_all_probes(self):
        for pr in run_tasks_eval.load_jsonl(os.path.join(EVAL, "guardrail_probes.jsonl")):
            if pr["kind"] == "hook":
                with self.subTest(pr["id"]):
                    self.assertEqual(self.hook(os.path.basename(pr["hook"]), pr.get("args", []), pr["input"]), pr["expect_exit"], pr["danger"])


if __name__ == "__main__":
    unittest.main()
