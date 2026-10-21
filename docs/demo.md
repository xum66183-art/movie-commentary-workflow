# Reproduce the offline demonstration

The demo exercises real local indexing and evidence export using original synthetic material. It generates six seconds of red, blue, and green geometric footage, a 440 Hz tone, and four Chinese subtitle cues. One cue crosses the cut at 2.000 seconds. It then calls the existing `movie_index.py` CLI for `prepare`, `search`, `evidence`, and `verify`; no API credentials or network requests are needed.

## Run it

Use Python 3.11 or newer and install the index dependencies from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[index]'
```

The index extra selects `opencv-python-headless`; an existing `opencv-python` distribution also works. The runtime report records the installed distribution name and version rather than relabeling it.

Install FFmpeg separately and ensure both `ffmpeg` and `ffprobe` are on `PATH`. The build needs the `libx264` video encoder, AAC audio encoder, and `mov_text` subtitle encoder. On macOS, `brew install ffmpeg` provides these tools. See [macOS setup](macos-tools.md) for local prerequisites.

Choose an absolute path to a **new directory outside the checkout**:

```bash
python scripts/run_demo.py --output /absolute/path/new-synthetic-demo
```

The command rejects existing targets, output inside the checkout, and symlinked output paths or parent directories. It creates no media in the checkout and does not overwrite an earlier run. Choose another new directory to reproduce a run. If a dependency or check fails, the command exits with code 2; an incomplete external directory is retained for inspection.

The `release/` subdirectory contains the public demonstration:

| File | What it shows |
| --- | --- |
| `demo.mp4` | A 22-second walkthrough: source → index → subtitle search → actual evidence export → production-state boundary |
| `preview.png` | Readable overview with real extracted frames, shot coordinates, and the cross-cut subtitle result |
| `source.mp4` | Original six-second geometric fixture, synthetic source tone, and selectable Chinese subtitle track |
| `source.srt` | UTF-8 Chinese sidecar used by the actual indexer |
| `evidence.mp4` | Real export of source interval 1.500–3.500 seconds, preserving the synthetic source audio |
| `summary.json` | Actual coordinates, search result IDs, runtime versions, hashes, and self-check results |
| `transcript.json` | Executed subprocess arguments, return codes, and outputs with local path prefixes replaced |
| `SHA256SUMS` | SHA-256 checksums for the other public files |
| `README.md` | Artifact contents, scope, and synthetic-media reuse terms |

Publish **only `release/`** as Release attachments. The sibling `project/` contains the actual index, databases, keyframes, source fingerprints, and state; these include local absolute paths and are intentionally excluded from public output. `build/` holds intermediate explanation cards. The generated synthetic media, captions, and artwork use the project [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0). See the source checkout LICENSE and NOTICE for repository attribution.

## What the checks prove

The command must pass all of the following before reporting success:

- The source lasts 6.000 seconds, with cuts at 2.000 and 4.000 seconds, three technical shots, and six visual units.
- Original source frame intervals are exactly `[0, 50)`, `[50, 100)`, and `[100, 150)` at 25 fps.
- Subtitle #2 (`我穿过边界`, 1.500–2.500 seconds) links to both adjacent shots; actual subtitle search retrieves both.
- The selected visual unit plus 500 ms padding exports exactly 1.500–3.500 seconds. The encoded evidence duration is within 50 ms, contains audio, decodes without error, and has three evidence frames.
- Structural `verify` passes; the database contains zero API attempts and zero visual model observations.
- Production remains `PROJECT_CREATED`, the index lock remains `null`, and `index_verified` remains `false`.
- The 22-second public walkthrough decodes and contains its audio stream.

Inspect `summary.json` and `transcript.json` to see what happened on your machine. Verify downloaded artifacts with `sha256sum -c SHA256SUMS` on Linux, or `shasum -a 256 -c SHA256SUMS` on macOS, from inside `release/`. Different FFmpeg builds can produce different media hashes; the deterministic fixture, timeline coordinates, and required checks are the reproducible contract.

## Scope

This is a small integration example, not a benchmark for real-film scene detection or retrieval quality. It does not run visual inference, write a script, clone a voice, generate narration, or complete a film commentary. The audio is a generated test tone. The walkthrough's explanation cards are English for portable rendering; the real indexed subtitles and sidecar are Chinese.

A structural pass never automatically adopts an index. Real work still requires the director's complete-film understanding, representative retrieval checks, continuous source review with audio, and explicit production-state locks before downstream creation. See [workflow](workflow.md) and [data contracts](data-contracts.md).
