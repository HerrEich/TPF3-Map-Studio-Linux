import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

from src.core import bug_report as b

HOME = r"C:\Users\Max Mustermann"


class AnonymizeTests(unittest.TestCase):

    def test_benutzerordner_in_allen_schreibweisen(self):
        lines = [
            r"C:\Users\Max Mustermann\.tpf3_map_studio\cache",
            "C:/Users/Max Mustermann/Documents/x.zip",
            "C:\\\\Users\\\\Max Mustermann\\\\y",
            r"c:\users\max mustermann\z",
        ]

        result = b.anonymize("\n".join(lines), home=HOME, username="Max")

        self.assertNotIn("mustermann", result.lower())
        self.assertEqual(result.count(b.HOME_PLACEHOLDER), 4)

    def test_anderer_benutzer(self):
        result = b.anonymize(
            r"C:\Users\anna\Documents\x", home=HOME, username="Max"
        )
        self.assertEqual(result, r"C:\Users\<user>\Documents\x")

    def test_steam_id(self):
        result = b.anonymize(
            r"D:\Steam\userdata\123456789\3493540\local",
            home=HOME,
            username="Max",
        )
        self.assertEqual(result, r"D:\Steam\userdata\<id>\3493540\local")

    def test_email(self):
        result = b.anonymize(
            "Kontakt: max.m@example.com ok", home=HOME, username="Max"
        )
        self.assertEqual(result, "Kontakt: <email> ok")

    def test_benutzername_nur_als_ganzes_wort(self):
        result = b.anonymize(
            "angemeldet als sharp, Repo sharpi13822",
            home=HOME,
            username="sharp",
        )
        self.assertEqual(result, "angemeldet als <user>, Repo sharpi13822")

    def test_kurzer_benutzername_wird_nicht_ersetzt(self):
        text = "table ab cab"
        self.assertEqual(b.anonymize(text, home=HOME, username="ab"), text)

    def test_standardwerte_ersetzen_den_echten_benutzerordner(self):
        home = str(Path.home())
        result = b.anonymize("Pfad: " + home + "\\x")
        self.assertNotIn(home, result)


class ReportTests(unittest.TestCase):

    def test_zip_mit_logs_und_info(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            log = folder / "tpf3-map-studio.log"
            log.write_text(
                r"start C:\Users\Max Mustermann\x" + "\n", encoding="utf-8"
            )
            (folder / "tpf3-map-studio.log.1").write_text(
                "alt D:\\Steam\\userdata\\555\\x\n", encoding="utf-8"
            )
            (folder / "tpf3-map-studio.log.3").write_text(
                "drei\n", encoding="utf-8"
            )
            out = folder / "bericht.zip"

            names = b.create_report(
                out,
                log,
                "0.5.0",
                "de",
                pyside_version="6.8",
                extras={"osm_nodes": 12},
                now=datetime(2026, 10, 13, 18, 0, 0),
                home=HOME,
                username="Max",
            )

            with zipfile.ZipFile(out) as archive:
                self.assertEqual(sorted(archive.namelist()), sorted(names))
                info = archive.read("info.txt").decode("utf-8")
                log_text = archive.read(
                    "logs/tpf3-map-studio.log"
                ).decode("utf-8")
                old_text = archive.read(
                    "logs/tpf3-map-studio.log.1"
                ).decode("utf-8")

        self.assertEqual(
            names,
            [
                "info.txt",
                "logs/tpf3-map-studio.log",
                "logs/tpf3-map-studio.log.1",
                "logs/tpf3-map-studio.log.3",
            ],
        )
        self.assertIn("studio_version: 0.5.0", info)
        self.assertIn("osm_nodes: 12", info)
        self.assertIn("2026-10-13T18:00:00", info)
        self.assertIn("%USERPROFILE%", log_text)
        self.assertNotIn("Mustermann", log_text)
        self.assertIn("userdata\\<id>", old_text)

    def test_ohne_logdatei(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            out = folder / "bericht.zip"

            names = b.create_report(
                out, folder / "gibt-es-nicht.log", "0.5.0", "en",
                home=HOME, username="Max",
            )

            with zipfile.ZipFile(out) as archive:
                info = archive.read("info.txt").decode("utf-8")

        self.assertEqual(names, ["info.txt"])
        self.assertIn("logs: none found", info)

    def test_grosse_logdatei_nur_das_ende(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            log = folder / "tpf3-map-studio.log"
            rows = ["line %07d %s\n" % (i, "x" * 80) for i in range(50000)]
            log.write_text("".join(rows), encoding="utf-8")
            out = folder / "bericht.zip"

            b.create_report(out, log, "0.5.0", "de", home=HOME, username="Max")

            with zipfile.ZipFile(out) as archive:
                text = archive.read(
                    "logs/tpf3-map-studio.log"
                ).decode("utf-8")

        self.assertLessEqual(
            len(text.encode("utf-8")), b.MAX_LOG_BYTES + 200
        )
        lines = text.splitlines()
        self.assertIn("left out", lines[0])
        self.assertTrue(all(row.startswith("line ") for row in lines[1:]))
        self.assertTrue(lines[-1].startswith("line 0049999"))

    def test_ungueltige_bytes_im_log(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            log = folder / "tpf3-map-studio.log"
            log.write_bytes(b"ok \xff\xfe kaputt\n")
            out = folder / "bericht.zip"

            names = b.create_report(out, log, "0.5.0", "de", home=HOME, username="Max")

        self.assertIn("logs/tpf3-map-studio.log", names)

    def test_fehler_hinterlaesst_keine_datei(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "fehlt" / "bericht.zip"

            with self.assertRaises(OSError):
                b.create_report(out, Path(folder) / "x.log", "0.5.0", "de")

            self.assertFalse(out.exists())

    def test_standardname(self):
        self.assertEqual(
            b.default_report_name(datetime(2026, 10, 13, 18, 5, 9)),
            "tpf3-map-studio-fehlerbericht-20261013-180509.zip",
        )