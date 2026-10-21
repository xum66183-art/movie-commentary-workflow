# 安装与配置

## 运行环境

支持 Python 3.11+、macOS 或 Linux，Windows 使用 WSL。FFmpeg/FFprobe 需先安装并加入 PATH。macOS 的字幕 OCR 和 MIDI 配乐工具另需 Xcode Command Line Tools；它们不是核心流程的必需依赖。只有 Fish 路线才需要 Fish SDK。

```bash
git clone https://github.com/xum66183-art/movie-commentary-workflow.git
cd movie-commentary-workflow
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[index,dev]'
python scripts/doctor.py --index
python scripts/install_skills.py --dry-run
python scripts/install_skills.py
```

安装器复制八个技能到 `${CODEX_HOME:-$HOME/.codex}/skills`，遇到任意同名技能就停止，保留现有版本。需要更新时先备份已有技能，再选择新的安装位置或自行替换。重新打开 Codex 会话发现技能。也可以只在此仓库使用 `.codex/skills`，无需全局安装。

本版以 `pyproject.toml` 和上面的 pip 安装命令为准；未分发跨平台冻结锁。使用 uv 的用户可以按自己的平台生成锁文件。

## 私有工作区与密钥

外接 SSD 可作为下面变量的目录，目录名由使用者选择。不要把工作区放在本仓库里。

```bash
export MOVIE_WORKFLOW_ROOT="$HOME/MovieCommentaryWorkflow"
export MOVIE_WORKFLOW_ENV_FILE="$MOVIE_WORKFLOW_ROOT/config/.env"
mkdir -p "$MOVIE_WORKFLOW_ROOT/config" "$MOVIE_WORKFLOW_ROOT/projects" "$MOVIE_WORKFLOW_ROOT/tmp"
cp .env.example "$MOVIE_WORKFLOW_ENV_FILE"
chmod 600 "$MOVIE_WORKFLOW_ENV_FILE"
```

编辑私有配置文件，只填写所选供应商所需的字段。索引工具读取该配置文件；语音工具可用 `--env-file`，或读取 `MOVIE_WORKFLOW_ENV_FILE`。`doctor` 只显示当前进程中变量是否存在，不读取文件，也不显示值。

| 用途 | 必需配置 | 说明 |
|---|---|---|
| 离线切点、字幕检索、取证据 | 无 API | 需索引依赖与 FFmpeg |
| Qwen 视觉分析 | `DASHSCOPE_API_KEY` | 北京接口；Flash 先有限试跑，Plus 定点复核 |
| Qwen VC 克隆及旁白 | `DASHSCOPE_API_KEY` | 克隆与合成是不同的付费动作；需有权使用参考声音 |
| MiniMax / Fish | 对应的 API Key | 按需任选，无需全部开通 |
| 火山 ASR | `VOLCENGINE_APPID`、`VOLCENGINE_TOKEN` | 按供应商要求准备音频地址 |
| 火山复刻短试音 | `VOLCENGINE_TTS_API_KEY` | 专用语音服务权限；方舟模型密钥不等于语音权限 |

模型名、可用地域、权限和价格以供应商账户及官方文档为准。代码中的价格是历史估算，不能视为当前报价、免费额度或费用上限。先检查 `--help`，再做有限试跑。模型分析和自动技术检查均不能替代最终完整带声观看。

## 建立索引

不要先复制项目模板到同一个目录：`prepare` 会创建项目和初始状态，已有项目先阅读迁移文档。

```bash
python scripts/movie_index.py prepare \
  --project "$MOVIE_WORKFLOW_ROOT/projects/my-film" \
  --video /absolute/path/to/authorized-film.mp4 \
  --subtitle /absolute/path/to/authorized-subtitles.srt --title "我的影片"
python scripts/movie_index.py analyze --project "$MOVIE_WORKFLOW_ROOT/projects/my-film" --max-units 3
python scripts/movie_index.py search --project "$MOVIE_WORKFLOW_ROOT/projects/my-film" "道具线索"
python scripts/movie_index.py evidence --project "$MOVIE_WORKFLOW_ROOT/projects/my-film" shot-000001
python scripts/movie_index.py verify --project "$MOVIE_WORKFLOW_ROOT/projects/my-film"
```

`prepare`、`search`、`evidence`、`verify` 不调用云模型。`analyze` 会提交关键帧并可能产生费用；默认每次最多 20 个新单元，`--max-units 0` 才是全部剩余单元。成功结果可复用。该实现使用 POSIX 文件锁，原片不变更。更多参数见[索引工具](../.codex/skills/movie-index/references/local-qwen-tool.md)。

## 配音及导演流程

在 Codex 中使用 `$movie-master-director` 接管私有项目。先确认叙述者与文稿，再试音并确认音色，最后生成整篇旁白。克隆只使用有权处理的音频。

```bash
python .codex/skills/movie-voice-tts/scripts/movie_voice_tts.py --help
python .codex/skills/movie-voice-tts/scripts/movie_voice_tts.py qwen-vc-audition --help
python .codex/skills/movie-voice-tts/scripts/movie_voice_tts.py qwen-vc-narrate --help
```

`qwen-vc-narrate` 读取项目中已确认的文稿与音色锁，按段生成，复用同一音色。旧式锁格式要求路径为绝对路径；不要把真实锁文件提交到仓库。`--dry-run` 验证输入但不请求 API。结果未知的合成请求不会自动重发，先核查本地记录及账单。

文稿、旁白、时间戳和导演方案逐步锁定；用户认可样片后才扩展全片。镜头编排及各项目渲染仍由技能指导完成，本版不提供适用于任意电影的一键渲染器。流程与合同见[工作流](workflow.md)和[数据合同](data-contracts.md)。
