from __future__ import annotations

from mcp_app.config import skills_dir


def list_skill_names() -> list[str]:
    root = skills_dir()
    if not root.is_dir():
        return []
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and (p / "SKILL.md").is_file()
    )


def load_skill_markdown(name: str) -> str:
    path = skills_dir() / name / "SKILL.md"
    if not path.is_file():
        raise FileNotFoundError(f"Skill not found: {name} ({path})")
    return path.read_text(encoding="utf-8")


def load_skill_body(name: str) -> str:
    """Текст skill без YAML-frontmatter — для ответов MCP."""
    text = load_skill_markdown(name)
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()
