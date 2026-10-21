# 生产工作流

## 状态机

| 状态 | 负责人 | 主要产物 | 进入下一阶段的门槛 |
|---|---|---|---|
| `PROJECT_CREATED` | 总导演 | 项目元数据、初始状态、导演记忆 | 输入路径和项目身份明确 |
| `INDEX_VERIFIED` | `movie-index` | 镜头库、字幕库、视觉库、索引报告 | 覆盖与检索验证通过 |
| `DRAFT_READY` | `movie-first-person-writer` | 剧情地图、POV 简报、编号草稿 | 执笔自审通过 |
| `DIRECTOR_SCRIPT_REVIEW` | `movie-direct` | 文稿预审 | 事实、视角和画面可实现性通过 |
| `SCRIPT_LOCKED` | 总导演 | 锁定文稿及指纹 | 正文不可静默修改 |
| `VOICE_LOCKED` | 用户 + `movie-voice-tts` | 入选供应商和音色 | 用户明确选中试音 |
| `NARRATION_LOCKED` | `movie-voice-tts` | 完整旁白、时间戳、SRT | 文稿指纹与音频文本一致 |
| `DIRECTOR_PROXY_PLAN_LOCKED` | `movie-direct` | 样片画面与混音方案 | 时间轴和关键事实检查通过 |
| `DIRECTOR_PROXY_RENDERED` | `movie-render-qa` | 可播放样片、基础技术报告 | 能播放且无阻断技术错误 |
| `USER_CREATIVE_REVIEW` | 总导演 + 用户 | 观看结论 | 每版最多一次内部集中修正 |
| `USER_SAMPLE_APPROVED` | 用户 | 明确认可记录 | 才可扩展正式全片 |
| `DIRECTOR_PLAN_LOCKED` | `movie-direct` | 正式画面与声音方案 | 全片拼接版完整观看通过 |
| `FINAL_RENDERED` | `movie-render-qa` | 正式成片、技术报告 | 正式技术验收通过 |
| `SECOND_REVIEW` | `movie-second-review` | 两遍看片记录、切点清单 | 所有问题已定位和归责 |
| `SECOND_REVIEW_PASS` | `movie-second-review` | 复检通过记录 | 阻断问题全部复验通过 |
| `FINAL_VERIFIED` | 总导演 | 最终状态锁 | 创意、方案、成片和复检一致 |

## 每个项目的启动顺序

1. 读取根目录 `AGENTS.md`；
2. 读取影片 `project.json`；
3. 读取 `production/state.json`；
4. 读取 `DIRECTOR_MEMORY.md`；
5. 只验证下一阶段直接需要的路径和指纹；
6. 如果工作流为 `PAUSED`，没有用户明确授权时停止；
7. 只继续未完成项，不重跑已经验证的索引或视觉批次。

## 每批导演循环

1. 理解旁白在全片中的因果位置；
2. 按 8～15 秒叙事节拍组织画面；
3. 用字幕、索引、模型和技术切点召回候选；
4. 查看关键事实对应的带声连续原片；
5. 由总导演决定镜头和声音；
6. 渲染真实可播放样片；
7. 正常速度完整观看；
8. 只集中修正 A级事实错误和明显节奏问题一次；
9. 立即交给用户判断。

## 原片接管叙事

原片接管是按内容决定的可选手段，不设置次数或时长配额。使用时必须：

- 替换附近表达同一事实的解说，避免重复；
- 原片期间完全停止解说；
- 保留同步原声和必要字幕；
- 从完整对白、动作或情绪边界进入和退出；
- 在导演方案中登记替换范围和原片精确坐标。
