# Movie Commentary Workflow

一套面向 Codex 的电影解说生产工作流：由同一个总导演主脑持续完成全片理解、第一人称文稿、角色配音、选镜、渲染和复检，并用证据、状态锁和用户创意门槛保持结果可追溯。

## 项目定位

当前 `v0.2` 是 **整合增强版（Skills + Tools）**，基于 [straighttttt/movie-commentary-workflow](https://github.com/straighttttt/movie-commentary-workflow) 开发，保留 Apache-2.0 许可证与上游署名。主要提供：

- 8 个可组合的 Codex 技能；
- 可执行镜头索引：切点、字幕关联、关键帧、SQLite 检索、Flash/Plus 分析、缓存续跑与原片证据导出；
- 从镜头索引到正式复检的状态机；
- 项目、导演方案、混音和复检数据合同；
- 千问、MiniMax、Fish Audio 与火山 ASR 的语音工具；
- Qwen VC 音色复用、按锁定文稿分段合成，以及火山复刻短试音；
- 可选的 macOS 烧录字幕 OCR 与 MIDI 配乐渲染源码；
- 项目模板、JSON Schema、安全扫描、合成素材测试和状态校验。

它不是一键生成器。索引、编导和渲染仍要求主脑观看连续原片并做创意判断；通用索引已随仓库分发；镜头编排和最终渲染仍按项目导演方案执行，本版不提供任意影片的一键成片功能。

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

## 快速开始

要求：

- Codex；
- Python 3.11 或更高版本；
- `ffmpeg` 与 `ffprobe`；
- 可选：`uv`，用于隔离 Python 依赖；
- 可选：对应语音供应商账户和合法可用的声音素材。

完整的环境、密钥、技能安装和试跑说明见 **[安装与配置](docs/getting-started.md)**，macOS 辅助工具见 [本地 OCR 与配乐](docs/macos-tools.md)。

安装索引和校验依赖：

```bash
python -m pip install -e '.[index,dev]'
python scripts/doctor.py --index
python scripts/install_skills.py --dry-run
python scripts/install_skills.py
```

验证公开仓库不含私密文件：

```bash
python scripts/check_repository.py
```

验证元数据示例：

```bash
python scripts/validate_project.py examples/synthetic-demo
```

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
python -m pytest
```

更详细的隔离规则见 [公开与私有边界](docs/open-source-boundary.md)。

## 许可证

代码、技能和项目文档采用 [Apache License 2.0](LICENSE)。第三方服务、模型、电影素材和声音仍分别受其自身条款与权利约束。
