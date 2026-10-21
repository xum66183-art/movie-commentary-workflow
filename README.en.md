# Movie Commentary Workflow

[中文](README.md) · [Offline demo](docs/demo.md) · [Releases](https://github.com/xum66183-art/movie-commentary-workflow/releases) · [CI](https://github.com/xum66183-art/movie-commentary-workflow/actions/workflows/ci.yml) · [Provenance](docs/provenance.md)

Codex skills and local tools for evidence-based movie commentary production. Eight stage skills organize story analysis, first-person writing, narration, shot planning, rendering and review. Local indexing tools preserve source coordinates, retrieval records and evidence clips; state locks record which creative artifacts were actually accepted.

This independent integrated edition is based on [straighttttt/movie-commentary-workflow](https://github.com/straighttttt/movie-commentary-workflow). The skill framework, production state contracts and templates come from that upstream project. This edition adds local indexing, selected voice helpers, installation and validation improvements, and a reproducible demo. See [provenance](docs/provenance.md), [NOTICE](NOTICE) and the preserved [Apache-2.0 license](LICENSE). This project is not affiliated with OpenAI or the connected service providers.

## Run the offline demo

Requirements: Python 3.11+, FFmpeg and FFprobe on your PATH. The commands below target macOS / Linux; use WSL on Windows. The demo needs no Codex account, API credentials, cloud models or film footage.

```bash
git clone https://github.com/xum66183-art/movie-commentary-workflow.git
cd movie-commentary-workflow
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[index,dev]'
python scripts/doctor.py --index
python scripts/run_demo.py --output "$HOME/movie-workflow-demo"
```

The output must be a new absolute path outside the repository, with no symlinks in the path or its parent directories. Choose a different path if it already exists. For a Release source archive, extract it, enter the complete source directory, and run the same installation and demo commands. Keep that directory: scripts, skills and contracts are loaded from the source tree. Supported distributions are the complete checkout or source archive. A wheel installs dependency metadata only; it does not contain standalone runnable tools.

The demo creates six seconds of original geometric video, a synthetic tone and synthetic subtitles, then runs the real `prepare`, `search`, `evidence` and `verify` commands. The output includes an explanatory video, evidence clips, retrieval records and a SHA-256 manifest. Shareable files are under `$HOME/movie-workflow-demo/release/`; keep the `project/` directory local because it contains machine paths and databases. See the [demo guide](docs/demo.md) for outputs and checks.

This demonstrates offline indexing and evidence export. It does not run a vision model, generate TTS narration or a commentary script, or grant an index or creative approval lock.

## What is executable, and what needs creative review?

| Capability | Inspectable entry point | Requirements |
|---|---|---|
| Shot detection, subtitle association, keyframes, SQLite retrieval and source evidence | [`scripts/movie_index.py`](scripts/movie_index.py), [index reference](.codex/skills/movie-index/references/local-qwen-tool.md) | Local dependencies and FFmpeg; covered by the synthetic demo |
| Qwen visual analysis, resume cache and raw response records | `movie_index.py analyze` | A provider account and API access; charges may apply |
| Qwen, MiniMax, Fish and Volcengine ASR helpers | [Voice skill](.codex/skills/movie-voice-tts/SKILL.md) and its scripts | Provider-specific access and authorized audio |
| Qwen VC voice reuse, locked-script segmented synthesis and Volcengine clone auditions | [Setup guide](docs/getting-started.md) | Audition and lock steps; paid calls are outside the offline demo |
| macOS subtitle OCR and MIDI rendering source | [macOS tools](docs/macos-tools.md) | Optional system-specific capabilities |
| Story interpretation, writing, directing, state locks and review | [Workflow](docs/workflow.md), [data contracts](docs/data-contracts.md) | Codex skills, continuous source viewing with audio, and human judgment |

Shot planning and final rendering follow a project-specific directing plan. The repository does not contain a universal one-command film renderer. Technical validation cannot establish story accuracy, voice authorization or user approval. Provider models, regions, permissions and prices follow the providers' current terms.

## Use the skills in Codex

Follow the [setup guide](docs/getting-started.md) to create a private workspace outside this checkout and configure any optional providers. Then install the skills:

```bash
python scripts/install_skills.py --dry-run
python scripts/install_skills.py
```

The installer stops if a skill with the same name already exists. Back up existing skills before updating. Reopen your Codex session after installation, then ask:

```text
Use $movie-master-director to take over this film project and continue from its current locked state.
```

`movie-master-director` is the main entry point. `movie-index`, `movie-first-person-writer`, `movie-voice-tts`, `movie-direct`, `movie-render-qa` and `movie-second-review` provide stage-specific guidance. `movie-batch-director` is reserved for explicitly requested parallel creative candidates. See the [workflow](docs/workflow.md) for approval gates. Existing projects should follow the [migration guide](docs/migration.md) before changing state files.

## Contribute or report a problem

[Issues](https://github.com/xum66183-art/movie-commentary-workflow/issues/new/choose) in English or Chinese are welcome. Include a tag or commit hash, environment, reproducible steps and sanitized logs. Reproduce media problems with synthetic inputs where possible. See [CONTRIBUTING](CONTRIBUTING.md), [SECURITY](SECURITY.md), [CHANGELOG](CHANGELOG.md) and the [maintainer roadmap](docs/maintainer-roadmap.md).

Run before proposing changes:

```bash
python scripts/check_repository.py
python scripts/validate_skills.py
python scripts/validate_project.py examples/synthetic-demo
python -m pytest
python -m ruff check .
```

Keep real footage, subtitles, voice references, generated narration, credentials, provider responses and production state in a private workspace. The repository distributes source, contracts and synthetic examples. The demo's generated public media is packaged separately as Release assets. Third-party services, models, film and audio remain subject to their own rights and terms; see the [public/private boundary](docs/open-source-boundary.md).
