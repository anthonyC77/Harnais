"""Tests de la boucle d'apprentissage — stdlib, sans réseau, sur eval/fixtures/sessions.
`python3 -m unittest discover -s eval/tests`"""
import json, os, shutil, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); EVAL = os.path.dirname(HERE); PROJECT = os.path.dirname(EVAL)
sys.path.insert(0, EVAL)
import lire_transcripts  # noqa: E402

SESSIONS = os.path.join(EVAL, "fixtures", "sessions")


def _session(nom):
    return lire_transcripts.lire_session(os.path.join(SESSIONS, nom + ".jsonl"))


class LireTranscripts(unittest.TestCase):
    def test_ignore_le_bruit_et_la_ligne_tronquee(self):
        s = _session("s1-chere")
        self.assertEqual(s.session_id, "s1-chere"); self.assertEqual(s.projet, "sessions")
        # 4 messages humains : la sidechain, les titres et la ligne tronquée ne comptent pas.
        self.assertEqual([m.texte for m in s.humains()][:2], ["Ajoute la validation des badges dans le service", "non, pas ça : la validation va dans b.py"])
        self.assertEqual(len(s.humains()), 4)

    def test_usage_compte_une_fois_par_requete(self):
        # 10 requêtes API, dont une à deux blocs (thinking + text) : 11 entrées assistant, 10 usages.
        # Plus un sous-agent (une requête, deux entrées) dont l'usage est facturé à la session.
        s = _session("s1-chere")
        self.assertEqual(s.requetes, 10)
        self.assertEqual(s.sous_agents, {"transcripts": 1, "requetes": 1})
        self.assertEqual(s.usage_total(), {"input_tokens": 22000, "cache_creation_input_tokens": 220000,
                                           "cache_read_input_tokens": 440000, "output_tokens": 11000})
        self.assertEqual(s.modeles(), {"modele-test"})
        self.assertEqual(s.usage_par_modele(), {"modele-test": s.usage_total()})

    def test_outils_fichiers_commandes(self):
        s = _session("s1-chere")
        self.assertEqual(len(s.appels_outils()), 9)
        self.assertEqual(s.fichiers_lus(), {"d:/fixture/src/a.py", "d:/fixture/src/b.py", "d:/fixture/docs/INDEX.md",
                                            "d:/fixture/src/c.md", "d:/fixture/src"})
        self.assertEqual(s.fichiers_modifies(), {"d:/fixture/src/a.py", "d:/fixture/src/b.py"})
        self.assertEqual(s.commandes(), ["python -m mypy src"])
        self.assertEqual(len(s.resultats_en_erreur()), 1)
        self.assertEqual(s.refus_permission(), 0)
        self.assertEqual(s.escalades(), 1)

    def test_refus_de_permission_et_commits(self):
        s = _session("s3-corrections")
        self.assertEqual(s.refus_permission(), 1)
        self.assertEqual(len(s.resultats_en_erreur()), 1)
        self.assertEqual(s.commits(), ["git commit -am 'renommage'"])
        self.assertEqual(_session("s1-chere").commits(), [])

    def test_bornes_temporelles(self):
        s = _session("s2-propre")
        self.assertEqual(s.debut.isoformat(), "2026-09-09T10:00:30+00:00")
        self.assertLess(s.debut, s.fin)
        self.assertEqual(s.semaine(), "2026-W37")
        self.assertEqual(_session("s3-corrections").semaine(), "2026-W38")

    def test_iter_sessions_ordre_chronologique(self):
        ids = [s.session_id for s in lire_transcripts.iter_sessions(SESSIONS)]
        self.assertEqual(ids, ["s1-chere", "s2-propre", "s3-corrections"])

    def test_digest_sans_resultats_ni_reflexion(self):
        d = lire_transcripts.digest(_session("s1-chere"))
        self.assertIn("[humain] non, pas ça", d)
        self.assertIn("[Read] d:/fixture/src/a.py", d)
        self.assertIn("[Bash] python -m mypy src → erreur", d)
        self.assertNotIn("contenu a", d)          # résultats d'outils : jamais
        self.assertNotIn("raisonnement", d)       # thinking : jamais
        self.assertIn("Voilà, c'est dans b.py.", d)

    def test_digest_tronque_les_reponses_longues(self):
        s = _session("s2-propre")
        s.tours[-1].texte = "x" * 2000
        d = lire_transcripts.digest(s, limite=600)
        self.assertIn("x" * 600 + "…", d); self.assertNotIn("x" * 601, d)

    def test_fichier_illisible_donne_session_vide(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "vide.jsonl"); open(p, "w").close()
            s = lire_transcripts.lire_session(p)
            self.assertEqual(s.tours, []); self.assertIsNone(s.debut); self.assertEqual(s.usage_total()["input_tokens"], 0)
            self.assertIsNone(lire_transcripts.lire_session(os.path.join(d, "absent.jsonl")))


import mesurer_sessions  # noqa: E402

ETALON = os.path.join(EVAL, "fixtures", "apprentissage")


def _mesure(**kw):
    """Mesure les trois fixtures dans un dossier temporaire ; renvoie (code, rapports par semaine, dossier)."""
    d = tempfile.mkdtemp()
    args = ["--projet", SESSIONS, "--etalon-dir", ETALON, "--out-dir", d, "--quiet"]
    for k, v in kw.items():
        args += ["--" + k.replace("_", "-"), v]
    code = mesurer_sessions.main(args)
    rapports = {}
    for nom in sorted(os.listdir(d)):
        if nom.endswith(".json"):
            with open(os.path.join(d, nom), encoding="utf-8") as f:
                rapports[nom[:-5]] = json.load(f)
    return code, rapports, d


class MesurerSessions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.rapports, cls.dir = _mesure()
        cls.w37 = cls.rapports["semaine-2026-W37"]; cls.w38 = cls.rapports["semaine-2026-W38"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_un_fichier_json_et_md_par_semaine(self):
        self.assertEqual(sorted(self.rapports), ["semaine-2026-W37", "semaine-2026-W38"])
        self.assertTrue(os.path.exists(os.path.join(self.dir, "semaine-2026-W38.md")))

    def test_cout_par_session_selon_la_grille(self):
        s1 = next(s for s in self.w37["sessions"] if s["session"] == "s1-chere")
        self.assertAlmostEqual(s1["cout"], 1.188, places=6)
        self.assertEqual(s1["modeles_sans_prix"], [])
        self.assertEqual(s1["resultats_acceptes"], 0); self.assertEqual(s1["accepte_source"], "aucun")
        s2 = next(s for s in self.w37["sessions"] if s["session"] == "s2-propre")
        self.assertAlmostEqual(s2["cout"], 0.054, places=6)
        self.assertEqual(s2["resultats_acceptes"], 1); self.assertEqual(s2["accepte_source"], "commit")

    def test_signal_1_cout_par_resultat_accepte(self):
        self.assertAlmostEqual(self.w37["signaux"]["cout_par_resultat_accepte"], 1.242, places=6)
        self.assertAlmostEqual(self.w38["signaux"]["cout_par_resultat_accepte"], 0.072, places=6)

    def test_signal_2_temps_jusqu_au_resultat_fiable(self):
        self.assertEqual(self.w37["signaux"]["temps_resultat_fiable_min"], 4.5)   # s2 : premier message → commit
        self.assertEqual(self.w38["signaux"]["temps_resultat_fiable_min"], 7.5)

    def test_signal_3_corrections(self):
        s1 = next(s for s in self.w37["sessions"] if s["session"] == "s1-chere")
        self.assertEqual(s1["corrections"], 3)   # « non, pas ça », « corrige » après une erreur, « je t'ai dit »
        self.assertEqual(self.w37["signaux"]["corrections_repetees"], 3)
        self.assertEqual(self.w38["signaux"]["corrections_repetees"], 2)   # « non », « encore » (pas compté deux fois)

    def test_signal_4_escalade(self):
        self.assertAlmostEqual(self.w37["signaux"]["taux_escalade_humaine"], 1 / 16)
        self.assertAlmostEqual(self.w38["signaux"]["taux_escalade_humaine"], 1 / 8)

    def test_signal_5_tests(self):
        self.assertEqual(self.w37["signaux"]["part_couverte_par_tests"], 0.5)
        self.assertEqual(self.w38["signaux"]["part_couverte_par_tests"], 0.0)

    def test_signal_6_redecouverte(self):
        self.assertEqual(self.w37["signaux"]["taux_redecouverte"], 0.0)
        self.assertAlmostEqual(self.w38["signaux"]["taux_redecouverte"], 2 / 3, places=5)
        self.assertEqual(self.w38["top_redecouverts"][:2], [["d:/fixture/src/a.py", 3], ["d:/fixture/src/b.py", 3]])

    def test_delta_et_code_1_sur_degradation(self):
        self.assertIsNone(self.w37["delta"])
        d = self.w38["delta"]
        self.assertEqual(d["semaine_precedente"], "2026-W37")
        self.assertEqual(sorted(d["degrades"]), ["part_couverte_par_tests", "taux_escalade_humaine", "taux_redecouverte", "temps_resultat_fiable_min"])
        self.assertEqual(sorted(d["ameliores"]), ["corrections_repetees", "cout_par_resultat_accepte"])
        self.assertEqual(self.code, 1)

    def test_tolerance_large_donne_code_0(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "seuils.json"), "w") as f:
                json.dump({"tolerance": 100}, f)
            shutil.copy(os.path.join(ETALON, "prix.json"), d)
            code, _, out = _mesure(etalon_dir=d)
            shutil.rmtree(out, ignore_errors=True)
            self.assertEqual(code, 0)

    def test_passation_prime_sur_le_commit(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "passations"))
            with open(os.path.join(d, "passations", "s1-chere.md"), "w", encoding="utf-8") as f:
                f.write("# Passation\n\n- résultat accepté : oui\n")
            with open(os.path.join(d, "passations", "s2-propre.md"), "w", encoding="utf-8") as f:
                f.write("- Résultat accepté : NON\n")
            code, r, out = _mesure(apprentissage_dir=d)
            shutil.rmtree(out, ignore_errors=True)
            s = {x["session"]: x for x in r["semaine-2026-W37"]["sessions"]}
            self.assertEqual((s["s1-chere"]["resultats_acceptes"], s["s1-chere"]["accepte_source"]), (1, "passation"))
            self.assertEqual((s["s2-propre"]["resultats_acceptes"], s["s2-propre"]["accepte_source"]), (0, "passation"))
            self.assertAlmostEqual(r["semaine-2026-W37"]["signaux"]["cout_par_resultat_accepte"], 1.242, places=6)
            self.assertEqual(r["semaine-2026-W37"]["signaux"]["temps_resultat_fiable_min"], 12.0)   # s1 : début → fin

    def test_modele_sans_prix_est_signale_pas_tu(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "prix.json"), "w") as f:
                json.dump({"devise": "EUR", "par_million": {}}, f)
            code, r, out = _mesure(etalon_dir=d)
            shutil.rmtree(out, ignore_errors=True)
            s1 = r["semaine-2026-W37"]["sessions"][0]
            self.assertEqual(s1["cout"], 0.0); self.assertEqual(s1["modeles_sans_prix"], ["modele-test"])
            self.assertIn("modele-test", r["semaine-2026-W37"]["modeles_sans_prix"])

    def test_grille_absente_est_code_2(self):
        with tempfile.TemporaryDirectory() as d:
            code = mesurer_sessions.main(["--projet", SESSIONS, "--etalon-dir", d, "--out-dir", d, "--quiet"])
            self.assertEqual(code, 2)
            self.assertEqual(mesurer_sessions.main(["--projet", "/nulle/part", "--etalon-dir", ETALON, "--out-dir", d, "--quiet"]), 2)

    def test_depreciation_des_candidats(self):
        with tempfile.TemporaryDirectory() as d:
            cands = [
                {"id": "c-1", "statut": "promu", "promu_vers": os.path.join(d, "existe.md"), "valide_jusqua": "2099-01-01", "enonce": "a"},
                {"id": "c-2", "statut": "promu", "promu_vers": os.path.join(d, "absent.md"), "valide_jusqua": "2099-01-01", "enonce": "b"},
                {"id": "c-3", "statut": "promu", "promu_vers": os.path.join(d, "existe.md"), "valide_jusqua": "2020-01-01", "enonce": "c"},
                {"id": "c-4", "statut": "propose", "enonce": "d"},
            ]
            open(os.path.join(d, "existe.md"), "w").close()
            with open(os.path.join(d, "candidats.jsonl"), "w", encoding="utf-8") as f:
                for c in cands:
                    f.write(json.dumps(c) + "\n")
            code, r, out = _mesure(apprentissage_dir=d)
            shutil.rmtree(out, ignore_errors=True)
            with open(os.path.join(d, "candidats.jsonl"), encoding="utf-8") as f:
                apres = {c["id"]: c for c in map(json.loads, f)}
            self.assertEqual(apres["c-1"]["statut"], "promu")
            self.assertEqual(apres["c-2"]["statut"], "deprecie"); self.assertIn("absent", apres["c-2"]["motif"])
            self.assertEqual(apres["c-3"]["statut"], "deprecie"); self.assertIn("2020-01-01", apres["c-3"]["motif"])
            self.assertEqual(apres["c-4"]["statut"], "propose")
            self.assertEqual(sorted(r["semaine-2026-W38"]["deprecies"]), ["c-2", "c-3"])


if __name__ == "__main__":
    unittest.main()
