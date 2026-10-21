# 公开与私有边界

## 可以进入公开仓库

- `SKILL.md`、技能元数据和通用参考文档；
- 参数驱动、无个人路径的通用脚本；
- JSON Schema、空白模板和合成示例；
- 安装、贡献、安全和架构文档；
- 不含真实值的 `.env.example`。

## 必须保存在私有项目

- 电影原片、外挂字幕和 OCR 字幕；
- 剧照、关键帧、视觉模型响应和证据片；
- 文稿、旁白、声音参考、克隆音色和成片；
- `project.json`、`production/state.json` 和导演记忆的真实实例；
- API 密钥、供应商账户、请求日志和费用记录；
- 模型权重、运行时、缓存和第三方仓库副本。

## 推荐目录

```text
Documents/
├── movie-commentary-workflow/   # 公开代码仓库
└── movie-projects-private/      # 不进入公开仓库
    ├── film-a/
    └── film-b/
```

## 发布前检查

1. `git status` 只包含预期源文件；
2. `python scripts/check_repository.py` 通过；
3. 没有 `.env`、媒体、数据库、模型或大文件；
4. 没有 `/Users/...`、`C:\\Users\\...` 等个人路径；
5. 没有真实电影名、人物项目记忆或供应商私有编号；
6. 测试和技能结构校验通过。
