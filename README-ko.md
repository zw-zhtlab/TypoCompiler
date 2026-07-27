# TypoCompiler

**언어:** [简体中文](./README.md) · [English](./README-en.md) · [日本語](./README-ja.md) · **한국어** · [Español](./README-es.md) · [Deutsch](./README-de.md) · [Français](./README-fr.md)

TypoCompiler는 자연어 문제를 컴파일러 진단처럼 보여 주는 데스크톱 교정 클라이언트입니다. 편집기, 소스 위치가 있는 진단 목록, 읽기 전용 Python/Java/C++ 스타일 출력을 한 창에 배치합니다. 모델이 입력 언어를 감지하지만, 검사 품질은 설정한 모델에 따라 달라지며 모든 문제를 찾는다고 보장하지 않습니다.

## 주요 기능

- LLM은 구조화된 JSON 진단만 만들고, 앱이 줄·열·심각도를 로컬에서 검증합니다.
- 하나의 canonical 진단 집합에서 Python/Java/C++ 출력을 결정적으로 렌더링합니다.
- 진단을 두 번 클릭하면 원문 위치로 이동하며, 오래된 텍스트에 대한 결과는 명확히 표시됩니다.
- UTF-8 BOM과 줄바꿈 형식을 보존하고 설정과 문서를 원자적으로 저장합니다.
- 백그라운드 작업은 큐를 통해 Tk 메인 스레드로 돌아오며, 이전 요청이나 창을 닫은 뒤의 결과는 무시됩니다.

## 요구 사항 및 실행

- Python 3.10 이상
- Tkinter(일반적인 Windows/macOS Python에 포함되며 Linux에서는 `python3-tk`가 필요할 수 있음)
- OpenAI Chat Completions 호환 엔드포인트와 모델

추가 Python 런타임 의존성은 없습니다.

```bash
python typocompiler.py
python -m typocompiler

# 설치된 GUI 명령
python -m pip install .
typocompiler
```

**설정 → LLM 설정**에서 서버와 모델을 지정하고 `F5`로 분석합니다. `Esc`는 해당 결과를 무효화하지만, 이미 전송된 HTTP 호출 자체를 중단하지 못할 수 있습니다.

## 보안, 개인정보 및 설정

- 분석할 때마다 현재 텍스트와 검토 지침이 설정한 공급자에게 전송됩니다. 민감한 문서는 신뢰할 수 있는 서비스에만 보내세요.
- 원격 연결은 HTTPS가 필수입니다. 평문 HTTP는 `localhost`, `127.0.0.1`, `::1`에서만 허용되고 리디렉션은 차단됩니다.
- `TYPOCOMPILER_API_KEY`를 선택하면 키를 로컬에 저장하지 않습니다. 로컬 저장을 선택하면 키가 `~/.typocompiler/config.json`에 평문으로 기록됩니다.
- 손상된 설정은 이전 증거를 덮어쓰지 않는 고유한 `config.json.broken-*`로 이동하고 가능한 경우 소유자 전용 권한을 적용합니다.
- 한 번의 UTF-8 분석 본문은 2 MiB로 제한되며 정상/오류 응답에도 크기 제한과 전체 제한 시간이 있습니다. 출력 토큰 필드는 호환성을 위한 `max_tokens`와 최신 `max_completion_tokens` 중에서 선택할 수 있습니다.

## 진단 및 사용자 프로필

빈 응답, 거부, 잘린 응답, 잘못된 JSON, 범위를 벗어난 위치는 fail closed로 거부됩니다. 사용자 지침에서 허용되는 자리표시자는 `{input_text}`와 `{style_name}`뿐입니다. 속성 접근, 인덱스, 알 수 없는 필드, 닫히지 않은 중괄호는 저장 전에 거부됩니다. 표시 스타일은 분석 결과를 바꾸지 않고 같은 진단을 로컬에서 다시 렌더링합니다.

## 개발

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
python -m pip wheel . --no-deps -w dist-test
```

CI는 Ruff, 포맷, wheel 빌드와 임포트 확인을 실행합니다. [MIT 라이선스](./LICENSE)를 사용합니다.
