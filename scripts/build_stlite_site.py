"""
Build script for Community Pulse Stlite static site.

Generates a self-contained index.html that loads the Streamlit app
via Stlite CDN. All Python source files and data.json are inlined
as JavaScript template literal strings so no external file requests
are needed at runtime.

Usage:
    python3 scripts/build_stlite_site.py
    # Output: _site/index.html
"""

import json
import pathlib
import re

# Files to inline into the HTML
FILES_TO_INLINE = {
    "app/app.py": "app/app.py",
    "app/utils/data_loader.py": "app/utils/data_loader.py",
    "app/components/dashboard.py": "app/components/dashboard.py",
    "app/components/timeline.py": "app/components/timeline.py",
    "app/components/signal_table.py": "app/components/signal_table.py",
    "app/components/topic_cloud.py": "app/components/topic_cloud.py",
    "app/requirements.txt": "app/requirements.txt",
    "data/data.json": "data/data.json",
}

STLITE_CDN_URL = "https://cdn.jsdelivr.net/npm/@stlite/browser@1.8.1/umd/stlite.js"


def escape_for_js_template(text: str) -> str:
    """Escape backticks and ${} for JavaScript template literals."""
    text = text.replace("\\", "\\\\")  # Must escape backslashes first
    text = text.replace("`", "\\`")
    text = text.replace("${", "\\${")
    return text


def build_site():
    """Generate the static site in _site/."""
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    output_dir = repo_root / "_site"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read all files
    file_contents = {}
    for file_key, file_path in FILES_TO_INLINE.items():
        full_path = repo_root / file_path
        content = full_path.read_text()
        file_contents[file_key] = escape_for_js_template(content)

    # Build the files JSON object for the stlite.mount() call
    files_js_lines = []
    for file_key in FILES_TO_INLINE:
        var_name = f"file_{file_key.replace('/', '_').replace('.', '_')}"
        files_js_lines.append(f'        "{file_key}": `{file_contents[file_key]}`')

    files_js = ",\n".join(files_js_lines)

    # Build the complete HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Community Pulse — Enterprise Storage Intelligence</title>
  <style>
    body {{ margin: 0; padding: 0; background: #F9FAFB; }}
    #root {{ width: 100vw; height: 100vh; }}
  </style>
  <script src="{STLITE_CDN_URL}"></script>
</head>
<body>
  <div id="root"></div>
  <script>
    stlite.mount({{
      entrypoint: "app/app.py",
      files: {{
{files_js}
      }},
    }}, document.getElementById("root"));
  </script>
</body>
</html>
"""

    output_path = output_dir / "index.html"
    output_path.write_text(html)

    file_count = len(FILES_TO_INLINE)
    size_kb = len(html) / 1024
    print(f"✅ Built _site/index.html ({size_kb:.0f} KB, {file_count} files inlined)")
    print(f"   Stlite CDN: {STLITE_CDN_URL}")


if __name__ == "__main__":
    build_site()