"""Generate assets/top-languages-{light,dark}.svg from the public repos of a GitHub user.

Runs in GitHub Actions (see .github/workflows/top-languages.yml). Standard library only.
Env vars:
  GH_USERNAME    GitHub user to analyse (required)
  GITHUB_TOKEN   token for higher API rate limits (optional)
  MAX_LANGS      number of languages to show (default 6)
  EXCLUDE_LANGS  comma-separated languages to ignore, e.g. "HTML,CSS"
"""

import json
import os
import urllib.request
from html import escape
from pathlib import Path

USERNAME = os.environ.get("GH_USERNAME", "").strip()
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
MAX_LANGS = int(os.environ.get("MAX_LANGS", "6"))
EXCLUDE = {s.strip().lower() for s in os.environ.get("EXCLUDE_LANGS", "").split(",") if s.strip()}
OUT_DIR = Path(__file__).resolve().parents[2] / "assets"

# Colours from github-linguist for common languages; others fall back to a palette.
LANG_COLORS = {
    "Python": "#3572A5", "Jupyter Notebook": "#DA5B0B", "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a", "HTML": "#e34c26", "CSS": "#663399", "SCSS": "#c6538c",
    "Shell": "#89e051", "Dockerfile": "#384d54", "Swift": "#F05138", "Kotlin": "#A97BFF",
    "Java": "#b07219", "C": "#555555", "C++": "#f34b7d", "C#": "#178600", "Go": "#00ADD8",
    "Rust": "#dea584", "Dart": "#00B4AB", "Vue": "#41b883", "PLpgSQL": "#336790",
    "TSQL": "#e38c00", "R": "#198CE7", "Ruby": "#701516", "PHP": "#4F5D95", "MDX": "#fcb32c",
    "Objective-C": "#438eff", "Svelte": "#ff3e00", "Astro": "#ff5a03",
}
FALLBACK = ["#3b82f6", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ec4899"]

THEMES = {
    "light": dict(bg="#f8faff", border="#e3e8f5", title="#1f2937", text="#374151", muted="#6b7280", track="#e5e9f5"),
    "dark": dict(bg="#0f1420", border="#252c3d", title="#e6edf3", text="#c9d1d9", muted="#8b949e", track="#1f2637"),
}
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"


def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-readme-top-languages")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def collect():
    totals, page = {}, 1
    while True:
        repos = api(f"/users/{USERNAME}/repos?type=owner&per_page=100&page={page}")
        if not repos:
            break
        for repo in repos:
            # skip forks and the profile repo itself (it only holds this script)
            if repo["fork"] or repo["name"].lower() == USERNAME.lower():
                continue
            for lang, size in api(f"/repos/{repo['full_name']}/languages").items():
                if lang.lower() not in EXCLUDE:
                    totals[lang] = totals.get(lang, 0) + size
        page += 1
    return totals


def render(totals, t):
    width, pad, cols = 840, 28, 3
    langs = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:MAX_LANGS]
    total = sum(size for _, size in langs)
    parts = [
        f'<text x="{pad}" y="38" font-size="17" font-weight="600" fill="{t["title"]}">Most used languages</text>'
    ]

    if not total:
        height = 110
        parts.append(
            f'<text x="{pad}" y="76" font-size="13" fill="{t["muted"]}">Stats will appear after the first workflow run.</text>'
        )
    else:
        bar_w, x = width - 2 * pad, float(pad)
        segs = []
        for i, (lang, size) in enumerate(langs):
            w = bar_w * size / total
            color = LANG_COLORS.get(lang, FALLBACK[i % len(FALLBACK)])
            segs.append(f'<rect x="{x:.2f}" y="58" width="{w + 0.5:.2f}" height="10" fill="{color}"/>')
            x += w
        parts.append('<clipPath id="bar"><rect x="%d" y="58" width="%d" height="10" rx="5"/></clipPath>' % (pad, bar_w))
        parts.append(f'<rect x="{pad}" y="58" width="{bar_w}" height="10" rx="5" fill="{t["track"]}"/>')
        parts.append('<g clip-path="url(#bar)">' + "".join(segs) + "</g>")

        col_w = (width - 2 * pad) / cols
        for i, (lang, size) in enumerate(langs):
            cx = pad + (i % cols) * col_w
            cy = 98 + (i // cols) * 28
            color = LANG_COLORS.get(lang, FALLBACK[i % len(FALLBACK)])
            pct = 100 * size / total
            parts.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{color}"/>')
            parts.append(f'<text x="{cx + 18}" y="{cy}" font-size="13" fill="{t["text"]}">{escape(lang)}</text>')
            pct_x = cx + col_w - (0 if i % cols == cols - 1 else 32)
            parts.append(
                f'<text x="{pct_x:.0f}" y="{cy}" font-size="13" fill="{t["muted"]}" text-anchor="end">{pct:.1f}%</text>'
            )
        height = 98 + ((len(langs) + cols - 1) // cols - 1) * 28 + 26

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Most used languages" font-family="{FONT}">'
        f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="14" fill="{t["bg"]}" '
        f'stroke="{t["border"]}" stroke-width="2"/>' + "".join(parts) + "</svg>\n"
    )


def main():
    if not USERNAME:
        raise SystemExit("GH_USERNAME is not set")
    totals = collect()
    OUT_DIR.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        (OUT_DIR / f"top-languages-{name}.svg").write_text(render(totals, theme))
    print(f"{len(totals)} languages found for {USERNAME}")


if __name__ == "__main__":
    main()
