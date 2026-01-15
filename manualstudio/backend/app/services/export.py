"""Export services for generating Markdown and HTML from steps.json."""

from __future__ import annotations

import html
from typing import Any


def generate_markdown(steps_data: dict[str, Any]) -> str:
    """
    Generate Markdown document from steps.json data.

    Args:
        steps_data: The steps.json dictionary containing title, goal, steps, etc.

    Returns:
        Markdown formatted string
    """
    lines: list[str] = []

    # Title
    title = steps_data.get("title", "操作マニュアル")
    lines.append(f"# {title}")
    lines.append("")

    # Goal
    goal = steps_data.get("goal")
    if goal:
        lines.append(f"**目的**: {goal}")
        lines.append("")

    # Source info
    source = steps_data.get("source", {})
    if source:
        lines.append("## 動画情報")
        lines.append("")
        if source.get("video_duration_sec"):
            lines.append(f"- 長さ: {source['video_duration_sec']:.1f}秒")
        if source.get("resolution"):
            lines.append(f"- 解像度: {source['resolution']}")
        lines.append("")

    # Steps
    steps = steps_data.get("steps", [])
    if steps:
        lines.append("## 操作手順")
        lines.append("")

        for step in steps:
            no = step.get("no", "")
            telop = step.get("telop", "")
            action = step.get("action", "")
            target = step.get("target", "")
            narration = step.get("narration", "")
            caution = step.get("caution", "")
            start = step.get("start", "")
            end = step.get("end", "")

            lines.append(f"### ステップ {no}: {telop}")
            lines.append("")

            if start and end:
                lines.append(f"**時間**: {start} - {end}")
                lines.append("")

            if target:
                lines.append(f"**対象**: {target}")
                lines.append("")

            if action:
                lines.append(f"**操作**: {action}")
                lines.append("")

            if narration:
                lines.append(f"> {narration}")
                lines.append("")

            if caution:
                lines.append(f"⚠️ **注意**: {caution}")
                lines.append("")

    # Common mistakes
    mistakes = steps_data.get("common_mistakes", [])
    if mistakes:
        lines.append("## よくある間違い")
        lines.append("")

        for mistake in mistakes:
            lines.append(f"- **{mistake.get('mistake', '')}**")
            lines.append(f"  - 対処法: {mistake.get('fix', '')}")
        lines.append("")

    # Quiz
    quiz = steps_data.get("quiz", [])
    if quiz:
        lines.append("## 確認クイズ")
        lines.append("")

        for i, q in enumerate(quiz, 1):
            question = q.get("q", "")
            answer = q.get("a", "")
            q_type = q.get("type", "text")
            choices = q.get("choices", [])

            lines.append(f"**Q{i}**: {question}")
            lines.append("")

            if q_type == "choice" and choices:
                for choice in choices:
                    lines.append(f"- [ ] {choice}")
                lines.append("")

            lines.append("<details><summary>答えを見る</summary>")
            lines.append("")
            lines.append(f"**A**: {answer}")
            lines.append("")
            lines.append("</details>")
            lines.append("")

    return "\n".join(lines)


def _escape_html(text: str | None) -> str:
    """Escape HTML special characters to prevent XSS."""
    if text is None:
        return ""
    return html.escape(str(text))


def generate_html(steps_data: dict[str, Any]) -> str:
    """
    Generate HTML document from steps.json data.

    All user-provided content is HTML-escaped to prevent XSS attacks.

    Args:
        steps_data: The steps.json dictionary containing title, goal, steps, etc.

    Returns:
        HTML formatted string (complete document)
    """
    # Escape all user-provided content
    title = _escape_html(steps_data.get("title", "操作マニュアル"))
    goal = _escape_html(steps_data.get("goal", ""))

    parts: list[str] = []

    # HTML header
    parts.append(
        f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
            line-height: 1.6;
            color: #333;
        }}
        h1 {{ color: #2563eb; border-bottom: 2px solid #2563eb; padding-bottom: 0.5rem; }}
        h2 {{ color: #1e40af; margin-top: 2rem; }}
        h3 {{ color: #1e3a8a; }}
        .goal {{ background: #eff6ff; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem; }}
        .step {{ background: #f8fafc; padding: 1.5rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #2563eb; }}
        .step-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }}
        .step-time {{ color: #64748b; font-size: 0.9rem; }}
        .step-target {{ color: #64748b; font-size: 0.9rem; margin-bottom: 0.5rem; }}
        .step-action {{ font-weight: 500; margin-bottom: 0.5rem; }}
        .step-narration {{ color: #475569; font-style: italic; border-left: 3px solid #cbd5e1; padding-left: 1rem; }}
        .caution {{ background: #fef3c7; padding: 0.75rem; border-radius: 4px; margin-top: 0.5rem; color: #92400e; }}
        .caution::before {{ content: "⚠️ "; }}
        .mistakes {{ background: #fef2f2; padding: 1rem; border-radius: 8px; }}
        .mistake-item {{ margin-bottom: 1rem; }}
        .mistake-title {{ color: #dc2626; font-weight: 500; }}
        .mistake-fix {{ color: #16a34a; margin-left: 1rem; }}
        .quiz {{ background: #f0fdf4; padding: 1rem; border-radius: 8px; }}
        .quiz-item {{ margin-bottom: 1.5rem; }}
        .quiz-question {{ font-weight: 500; }}
        .quiz-choices {{ list-style: none; padding-left: 1rem; }}
        .quiz-answer {{ margin-top: 0.5rem; padding: 0.5rem; background: #dcfce7; border-radius: 4px; }}
        .source-info {{ color: #64748b; font-size: 0.9rem; }}
    </style>
</head>
<body>
"""
    )

    # Title
    parts.append(f"<h1>{title}</h1>")

    # Goal
    if goal:
        parts.append(f'<div class="goal"><strong>目的:</strong> {goal}</div>')

    # Source info
    source = steps_data.get("source", {})
    if source:
        parts.append('<div class="source-info">')
        parts.append("<h2>動画情報</h2>")
        parts.append("<ul>")
        if source.get("video_duration_sec"):
            parts.append(f"<li>長さ: {_escape_html(str(source['video_duration_sec']))}秒</li>")
        if source.get("resolution"):
            parts.append(f"<li>解像度: {_escape_html(source['resolution'])}</li>")
        parts.append("</ul>")
        parts.append("</div>")

    # Steps
    steps = steps_data.get("steps", [])
    if steps:
        parts.append("<h2>操作手順</h2>")

        for step in steps:
            no = _escape_html(str(step.get("no", "")))
            telop = _escape_html(step.get("telop", ""))
            action = _escape_html(step.get("action", ""))
            target = _escape_html(step.get("target", ""))
            narration = _escape_html(step.get("narration", ""))
            caution = _escape_html(step.get("caution", ""))
            start = _escape_html(step.get("start", ""))
            end = _escape_html(step.get("end", ""))

            parts.append('<div class="step">')
            parts.append('<div class="step-header">')
            parts.append(f"<h3>ステップ {no}: {telop}</h3>")
            if start and end:
                parts.append(f'<span class="step-time">{start} - {end}</span>')
            parts.append("</div>")

            if target:
                parts.append(f'<div class="step-target">対象: {target}</div>')

            if action:
                parts.append(f'<div class="step-action">{action}</div>')

            if narration:
                parts.append(f'<div class="step-narration">{narration}</div>')

            if caution:
                parts.append(f'<div class="caution">{caution}</div>')

            parts.append("</div>")

    # Common mistakes
    mistakes = steps_data.get("common_mistakes", [])
    if mistakes:
        parts.append("<h2>よくある間違い</h2>")
        parts.append('<div class="mistakes">')

        for mistake in mistakes:
            mistake_text = _escape_html(mistake.get("mistake", ""))
            fix_text = _escape_html(mistake.get("fix", ""))
            parts.append('<div class="mistake-item">')
            parts.append(f'<div class="mistake-title">❌ {mistake_text}</div>')
            parts.append(f'<div class="mistake-fix">✅ 対処法: {fix_text}</div>')
            parts.append("</div>")

        parts.append("</div>")

    # Quiz
    quiz = steps_data.get("quiz", [])
    if quiz:
        parts.append("<h2>確認クイズ</h2>")
        parts.append('<div class="quiz">')

        for i, q in enumerate(quiz, 1):
            question = _escape_html(q.get("q", ""))
            answer = _escape_html(q.get("a", ""))
            q_type = q.get("type", "text")
            choices = q.get("choices", [])

            parts.append('<div class="quiz-item">')
            parts.append(f'<div class="quiz-question">Q{i}: {question}</div>')

            if q_type == "choice" and choices:
                parts.append('<ul class="quiz-choices">')
                for choice in choices:
                    parts.append(f"<li>☐ {_escape_html(choice)}</li>")
                parts.append("</ul>")

            parts.append(f'<div class="quiz-answer"><strong>答え:</strong> {answer}</div>')
            parts.append("</div>")

        parts.append("</div>")

    # Close HTML
    parts.append("""
</body>
</html>""")

    return "\n".join(parts)
