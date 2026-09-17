# Research Workflow

> Rules and process for project-level research (industry/market survey, technology comparison, feasibility study). Ensures traceable sources, **recorded citations for key conclusions and data**, **credibility assessment of sources**, clear scope, and consistent output location.

- **Scope**: Applies when the task is **research-oriented**: industry or market research, competitive or technology comparison, tooling survey, feasibility or option analysis, or any structured information gathering to support a decision.
- **Authority**: This workflow is mandatory for research tasks; do not skip steps or bypass constraints.

---

## 1. When This Workflow Applies

Apply this workflow when **any** of the following is true:

- The user asks for **industry research**, **market survey**, **competitive analysis**, or **technology/tooling comparison**.
- The task is to **gather and synthesize** information from external sources (web, docs, papers) to answer a question or support a decision.
- The output is a **research report**, **comparison table**, **feasibility summary**, or **option analysis** that will be stored in the project.

Before starting research or writing a report, you **must** read this workflow and, if present, the project's `project/research/research-index.md`.

---

## 2. Mandatory Reading Before Research

1. **This file** — [core/workflows/research-workflow.md](research-workflow.md).
2. **Project research index** — If it exists: `project/research/research-index.md`. Use it to see existing reports and naming conventions.
3. **Scope or question** — If the research is tied to an active SDD change or a spec, read the relevant `project/changes/<name>/` or `project/specs/` so that the research question and success criteria are clear.

If the project has no `project/research/` directory yet, create it and add `research-index.md` when you add the first report (see §4.3).

---

## 3. Task Decomposition (Required)

Break **every** research task into the following phases. Execute in order; do not publish a report before completing scope and source planning.

| Phase | Action | Outcome |
|-------|--------|---------|
| **3.1 Define scope** | State the research question, boundaries (what is in/out of scope), and success criteria. If the research feeds a decision or change, note that. | Written scope: question, boundaries, success criteria. |
| **3.2 Sources and method** | Decide which sources to use (official docs, articles, papers, etc.), and how to sample (e.g. "latest stable docs", "last 2 years"). Note language/region if relevant. | Short method note: sources, sampling, limitations. |
| **3.3 Collect and synthesize** | Gather information, compare options, and summarize. Do not copy large unreduced blocks; structure findings (e.g. tables, bullet lists, short paragraphs). | Structured findings, comparable format where applicable. |
| **3.4 Record citations and assess credibility** | For **every key conclusion and every datum**: record the exact source (see §4.1). For **every source used**, record a credibility assessment (see §4.2). Inline or in a dedicated "References / Source credibility" section. | Citation record complete; credibility assessment recorded per source. |
| **3.5 Place output and link** | Place the report under `project/research/`, register it in `research-index.md` (see §4.3). If the research feeds a decision, update specs or ADR/change as agreed. | Report in `project/research/`; index updated. |
| **3.6 Validate** | Run the checklist in §5: citation record complete, credibility assessed, index updated, limitations stated. | Checklist in §5 passed. |

---

## 4. Mandatory Constraints

These constraints are **non-negotiable**. Violations lead to untraceable, unverifiable, or inconsistent research.

| Constraint | Rule |
|------------|------|
| **Citation record for key conclusions and data** | **Every key conclusion** and **every datum** (numbers, statistics, comparisons, factual claims) **must** have its source **explicitly recorded** in the report. Use inline citations plus a "References" or "Sources" section, or a table mapping "Conclusion / Datum → Source". Do not leave key findings without a written citation. |
| **Credibility assessment** | For **every source** used to support key conclusions or data, **assess and record credibility** (see §4.2). The report must include this assessment (e.g. in the References section or a "Source credibility" subsection). |
| **Traceable sources** | Every factual claim, comparison, or number must be attributable to a stated source (URL, document name, date, or "user-provided"). Do not state facts without a source. |
| **Consistent citation** | Use one citation style per report (e.g. `[Name](https://example.com/source)` or footnotes). For web content, include URL and access/date if relevance is time-sensitive. |
| **Output location** | New research reports go under `project/research/`. Use names like `research/<topic>-<yyyy-mm>.md` or `research/<name>.md`. Each new report **must** be registered in `project/research/research-index.md` (add a row to the index table). |
| **No fabrication** | Do not invent data, URLs, or sources. If information is missing or uncertain, say so and state the limitation. |
| **Scope respected** | Do not expand the research question or add out-of-scope conclusions. If new questions arise, note them as "future research" or propose a separate task. |

### 4.1 Citation record (required format)

For **each key conclusion and each datum**, the report must record:

- The **exact source** (title, URL or doc identifier, date or version, access date if web).
- Where in the report the conclusion/datum appears (e.g. section or table row), so that a reader can match "claim ↔ source".

Example (References section with inline keys):

```markdown
## References and citation record

| Key | Conclusion / Datum (summary) | Source | Credibility (see §4.2) |
|-----|------------------------------|--------|-------------------------|
| [1] | Market size figure X | [Report Title](https://example.com/report), Date | High – official release |
| [2] | Tool A supports feature Y | [Official Docs](https://example.com/docs), v2.1, 2026-01 | High – primary source |
```

Inline alternative: after each key claim, add a citation key and ensure the References section lists that key with full source and credibility.

### 4.2 Credibility assessment (required dimensions)

For **each source** used for key conclusions or data, **assess and record** the following. You may use a short table (e.g. in "References" or "Source credibility").

| Dimension | What to record |
|-----------|----------------|
| **Source type** | Primary (official docs, first-party data) / Secondary (article, review) / Tertiary (aggregator, wiki). Prefer primary for critical claims. |
| **Authority** | Who produced it (vendor, analyst, press, community). Any known bias or conflict of interest. |
| **Recency** | Publication or update date; whether it is still current for the research question. |
| **Corroboration** | Single source vs. multiple independent sources for the same claim. Note when a key conclusion relies on a single source. |

**Credibility level** (recommended): Assign one label per source and state briefly why (e.g. **High**: official, current, corroborated; **Medium**: secondary but reputable, or primary but outdated; **Low**: tertiary, unverified, or single uncorroborated source). If a key conclusion rests only on Low-credibility sources, state that explicitly in the report and in the limitations.

### 4.3 Research index format

When adding a report, add a row to the table in `project/research/research-index.md`:

```markdown
| Report | File | Topic | Date |
|--------|------|-------|------|
| ... existing rows ...
| Short title | `your-report-name-2026-03.md` | Brief topic | 2026-03 |
```

### 4.4 When research feeds a decision

If the research is input to a spec, ADR, or SDD change:

- Keep the full report in `project/research/` and cite it from the spec/ADR/change.
- In the spec/ADR/change, summarize only the conclusions and link to the research report; do not duplicate long unsourced blocks.
- When summarizing, preserve the distinction between high- and lower-credibility conclusions so that decision-makers can weigh evidence.

---

## 5. Verification Checklist (Before Completing Research)

Before marking a research task complete, confirm:

- [ ] The research question and scope were written down before gathering.
- [ ] **Citation record**: Every key conclusion and every datum has its source **explicitly recorded** (inline + References or mapping table).
- [ ] **Credibility assessment**: For every source used for key conclusions/data, credibility is assessed and recorded (source type, authority, recency, corroboration; and a credibility level with brief rationale).
- [ ] Every factual claim or comparison has a stated source (citation or footnote).
- [ ] The report is under `project/research/` and its filename follows project convention.
- [ ] `project/research/research-index.md` was updated with the new report (file, topic, date).
- [ ] Conclusions and recommendations are clearly tied to cited evidence; where a conclusion relies on low-credibility or single sources, this is stated.
- [ ] Limitations or uncertainties (e.g. missing data, single source, low-credibility basis) are stated where relevant.

---

## 6. Summary for AI

- **Before any research**: Read this workflow and `project/research/research-index.md` if present. Define scope (question, boundaries, success criteria) and method (sources, sampling).
- **During research**: Collect and synthesize in a structured way; for every key conclusion and datum, record the source and assess source credibility; do not fabricate sources or data.
- **After writing**: Ensure the report includes a complete citation record and credibility assessment per source; put the report in `project/research/`, register it in `research-index.md`, and run the checklist in §5.

*This file is a generic engine rule; it does not contain project-specific research content. Project-specific reports live in `project/research/`.*
