# Zhihu Fiction Particle Workbench Design

## Goal

Upgrade the `zhihu_fiction` web interface from a plain light admin page into a polished dark content-production workbench with a restrained particle network effect.

The chosen direction is **B / 内容网络流**: a low-density node-and-link particle background that visually suggests the workspace flow:

```text
素材 -> 选题卡 -> 任务队列 -> 审核草稿 -> 发布包
```

The interface must remain a practical tool. Animation should support the work surface, not compete with forms, lists, and long story text.

## Current State

`zhihu_fiction/static/index.html` is a single Alpine/Tailwind page with:

- Existing tabs: `运行`, `历史`, `技能`, `调度`, `作品`.
- Workspace tabs: `素材`, `选题卡`, `任务`, `审核`, `发布包`.
- Light gray page background, white cards, indigo primary actions.
- Functional workspace API calls and basic manual workflow controls.

Known frontend issues to address while restyling:

- Form labels are visually adjacent but not programmatically associated with controls, which weakens Playwright/accessibility label targeting.
- Workspace list loaders silently swallow failures, leaving stale or empty UI without feedback.
- `生成知乎包` is clickable before the selected draft is `ready_for_package`, producing a recoverable backend `409`.
- Long task/package titles and paths have minor overflow risk on narrow screens.

## Visual Direction

### Theme

Use a dark, operational palette:

- Page background: near-black charcoal, not pure black.
- Panels: translucent dark surfaces with subtle borders.
- Accent: teal/green for the content network and ready/healthy states.
- Secondary accent: cyan for active navigation and focus states.
- Warning/failure states keep semantic amber/red.

Avoid making the screen a one-note teal interface. Use neutral grays for most surfaces, reserve teal/cyan for active/interactive signals, and preserve red/amber/green status semantics.

### Particle Effect

Implement a small native `<canvas>` background:

- Nodes drift slowly.
- Nearby nodes draw faint connecting lines.
- Motion should be subtle and low density.
- The canvas sits behind the application shell.
- It must not block pointer events.
- It must not require new npm/package dependencies.
- It must respect `prefers-reduced-motion: reduce` by rendering a static or disabled state.

The effect should be most visible in the top/background whitespace and least visible behind text-heavy panels.

### Layout

Keep the current single-page tabbed workbench. Do not create a landing page.

Refinements:

- Add an app shell wrapper for particle background and dark theme.
- Upgrade header/nav to a compact dark workbench bar.
- Keep horizontal nav overflow for smaller screens.
- Convert white cards to dark panels with clear section boundaries.
- Preserve dense, scannable forms and lists.
- Keep cards at 8px radius or less unless already established styles need a slightly larger shell radius.

## Components

### App Shell

Responsibilities:

- Host the particle canvas.
- Provide page-level dark background and constrained content width.
- Keep main content above the canvas with stable z-index.

Implementation target:

- `zhihu_fiction/static/index.html`
- No new source files unless the single file becomes harder to maintain than adding a tiny static JS/CSS file.

### Particle Canvas

Responsibilities:

- Initialize once on page load.
- Resize with viewport.
- Animate low-density particles with requestAnimationFrame.
- Stop or render static when reduced motion is preferred.

Interface:

- A small `initParticleNetwork()` function in the existing script block.
- Called from Alpine `init()` after existing startup calls.

### Dark Workbench Styles

Responsibilities:

- Define reusable classes or CSS variables for surfaces, text, borders, status chips, and controls.
- Keep Tailwind utility usage where it is already readable.
- Avoid a full CSS architecture rewrite.

Expected additions:

- CSS custom properties for theme colors.
- Classes such as `.app-shell`, `.particle-canvas`, `.surface`, `.surface-muted`, `.nav-tab`, `.status-chip`.

### Workspace UX Fixes

Include these small behavior improvements in the same frontend pass because they directly affect interface quality:

- Add `id`/`for` associations for visible form labels and controls in workspace forms.
- Disable `生成知乎包` unless `selectedDraft?.status === 'ready_for_package'`.
- Add a small workspace error field such as `workspaceError` and set it when list refreshes fail.
- Use `break-words`, `min-w-0`, or truncation consistently for long task titles, package paths, and card headings.

## Data Flow

Existing API data flow remains unchanged:

- Workspace tabs still call `loadWorkspace()`.
- Individual list refreshes still call `/api/workspace/*`.
- Create/approve/retry/cancel/save/generate/confirm actions keep their current endpoints.

Only frontend presentation and small client-side state handling changes are in scope.

## Error Handling

- Mutation errors keep the existing alert behavior for now.
- List loading failures should set a visible lightweight message in the workspace page instead of silently swallowing all failures.
- The message should be short and non-blocking, with refresh buttons still available.
- Particle initialization failures must fail closed: the app still renders, only the effect is absent.

## Accessibility And Motion

- Controls with visible labels should be label-addressable.
- Focus states must remain visible on dark surfaces.
- Text contrast should remain readable on all panels.
- Particle canvas must have `aria-hidden="true"`.
- `prefers-reduced-motion: reduce` should disable animation loops.

## Testing

Automated checks:

- Existing workspace API and queue tests should still pass.
- Static marker check should verify the particle canvas/function and dark workbench classes exist.
- Browser smoke should verify:
  - Existing tabs render.
  - Workspace tabs render.
  - Manual material creation appears in the material list.
  - Topic card can be created and approved.
  - Task can be created from the approved topic card.
  - No console error from particle initialization.
  - Screenshot shows dark workbench styling and nonblank particle canvas.

Manual visual checks:

- Desktop: 1440x1000.
- Mobile/narrow viewport: 390x844.
- Confirm text does not overlap and nav remains usable.

## Non-Goals

- No new backend endpoints.
- No database migration.
- No landing page.
- No heavy particle library.
- No three-dimensional scene.
- No redesign of the business workflow itself.
- No remote push/upload.

## Success Criteria

- The page reads as a polished content-production workbench, not a marketing hero.
- Particle effect is visible but subtle.
- Forms and lists remain faster to scan than before.
- Existing workspace manual flow still works end to end.
- Tests and browser smoke pass.
- Worktree remains clean except intentional local commits.
