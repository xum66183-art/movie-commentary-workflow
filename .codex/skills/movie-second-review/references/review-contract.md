# 二次复检数据合同

## 目录

```text
review/<render-version>/
├── SECOND_REVIEW.md
├── review_issues.json
├── cut_audit.csv
└── evidence/
```

所有时间字段使用整数毫秒。旧版本只读保留。

## `review_issues.json`

```json
{
  "schema_version": 1,
  "film_id": "stable-film-id",
  "render_version": "v001",
  "render_sha256": "...",
  "review_status": "IN_PROGRESS",
  "coverage": {
    "first_pass_start_ms": 0,
    "first_pass_end_ms": 538462,
    "first_pass_complete": true,
    "second_pass_complete": false
  },
  "issues": [
    {
      "id": "review_001",
      "severity": "blocking",
      "status": "open",
      "timeline_start_ms": 3200,
      "timeline_end_ms": 4100,
      "first_visible_frame": 77,
      "category": "micro-cut",
      "boundary_kind": "source-internal",
      "clip_ids": ["clip_001"],
      "source_ranges_ms": [[3530614, 3535077]],
      "observation": "相似构图间出现一瞬间跳画面，观众能感到画面闪动。",
      "evidence": ["evidence/review_001-frames.jpg"],
      "required_outcome": "去除非叙事需要的瞬闪，同时保持当前旁白揭示顺序。",
      "owner": "movie-direct",
      "director_decision": null,
      "resolved_by_version": null,
      "rechecked": false
    }
  ]
}
```

`review_status` 使用：

- `IN_PROGRESS`
- `CHANGES_REQUIRED`
- `SECOND_REVIEW_PASS`

问题 `status` 使用：

- `open`
- `director_decided`
- `rendered`
- `verified`
- `wont_fix`

`blocking` 问题不得以 `wont_fix` 进入通过状态，除非用户明确批准为创意例外，并在记录中写明批准依据。

## `cut_audit.csv`

至少包含：

- `visible_segment`
- `timeline_start_ms`
- `timeline_end_ms`
- `duration_ms`
- `boundary_kind`
- `clip_id`
- `pace`
- `under_2000ms`
- `frame_reviewed`
- `result`
- `issue_id`

自动检测只用于召回候选。每个小于 2 秒的段和每个第一遍观感异常都必须人工逐帧复核。

## `SECOND_REVIEW.md`

记录：

- 最终成片路径、版本和指纹；
- 两遍看片的覆盖范围与完成时间；
- 总切点数、短段数量和逐帧复查数量；
- 按严重程度汇总的问题；
- 给 04 的待处理清单；
- 04 的决定与新导演方案版本；
- 05 的重渲染版本；
- 06 的复验结论；
- `CHANGES_REQUIRED` 或 `SECOND_REVIEW_PASS`。
