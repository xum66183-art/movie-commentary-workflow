# Maintainer roadmap

This is an early-stage extension of the upstream Movie Commentary Workflow. These are
planned maintenance priorities, not claims of existing users, integrations or funding.

## Current release

- Keep the offline synthetic demo reproducible without API credentials.
- Deliver complete source archives with the skills, scripts, schemas and tests.
- Preserve upstream attribution and distinguish local verification from cloud-provider tests.
- Collect bug reports with environment, reproduction steps and redacted logs through the issue templates.

## Next maintenance work

1. Triage real installation reports on macOS and Linux; turn confirmed failures into regression tests.
2. Document actual external use cases when users provide them and consent to public attribution.
3. Review dependency updates against the offline index and evidence tests before releasing.
4. Improve provider adapters only when authorized test inputs and credentials are available.

## Contribution scope

Installation fixes, indexing correctness, subtitle edge cases, source-coordinate preservation,
documentation and synthetic tests are suitable contributions. Film footage, personal voice
references, private project state and credentials belong outside the repository.

No adoption target, release cadence or maintainer funding is promised by this roadmap.
