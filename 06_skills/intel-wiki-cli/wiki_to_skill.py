#!/usr/bin/env python3
"""
wiki_to_skill.py — Bootstrap a new Copilot skill from an Intel Wiki page.

Pipeline:
  1. Fetch a wiki page (by --id or --title) via wiki_cli.py  → JSON
  2. Call skill-creator/init_skill.py to scaffold the directory
  3. Overwrite the placeholder SKILL.md with a populated draft:
       - YAML frontmatter (name, description, triggers, source URL)
       - Markdown body converted from the Confluence storage body
  4. Print next-step hints (validate + edit)

Usage:
    wiki_to_skill.py --id 12345        --skill-name my-new-skill   [--path <dir>]
    wiki_to_skill.py --title "Page X"  --skill-name my-new-skill   [--path <dir>]
    wiki_to_skill.py --id 12345        --skill-name foo --triggers "foo, bar, baz"

Defaults:
    --path defaults to the parent of this script (i.e. 06_skills/)

The skill body is the wiki page content converted with a *minimal* HTML→Markdown
transform — review/clean it before committing.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIKI_CLI = HERE / "wiki_cli.py"
DEFAULT_SKILLS_DIR = HERE.parent  # 06_skills/
INIT_SKILL = DEFAULT_SKILLS_DIR / "skill-creator" / "scripts" / "init_skill.py"

WIKI_BASE_URL = "https://wiki.ith.intel.com"


# ───────── helpers ──────────────────────────────────────────────────────────
def fetch_wiki_page(page_id: str | None, title: str | None) -> dict:
    """Call wiki_cli.py get and return the parsed JSON."""
    if not WIKI_CLI.exists():
        sys.exit(f"❌ wiki_cli.py not found at {WIKI_CLI}")
    cmd = [sys.executable, str(WIKI_CLI), "get"]
    if page_id:
        cmd += ["--id", str(page_id)]
    elif title:
        cmd += ["--title", title]
    else:
        sys.exit("❌ Provide --id or --title")
    try:
        out = subprocess.check_output(cmd, text=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"❌ wiki_cli.py failed (exit {e.returncode}). "
                 f"Run `{WIKI_CLI} check-setup` first.")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        sys.exit(f"❌ wiki_cli.py returned non-JSON output:\n{out[:500]}")


def html_to_markdown(raw: str) -> str:
    """Minimal Confluence-HTML → Markdown. Not perfect; meant as a starting point."""
    if not raw:
        return ""
    s = raw
    # Unescape HTML entities first
    s = html.unescape(s)
    # Drop Confluence-specific macros (very common ones)
    s = re.sub(r"<ac:[^>]*?/>", "", s)
    s = re.sub(r"<ac:[^>]*>(.*?)</ac:[^>]+>", r"\1", s, flags=re.DOTALL)
    s = re.sub(r"<ri:[^>]*?/>", "", s)
    # Headings
    for n in range(6, 0, -1):
        s = re.sub(rf"<h{n}[^>]*>(.*?)</h{n}>",
                   lambda m, n=n: "\n" + "#" * n + " " + m.group(1).strip() + "\n",
                   s, flags=re.DOTALL | re.IGNORECASE)
    # Paragraphs / line breaks
    s = re.sub(r"</?p[^>]*>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    # Lists
    s = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"</?[ou]l[^>]*>", "\n", s, flags=re.IGNORECASE)
    # Bold / italic / code
    s = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<(em|i)[^>]*>(.*?)</\1>", r"*\2*", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<pre[^>]*>(.*?)</pre>",
               lambda m: "\n```\n" + m.group(1).strip() + "\n```\n",
               s, flags=re.DOTALL | re.IGNORECASE)
    # Links
    s = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
               r"[\2](\1)", s, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining tags
    s = re.sub(r"<[^>]+>", "", s)
    # Collapse excess whitespace
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def build_skill_md(skill_name: str, page: dict, triggers: str | None) -> str:
    title = page.get("title") or skill_name
    pid = page.get("id", "")
    url = f"{WIKI_BASE_URL}/pages/viewpage.action?pageId={pid}" if pid else ""
    body_raw = (
        page.get("body", {}).get("storage", {}).get("value")
        or page.get("body", {}).get("view", {}).get("value")
        or ""
    )
    body_md = html_to_markdown(body_raw)

    trigger_line = triggers or f"{skill_name}, {title.lower()}, intel wiki page"
    desc = (
        f"Imported from Intel Wiki page '{title}'. "
        f"Use this skill when you need the reference material from that page. "
        f"Triggers: {trigger_line}."
    )

    src_line = f"**Source:** [{title}]({url})" if url else f"**Source title:** {title}"

    return (
        f"---\n"
        f"name: {skill_name}\n"
        f"description: >-\n  {desc}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{src_line}\n\n"
        f"> ⚠️ This skill was auto-generated from a wiki page via `wiki_to_skill.py`. "
        f"Review and edit before relying on it — HTML→Markdown conversion is best-effort.\n\n"
        f"## Content\n\n"
        f"{body_md or '_(empty page body — fetch may have returned no `body.storage.value`.)_'}\n"
    )


def scaffold_with_init_skill(skill_name: str, path: Path) -> Path:
    """Run skill-creator/init_skill.py and return the created skill dir."""
    if not INIT_SKILL.exists():
        sys.exit(f"❌ init_skill.py not found at {INIT_SKILL}")
    path.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(INIT_SKILL), skill_name, "--path", str(path)]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        sys.exit(f"❌ init_skill.py failed (exit {e.returncode})")
    skill_dir = path / skill_name
    if not skill_dir.exists():
        sys.exit(f"❌ Expected skill dir not found: {skill_dir}")
    return skill_dir


# ───────── main ─────────────────────────────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser(
        description="Create a Copilot skill from an Intel Wiki page.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--id", help="Wiki page ID")
    g.add_argument("--title", help="Exact wiki page title")
    p.add_argument("--skill-name", required=True,
                   help="Kebab-case skill name (e.g. my-new-skill)")
    p.add_argument("--path", default=str(DEFAULT_SKILLS_DIR),
                   help=f"Output directory (default: {DEFAULT_SKILLS_DIR})")
    p.add_argument("--triggers", default=None,
                   help='Comma-separated trigger keywords for the YAML frontmatter')
    p.add_argument("--dry-run", action="store_true",
                   help="Fetch + print the would-be SKILL.md, do not write")
    args = p.parse_args()

    if not re.match(r"^[a-z][a-z0-9-]*$", args.skill_name):
        sys.exit("❌ --skill-name must be kebab-case (lowercase, digits, hyphens)")

    print(f"📥 Fetching wiki page...")
    page = fetch_wiki_page(args.id, args.title)

    print(f"📝 Building SKILL.md draft for '{args.skill_name}'...")
    skill_md = build_skill_md(args.skill_name, page, args.triggers)

    if args.dry_run:
        print("\n" + "─" * 70)
        print(skill_md)
        print("─" * 70)
        return

    out_path = Path(args.path)
    print(f"🏗  Scaffolding skill at {out_path}/{args.skill_name}/ ...")
    skill_dir = scaffold_with_init_skill(args.skill_name, out_path)

    skill_md_path = skill_dir / "SKILL.md"
    skill_md_path.write_text(skill_md)
    print(f"✏  Overwrote {skill_md_path} with wiki content")

    print(f"\n✅ Done. Next steps:")
    print(f"   1. Edit:    {skill_md_path}")
    print(f"   2. Validate: {INIT_SKILL.parent / 'quick_validate.py'} {skill_dir}")
    print(f"   3. Commit:  git add {skill_dir.relative_to(Path.cwd())} && git commit")


if __name__ == "__main__":
    main()
