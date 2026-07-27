# TypoCompiler

**言語：** [简体中文](./README.md) · [English](./README-en.md) · **日本語** · [한국어](./README-ko.md) · [Español](./README-es.md) · [Deutsch](./README-de.md) · [Français](./README-fr.md)

TypoCompiler は、自然言語の問題をコンパイラ風に表示するデスクトップ校正クライアントです。編集欄、ソース位置付きの診断一覧、読み取り専用の Python／Java／C++ 風出力を一つのウィンドウにまとめています。モデルは入力言語を推定しますが、検出品質は設定したモデルに依存し、すべての問題を見つける保証はありません。

## 主な機能

- LLM は構造化 JSON 診断だけを生成し、行・列・重要度をローカルで検証します。
- 一つの canonical 診断セットから Python／Java／C++ 表示を決定的に生成します。
- 診断をダブルクリックすると原文へ移動し、古いテキストに対する結果は明示されます。
- UTF-8 BOM と改行形式を保ち、設定と文書を原子的に保存します。
- バックグラウンド処理はキューで Tk メインスレッドへ返され、古い要求や終了後の結果は無視されます。

## 要件と起動

- Python 3.10 以降
- Tkinter（Windows／macOS の一般的な Python には同梱。Linux では `python3-tk` が必要な場合があります）
- OpenAI Chat Completions 互換のエンドポイントとモデル

追加の Python ランタイム依存はありません。

```bash
python typocompiler.py
python -m typocompiler

# インストールした GUI コマンド
python -m pip install .
typocompiler
```

**設定 → LLM 設定**で接続先とモデルを設定し、`F5` で解析します。`Esc` は結果を無効化しますが、すでに送信した HTTP 通信そのものを停止できるとは限りません。

## セキュリティ、プライバシー、設定

- 解析ごとに現在の本文とレビュー指示が設定先プロバイダーへ送信されます。機密文書は信頼できるサービスにだけ送信してください。
- リモート接続は HTTPS 必須です。平文 HTTP は `localhost`、`127.0.0.1`、`::1` に限定されます。リダイレクトは無効です。
- `TYPOCOMPILER_API_KEY` を選べばキーはローカル保存されません。設定画面でローカル保存を選ぶと、キーは `~/.typocompiler/config.json` に平文で保存されます。
- 壊れた設定は既存証拠を上書きしない一意な `config.json.broken-*` へ移動し、可能な範囲で所有者だけが読める権限にします。
- 一回の UTF-8 解析本文は 2 MiB に制限され、応答とエラー本文にもサイズ上限と総タイムアウトがあります。出力トークン項目は互換性重視の `max_tokens` と新しい `max_completion_tokens` から選択できます。

## 診断とカスタムプロファイル

モデル応答が空、拒否、途中終了、不正 JSON、範囲外の位置を含む場合は fail closed で拒否されます。カスタム指示で使えるプレースホルダーは `{input_text}` と `{style_name}` だけです。属性参照、インデックス、未知の項目、壊れた波括弧は保存前に拒否されます。表示スタイルを変えても解析内容は変わらず、同じ診断をローカルで再描画するだけです。

## 開発

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
python -m pip wheel . --no-deps -w dist-test
```

CI は Ruff、フォーマット、wheel ビルド、インポート確認を実行します。ライセンスは [MIT](./LICENSE) です。
