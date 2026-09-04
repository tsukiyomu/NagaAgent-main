# Testing Documentation Reorganization Plan

> `SUSPENDED`（2026-08-18）：初始目录重组已完成，剩余去重工作后置；当前计划结构见 [`../sop-compiler-runtime-practical-roadmap.md`](../sop-compiler-runtime-practical-roadmap.md) 和本目录 [`README.md`](README.md)。

## Purpose

Separate stable module explanations, current progress/plans, generated report guidance, portfolio material, and historical task records under `docs/testing`.

## Current Execution Checklist

- [REVIEW_NEEDED] Reorganize `docs/testing`, add a navigation index, separate Allure/quality-gate result guidance, and repair internal references.
  - Completed in: `docs-reorg-001`
  - Evidence: moved the existing Markdown set into `architecture/`, `plans/`, `showcase/`, and `archive/`; added root/report indexes; local Markdown link validation reports `ALL_LOCAL_MARKDOWN_LINKS_EXIST`.
  - Review issue: two root-level PNG files are byte-identical duplicates of `img/image-20260428211733612.png`; automated deletion was blocked by the environment policy, so they remain for manual review.
- [TODO] Audit and deduplicate overlapping content after the new structure is reviewed.
- [TODO] Reconcile document status claims with the latest repository and CI evidence.

## Progress Ledger

| Run ID | Date | Selected Task | Status | Evidence | Next Recommended Task |
|---|---|---|---|---|---|
| docs-reorg-001 | 2026-07-27 | Reorganize testing documentation and separate generated report guidance | REVIEW_NEEDED | New category directories and indexes exist; stale-path scan is clean; all local Markdown links resolve | Review the new navigation, then remove or retain the two duplicate root PNG files before content deduplication |
