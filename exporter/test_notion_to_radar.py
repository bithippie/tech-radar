import json
import tempfile
import unittest
from pathlib import Path

import notion_to_radar as nr

CONFIG = nr.load_config()


def text(value, **annotations):
    part = {"plain_text": value, "annotations": annotations, "text": {"content": value, "link": None}}
    return part


def row(name, quadrant="Tools", ring="Trial", movement="No Change", description=None):
    return {
        "id": f"id-{name}",
        "properties": {
            nr.PROP_NAME: {"title": [text(name)] if name else []},
            nr.PROP_QUADRANT: {"select": {"name": quadrant} if quadrant else None},
            nr.PROP_RING: {"select": {"name": ring} if ring else None},
            nr.PROP_MOVEMENT: {"select": {"name": movement} if movement else None},
            nr.PROP_DESCRIPTION: {"rich_text": description or []},
        },
    }


class ToBlipsTest(unittest.TestCase):
    def test_a_row_becomes_a_byor_blip(self):
        (blip,) = nr.to_blips([row("Argo", "Platforms", "Adopt", "New", [text("ok")])], CONFIG)
        self.assertEqual(
            blip,
            {"name": "Argo", "ring": "Adopt", "quadrant": "Platforms", "isNew": "TRUE", "status": "New", "description": "ok"},
        )

    def test_every_field_is_a_string_because_byor_trims_each_one(self):
        (blip,) = nr.to_blips([row("Argo")], CONFIG)
        self.assertTrue(all(isinstance(v, str) for v in blip.values()))

    def test_a_missing_movement_means_no_change(self):
        (blip,) = nr.to_blips([row("Argo", movement=None)], CONFIG)
        self.assertEqual((blip["status"], blip["isNew"]), ("No Change", "FALSE"))

    def test_blips_are_ordered_by_quadrant_then_ring_then_name(self):
        rows = [
            row("b", "Tools", "Hold"),
            row("a", "Tools", "Hold"),
            row("c", "Tools", "Adopt"),
            row("d", "Techniques", "Hold"),
        ]
        self.assertEqual([b["name"] for b in nr.to_blips(rows, CONFIG)], ["d", "c", "a", "b"])

    def test_rows_that_byor_would_drop_fail_the_export_naming_each_one(self):
        rows = [
            row("Caution ring", ring="Caution"),
            row("No quadrant", quadrant=None),
            row("", ring="Adopt"),
            row("Bad move", movement="Sideways"),
        ]
        with self.assertRaises(nr.ExportError) as caught:
            nr.to_blips(rows, CONFIG)
        message = str(caught.exception)
        for expected in ("Caution ring: ring 'Caution'", "No quadrant: quadrant None", "no name", "Bad move: movement"):
            self.assertIn(expected, message)

    def test_duplicate_names_fail_case_insensitively(self):
        with self.assertRaisesRegex(nr.ExportError, "argo: duplicate name"):
            nr.to_blips([row("Argo"), row("argo")], CONFIG)

    def test_an_empty_radar_is_refused(self):
        with self.assertRaisesRegex(nr.ExportError, "empty radar"):
            nr.to_blips([], CONFIG)


class RichTextTest(unittest.TestCase):
    def test_html_in_the_text_is_escaped(self):
        html = nr.rich_text_to_html({"rich_text": [text("<script>x</script> & y")]})
        self.assertEqual(html, "&lt;script&gt;x&lt;/script&gt; &amp; y")

    def test_annotations_and_links_become_allowed_tags(self):
        link = text("demo", bold=True)
        link["text"]["link"] = {"url": "https://example.com/?a=1&b=2"}
        html = nr.rich_text_to_html({"rich_text": [text("see ", italic=True), link, text("\nnext")]})
        self.assertEqual(
            html,
            '<em>see </em><a href="https://example.com/?a=1&amp;b=2" target="_blank" rel="noopener">'
            "<strong>demo</strong></a><br>next",
        )


class ExportTest(unittest.TestCase):
    def test_writes_a_json_array_and_creates_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site" / "radar.json"
            count = nr.export(out, lambda: iter([row("Argo"), row("Notion", "Platforms")]), CONFIG)
            self.assertEqual(count, 2)
            self.assertEqual([b["name"] for b in json.loads(out.read_text())], ["Notion", "Argo"])

    def test_a_failed_export_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "radar.json"
            with self.assertRaises(nr.ExportError):
                nr.export(out, lambda: iter([row("Argo", ring="Caution")]), CONFIG)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
