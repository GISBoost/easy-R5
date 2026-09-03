# Prompts for Claude Code

One file per milestone, paste-ready. Same convention as
[easy-OTP's `docs/prompts/`](https://github.com/GISBoost/easy-OTP/tree/main/docs/prompts):
each prompt names the context to load, why the milestone exists, exactly what to build, the
acceptance criteria, what **not** to touch, and what Michał has to verify by hand afterwards
(the agent has no R5, no QGIS session and no data of its own).

| Prompt | Milestone | Depends on | Status |
|---|---|---|---|
| [`easy-R5_M1-skeleton-and-engine_prompt_for-claude-code.md`](easy-R5_M1-skeleton-and-engine_prompt_for-claude-code.md) | M1 — plugin skeleton, `DownloadR5`, `TestR5Setup`, runner `info` | — | ✅ implemented; ⏳ Michał's clean-profile check |
| [`easy-R5_M2-build-network_prompt_for-claude-code.md`](easy-R5_M2-build-network_prompt_for-claude-code.md) | M2 — `BuildNetwork`, cache, `service_days` | M1 | ✅ implemented; ⏳ Michał's large-PBF check |
| [`easy-R5_M3-travel-time-matrix_prompt_for-claude-code.md`](easy-R5_M3-travel-time-matrix_prompt_for-claude-code.md) | M3 — `RunTravelTimeMatrix` (flagship) | M2 | ✅ implemented + **verified end-to-end vs R5 7.6** |
| [`easy-R5_M4-accessibility_prompt_for-claude-code.md`](easy-R5_M4-accessibility_prompt_for-claude-code.md) | M4 — `RunAccessibility` + Gdańsk validation | M3 | ✅ implemented; **reproduces r5r's Gdańsk output exactly** |
| [`easy-R5_M5-isochrones-and-release_prompt_for-claude-code.md`](easy-R5_M5-isochrones-and-release_prompt_for-claude-code.md) | M5 — isochrones, hex grid, release 0.1.0 | M4 | ✅ implemented + verified in QGIS 3.40; ⏳ clean-profile pipeline |

**Status of all five: see [`../handoffs/2026-09-03_M3-M5-implementation.md`](../handoffs/2026-09-03_M3-M5-implementation.md).**
`metadata.txt` is at `0.1.0`, `experimental=True` until Michał signs off the clean-profile run.

**One milestone per session.** After each: test in QGIS → review → fix blockers → commit → clear.

All five implement [`../prd/PR_easy-R5_v01.md`](../prd/PR_easy-R5_v01.md). If a prompt and the PRD
disagree, the PRD wins and the prompt is the bug.
