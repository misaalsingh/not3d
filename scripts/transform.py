#!/usr/bin/env python3
"""
Transform markdown notes into interactive HTML study pages using Claude API.

Usage:
    # Transform all notes
    python scripts/transform.py

    # Transform only changed files (used by GitHub Action)
    python scripts/transform.py --changed notes/pods.md notes/services.md
"""

import argparse
import os
import sys
import glob
import json
import hashlib
from pathlib import Path

import anthropic

NOTES_DIR = Path("notes")
DOCS_DIR = Path("docs")
CACHE_FILE = DOCS_DIR / ".transform-cache.json"

SYSTEM_PROMPT = """\
You are an expert at transforming technical study notes into interactive, \
visually engaging HTML study pages. You apply evidence-based learning techniques:

1. **Active Recall**: Hide answers behind clickable reveals so the learner \
must try to remember before seeing the answer.
2. **Spaced Repetition Cues**: Generate flashcard sets at the end of each topic.
3. **Chunking**: Break dense content into digestible visual sections with \
clear hierarchy.
4. **Dual Coding**: Pair text explanations with Mermaid.js diagrams wherever \
architecture or flow is involved.
5. **Elaborative Interrogation**: Insert "Why?" and "How?" questions \
throughout the material.
6. **Interleaving**: When multiple concepts exist, create comparison tables \
and mixed-topic quiz sections.

OUTPUT RULES:
- Return a SINGLE, COMPLETE HTML file. No markdown, no code fences, no \
explanation outside the HTML.
- The first line must be `<!DOCTYPE html>`.
- Use Tailwind CSS via CDN for styling.
- Use Mermaid.js via CDN for diagrams (include the init script).
- All interactivity must be vanilla JS (no frameworks).
- Use a dark theme (slate/gray background, light text) with accent colors \
for different section types.
- Make it mobile-responsive.

REQUIRED SECTIONS (use your judgment on which apply to the content):
1. **Hero/Title**: Topic name, a one-line summary, and a "confidence meter" \
the learner can self-assess with (1-5 clickable stars that persist via localStorage).
2. **Key Concepts**: Styled cards with term on front, explanation revealed on click.
3. **Visual Architecture**: Mermaid diagram(s) showing how concepts relate.
4. **Deep Dive**: The full notes content, restructured with clear headings, \
code blocks (syntax highlighted), and callout boxes for tips/warnings.
5. **Practice Questions**: Multiple choice and short answer with hidden answers.
6. **Flashcards**: A deck the learner can flip through (previous/next buttons), \
term on front, definition on back, with a "Got it" / "Review again" tracker \
using localStorage.
7. **Cheat Sheet**: A compact, printable summary table at the bottom.
8. **Command Reference** (if applicable): Interactive table of commands with \
copy buttons.

Keep the HTML clean and well-structured. Optimize for learning, not decoration.\
"""


def get_file_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def save_cache(cache: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def transform_note(client: anthropic.Anthropic, note_path: Path, cache: dict) -> bool:
    """Transform a single markdown note into an interactive HTML page.

    Returns True if the file was transformed, False if skipped (cached).
    """
    content = note_path.read_text()
    content_hash = get_file_hash(content)

    # Skip if content hasn't changed
    cache_key = str(note_path)
    if cache.get(cache_key) == content_hash:
        print(f"  Skipped (unchanged): {note_path}")
        return False

    print(f"  Transforming: {note_path}")

    # Build the output path: notes/foo/bar.md -> docs/foo/bar.html
    relative = note_path.relative_to(NOTES_DIR)
    output_path = DOCS_DIR / relative.with_suffix(".html")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    topic_name = note_path.stem.replace("-", " ").replace("_", " ").title()

    user_message = (
        f"Transform these study notes on '{topic_name}' into an interactive "
        f"HTML study page.\n\n"
        f"---\n\n{content}"
    )

    # Use streaming for large outputs to avoid timeouts
    collected_html = []
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for text in stream.text_stream:
            collected_html.append(text)

    html_output = "".join(collected_html)

    # Strip code fences if Claude wrapped the output
    if html_output.startswith("```"):
        lines = html_output.split("\n")
        # Remove first line (```html) and last line (```)
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        html_output = "\n".join(lines)

    output_path.write_text(html_output)
    print(f"  Output: {output_path}")

    # Update cache
    cache[cache_key] = content_hash
    return True


def generate_index(docs_dir: Path):
    """Generate an index.html that links to all study pages."""
    html_files = sorted(docs_dir.glob("**/*.html"))
    html_files = [f for f in html_files if f.name != "index.html"]

    if not html_files:
        return

    entries = []
    for f in html_files:
        relative = f.relative_to(docs_dir)
        name = f.stem.replace("-", " ").replace("_", " ").title()
        # Group by subdirectory if any
        parts = relative.parts
        category = parts[0].replace("-", " ").replace("_", " ").title() if len(parts) > 1 else "General"
        entries.append({"name": name, "path": str(relative), "category": category})

    # Group entries by category
    categories = {}
    for entry in entries:
        cat = entry["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(entry)

    cards_html = ""
    for category, items in sorted(categories.items()):
        cards_html += f'<h2 class="text-xl font-semibold text-slate-300 mt-8 mb-4">{category}</h2>\n'
        cards_html += '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">\n'
        for item in items:
            cards_html += f"""\
            <a href="{item['path']}" class="block p-6 bg-slate-800 rounded-lg border border-slate-700
               hover:border-blue-500 hover:bg-slate-750 transition-all duration-200">
                <h3 class="text-lg font-medium text-white">{item['name']}</h3>
                <p class="text-sm text-slate-400 mt-1">Click to study</p>
            </a>
"""
        cards_html += "</div>\n"

    index_html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Study Notes</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen">
    <div class="max-w-5xl mx-auto px-6 py-12">
        <header class="mb-10">
            <h1 class="text-4xl font-bold text-white mb-2">Study Notes</h1>
            <p class="text-slate-400">Interactive study pages generated from your notes.
               Click any topic to start reviewing.</p>
        </header>
        <main>
            {cards_html}
        </main>
        <footer class="mt-16 pt-8 border-t border-slate-800 text-sm text-slate-500">
            Generated with Notez &mdash; AI-powered study pages
        </footer>
    </div>
</body>
</html>
"""
    (docs_dir / "index.html").write_text(index_html)
    print(f"  Generated index: {docs_dir / 'index.html'}")


def main():
    parser = argparse.ArgumentParser(description="Transform markdown notes into interactive HTML study pages")
    parser.add_argument(
        "--changed",
        nargs="*",
        help="Only transform these specific files (used by CI for diff-based builds)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Transform all notes, ignoring cache",
    )
    args = parser.parse_args()

    api_key = os.environ.get("NOT3D_API_KEY")

    # Also try loading from .env file if env var not set
    if not api_key:
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text().strip().splitlines():
                if "=" in line:
                    key, _, value = line.partition("=")
                    if key.strip() == "NOT3D_API_KEY":
                        api_key = value.strip()
                else:
                    # Raw key with no KEY= prefix
                    api_key = line.strip()

    if not api_key:
        print("Error: NOT3D_API_KEY not found in environment or .env file.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    cache = {} if args.all else load_cache()

    # Determine which files to process
    if args.changed is not None:
        # CI mode: only process specified changed files
        note_files = [Path(f) for f in args.changed if f.endswith(".md") and Path(f).exists()]
    else:
        # Local mode: process all .md files in notes/
        note_files = sorted(NOTES_DIR.glob("**/*.md"))

    if not note_files:
        print("No markdown files found to transform.")
        sys.exit(0)

    print(f"Found {len(note_files)} note(s) to process.\n")

    transformed_count = 0
    for note_path in note_files:
        try:
            if transform_note(client, note_path, cache):
                transformed_count += 1
        except anthropic.APIError as e:
            print(f"  API Error on {note_path}: {e}")
            continue

    save_cache(cache)

    if transformed_count > 0 or not (DOCS_DIR / "index.html").exists():
        generate_index(DOCS_DIR)

    print(f"\nDone. Transformed {transformed_count} file(s).")


if __name__ == "__main__":
    main()
