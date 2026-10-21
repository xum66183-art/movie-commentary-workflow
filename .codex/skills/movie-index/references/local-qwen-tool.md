# 本地千问索引工具

随技能分发的 `scripts/movie_index.py` 提供北京地域百炼适配器、离线镜头索引和原片证据导出。

## 配置与入口

安装依赖后使用 `python scripts/movie_index.py`（从仓库根目录）或 `python <技能目录>/scripts/movie_index.py`。下文 `movie-index` 表示该入口；可以自行设置 shell alias。配置文件由 `MOVIE_WORKFLOW_ENV_FILE` 指定，未设置时读取 `${MOVIE_WORKFLOW_ROOT:-$HOME/MovieCommentaryWorkflow}/config/.env`。字段为：

- `DASHSCOPE_API_KEY`：密钥，只存在本地配置，不写进项目、日志或 Git。
- `MOVIE_DASHSCOPE_REGION=cn-beijing`。
- `DASHSCOPE_BASE_URL`：默认已验证的 `https://dashscope.aliyuncs.com/compatible-mode/v1`。可改为控制台提供的北京业务空间专属地址。
- `QWEN_VISION_MODEL=qwen3-vl-flash`：默认视觉模型，可在单次运行指定 Plus。

源码随本技能分发。先将 MOVIE_WORKFLOW_ROOT 设置为仓库之外的私有目录，示例命令按此约定存放产物。

```bash
movie-index check --live
movie-index prepare --project "$MOVIE_WORKFLOW_ROOT/projects/film-example" \
  --video /absolute/path/to/film.mp4 --subtitle /absolute/path/to/film.srt \
  --title "影片名"
movie-index analyze --project "$MOVIE_WORKFLOW_ROOT/projects/film-example" --max-units 20
movie-index status --project "$MOVIE_WORKFLOW_ROOT/projects/film-example"
movie-index search --project "$MOVIE_WORKFLOW_ROOT/projects/film-example" "黑色手机"
movie-index evidence --project "$MOVIE_WORKFLOW_ROOT/projects/film-example" shot-000001
movie-index verify --project "$MOVIE_WORKFLOW_ROOT/projects/film-example"
```

没有独立字幕时省略 `--subtitle`。支持 UTF-8/GB18030 的 SRT、ASS、VTT；坏字幕报错，不静默忽略。字幕只在本地用于检索，不作为视觉模型的剧情证据。

项目可以存放在用户选择的 SSD 或其他私有目录；工具拒绝把产物写进自身仓库或已安装技能目录。建议使用私有工作区的 `projects/`。影片原始文件保持不变。支持 macOS/Linux；Windows 请使用 WSL。

## 批量、续跑与费用

`prepare` 生成原片指纹、媒体信息、技术切点、字幕关联、关键帧和两个 SQLite 数据库，不调用云模型。默认每个视觉单元最多 20 秒、取三张图片，边长上限 768；这些均可调整，技术镜头和原片坐标保持独立。只有超长镜头因传输需要才拆视觉单元。

`analyze` 每次默认最多分析 20 个未完成单元。再次执行同一命令自动续跑，已成功的相同输入、模型、提示词及输出参数不再请求。`--max-units 0` 明确分析所有剩余单元；在原片规模与试跑费用已明确后才使用。429、服务端错误和网络异常最多尝试三次；认证或模型权限错误停止当前批次。网络超时可能已经计费，缺失用量不能按零成本处理。

Plus 必须明确指定单元，例如：

```bash
movie-index analyze --project "$MOVIE_WORKFLOW_ROOT/projects/film-example" \
  --model qwen3-vl-plus --unit-id shot-000001-unit-001
```

Flash 和 Plus 的响应与检索来源分别保留，不覆盖。原始响应逐次保存，数据库记录状态、尝试、模型、提示词、Token 用量、耗时和内置历史价格估算（不能当作当前报价）。费用不是账单上限，以百炼账单为准。

原片、字幕或准备参数改变时，使用新项目目录，保留旧证据。损坏关键帧拒绝调用；失败或输出截断的响应不进入成功缓存。

## 检索与证据

`search` 合并字幕、视觉 JSON 和有证据来源的人工纠错，返回镜头区间、关键帧和各项观察来源。中文使用显式字与双字片段建立 FTS 检索；先由主脑把自然语言拆成具体线索，工具的召回分数不代表创意优劣。

人工纠错写入 `database/retrieval_overrides.json` 的 `overrides` 数组，每项包含：`target_id`（镜头或视觉单元）、`corrected_facts`、`evidence`、`author`、`created_at`、`reason`。保留原始模型观察，纠错的事实由主脑查看原片后确认。

`evidence` 为镜头或视觉单元导出三张按时间排序的原片图片和有前后余量的片段，保留存在的原声。`evidence.json` 记录原片区间与时间坐标。

`verify` 检查来源指纹、完整时间轴、图片可读性、字幕关联及数据库完整性。项目与正式状态只在初建时创建；后续工具不修改导演锁或制作状态。通过结构检查后，仍需按 `retrieval-and-validation.md` 做代表性检索和连续带声看片；报告中的 `verified` 始终为 false，由唯一总导演完成正式认可。

官方接口：[图像与视频理解](https://help.aliyun.com/zh/model-studio/vision)。官方费用：[百炼价格](https://help.aliyun.com/zh/model-studio/model-pricing)。


## 分析代理

`prepare --analysis-proxy /absolute/path/to/proxy.mp4` 可使用轻量代理检测切点和提取检索图。`--video` 始终指定原片；媒体元数据、原片帧号与证据导出仍使用原片。代理须从原片零点开始、不变速、不剪裁时间，时长误差不超过100毫秒；调用者还须核对画面在时间轴上对齐，不能只凭同长认定。代理指纹也参与续跑校验。

代理帧率不同会降低切点时间分辨率；检测器的 `--min-scene-frames` 按代理帧率解释。必须在项目中记录转换方法、时间精度与已核对的对齐依据。HDR转SDR分析图不代表正式成片调色已获认可。


`analyze --workers 4` 可并发提交彼此独立的视觉单元；默认仍是1。同一项目仍由父调用持有唯一文件锁，各工作线程使用独立SQLite连接，父调用统一生成汇总。已成功缓存不重发；认证/权限错误停止新任务（至多已有并发请求仍可能完成）。先试跑有限单元并确认费用再增加并发和覆盖范围。

## 原始响应恢复

视觉模型偶尔将objects中的字符串返回为name、description、appearance、evidence、confidence标量字典。解析器仅接受这些已观察到的字段组合，以文本无损保留；未知字段或坏类型仍拒绝。下一次analyze会先在项目锁内重新解析同源、同提示词与同输出参数的原始失败响应，恢复成功缓存且不发新请求。原始响应、失败尝试、用量仍保留，恢复来源登记在vision/normalization-recovery.json。规范化成功不表示模型语义真实或索引已获导演认可。

HTTP 400 的 Arrearage（欠费/余额不足）及已观察到的余额不足错误也会停止整批，不继续逐单元提交。处理账户状态后可以正常续跑，成功缓存不重新请求。
