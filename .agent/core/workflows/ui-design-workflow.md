# UI Design Workflow

> Rules and task decomposition for UI/frontend work. No built-in templates; projects maintain their own UI spec under `project/specs/`. AI must follow this workflow to ensure consistency and stability of UI output.

- **Scope**: Applies whenever the task involves **UI, frontend, or visual layout** (new pages, new components, theme changes, layout changes).
- **Authority**: This workflow is mandatory for UI-related tasks; do not skip steps or bypass constraints.

---

## 1. When This Workflow Applies

Apply this workflow when **any** of the following is true:

- The user asks for new or changed **UI pages**, **components**, **layout**, or **theme**.
- The task touches **frontend** code (React/Vue/Svelte/HTML/CSS, admin dashboards, forms, tables, navigation).
- The task involves **design tokens**, **style consistency**, or **component reuse**.

Before writing or refactoring UI code, you **must** read this workflow and the project's UI spec (see §2).

---

## 2. Mandatory Reading Before UI Work

1. **This file** — [core/workflows/ui-design-workflow.md](ui-design-workflow.md).
2. **Project UI spec** — At least one of:
   - `project/specs/*-ui*.md` (e.g. `admin-ui-framework-and-theme.md`, `*-ui-design-process*.md`), or
   - Path declared in `project/status.md` or `project/context.md` as the project's UI design spec.

If the project has **no** UI spec yet, you **must not** invent layout or components ad hoc. Propose creating a single UI spec document first; its recommended structure is in §2.1. When the project is setting up UI for the first time, the optional three-phase flow in §2.2 can be used.

### 2.1 Recommended Structure for the Project UI Spec

A project UI spec document should typically cover the following so that layout, theme, and components have a single source of truth. Technology choices (e.g. CSS framework, component library) are up to the project; the protocol does not prescribe them.

| Section | Purpose |
|--------|---------|
| **Framework and theme** | How the UI is built: CSS/utility approach, dark/light mode strategy, fonts, icons, primary and semantic colors, spacing, radii, shadows. Enough for the project to configure its build and global styles from this section alone. |
| **Layout structure** | Root layout and main regions (e.g. sidebar, header, main content area). Describe structure and responsibilities so that one shared layout (e.g. Sidebar + Header + main area) can be implemented once and reused. |
| **Public components** | Reusable UI building blocks (e.g. cards, buttons, tables, badges, forms). For each: name, purpose, and usage (structure and/or class names or API). List what lives in the single source directory (e.g. `components/ui/`) and is exported for use everywhere. |

Projects may use different stacks and naming; the important thing is that the spec is the one place that defines these three areas so that implementation and verification can align with it.

### 2.2 Optional: First-Time UI Setup (Three Phases)

When a project has **no** UI spec yet and is introducing a frontend or adopting this workflow, a common approach is to follow three phases. This is **optional** and for reference; it does not replace the mandatory five-phase task decomposition in §3 when executing UI work.

| Phase | Goal | Typical actions |
|-------|------|------------------|
| **Phase 1 — Refinement** | One spec document as the single source of truth. | Choose one or two reference pages (e.g. design export or existing UI). Extract framework/theme, layout structure, and public components; write them into a single spec under `project/specs/` (e.g. `*-ui-framework-and-theme.md`). |
| **Phase 2 — Implementation** | Layout and shared components exist and match the spec. | Configure global styles and theme per spec; implement one shared layout (e.g. Sidebar + Header + main content); implement public components in a single directory and export them; business pages only mount the layout and use those components. |
| **Phase 3 — Validation and extension** | Consistency checked; future changes follow the same discipline. | Use the checklist in §5 to verify pages use only the prescribed layout and components. When new public components are needed, update the spec first, then implement and export; do not add one-off components only in a single page. |

---

## 3. Task Decomposition (Required)

Break **every** UI-related task into the following phases. Execute in order; do not implement code before completing the reading and planning steps.

| Phase | Action | Outcome |
|-------|--------|---------|
| **3.1 Confirm scope** | Identify which pages/components/layout/theme are in scope. | Clear list of affected areas. |
| **3.2 Read spec** | Read the project UI spec (see §2). Confirm where layout, theme, and public components are defined. | Knowledge of the single source of truth for UI. |
| **3.3 Plan changes** | If adding **new** public components or layout: plan **spec update first**, then implementation. If only composing existing components: plan which existing layout and ui components to use. | No new layout/component in code without a prior spec update. |
| **3.4 Implement** | Implement only according to the spec: use prescribed layout and public components; do not duplicate layout or component structure in business pages. | Code aligned with project UI spec. |
| **3.5 Verify** | Check: (a) Only prescribed layout and ui components are used in pages; (b) No duplicate layout or component markup in business pages; (c) New public components exist only after spec was updated. | Checklist in §5 passed. |

---

## 4. Mandatory Constraints

These constraints are **non-negotiable**. Violations lead to inconsistent and unstable UI.

| Constraint | Rule |
|------------|------|
| **Single spec source** | The project has **one** authoritative UI spec (or one set of spec files referenced as the UI spec). All layout, theme, and public component definitions stem from it. Do not create a second, competing source of truth. |
| **Single layout** | One shared layout (e.g. MainLayout with Sidebar + Header + content area) is used for all pages that share that layout. **Do not** reimplement the same layout in individual pages. |
| **Single source for public components** | Public UI components (buttons, cards, tables, badges, etc.) are implemented **once** in a dedicated directory (e.g. `components/ui/`), exported from a single entry (e.g. `components/ui/index.ts`), and **reused** everywhere. |
| **No duplicate layout/components in business pages** | Business pages (e.g. Dashboard, Settings, list views) **only** compose the shared layout and the public ui components. They **must not** reimplement the same structure (e.g. same sidebar/header markup or same card/table markup) inline. |
| **Extend spec before new components** | If the task requires a **new** public component or layout element that is not in the spec, **update the project UI spec first** (describe the component, its structure, and usage), then implement the component and use it. Do not add a new public component in code without a prior spec update. |

---

## 5. Verification Checklist (Before Completing UI Work)

Before marking a UI task complete, confirm:

- [ ] The project UI spec was read and used as the only source for layout, theme, and public components.
- [ ] No new public component was added without a prior update to the UI spec.
- [ ] Business pages only use the shared layout and public ui components; they do not contain duplicate layout or component markup.
- [ ] Theme and tokens (colors, spacing, typography) match the spec; no ad hoc values were introduced that contradict the spec.

---

## 6. Summary for AI

- **Before any UI code**: Read this workflow + project UI spec. If there is no spec, propose one using the structure in §2.1 (and optionally the three-phase setup in §2.2). Then decompose the task into §3 phases.
- **During implementation**: Single spec, single layout, single source for components; no duplication in pages; spec first for new components.
- **Before closing the task**: Run through the checklist in §5 and fix any violation.

*This file is a generic engine rule; it does not contain project-specific UI content. Project-specific UI lives in `project/specs/`.*
