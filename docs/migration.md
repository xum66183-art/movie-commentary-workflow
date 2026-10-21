# 状态迁移

公开版 `v0.1` 使用比早期实验项目更严格的锁合同。迁移必须新建状态版本或先备份原文件，不得根据目录中“看起来最新”的文件自动推断采用版本。

## 只读预检

```bash
python scripts/validate_project.py /absolute/path/to/private-film-project --json
```

默认只检查元数据、状态结构和锁的逻辑关系；增加 `--check-artifacts` 后才检查已登记产物是否存在。

## 必要字段

1. `project.json` 至少声明 `title`、`title_zh` 或 `title_original` 之一；
2. `state.film_id` 与 `project.id` 一致；
3. 每个正式锁都明确保存对应 `status`；
4. 已进入某一阶段时，其所有前置锁都必须存在；
5. `canonical_project` 必须指向当前项目的 `project.json`；
6. 未完成且处于 `ACTIVE` 的项目必须声明 `next_legal_action`；
7. `FINAL_VERIFIED` 不再声明下一动作。

标准锁状态映射：

| 锁 | `status` |
|---|---|
| `index` | `INDEX_VERIFIED` |
| `script` | `SCRIPT_LOCKED` |
| `voice` | `VOICE_LOCKED` |
| `narration` | `NARRATION_LOCKED` |
| `director_plan` | `DIRECTOR_PLAN_LOCKED` |
| `final_render` | `FINAL_RENDERED` |
| `second_review` | `SECOND_REVIEW_PASS` |

## 不允许自动迁移的内容

- 用户是否认可样片；
- 哪一个候选文稿、音色或导演方案被采用；
- 历史成片是否可以视为正式渲染；
- 没有连续原片证据支持的剧情事实；
- 状态文件与导演记忆冲突时的最终判断。

这些项目必须由总导演依据用户反馈、指纹和现有锁明确确认。
