# TypoCompiler

**语言：** **简体中文** · [English](./README-en.md) · [日本語](./README-ja.md) · [한국어](./README-ko.md) · [Español](./README-es.md) · [Deutsch](./README-de.md) · [Français](./README-fr.md)

TypoCompiler 是一款小巧的桌面写作检查工具：它让 LLM 分析自然语言文本，再以 Python、Java 或 C++ 编译器风格展示问题。编辑、运行、查看诊断和定位原文都在同一个窗口中完成。

## 2.1 版的主要改进

- 单窗口工作区同时显示编辑器、诊断列表和只读编译器输出。
- 双击诊断即可跳到对应文本位置；问题级别既有文字说明，也有高亮提示。
- 加入滚动条、完整快捷键、键盘焦点、光标行列状态、过期结果提示与运行取消。
- 模型只负责返回结构化 JSON；程序会校验每个行列坐标，再在本地生成三种编译器风格。
- 打开的文件会保留检测到的 UTF-8 BOM 和换行格式，并采用原子替换方式保存。
- 后台线程只向队列写入结果，由 Tk 主线程轮询处理；过期或关闭后的结果无法操作界面或覆盖新任务。
- 远程端点必须使用 HTTPS；明文 HTTP 仅允许 `localhost`、`127.0.0.1` 和 `::1`。
- 提供 `pyproject.toml` 以及代码质量和打包 CI 配置。

## 环境与启动

- Python 3.10 或更高版本
- Tkinter（Windows 和 macOS 官方 Python 通常自带；部分 Linux 发行版需要安装 `python3-tk`）
- 一个兼容 OpenAI Chat Completions 的服务端和模型

程序没有第三方 Python 运行时依赖。

```bash
python typocompiler.py
# 等价的模块入口
python -m typocompiler
```

也可以安装本地命令：

```bash
python -m pip install .
typocompiler
```

安装后的 `typocompiler` 使用 GUI 入口，Windows 启动时不会额外弹出控制台。在 **设置 → LLM 设置** 中填写基础 URL、模型和可选凭据，然后按 **F5** 分析编辑器中的文本。程序会在基础 URL 后追加 `/chat/completions`。

## 快捷键

| 操作 | 快捷键 |
| --- | --- |
| 新建 / 打开 / 保存 | `Ctrl+N` / `Ctrl+O` / `Ctrl+S` |
| 另存为 | `Ctrl+Shift+S` |
| 运行分析 | `F5` |
| 取消当前运行 | `Esc` |
| 复制编译器输出 | `Ctrl+Shift+C` |
| 增大 / 减小 / 重置字号 | `Ctrl++` / `Ctrl+-` / `Ctrl+0` |

取消操作不能中止已经发出的 HTTP 请求，但程序会忽略该请求随后返回的结果。如果运行期间文本发生变化，结果仍会保留，同时明确提示它对应的是较早的文本快照。

## 诊断与风格

模型会识别输入语言并返回 JSON 诊断列表。每条诊断必须包含有效的行号、起止列、级别、类别和消息；还可以包含原文、替换内容和解释。无效或越界的响应会被拒绝，不会冒充可靠结果显示。

Python、Java 和 C++ 只是对同一份已校验结果进行本地排版。**设置 → 管理风格** 修改的是检查指导语，并不会执行代码或调用真实编译器。检查质量取决于所配置的模型，无法保证找出所有语言问题。

自定义指导语只允许无副作用的 `{input_text}` 和 `{style_name}` 占位符。空模板、花括号不匹配、未知字段、属性访问、索引、转换和格式说明都会在写盘前被拒绝。分析始终生成一份 canonical 诊断集；切换风格只会在本地重新渲染。

## 文件、隐私与配置

- 可打开不超过 16 MiB 的文本和 Markdown 文件；单次分析的 UTF-8 文本上限为 2 MiB，以限制界面开销和服务费用。
- 每次分析都会把当前文本和检查指导语发送给所配置的服务商。敏感文本仅应提交给可信服务。
- 设置界面会明确选择“使用 `TYPOCOMPILER_API_KEY`（不在本地保存密钥）”或“明文保存到 `~/.typocompiler/config.json`”。建议使用权限受限的 Token，并优先选择环境变量。
- 配置损坏时，原文件会先移动到唯一、尽力限制为仅所有者可读的 `config.json.broken-*`，旧备份不会被主动覆盖，然后恢复默认值。
- 程序拒绝远程 HTTP、URL 内凭据、查询参数、片段、空白和控制字符；同时禁止重定向、限制正常及错误响应大小，并对完整响应读取执行总超时。
- 输出 Token 字段可以选择：兼容服务默认使用 `max_tokens`，需要新版字段的服务或模型可选择 `max_completion_tokens`。

## 开发

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
python -m pip wheel . --no-deps -w dist-test
```

GitHub Actions 会执行 Ruff、格式、wheel 构建和导入冒烟检查。

本项目采用 [MIT License](./LICENSE)。
