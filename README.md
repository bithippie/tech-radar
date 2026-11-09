# Bithippie Tech Radar

Our technology radar: what we adopt, trial, assess and hold. It feeds the Demo Day agenda —
pick a blip, demo it.

Built with Thoughtworks' [Build Your Own Radar](https://github.com/thoughtworks/build-your-own-radar)
(AGPL-3.0). This repo holds only our data pipeline and two build-time patches, both in
`.github/workflows/publish.yml`.

## How it works

```
Notion database "Tech Radar"  ──(daily Action)──►  exporter/notion_to_radar.py
        (rows with Publish ✓)                                │
                                                            ▼
                                     "<title>.json"  +  BYOR build (pinned SHA)
                                                            │
                                                            ▼
                                          GitHub Pages  ──►  embedded in Notion
```

- **Edit the radar in Notion.** Only rows with `Publish` checked are published.
- **Publishing** runs weekdays at 09:00 UTC, on every push to `main`, or by hand
  (Actions → Publish radar → Run workflow).
- **A bad row fails the run** and names the row. BYOR would otherwise drop a blip whose
  ring or quadrant it does not know, without saying so.

## The Notion database

| Property      | Type      | Values |
|---------------|-----------|--------|
| `Name`        | title     | the blip, unique |
| `Quadrant`    | select    | Techniques, Platforms, Tools, Languages & Frameworks |
| `Ring`        | select    | Adopt, Trial, Assess, Hold |
| `Movement`    | select    | New, Moved In, Moved Out, No Change (empty = No Change) |
| `Description` | text      | shown on the radar; bold, italic and links are kept |
| `Publish`     | checkbox  | only checked rows are published |

Quadrants, rings and the radar title live in `radar.config.json`; the build and the
exporter both read it.

## Setup (once)

1. Create an internal Notion integration, share the database with it, and add two repo
   secrets: `NOTION_TOKEN` and `NOTION_DATABASE_ID`.
2. Settings → Pages → Source: **GitHub Actions**.
3. Run the workflow. Its summary prints the URL to embed in Notion (use a full-width page:
   below ~1100px BYOR switches to its compact layout).

## Build-time patches to BYOR

- `normalizeRingNameHoldToCaution` off — upstream renames "Hold" to "Caution" and shows a
  Thoughtworks notice about it.
- Image paths in `index.html` made relative — upstream links them from the site root, which
  breaks when served from `/tech-radar/`.

Each patch is checked after it is applied; if upstream changes the line, the build fails
rather than shipping unpatched. Bump `BYOR_REF` deliberately.

## Tests

```
python3 -m unittest discover -s exporter -v
```
