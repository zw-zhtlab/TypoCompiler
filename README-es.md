# TypoCompiler: cuando ejecutas el idioma como si fuera código

**语言 / Languages / 言語 / 언어 / Idiomas / Sprachen / Langues**：  
[简体中文](./README.md) · [English](./README-en.md) · [日本語](./README-ja.md) · [한국어](./README-ko.md) · [Español](./README-es.md) · [Deutsch](./README-de.md) · [Français](./README-fr.md)


> Las personas no son analizadores sintácticos. No detienen la ejecución solo porque tengas mala gramática. Así que hice un analizador de verdad.

¿Alguna vez pensaste que, cuando hablas en un idioma extranjero con errores, detrás de la sonrisa del otro hay un montón de “errores de compilación”? Ahora por fin puedes compilar tus conversaciones diarias como si fueran programas.

TypoCompiler usa estilos clásicos de compilador para localizar errores de lenguaje en el texto, tan implacable como Python, Java y C++.

No vuelvas a preocuparte: esa sonrisa incómoda ya no estará llamando a `exit(1)` en secreto.

---

✨ **Funciones**

* **Diagnóstico al estilo compilador**: gruñón como Python, estricto como Java, rígido como C++. El dolor que recuerdan los programadores.
* **Detección automática multilingüe**: te equivoques en el idioma que te equivoques, TypoCompiler lo señala con precisión.
* **Interfaz clásica**: tan simple que la puede usar un PM, tan potente que un ingeniero también la quiere.
* **Integración con LLM**: interfaz compatible con OpenAI. Encuentra errores con eficiencia y gasta tu cuota de API con la misma eficiencia.
* **Estilos personalizables**: tu idioma, tus reglas. Incluso estilos internos de revisión son fáciles de adaptar.

---

🧭 **Inicio rápido**

**Requisitos**: Python 3.8+. Sin dependencias adicionales, porque yo también soy perezoso.

```bash
python typocompiler.py
```

1. Abre el editor y escribe tu “brillante” texto en lengua extranjera.
2. Configura tu LLM para que la IA sufra tus expresiones contigo.
3. Haz clic en **Run** y deja que el compilador señale tus errores con ganas.

---

🖥️ **Guía de menús**

* **Archivo**: lo de siempre.
* **Configuración**: cambia idioma y estilos. La actitud corre por tu cuenta.
* **Ejecutar**: ejecutar con un clic, fallar con un clic, copiar errores con un clic.

---

🧠 **Estilos integrados**

* **Estilo Python**: Traceback, el bofetón clásico.
* **Estilo Java**: resumen de errores, la regañina clásica.
* **Estilo C++**: precisión al carácter, la crítica clásica.

Si el modelo devuelve `__TC_OK__`, enhorabuena. Al menos esta vez engañaste a la IA.

---

🧩 **Personalización de estilos**

¿No te gustan los predeterminados? En **Configuración → Gestionar estilos** crea tus propias plantillas para que TypoCompiler golpee tu ego con más precisión.

---

⚙️ **Configuración y recuperación**

¿Rompiste la configuración? No pasa nada. La app restablece los valores por defecto y guarda copia de la configuración rota.

---

🌐 **Privacidad y seguridad**

Cada vez que pulsas **Run**, tus errores se envían al servidor LLM configurado. Tranquilo, tus errores están a salvo, siempre que a tu API key le quede saldo.

---

🗂️ **Para desarrolladores**

¿Quieres trastear más? La estructura del proyecto está lista. Experimenta sin miedo.

---

❗ **Último aviso**

¿Crees que la gente es tolerante cuando te equivocas al hablar? Tal vez su “compilador de lenguaje” simplemente no se ha caído.

Ahora tenemos TypoCompiler.

Happy “Coding”!
