# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# RUN: %python %s

"""Archive extraction refuses anything that could write outside its destination, and an install
that fails leaves the previous one in place."""

import io
import os
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from xtool import download  # noqa: E402
from xtool.ui import XError  # noqa: E402


def make_tar(path, entries):
    """`entries`: (name, data) for a file, (name, None) for a directory, (name, "->target") for a
    symbolic link."""
    with tarfile.open(path, "w:gz") as tar:
        for name, data in entries:
            info = tarfile.TarInfo(name)
            if data is None:
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            elif isinstance(data, str):
                info.type = tarfile.SYMTYPE
                info.linkname = data[2:]
                tar.addfile(info)
            else:
                info.size = len(data)
                info.mode = 0o755 if name.endswith(".sh") else 0o644
                tar.addfile(info, io.BytesIO(data))


class Extraction(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.base = Path(self.directory.name)
        self.out = self.base / "out"

    def tearDown(self):
        self.directory.cleanup()

    def test_tree_strips_the_top_directory_and_keeps_modes(self):
        archive = self.base / "a.tar.gz"
        make_tar(archive, [("pkg-1/", None), ("pkg-1/include/a.h", b"a"), ("pkg-1/run.sh", b"#!")])
        self.assertEqual(download.extract_tree(archive, "pkg-1", self.out), 2)
        self.assertEqual((self.out / "include" / "a.h").read_bytes(), b"a")
        if os.name != "nt":
            self.assertTrue(os.access(self.out / "run.sh", os.X_OK))
            self.assertFalse(os.access(self.out / "include" / "a.h", os.X_OK))

    def assert_refused(self, archive, message):
        with self.assertRaises(XError) as raised:
            download.extract_tree(archive, "pkg-1", self.out)
        self.assertIn(message, str(raised.exception))
        self.assertFalse((self.base / "evil").exists())

    def test_parent_directory_is_refused(self):
        archive = self.base / "a.tar.gz"
        make_tar(archive, [("pkg-1/../../evil", b"x")])
        self.assert_refused(archive, "points outside the archive")

    def test_absolute_path_is_refused(self):
        archive = self.base / "a.tar.gz"
        # With forward slashes, as an archive names members: on Windows, the backslashes of
        # str() would be refused by an earlier check, and this one would go untested.
        make_tar(archive, [((self.base / "evil").as_posix(), b"x")])
        self.assert_refused(archive, "points outside the archive")

    def test_links_are_refused(self):
        archive = self.base / "a.tar.gz"
        make_tar(archive, [("pkg-1/link", "->../../evil")])
        self.assert_refused(archive, "not a regular file or directory")

    def test_zip_traversal_and_links_are_refused(self):
        archive = self.base / "a.zip"
        with zipfile.ZipFile(archive, "w") as zip_file:
            zip_file.writestr("pkg-1/../../evil", b"x")
        self.assert_refused(archive, "points outside the archive")
        with zipfile.ZipFile(archive, "w") as zip_file:
            info = zipfile.ZipInfo("pkg-1/link")
            info.external_attr = (0o120777 << 16)
            zip_file.writestr(info, "../../evil")
        self.assert_refused(archive, "is a link")

    def test_members_outside_the_top_directory_are_refused(self):
        archive = self.base / "a.tar.gz"
        make_tar(archive, [("other/a.h", b"a")])
        self.assert_refused(archive, "outside its top directory")

    def test_binary_is_found_anywhere_and_made_executable(self):
        archive = self.base / "a.zip"
        with zipfile.ZipFile(archive, "w") as zip_file:
            zip_file.writestr("dist/bin/tool", b"binary")
            zip_file.writestr("dist/README", b"text")
        download.extract_binary(archive, "tool", self.out / "tool")
        self.assertEqual((self.out / "tool").read_bytes(), b"binary")
        if os.name != "nt":
            self.assertTrue(os.access(self.out / "tool", os.X_OK))
        with self.assertRaises(XError):
            download.extract_binary(archive, "missing", self.out / "missing")


class Install(unittest.TestCase):
    def test_a_failed_install_keeps_the_previous_one(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "tool"
            download.install_directory(destination, lambda path: (path / "v1").write_text("1"))

            def fail(path):
                (path / "v2").write_text("2")
                raise XError("broken archive")

            with self.assertRaises(XError):
                download.install_directory(destination, fail)
            self.assertEqual(sorted(os.listdir(directory)), ["tool"])
            self.assertEqual(os.listdir(destination), ["v1"])

            download.install_directory(destination, lambda path: (path / "v3").write_text("3"))
            self.assertEqual(os.listdir(destination), ["v3"])


if __name__ == "__main__":
    unittest.main()
