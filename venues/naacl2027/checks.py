"""ARR rule the generic set cannot express: the submission must load acl.sty in review mode."""
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
        for m in ACL_RE.finditer(text):
            opts = [o.strip() for o in (m.group(2) or "").split(",")]
            if "review" not in opts:
                out.append(("warning", f.relative_to(root).as_posix(),
                            f"{m.group(0)} is not the review version; ARR submissions use "
                            "\\usepackage[review]{acl} (anonymous, with line numbers)"))
    return out
