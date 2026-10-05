"""Execute the eight lab notebooks, preserving outputs and per-notebook logs.

Run with the lab virtualenv: python scripts/execute_notebooks.py
Optional positional arguments select notebook numbers, e.g. 3 4.
"""
from pathlib import Path
import sys

import jupytext
import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "submission" / "logs"


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    selected = {int(n) for n in sys.argv[1:]}
    for source in sorted((ROOT / "notebooks").glob("[0-9]*.py")):
        if selected and int(source.name[:2]) not in selected:
            continue
        notebook = jupytext.read(source)
        target = source.with_suffix(".ipynb")
        print(f"Executing {source.stem}", flush=True)
        try:
            NotebookClient(
                notebook, timeout=900, kernel_name="python3",
                resources={"metadata": {"path": str(source.parent)}},
            ).execute()
        finally:
            nbformat.write(notebook, target)
            outputs = []
            for cell in notebook.cells:
                for out in cell.get("outputs", []):
                    if out.output_type == "stream":
                        outputs.append(out.text)
                    elif out.output_type in ("display_data", "execute_result"):
                        outputs.append(out.get("data", {}).get("text/plain", ""))
                    elif out.output_type == "error":
                        outputs.append(f"{out.ename}: {out.evalue}")
            (LOGS / f"{source.stem}.txt").write_text("\n".join(outputs), encoding="utf-8")
        print(f"PASS {target.name}", flush=True)


if __name__ == "__main__":
    main()
