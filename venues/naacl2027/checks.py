"""ARR rule the generic set cannot express: the submission must load acl.sty in review mode.

Only the preamble (before \\begin{document}) is read, so a \\usepackage shown in the body is not a load.
"""
import re
from pathlib import Path

ACL_RE = re.compile(r"\\usepackage\s*(\[([^\]]*)\])?\s*\{acl\}")


def check(project_dir, venue):
    root = Path(project_dir)
    out = []
    for f in sorted(root.rglob("*.tex")):
        if any(part.startswith(".") for part in f.relative_to(root).parts[:-1]):
            continue
        text = re.sub(r"(?<!\\)%.*", "", f.read_text(errors="replace"))
        text = text.split("\\begin{document}", 1)[0]  # the preamble; body examples are not loads
        for m in ACL_RE.finditer(text):
            opts = [o.strip() for o in (m.group(2) or "").split(",")]
            if "review" not in opts:
                out.append(("warning", f.relative_to(root).as_posix(),
                            f"{m.group(0)} is not the review version; ARR submissions use "
                            "\\usepackage[review]{acl} (anonymous, with line numbers)"))
    return out
