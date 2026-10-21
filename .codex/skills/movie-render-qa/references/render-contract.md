# 渲染数据合同

## 输入

- 原片与指纹；
- 锁定的 `visual_edit.json`；
- 锁定的 `audio_mix_plan.json`；
- 旁白、时间戳和字幕；
- 输出规格。

所有时间使用整数毫秒。

## 样片输出

```text
render/proxy-v001/
├── segments/
├── cache-manifest.json
├── picture-lock.mp4
├── subtitles.srt
├── proxy.mp4
└── BASIC_VALIDATION.md
```

编导要求时，可以增加局部审核片段。

## 正式输出

```text
render/v001/
├── segments/
├── cache-manifest.json
├── picture-lock.mp4
├── subtitles.srt
├── final.mp4
├── qa/
└── VALIDATION.md
```

不得覆盖旧版本。

## 缓存键

包含：

- 原片指纹和精确区间；
- 裁切、缩放、帧率、像素格式；
- 音轨与标准化参数；
- 编码器、预设和质量参数；
- 导演方案指纹。

## 不变量

- 保持导演方案的顺序和原片区间；
- 只保留方案明确要求的原片声音；
- 画面、旁白和字幕时长一致；
- 使用确定字体并记录；
- 默认输出兼容的 H.264/AAC；
- 导演方案不可执行时停止，不自行修复创意。
