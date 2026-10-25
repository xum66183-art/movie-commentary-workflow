# Movie Commentary Workflow

[English](README.en.md) · [离线演示](docs/demo.md) · [Releases](https://github.com/xum66183-art/movie-commentary-workflow/releases) · [CI](https://github.com/xum66183-art/movie-commentary-workflow/actions/workflows/ci.yml) · [来源与贡献边界](docs/provenance.md)

面向 Codex 的电影解说工作流与本地工具。用八个阶段技能组织剧情理解、第一人称文稿、配音、选镜和复检；用可执行索引、原片坐标、状态锁和数据合同保留制作证据。

本项目是基于 [straighttttt/movie-commentary-workflow](https://github.com/straighttttt/movie-commentary-workflow) 的独立整合版，保留 Apache-2.0 许可证与上游署名。八个技能的工作流基础、状态合同和模板来自上游；本版主要增加本地索引、部分语音工具、安装与检查工具，以及可复现演示。详细归因见 [provenance](docs/provenance.md) 和 [NOTICE](NOTICE)。本项目与 OpenAI 及所接入供应商没有官方隶属关系。

## 先运行一个不需要 API 的演示

需要 Python 3.11+、FFmpeg 和 FFprobe。以下命令适用于 macOS / Linux；Windows 可在 WSL 中运行。演示不需要 Codex 账号、云模型、供应商密钥或真实影片。

```bash
git clone https://github.com/xum66183-art/movie-commentary-workflow.git
cd movie-commentary-workflow
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[index,dev]'
python scripts/doctor.py --index
python scripts/run_demo.py --output "$HOME/movie-workflow-demo"
```

`--output` 必须是**仓库外、尚不存在的绝对路径**，路径及其父目录不能是符号链接。如果该目录已有内容，换一个新目录。使用 Release 源码包时，解压后进入完整源码目录执行同样的安装和运行命令；保留整个目录，脚本、技能和合同均从源码树读取。本版支持完整 checkout 或源码归档；wheel 现在包含 `movie_workflow` 执行包；索引技能、模板和旧演示仍需完整源码目录。

演示生成 6 秒原创几何画面、合成音调和合成字幕，实际运行 `prepare`、`search`、`evidence` 和 `verify`，并输出可播放说明视频、证据片段、检索记录和 SHA-256 校验清单。可分享的文件位于 `$HOME/movie-workflow-demo/release/`；包含本机路径和数据库的 `project/` 保留在本地。完整输出说明见 [演示指南](docs/demo.md)。

演示展示离线索引和证据链。它不调用视觉模型或 TTS，不生成解说文稿，也不代表一个影片项目已获创意认可或正式索引锁定。

## 已有能力与使用边界

| 能力 | 可检查的入口 | 使用条件 |
|---|---|---|
| 离线切点、字幕关联、关键帧、SQLite 检索与证据导出 | [`scripts/movie_index.py`](scripts/movie_index.py)、[索引说明](.codex/skills/movie-index/references/local-qwen-tool.md) | 本地依赖与 FFmpeg；演示可复现 |
| Qwen 视觉分析、缓存续跑与原始响应记录 | 同一索引工具的 `analyze` 子命令 | 供应商账户与 API；可能产生费用 |
| Qwen、MiniMax、Fish 与火山 ASR 辅助工具 | [语音技能](.codex/skills/movie-voice-tts/SKILL.md)及其 `scripts/` | 对应供应商权限；有权使用的音频 |
| Qwen VC 音色复用、按锁定文稿分段合成、火山复刻短试音 | [安装与配置](docs/getting-started.md) | 先试音与锁定；本地演示不覆盖付费调用 |
| macOS 烧录字幕 OCR 与 MIDI 配乐源码 | [macOS 工具](docs/macos-tools.md) | 可选；需对应系统能力 |
| 创意阶段、制作状态、数据合同和复检流程 | [工作流](docs/workflow.md)、[合同](docs/data-contracts.md) | Codex 技能指导、连续带声看片与人工判断 |

镜头编排与最终渲染按每个项目的导演方案执行。当前没有适用于任意影片的一键成片器；技术检查也不能代替剧情核对、声音授权或用户样片认可。供应商模型、地域、权限和价格以各供应商当前说明为准。

## v0.4 执行能力

新增统一的项目锁与 SHA-256 校验、配音进程锁与预算预检、可回滚技能升级、OCR 转 SRT，以及按锁定方案执行的普通切镜渲染器。原有离线索引演示和发布流程完整保留。

运行 `python -m movie_workflow.demo --project /absolute/path/to/new-private-demo` 可额外验证模拟旁白、字幕、混音、成片解码和增量缓存。它使用本地正弦音调，不生成真实讲话、不调用付费 API、不登记真实创意认可。完整用法与边界见 **[执行工具](docs/execution-tools.md)**。

## 核心原则

1. **单一总导演主脑**：技能是阶段能力，不是互相丢失上下文的固定岗位。
2. **原片证据优先**：字幕、视觉模型和技术切点只帮助定位，不能代替连续带声原片。
3. **用户尽早看样片**：每版最多集中修正一次，然后交给用户判断。
4. **关键事实严格，普通叙事宽松**：身份、动作、道具和反转必须准确；心理与过渡按整体观感判断。
5. **文件存在不等于采用**：只有 `production/state.json` 中登记的锁才是正式版本。
6. **创意与技术分离**：编导决定镜头和声音意图，渲染只忠实执行。

## 工作流

```text
INDEX_VERIFIED
→ DRAFT_READY
→ DIRECTOR_SCRIPT_REVIEW
→ SCRIPT_LOCKED
→ VOICE_LOCKED
→ NARRATION_LOCKED
→ DIRECTOR_PROXY_PLAN_LOCKED
→ DIRECTOR_PROXY_RENDERED
→ USER_CREATIVE_REVIEW
↔ 按用户反馈修改
→ USER_SAMPLE_APPROVED
→ DIRECTOR_PLAN_LOCKED
→ FINAL_RENDERED
→ SECOND_REVIEW
→ SECOND_REVIEW_PASS
→ FINAL_VERIFIED
```

完整解释见 [工作流](docs/workflow.md) 和 [架构说明](docs/architecture.md)。

## 在 Codex 中使用

运行离线演示后，按 **[安装与配置](docs/getting-started.md)** 准备私有工作区和可选供应商配置，再安装技能：

```bash
python scripts/install_skills.py --dry-run
python scripts/install_skills.py
```

普通安装遇到同名技能仍会停止；可使用带备份与回滚保护的 `--upgrade`，见执行工具说明。`examples/synthetic-demo/` 是用于合同检查的元数据示例；可执行媒体演示使用上面的 `run_demo.py`。

旧项目接入新版状态合同时，先阅读 [状态迁移](docs/migration.md)，不要直接覆盖原状态文件。

仅手动建档时，把 `templates/film-project/` 复制到**仓库之外的私有目录**，填写本地原片信息。使用 `prepare` 自动建索引时直接指定一个新目录，由工具初建项目。然后在 Codex 中使用：

```text
使用 $movie-master-director 接管这个电影项目，并从当前锁定状态继续。
```

## 技能

| 技能 | 职责 |
|---|---|
| `movie-master-director` | 唯一总入口、状态恢复与阶段调度 |
| `movie-index` | 镜头、字幕、关键帧与视觉证据索引 |
| `movie-first-person-writer` | 全片理解与第一人称文稿 |
| `movie-voice-tts` | 试音、整篇旁白和时间戳 |
| `movie-direct` | 文稿预审、叙事节拍、画面与声音方案 |
| `movie-render-qa` | 忠实渲染和技术验收 |
| `movie-second-review` | 正式成片两遍隔离复检 |
| `movie-batch-director` | 用户明确要求时生成隔离候选 |

## 隐私与版权边界

本仓库不包含电影原片、字幕、剧照、证据帧、成片、声音参考、克隆音色、模型权重、API 密钥或真实项目状态。真实项目默认保存在仓库外，并只处理你有权使用的素材。

提交代码前运行：

```bash
python scripts/check_repository.py
python scripts/validate_skills.py
python scripts/validate_project.py examples/synthetic-demo
python -m pytest
python -m ruff check .
```

更详细的隔离规则见 [公开与私有边界](docs/open-source-boundary.md)。

## 反馈与贡献

欢迎用中文或英文提交 [问题报告](https://github.com/xum66183-art/movie-commentary-workflow/issues/new/choose) 和改进建议。请附版本或提交号、运行环境、可复现步骤和脱敏日志；优先用合成素材复现。开发与验证流程见 [CONTRIBUTING](CONTRIBUTING.md)，安全问题见 [SECURITY](SECURITY.md)，版本变更见 [CHANGELOG](CHANGELOG.md)，后续维护方向见 [roadmap](docs/maintainer-roadmap.md)。

## 许可证

代码、技能和项目文档采用 [Apache License 2.0](LICENSE)。第三方服务、模型、电影素材和声音仍分别受其自身条款与权利约束。
