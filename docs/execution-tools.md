# v0.4 执行工具

先按 [安装与配置](getting-started.md) 在所用 Python 环境执行 `python -m pip install -e '.[index,dev]'`。八个技能的新增保护共用已安装的 `movie_workflow` 包；复制技能后仍需保留这个 Python 环境。全部测试与合成示例均无需密钥。

## 锁与文件

- `artifact` 和 `path` 都可使用项目相对路径或绝对路径，同时出现时必须指向同一文件。
- 项目相对路径不允许通过 `..` 或符号链接逃出项目目录；明确登记的外部绝对素材路径可以使用。
- `--check-artifacts` 现在要求实际文件及 SHA-256 匹配。只有结构检查通过不代表素材已验证。
- 配音和渲染读取项目声明的 `paths.production_state`；暂停状态会阻止执行。
- 工具不会替用户确认文稿、音色、样片或正式成片。

## 配音保护

Qwen VC 整篇旁白、Qwen/火山短试音使用操作目录进程锁，整篇旁白另有项目进程锁；通用 Qwen/MiniMax/Fish 输出也有文件锁和请求收据。同一操作的未知、拒绝或中断结果不得自动重发，先对账，再明确选择新操作版本或人工恢复。

整篇 Qwen VC 新增参数：

```bash
python .codex/skills/movie-voice-tts/scripts/movie_voice_tts.py qwen-vc-narrate \
  --project /absolute/path/to/private-project \
  --operation-dir /absolute/path/to/private-project/voice/v002 \
  --env-file /absolute/path/to/private-config/.env \
  --max-new-requests 25 --max-billable-characters 20000 --dry-run
```

默认最多 20 次新合成请求、估算 20000 计费字符。已成功或仅待下载的片段不计入新请求；所有已存片段的身份先检查，未知结果先阻断。`budget.json` 保存计划，旁白收据保存供应商用量与缺失用量数量。

可以显式提供 `--price-per-10k` 与 `--max-estimated-cost`，工具在提交前按提供的单价限制估价。不提供单价就保持费用未知；字符估算、单价及总价都不能视为账单保证或硬性金额上限。短试音固定范围有单独上限。通用供应商输出收据保护的是完整输出工作流，不代表只发生一次底层注册/合成 API 请求。

## 完整离线示例

从源码仓库运行，输出目录必须全新且位于仓库外：

```bash
python -m movie_workflow.demo --project /absolute/path/to/private-demo
```

复用原有演示生成彩色几何画面、原声测试音和标明用途的“模拟旁白”正弦音轨；实际执行索引、方案锁指纹、字幕、混音、H.264/AAC 输出、完整解码及第二版本缓存复用。不生成真实讲话，不测试音色相似度，也不登记真实创意认可。

`DEMO_REPORT.json` 给出结果，观看 `render/proxy-v001/proxy.mp4`。默认外挂 SRT；在有 DejaVu Sans 字体的系统可用 `--font /absolute/path/to/DejaVuSans.ttf` 测试烧录。轮子安装用户需另提供源码目录 `--repository /absolute/path/to/checkout`，索引技能和模板保留在源码仓库中。

## 通用渲染器的受支持范围

```bash
python -m movie_workflow.render --project /absolute/path/to/private-project \
  --output /absolute/path/to/private-project/render/proxy-v001 --mode proxy
```

当前实现是明确限定的普通切镜执行器，支持单原片、固定等比例缩放补边、统一帧率、旁白、同步原片接管、环境音、音乐、显式静音，以及外挂或烧录 SRT。不支持变速、转场、动态裁切或任意滤镜；收到未支持字段会报错，不会自行替换创意。

`production/state.json` 中登记 `locks.proxy_plan` 或 `locks.director_plan`，锁引用一个 bundle JSON，并记录对应 `status` 与 `sha256`。正式模式还要求锁的 `user_confirmed=true` 及状态中的 `user_sample_approved=true`。旁白锁必须指向音频，或含 `output_audio`、`output_sha256` 的旁白元数据。

bundle 示例结构（下面省略的 sha256 需填真实指纹）：

```json
{
  "visual_edit": {"artifact": "director/visual_edit.json", "sha256": "..."},
  "audio_mix_plan": {"artifact": "director/audio_mix_plan.json", "sha256": "..."},
  "subtitles": {"artifact": "subtitles/locked.srt", "sha256": "..."}
}
```

方案在既有 Schema 上增加这些执行字段：

- visual：原片 `source_sha256`、旁白 `narration_sha256`，以及 `output`（width、height、fps、subtitle_mode）。
- clip：普通 1 倍速，原片与输出区间等长，输出时间轴连续，边界落在输出帧上，新镜头至少一秒。
- audio event：除静音外，显式 `source`、`source_sha256`，可选 `source_start_ms` 与 `gain_db`。静音不能与其他事件重叠；原片接管必须开启 clip 的 `source_audio`，坐标同步且不与旁白重叠。
- 烧录：bundle 另含 `font` 文件指纹；output 指定 `font_family`，可选 `font_size`、`margin_v`。字体由使用者提供，不分发系统字体。

完整示例由离线 demo 生成，避免维护一份无法运行的假指纹方案。相同版本输入改变会拒绝覆盖；音频或字幕调整可复用未变的画面片段。每个成片记录输出指纹、完整解码、时长及音轨规格，超出满幅的混音会停止。技术收据始终保留 `formal_verified=false`，不修改正式制作状态。

## OCR 后处理与环境诊断

```bash
python -m movie_workflow.subtitles /absolute/path/to/ocr.jsonl /absolute/path/to/draft.srt
python scripts/doctor.py --index --config /absolute/path/to/config/.env --provider qwen
```

OCR 仅合并时间连续且文字相同的采样，保留低置信度复核清单，不自动猜改错字。固定步长得到近似边界，需人工对照原片校正；并不宣称逐字精准对齐。

doctor 实际尝试导入依赖并核对支持版本，按所选供应商检查配置是否存在；不输出配置值，不查询账户权限或余额，也不声称密钥有效。

## 升级与回滚

```bash
python scripts/install_skills.py --upgrade --backup-directory /absolute/path/to/skills-backup-v003
python scripts/install_skills.py --rollback /absolute/path/to/skills-backup-v003
```

普通安装仍保留已有同名技能。升级先暂存新版本，再保存原目录或符号链接，并生成回滚收据；异常会尝试恢复本次改动。回滚会检查安装后文件是否变化，发现用户改动就停止，防止覆盖。进程被强制杀死或磁盘损坏时应保留备份并人工核对，不宣称跨磁盘事务保证。依赖包本身按自己的 Python 环境升级或回退。
