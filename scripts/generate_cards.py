"""Generate the profile's stat cards as SVG files, using only the GitHub API."""

import json
import os
import sys
import urllib.request
from collections import Counter
from datetime import date, timedelta
from html import escape
from pathlib import Path

API_URL = "https://api.github.com/graphql"
USERNAME = "Shashank17singh"
TOP_LANGUAGES = 6
# Notebooks store their output in the file, so their size says little about the code.
IGNORED_LANGUAGES = {"Jupyter Notebook"}

BACKGROUND = "#0F172A"
BORDER = "#1E293B"
TITLE = "#3B82F6"
TEXT = "#F8FAFC"
MUTED = "#94A3B8"
FONT = "'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif"

PROFILE_QUERY = """
query ($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection { contributionYears }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

YEAR_QUERY = """
query ($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def graphql(query, variables, token):
    request = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={"Authorization": f"bearer {token}", "User-Agent": USERNAME},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0]["message"])
    return payload["data"]


def streaks(days, today):
    """Return the current and longest streak from a {date: count} mapping.

    Today may still be empty without ending the current streak, because the day is not over.
    """
    longest = run = 0
    for day in sorted(days):
        run = run + 1 if days[day] else 0
        longest = max(longest, run)

    cursor = today if days.get(today) else today - timedelta(days=1)
    current = 0
    while days.get(cursor):
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def language_shares(repositories, limit=TOP_LANGUAGES):
    """Return (name, colour, percent) for the largest languages across repositories."""
    sizes, colours = Counter(), {}
    for repository in repositories:
        for edge in repository["languages"]["edges"]:
            name = edge["node"]["name"]
            if name in IGNORED_LANGUAGES:
                continue
            sizes[name] += edge["size"]
            colours[name] = edge["node"]["color"] or MUTED
    total = sum(sizes.values())
    return [
        (name, colours[name], size / total * 100)
        for name, size in sizes.most_common(limit)
    ]


def card(width, height, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8" fill="{BACKGROUND}" stroke="{BORDER}"/>
  <text x="24" y="36" fill="{TITLE}" font-family="{FONT}" font-size="17" font-weight="600">{escape(title)}</text>
{body}
</svg>
"""


def stats_height(rows):
    return 70 + len(rows) * 26


def languages_height(shares):
    return 90 + ((len(shares) + 1) // 2) * 26


def stats_card(rows, height=0):
    """Draw the stats, spreading the rows out when the card is taller than they need."""
    height = max(height, stats_height(rows))
    gap = (height - 70) / len(rows)
    lines = []
    for index, (label, value) in enumerate(rows):
        y = round(70 + index * gap)
        lines.append(
            f'  <text x="24" y="{y}" fill="{MUTED}" font-family="{FONT}" font-size="14">{escape(label)}</text>'
        )
        lines.append(
            f'  <text x="361" y="{y}" fill="{TEXT}" font-family="{FONT}" font-size="14" font-weight="600" text-anchor="end">{value:,}</text>'
        )
    return card(385, height, "GitHub stats", "\n".join(lines))


def languages_card(shares, height=0):
    bar, x = [], 24.0
    for _, colour, percent in shares:
        width = 337 * percent / sum(share[2] for share in shares)
        bar.append(
            f'  <rect x="{x:.2f}" y="54" width="{width:.2f}" height="8" fill="{colour}"/>'
        )
        x += width
    legend = []
    for index, (name, colour, percent) in enumerate(shares):
        column, row = index % 2, index // 2
        lx, ly = 24 + column * 170, 90 + row * 26
        legend.append(f'  <circle cx="{lx + 5}" cy="{ly - 5}" r="5" fill="{colour}"/>')
        legend.append(
            f'  <text x="{lx + 16}" y="{ly}" fill="{TEXT}" font-family="{FONT}" font-size="13">{escape(name)} {percent:.1f}%</text>'
        )
    return card(
        385,
        max(height, languages_height(shares)),
        "Most used languages",
        "\n".join(bar + legend),
    )


def streak_card(total, current, longest):
    columns = [
        ("Total contributions", total),
        ("Current streak", current),
        ("Longest streak", longest),
    ]
    body = []
    for index, (label, value) in enumerate(columns):
        x = 90 + index * 165
        body.append(
            f'  <text x="{x}" y="86" fill="{TEXT}" font-family="{FONT}" font-size="28" font-weight="700" text-anchor="middle">{value:,}</text>'
        )
        body.append(
            f'  <text x="{x}" y="112" fill="{MUTED}" font-family="{FONT}" font-size="13" text-anchor="middle">{label}</text>'
        )
    return card(495, 135, "Contributions", "\n".join(body))


def collect(token, today):
    profile = graphql(PROFILE_QUERY, {"login": USERNAME}, token)["user"]
    days, commits, pulls, issues = {}, 0, 0, 0
    for year in profile["contributionsCollection"]["contributionYears"]:
        window = {
            "login": USERNAME,
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year}-12-31T23:59:59Z",
        }
        collection = graphql(YEAR_QUERY, window, token)["user"][
            "contributionsCollection"
        ]
        commits += collection["totalCommitContributions"]
        pulls += collection["totalPullRequestContributions"]
        issues += collection["totalIssueContributions"]
        for week in collection["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                when = date.fromisoformat(day["date"])
                if when <= today:
                    days[when] = day["contributionCount"]

    repositories = profile["repositories"]
    rows = [
        ("Commits", commits),
        ("Pull requests", pulls),
        ("Issues", issues),
        ("Public repositories", repositories["totalCount"]),
        ("Stars earned", sum(r["stargazerCount"] for r in repositories["nodes"])),
        ("Followers", profile["followers"]["totalCount"]),
    ]
    return [row for row in rows if row[1]], language_shares(repositories["nodes"]), days


def main():
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "cards")
    output.mkdir(parents=True, exist_ok=True)
    today = date.today()
    rows, shares, days = collect(os.environ["GITHUB_TOKEN"], today)
    current, longest = streaks(days, today)
    # The two sit side by side in the README, so they share a height.
    height = max(stats_height(rows), languages_height(shares))
    (output / "stats.svg").write_text(stats_card(rows, height), encoding="utf-8")
    (output / "languages.svg").write_text(
        languages_card(shares, height), encoding="utf-8"
    )
    (output / "streak.svg").write_text(
        streak_card(sum(days.values()), current, longest), encoding="utf-8"
    )
    print(f"Wrote 3 cards to {output}")


if __name__ == "__main__":
    main()
