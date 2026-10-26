"""Build the controlled documents: Markdown sources in src/ -> Word files and rendered Markdown in out/.

    python build_docs.py           # needs ../payload/trial_data (run ../payload/run_trial.sh first)

Numbers in the documents are not typed by hand: {{evaluation.centroid_rms_px:.2f}}-style fields are filled
from the trial and budget outputs, so the documents cannot drift from the software.
"""
import json
import pathlib
import re
import sys
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

HERE = pathlib.Path(__file__).resolve().parent
TRIAL = HERE.parent / "payload" / "trial_data"


def context():
    def load(p):
        if not p.exists():
            sys.exit(f"missing {p}: run payload/run_trial.sh and payload/budgets.py first")
        return json.loads(p.read_text())
    return {"evaluation": load(TRIAL / "evaluation.json"), "char": load(TRIAL / "calib" / "characterization.json"),
            "budget": load(HERE / "budgets" / "budgets.json"), "schedule": load(HERE / "figures" / "schedule.json")}


def fill(text, ctx):
    def sub(m):
        path, fmt = m.group(1), m.group(2) or ""
        v = ctx
        for part in path.split("."):
            v = v[int(part)] if isinstance(v, list) else v[part]
        return format(v, fmt)
    return re.sub(r"\{\{([\w.\-]+?)(?::([^}]+))?\}\}", sub, text)


def split_front(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    meta = {}
    for line in m.group(1).splitlines():
        k, v = line.split(":", 1)
        meta.setdefault(k.strip(), []).append(v.strip())
    return {k: v if k == "history" else v[0] for k, v in meta.items()}, text[m.end():]


def add_field(paragraph, instr):
    """A Word field (TOC, PAGE): Word fills it in when the document is opened and fields are updated."""
    run = paragraph.add_run()
    for tag, attr in (("w:fldChar", "begin"), ("w:instrText", None), ("w:fldChar", "separate"), ("w:fldChar", "end")):
        el = OxmlElement(tag)
        if attr:
            el.set(qn("w:fldCharType"), attr)
        else:
            el.set(qn("xml:space"), "preserve"); el.text = instr
        run._r.append(el)


def inline(paragraph, text):
    for part in re.split(r"(\*\*.+?\*\*|`.+?`)", text):
        if part.startswith("**") and part.endswith("**"):
            paragraph.add_run(part[2:-2]).bold = True
        elif part.startswith("`") and part.endswith("`"):
            r = paragraph.add_run(part[1:-1]); r.font.name = "Consolas"; r.font.size = Pt(9.5)
        elif part:
            paragraph.add_run(part)


def table(doc, rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows if not re.match(r"^\|[\s:|-]+\|$", r.strip())]
    t = doc.add_table(rows=len(cells), cols=len(cells[0])); t.style = "Table Grid"
    for i, row in enumerate(cells):
        for j, c in enumerate(row):
            p = t.cell(i, j).paragraphs[0]; inline(p, c)
            for r in p.runs:
                r.font.size = Pt(9); r.bold = r.bold or i == 0
    doc.add_paragraph()


def build(src, ctx):
    meta, body = split_front(fill(src.read_text(), ctx))
    out_md = HERE / "out" / f"{meta['id']}.md"
    out_md.write_text(f"# {meta['title']}\n\n{meta['id']} rev {meta['revision']}, {meta['date']}\n" + body)
    doc = Document()
    st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2.2)
        hp = s.header.paragraphs[0]; hp.text = f"{meta['id']}  rev {meta['revision']}\t\t{meta['title']}"
        hp.runs[0].font.size = Pt(8)
        fp = s.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER; fp.add_run("Page "); add_field(fp, "PAGE")
    doc.add_paragraph(meta["title"], style="Title")
    p = doc.add_paragraph(); inline(p, f"**Document:** {meta['id']}    **Revision:** {meta['revision']}    **Date:** {meta['date']}")
    p = doc.add_paragraph(); inline(p, f"**Status:** {meta['status']}    **Prepared by:** {meta['author']}")
    doc.add_heading("Document control", level=2)
    table(doc, ["| Revision | Date | Change |"] + [f"| {h.replace(' / ', ' | ')} |" for h in meta["history"]])
    table(doc, ["| Role | Name | Signature | Date |", f"| Prepared | {meta['author']} | | |", "| Checked | | | |", "| Approved | | | |"])
    doc.add_heading("Contents", level=2)
    add_field(doc.add_paragraph(), 'TOC \\o "1-3" \\h \\z \\u')
    doc.add_page_break()
    lines, i = body.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if m := re.match(r"^(#{1,3}) (.*)", ln):
            doc.add_heading(m.group(2), level=len(m.group(1)))
        elif ln.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i]); i += 1
            table(doc, block); continue
        elif m := re.match(r"^!\[(.*)\]\((.*)\)", ln):
            doc.add_picture(str((src.parent / m.group(2)).resolve()), width=Cm(16))
            doc.add_paragraph(m.group(1), style="Caption")
        elif m := re.match(r"^\s*- (\[ \] )?(.*)", ln):
            if m.group(1):                                   # checklist item: a box to tick on paper
                inline(doc.add_paragraph(), "\u2610  " + m.group(2))
            else:
                inline(doc.add_paragraph(style="List Bullet"), m.group(2))
        elif m := re.match(r"^\s*\d+\. (.*)", ln):
            inline(doc.add_paragraph(style="List Number"), m.group(1))
        elif ln.strip():
            para = [ln]
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^(#|\||!\[|\s*- |\s*\d+\. )", lines[i + 1]):
                i += 1; para.append(lines[i])
            inline(doc.add_paragraph(), " ".join(para))
        i += 1
    doc.save(HERE / "out" / f"{meta['id']}.docx")
    return meta["id"]


if __name__ == "__main__":
    (HERE / "out").mkdir(exist_ok=True)
    ctx = context()
    for src in sorted((HERE / "src").glob("*.md")):
        print("built", build(src, ctx))
