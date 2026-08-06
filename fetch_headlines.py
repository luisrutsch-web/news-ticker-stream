"""
Fetches recent AI/tech headlines from RSS feeds, summarizes them into
punchy one-line ticker text using Claude, and writes headlines.json.

Run this on a schedule (cron, GitHub Actions, etc.) — see setup notes
at the bottom of this file.

Requirements: pip install feedparser requests
Environment variable required: ANTHROPIC_API_KEY
"""

import json
import os
import feedparser
import requests

# ---- 1. Sources: add/remove RSS feeds here ----
RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://venturebeat.com/category/ai/feed/",
]

MAX_HEADLINES = 10          # how many headlines to keep on the ticker
ARTICLES_PER_FEED = 5       # how many recent items to pull from each feed


def fetch_raw_headlines():
    """Pull recent article titles from each RSS feed."""
    raw = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:ARTICLES_PER_FEED]:
                raw.append(entry.title.strip())
        except Exception as e:
            print(f"Skipping feed {url}: {e}")
    return raw


def summarize_with_claude(raw_titles):
    """
    Send raw headlines to Claude and get back clean, punchy,
    ticker-ready one-liners (deduplicated, AI/tech-relevant only).
    """
    api_key = os.environ["ANTHROPIC_API_KEY"]

    prompt = (
        "Here is a list of raw news headlines:\n\n"
        + "\n".join(f"- {t}" for t in raw_titles)
        + f"\n\nRewrite the {MAX_HEADLINES} most interesting AI/tech-relevant "
        "ones as short, punchy news-ticker lines (under 12 words each). "
        "Remove duplicates and anything not about AI or technology. "
        "Respond with ONLY a JSON array of strings, nothing else, "
        "no markdown formatting, no explanation."
    )

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    text = "".join(
        block.get("text", "") for block in data["content"] if block.get("type") == "text"
    )

    # Strip accidental code fences just in case
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):]
    if text.startswith("```"):
        text = text[len("```"):]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    return json.loads(text)


def main():
    raw = fetch_raw_headlines()
    if not raw:
        print("No headlines fetched — leaving headlines.json untouched.")
        return

    try:
        clean_headlines = summarize_with_claude(raw)
    except Exception as e:
        print(f"Claude summarization failed, falling back to raw titles: {e}")
        clean_headlines = raw[:MAX_HEADLINES]

    with open("headlines.json", "w") as f:
        json.dump(clean_headlines, f, indent=2)

    print(f"Wrote {len(clean_headlines)} headlines to headlines.json")


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------
# HOW TO RUN THIS ON A SCHEDULE (pick one):
#
# OPTION A — GitHub Actions (free, no server needed):
#   1. Put this script + your news_ticker_overlay.html in a GitHub repo.
#   2. Enable GitHub Pages for that repo (Settings > Pages > deploy from
#      main branch). You'll get a URL like:
#      https://yourusername.github.io/your-repo/news_ticker_overlay.html
#   3. Add a repo secret named ANTHROPIC_API_KEY with your API key.
#   4. Add a workflow file at .github/workflows/update-headlines.yml
#      that runs this script every 15-30 minutes and commits the
#      updated headlines.json back to the repo. (Ask Claude for this
#      workflow file if you want it written out.)
#   5. Point Upstream's "Embed Website" overlay at your GitHub Pages URL.
#
# OPTION B — A cheap VPS/server with cron:
#   1. Upload this script + html file to any small server (e.g. a $5/mo
#      VPS, or a free-tier cloud function host).
#   2. Serve the folder with a simple web server (e.g. `python -m
#      http.server`, or nginx) so it has a public URL.
#   3. Add a cron job: */15 * * * * python3 /path/to/fetch_headlines.py
#   4. Point Upstream's "Embed Website" overlay at that public URL.
# ---------------------------------------------------------------------
