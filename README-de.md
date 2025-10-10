# TypoCompiler: Wenn du Sprache wie Code ausführst

**语言 / Languages / 言語 / 언어 / Idiomas / Sprachen / Langues**：  
[简体中文](./README.md) · [English](./README-en.md) · [日本語](./README-ja.md) · [한국어](./README-ko.md) · [Español](./README-es.md) · [Deutsch](./README-de.md) · [Français](./README-fr.md)


> Menschen sind keine Syntax-Parser. Sie beenden die Ausführung nicht nur wegen schlechter Grammatik. Also habe ich einen echten Parser gebaut.

Hast du dich schon einmal gefragt, ob hinter dem Lächeln deines Gegenübers eine Menge „Kompilierfehler“ steckt, wenn du in holpriger Fremdsprache sprichst? Jetzt kannst du Alltagsgespräche endlich wie Programme kompilieren.

TypoCompiler nutzt klassische Compiler-Stile, um Sprachfehler im Text aufzuspüren – so unerbittlich wie Python, Java und C++.

Du musst dich nicht mehr fragen, ob das verlegene Lächeln heimlich `exit(1)` aufruft.

---

✨ **Funktionen**

* **Diagnosen im Compiler-Stil**: launisch wie Python, streng wie Java, steif wie C++. Der Schmerz, den Programmierer kennen.
* **Mehrsprachige automatische Erkennung**: egal in welcher Sprache du patzt, TypoCompiler markiert es präzise.
* **Klassische Oberfläche**: so einfach, dass ein PM sie nutzen kann, so mächtig, dass Entwickler sie haben wollen.
* **LLM-Integration**: OpenAI-kompatible Schnittstelle. Findet Fehler effizient und verbraucht deine API-Quota ebenso effizient.
* **Anpassbare Stile**: deine Sprache, deine Regeln. Auch interne Review-Stile sind leicht anzupassen.

---

🧭 **Schnellstart**

**Voraussetzungen**: Python 3.8+. Keine weiteren Abhängigkeiten – ich bin schließlich auch bequem.

```bash
python typocompiler.py
```

1. Öffne den Editor und schreibe deinen „brillanten“ Fremdsprachen-Text.
2. Konfiguriere dein LLM, damit die KI dein Gestammel mit dir erträgt.
3. Klicke auf **Run**, damit der Compiler deine Fehler gnadenlos aufzeigt.

---

🖥️ **Menü-Übersicht**

* **Datei**: die üblichen Dinge.
* **Einstellungen**: Sprache und Stile umschalten. Die Einstellung deiner Stimmung liegt bei dir.
* **Ausführen**: mit einem Klick ausführen, mit einem Klick scheitern, mit einem Klick Fehler kopieren.

---

🧠 **Eingebaute Stile**

* **Python-Stil**: Traceback – die klassische Ohrfeige.
* **Java-Stil**: Fehlerzusammenfassung – die klassische Standpauke.
* **C++-Stil**: Genauigkeit bis zum Zeichen – der klassische Seitenhieb.

Gibt das Modell `TC_OK` zurück, Glückwunsch. Zumindest diesmal hast du die KI ausgetrickst.

---

🧩 **Stile anpassen**

Dir gefallen die Defaults nicht? In **Einstellungen → Stile verwalten** kannst du eigene Templates bauen, damit TypoCompiler dein Ego noch gezielter trifft.

---

⚙️ **Konfiguration und Wiederherstellung**

Konfiguration zerschossen? Kein Problem. Die App setzt auf Standardwerte zurück und sichert die kaputte Datei.

---

🌐 **Datenschutz und Sicherheit**

Bei jedem Klick auf **Run** werden deine Sprachfehler an den konfigurierten LLM-Server gesendet. Keine Sorge: sicher sind sie – solange dein API-Schlüssel noch Guthaben hat.

---

🗂️ **Für Entwickler**

Du willst tiefer einsteigen? Die Projektstruktur ist bereit. Viel Spaß beim Basteln.

---

❗ **Letzte Erinnerung**

Du glaubst, Menschen sind tolerant, wenn du dich versprichst? Vielleicht ist ihr „Sprach-Compiler“ nur noch nicht abgestürzt.

Jetzt haben wir TypoCompiler.

Happy „Coding“!
