# TypoCompiler: When you run language like code

**语言 / Languages / 言語 / 언어 / Idiomas / Sprachen / Langues**：  
[简体中文](./README.md) · [English](./README-en.md) · [日本語](./README-ja.md) · [한국어](./README-ko.md) · [Español](./README-es.md) · [Deutsch](./README-de.md) · [Français](./README-fr.md)


> People aren’t syntax parsers. They don’t stop execution just because your grammar is wrong. So I built a real parser.

Have you ever wondered whether, when you speak in broken foreign languages, the smile on the other person’s face hides a pile of “compile errors”? Now you can finally compile everyday conversations as if they were programs!

TypoCompiler uses classic compiler styles to pinpoint language issues in text, as strict as Python, Java, and C++.

No more worrying that the awkward smile is secretly calling `exit(1)`.

---

✨ **Features**

* **Compiler-style diagnostics**: cranky like Python, strict like Java, stiff like C++. The kind of pain programmers remember.
* **Multilingual auto detection**: whatever language you mess up in, TypoCompiler calls it out precisely.
* **Classic UI**: simple enough for PMs to use, powerful enough that engineers want it.
* **LLM integration**: an OpenAI-compatible interface that finds mistakes efficiently and spends your API quota efficiently, too.
* **Custom styles**: your language, your rules. Even in-house review styles are easy to adapt.

---

🧭 **Quick start**

**Requirements**: Python 3.8+. No other dependencies, because I’m lazy too.

```bash
python typocompiler.py
```

1. Open the editor and write your “brilliant” foreign-language text.
2. Configure your LLM so the AI can suffer your awkward phrasing with you.
3. Click **Run** to let the compiler point out your mistakes, hard.

---

🖥️ **Menu guide**

* **File**: the usual things you know.
* **Settings**: switch language, choose styles, adjust your mindset (the last part is on you).
* **Run**: run once, crash once, copy errors with one click.

---

🧠 **Built-in diagnostic styles**

* **Python style**: Traceback, the classic slap in the face.
* **Java style**: error summaries, the classic scolding.
* **C++ style**: character-precise, the classic roast.

If the model returns `__TC_OK__`, congratulations. At least this time you fooled the AI.

---

🧩 **Style customization**

Don’t like the defaults? In **Settings → Manage Styles**, craft your own templates so TypoCompiler can hit your ego even more precisely.

---

⚙️ **Config and recovery**

Broke the config? No problem. The app resets to defaults and backs up the broken one for you.

---

🌐 **Privacy and security**

Every time you click **Run**, your language mistakes are sent to the configured LLM server. Don’t worry, your mistakes are safe—as long as your API key still has credit.

---

🗂️ **For developers**

Want to dig deeper? The directory structure is ready. Tinker as you like.

---

❗ **One last reminder**

You think people are tolerant when you misspeak? Maybe their “language compiler” just didn’t crash.

Now we have TypoCompiler.

Happy “Coding”!
