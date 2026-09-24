#!/usr/bin/env python3
"""Tests de agent_qwen.py : tout ce qui se décide avant d'ouvrir `claude`, sans Mac ni modèle.

    python tests/test_agent_qwen.py
    python -m unittest tests.test_agent_qwen

Le seul réseau touché est un serveur HTTP éphémère sur 127.0.0.1, qui joue le pont.
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_qwen  # noqa: E402


class EnvironnementQwen(unittest.TestCase):
    def test_pointe_claude_code_vers_le_pont_et_epingle_brain_partout(self):
        env = agent_qwen.environnement_qwen({})
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "http://192.168.1.50:1235")
        for cle in ("ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
                    "ANTHROPIC_DEFAULT_OPUS_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL"):
            self.assertEqual(env[cle], "brain", cle)

    def test_jeton_factice_pour_ne_jamais_envoyer_le_jeton_claude_ai_sur_le_lan(self):
        env = agent_qwen.environnement_qwen({})
        self.assertTrue(env["ANTHROPIC_AUTH_TOKEN"])
        self.assertNotIn("sk-", env["ANTHROPIC_AUTH_TOKEN"])

    def test_coupe_le_trafic_non_essentiel_et_les_betas_que_le_pont_jette(self):
        env = agent_qwen.environnement_qwen({})
        self.assertEqual(env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"], "1")
        self.assertEqual(env["CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS"], "1")
        self.assertEqual(env["CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING"], "1")

    def test_laisse_trente_minutes_a_un_tour_lent_avant_de_couper(self):
        # brain relit tout le prompt puis réfléchit sans rien émettre : Claude Code coupe à 5 min par défaut.
        env = agent_qwen.environnement_qwen({})
        self.assertEqual(env["CLAUDE_STREAM_IDLE_TIMEOUT_MS"], "1800000")
        self.assertEqual(env["API_TIMEOUT_MS"], "1800000")

    def test_retire_une_vraie_cle_api_presente_dans_le_shell(self):
        env = agent_qwen.environnement_qwen({"ANTHROPIC_API_KEY": "sk-ant-vraie"})
        self.assertNotIn("ANTHROPIC_API_KEY", env)

    def test_conserve_le_reste_du_shell_et_ne_modifie_pas_l_original(self):
        base = {"PATH": "C:\\x", "HOME": "C:\\Users\\a"}
        env = agent_qwen.environnement_qwen(base)
        self.assertEqual(env["PATH"], "C:\\x")
        self.assertEqual(env["HOME"], "C:\\Users\\a")
        self.assertEqual(base, {"PATH": "C:\\x", "HOME": "C:\\Users\\a"}, "l'original ne doit pas bouger")


class CommandeClaude(unittest.TestCase):
    def test_sans_argument_c_est_claude_tout_seul(self):
        self.assertEqual(agent_qwen.commande_claude([]), ["claude"])

    def test_les_arguments_supplementaires_passent_dans_l_ordre(self):
        self.assertEqual(agent_qwen.commande_claude(["--continue", "-p", "salut"]),
                         ["claude", "--continue", "-p", "salut"])


class ArgumentsClaude(unittest.TestCase):
    def test_le_double_tiret_de_tete_est_retire_le_reste_passe_tel_quel(self):
        self.assertEqual(agent_qwen.arguments_claude(["--", "--continue", "-p", "x"]), ["--continue", "-p", "x"])

    def test_sans_double_tiret_rien_ne_change(self):
        self.assertEqual(agent_qwen.arguments_claude(["--continue"]), ["--continue"])
        self.assertEqual(agent_qwen.arguments_claude([]), [])


class DiagnosticPont(unittest.TestCase):
    def test_pont_debout_rien_a_dire(self):
        self.assertEqual(agent_qwen.diagnostic_pont(True, True), "")

    def test_lm_studio_repond_mais_pas_le_pont_designe_le_pont(self):
        msg = agent_qwen.diagnostic_pont(False, True)
        self.assertIn("bridge/server.py", msg)
        self.assertNotIn("ping", msg)

    def test_rien_ne_repond_designe_le_mac_ou_le_reseau(self):
        msg = agent_qwen.diagnostic_pont(False, False)
        self.assertIn("ping 192.168.1.50", msg)
        self.assertNotIn("bridge/server.py", msg)


class _FauxPont(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        corps = json.dumps({"ok": True, "upstream": "faux"}).encode()
        code = 200 if self.path == "/health" else 404
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *_):
        pass


class PontDebout(unittest.TestCase):
    def setUp(self):
        self.serveur = HTTPServer(("127.0.0.1", 0), _FauxPont)
        self.port = self.serveur.server_address[1]
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()

    def tearDown(self):
        self.serveur.shutdown()
        self.serveur.server_close()

    def test_vrai_quand_health_repond_ok(self):
        self.assertTrue(agent_qwen.pont_debout(f"http://127.0.0.1:{self.port}"))

    def test_faux_sur_un_port_ferme(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port_libre = s.getsockname()[1]
        self.assertFalse(agent_qwen.pont_debout(f"http://127.0.0.1:{port_libre}", timeout=1))


if __name__ == "__main__":
    unittest.main()
