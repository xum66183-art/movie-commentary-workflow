# Changelog

版本记录区分源码版本与 GitHub Release。正式附件、提交号和发布说明以 [Releases](https://github.com/xum66183-art/movie-commentary-workflow/releases) 为准。Changes below distinguish source versions from published releases.

## [0.3.0] - 2026-10-21

### Added

- Offline synthetic demo: generate original inputs, run real indexing, search, evidence export and verification, then prepare shareable media and checksums outside the source checkout.
- Demo guide, English README, explicit upstream provenance and contribution boundaries.
- Structured bug and feature issue forms, with reproducibility and sanitized evidence prompts.
- Source archive manifest covering all eight hidden skill directories, tools, schemas, templates, documentation and tests; build dependencies and CI source-distribution checks.
- Integration coverage for unpacked-source validation, index help, environment diagnostics and skill installation.

### Fixed

- Installed index tools now identify their actual source checkout boundary instead of treating the user's home directory as the public repository, so private projects outside the installed skills directory are accepted.

### Clarified

- The demo covers local indexing and source evidence; cloud vision, TTS, narrative writing and creative approval remain separate stages.
- The skill framework, production schemas and core templates are inherited from the attributed upstream project.
- Source-tree installation requires keeping the complete checkout or extracted source archive.

## [0.2.0] - 2026-10-21 (source version)

The existing source version was introduced in commit [`36c93f5`](https://github.com/xum66183-art/movie-commentary-workflow/commit/36c93f5). This entry records the source history; it does not assert that a GitHub Release or downloadable binary was published for that version.

- Integrated the upstream eight-skill workflow with executable local shot indexing, subtitle retrieval, evidence export and optional Qwen visual analysis.
- Added Qwen VC narration helpers, Volcengine clone audition helpers and optional macOS OCR / MIDI source tools.
- Added portable setup, skill installation, environment diagnostics and synthetic integration tests; enhanced existing voice and project validation tools.
- Preserved the upstream Apache-2.0 license and added NOTICE attribution to baseline `3d50c17`.

Follow-up fixes in the source history corrected PySceneDetect timecode compatibility (`c54bf02`) and removed an obsolete upstream lock file while clarifying supported installation (`f020e0c`).

[0.3.0]: https://github.com/xum66183-art/movie-commentary-workflow/compare/f020e0c...v0.3.0
[0.2.0]: https://github.com/xum66183-art/movie-commentary-workflow/commit/36c93f5
