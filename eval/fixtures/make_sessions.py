#!/usr/bin/env python3
"""Fabrique eval/fixtures/sessions/*.jsonl : trois transcripts Claude Code synthétiques
aux valeurs connues, pour tester lire_transcripts.py et mesurer_sessions.py sans
toucher à ~/.claude/projects.

  s1-chere        (W37) lit beaucoup, corrige trois fois, une escalade, aucun test, aucun commit
  s2-propre       (W37) relit deux fichiers, édite, lance pytest, commite
  s3-corrections  (W38) relit trois fichiers dont deux déjà vus deux fois, deux corrections,
                        un refus de permission, commite sans test

La forme des entrées est celle observée dans un transcript réel du 12 septembre 2026
(version 2.1.269) : une entrée `assistant` par bloc de contenu, toutes portant le même
`requestId` et le même `usage` — le lecteur doit compter l'usage une fois par requête."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sessions")
MODELE = "modele-test"
PROJET = "d--fixture"


class Session:
    def __init__(self, sid, debut):
        self.sid, self.t, self.n, self.req, self.lignes = sid, debut, 0, 0, []
        self.dernier = None

    def _base(self, kind):
        self.n += 1
        self.t += 30
        e = {"parentUuid": self.dernier, "isSidechain": False, "type": kind, "uuid": f"{self.sid}-{self.n:03d}",
             "timestamp": f"2026-09-{self.t // 86400 + 1:02d}T{(self.t // 3600) % 24:02d}:{(self.t // 60) % 60:02d}:{self.t % 60:02d}.000Z",
             "sessionId": self.sid, "cwd": "d:\\fixture", "gitBranch": "main", "version": "2.1.269"}
        self.dernier = e["uuid"]
        return e

    def humain(self, texte):
        e = self._base("user")
        e.update({"origin": {"kind": "human"}, "message": {"role": "user", "content": texte}})
        self.lignes.append(e)

    def assistant(self, blocs, usage):
        """Une requête API : un bloc par entrée, même requestId, même usage."""
        self.req += 1
        rid = f"req_{self.sid}_{self.req:03d}"
        for i, bloc in enumerate(blocs):
            e = self._base("assistant")
            e.update({"requestId": rid, "apiBlockIndex": i,
                      "message": {"role": "assistant", "model": MODELE, "content": [bloc], "usage": dict(usage)}})
            self.lignes.append(e)

    def resultat(self, tool_id, contenu, erreur=False):
        e = self._base("user")
        bloc = {"type": "tool_result", "tool_use_id": tool_id, "content": contenu}
        if erreur:
            bloc["is_error"] = True
        e.update({"message": {"role": "user", "content": [bloc]}, "toolUseResult": contenu})
        self.lignes.append(e)

    def outil(self, nom, entree, contenu="ok", erreur=False, usage=None, texte=None):
        """Un tour complet : (texte facultatif +) tool_use, puis son résultat."""
        tid = f"toolu_{self.sid}_{self.n:03d}"
        blocs = ([{"type": "text", "text": texte}] if texte else []) + [{"type": "tool_use", "id": tid, "name": nom, "input": entree}]
        self.assistant(blocs, usage or U_PETIT)
        self.resultat(tid, contenu, erreur)

    def bruit(self):
        """Entrées hors conversation : le lecteur doit les ignorer sans lever."""
        self.lignes.append({"type": "ai-title", "sessionId": self.sid, "title": "x"})
        self.lignes.append({"type": "queue-operation", "operation": "enqueue", "sessionId": self.sid})
        e = self._base("user")
        e.update({"isSidechain": True, "origin": {"kind": "human"}, "message": {"role": "user", "content": "sous-agent : ignoré"}})
        self.lignes.append(e)
        self.lignes.append({"type": "attachment", "attachment": {"type": "total_tokens_reminder"}, "sessionId": self.sid})

    def ecrire(self):
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, f"{self.sid}.jsonl"), "w", encoding="utf-8") as f:
            for e in self.lignes:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
            # Une dernière ligne tronquée : une session encore en cours d'écriture.
            f.write('{"type":"assistant","message":{"role":"assis')


# Usages en tokens. Les prix de fixtures/prix.json valent, par million :
# input 3, cache_creation 3.75, cache_read 0.30, output 15.
U_PETIT = {"input_tokens": 1000, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 10000, "output_tokens": 200}
U_GROS = {"input_tokens": 2000, "cache_creation_input_tokens": 20000, "cache_read_input_tokens": 40000, "output_tokens": 1000}
DENI = "The user doesn't want to proceed with this tool use. The tool call was rejected."


def s1():
    # Jour 8 septembre 2026 (W37). debut = 7 jours * 86400 + 9h.
    s = Session("s1-chere", 7 * 86400 + 9 * 3600)
    s.humain("Ajoute la validation des badges dans le service")
    s.bruit()
    s.outil("Read", {"file_path": "d:\\fixture\\src\\a.py"}, "contenu a", usage=U_GROS)
    s.outil("Read", {"file_path": "d:\\fixture\\src\\b.py"}, "contenu b", usage=U_GROS)
    s.outil("Grep", {"pattern": "badge", "path": "d:\\fixture\\src"}, "a.py:3", usage=U_GROS)
    s.outil("Read", {"file_path": "d:\\fixture\\docs\\INDEX.md"}, "index", usage=U_GROS)
    s.outil("Read", {"file_path": "d:\\fixture\\src\\c.md"}, "c", usage=U_GROS)
    s.outil("Edit", {"file_path": "d:\\fixture\\src\\a.py", "old_string": "x", "new_string": "y"}, "ok", usage=U_GROS)
    s.humain("non, pas ça : la validation va dans b.py")
    s.outil("Edit", {"file_path": "d:\\fixture\\src\\b.py", "old_string": "x", "new_string": "y"}, "ok", usage=U_GROS)
    s.outil("Bash", {"command": "python -m mypy src"}, "error: src/b.py:3", erreur=True, usage=U_GROS)
    s.humain("corrige")
    s.humain("je t'ai dit que c'est dans b.py")
    tid = "toolu_s1_ask"
    s.assistant([{"type": "tool_use", "id": tid, "name": "AskUserQuestion", "input": {"questions": [{"question": "Quel fichier ?"}]}}], U_GROS)
    s.resultat(tid, "b.py")
    s.assistant([{"type": "thinking", "thinking": "raisonnement"}, {"type": "text", "text": "Voilà, c'est dans b.py."}], U_GROS)
    s.ecrire()


def s2():
    # Jour 9 septembre 2026 (W37).
    s = Session("s2-propre", 8 * 86400 + 10 * 3600)
    s.humain("Ajoute un test pour la validation")
    s.outil("Read", {"file_path": "d:\\fixture\\src\\a.py"}, "contenu a")
    s.outil("Read", {"file_path": "d:\\fixture\\src\\b.py"}, "contenu b")
    s.outil("Write", {"file_path": "d:\\fixture\\tests\\test_b.py", "content": "def test(): pass"}, "ok")
    s.outil("Bash", {"command": "python -m pytest -q"}, "1 passed")
    s.outil("Bash", {"command": "git add -A && git commit -m 'test'"}, "[main abc] test")
    s.assistant([{"type": "text", "text": "Fait, commité."}], U_PETIT)
    s.ecrire()


def s3():
    # Jour 15 septembre 2026 (W38).
    s = Session("s3-corrections", 14 * 86400 + 14 * 3600)
    s.humain("Renomme la validation en verification")
    s.outil("Read", {"file_path": "d:\\fixture\\src\\a.py"}, "contenu a")
    s.outil("Read", {"file_path": "d:\\fixture\\src\\b.py"}, "contenu b")
    s.outil("Read", {"file_path": "d:\\fixture\\src\\d.py"}, "contenu d")
    s.outil("Edit", {"file_path": "d:\\fixture\\src\\b.py", "old_string": "validation", "new_string": "verification"}, "ok")
    s.humain("non")
    s.outil("Bash", {"command": "rm -rf d:\\fixture\\src"}, DENI, erreur=True)
    s.humain("encore une fois : renomme, ne supprime pas")
    s.outil("Edit", {"file_path": "d:\\fixture\\src\\a.py", "old_string": "validation", "new_string": "verification"}, "ok")
    s.outil("Bash", {"command": "git commit -am 'renommage'"}, "[main def] renommage")
    s.assistant([{"type": "text", "text": "Renommé et commité."}], U_PETIT)
    s.ecrire()


if __name__ == "__main__":
    s1(); s2(); s3()
    print("fixtures écrites dans", OUT)
