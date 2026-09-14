# Intégration : index de contexte

Trois pièces distinctes. Ne pas les confondre, c'est là que la plupart des gens se plantent.

| Pièce | Rôle | Où elle vit |
|---|---|---|
| Les fragments | Le contenu | `docs/**/*.md` dans le dépôt |
| `INDEX.md` | Le sommaire | `docs/INDEX.md` dans le dépôt |
| La règle de routage | Dit à l'agent d'utiliser l'index | `CLAUDE.md` |
| Le skill | La procédure qui crée et maintient tout ça | `~/.claude/skills/context-index/` |

Le skill n'est pas obligatoire. Il sert à ne pas réexpliquer la méthode à chaque projet.

---

## 1. Le bloc à coller dans CLAUDE.md

À la racine du projet, dans `./CLAUDE.md` :

```markdown
## Documentation du projet

La documentation est découpée en fragments courts, indexés dans `docs/INDEX.md`.

Avant de chercher dans le code ou de poser une question sur une convention,
une décision d'architecture ou un contrat d'API : lis `docs/INDEX.md`, puis
ouvre uniquement les fragments pertinents pour la tâche en cours.

N'ouvre pas tous les fragments. Si l'index ne suffit pas à trancher, demande.

Quand tu modifies, crées ou renommes un fragment, mets à jour `docs/INDEX.md`
dans le même commit.
```

C'est tout. Environ 80 tokens chargés à chaque session, en échange de tout le reste chargé à la demande.

**Variante plus agressive** si l'agent continue à fouiller le code au lieu de lire l'index — utile sur les gros dépôts où `grep` part dans tous les sens :

```markdown
Pour toute question sur les conventions, l'architecture ou les contrats d'API,
`docs/INDEX.md` fait autorité et doit être consulté en premier. Ne pars pas
explorer l'arborescence du code pour retrouver une règle qui est documentée.
```

---

## 2. Le piège des imports `@`

La doc de Claude Code est explicite là-dessus : les imports `@chemin` **organisent** un gros `CLAUDE.md`, ils ne **réduisent pas** le contexte. Les fichiers importés sont chargés au lancement, exactement comme s'ils étaient collés dans le fichier.

Donc :

```markdown
❌ @docs/api/authentification.md
❌ @docs/architecture/couches.md

✅ Voir `docs/INDEX.md` et ouvrir les fragments utiles.
```

Un `CLAUDE.md` de 40 lignes qui importe six fichiers de 300 lignes consomme 1840 lignes à chaque démarrage. C'est le scénario exact que l'index est censé éliminer.

---

## 3. Mécanisme complémentaire : les CLAUDE.md imbriqués

Claude Code découvre les `CLAUDE.md` situés dans les sous-dossiers de ton répertoire de travail, et **ne les charge que lorsqu'il lit des fichiers de ce sous-arbre**. C'est du chargement à la demande natif, gratuit.

Concrètement, sur une solution C#/Angular :

```
CLAUDE.md                    ← règles globales + pointeur vers l'index
src/Api/CLAUDE.md            ← conventions backend, chargé si Claude touche au backend
src/ClientApp/CLAUDE.md      ← conventions Angular, chargé si Claude touche au front
tests/CLAUDE.md              ← conventions de test
```

Un dev qui bosse uniquement sur le front ne paie jamais les conventions backend. Combine ça avec l'index pour la doc de fond, et tu as couvert les deux cas.

---

## 4. Installer le skill

### Claude Code

```bash
mkdir -p ~/.claude/skills/context-index
cp SKILL.md ~/.claude/skills/context-index/SKILL.md
```

Pour le partager avec ton équipe, mets-le dans le dépôt à la place :

```bash
mkdir -p .claude/skills/context-index
cp SKILL.md .claude/skills/context-index/SKILL.md
```

Vérifie avec `/context` que le skill apparaît, puis teste avec une phrase du genre « ma doc est devenue trop grosse, réorganise-la ».

### Claude.ai

Le fichier `SKILL.md` présenté dans la conversation affiche un bouton **Save skill** si ton organisation autorise la création de skills. Sinon, colle simplement son contenu dans un projet.

---

## 5. Démarrage progressif

Ne refactorise pas six mois de documentation d'un coup. Ordre recommandé :

1. **Mesure d'abord.** `/context` dans une session normale. Note le chiffre.
2. **Sors le plus gros morceau.** Prends la section la plus volumineuse de ton `CLAUDE.md` actuel — souvent les conventions ou la description d'architecture — mets-la dans un fragment, ajoute une ligne d'index.
3. **Re-mesure.** Si le chiffre bouge, la méthode fonctionne chez toi, continue. Sinon, cherche l'import `@` oublié.
4. **Élague.** La commande `/doctor` (Claude Code v2.1.206+) propose des coupes dans un `CLAUDE.md` trop gros : elle retire ce que Claude peut déduire du code lui-même — arborescences, listes de dépendances, aperçus d'architecture — et conserve les pièges, les raisons et les conventions qui s'écartent des défauts. C'est un bon complément : beaucoup de ce que tu documentes n'a peut-être pas besoin d'exister.

---

## 6. Critère de réussite

Le bon signal n'est pas un pourcentage. C'est celui-ci : **sur une question précise, l'agent ouvre un ou deux fragments, pas six.**

Si tu le vois en ouvrir six, le problème est dans les descriptions de l'index, pas dans le découpage.
