import re


_ORDERED_STEP_RE = re.compile(r"^\d+[.)]\s+")


def _is_section_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith("#"):
        return stripped.lstrip("#").strip() or None
    if stripped.startswith("[") and stripped.endswith("]") and len(stripped) > 2:
        return stripped[1:-1].strip() or None
    if stripped.endswith(":") and len(stripped) > 1:
        return stripped[:-1].strip() or None
    return None


def _clean_step(line: str) -> str:
    stripped = line.strip()
    for prefix in ("- ", "* ", "• "):
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return _ORDERED_STEP_RE.sub("", stripped).strip()


def parse_instruction_sections(instructions: str) -> list[dict]:
    sections: list[dict] = []
    current_section: dict | None = None

    for raw_line in (instructions or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading = _is_section_heading(line)
        if heading:
            current_section = {"title": heading, "steps": []}
            sections.append(current_section)
            continue

        step = _clean_step(line)
        if not step:
            continue

        if current_section is None:
            current_section = {"title": None, "steps": []}
            sections.append(current_section)

        current_section["steps"].append(step)

    return [section for section in sections if section["steps"]]
