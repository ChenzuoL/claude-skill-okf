#!/usr/bin/env python3
"""OKF CLI — Open Knowledge Format toolkit.

Create, validate, migrate, and index OKF v0.1 bundles.
Generic, portable, no hardcoded paths or project-specific rules.

Usage:
    okf init [path]              Initialize a knowledge base
    okf create <type> [...]      Create a concept file
    okf validate <path>          Validate bundle conformance
    okf index <directory>        Generate index.md
    okf check <file>             Quick check on one file
    okf migrate <path>           Migrate markdown to OKF
    okf scan <path>              Scan and suggest types
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ─── helpers ─────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '_', slug)
    return slug[:80]


def read_frontmatter(filepath: str) -> tuple[dict | None, str | None]:
    try:
        with open(filepath) as f:
            content = f.read()
    except Exception:
        return None, None
    if not content.startswith('---'):
        return None, content
    parts = content.split('---', 2)
    if len(parts) < 3:
        return None, content
    try:
        import yaml
        fm = yaml.safe_load(parts[1])
    except ImportError:
        fm = _parse_simple_yaml(parts[1])
    except Exception:
        return None, content
    if not isinstance(fm, dict):
        return None, content
    return fm, parts[2] if len(parts) > 2 else ''


def _parse_simple_yaml(text: str) -> dict:
    result = {}
    key = None
    in_list = False
    list_items = []
    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if in_list and stripped.startswith('- '):
            list_items.append(stripped[2:].strip().strip("'\""))
            continue
        elif in_list:
            if list_items:
                result[key] = list_items
            in_list = False
            list_items = []
        m = re.match(r'^(\w[\w_-]*)\s*:\s*(.*)', stripped)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            if val == '[' or val == '[]':
                in_list = True
                list_items = []
            elif val.startswith('[') and val.endswith(']'):
                items = re.findall(r'[\'"]?([^\'"\[\],]+)[\'"]?', val)
                result[key] = [i.strip() for i in items]
            elif val.strip() in ('true', 'false'):
                result[key] = val.strip() == 'true'
            elif val.strip().isdigit():
                result[key] = int(val.strip())
            elif val.startswith("'") or val.startswith('"'):
                result[key] = val.strip("'\"")
            else:
                result[key] = val.strip("'\"")
    if in_list and list_items:
        result[key] = list_items
    return result


def write_frontmatter(filepath: str, fm: dict, body: str | None = None) -> None:
    def _fmt_val(v):
        if isinstance(v, list):
            return None
        if isinstance(v, bool):
            return 'true' if v else 'false'
        if isinstance(v, (int, float)):
            return str(v)
        s = str(v)
        return '"' + s.replace('"', '\\"') + '"'

    lines = ['---']
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f'{k}:')
            for item in v:
                lines.append(f'  - {item}')
        elif isinstance(v, datetime):
            lines.append(f'{k}: "{v.strftime("%Y-%m-%dT%H:%M:%SZ")}"')
        else:
            val = _fmt_val(v)
            lines.append(f'{k}: {val}')
    lines.append('---')
    if body:
        lines.append('')
        lines.append(body.lstrip('\n'))

    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    with open(filepath, 'w') as f:
        f.write('\n'.join(lines) + '\n')


def find_md_files(directory: str) -> list[str]:
    results = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.endswith('.md') and f not in ('index.md', 'log.md'):
                results.append(os.path.join(root, f))
    return sorted(results)


def load_config(root: str) -> dict:
    """Load .okfconfig.json from a directory, or return defaults."""
    config_path = os.path.join(root, '.okfconfig.json')
    if os.path.exists(config_path):
        with open(config_path) as f:
            return json.load(f)
    return {}


def save_config(root: str, config: dict) -> str:
    path = os.path.join(root, '.okfconfig.json')
    with open(path, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    return path


def derive_type_from_fm(fm: dict) -> str | None:
    """Heuristic: guess type from existing frontmatter fields."""
    if fm.get('type'):
        return fm['type']  # Already has OKF type
    if fm.get('platform'):
        return 'Social Post'
    if fm.get('entity_type'):
        return fm['entity_type']
    if fm.get('category'):
        return fm['category']
    return None


def derive_type_from_content(body: str) -> str | None:
    """Heuristic: guess type from markdown content."""
    if not body:
        return None
    # Strong signals only — avoid matching incidental keywords in READMEs
    if re.search(r'(?:\|\s*Column\s*\||CREATE TABLE|BigQuery)', body, re.IGNORECASE):
        return 'Database Table'
    if re.search(r'^#\s*(?:Incident|Runbook|Troubleshooting)', body, re.MULTILINE | re.IGNORECASE):
        return 'Runbook'
    if re.search(r'https?://(?:x\.com|twitter\.com)/\w+/status/', body):
        return 'Social Post'
    if re.search(r'https?://(?:xhslink|xiaohongshu)\.com/', body):
        return 'Social Post'
    if re.search(r'https?://(?:v\.douyin|douyin)\.com/', body):
        return 'Social Post'
    if re.search(r'https?://(?:bilibili\.com|b23\.tv)/', body):
        return 'Social Post'
    return None


def derive_type_from_path(relpath: str, rules: list) -> str | None:
    """Match path against user-defined rules."""
    for rule in rules:
        pattern = rule.get('pattern', '')
        if not pattern:
            continue
        # Support glob-like and regex patterns
        if '*' in pattern:
            import fnmatch
            if fnmatch.fnmatch(relpath, pattern) or fnmatch.fnmatch(os.path.basename(relpath), pattern):
                return rule['type']
        elif re.search(pattern, relpath):
            return rule['type']
    return None


def auto_type(filepath: str, root: str, config: dict) -> str:
    """Three-tier type detection: frontmatter → content → path → default."""
    relpath = os.path.relpath(filepath, root) if root else os.path.basename(filepath)
    rules = config.get('type_rules', [])
    default = config.get('default_type', 'Note')

    fm, body = read_frontmatter(filepath)
    if body is None:
        with open(filepath) as f:
            body = f.read()

    t = derive_type_from_fm(fm or {})
    if t:
        return t
    t = derive_type_from_content(body or '')
    if t:
        return t
    t = derive_type_from_path(relpath, rules)
    if t:
        return t
    return default


def derive_title(body: str) -> str:
    if body:
        m = re.search(r'^#\s+(.+)$', body, re.MULTILINE)
        if m:
            return m.group(1).strip()[:200]
    return ''


def derive_description(body: str) -> str:
    if not body:
        return ''
    lines = body.split('\n')
    parts = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith('#') or s.startswith('![') or s.startswith('|'):
            if parts:
                break
            continue
        parts.append(s)
    desc = ' '.join(parts)
    return desc[:200].rstrip()


# ─── commands ────────────────────────────────────────────────────────────────

def cmd_init(args):
    """Initialize an OKF knowledge base."""
    path = os.path.abspath(args.path or '.')
    os.makedirs(path, exist_ok=True)

    config = {
        'version': '0.1',
        'title': args.title or os.path.basename(path) or 'My Knowledge Base',
        'description': args.description or '',
        'type_rules': args.type_rules or [],
        'default_type': args.default_type or 'Note',
        'created': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }

    config_path = save_config(path, config)

    # Create root index.md
    root_index = os.path.join(path, 'index.md')
    if not os.path.exists(root_index):
        write_frontmatter(root_index, {
            'type': 'Knowledge Bundle',
            'title': config['title'],
            'description': config['description'],
            'timestamp': config['created'],
        }, f"# {config['title']}\n")

    print(json.dumps({
        'ok': True,
        'action': 'initialized',
        'path': path,
        'config': config_path,
        'index': root_index,
    }, ensure_ascii=False, indent=2))


def cmd_create(args):
    """Create a new OKF concept file."""
    type_val = args.type
    title = args.title or type_val
    slug = args.slug or slugify(title)
    path_dir = os.path.abspath(args.path or '.')
    config = load_config(path_dir)

    filename = f'{slug}.md'
    filepath = os.path.join(path_dir, filename)

    if os.path.exists(filepath) and not args.force:
        print(json.dumps({'ok': False, 'error': f'File exists: {filename}'}, ensure_ascii=False))
        sys.exit(1)

    fm = {'type': type_val}
    if title:
        fm['title'] = title
    if args.description:
        fm['description'] = args.description
    if args.resource:
        fm['resource'] = args.resource
    if args.tags:
        fm['tags'] = [t.strip() for t in args.tags.split(',')]
    fm['timestamp'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    body = args.body
    if not body and args.template:
        body = _get_template(type_val, config)
    if not body:
        body = f'# {title}\n'
    write_frontmatter(filepath, fm, body)

    print(json.dumps({
        'ok': True, 'action': 'created', 'path': filepath,
        'type': type_val, 'title': fm.get('title', ''),
    }, ensure_ascii=False, indent=2))


def cmd_validate(args):
    """Validate a bundle against OKF v0.1."""
    path = os.path.abspath(args.path)
    strict = args.strict
    root = path if os.path.isdir(path) else os.path.dirname(path)

    if os.path.isfile(path) and path.endswith('.md'):
        md_files = [path]
    elif os.path.isdir(path):
        md_files = []
        for d_root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if f.endswith('.md'):
                    md_files.append(os.path.join(d_root, f))
    else:
        print(json.dumps({'ok': False, 'error': f'Not a valid path: {path}'}, ensure_ascii=False))
        sys.exit(1)

    errors, warnings = [], []
    all_files_set = set(os.path.relpath(f, root) for f in md_files)
    root_has_index = any(os.path.basename(f) == 'index.md' and os.path.dirname(f) == root for f in md_files)

    if not md_files:
        errors.append({'rule': 'M1', 'msg': 'Bundle contains no .md files'})

    for f in md_files:
        relpath = os.path.relpath(f, root)
        basename = os.path.basename(f)

        # Reserved files (index.md, log.md) — no frontmatter per spec §3.1
        if basename in ('index.md', 'log.md'):
            continue

        fm, body = read_frontmatter(f)

        if fm is None:
            errors.append({'rule': 'M2', 'file': relpath, 'msg': 'No YAML frontmatter block'})
            continue
        if not fm.get('type') or not isinstance(fm.get('type'), str) or not fm['type'].strip():
            errors.append({'rule': 'M3', 'file': relpath, 'msg': "Missing or empty 'type' field"})

        ts = fm.get('timestamp')
        if ts and not isinstance(ts, str) and not isinstance(ts, datetime):
            warnings.append({'rule': 'S5', 'file': relpath, 'msg': 'timestamp should be ISO-8601'})
        if fm.get('tags') and not isinstance(fm.get('tags'), list):
            warnings.append({'rule': 'S5', 'file': relpath, 'msg': 'tags should be a list'})
        if fm.get('resource') and not isinstance(fm.get('resource'), str):
            warnings.append({'rule': 'S5', 'file': relpath, 'msg': 'resource should be a URI'})

        if body:
            links = re.findall(r'\[([^\]]*)\]\(([^)]+)\)', body)
            for link_text, link_target in links:
                if link_target.endswith('.md') and not link_target.startswith('http'):
                    link_dir = os.path.dirname(relpath)
                    # Support absolute bundle-relative links (starting with /)
                    if link_target.startswith('/'):
                        resolved = os.path.normpath(link_target.lstrip('/'))
                    else:
                        resolved = os.path.normpath(os.path.join(link_dir, link_target))
                    if resolved not in all_files_set:
                        warnings.append({
                            'rule': 'M4', 'file': relpath,
                            'msg': f'Dangling link: [{link_text}]({link_target}) → {resolved} (spec allows this)'
                        })

    if not root_has_index and os.path.isdir(path):
        warnings.append({'rule': 'S1', 'msg': 'No root index.md (recommended)'})

    conformant = len(errors) == 0
    if strict:
        conformant = conformant and len(warnings) == 0

    result = {
        'ok': True, 'conformant': conformant, 'bundle_root': root,
        'files_checked': len(md_files), 'errors': errors, 'warnings': warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not conformant:
        sys.exit(1)


def cmd_index(args):
    """Generate index.md per OKF spec: no frontmatter, bullet list."""
    directory = os.path.abspath(args.directory)

    if not os.path.isdir(directory):
        print(json.dumps({'ok': False, 'error': f'Not a directory: {directory}'}, ensure_ascii=False))
        sys.exit(1)

    title = args.title or os.path.basename(directory)

    # Collect non-index, non-log .md files
    md_files = [f for f in os.listdir(directory)
                if f.endswith('.md') and f not in ('index.md', 'log.md') and not f.startswith('.')]

    # Also collect subdirectories
    subdirs = [d for d in os.listdir(directory)
               if os.path.isdir(os.path.join(directory, d)) and not d.startswith('.')]

    if not md_files and not subdirs:
        if not args.dry_run:
            print(json.dumps({'ok': True, 'action': 'skipped', 'path': directory, 'msg': 'Nothing to index'}, ensure_ascii=False, indent=2))
        return

    entries = []
    for f in sorted(md_files):
        fp = os.path.join(directory, f)
        fm, _ = read_frontmatter(fp)
        fm_title = fm.get('title', '') if fm else ''
        fm_desc = fm.get('description', '') if fm else ''
        entries.append({
            'file': f,
            'title': fm_title or f.replace('.md', '').replace('_', ' '),
            'desc': fm_desc,
        })

    # Generate bullet-list index per OKF spec (§6)
    lines = [f'# {title}', '']
    if entries:
        for e in entries:
            desc_suffix = f' - {e["desc"]}' if e['desc'] else ''
            lines.append(f'* [{e["title"]}]({e["file"]}){desc_suffix}')
        lines.append('')
    if subdirs:
        lines.append('## Subdirectories')
        lines.append('')
        for sd in sorted(subdirs):
            lines.append(f'* [{sd}/]({sd}/)')
        lines.append('')

    index_path = os.path.join(directory, 'index.md')

    if args.dry_run:
        print('\n'.join(lines))
        return

    with open(index_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    print(json.dumps({
        'ok': True, 'action': 'indexed', 'path': index_path,
        'entries': len(entries), 'subdirs': len(subdirs),
    }, ensure_ascii=False, indent=2))

    if args.recursive:
        for sd in subdirs:
            subpath = os.path.join(directory, sd)
            args_copy = argparse.Namespace(**vars(args))
            args_copy.directory = subpath
            args_copy.title = None
            args_copy.recursive = True
            cmd_index(args_copy)


def cmd_check(args):
    """Quick check of a single file."""
    filepath = os.path.abspath(args.file)
    if not os.path.exists(filepath):
        print(json.dumps({'ok': False, 'error': 'File not found'}, ensure_ascii=False))
        sys.exit(1)

    fm, body = read_frontmatter(filepath)

    def _safe(v):
        return v.isoformat() if isinstance(v, datetime) else (str(v) if v else '')

    def _safe_tags(t):
        if isinstance(t, list):
            return t
        if t:
            return [t]
        return []

    result = {
        'ok': True, 'path': filepath,
        'has_frontmatter': fm is not None,
        'has_type': bool(fm and fm.get('type')),
        'type': _safe(fm.get('type')) if fm else '',
        'title': _safe(fm.get('title')) if fm else '',
        'description': _safe(fm.get('description')) if fm else '',
        'tags': _safe_tags(fm.get('tags')) if fm else [],
        'resource': _safe(fm.get('resource')) if fm else '',
        'timestamp': _safe(fm.get('timestamp')) if fm else '',
        'body_length': len(body) if body else 0,
        'issues': [],
    }

    if not result['has_frontmatter']:
        result['issues'].append('No YAML frontmatter')
    elif not result['has_type']:
        result['issues'].append("Missing 'type' field (required by OKF)")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['issues']:
        sys.exit(1)


def cmd_migrate(args):
    """Migrate existing markdown files to OKF v0.1."""
    root = os.path.abspath(args.path or '.')
    config = load_config(root)
    apply = args.apply
    dirs = args.dirs.split(',') if args.dirs else ['.']

    all_results = []
    for d in dirs:
        full = os.path.join(root, d.strip())
        if not os.path.isdir(full):
            continue
        for f in find_md_files(full):
            r = _migrate_one(f, root, config, apply=apply)
            all_results.append(r)

    changed = [r for r in all_results if r['changed']]

    # Generate indexes for configured dirs
    index_dirs = config.get('index_dirs', [])
    index_results = []
    if apply and index_dirs:
        for d in index_dirs:
            full = os.path.join(root, d)
            if os.path.isdir(full):
                cmd_index(argparse.Namespace(
                    directory=full, title=d.replace('_', ' ').title(),
                    description=None, index_type='Knowledge Bundle',
                    recursive=False, dry_run=False,
                ))
                index_results.append(d)

    summary = {
        'total': len(all_results), 'changed': len(changed),
        'unchanged': len(all_results) - len(changed),
        'indexes_generated': index_results,
    }

    if args.json:
        summary['changes'] = [{
            'path': r['path'], 'type': r['type'], 'changes': r['changes'],
        } for r in changed]
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f'Total: {summary["total"]} | Changed: {summary["changed"]} | Mode: {"APPLY" if apply else "DRY-RUN"}')
        for r in changed[:10]:
            print(f"  {r['path']}: {', '.join(r['changes'])}")
        if len(changed) > 10:
            print(f'  ... and {len(changed) - 10} more')
        if index_results:
            print(f'Indexes: {", ".join(index_results)}')


def _migrate_one(filepath: str, root: str, config: dict, apply: bool = False) -> dict:
    """Migrate a single file to OKF. Returns change summary."""
    with open(filepath) as f:
        raw = f.read()

    relpath = os.path.relpath(filepath, root)
    fm, _ = read_frontmatter(filepath)
    body = _strip_all_frontmatter(raw)
    new_fm = fm.copy() if fm else {}
    changes = []

    # type
    okf_type = auto_type(filepath, root, config)
    if "type" not in new_fm or not new_fm.get("type"):
        new_fm["type"] = okf_type
        changes.append(f"+type: {okf_type}")

    # url → resource
    if "url" in new_fm and "resource" not in new_fm:
        new_fm["resource"] = new_fm.pop("url")
        changes.append("url → resource")

    # title
    title = derive_title(body)
    if title and not new_fm.get("title"):
        new_fm["title"] = title
        changes.append("+title")

    # description
    desc = derive_description(body)
    if desc and not new_fm.get("description"):
        new_fm["description"] = desc
        changes.append("+description")

    # timestamp
    if not new_fm.get("timestamp"):
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        new_fm["timestamp"] = ts
        changes.append("+timestamp")

    # tags as list
    tags = new_fm.get("tags")
    if tags and not isinstance(tags, list) and isinstance(tags, str):
        new_fm["tags"] = [t.strip() for t in tags.split(',')]
        changes.append("tags: str → list")

    if apply and changes:
        write_frontmatter(filepath, new_fm, body)

    return {
        'path': relpath, 'type': new_fm.get('type', ''),
        'title': (new_fm.get('title', '') or '')[:60],
        'changes': changes, 'changed': len(changes) > 0,
    }


def _strip_all_frontmatter(raw_text: str) -> str:
    text = raw_text
    while True:
        stripped = text.lstrip()
        if not stripped.startswith('---'):
            break
        idx = stripped.find('---', 3)
        text = stripped[idx + 3:] if idx >= 0 else stripped[3:]

    lines = text.split('\n')
    last_sep = -1
    for i, line in enumerate(lines):
        s = line.strip()
        if s == '---':
            last_sep = i
        elif s.startswith('#') or (s and not re.match(r'^[\w_-]+\s*:', s)):
            break
    if last_sep >= 0:
        text = '\n'.join(lines[last_sep + 1:])
    return text.lstrip()


def cmd_scan(args):
    """Scan a directory and suggest types."""
    root = os.path.abspath(args.path or '.')
    config = load_config(root)

    results = []
    for f in find_md_files(root):
        relpath = os.path.relpath(f, root)
        fm, body = read_frontmatter(f)
        if body is None:
            with open(f) as fh:
                body = fh.read()

        detected = {
            'from_fm': derive_type_from_fm(fm or {}),
            'from_content': derive_type_from_content(body or ''),
            'from_path': derive_type_from_path(relpath, config.get('type_rules', [])),
        }

        existing_type = fm.get('type', '') if fm else ''
        suggested = auto_type(f, root, config)

        results.append({
            'path': relpath,
            'existing_type': existing_type,
            'suggested': suggested,
            'detected': detected,
            'has_frontmatter': fm is not None,
            'has_okf_type': bool(existing_type),
        })

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        okf_ready = sum(1 for r in results if r['has_okf_type'])
        print(f'Files: {len(results)} | OKF-ready: {okf_ready} | Need type: {len(results) - okf_ready}')
        print()
        for r in results:
            status = '✅' if r['has_okf_type'] else '⬜'
            print(f'  {status} [{r["suggested"]}] {r["path"]}')
            if r['existing_type']:
                print(f'     existing: {r["existing_type"]}')
            if args.verbose:
                print(f'     detected: {r["detected"]}')


# ─── templates ───────────────────────────────────────────────────────────────

TYPE_TEMPLATES = {
    'Runbook': '''# Symptoms\n\n- \n\n# Steps\n\n1. \n2. \n\n# Recovery\n\n- \n\n# Notes\n\n''',
    'Database Table': '''# Schema\n\n| Column | Type | Description |\n|:---|:---|:---|\n| | | |\n\n# Joins\n\n- \n\n# Notes\n\n''',
    'Metric': '''# Definition\n\n\n# Calculation\n\n```\n\n```\n\n# Owners\n\n- \n\n# Dashboard\n\n''',
    'API': '''# Endpoint\n\n```\nMETHOD /path\n```\n\n# Auth\n\n- \n\n# Request\n\n```json\n\n```\n\n# Response\n\n```json\n\n```\n\n# Example\n\n```bash\n\n```\n''',
    'Report': '''# Summary\n\n\n# Key Findings\n\n- \n\n# Data\n\n\n# Next Steps\n\n- \n''',
    'Social Post': '''# Content\n\n\n# Source\n\n- \n\n# Tags\n\n''',
    'Note': '''# \n\n''',
}


def _get_template(type_val: str, config: dict) -> str | None:
    """Get body template for a concept type."""
    # Check user config first
    templates = config.get('templates', {})
    if type_val in templates:
        tmpl = templates[type_val]
        if isinstance(tmpl, str):
            return tmpl
        if isinstance(tmpl, dict) and 'body' in tmpl:
            return tmpl['body']
    # Check built-in templates (fuzzy match)
    for key, tmpl in TYPE_TEMPLATES.items():
        if key.lower() in type_val.lower() or type_val.lower() in key.lower():
            return tmpl
    return None


# ─── link ─────────────────────────────────────────────────────────────────────

def cmd_link(args):
    """Create bidirectional links between two OKF concepts."""
    source = os.path.abspath(args.source)
    target = os.path.abspath(args.target)
    root = os.path.commonpath([source, target])

    if not os.path.exists(source):
        print(json.dumps({'ok': False, 'error': f'Source not found: {args.source}'}, ensure_ascii=False))
        sys.exit(1)
    if not os.path.exists(target):
        print(json.dumps({'ok': False, 'error': f'Target not found: {args.target}'}, ensure_ascii=False))
        sys.exit(1)

    src_rel = os.path.relpath(target, os.path.dirname(source))
    tgt_rel = os.path.relpath(source, os.path.dirname(target))

    links_added = []

    # Add link to source
    fm_src, body_src = read_frontmatter(source)
    if body_src is None:
        with open(source) as f:
            body_src = f.read()
    link_src = f'\n- Related: [{args.target_title or os.path.basename(target).replace(".md","")}]({src_rel})'
    if link_src not in (body_src or ''):
        body_src = (body_src or '').rstrip() + link_src + '\n'
        write_frontmatter(source, fm_src or {'type': 'Note'}, body_src)
        links_added.append(f'{args.source} → {args.target}')

    # Add link to target
    fm_tgt, body_tgt = read_frontmatter(target)
    if body_tgt is None:
        with open(target) as f:
            body_tgt = f.read()
    link_tgt = f'\n- Related: [{args.source_title or os.path.basename(source).replace(".md","")}]({tgt_rel})'
    if link_tgt not in (body_tgt or ''):
        body_tgt = (body_tgt or '').rstrip() + link_tgt + '\n'
        write_frontmatter(target, fm_tgt or {'type': 'Note'}, body_tgt)
        links_added.append(f'{args.target} → {args.source}')

    print(json.dumps({
        'ok': True, 'action': 'linked',
        'links': links_added,
        'source': args.source, 'target': args.target,
    }, ensure_ascii=False, indent=2))


# ─── export ───────────────────────────────────────────────────────────────────

def cmd_export(args):
    """Export a knowledge bundle as tar.gz."""
    import tarfile
    import tempfile

    root = os.path.abspath(args.path or '.')
    config = load_config(root)
    title = args.name or config.get('title', 'okf-bundle')
    slug = re.sub(r'[^\w\-]', '_', title)[:60]
    ts = datetime.now(timezone.utc).strftime('%Y%m%d')
    filename = args.output or f'{slug}-{ts}.tar.gz'

    # Determine what to include
    index_dirs = config.get('index_dirs', [])
    if index_dirs:
        includes = index_dirs + ['index.md', '.okfconfig.json']
    else:
        includes = ['.']

    count = 0
    with tarfile.open(filename, 'w:gz') as tar:
        for inc in includes:
            full = os.path.join(root, inc)
            if not os.path.exists(full):
                continue
            if os.path.isfile(full):
                tar.add(full, arcname=os.path.join(slug, inc))
                count += 1
            else:
                for dirpath, dirnames, filenames in os.walk(full):
                    dirnames[:] = [d for d in dirnames if not d.startswith('.')]
                    for f in filenames:
                        fpath = os.path.join(dirpath, f)
                        arcname = os.path.join(slug, os.path.relpath(fpath, root))
                        tar.add(fpath, arcname=arcname)
                        count += 1

    size_mb = os.path.getsize(filename) / (1024 * 1024)
    print(json.dumps({
        'ok': True, 'action': 'exported',
        'file': filename, 'size_mb': round(size_mb, 2),
        'files': count, 'title': title,
    }, ensure_ascii=False, indent=2))


# ─── main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='OKF — Open Knowledge Format CLI')
    sub = parser.add_subparsers(dest='command')

    p_init = sub.add_parser('init', help='Initialize an OKF knowledge base')
    p_init.add_argument('path', nargs='?', default='.', help='Target directory')
    p_init.add_argument('--title', help='Knowledge base title')
    p_init.add_argument('--description', help='Knowledge base description')
    p_init.add_argument('--type-rules', help='JSON array of type rules, e.g. \'[{"pattern":"blog/","type":"Blog"}]\'')
    p_init.add_argument('--default-type', default='Note', help='Default concept type')

    p_create = sub.add_parser('create', help='Create a new OKF concept file')
    p_create.add_argument('type', help='Concept type')
    p_create.add_argument('--title', help='Human-readable title')
    p_create.add_argument('--description', help='One-line description')
    p_create.add_argument('--resource', help='Canonical URL or identifier')
    p_create.add_argument('--tags', help='Comma-separated tags')
    p_create.add_argument('--path', default='.', help='Target directory')
    p_create.add_argument('--slug', help='Filename slug')
    p_create.add_argument('--body', help='Initial markdown body')
    p_create.add_argument('--force', action='store_true', help='Overwrite existing file')
    p_create.add_argument('--template', action='store_true', help='Use built-in body template for this type')

    p_val = sub.add_parser('validate', help='Validate bundle against OKF v0.1')
    p_val.add_argument('path', help='Directory or file to validate')
    p_val.add_argument('--strict', action='store_true', help='Treat warnings as errors')

    p_idx = sub.add_parser('index', help='Generate index.md for a directory')
    p_idx.add_argument('directory', help='Directory to index')
    p_idx.add_argument('--title', help='Title for this index page')
    p_idx.add_argument('--description', help='Description')
    p_idx.add_argument('--index-type', help='Type for the index page')
    p_idx.add_argument('--recursive', action='store_true', help='Also index subdirectories')
    p_idx.add_argument('--dry-run', action='store_true', help='Print without writing')

    p_chk = sub.add_parser('check', help='Quick check of a single file')
    p_chk.add_argument('file', help='Path to .md file')

    p_mig = sub.add_parser('migrate', help='Migrate markdown files to OKF v0.1')
    p_mig.add_argument('path', nargs='?', default='.', help='Root directory')
    p_mig.add_argument('--apply', action='store_true', help='Actually write changes')
    p_mig.add_argument('--dirs', default='.', help='Comma-separated directories to process')
    p_mig.add_argument('--json', action='store_true', help='Output as JSON')

    p_scan = sub.add_parser('scan', help='Scan directory and suggest types')
    p_scan.add_argument('path', nargs='?', default='.', help='Directory to scan')
    p_scan.add_argument('--json', action='store_true', help='Output as JSON')
    p_scan.add_argument('--verbose', '-v', action='store_true', help='Show detection details')

    p_serve = sub.add_parser('serve', help='Start local visualizer for an OKF bundle')
    p_serve.add_argument('path', nargs='?', default='.', help='Bundle directory')
    p_serve.add_argument('--port', '-p', type=int, default=3000, help='Port to listen on')
    p_serve.add_argument('--title', help='Bundle title (default: directory name)')

    p_link = sub.add_parser('link', help='Create bidirectional links between concepts')
    p_link.add_argument('source', help='Source concept file')
    p_link.add_argument('target', help='Target concept file')
    p_link.add_argument('--source-title', help='Link text from source to target')
    p_link.add_argument('--target-title', help='Link text from target to source')

    p_export = sub.add_parser('export', help='Export bundle as tar.gz')
    p_export.add_argument('path', nargs='?', default='.', help='Bundle root')
    p_export.add_argument('--output', '-o', help='Output filename')
    p_export.add_argument('--name', help='Bundle name (default: from config)')

    args = parser.parse_args()

    if args.command == 'init':
        cmd_init(args)
    elif args.command == 'create':
        cmd_create(args)
    elif args.command == 'validate':
        cmd_validate(args)
    elif args.command == 'index':
        cmd_index(args)
    elif args.command == 'check':
        cmd_check(args)
    elif args.command == 'migrate':
        cmd_migrate(args)
    elif args.command == 'scan':
        cmd_scan(args)
    elif args.command == 'serve':
        from serve import cmd_serve
        cmd_serve(args)
    elif args.command == 'link':
        cmd_link(args)
    elif args.command == 'export':
        cmd_export(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
