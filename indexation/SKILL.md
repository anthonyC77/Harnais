---
name: context-index
description: Découpe une documentation de projet trop volumineuse en fragments courts et construit un INDEX.md qui permet à l'agent de ne charger que ce dont il a besoin. Utilise ce skill dès que l'utilisateur parle d'un CLAUDE.md ou d'une doc devenue trop grosse, de contexte saturé, de consommation de tokens excessive sur un gros projet, de découper ou réorganiser des specs, de "context rot", ou demande un index / sommaire pour ses agents. Déclenche-le aussi quand l'utilisateur se plaint que l'agent "lit tout le fichier" ou "se perd" dans un gros dépôt, même s'il ne mentionne jamais le mot index.
---

# Context Index

Construire et maintenir un index de documentation pour qu'un agent charge peu, et pertinent.

## Le principe en une phrase

Sans index, l'agent lit le fichier entier pour en extraire trois lignes. Avec un index, il lit un sommaire léger puis ouvre uniquement le fragment utile.

## Ce qui fait réellement l'économie

**L'unité de granularité est le fichier, pas l'ancre.** L'outil de lecture d'un agent prend un chemin et éventuellement une plage de lignes. Il ne résout pas les ancres : ni `#section` en Markdown, ni `id="section"` en HTML. Un gros fichier bourré d'ancres coûte exactement le même prix qu'un gros fichier sans ancres.

Donc ce qui compte, dans l'ordre :

1. **Découper** en fichiers courts, un sujet par fichier.
2. **Décrire** chaque fichier en une ligne, assez précise pour que l'agent décide de l'ouvrir ou non **sans l'ouvrir**.
3. **Router** : une règle courte qui dit à l'agent de consulter l'index avant de fouiller.

Le point 2 est celui qui fait la différence entre un index qui marche et un index décoratif. Une entrée comme `auth.md — l'authentification` est inutile : l'agent devra ouvrir le fichier pour savoir s'il contient ce qu'il cherche. `auth.md — flux OAuth2, refresh tokens, durées de validité, gestion du 401` lui permet de trancher immédiatement.

Le format des fichiers (Markdown, texte, HTML) n'entre pas dans l'équation. Reste en Markdown : à contenu égal c'est le moins cher en tokens.

## Procédure

### 1. Auditer l'existant

Repérer ce qui est chargé à chaque session : `CLAUDE.md`, ses imports `@`, les fichiers de specs, les README. Mesurer. Dans Claude Code, `/context` affiche le poids de chaque fichier mémoire.

Signaler à l'utilisateur tout fichier qui dépasse ~200 lignes et qui est chargé systématiquement alors qu'il ne sert que dans certaines tâches.

### 2. Découper

Cible : **50 à 200 lignes par fragment**, un sujet cohérent par fichier.

Un fragment est bien découpé quand on peut écrire sa ligne de description sans employer « et » plus d'une fois. Si la description ressemble à une liste, le fichier contient plusieurs sujets : le scinder.

Ne pas tomber dans l'excès inverse : trente fichiers de dix lignes forcent l'agent à faire trente lectures. Si deux fragments sont presque toujours lus ensemble, les fusionner.

Arborescence type (exemple pour un projet C#/Angular) :

```
docs/
  INDEX.md
  architecture/
    couches.md
    conventions-nommage.md
    gestion-erreurs.md
  api/
    authentification.md
    endpoints-facturation.md
    codes-retour.md
  front/
    state-management.md
    design-system.md
    formulaires.md
  ops/
    deploiement.md
    variables-environnement.md
```

Les chemins doivent être stables et parlants. Un chemin renommé est un lien mort dans l'index.

### 3. Écrire l'INDEX.md

Format attendu :

```markdown
# Index de la documentation

Ouvre uniquement les fichiers dont tu as besoin pour la tâche en cours.

## Architecture
- `docs/architecture/couches.md` — découpage Domain/Application/Infrastructure, règles de dépendance entre projets, où placer un nouveau service
- `docs/architecture/conventions-nommage.md` — nommage des classes, dossiers, DTOs, branches Git
- `docs/architecture/gestion-erreurs.md` — hiérarchie d'exceptions, middleware global, ce qui remonte au client

## API
- `docs/api/authentification.md` — flux OAuth2, refresh tokens, durées de validité, gestion du 401
- `docs/api/endpoints-facturation.md` — contrats des endpoints /invoices et /payments, schémas de requête et réponse
- `docs/api/codes-retour.md` — codes HTTP utilisés, format du corps d'erreur, corrélation des logs

## Front
- `docs/front/state-management.md` — organisation des stores, effets, règles sur les signals
- `docs/front/design-system.md` — tokens, composants disponibles, quand créer un nouveau composant
- `docs/front/formulaires.md` — reactive forms, validateurs maison, affichage des erreurs

## Ops
- `docs/ops/deploiement.md` — pipeline CI/CD, environnements, procédure de rollback
- `docs/ops/variables-environnement.md` — liste des variables, lesquelles sont secrètes, où elles sont définies
```

Règles :

- L'index lui-même doit rester court. **Sous 100 lignes.** S'il gonfle, c'est que le découpage est trop fin ou que les descriptions sont trop longues.
- Une ligne par fragment. Chemin en `code`, tiret, description.
- La description dit **ce qu'on trouve dedans**, pas ce que fait le module. Elle répond à « est-ce que ma réponse est là-dedans ? ».
- Grouper par thème avec des titres de niveau 2. Les titres aident le modèle à éliminer des sections entières d'un coup.
- Pas de sommaire, pas de table des matières, pas de métadonnées. L'index est déjà un sommaire.

### 4. Câbler

Ajouter dans `CLAUDE.md` un bloc court qui pointe vers l'index. Voir `INTEGRATION.md` pour le texte exact et les pièges.

**Ne jamais importer les fragments avec la syntaxe `@chemin`.** Les imports sont chargés au démarrage de la session : ils annulent entièrement le bénéfice du découpage. Les chemins doivent apparaître comme du texte, pour que l'agent décide de les lire.

### 5. Mesurer

Avant / après, sur une tâche représentative. Dans Claude Code, `/context`. L'objectif n'est pas d'atteindre un pourcentage annoncé quelque part, c'est que le contexte de démarrage descende à quelques milliers de tokens au lieu de quelques dizaines de milliers.

Si le gain est faible, la cause est presque toujours l'une des trois : des fragments encore importés avec `@`, un `CLAUDE.md` qui contient toujours le contenu au lieu de le référencer, ou des descriptions trop vagues qui poussent l'agent à ouvrir cinq fichiers pour en trouver un.

## Maintenance

Un index qui ment est pire que pas d'index : l'agent ouvre un fichier qui ne contient plus ce qui est annoncé, puis part fouiller à l'aveugle.

- Toute création, suppression ou renommage d'un fragment implique une mise à jour de l'index dans le même commit.
- Quand un fragment dépasse ~200 lignes, proposer de le scinder et d'ajuster l'index.
- Relire les descriptions périodiquement : elles dérivent plus vite que les fichiers.

## Anti-patterns

| À éviter | Pourquoi |
|---|---|
| Importer les fragments avec `@chemin` | Chargés au démarrage, bénéfice nul |
| Descriptions génériques (« la couche métier ») | L'agent doit ouvrir pour savoir, donc il ouvre tout |
| Un INDEX.md de 400 lignes | L'index devient lui-même le problème qu'il résout |
| Des ancres `#section` comme unité de découpe | Non résolues par les outils de lecture |
| Convertir la doc en HTML pour « économiser des tokens » | À contenu égal, le HTML en coûte davantage |
| Dupliquer dans la doc ce que le code dit déjà | L'agent peut lire le code ; garde les décisions et les pièges |

## Ce que ce skill ne résout pas

La lisibilité humaine. Si le besoin est un plan ou une revue que **toi** tu dois lire attentivement, le HTML autonome est un meilleur format — mais c'est un problème de restitution, pas de consommation de contexte. Les deux approches se combinent : Markdown indexé pour ce que l'agent lit, HTML pour ce que tu regardes.
