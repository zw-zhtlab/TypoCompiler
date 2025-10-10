# TypoCompiler : quand tu exécutes la langue comme du code

**语言 / Languages / 言語 / 언어 / Idiomas / Sprachen / Langues**：  
[简体中文](./README.md) · [English](./README-en.md) · [日本語](./README-ja.md) · [한국어](./README-ko.md) · [Español](./README-es.md) · [Deutsch](./README-de.md) · [Français](./README-fr.md)


> Les gens ne sont pas des analyseurs syntaxiques. Ils n’arrêtent pas l’exécution juste parce que ta grammaire est mauvaise. J’ai donc construit un vrai parseur.

Tu t’es déjà demandé si, quand tu parles une langue étrangère bancale, le sourire en face ne cachait pas une pile « d’erreurs de compilation » ? Maintenant tu peux compiler tes conversations quotidiennes comme des programmes.

TypoCompiler utilise des styles de compilateur classiques pour repérer les erreurs de langue dans le texte, aussi impitoyable que Python, Java et C++.

Plus besoin de craindre que ce sourire gêné appelle `exit(1)` en douce.

---

✨ **Fonctionnalités**

* **Diagnostics façon compilateur** : grognon comme Python, strict comme Java, rigide comme C++. La douleur dont se souviennent les développeurs.
* **Détection multilingue automatique** : quelle que soit la langue où tu te trompes, TypoCompiler le signale avec précision.
* **Interface classique** : assez simple pour un PM, assez puissante pour donner envie aux ingénieurs.
* **Intégration LLM** : interface compatible OpenAI. Trouve les erreurs efficacement et dépense tout aussi efficacement ton quota d’API.
* **Styles personnalisables** : ta langue, tes règles. Même les styles de relecture internes sont faciles à adapter.

---

🧭 **Démarrage rapide**

**Prérequis** : Python 3.8+. Pas d’autres dépendances, parce que moi aussi je suis paresseux.

```bash
python typocompiler.py
```

1. Ouvre l’éditeur et écris ton texte en langue étrangère « brillant ».
2. Configure ton LLM pour que l’IA partage ta souffrance linguistique.
3. Clique sur **Run** pour que le compilateur relève tes erreurs sans pitié.

---

🖥️ **Guide des menus**

* **Fichier** : les classiques.
* **Paramètres** : changer la langue et les styles. L’humeur, c’est pour ta pomme.
* **Exécuter** : exécuter en un clic, planter en un clic, copier les erreurs en un clic.

---

🧠 **Styles intégrés**

* **Style Python** : Traceback, la claque classique.
* **Style Java** : résumé d’erreurs, la remontrance classique.
* **Style C++** : précision au caractère, la petite pique classique.

Si le modèle renvoie `TC_OK`, bravo. Au moins cette fois tu as dupé l’IA.

---

🧩 **Personnalisation des styles**

Tu n’aimes pas les valeurs par défaut ? Dans **Paramètres → Gérer les styles**, crée tes propres modèles pour que TypoCompiler atteigne ton ego encore plus précisément.

---

⚙️ **Configuration et restauration**

Configuration cassée ? Pas de souci. L’application revient aux paramètres par défaut et sauvegarde celle qui est cassée.

---

🌐 **Confidentialité et sécurité**

À chaque clic sur **Run**, tes erreurs sont envoyées au serveur LLM configuré. Ne t’inquiète pas, elles sont en sécurité tant que ta clé API a du crédit.

---

🗂️ **Pour les développeurs**

Tu veux creuser ? L’arborescence est prête. Bidouille à volonté.

---

❗ **Dernier rappel**

Tu crois que les gens sont indulgents quand tu parles de travers ? Peut-être que leur « compilateur de langue » ne s’est tout simplement pas écrasé.

Maintenant, il y a TypoCompiler.

Happy “Coding”!
