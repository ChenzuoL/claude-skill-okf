# Open Knowledge Format (OKF) v0.1

> Source: [GoogleCloudPlatform/knowledge-catalog](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)

OKF is an open, human- and agent-friendly format for representing knowledge. A directory of markdown files with YAML frontmatter.

---

## Bundle Structure

```
bundle/
├── index.md           # Optional. Directory listing (NO frontmatter).
├── log.md             # Optional. Chronological history.
├── <concept>.md       # A concept at the bundle root.
└── <subdirectory>/
    ├── index.md
    └── <concept>.md
```

## Concept Documents

Each concept is a UTF-8 `.md` file with two parts:

1. **YAML frontmatter** delimited by `---`
2. **Markdown body**

### Frontmatter (REQUIRED)

| Field | Required | Description |
|:---|:---|:---|
| `type` | ✅ | Concept kind. Free-form but descriptive. Ex: `BigQuery Table`, `Metric`, `Runbook` |
| `title` | | Display name |
| `description` | | One-line summary |
| `resource` | | Canonical URI for the underlying asset |
| `tags` | | List of strings |
| `timestamp` | | ISO 8601 datetime |

Only `type` is required. Extensions: any custom keys allowed.

### Body

Standard markdown. Recommended headings:

| Heading | Purpose |
|:---|:---|
| `# Schema` | Columns/fields description |
| `# Examples` | Usage examples |
| `# Citations` | External sources |

## Cross-linking

- **Absolute** (recommended): `[customers](/tables/customers.md)` — stable when docs move.
- **Relative**: `[other](./other.md)`.
- **Broken links tolerated**: a dangling link represents knowledge not yet written.

## Index Files (index.md)

**No frontmatter.** Bullet list:

```markdown
# Directory Title

* [Concept Title](file.md) - description from frontmatter
* [Subdirectory](subdir/)

## Subdirectories

* [subdir/](subdir/)
```

## Log Files (log.md)

**No frontmatter.** Reverse chronological markdown list:

```markdown
# Changelog

## 2026-06-24

* Added `orders` table.
* Updated `customers` schema.

## 2026-06-22

* Initial bundle created.
```

## Reserved Filenames

| Filename | Purpose | Has frontmatter? |
|:---|:---|:---|
| `index.md` | Directory listing | ❌ No |
| `log.md` | Changelog | ❌ No |

## Conformance

### MUST (violation → nonconformant)

| Rule | Description |
|:---|:---|
| M1 | Bundle is a directory with ≥1 `.md` concept files |
| M2 | Each concept has YAML frontmatter (`---` … `---`) |
| M3 | Each concept has non-empty `type` field |
| M5 | Concept ID = path without `.md` suffix |
| M6 | Bundle is text only — no SDK/runtime/DB required |

### SHOULD (violation → warning)

| Rule | Description |
|:---|:---|
| S1 | Root `index.md` recommended |
| S2 | `index.md` SHOULD list concepts in its directory |
| S4 | No orphan concepts (every concept reachable via at least one link) |
| S5 | `timestamp` ISO-8601, `tags` as list, `resource` as URI |
| M4† | Broken internal links are allowed per spec |

> † M4: The spec explicitly says "Consumers MUST tolerate broken links". The validator flags them as warnings, not errors.
