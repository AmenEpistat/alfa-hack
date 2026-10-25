"""Save each insight and its sources as separate Markdown files."""
from pathlib import Path

from alpha_parser.cache import atomic_text as write_text
from .markdown import render_insight_markdown, render_sources_markdown


def article_outputs(result: dict, *, directory: Path) -> list[tuple[Path, str]]:
    outputs = []
    for index, insight in enumerate(result.get("insights", []), 1):
        text = render_insight_markdown(insight)
        if not text:
            continue
        topic = insight.get("primary_topic")
        if topic not in {"news", "pdf", "competitors"}:
            topic = "insight"
        path = Path(directory) / f"{index:02d}_{topic}.md"
        outputs.extend([
            (path, text),
            (path.with_name(path.stem + "_sources.md"), render_sources_markdown(insight)),
        ])
    return outputs


def save_articles(result: dict, *, directory: Path, protected=()) -> list[str]:
    outputs = article_outputs(result, directory=directory)
    protected_paths = {path.resolve() for path in protected}
    if any(path.resolve() in protected_paths for path, _ in outputs):
        raise ValueError("Input, JSON and Markdown output must be different files")
    for path, text in outputs:
        write_text(path, text)
    return [str(path.resolve()) for path, _ in outputs]
