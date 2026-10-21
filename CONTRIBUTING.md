# Contributing

欢迎用中文或英文报告问题、改进工具或完善文档。提交内容应可审计、可复现，并尊重公开与私有素材的边界。

Issues and pull requests in Chinese or English are welcome. Use synthetic inputs, preserve upstream attribution, and distinguish measured behavior from proposals.

## 报告问题与提出改进

使用 [Issue 模板](https://github.com/xum66183-art/movie-commentary-workflow/issues/new/choose)，注明 tag 或提交号、系统、Python / FFmpeg 版本、最小命令和实际输出。优先用 [离线演示](docs/demo.md) 或自制合成素材复现；日志中删除密钥、本机身份路径和供应商私有信息。涉及安全漏洞时先阅读 [SECURITY](SECURITY.md)。

功能建议说明对应制作阶段、遇到的具体问题和可验证的完成条件。第三方 API 的实际调用与本地模拟测试应分别说明；无需为了贡献而购买模型或语音服务。

## 开发流程

1. Fork 本仓库或从 `main` 创建短生命周期分支。阅读 [AGENTS](AGENTS.md) 与[来源说明](docs/provenance.md)。
2. 只修改与目标直接相关的文件。
3. 对新增行为或修复补充有意义的测试；仅文案、布局或其他低影响可逆变更按实际需要验证。
4. 运行：

   ```bash
   python scripts/check_repository.py
   python scripts/validate_skills.py
   python scripts/validate_project.py examples/synthetic-demo
   python -m pytest
   python -m ruff check .
   ```

5. 修改索引或演示时，在仓库外的新绝对路径运行 `python scripts/run_demo.py --output /absolute/path/new-demo-output`，检查输出与 [演示指南](docs/demo.md) 一致。
6. 在 PR 中写明问题、行为变化、验证命令及结果。分别注明本地验证、CI 和尚未验证的供应商调用；不要只写“全部正常”。

提交 PR 前不需要等待维护者批准。较大改动可以先用 Issue 说明设计，便于提前讨论。

## 禁止提交

- 电影原片、字幕、剧照、证据帧或生成成片；
- 真实声音参考、克隆音色、用户文稿或项目状态；
- API 密钥、`.env`、个人路径或供应商账户信息；
- 未说明来源与许可证的第三方代码、模型和二进制文件。

示例素材必须是合成、公共领域或明确获授权的内容。

演示生成的可公开媒体可作为 Release 附件；不提交到 Git 源码树。不发布包含绝对路径的演示 `project/`、本地请求记录或真实项目数据。当前仓库扫描会拒绝媒体与数据库文件。

## 归因与许可证

本项目采用 [Apache-2.0](LICENSE)。提交改动表示你有权按该许可证贡献相应内容。保留 [NOTICE](NOTICE) 和上游署名；加入第三方源码或素材时注明原始来源、版本、许可证及修改内容。不要把继承的技能、状态合同或模板描述为本版原创，详见 [provenance](docs/provenance.md)。

## 技能修改

保持 `SKILL.md` 简洁，把详细合同放入 `references/`，把确定性工具放入 `scripts/`。技能目录名、frontmatter 中的 `name` 和触发描述必须一致；修改后应运行技能结构校验。

修改创意门槛时同步检查工作流、状态 Schema、模板和验证器。文件存在不能替代正式锁；本地演示不得伪造用户认可、供应商结果或 `FINAL_VERIFIED` 状态。
