# TypoCompiler

**Idiomas:** [简体中文](./README.md) · [English](./README-en.md) · [日本語](./README-ja.md) · [한국어](./README-ko.md) · **Español** · [Deutsch](./README-de.md) · [Français](./README-fr.md)

TypoCompiler es un cliente de escritorio para revisar lenguaje natural y presentar los problemas como diagnósticos de compilador. El editor, la lista de diagnósticos con posiciones de origen y la salida de solo lectura con estilo Python, Java o C++ comparten una ventana. El modelo detecta el idioma de entrada, pero la calidad depende del modelo configurado y no se garantiza que encuentre todos los problemas.

## Funciones principales

- El LLM solo produce diagnósticos JSON estructurados; la aplicación valida localmente líneas, columnas y gravedad.
- Un único conjunto canonical de diagnósticos alimenta los renderizadores deterministas de Python, Java y C++.
- Un doble clic salta al texto correspondiente; los resultados de una versión anterior se marcan como obsoletos.
- Se conservan el BOM UTF-8 y los saltos de línea, y la configuración y los documentos se guardan de forma atómica.
- Los trabajadores en segundo plano entregan datos mediante una cola al hilo principal de Tk; se ignoran resultados antiguos o posteriores al cierre.

## Requisitos e inicio

- Python 3.10 o posterior
- Tkinter (normalmente incluido en Windows y macOS; en Linux puede requerir `python3-tk`)
- Un endpoint y modelo compatibles con OpenAI Chat Completions

No hay dependencias Python adicionales en tiempo de ejecución.

```bash
python typocompiler.py
python -m typocompiler

# Comando GUI instalado
python -m pip install .
typocompiler
```

Configura el servidor y el modelo en **Configuración → LLM** y pulsa `F5`. `Esc` invalida el resultado activo, pero puede no detener una llamada HTTP que ya se envió.

## Seguridad, privacidad y configuración

- Cada análisis envía el texto actual y las instrucciones de revisión al proveedor configurado. Envía documentos sensibles solo a servicios de confianza.
- Los servidores remotos requieren HTTPS. HTTP sin cifrar solo se admite en `localhost`, `127.0.0.1` y `::1`; las redirecciones están desactivadas.
- Con `TYPOCOMPILER_API_KEY` no se guarda una clave local. Si eliges almacenamiento local, la clave queda en texto plano en `~/.typocompiler/config.json`.
- Una configuración dañada se mueve a un `config.json.broken-*` único, sin sobrescribir evidencias anteriores y con permisos de propietario cuando el sistema lo permite.
- Cada texto UTF-8 enviado a análisis se limita a 2 MiB; las respuestas normales y de error también tienen límites de tamaño y un plazo total. El campo de tokens puede ser `max_tokens` para compatibilidad o `max_completion_tokens` para servicios y modelos que lo requieran.

## Diagnósticos y perfiles personalizados

Las respuestas vacías, rechazadas, truncadas, con JSON inválido o posiciones fuera del texto se rechazan de forma cerrada. Las únicas variables permitidas en una instrucción personalizada son `{input_text}` y `{style_name}`. El acceso a atributos o índices, los campos desconocidos y las llaves incompletas se rechazan antes de guardar. Cambiar el estilo solo vuelve a renderizar localmente los mismos diagnósticos; no repite ni modifica el análisis.

## Desarrollo

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
python -m pip wheel . --no-deps -w dist-test
```

La CI ejecuta Ruff, formato, construcción del wheel y una comprobación de importación. Licencia [MIT](./LICENSE).
