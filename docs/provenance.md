# 来源、归因与本版贡献 / Provenance

## 上游基础

本仓库是 [straighttttt/movie-commentary-workflow](https://github.com/straighttttt/movie-commentary-workflow) 的独立整合版。所采用的上游基线为 [`3d50c17`](https://github.com/straighttttt/movie-commentary-workflow/tree/3d50c17)，上游提交说明为 `Initial open-source skills edition`。本仓库保留上游 [Apache-2.0 许可证](../LICENSE)，并在 [NOTICE](../NOTICE) 中登记来源。此仓库采用独立 Git 历史；上游来源通过基线链接与归因文件追溯。

This is an independent integrated edition of the upstream project above, based on commit `3d50c17`. The upstream Apache-2.0 license is preserved. This repository has its own Git history; the linked baseline and NOTICE record its source.

## 哪些来自上游

以下核心设计与源文件来自上游，不能作为本版从零原创的成果：

- 八个阶段技能的整体结构、唯一总导演入口、原片证据优先、用户样片认可和二次复检原则；本版对索引技能补充了可执行工具的接入说明。
- `schemas/` 中的项目、状态、导演方案、混音和复检数据合同。
- `templates/film-project/`、`examples/synthetic-demo/` 及导演记忆模板。
- `docs/architecture.md`、`docs/workflow.md`、`docs/data-contracts.md`、`docs/migration.md` 和 `docs/open-source-boundary.md`。
- 语音技能的基础脚本和供应商说明，以及技能结构、项目状态与仓库边界检查的基础实现。

The eight-skill framework, creative approval model, state schemas, templates and core workflow documentation are upstream work. Existing voice helpers and validators also have an upstream foundation. Integration changes do not transfer their authorship.

## 本版可检查的增量

| 增量 | 源码或证据入口 | 说明 |
|---|---|---|
| 可执行镜头索引 | [技能内索引实现](../.codex/skills/movie-index/scripts/movie_index.py)、[仓库入口](../scripts/movie_index.py)、[索引测试](../tests/test_movie_index.py) | 本地切点、字幕关联、关键帧、SQLite 检索、证据片段；另有可选 Qwen 视觉分析、缓存与失败恢复 |
| Qwen VC 与火山复刻辅助 | [Qwen 试音](../.codex/skills/movie-voice-tts/scripts/qwen_vc_audition.py)、[分段旁白](../.codex/skills/movie-voice-tts/scripts/qwen_vc_narration.py)、[火山复刻](../.codex/skills/movie-voice-tts/scripts/volc_voice_clone.py)、[测试](../tests/test_qwen_vc.py) | 在上游语音技能基础上补充实现与接入；供应商服务和模型属于第三方 |
| macOS 可选工具 | [字幕 OCR](../scripts/macos/local_subtitle_ocr.swift)、[MIDI 渲染](../scripts/macos/render_music_score.swift) | 调用系统能力的本地源码，不分发系统音库 |
| 安装、诊断与验证增强 | [技能安装器](../scripts/install_skills.py)、[环境检查](../scripts/doctor.py)、[项目校验](../scripts/validate_project.py)、[仓库检查](../scripts/check_repository.py) | 技能安装与环境诊断为本版工具；校验器在上游基础上增强 |
| 可复现公开演示与文档 | [演示入口](../scripts/run_demo.py)、[演示指南](demo.md)、[英文 README](../README.en.md)、[变更记录](../CHANGELOG.md) | 仅合成素材；公开输出与含本机路径的工作目录分离 |

上表描述源码中可检查的功能，不代表所有供应商能力均已在每个平台实测，也不代表外部用户采用量、商业成果或性能基准。提交记录与发布包用于确认具体版本；测试范围和运行结果应以相应版本的 CI 与 Release 说明为准。

The table identifies inspectable integration work: executable indexing, selected voice and macOS helpers, installation and diagnostic tools, validator improvements, and the synthetic demo. It is not a claim of adoption, commercial outcomes, provider-wide validation or benchmark performance.

## 素材与第三方依赖

离线演示的几何画面、音调和字幕由仓库脚本生成，不取自电影、真实人物或语音模型。它展示工具的数据流与坐标证据，不展示真实影片的叙事质量。生成媒体在仓库外输出；如作为 Release 附件发布，必须按演示指南只发布整理后的 `release/` 文件。

FFmpeg、PySceneDetect、Python 依赖、操作系统框架及云服务各自受其许可证或条款约束。本仓库不分发模型权重、供应商 SDK 副本、系统音库、真实影片或声音参考。OpenAI、Codex、Qwen、MiniMax、Fish Audio 等名称仅用于说明兼容或接入对象；本项目未获其官方背书。

Contributions must preserve upstream attribution and identify any new third-party code or assets. See [CONTRIBUTING](../CONTRIBUTING.md) before submitting a change.
