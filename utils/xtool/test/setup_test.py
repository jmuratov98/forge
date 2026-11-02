# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# RUN: %python %s

"""./x setup against a fixture repository whose tools.json points at a local HTTP server, so that
nothing reaches the network. lit's Python is the venv's, which has requests, so setup's download
phase runs in it and the fixture never needs a venv of its own."""

import functools
import hashlib
import http.server
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

X = Path(__file__).resolve().parents[3] / "x.py"
sys.path.insert(0, str(X.parent / "utils"))

from xtool.host import host_key  # noqa: E402


def tar_gz(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, data, mode in entries:
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), mode
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def zipped(name, data):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        zip_file.writestr(name, data)
    return buffer.getvalue()


FAKE_PREMAKE = b"#!/bin/sh\necho 'premake5 (Premake Build Script Generator) 5.0.0'\n"
FAKE_NINJA = b"#!/bin/sh\necho 1.13.2\n"


@unittest.skipIf(os.name == "nt", "the fake tools are shell scripts")
class Setup(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        base = Path(self.directory.name)
        self.served = base / "served"
        self.served.mkdir()
        self.root = base / "root"
        (self.root / "utils" / "xtool").mkdir(parents=True)

        handler = functools.partial(QuietHandler, directory=str(self.served))
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

        self.serve("premake.tar.gz", tar_gz([("premake5", FAKE_PREMAKE, 0o755)]))
        self.serve("ninja.zip", zipped("ninja", FAKE_NINJA))
        self.serve("googletest.tar.gz", tar_gz([("googletest-1.0/googletest/include/gtest/gtest.h", b"//", 0o644)]))
        self.manifest = {
            "premake5": {"version": "5.0.0", "url": self.url + "/{asset}", "binary": "premake5",
                         "hosts": {host_key(): {"asset": "premake.tar.gz", "sha256": self.sha("premake.tar.gz")}}},
            "ninja": {"version": "1.13.2", "url": self.url + "/{asset}", "binary": "ninja",
                      "hosts": {host_key(): {"asset": "ninja.zip", "sha256": self.sha("ninja.zip")}}},
            "googletest": {"version": "1.0", "url": self.url + "/googletest.tar.gz", "strip": "googletest-{version}",
                           "into": "third_party/googletest", "sha256": self.sha("googletest.tar.gz")},
            "python": {},
        }
        self.write_manifest()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.directory.cleanup()

    def serve(self, name, data):
        (self.served / name).write_bytes(data)

    def sha(self, name):
        return hashlib.sha256((self.served / name).read_bytes()).hexdigest()

    def write_manifest(self):
        (self.root / "utils" / "xtool" / "tools.json").write_text(json.dumps(self.manifest))

    def setup(self, *arguments):
        environment = {name: value for name, value in os.environ.items()
                       if name not in ("FORGE_PREMAKE5", "FORGE_NINJA")}
        environment["NO_PROXY"] = "127.0.0.1"
        return subprocess.run([sys.executable, str(X), "--root", str(self.root), "setup", "--only",
                               "premake5,ninja,googletest", *arguments],
                              capture_output=True, text=True, env=environment)

    def test_install_then_nothing_to_do(self):
        first = self.setup()
        self.assertEqual(first.returncode, 0, first.stderr)
        premake = self.root / ".forge" / "tools" / "premake5" / "bin" / "premake5"
        self.assertTrue(os.access(premake, os.X_OK))
        self.assertTrue((self.root / ".forge" / "tools" / "ninja" / "bin" / "ninja").is_file())
        self.assertTrue((self.root / "third_party" / "googletest" / "googletest" / "include" / "gtest" / "gtest.h").is_file())
        self.assertIn("premake5: installed 5.0.0", first.stdout)

        installed = premake.stat().st_mtime_ns
        second = self.setup()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout.count("is up to date"), 3, second.stdout)
        self.assertEqual(premake.stat().st_mtime_ns, installed)

    def test_a_corrupt_download_keeps_the_previous_install(self):
        self.assertEqual(self.setup().returncode, 0)
        self.serve("ninja.zip", zipped("ninja", b"#!/bin/sh\necho 1.14.0\n"))
        self.manifest["ninja"]["version"] = "1.14.0"
        self.manifest["ninja"]["hosts"][host_key()]["sha256"] = "0" * 64
        self.write_manifest()

        failed = self.setup()
        self.assertEqual(failed.returncode, 1)
        self.assertIn("but tools.json pins " + "0" * 64, failed.stderr)
        ninja = self.root / ".forge" / "tools" / "ninja"
        self.assertEqual((ninja / "bin" / "ninja").read_bytes(), FAKE_NINJA)
        self.assertEqual(json.loads((ninja / "stamp.json").read_text())["version"], "1.13.2")
        self.assertEqual([path.name for path in ninja.parent.iterdir() if "ninja" in path.name], ["ninja"])

    def test_an_archive_that_escapes_is_refused(self):
        self.serve("googletest.tar.gz", tar_gz([("googletest-1.0/../../escaped", b"x", 0o644)]))
        self.manifest["googletest"]["sha256"] = self.sha("googletest.tar.gz")
        self.write_manifest()
        failed = self.setup()
        self.assertEqual(failed.returncode, 1)
        self.assertIn("points outside the archive", failed.stderr)
        self.assertFalse((self.root / "escaped").exists())
        self.assertFalse((self.root / "third_party" / "googletest").exists())

    def test_a_googletest_that_setup_did_not_install_is_kept(self):
        own = self.root / "third_party" / "googletest"
        own.mkdir(parents=True)
        (own / "mine").write_text("")
        refused = self.setup()
        self.assertEqual(refused.returncode, 1)
        self.assertIn("pass --force to replace it", refused.stderr)
        self.assertTrue((own / "mine").exists())

        forced = self.setup("--force")
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertFalse((own / "mine").exists())
        self.assertTrue((own / ".forge-stamp.json").is_file())


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *arguments):
        pass


if __name__ == "__main__":
    unittest.main()
