# 本地普通切镜执行器

依赖已安装的 `movie_workflow`（从仓库执行 `python -m pip install -e ".[index]"`）；技能复制不等于运行包安装。

使用 `python -m movie_workflow.render --project PROJECT --output PROJECT/render/proxy-v001 --mode proxy`。所有输入按项目状态锁、bundle 和素材指纹验证；正式模式另需用户样片认可和正式方案确认。完整合同与可运行的合成示例见源码仓库 `docs/execution-tools.md`，或在源码目录运行 `python -m movie_workflow.demo --project PRIVATE_NEW_DIRECTORY`。

支持单原片普通切镜、固定缩放补边、显式同步原声、旁白、音乐、静音与 SRT。原片与输出区间须等长；变速、转场、动态裁切与任意滤镜均不支持。输出独立版本，SHA 缓存复用只针对完全相同的画面输入；不得把技术收据视为审片认可。
