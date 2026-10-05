"""Render actual notebook outputs as HTML and capture them with headless Edge.

Requires executed notebooks. No generated or manually fabricated results.
On Windows: python scripts/capture_evidence.py
"""
import html
from pathlib import Path
import re
import subprocess

import nbformat

ROOT = Path(__file__).resolve().parent.parent


def main():
    destination = ROOT / "submission" / "screenshots"
    destination.mkdir(parents=True, exist_ok=True)
    browser = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    if not browser.exists():
        raise FileNotFoundError("Microsoft Edge is required to capture evidence on Windows")
    for path in sorted((ROOT / "notebooks").glob("[0-9]*.ipynb")):
        notebook = nbformat.read(path, as_version=4)
        blocks = []
        for cell in notebook.cells:
            for output in cell.get("outputs", []):
                if output.output_type == "error":
                    raise RuntimeError(f"{path.name} has an error output")
                if output.output_type == "stream" and output.get("name") == "stdout":
                    blocks.append(output.text)
                elif output.output_type in ("execute_result", "display_data"):
                    blocks.append(output.get("data", {}).get("text/plain", ""))
        content = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(blocks))
        # Split long output into legible pages; retain every stdout block.
        lines = content.splitlines()
        for page, start in enumerate(range(0, len(lines), 65), 1):
            part = lines[start:start + 65]
            stem = f"{path.stem}_{page:02d}"
            document = destination / f"{stem}.html"
            document.write_text(
                '<!doctype html><meta charset="utf-8"><style>'
                'body{margin:36px;background:#f4f7fb;color:#172438;font:18px Segoe UI;}'
                'h1{font-size:27px}pre{background:white;border:1px solid #ccd6e2;'
                'padding:24px;font:17px Consolas;white-space:pre-wrap;line-height:1.5;}'
                '</style>'
                f'<h1>{html.escape(path.stem)} — executed output ({page})</h1>'
                f'<pre>{html.escape(chr(10).join(part))}</pre>', encoding="utf-8",
            )
            image = destination / f"{stem}.png"
            subprocess.run([
                str(browser), "--headless", "--disable-gpu", "--hide-scrollbars",
                f"--user-data-dir={ROOT / '.browser-profile'}",
                f"--screenshot={image}", f"--window-size=1600,{max(700, 250 + len(part) * 28)}",
                document.as_uri(),
            ], check=True, capture_output=True, timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW)
            if not image.exists():
                raise RuntimeError(f"Browser did not create {image}")
            print(image.relative_to(ROOT))


if __name__ == "__main__":
    main()
