# Journey Target Hierarchy Design

## Goal

Make every Journey visibly identify the job direction, company, and business line being prepared, without exposing internal task-reuse concepts as navigation choices.

## Information architecture

The Journey hierarchy is:

1. Job direction, such as `AI 产品经理`, `后端开发`, or `Agent 开发`.
2. Company, such as `京东` or `腾讯`.
3. Business line or business unit, such as `京东零售`, `京东物流`, or `混元`.

`综合路径` and `通用主线` are not user-facing navigation levels. Common job-direction tasks remain reusable in storage and are automatically included when a concrete company/business target is selected.

## Backend contract

- A target signal from a later conversation may attach to an existing confirmed direction by an exact normalized role or label match.
- Explicit historical target signals that were previously left unbound are repaired when the product store opens.
- Dashboard `journey_branches` entries expose `company`, `business`, `role`, and `location` from their Compass target branch.
- Existing endpoint names remain backward compatible.

## Frontend behavior

- Same-named Journey rows are presented as one job-direction selector and use stable IDs rather than titles as React keys.
- Target branches are grouped first by company and then shown as business-line choices.
- Selecting a target shows the reusable common tasks plus that target's specific tasks.
- The current context is always visible as `岗位方向 / 公司 / 业务线`.
- If no target branch exists, the direction's current common route remains usable and the page explains that a company target can be added from Compass.
- Draft targets keep the existing explicit activation confirmation.

## Compatibility and safety

- No existing Journey, task, direction, or branch row is deleted.
- Historical duplicate Journey titles are collapsed only in the presentation layer.
- Legacy dashboard payloads without enriched target fields still render using branch titles as a fallback.

