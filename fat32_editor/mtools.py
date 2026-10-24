"""mtools execution and FAT32 image path helpers."""

import os
import subprocess
import tempfile
import uuid
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

    def rename_image_entry(self, source, destination):
        source_name = source.rsplit("/", 1)[-1]
        destination_name = destination.rsplit("/", 1)[-1]
        source_argument = self.image_path_argument(source)
        destination_argument = self.image_path_argument(destination)

        if source_name.casefold() != destination_name.casefold():
            return self.run_mtools(
                "mren", source_argument, destination_argument
            )

        parent = self.parent_image_path(source)
        directories, files, error = self.list_image_directory(parent)
        if error:
            return subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr=error
            )

        is_directory = any(
            name.casefold() == source_name.casefold()
            for name in directories
        )
        existing_names = directories + files
        while True:
            temporary_name = f"F32REN{uuid.uuid4().hex}"
            if not any(
                name.casefold() == temporary_name.casefold()
                for name in existing_names
            ):
                break

        temporary_path = parent.rstrip("/") + "/" + temporary_name
        temporary_argument = self.image_path_argument(temporary_path)
        result = self.run_mtools(
            "mren", source_argument, temporary_argument
        )
        if result.returncode != 0:
            return result

        result = self.run_mtools(
            "mren", temporary_argument, destination_argument
        )
        if result.returncode == 0:
            if self.image_name_listed(parent, destination_name):
                return result

            # mren keeps the old case flags of all-lower/all-upper names,
            # so move the entry back to its temporary name and recreate it.
            result = self.run_mtools(
                "mren", destination_argument, temporary_argument
            )
            if result.returncode == 0:
                error = self.recreate_image_entry(
                    temporary_path, destination, is_directory
                )
                if not error:
                    return subprocess.CompletedProcess(
                        args=[], returncode=0, stdout="", stderr=""
                    )
                result = subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr=error
                )

        rollback = self.run_mtools(
            "mren", temporary_argument, source_argument
        )
        if rollback.returncode != 0:
            return subprocess.CompletedProcess(
                args=result.args,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=(
                    f"{self.error_text(result)} "
                    "The temporary name could not be rolled back: "
                    f"{self.error_text(rollback)}"
                )
            )

        return result

    def image_name_listed(self, parent, name):
        directories, files, error = self.list_image_directory(parent)
        return not error and name in directories + files

    def recreate_image_entry(self, source, destination, is_directory):
        """Copy an entry out and back in under an exactly-cased name."""
        parent = self.parent_image_path(destination)
        destination_name = destination.rsplit("/", 1)[-1]
        parent_argument = self.directory_argument(parent)
        if not parent_argument.endswith("/"):
            parent_argument += "/"

        try:
            with tempfile.TemporaryDirectory(
                prefix="fat32-rename-"
            ) as work:
                staged = os.path.join(work, "out")
                renamed = os.path.join(work, "in")
                os.makedirs(staged)
                os.makedirs(renamed)
                local = os.path.join(renamed, destination_name)

                if is_directory:
                    result = self.run_mtools(
                        "mcopy", "-s", "-m",
                        self.image_path_argument(source), staged
                    )
                    copied = os.listdir(staged)
                    if result.returncode == 0 and len(copied) == 1:
                        os.rename(
                            os.path.join(staged, copied[0]), local
                        )
                else:
                    result = self.run_mtools(
                        "mcopy", "-m",
                        self.image_path_argument(source), local
                    )
                if result.returncode != 0:
                    return self.error_text(result)
                if not os.path.exists(local):
                    return "Could not copy the entry out of the image."

                result = self.run_mtools(
                    "mcopy", "-s", "-m", local, parent_argument
                )
                if result.returncode != 0 or not self.image_name_listed(
                    parent, destination_name
                ):
                    self.run_mtools(
                        "mdeltree" if is_directory else "mdel",
                        self.image_path_argument(destination)
                    )
                    return (
                        self.error_text(result)
                        if result.returncode != 0
                        else "The new name was not stored with the "
                             "requested letter case."
                    )
        except OSError as exc:
            return str(exc)

        cleanup = self.run_mtools(
            "mdeltree" if is_directory else "mdel",
            self.image_path_argument(source)
        )
        if cleanup.returncode != 0:
            return (
                "Renamed, but could not remove the temporary entry "
                f"'{source}': {self.error_text(cleanup)}"
            )
        return None

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
