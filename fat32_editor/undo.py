"""Single-level undo operations for disk image edits."""

import os
import tkinter as tk
from tkinter import messagebox


class UndoMixin:
    def record_undo(self, label, steps, backup=None):
        if not steps:
            if backup:
                backup.cleanup()
            return

        previous_backup = self.undo_tempdir
        self.undo_action = {
            "label": label,
            "image": self.image,
            "steps": steps
        }
        self.undo_tempdir = backup
        self.undo_button.config(state=tk.NORMAL)

        if previous_backup:
            try:
                previous_backup.cleanup()
            except OSError as exc:
                messagebox.showwarning(
                    "Could not remove previous undo data",
                    str(exc),
                    parent=self.root
                )

        self.status.config(text=f"{label}. Undo is available.")

    def clear_undo(self):
        backup = self.undo_tempdir
        self.undo_action = None
        self.undo_tempdir = None
        self.undo_button.config(state=tk.DISABLED)

        if backup:
            try:
                backup.cleanup()
            except OSError as exc:
                messagebox.showwarning(
                    "Could not remove undo data",
                    str(exc),
                    parent=self.root
                )

    def backup_image_file(self, image_path, local_path):
        result = self.run_mtools(
            "mcopy",
            "-o",
            self.image_path_argument(image_path),
            local_path
        )
        return None if result.returncode == 0 else self.error_text(result)

    def backup_folder_contents(self, image_path, local_path):
        os.makedirs(local_path, exist_ok=True)
        directories, files, error = self.list_image_directory(image_path)
        if error:
            return error

        for name in directories:
            child_error = self.backup_folder_contents(
                image_path.rstrip("/") + "/" + name,
                os.path.join(local_path, name)
            )
            if child_error:
                return child_error

        for name in files:
            source = image_path.rstrip("/") + "/" + name
            destination = os.path.join(local_path, name)
            copy_error = self.backup_image_file(source, destination)
            if copy_error:
                return copy_error

        return None

    def ensure_image_directory(self, path):
        parent = self.parent_image_path(path)
        name = path.rsplit("/", 1)[-1]
        existing, error = self.find_image_entry(
            parent, name, "directory"
        )
        if error:
            return error
        if existing:
            return None

        result = self.run_mtools(
            "mmd", self.image_path_argument(path)
        )
        return None if result.returncode == 0 else self.error_text(result)

    def restore_folder_contents(self, image_path, local_path):
        for current, directories, files in os.walk(local_path):
            directories.sort()
            files.sort()
            relative = os.path.relpath(current, local_path)
            remote_dir = image_path

            if relative != ".":
                remote_dir += "/" + relative.replace(os.sep, "/")

            for name in directories:
                child = remote_dir.rstrip("/") + "/" + name
                error = self.ensure_image_directory(child)
                if error:
                    return error

            for name in files:
                local_file = os.path.join(current, name)
                destination = self.directory_argument(remote_dir)
                if not destination.endswith("/"):
                    destination += "/"
                result = self.run_mtools(
                    "mcopy", "-o", local_file, destination
                )
                if result.returncode != 0:
                    return self.error_text(result)

        return None

    def apply_undo_step(self, step):
        kind = step["kind"]
        path = step.get("path")

        if kind in ("delete_file", "delete_folder"):
            entry_type = "file" if kind == "delete_file" else "directory"
            existing, error = self.find_image_entry(
                self.parent_image_path(path),
                path.rsplit("/", 1)[-1],
                entry_type
            )
            if error:
                return error
            if not existing:
                return None

            command = "mdel" if kind == "delete_file" else "mdeltree"
            result = self.run_mtools(
                command, self.image_path_argument(path)
            )
            return None if result.returncode == 0 else self.error_text(result)

        if kind == "restore_file":
            result = self.run_mtools(
                "mcopy",
                "-o",
                step["backup_path"],
                self.image_path_argument(path)
            )
            return None if result.returncode == 0 else self.error_text(result)

        if kind == "restore_folder":
            error = self.ensure_image_directory(path)
            if error:
                return error
            return self.restore_folder_contents(path, step["backup_path"])

        if kind == "rename":
            source = step["source"]
            destination = step["destination"]
            entry_type = step["entry_type"]
            source_name, error = self.find_image_entry(
                self.parent_image_path(source),
                source.rsplit("/", 1)[-1],
                entry_type
            )
            if error:
                return error

            if not source_name:
                destination_name, error = self.find_image_entry(
                    self.parent_image_path(destination),
                    destination.rsplit("/", 1)[-1],
                    entry_type
                )
                if error:
                    return error
                return None if destination_name else (
                    f"Neither '{source}' nor '{destination}' exists."
                )

            result = self.rename_image_entry(source, destination)
            return None if result.returncode == 0 else self.error_text(result)

        return f"Unknown undo operation: {kind}"

    def undo(self):
        if not self.undo_action:
            return

        if self.undo_action["image"] != self.image:
            messagebox.showerror(
                "Cannot undo",
                "The selected disk image has changed.",
                parent=self.root
            )
            self.clear_undo()
            return

        label = self.undo_action["label"]
        steps = self.undo_action["steps"]
        while steps:
            error = self.apply_undo_step(steps[-1])
            if error:
                messagebox.showerror(
                    "Undo incomplete",
                    f"Could not undo {label}:\n{error}",
                    parent=self.root
                )
                self.refresh()
                self.status.config(
                    text=f"Undo incomplete: {label}. Undo can be retried."
                )
                return
            steps.pop()

        self.clear_undo()
        self.refresh()
        self.status.config(text=f"Undid: {label}")
