"""
Build script for Community Pulse Stlite static site.

Generates a self-contained index.html that loads the Streamlit app
from a locally-bundled Stlite runtime. All Python source files and
data.json are inlined as JavaScript template literal strings.

The Stlite browser package is downloaded from npm during the build
and served from the same GitHub Pages origin — no external CDN needed.

Usage:
    python3 scripts/build_stlite_site.py
    # Output: _site/index.html + _site/stlite/
"""

import json
import pathlib
import re
import shutil
import subprocess
import sys

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

STLITE_PACKAGE = "@stlite/browser"
STLITE_VERSION = "1.8.1"
STLITE_LOCAL_DIR = "_site/stlite"


def escape_for_js_template(text: str) -> str:
    """Escape backticks and ${} for JavaScript template literals."""
    text = text.replace("\\", "\\\\")  # Must escape backslashes first
    text = text.replace("`", "\\`")
    text = text.replace("${", "\\${")
    return text


def download_stlite():
    """Download @stlite/browser npm package and copy build/ to _site/stlite/."""
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    output_dir = repo_root / "_site"
    stlite_dest = output_dir / "stlite"

    # Skip if already present
    if stlite_dest.exists() and (stlite_dest / "stlite.js").exists():
        print(f"✅ Stlite runtime already present at {stlite_dest}")
        return

    print(f"📦 Downloading {STLITE_PACKAGE}@{STLITE_VERSION} from npm...")
    # Download the package tarball to a temp directory
    tmp_dir = output_dir / "_tmp_npm"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    npm_cmd = shutil.which("npm")
    if not npm_cmd:
        print("❌ npm not found. Install Node.js/npm to enable local Stlite bundling.")
        print("   Falling back to CDN mode is not supported in this build.")
        sys.exit(1)

    try:
        subprocess.run(
            [
                npm_cmd, "pack",
                f"{STLITE_PACKAGE}@{STLITE_VERSION}",
                "--pack-destination", str(tmp_dir),
            ],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError:
        print("❌ npm not found. Install Node.js/npm to enable local Stlite bundling.")
        print("   Falling back to CDN mode is not supported in this build.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ npm pack failed: {e.stderr.decode()}")
        sys.exit(1)

    # Extract the tarball
    tarball = list(tmp_dir.glob("*.tgz"))[0]
    extract_dir = tmp_dir / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["tar", "-xzf", str(tarball), "-C", str(extract_dir)], check=True)

    # Copy the build/ directory to _site/stlite/
    package_build = extract_dir / "package" / "build"
    if not package_build.exists():
        print(f"❌ Expected build/ directory not found in {STLITE_PACKAGE} tarball")
        sys.exit(1)

    if stlite_dest.exists():
        shutil.rmtree(stlite_dest)
    shutil.copytree(package_build, stlite_dest)
    print(f"✅ Stlite runtime copied to {stlite_dest}")

    # Cleanup temp files
    shutil.rmtree(tmp_dir)


def build_site():
    """Generate the static site in _site/."""
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    output_dir = repo_root / "_site"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Download Stlite runtime locally
    download_stlite()

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
  <script type="module" src="/stlite/stlite.js"></script>
</head>
<body>
  <div id="root"></div>
  <script type="module">
    async function initStlite() {{
      try {{
        const stlite = await import("/stlite/stlite.js");
        stlite.mount({{
          entrypoint: "app/app.py",
          files: {{
{files_js}
          }},
        }}, document.getElementById("root"));
      }} catch (e) {{
        document.getElementById("root").innerHTML =
          "<pre style='padding:20px;color:red;white-space:pre-wrap;'>" +
          "Stlite mount failed: " + e.message + "</pre>";
        console.error(e);
      }}
    }}
    initStlite();
  </script>
</body>
</html>
"""

    output_path = output_dir / "index.html"
    output_path.write_text(html)

    file_count = len(FILES_TO_INLINE)
    size_kb = len(html) / 1024
    stlite_size = sum(f.stat().st_size for f in (output_dir / "stlite").rglob("*") if f.is_file()) / 1024
    total_kb = size_kb + stlite_size
    print(f"✅ Built _site/index.html ({size_kb:.0f} KB, {file_count} files inlined)")
    print(f"   Stlite runtime: {stlite_size:.0f} KB (local, no CDN)")
    print(f"   Total site size: {total_kb:.0f} KB")


if __name__ == "__main__":
    build_site()