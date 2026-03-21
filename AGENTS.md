# AGENTS.md

## Project Overview

This repository implements an **Acceptance Evidence Agent** for project acceptance materials.

The system is designed to process:
- template files (Word / Excel)
- material files (Word / Excel / images, with future extension to PDF / OCR / screenshots)
- structured template nodes
- structured material units
- candidate evidence matches
- future section drafts, gap reviews, and export results

The product is **not** a generic chatbot.
It is an **agentic task workflow system** for:
1. understanding acceptance templates
2. identifying fill/generate/mixed nodes
3. retrieving relevant evidence from project materials
4. generating draft content or filling fields
5. reviewing gaps and export readiness

---

## Current Product Stage

The project is currently in the **early usable workflow stage**.

Already implemented or expected to be implemented in this stage:
- task creation
- file upload
- JSON-based persistence
- template parsing
- template node visualization
- lightweight editing of template nodes
- template confirmation
- initial fill-node candidate matching

Not yet the focus:
- complex multi-agent systems
- final document export
- OCR-heavy workflows
- automatic screenshots
- vector database
- production multi-user deployment

When making changes, prioritize:
- clear workflow progression
- stable data models
- JSON persistence
- incremental development
- minimal but usable UI/UX

---

## Core Product Philosophy

### 1. This is a workflow application, not just an LLM wrapper
The system should behave like a task-oriented application with explicit states and structured outputs.

### 2. Structure first, model second
Deterministic parsing and structured intermediate data come before LLM reasoning.
Do not give the LLM responsibility for raw file parsing or uncontrolled document interpretation if regular code can do it more reliably.

### 3. Incremental agentization
The system should become more agentic over time:
- first structured parsing
- then retrieval and matching
- then generation
- then orchestration
- then advanced model reasoning

### 4. Keep humans in the loop
Template understanding and candidate evidence selection should remain inspectable and correctable.
Do not hide important decisions behind opaque automation.

---

## High-Level Workflow

The expected workflow is:

1. **Create task**
2. **Upload template and material files**
3. **Parse template**
4. **Convert template into unified template nodes**
5. **Visualize and lightly edit template nodes**
6. **Confirm template**
7. **Parse material files**
8. **Convert materials into material units**
9. **Match fill nodes to candidate evidence**
10. **Generate drafts for generate nodes**
11. **Review missing/risky items**
12. **Export final results**

At the current stage, active focus is primarily on:
- steps 3 to 9

---

## Domain Model

### TemplateNode
A unified node model is the center of template understanding.

Typical fields:

- `node_id`
- `task_id`
- `node_type`: `section | field | note`
- `title`
- `level`
- `parent_id`
- `content_mode`: `generate | fill | mixed`
- `field_type`: `text | image | table | list | unknown`
- `required`
- `requires_screenshot`
- `enabled`
- `status`
- `source_location`
- `parser_notes`

### MaterialUnit
A normalized piece of material content.

Typical fields:

- `unit_id`
- `task_id`
- `file_id`
- `source_type`
- `unit_type`
- `title`
- `content`
- `metadata`

### FillNodeMatch
Candidate evidence matches for a fill node.

Typical fields:

- `task_id`
- `node_id`
- `node_title`
- `query_text`
- `expected_unit_types`
- `candidates`
- `status`

Each candidate should ideally contain:
- `unit_id`
- `file_id`
- `title`
- `unit_type`
- `source_type`
- `score`
- `reason`

---

## Template Understanding Rules

The system must support at least three types of template structures:

### 1. Field-oriented templates
These have clear fillable fields or table-like placeholders.

Examples:
- 功能名称
- 功能描述
- 验收截图
- 输入
- 输出
- 接口说明

These should usually map to:
- `node_type = field`
- `content_mode = fill`

### 2. Directory / section-oriented templates
These are more like document outlines and require content generation.

Examples:
- 项目概述
- 建设内容
- 验收结论
- 风险与问题

These should usually map to:
- `node_type = section`
- `content_mode = generate`

### 3. Mixed templates
Some sections contain both narrative writing and fillable structured sub-parts.

Examples:
- 功能实现说明及效果截图
- 功能验收情况
- 系统建设情况与证明材料

These should usually map to:
- `node_type = section` or `field`
- `content_mode = mixed`

### Parsing strategy
Template parsing should follow:
- deterministic structure extraction first
- rule-based classification second
- optional LLM semantic enhancement later

Do **not** fully outsource template parsing to the LLM.

---

## Material Parsing Rules

Material parsing should normalize uploaded files into `MaterialUnit[]`.

Initial support should prioritize:
- `.docx`
- `.xlsx`
- `.png`
- `.jpg`
- `.jpeg`

Material parsing should extract:
- text paragraphs
- table rows
- image placeholders or image units
- metadata useful for retrieval

At this stage:
- OCR is optional and may be deferred
- embeddings are optional and may be deferred
- simple rule-based retrieval is acceptable

---

## Matching Philosophy

### First-stage matching is lightweight RAG
Do not immediately introduce embeddings or vector search unless clearly necessary.

The initial matching system should:
1. read fill nodes
2. build a retrieval intent from node context
3. retrieve candidate material units
4. score and rank candidates
5. persist candidate results

### Query construction should not rely only on title
For each fill node, retrieval should consider:
- node title
- parent section title
- field type
- screenshot requirement
- parser notes
- future normalized labels if available

### Candidate scoring may use simple rules
Examples:
- title keyword match: +3
- content keyword match: +2
- section-context match: +2
- unit type match: +2
- weak filename/title relevance: +1

This is preferred over premature complexity.

---

## Agent Development Principles

### What "agent" means in this repository
An agent is **not** just a chat interface.

In this repository, an agent means:
- a workflow-oriented orchestrator
- that reads structured task state
- decides which tool/service step to run next
- persists intermediate outputs
- produces inspectable structured results

### The first useful agent in this project
The first meaningful agent capability is:

**Fill Node Matching Agent**
- read confirmed template nodes
- select fill nodes
- construct retrieval intents
- match candidate material units
- persist candidate evidence results

Later capabilities may include:
- section draft generation agent
- gap review agent
- export orchestrator

### Do not over-agentize too early
Avoid introducing:
- unnecessary multi-agent splitting
- chat-first UX for everything
- overly abstract orchestration frameworks before the workflow is stable

Prefer:
- simple services
- explicit routing
- small orchestrator functions
- structured outputs

---

## Engineering Constraints

### Persistence
Use JSON persistence for the current stage.
Do not introduce a database unless it is clearly required by the current feature.

Expected storage layout may include:
- `data/tasks/`
- `data/files/`
- `data/template_nodes/`
- `data/material_units/`
- `data/matches/`

### Architecture
Prefer clear separation between:
- repositories
- services
- routes
- parsers
- front-end views/components

Avoid putting business logic directly in route handlers.

### Incremental development
Make the smallest useful change that advances the workflow.

Prefer:
- stable intermediate data
- explicit APIs
- visible results in UI
- persistent JSON outputs

Over:
- hidden “smart” behavior
- large speculative refactors
- jumping ahead to export/multi-agent/database too early

### Debuggability
All important processing stages should remain inspectable:
- parsed template nodes
- parsed material units
- candidate match results
- status flags
- parser notes
- source locations

This repository values traceability over cleverness.

---

## Frontend Guidelines

The frontend should support structured task workflows, not only chat.

Preferred UI progression:
1. task creation
2. file upload
3. template parsing result
4. template node review/edit
5. template confirmation
6. material parsing result
7. fill-node match result
8. later: draft review / gap review / export

### UI principles
- practical over polished
- structured views over freeform text walls
- clear status indicators
- editable critical fields
- avoid heavy visual complexity early

### Important
For template parsing results, the UI should support:
- visualization
- lightweight editing
- confirmation

Do not build a full WYSIWYG document editor at this stage.

---

## Backend Guidelines

### Preferred layering
- `repositories/` for persistence
- `services/` for workflow logic
- `routes/` for API endpoints
- `parsers/` for file-specific extraction logic

### Route responsibilities
Routes should:
- validate input
- call service methods
- return structured JSON

Routes should not:
- contain parsing logic
- contain ranking logic
- contain matching heuristics
- directly manipulate unrelated persistence concerns

### Service responsibilities
Services should:
- encapsulate workflow logic
- coordinate repositories and parsers
- produce stable intermediate outputs
- be testable without the web layer

---

## Codex / Coding Agent Instructions

When working in this repository, follow these rules:

### 1. Read before changing
Before modifying code:
- inspect repository structure
- identify current implementations of tasks, files, template parsing, persistence, and related pages
- prefer incremental change over replacement

### 2. Respect existing models
Do not introduce a parallel concept if an existing one can be extended.
Avoid ending up with both old and new incompatible models unless a migration path is explicit.

Examples:
- do not keep drifting between `fields` and `template_nodes` without a plan
- do not create competing storage formats for the same entity without a reason

### 3. Prefer stable intermediate JSON
Whenever adding a new workflow stage, define and persist a structured JSON representation first.

### 4. Make visible progress
Each meaningful feature should result in at least one of:
- a new API
- a new JSON output
- a new frontend view
- a new persisted workflow state

### 5. Avoid speculative complexity
Do not add:
- vector DB
- database
- multi-agent architecture
- OCR pipeline
- export engine
- sophisticated orchestration frameworks

unless the current task explicitly requires it.

### 6. Leave extension points
It is good to design function boundaries for future upgrades such as:
- query expansion via LLM
- candidate reranking via LLM
- embeddings
- OCR
- export
- section draft generation

But do not implement those prematurely.

### 7. Preserve traceability
When adding matching or parsing logic, include:
- source identifiers
- reasons/scores
- status fields
- parser notes when useful

### 8. Prefer explicit naming
Use names that reflect the domain:
- `template_nodes`
- `material_units`
- `fill_node_matches`
- `confirm_template`

Avoid vague names like:
- `items`
- `results`
- `data2`
- `processor_final`

---

## Near-Term Priorities

Unless explicitly told otherwise, the preferred development order is:

1. stable JSON persistence
2. template parsing into template nodes
3. template node visualization and lightweight editing
4. template confirmation
5. material parsing into material units
6. fill node candidate matching
7. generate-node drafting
8. gap review
9. export

If a requested change conflicts with this order, prefer the smallest change that still supports the requested feature.

---

## What Not To Do Right Now

Avoid spending time on these unless explicitly requested:

- production authentication
- multi-user roles
- vector databases
- full OCR pipeline
- screenshot automation
- advanced export rendering
- generalized multi-agent systems
- fully autonomous planning loops
- replacing JSON persistence with a DB too early
- over-abstracting the architecture

---

## Quality Bar

A change is considered good in this repository if it is:

- runnable
- inspectable
- persisted
- incremental
- aligned with the workflow
- easy to extend later

A change is not good if it is:

- overly magical
- hard to debug
- tightly coupled
- speculative
- disconnected from the current workflow stage

---

## Preferred Next-Step Heuristic

If unsure what to build next, ask:

1. Does this help the system better understand the template?
2. Does this help the system better understand the materials?
3. Does this help connect template needs to material evidence?
4. Does this make results more inspectable and correctable?
5. Does this advance the main workflow without introducing premature complexity?

If the answer is no, reconsider the change.

---

## Summary

This repository is building a structured, inspectable, agentic workflow for acceptance material generation.

The central progression is:

- understand the template
- normalize the template into nodes
- understand the materials
- normalize the materials into units
- match evidence to fill nodes
- generate drafts for narrative sections
- review gaps
- export results

All engineering decisions should reinforce that progression.