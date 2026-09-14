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
        s = _session("s1-chere")
        self.assertEqual(s.requetes, 10)
        self.assertEqual(s.usage_total(), {"input_tokens": 20000, "cache_creation_input_tokens": 200000,
                                           "cache_read_input_tokens": 400000, "output_tokens": 10000})
        self.assertEqual(s.modeles(), {"modele-test"})

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


if __name__ == "__main__":
    unittest.main()
