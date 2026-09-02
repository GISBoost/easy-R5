# Prompts for Claude Code

One file per milestone, paste-ready. Same convention as
[easy-OTP's `docs/prompts/`](https://github.com/GISBoost/easy-OTP/tree/main/docs/prompts):
each prompt names the context to load, why the milestone exists, exactly what to build, the
acceptance criteria, what **not** to touch, and what Michał has to verify by hand afterwards
(the agent has no R5, no QGIS session and no data of its own).

| Prompt | Milestone | Depends on |
|---|---|---|
| [`easy-R5_M1-skeleton-and-engine_prompt_for-claude-code.md`](easy-R5_M1-skeleton-and-engine_prompt_for-claude-code.md) | M1 — plugin skeleton, `DownloadR5`, `TestR5Setup`, runner `info` | — |
| [`easy-R5_M2-build-network_prompt_for-claude-code.md`](easy-R5_M2-build-network_prompt_for-claude-code.md) | M2 — `BuildNetwork`, cache, `service_days` | M1 |
| [`easy-R5_M3-travel-time-matrix_prompt_for-claude-code.md`](easy-R5_M3-travel-time-matrix_prompt_for-claude-code.md) | M3 — `RunTravelTimeMatrix` (flagship) | M2 |
| [`easy-R5_M4-accessibility_prompt_for-claude-code.md`](easy-R5_M4-accessibility_prompt_for-claude-code.md) | M4 — `RunAccessibility` + Gdańsk validation | M3 |
| [`easy-R5_M5-isochrones-and-release_prompt_for-claude-code.md`](easy-R5_M5-isochrones-and-release_prompt_for-claude-code.md) | M5 — isochrones, hex grid, release 0.1.0 | M4 |

**One milestone per session.** After each: test in QGIS → review → fix blockers → commit → clear.

All five implement [`../prd/PR_easy-R5_v01.md`](../prd/PR_easy-R5_v01.md). If a prompt and the PRD
disagree, the PRD wins and the prompt is the bug.
