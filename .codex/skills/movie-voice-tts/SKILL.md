---
name: movie-voice-tts
description: 使用千问 Audio 3.0 TTS Plus、MiniMax Speech 2.8 HD 和 Fish Audio S2.1 Pro 生成或克隆电影角色旁白，包括直接复用用户选定的 Fish 公共音色编号并保存原生时间戳；供应商没有原生时间戳时，使用火山引擎语音识别恢复中文字幕或字级时间戳。制作中英文第一人称电影旁白、三模型克隆试音、供应商对比、整篇配音、字幕定时或音文对齐时使用。
---

# 电影角色配音与时间戳

统一使用本技能附带的程序，保证供应商选择、密钥、元数据、时间戳和输出处理方式一致。

## 检查生产状态

1. 读取项目 `AGENTS.md` 和影片的 `production/state.json`。
2. 第一人称角色和 `POV_BRIEF.md` 确定后，可以制作短试音。
3. 生成整篇旁白前，必须确认状态为 `SCRIPT_LOCKED`，并核对文稿指纹。
4. 用户明确选择试音版本后，才能设置 `VOICE_LOCKED`。
5. 不得为了修正读音擅自修改锁定文稿。文本问题必须退回执笔人。

## 选择生成路线

1. 原生中文旁白优先使用千问 `qwen-audio-3.0-tts-plus`。
2. 用户已选定 Fish 公共音色，或英文参考音频克隆英文旁白时，优先使用 Fish `s2.1-pro-free`。
3. 需要额外对比或可长期复用的 MiniMax 音色编号时，使用 MiniMax `speech-2.8-hd`。
4. 把英文参考音频克隆中文旁白视为实验路线；生成整篇前必须先做短试音。
5. 优先使用供应商原生时间戳。千问 Audio 3.0 或其他缺少时间戳的结果，使用火山引擎语音识别补齐。
6. 需要查看适配器基线、供应商差异和公平对比方法时，读取 [references/providers.md](references/providers.md)。

## 准备输入

- 使用 10～20 秒干净参考音频，只包含一位说话人，噪声和音乐尽量少。
- 使用 Fish 零样本参考音频时，必须提供准确逐字稿；使用公开音色模型编号时，不需要再次下载参考音频。
- 正式文稿使用 UTF-8 文本文件。
- 单次试音使用一小段文稿，目标时长为 8～15 秒。
- 在元数据中记录文稿、供应商、模型、音色编号、参考音频指纹、语言和生成参数。
- 只克隆用户有权使用的声音。

## 制作三模型试音

1. 千问、MiniMax、Fish 必须使用同一份锁定参考音频、参考逐字稿、目标语言、试音文案、情绪要求和可比较播放响度。
2. 每份试音控制在 8～15 秒；添加可选风格指令前，先导出各供应商未经风格修饰的基准版本。
3. 把三份试音和元数据保存到影片项目的 `voice/auditions/`。
4. 编写 `AUDITION_REPORT.md`，记录供应商、模型、音色新建或复用、时长、格式、身份稳定度、中文口音、情绪适配、瑕疵和输出路径。
5. 向用户展示三份可播放音频，把用户的明确选择记录为 `VOICE_LOCKED`。
6. 某家供应商失败或暂不可用时，准确报告失败原因；不得把两模型对比冒充要求的三模型试音。

## 运行程序

先把仓库根目录的 `.env.example` 复制为本地 `.env` 并填写真实值，或者直接设置进程环境变量。然后从仓库根目录运行：

```bash
uv run --with requests --with fish-audio-sdk==1.3.0 \
  .codex/skills/movie-voice-tts/scripts/movie_voice_tts.py check
```

千问中文克隆：

```bash
uv run --with requests --with fish-audio-sdk==1.3.0 \
  .codex/skills/movie-voice-tts/scripts/movie_voice_tts.py qwen \
  --reference "/absolute/path/reference.wav" \
  --reference-language en \
  --language zh \
  --text-file "/absolute/path/narration.txt" \
  --output "/absolute/path/qwen.wav"
```

MiniMax 克隆：

```bash
uv run --with requests --with fish-audio-sdk==1.3.0 \
  .codex/skills/movie-voice-tts/scripts/movie_voice_tts.py minimax \
  --reference "/absolute/path/reference.wav" \
  --reference-language en \
  --language zh \
  --text-file "/absolute/path/narration.txt" \
  --output "/absolute/path/minimax.mp3"
```

Fish 同语言或跨语言克隆：

```bash
uv run --with requests --with fish-audio-sdk==1.3.0 \
  .codex/skills/movie-voice-tts/scripts/movie_voice_tts.py fish \
  --reference "/absolute/path/reference.wav" \
  --reference-text-file "/absolute/path/reference-transcript.txt" \
  --language en \
  --text-file "/absolute/path/narration.txt" \
  --output "/absolute/path/fish.mp3"
```

Fish 公共音色整篇生成并保存原生时间戳：

```bash
uv run --with requests --with fish-audio-sdk==1.3.0 \
  .codex/skills/movie-voice-tts/scripts/movie_voice_tts.py fish \
  --fish-reference-id "https://fish.audio/m/<模型编号>" \
  --language zh \
  --text-file "/absolute/path/NARRATION_FIRST_PERSON_DRAFT.md" \
  --strip-markdown-headings \
  --output "/absolute/path/narration.mp3" \
  --timestamp-json "/absolute/path/narration.timestamps.json" \
  --output-srt "/absolute/path/narration.srt"
```

`--fish-reference-id` 可以接收 32 位模型编号，也可以直接接收 `fish.audio/m/<模型编号>` 链接。该路线调用 Fish 带时间戳流式接口，按事件顺序拼接音频，并只保留每个内部块的最后一份累计对齐快照，避免重复时间戳。

使用 `--voice-id` 复用现有千问或 MiniMax 音色。未提供时，程序会优先复用输出元数据中已有的音色编号，否则新建音色。

设置 `VOICE_LOCKED` 后，只使用入选供应商和音色生成完整 `SCRIPT_LOCKED` 文稿。保留每次请求的元数据，使局部句子能够单独重录而不改变已接受的相邻音频。全部片段接受后，先合并成唯一最终旁白，再生成正式时间戳。

## 使用火山引擎恢复时间戳

千问 Audio 3.0 输出或其他没有原生时间戳的音频，使用以下后备流程：

```bash
uv run --with requests \
  .codex/skills/movie-voice-tts/scripts/volc_asr.py \
  --audio "/absolute/path/narration.wav" \
  --language zh-CN \
  --output-json "/absolute/path/narration.timestamps.json" \
  --output-srt "/absolute/path/narration.srt"
```

JSON 中的 `utterances[].words[]` 保存字级毫秒时间戳，SRT 使用接口返回的句子边界。修改请求参数、密钥处理或输出逻辑前，读取 [references/volc-asr.md](references/volc-asr.md)。

## 验证并锁定

1. 确认配音程序生成音频和相邻 JSON 元数据；Fish 公共音色路线还必须生成原生时间戳 JSON 和 SRT。
2. 使用 `ffprobe` 和 `ffmpeg` 检查时长、采样率、声道、响度、峰值和削波。
3. 在相近播放响度下比较每份试音，淘汰中文外国口音、音色身份不稳定、吞字、姓名误读和机械停顿。
4. 确认最终旁白文本指纹与 `SCRIPT_LOCKED` 一致。
5. Fish 公共音色路线直接使用原生时间戳；其他路线没有原生时间戳时运行语音识别后备流程。
6. 将识别出的连续文字与源文稿对比，并检查第一项和最后一项时间戳。
7. 交付最终音频、元数据、时间戳 JSON 和 SRT，把它们的指纹记录为 `NARRATION_LOCKED`。

## 保护密钥

- 优先使用进程环境；也可以使用仓库根目录或本技能目录中被 Git 忽略的 `.env`。
- 需要把密钥文件放在仓库外时，使用 `MOVIE_WORKFLOW_ENV_FILE` 指向它。
- 火山引擎变量可以通过 `VOLCENGINE_ENV_FILE` 间接加载；该文件必须只保存在本地。
- 不得在终端输出、元数据或面向用户的内容中显示密钥。
- 使用项目 `.gitignore` 排除 `.env`。
- 密钥一旦在本地项目以外暴露，继续使用前必须轮换。
