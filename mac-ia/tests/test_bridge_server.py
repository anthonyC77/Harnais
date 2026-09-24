#!/usr/bin/env python3
"""Tests de bridge/server.py hors traduction : le battement qui tient le client éveillé.

    python tests/test_bridge_server.py

Pendant que le modèle relit le prompt puis réfléchit, LM Studio n'émet rien qui se
traduise en texte. Un client qui n'a reçu aucun octet pendant cinq minutes coupe et
relance (Claude Code). Le pont envoie donc un `ping`, événement prévu par le format
Anthropic et ignoré par les clients, dès que le flux se tait trop longtemps.
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
import server  # noqa: E402


class Battement(unittest.TestCase):
    def test_un_silence_plus_long_que_l_intervalle_produit_un_ping(self):
        ecrits = []
        b = server.Battement(ecrits.append, intervalle=0.05)
        b.demarrer()
        try:
            time.sleep(0.3)
        finally:
            b.arreter()
        self.assertGreaterEqual(len(ecrits), 1)
        self.assertEqual(ecrits[0], b'event: ping\ndata: {"type":"ping"}\n\n')

    def test_un_flux_qui_ecrit_regulierement_ne_recoit_aucun_ping(self):
        ecrits = []
        b = server.Battement(ecrits.append, intervalle=0.1)
        b.demarrer()
        try:
            for _ in range(10):
                time.sleep(0.03)
                b.toucher()
        finally:
            b.arreter()
        self.assertEqual(ecrits, [])

    def test_apres_arret_plus_aucun_ping(self):
        ecrits = []
        b = server.Battement(ecrits.append, intervalle=0.02)
        b.demarrer()
        time.sleep(0.1)
        b.arreter()
        n = len(ecrits)
        time.sleep(0.1)
        self.assertEqual(len(ecrits), n)

    def test_une_ecriture_qui_echoue_arrete_le_battement_sans_lever(self):
        def casse(_):
            raise BrokenPipeError
        b = server.Battement(casse, intervalle=0.02)
        b.demarrer()
        time.sleep(0.1)
        b.arreter()
        self.assertFalse(b.actif())


if __name__ == "__main__":
    unittest.main()
