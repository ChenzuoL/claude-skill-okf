---
name: okf
description: "Create, validate, and maintain Open Knowledge Format (OKF) v0.1 bundles. OKF is Google Cloud's open spec for portable, agent-readable knowledge as markdown + YAML frontmatter."
metadata:
  requires:
    bins: ["python3"]
---

# OKF (Open Knowledge Format)

A portable, project-agnostic toolkit for creating and maintaining OKF v0.1 knowledge bundles.

## Quick Start

```bash
# Initialize a knowledge base (creates .okfconfig.json + root index.md)
okf init ./my-knowledge --title "My Knowledge Base"

# Create a concept
okf create "Runbook" --title "DB Incident Response" --path ./my-knowledge/runbooks/

# Scan a directory to see what types would be assigned
okf scan ./my-knowledge/ --verbose

# Migrate existing markdown to OKF (adds type, title, description, timestamp)
okf migrate ./my-knowledge/ --apply

# Validate conformance
okf validate ./my-knowledge/

# Generate index.md for navigation
okf index ./my-knowledge/ --recursive

# Start a local web visualizer (no backend, no install)
okf serve ./my-knowledge/
```

## Commands

| Command | Description |
|:---|:---|
| `okf init [path]` | Initialize a knowledge base with `.okfconfig.json` |
| `okf create <type>` | Create a new concept file |
| `okf scan [path]` | Scan and suggest types for existing files |
| `okf migrate [path]` | Migrate markdown to OKF (add frontmatter fields) |
| `okf serve [path]` | Start local visualizer — browse concepts, graph view, search |
| `okf validate <path>` | Validate bundle conformance |
| `okf index <directory>` | Generate index.md navigation |
| `okf check <file>` | Quick check on a single file |

## Configuration (.okfconfig.json)

```json
{
  "version": "0.1",
  "title": "My Knowledge Base",
  "description": "Project documentation and runbooks",
  "type_rules": [
    {"pattern": "runbooks/", "type": "Runbook"},
    {"pattern": "schemas/", "type": "Database Table"},
    {"pattern": "blog/", "type": "Blog Post"},
    {"pattern": "*.social.md", "type": "Social Post"}
  ],
  "default_type": "Note",
  "index_dirs": ["runbooks", "schemas", "blog"]
}
```

Type detection is three-tier:
1. **Frontmatter heuristics** — `platform` field → "Social Post", `entity_type` → uses that value
2. **Content analysis** — keywords like "schema/SQL/metric/API/runbook" → relevant types
3. **Path rules** — matches against `type_rules` patterns (regex or glob)
4. **Fallback** — `default_type` from config

## Integration with other tools

**media-fetcher** → fetch social media posts → `okf create "Social Post"` or `okf migrate`

**cohub-silo** → indexes OKF files → maps `type` → `entity_type`, `title` → `title`, `tags` → `tags`, `resource` → `source`

## Spec Reference

See `reference/spec.md` for OKF v0.1 conformance criteria.
