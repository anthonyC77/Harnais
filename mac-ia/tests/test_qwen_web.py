#!/usr/bin/env python3
"""Tests de qwen_web.py : logique serveur pure (sans réseau, sans modèle) et rendu Markdown de la page.

    python tests/test_qwen_web.py
    python -m unittest tests.test_qwen_web

Le rendu Markdown est du JavaScript embarqué dans la page : on l'extrait et on l'exécute avec node.
Sans node, ces tests-là sont sautés, pas échoués.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import qwen_web  # noqa: E402


class ConstruireRequete(unittest.TestCase):
    def test_reflexion_active_ne_touche_pas_au_message(self):
        corps = qwen_web.construire_requete([{"role": "user", "content": "Bonjour"}], "", True, 4096, 0.5)
        self.assertEqual(corps["messages"], [{"role": "user", "content": "Bonjour"}])
        self.assertEqual(corps["max_tokens"], 4096)
        self.assertEqual(corps["temperature"], 0.5)
        self.assertTrue(corps["stream"])
        self.assertEqual(corps["model"], "brain")

    def test_reflexion_coupee_prerempli_un_bloc_think_vide(self):
        # Constaté sur LM Studio (Qwen3.8) : ni /no_think ni les paramètres d'API ne coupent la réflexion ;
        # seul un tour assistant pré-rempli par un bloc <think> vide donne une réponse directe.
        messages = [
            {"role": "user", "content": "Un"},
            {"role": "assistant", "content": "Deux"},
            {"role": "user", "content": "Trois"},
        ]
        corps = qwen_web.construire_requete(messages, "", False, 4096, 0.3)
        self.assertEqual(corps["messages"][:3], messages)
        self.assertEqual(corps["messages"][3], {"role": "assistant", "content": "<think>" + chr(10) * 2 + "</think>" + chr(10) * 2})
        self.assertEqual(len(corps["messages"]), 4)
        self.assertEqual(len(messages), 3, "la liste d'origine ne doit pas être modifiée")

    def test_reflexion_active_pas_de_prefill(self):
        corps = qwen_web.construire_requete([{"role": "user", "content": "Q"}], "", True, 100, 0.3)
        self.assertEqual(corps["messages"][-1]["role"], "user")

    def test_instruction_systeme_placee_en_tete(self):
        corps = qwen_web.construire_requete([{"role": "user", "content": "Q"}], "Réponds en breton.", True, 100, 0.3)
        self.assertEqual(corps["messages"][0], {"role": "system", "content": "Réponds en breton."})
        self.assertEqual(corps["messages"][1]["content"], "Q")

    def test_instruction_systeme_vide_ignoree(self):
        corps = qwen_web.construire_requete([{"role": "user", "content": "Q"}], "   ", True, 100, 0.3)
        self.assertEqual(len(corps["messages"]), 1)

    def test_bornes_des_reglages(self):
        corps = qwen_web.construire_requete([{"role": "user", "content": "Q"}], "", True, 10 ** 9, 99)
        self.assertLessEqual(corps["max_tokens"], 32768)
        self.assertLessEqual(corps["temperature"], 2)
        corps = qwen_web.construire_requete([{"role": "user", "content": "Q"}], "", True, -5, -1)
        self.assertGreaterEqual(corps["max_tokens"], 256)
        self.assertGreaterEqual(corps["temperature"], 0)


class EcrireJournal(unittest.TestCase):
    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_un_fichier_par_echange_avec_question_reponse_et_reglages(self):
        messages = [
            {"role": "user", "content": "Première question"},
            {"role": "assistant", "content": "Première réponse"},
            {"role": "user", "content": "Deuxième question"},
        ]
        reglages = {"reflexion": False, "max_tokens": 2048, "temperature": 0.7}
        nom = qwen_web.ecrire_journal(messages, "Instruction X", "La réponse", "pensée", reglages, self.dossier)
        contenu = (self.dossier / nom).read_text(encoding="utf-8")
        self.assertTrue(nom.endswith(".md"))
        self.assertIn("Deuxième question", contenu)
        self.assertIn("La réponse", contenu)
        self.assertIn("pensée", contenu)
        self.assertIn("Instruction X", contenu)
        self.assertIn("2048", contenu)
        self.assertIn("0.7", contenu)
        self.assertIn("réflexion : non", contenu)
        # Le tour précédent apparaît comme contexte, pas comme question du jour.
        self.assertLess(contenu.index("Première question"), contenu.index("Deuxième question"))

    def test_deux_echanges_au_meme_instant_donnent_deux_fichiers(self):
        # Deux PC dont les réponses se terminent dans la même seconde : rien ne doit être écrasé.
        instant = dt.datetime(2026, 9, 14, 22, 0, 0, 123456)
        reglages = {"reflexion": True, "max_tokens": 1, "temperature": 0}
        n1 = qwen_web.ecrire_journal([{"role": "user", "content": "A"}], "", "R1", "", reglages, self.dossier, quand=instant)
        n2 = qwen_web.ecrire_journal([{"role": "user", "content": "B"}], "", "R2", "", reglages, self.dossier, quand=instant)
        self.assertNotEqual(n1, n2)
        self.assertEqual(sorted(p.name for p in self.dossier.glob("*.md")), sorted([n1, n2]))
        self.assertIn("R1", (self.dossier / n1).read_text(encoding="utf-8"))
        self.assertIn("R2", (self.dossier / n2).read_text(encoding="utf-8"))

    def test_sans_reflexion_pas_de_section_reflexion(self):
        nom = qwen_web.ecrire_journal([{"role": "user", "content": "Q"}], "", "R", "   ",
                                      {"reflexion": True, "max_tokens": 1, "temperature": 0}, self.dossier)
        self.assertNotIn("## Réflexion", (self.dossier / nom).read_text(encoding="utf-8"))

    def test_titre_du_journal_est_la_question(self):
        nom = qwen_web.ecrire_journal([{"role": "user", "content": "Quelle heure est-il ?\nseconde ligne"}], "", "R", "",
                                      {"reflexion": True, "max_tokens": 1, "temperature": 0}, self.dossier)
        self.assertEqual(qwen_web.titre_journal(self.dossier / nom), "Quelle heure est-il ?")


class FauxSegment:
    def __init__(self, text):
        self.text = text


class FauxWhisper:
    """Imite l'objet WhisperModel de faster-whisper : on vérifie le circuit, pas la reconnaissance."""
    def __init__(self):
        self.chemins = []

    def transcribe(self, chemin, **kwargs):
        self.chemins.append(chemin)
        self.kwargs = kwargs
        info = type("Info", (), {"language": "fr", "language_probability": 0.99})()
        return iter([FauxSegment(" Bonjour "), FauxSegment("le monde ")]), info


class FauxWhisperLent(FauxWhisper):
    """Compte combien de transcriptions se chevauchent : on veut toujours au plus une."""
    def __init__(self):
        super().__init__()
        self.en_cours = 0
        self.pic = 0
        self.verrou = threading.Lock()

    def transcribe(self, chemin, **kwargs):
        with self.verrou:
            self.en_cours += 1
            self.pic = max(self.pic, self.en_cours)
        time.sleep(0.05)
        with self.verrou:
            self.en_cours -= 1
        return super().transcribe(chemin, **kwargs)


class TranscrireAudio(unittest.TestCase):
    def test_deux_transcriptions_simultanees_sont_mises_en_file(self):
        faux = FauxWhisperLent()
        fils = [threading.Thread(target=qwen_web.transcrire_audio, args=(b"x", ".wav"), kwargs={"modele": faux}) for _ in range(4)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        self.assertEqual(len(faux.chemins), 4)
        self.assertEqual(faux.pic, 1, "deux transcriptions ne doivent jamais tourner en même temps")

    def test_octets_vers_texte_puis_fichier_temporaire_supprime(self):
        faux = FauxWhisper()
        texte = qwen_web.transcrire_audio(b"RIFF....", ".webm", modele=faux)
        self.assertEqual(texte, "Bonjour le monde")
        self.assertEqual(len(faux.chemins), 1)
        self.assertTrue(faux.chemins[0].endswith(".webm"))
        self.assertFalse(os.path.exists(faux.chemins[0]), "le fichier temporaire doit être effacé")
        self.assertEqual(faux.kwargs.get("language"), "fr")

    def test_audio_vide_refuse(self):
        with self.assertRaises(ValueError):
            qwen_web.transcrire_audio(b"", ".webm", modele=FauxWhisper())

    def test_extension_inconnue_refusee(self):
        with self.assertRaises(ValueError):
            qwen_web.transcrire_audio(b"x", ".exe", modele=FauxWhisper())


@unittest.skipIf(shutil.which("node") is None, "node absent")
class RenduMarkdown(unittest.TestCase):
    """Exécute la fonction JS `md()` de la page dans node."""

    @classmethod
    def setUpClass(cls):
        cls.script = qwen_web.SCRIPT_MD

    def md(self, texte):
        programme = self.script + "\nprocess.stdout.write(md(" + json.dumps(texte) + "));"
        r = subprocess.run(["node", "-e", programme], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_html_echappe(self):
        self.assertIn("&lt;script&gt;", self.md("<script>alert(1)</script>"))
        self.assertNotIn("<script>", self.md("<script>alert(1)</script>"))

    def test_gras_italique_code_en_ligne(self):
        h = self.md("du **gras**, de l'*italique* et du `code<x>`")
        self.assertIn("<strong>gras</strong>", h)
        self.assertIn("<em>italique</em>", h)
        self.assertIn("<code>code&lt;x&gt;</code>", h)

    def test_titres_et_listes(self):
        h = self.md("# Titre\n\n- un\n- deux\n\n1. a\n2. b")
        self.assertIn("<h1>Titre</h1>", h)
        self.assertIn("<ul><li>un</li><li>deux</li></ul>", h.replace("\n", ""))
        self.assertIn("<ol><li>a</li><li>b</li></ol>", h.replace("\n", ""))

    def test_bloc_de_code_garde_le_texte_brut(self):
        h = self.md("```python\nprint('**pas gras**')\n```")
        self.assertIn('<pre><code class="lang-python">print(&#39;**pas gras**&#39;)', h.replace("\n</code>", "</code>"))
        self.assertNotIn("<strong>", h)

    def test_paragraphes_et_liens(self):
        h = self.md("Voir [le site](https://exemple.fr).\n\nAutre paragraphe.")
        self.assertIn('<a href="https://exemple.fr"', h)
        self.assertEqual(h.count("<p>"), 2)

    def test_tableau(self):
        h = self.md("| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertIn("<table>", h)
        self.assertIn("<th>a</th>", h)
        self.assertIn("<td>2</td>", h)

    def test_lien_javascript_neutralise(self):
        h = self.md("[x](javascript:alert(1))")
        self.assertNotIn("javascript:", h)


class AdresseEcoute(unittest.TestCase):
    def test_par_defaut_ce_pc_seulement(self):
        self.assertEqual(qwen_web.adresse_ecoute(False), "127.0.0.1")

    def test_reseau_ouvre_a_toutes_les_interfaces(self):
        self.assertEqual(qwen_web.adresse_ecoute(True), "0.0.0.0")


class CommandeCouper(unittest.TestCase):
    """Le bouton « Couper la file » : ce qu'on envoie au Mac par SSH, sans SSH."""

    def test_pont_tue_le_pont_et_le_relance_detache(self):
        cmd = qwen_web.commande_couper("pont", "/Users/x/.lmstudio/bin/lms")
        self.assertIn("pkill -f bridge/server.py", cmd)
        self.assertIn("nohup python3 bridge/server.py", cmd)
        self.assertIn("< /dev/null &", cmd, "sinon le ssh ne rend pas la main")
        self.assertNotIn("unload", cmd)

    def test_modele_decharge_tout_puis_recharge_brain_avec_le_meme_lms(self):
        cmd = qwen_web.commande_couper("modele", "/Users/x/.lmstudio/bin/lms")
        self.assertIn('"/Users/x/.lmstudio/bin/lms" unload --all', cmd)
        self.assertIn('"/Users/x/.lmstudio/bin/lms" load "qwen3.8-27b-mlx" --identifier "brain" --context-length 65536 -y', cmd)
        self.assertNotIn("pkill", cmd)

    def test_mode_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            qwen_web.commande_couper("tout", "/x/lms")


SKILL_COMPLET = """---
name: Relecture Rust
description: Relit du code Rust.
reflexion: oui
max_tokens: 8192
temperature: 0.2
---
Tu es un relecteur Rust.

Deuxième paragraphe.
"""


class Skills(unittest.TestCase):
    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def ecrire(self, nom, contenu):
        (self.dossier / nom).write_text(contenu, encoding="utf-8")

    def test_lire_un_skill_complet(self):
        self.ecrire("rust.md", SKILL_COMPLET)
        s = qwen_web.lire_skill(self.dossier / "rust.md")
        self.assertEqual(s["id"], "rust")
        self.assertEqual(s["nom"], "Relecture Rust")
        self.assertEqual(s["description"], "Relit du code Rust.")
        self.assertEqual(s["reflexion"], True)
        self.assertEqual(s["max_tokens"], 8192)
        self.assertEqual(s["temperature"], 0.2)
        self.assertEqual(s["corps"], "Tu es un relecteur Rust.\n\nDeuxième paragraphe.")
        self.assertIsNone(s.get("erreur"))

    def test_reglages_absents_restent_a_none(self):
        self.ecrire("a.md", "---\nname: A\ndescription: d\n---\ncorps")
        s = qwen_web.lire_skill(self.dossier / "a.md")
        self.assertIsNone(s["reflexion"])
        self.assertIsNone(s["max_tokens"])
        self.assertIsNone(s["temperature"])

    def test_reflexion_non_et_valeurs_anglaises(self):
        self.ecrire("a.md", "---\nname: A\nreflexion: non\n---\nx")
        self.assertEqual(qwen_web.lire_skill(self.dossier / "a.md")["reflexion"], False)
        self.ecrire("b.md", "---\nname: B\nreflexion: false\n---\nx")
        self.assertEqual(qwen_web.lire_skill(self.dossier / "b.md")["reflexion"], False)

    def test_fichier_sans_en_tete_signale_une_erreur_sans_planter(self):
        self.ecrire("casse.md", "juste du texte")
        s = qwen_web.lire_skill(self.dossier / "casse.md")
        self.assertEqual(s["id"], "casse")
        self.assertIn("erreur", s)
        self.assertNotIn("corps", s)

    def test_nom_manquant_prend_le_nom_du_fichier(self):
        self.ecrire("sans-nom.md", "---\ndescription: d\n---\nx")
        self.assertEqual(qwen_web.lire_skill(self.dossier / "sans-nom.md")["nom"], "sans-nom")

    def test_lister_trie_par_nom_et_ignore_le_reste(self):
        self.ecrire("z.md", "---\nname: Alpha\n---\na")
        self.ecrire("a.md", "---\nname: Zoulou\n---\nz")
        self.ecrire("notes.txt", "pas un skill")
        (self.dossier / "corbeille").mkdir()
        self.ecrire("corbeille/vieux.md", "---\nname: Vieux\n---\nv")
        noms = [s["nom"] for s in qwen_web.lister_skills(self.dossier)]
        self.assertEqual(noms, ["Alpha", "Zoulou"])

    def test_lister_dossier_absent_donne_une_liste_vide(self):
        self.assertEqual(qwen_web.lister_skills(self.dossier / "nulle-part"), [])

    def test_identifiant_de_fichier_depuis_le_nom(self):
        self.assertEqual(qwen_web.identifiant_skill("Relecture de code Rust !"), "relecture-de-code-rust")
        self.assertEqual(qwen_web.identifiant_skill("  Été  déjà  "), "ete-deja")
        with self.assertRaises(ValueError):
            qwen_web.identifiant_skill("   ")

    def test_enregistrer_puis_relire(self):
        ident = qwen_web.enregistrer_skill(self.dossier, "Correcteur", "Corrige.", "Corrige sans reformuler.",
                                           {"reflexion": False, "max_tokens": 4096, "temperature": 0})
        self.assertEqual(ident, "correcteur")
        s = qwen_web.lire_skill(self.dossier / "correcteur.md")
        self.assertEqual(s["nom"], "Correcteur")
        self.assertEqual(s["description"], "Corrige.")
        self.assertEqual(s["corps"], "Corrige sans reformuler.")
        self.assertEqual(s["reflexion"], False)
        self.assertEqual(s["max_tokens"], 4096)
        self.assertEqual(s["temperature"], 0)

    def test_enregistrer_refuse_d_ecraser_sauf_demande(self):
        qwen_web.enregistrer_skill(self.dossier, "Doublon", "", "v1", {})
        with self.assertRaises(FileExistsError):
            qwen_web.enregistrer_skill(self.dossier, "Doublon", "", "v2", {})
        self.assertEqual(qwen_web.lire_skill(self.dossier / "doublon.md")["corps"], "v1")
        qwen_web.enregistrer_skill(self.dossier, "Doublon", "", "v2", {}, ecraser=True)
        self.assertEqual(qwen_web.lire_skill(self.dossier / "doublon.md")["corps"], "v2")

    def test_enregistrer_corps_vide_refuse(self):
        with self.assertRaises(ValueError):
            qwen_web.enregistrer_skill(self.dossier, "Vide", "", "   ", {})

    def test_supprimer_deplace_en_corbeille(self):
        qwen_web.enregistrer_skill(self.dossier, "Temporaire", "", "x", {})
        qwen_web.supprimer_skill(self.dossier, "temporaire")
        self.assertFalse((self.dossier / "temporaire.md").exists())
        restes = list((self.dossier / "corbeille").glob("temporaire*.md"))
        self.assertEqual(len(restes), 1)
        self.assertEqual(restes[0].read_text(encoding="utf-8").count("name: Temporaire"), 1)

    def test_supprimer_refuse_identifiant_douteux_et_inconnu(self):
        with self.assertRaises(ValueError):
            qwen_web.supprimer_skill(self.dossier, "../resumer")
        with self.assertRaises(FileNotFoundError):
            qwen_web.supprimer_skill(self.dossier, "inconnu")

    def test_skills_livres_sont_lisibles(self):
        skills = qwen_web.lister_skills(qwen_web.SKILLS)
        ids = {s["id"] for s in skills}
        self.assertTrue({"correcteur", "traduction", "rust", "reformulation"} <= ids, ids)
        for s in skills:
            self.assertIsNone(s.get("erreur"), s)
            self.assertTrue(s["corps"].strip(), s["id"])
            self.assertTrue(s["description"].strip(), s["id"])


class JournalAvecSkills(unittest.TestCase):
    def test_les_skills_actifs_sont_notes(self):
        dossier = Path(tempfile.mkdtemp())
        try:
            nom = qwen_web.ecrire_journal([{"role": "user", "content": "Q"}], "instr", "R", "",
                                          {"reflexion": True, "max_tokens": 1, "temperature": 0}, dossier,
                                          skills=["Correcteur", "Traduction"])
            self.assertIn("skills : Correcteur, Traduction", (dossier / nom).read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(dossier, ignore_errors=True)


@unittest.skipIf(shutil.which("node") is None, "node absent")
class CombinerSkillsJS(unittest.TestCase):
    """La combinaison des skills cochés se fait dans la page : on exécute la fonction dans node."""

    def combiner(self, skills, ids):
        programme = qwen_web.SCRIPT_SKILLS + "\nprocess.stdout.write(JSON.stringify(combinerSkills(" + json.dumps(skills) + ", " + json.dumps(ids) + ")));"
        r = subprocess.run(["node", "-e", programme], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    SKILLS = [
        {"id": "a", "nom": "Alpha", "corps": "Instruction A", "reflexion": False, "max_tokens": None, "temperature": 0.1},
        {"id": "b", "nom": "Bravo", "corps": "Instruction B", "reflexion": True, "max_tokens": 2048, "temperature": None},
    ]

    def test_un_seul_skill_donne_son_corps_tel_quel(self):
        r = self.combiner(self.SKILLS, ["b"])
        self.assertEqual(r["systeme"], "Instruction B")
        self.assertEqual(r["reglages"], {"reflexion": True, "max_tokens": 2048})

    def test_plusieurs_skills_sont_titres_et_le_premier_regle(self):
        r = self.combiner(self.SKILLS, ["a", "b"])
        self.assertEqual(r["systeme"], "## Alpha\n\nInstruction A\n\n## Bravo\n\nInstruction B")
        self.assertEqual(r["reglages"], {"reflexion": False, "temperature": 0.1, "max_tokens": 2048})

    def test_aucun_skill(self):
        r = self.combiner(self.SKILLS, [])
        self.assertEqual(r, {"systeme": "", "reglages": {}})

    def test_identifiant_inconnu_ignore(self):
        self.assertEqual(self.combiner(self.SKILLS, ["zzz", "a"])["systeme"], "Instruction A")


if __name__ == "__main__":
    unittest.main(verbosity=2)
