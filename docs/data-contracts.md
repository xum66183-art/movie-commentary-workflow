# 数据合同

机器可读时间统一使用整数毫秒。路径在真实私有项目中可以是绝对路径；公开模板和示例不得包含个人绝对路径。

## 项目元数据

`project.json` 保存稳定影片编号、输入来源、媒体信息、索引配置和核心路径。不得只凭文件名判断输入没有变化。

Schema：[project.schema.json](../schemas/project.schema.json)

## 生产状态

`production/state.json` 只保存当前事实、正式锁、版本、路径、指纹和下一动作。候选文件存在不代表采用。

Schema：[state.schema.json](../schemas/state.schema.json)

## 导演方案

`visual_edit.json` 描述完整时间轴、原片坐标、节奏和创作目的：

- 时间轴必须连续，无空档或重叠；
- 原片区间必须合法；
- 后期素材块不得短于 1 秒；
- `pace` 只使用 `normal`、`suspense`、`climax`。

Schema：[visual-edit.schema.json](../schemas/visual-edit.schema.json)

## 声音方案

`audio_mix_plan.json` 登记旁白、电影原声、环境声、静默和音乐事件。渲染只能执行，不能重新设计声音意图。

Schema：[audio-mix-plan.schema.json](../schemas/audio-mix-plan.schema.json)

## 二次复检

`review_issues.json` 保存成片指纹、两遍观看覆盖率、问题严重程度、时间码、证据、责任归属和复验状态。

Schema：[review-issues.schema.json](../schemas/review-issues.schema.json)

## 指纹规则

正式锁至少记录直接输入的 SHA-256。文稿正文、旁白、时间戳或导演方案发生变化时，所有依赖旧指纹的下游锁都必须失效并重新确认。

已有私有项目接入本合同前，按 [状态迁移](migration.md) 做只读预检和显式迁移。
