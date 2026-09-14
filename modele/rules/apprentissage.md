# La boucle d'apprentissage — à copier dans le CLAUDE.md du projet

Cinq lignes, pas plus : c'est un sommaire, pas une encyclopédie.

```markdown
## Ce que le harnais a déjà appris

Au démarrage, la passation de la session précédente est injectée dans ton contexte
(`.claude/apprentissage/passations/`). Ne relis pas ce qu'elle établit — commence par
ses « prochaines actions » et vérifie seulement ce qui a pu changer. Avant de fouiller le
code pour une convention ou une commande, lis `docs/INDEX.md`. En fin de session, le hook
te demandera la section Narrative de la passation : écris-la sobre, factuelle, avec la
ligne « résultat accepté : oui/non ». Rien de ce que tu apprends n'entre dans `docs/`,
un skill ou une garde sans passer par `/capitaliser` et un humain.
```

Pourquoi ces trois gestes et pas d'autres :

- *Ne relis pas ce qu'elle établit* — la présence d'une information ne garantit pas
  qu'elle soit exploitée (« lost in the middle ») ; il faut dire à l'agent quoi en faire.
- *Lis INDEX.md avant de fouiller* — c'est le signal n° 6 (taux de redécouverte) qui
  baisse ou pas. Le skill `indexation/` du harnais construit cet index.
- *La ligne « résultat accepté »* — c'est le dénominateur du signal n° 1. Sans elle,
  `mesurer_sessions.py` se rabat sur les commits, qui ne disent pas si l'humain a accepté.
