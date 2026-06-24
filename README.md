# OKF — Open Knowledge Format Toolkit

> Turn a folder of markdown files into an AI-readable knowledge base. Linter + navigator + visualizer, zero dependencies.

## What is Open Knowledge Format

OKF is Google Cloud's open specification (v0.1, June 2026) for portable, agent-friendly knowledge. The idea is simple:

> Knowledge shouldn't be locked inside a platform. It should be **files anyone can read**.

An OKF bundle is:

```
Just a directory of .md files
Just YAML frontmatter declaring type / title / tags
Just markdown links connecting concepts into a graph
```

No SDK. No database. No login. Editable in any editor, versionable in git, indexable by any search tool.

### Why OKF

Organizational knowledge lives everywhere — table schemas in BigQuery, metric definitions in wikis, runbooks in shared drives, tribal knowledge in people's heads. Every AI agent has to reassemble this from scratch. OKF provides a **universal format**:

- Anyone can produce (human, script, AI agent)
- Anyone can consume (Claude, Codex, your search tool)
- No vendor lock-in

### Concept format

Each concept is a `.md` file with YAML frontmatter. Only `type` is required:

```yaml
---
type: BigQuery Table
title: Orders
description: One row per completed order.
resource: https://console.cloud.google.com/...
tags: [sales, revenue]
timestamp: 2026-05-28T14:30:00Z
---

# Free-form markdown body
Normal markdown: tables, code blocks, links, anything.
```

## What this tool does

11 commands covering the full lifecycle of a knowledge base:

| Command | What it does |
|:---|:---|
| `okf init` | Bootstrap a knowledge base (creates `.okfconfig.json`) |
| `okf create "Runbook" --title "DB outage"` | Create a concept with standard frontmatter |
| `okf scan` | Analyze a directory and suggest types for every file |
| `okf migrate --apply` | Batch-add OKF fields to existing markdown |
| `okf serve` | Start a local web visualizer — zero backend |
| `okf validate` | Check conformance against OKF v0.1 spec |
| `okf index --recursive` | Generate `index.md` navigation files |
| `okf check file.md` | Quick diagnostic on a single file |
| `okf link a.md b.md` | Create bidirectional links between concepts |
| `okf export` | Package the bundle as tar.gz |
| `okf label file.md --type "Note"` | Add/update frontmatter on one file |

## Quick Start

```bash
# 1. Initialize
okf init ./my-knowledge --title "My Knowledge Base"

# 2. Create a concept (--template for body skeleton)
okf create "Runbook" --title "DB incident response" \
  --tags "incident,sre" --template --path ./my-knowledge/runbooks/

# 3. Scan existing files
okf scan ./my-knowledge/ --verbose

# 4. Batch migrate (add frontmatter to existing files)
okf migrate ./my-knowledge/ --apply

# 5. Validate conformance
okf validate ./my-knowledge/

# 6. Browse
okf serve ./my-knowledge/
# → Open http://localhost:3000
```

## Built-in Visualizer (`okf serve`)

One command, Python stdlib only. Opens in your browser:

- **Sidebar tree** — browse concepts by directory hierarchy
- **Search** — filter by title, type, or path in real time
- **Concept detail** — rendered markdown, metadata grid, tags
- **Linked concepts** — auto-detected from `.md` links in body
- **Concept graph** — force-directed graph of all inter-concept links
- **Type browser** — home page grouped by type

## Type Auto-detection

Three-tier strategy used by `migrate` and `scan`:

1. **Frontmatter heuristics** — `platform` field → "Social Post", existing `type` → use it
2. **Content analysis** — social media links → "Social Post", SQL keywords → "Database Table"
3. **Path rules** — configurable in `.okfconfig.json`
4. **Fallback** — `default_type` (default: "Note")

## Configuration

`.okfconfig.json` at the bundle root:

```json
{
  "version": "0.1",
  "title": "My Knowledge Base",
  "type_rules": [
    {"pattern": "runbooks/", "type": "Runbook"},
    {"pattern": "schemas/", "type": "Database Table"}
  ],
  "default_type": "Note",
  "index_dirs": ["runbooks", "schemas"]
}
```

## Templates

`--template` generates a body skeleton based on concept type:

| Type | Sections |
|:---|:---|
| Runbook | Symptoms → Steps → Recovery → Notes |
| Database Table | Schema table → Joins → Notes |
| Metric | Definition → Calculation → Owners → Dashboard |
| API | Endpoint → Auth → Request → Response → Example |
| Report | Summary → Key Findings → Data → Next Steps |

## Validator

`okf validate` checks against the official OKF v0.1 conformance criteria:

- **MUST** (errors): M1-M3, M5-M6 — bundle structure, frontmatter presence, required `type`
- **SHOULD** (warnings): S1-S5 — root index.md, format checks, orphan detection
- **M4** — dangling links are warnings per spec ("Consumers MUST tolerate broken links")

## Integration

OKF frontmatter maps directly to the [cohub-silo](https://github.com/kjx-talesofai/cohub-silo-client) SED format — index your knowledge base with full-text search and a REST API:

```
OKF type        → silo entity_type
OKF title       → silo title
OKF description → silo description
OKF tags        → silo tags
OKF resource    → silo source
```

## Spec

See [reference/spec.md](reference/spec.md) for the complete OKF v0.1 conformance criteria, aligned with [GoogleCloudPlatform/knowledge-catalog](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md).

---

> **Core belief: no sign-up, no payment, no login.**  
> Knowledge should live in your filesystem, not someone else's backend.
