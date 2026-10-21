# macOS 本地辅助工具

这两个工具从实际制作中抽取，只包含通用源代码；不包含原片、字幕、声音、乐谱或系统音色库。它们要求 macOS、Swift 和相应系统框架，不在 Linux CI 中运行。

## 烧录字幕 OCR

先用 FFmpeg 在字幕区域按固定步长取 JPG，文件名须为从 `000001.jpg` 开始的连续数字。OCR 输出原始候选和置信度，采样时间不是精确字幕起止时间，仍需人工纠错与合并。

```bash
swift scripts/macos/local_subtitle_ocr.swift /absolute/path/to/cropped-frames /absolute/path/to/ocr.jsonl 0 0.5
```

参数依次是图片目录、输出 JSONL、起始秒数、步长秒数。脚本使用本地 Apple Vision；不调用云 API。可选环境变量 `OCR_REVISION` 指定系统支持的识别版本。只适用于固定步长采样，不适用于可变帧率时间戳直接推算。

## MIDI 乐谱渲染

```bash
swift scripts/macos/render_music_score.swift /absolute/path/to/score.json /absolute/path/to/music.wav
```

输入结构：

```json
{"duration":4,"tracks":[{"name":"piano","program":0,"volume":0.3,"pan":0}],"notes":[{"track":0,"start":0,"duration":1,"pitch":60,"velocity":50}]}
```

输出 48kHz 双声道 WAV。`program` 为从零开始的 GM 音色序号，`track` 为轨道数组下标，音符起点与时长以秒计。使用 macOS 自带音色库，不在仓库分发该库；其他系统需自备合适的合成器及音色授权。乐谱来源与用途由使用者确认，工具不提供配乐版权或可商用承诺。
