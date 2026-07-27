# TypoCompiler

**Langues :** [简体中文](./README.md) · [English](./README-en.md) · [日本語](./README-ja.md) · [한국어](./README-ko.md) · [Español](./README-es.md) · [Deutsch](./README-de.md) · **Français**

TypoCompiler est un client de bureau qui présente les problèmes de langue naturelle comme des diagnostics de compilateur. L’éditeur, la liste des diagnostics liés au texte et la sortie en lecture seule de style Python, Java ou C++ partagent une seule fenêtre. Le modèle détecte la langue d’entrée, mais la qualité dépend du modèle configuré et aucun résultat exhaustif n’est garanti.

## Fonctionnalités

- Le LLM produit uniquement des diagnostics JSON structurés ; les lignes, colonnes et niveaux sont validés localement.
- Un seul ensemble canonical de diagnostics alimente les rendus déterministes Python, Java et C++.
- Un double-clic rejoint la position source ; un résultat lié à une version antérieure du texte est signalé comme périmé.
- Le BOM UTF-8 et les fins de ligne sont préservés ; la configuration et les documents sont enregistrés de façon atomique.
- Les tâches d’arrière-plan remettent leurs données au thread principal Tk par une file ; les anciens résultats et ceux reçus après fermeture sont ignorés.

## Prérequis et lancement

- Python 3.10 ou version ultérieure
- Tkinter (généralement inclus sous Windows et macOS ; sous Linux, `python3-tk` peut être nécessaire)
- Un endpoint et un modèle compatibles avec OpenAI Chat Completions

Aucune dépendance Python d’exécution supplémentaire n’est requise.

```bash
python typocompiler.py
python -m typocompiler

# Commande graphique installée
python -m pip install .
typocompiler
```

Configurez le serveur et le modèle dans **Paramètres → LLM**, puis lancez l’analyse avec `F5`. `Esc` invalide le résultat actif, sans garantir l’arrêt d’un appel HTTP déjà envoyé.

## Sécurité, confidentialité et configuration

- Chaque analyse envoie le texte courant et les consignes de relecture au fournisseur configuré. N’envoyez un document sensible qu’à un service de confiance.
- Un serveur distant doit utiliser HTTPS. HTTP en clair est limité à `localhost`, `127.0.0.1` et `::1` ; les redirections sont désactivées.
- Le choix `TYPOCOMPILER_API_KEY` évite tout stockage local de la clé. Le stockage local écrit la clé en texte brut dans `~/.typocompiler/config.json`.
- Une configuration endommagée est déplacée vers un fichier unique `config.json.broken-*`, sans écraser volontairement les preuves précédentes et avec des droits réservés au propriétaire lorsque possible.
- Chaque texte UTF-8 envoyé à l’analyse est limité à 2 MiB ; les réponses normales et d’erreur sont aussi bornées et soumises à un délai total. Le champ de jetons peut être `max_tokens` pour la compatibilité ou `max_completion_tokens` pour les services et modèles qui l’exigent.

## Diagnostics et profils personnalisés

Les réponses vides, refusées, tronquées, au JSON invalide ou aux positions hors texte sont rejetées en mode fail closed. Les seuls champs autorisés dans une consigne sont `{input_text}` et `{style_name}`. Les accès aux attributs ou index, les champs inconnus et les accolades incomplètes sont rejetés avant l’enregistrement. Changer le style réaffiche localement les mêmes diagnostics sans relancer ni modifier l’analyse.

## Développement

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
python -m pip wheel . --no-deps -w dist-test
```

La CI exécute Ruff, le formatage, la construction du wheel et un contrôle d’import. Licence [MIT](./LICENSE).
