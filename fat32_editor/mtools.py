"""mtools execution and FAT32 image path helpers."""

import os
import subprocess
from tkinter import messagebox

from .config import MTOOLS, PARTITION_OFFSET


class MtoolsMixin:
    def image_arg(self):
        return f"{self.image}@@{PARTITION_OFFSET}"

    def run_mtools(self, command, *args):
        executable = os.path.join(MTOOLS, command)

        if not os.path.isfile(executable):
            return subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr=f"Cannot find {executable}. Check MTOOLS."
            )

        try:
            return subprocess.run(
                [executable, "-i", self.image_arg(), *args],
                capture_output=True,
                text=True,
                timeout=120
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr=str(exc)
            )

    @staticmethod
    def image_path_argument(path):
        if not path.startswith("/"):
            path = "/" + path
        return "::" + path

    @staticmethod
    def parent_image_path(path):
        return path.rsplit("/", 1)[0] or "/"

    def list_image_directory(self, path):
        result = self.run_mtools(
            "mdir", "-a", "-b", self.directory_argument(path)
        )
        if result.returncode != 0:
            return None, None, self.error_text(result)

        directories, files = self.get_entries(result.stdout)
        return directories, files, None

    def find_image_entry(self, parent, name, entry_type):
        directories, files, error = self.list_image_directory(parent)
        if error:
            return None, error

        names = directories if entry_type == "directory" else files
        match = next(
            (entry for entry in names if entry.casefold() == name.casefold()),
            None
        )
        return match, None

    def directory_argument(self, folder=None):
        folder = self.folder if folder is None else folder

        if not folder.startswith("/"):
            folder = "/" + folder

        return "::" + folder

    def image_ready(self):
        if not os.path.isfile(self.image):
            messagebox.showerror(
                "Image not found",
                "Choose a valid disk image before editing."
            )
            return False

        return True

    @staticmethod
    def error_text(result):
        return (
            result.stderr.strip()
            or result.stdout.strip()
            or "The operation failed."
        )

    @staticmethod
    def valid_name(name):
        invalid = '<>:"/\\|?*'

        return (
            bool(name)
            and name not in (".", "..")
            and not any(
                ord(char) < 32 or char in invalid
                for char in name
            )
            and not name.endswith((" ", "."))
    )

    def get_entries(self, output):
        directories = []
        files = []

        for entry in output.splitlines():
            is_directory = entry.endswith("/")
            name = entry.rstrip("/").rsplit("/", 1)[-1]

            if not name or name in (".", ".."):
                continue

            if is_directory:
                directories.append(name)
            else:
                files.append(name)

        return directories, files
