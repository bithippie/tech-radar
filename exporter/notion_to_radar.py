"""Export the Notion "Tech Radar" database to the JSON that Build Your Own Radar reads.

BYOR drops a blip silently when its ring or quadrant is not one the build was
configured with, so every row is validated here and the export fails loudly
instead of publishing a radar with blips missing.

Usage:
    NOTION_TOKEN=... NOTION_DATABASE_ID=... python exporter/notion_to_radar.py --out site/radar.json
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Iterator

NOTION_VERSION = "2022-06-28"
CONFIG_PATH = Path(__file__).resolve().parent.parent / "radar.config.json"

# Notion property names, as the database defines them.
PROP_NAME = "Name"
PROP_QUADRANT = "Quadrante"
PROP_RING = "Anel"
PROP_MOVEMENT = "Movimento"
PROP_DESCRIPTION = "Descrição"
PROP_PUBLISH = "Publicar"

# Notion "Movimento" option -> BYOR "status".
MOVEMENTS = {
    "New": "New",
    "Moved In": "Moved In",
    "Moved Out": "Moved Out",
    "No Change": "No Change",
}


class ExportError(Exception):
    pass


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def query_database(token: str, database_id: str) -> Iterator[dict]:
    """Yield every published row, following Notion's pagination."""
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    body = {"filter": {"property": PROP_PUBLISH, "checkbox": {"equals": True}}, "page_size": 100}
    while True:
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            page = json.load(response)
        yield from page["results"]
        if not page.get("has_more"):
            return
        body["start_cursor"] = page["next_cursor"]


def plain_title(prop: dict) -> str:
    return "".join(part["plain_text"] for part in prop.get("title", [])).strip()


def select_name(prop: dict) -> str | None:
    option = prop.get("select")
    return option["name"] if option else None


def rich_text_to_html(prop: dict) -> str:
    """Notion rich text -> HTML, kept to tags BYOR's sanitizer allows (b/i/em/strong/u/a/br/p...)."""
    out = []
    for part in prop.get("rich_text", []):
        text = html.escape(part["plain_text"]).replace("\n", "<br>")
        notes = part.get("annotations", {})
        if notes.get("bold"):
            text = f"<strong>{text}</strong>"
        if notes.get("italic"):
            text = f"<em>{text}</em>"
        href = (part.get("text") or {}).get("link") or part.get("href")
        if isinstance(href, dict):
            href = href.get("url")
        if href:
            text = f'<a href="{html.escape(href, quote=True)}" target="_blank" rel="noopener">{text}</a>'
        out.append(text)
    return "".join(out)


def to_blips(rows: list[dict], config: dict) -> list[dict]:
    quadrants, rings = config["quadrants"], config["rings"]
    blips, problems, seen = [], [], set()

    for row in rows:
        props = row["properties"]
        name = plain_title(props[PROP_NAME])
        label = name or row.get("url", row.get("id", "?"))
        quadrant = select_name(props[PROP_QUADRANT])
        ring = select_name(props[PROP_RING])
        movement = select_name(props[PROP_MOVEMENT]) or "No Change"

        if not name:
            problems.append(f"{label}: no name")
        elif name.lower() in seen:
            problems.append(f"{name}: duplicate name")
        if quadrant not in quadrants:
            problems.append(f"{label}: quadrant {quadrant!r} is not one of {quadrants}")
        if ring not in rings:
            problems.append(f"{label}: ring {ring!r} is not one of {rings}")
        if movement not in MOVEMENTS:
            problems.append(f"{label}: movement {movement!r} is not one of {list(MOVEMENTS)}")
        seen.add(name.lower())

        blips.append(
            {
                "name": name,
                "ring": ring,
                "quadrant": quadrant,
                "isNew": "TRUE" if movement == "New" else "FALSE",
                "status": MOVEMENTS.get(movement, movement),
                "description": rich_text_to_html(props[PROP_DESCRIPTION]),
            }
        )

    if problems:
        raise ExportError("rows that would not appear on the radar:\n  " + "\n  ".join(problems))
    if not blips:
        raise ExportError("no rows have 'Publicar' checked; refusing to publish an empty radar")

    blips.sort(key=lambda b: (quadrants.index(b["quadrant"]), rings.index(b["ring"]), b["name"].lower()))
    return blips


def export(out: Path, fetch: Callable[[], Iterator[dict]], config: dict) -> int:
    blips = to_blips(list(fetch()), config)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(blips, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(blips)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    token = os.environ.get("NOTION_TOKEN")
    database_id = os.environ.get("NOTION_DATABASE_ID")
    if not token or not database_id:
        print("NOTION_TOKEN and NOTION_DATABASE_ID must be set", file=sys.stderr)
        return 2

    try:
        count = export(args.out, lambda: query_database(token, database_id), load_config())
    except ExportError as error:
        print(f"export failed: {error}", file=sys.stderr)
        return 1
    print(f"wrote {count} blips to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
