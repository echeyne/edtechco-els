"""Build the arXiv upload folder (Task 13) from the paper sources.

Writes paper/arxiv_submission/src/ containing only what the build reads, with
every LaTeX comment stripped, figures flattened to the root, the bibliography
pre-compiled to main.bbl (references.bib is NOT shipped), and anc/ kept as a
directory so arXiv treats anc/prompts.txt as an ancillary file. Then tars it.

    python paper/analysis/build_arxiv_bundle.py

Requires a local pdflatex + bibtex, used once in a scratch copy to produce the
.bbl. Compile-from-clean verification is a separate step (see the README the
script writes next to the tarball).
"""
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
OUT = PAPER / "arxiv_submission"
SRC = OUT / "src"
TAR = OUT / "arxiv_upload.tar.gz"

STYLE_FILES = ["acl.sty", "acl_natbib.bst"]
ANCILLARY = ["anc/prompts.txt"]
TYPEOUT = r"\typeout{get arXiv to do 4 passes: Label(s) may have changed. Rerun}"

INPUT_RE = re.compile(r"\\input\{([^}]+)\}")
GRAPHICS_RE = re.compile(r"(\\includegraphics(?:\[[^\]]*\])?\{)([^}]+)(\})")


def strip_comments(text):
    """Remove every LaTeX comment without changing what TeX typesets.

    A line that is only a comment is dropped whole (TeX ignores its newline
    too, so no paragraph break appears or vanishes). An inline comment keeps
    its bare `%`, which preserves the end-of-line space suppression the author
    may have relied on. `\\%` is a literal percent, not a comment.
    """
    out = []
    for line in text.splitlines():
        m = re.search(r"(?<!\\)(?:\\\\)*%", line)
        if not m:
            out.append(line)
            continue
        # position of the unescaped % itself
        pct = m.end() - 1
        head = line[:pct]
        if head.strip() == "":
            continue
        out.append(head + "%")
    return "\n".join(out) + "\n"


PNG_METADATA_CHUNKS = {b"tEXt", b"iTXt", b"zTXt", b"eXIf", b"tIME"}


def strip_png_metadata(path):
    """Drop text/EXIF/XMP/timestamp chunks; pixels and colour profile are kept.

    Source files are public on arXiv, and a screenshot's metadata is not part
    of the figure. pdfTeX never copies these chunks into the PDF anyway.
    """
    data = path.read_bytes()
    out, i = [data[:8]], 8
    while i < len(data):
        n = int.from_bytes(data[i:i + 4], "big")
        chunk = data[i:i + 12 + n]
        if data[i + 4:i + 8] not in PNG_METADATA_CHUNKS:
            out.append(chunk)
        i += 12 + n
    path.write_bytes(b"".join(out))


def collect(tex_rel, seen):
    """Return every .tex file reachable by \\input from tex_rel."""
    if tex_rel in seen:
        return
    seen.append(tex_rel)
    body = strip_comments((PAPER / tex_rel).read_text())
    for name in INPUT_RE.findall(body):
        rel = name if name.endswith(".tex") else name + ".tex"
        collect(rel, seen)


def main():
    # Clear only what this script generates; SUBMISSION.md lives alongside.
    shutil.rmtree(SRC, ignore_errors=True)
    shutil.rmtree(OUT / "_bbl_build", ignore_errors=True)
    TAR.unlink(missing_ok=True)
    SRC.mkdir(parents=True)

    tex_files = []
    collect("main.tex", tex_files)

    figures = []
    for rel in tex_files:
        text = strip_comments((PAPER / rel).read_text())

        def flatten(m):
            path = m.group(2)
            figures.append(path)
            return m.group(1) + Path(path).name + m.group(3)

        text = GRAPHICS_RE.sub(flatten, text)
        if rel == "main.tex":
            text = text.rstrip("\n") + "\n" + TYPEOUT + "\n"
        dest = SRC / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)

    names = [Path(f).name for f in figures]
    if len(set(names)) != len(names):
        sys.exit(f"figure basenames collide after flattening: {names}")
    for f in figures:
        dest = SRC / Path(f).name
        shutil.copy2(PAPER / f, dest)
        if dest.suffix.lower() == ".png":
            strip_png_metadata(dest)
    for f in STYLE_FILES:
        shutil.copy2(PAPER / f, SRC / f)
    for f in ANCILLARY:
        (SRC / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PAPER / f, SRC / f)

    # Pre-compile the bibliography in a throwaway copy that does have the .bib,
    # so the shipped tree carries main.bbl and never references.bib.
    work = OUT / "_bbl_build"
    shutil.copytree(SRC, work)
    shutil.copy2(PAPER / "references.bib", work / "references.bib")
    run = lambda *cmd: subprocess.run(cmd, cwd=work, capture_output=True, text=True)
    run("pdflatex", "-interaction=nonstopmode", "main.tex")
    bib = run("bibtex", "main")
    (OUT / "bibtex.log").write_text(bib.stdout + bib.stderr)
    if not (work / "main.bbl").exists():
        sys.exit("bibtex produced no main.bbl; see arxiv_submission/bibtex.log")
    shutil.copy2(work / "main.bbl", SRC / "main.bbl")
    shutil.rmtree(work)

    def no_meta(info):
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        return info

    files = sorted(p for p in SRC.rglob("*") if p.is_file())
    with tarfile.open(TAR, "w:gz", format=tarfile.USTAR_FORMAT) as tar:
        for p in files:
            tar.add(p, arcname=str(p.relative_to(SRC)), filter=no_meta)

    print(f"{len(files)} files -> {TAR.relative_to(PAPER.parent)}")
    for p in files:
        print(f"  {p.relative_to(SRC)}  ({p.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
