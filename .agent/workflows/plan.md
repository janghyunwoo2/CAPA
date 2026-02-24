---
description: Generate a work plan markdown file under .plan/ with strict naming conventions. Use when asked to "write a plan" or when starting any non-trivial change. Supports Jira tickets.
---

# writing-plan Skill

## Trigger conditions
Use this skill when:
- The user asks for a plan / planning / 작업 플랜 / 실행 계획.
- You are about to implement a non-trivial change and there is no plan file yet.
- You are preparing a PR and need a PR-reviewable plan.

## Inputs (ask if missing)
- **title** (required): Short human-readable title for the plan.
- **ticket** (optional): Jira key like `ML-1234`.

## Output rules (MUST)

### Shared rules
- **Date format:** `YYYY-MM-DD` (must appear in filename and inside file body).
- **Slug generation:**
  - **Translate non-English titles to English summary for the slug.** (e.g., "가격 캐시 추가" -> "add-price-cache")
  - Lowercase everything.
  - Replace spaces/underscores with `-`.
  - Remove special characters.
  - Collapse repeated `-` and trim leading/trailing `-`.
  - Keep reasonably short (<= 50 chars).

### Plan location
1. **Ensure directory:** `docs\t1\devops\work`
2. **Check collision:**
   - Target: `.plan/<YYYY-MM-DD>-<slug>.md`
   - If target exists, append suffix: `-2`, `-3`, etc. (e.g., `...-slug-2.md`)
3. **Create File:** `.plan/<YYYY-MM-DD>-<slug>.md`

## Plan content (MUST)
1. **Load template:** Read `assets/PLAN_TEMPLATE.md`.
2. **Replace placeholders:**
   - `{{DATE}}` → Current date (YYYY-MM-DD)
   - `{{TITLE}}` → User provided title (Keep original language here)
   - `{{TICKET_OR_NONE}}` → Ticket ID (e.g., `ML-1234`) or string "None"
3. **Fill sections:** Do not delete headers. Add initial thoughts if context is available.

## Return format (in chat)
After creating the plan file, respond with:
- **Created file path** (clickable if possible)
- **3–5 bullet summary** of the plan goal
- **Open questions** (if any context is missing)
