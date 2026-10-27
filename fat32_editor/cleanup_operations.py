"""Removal of macOS ._ metadata files from the disk image."""

import os
import tempfile
import tkinter as tk
from tkinter import messagebox, ttk


class CleanupOperationsMixin:
    def open_cleanup_progress(self, title):
        """Progress dialog with an animated bar and a Cancel button."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.resizable(False, False)

        cancelled = [False]

        def cancel():
            cancelled[0] = True
            label.config(text="Cancelling after the current file…")
            cancel_button.config(state=tk.DISABLED)

        dialog.protocol("WM_DELETE_WINDOW", cancel)

        label = ttk.Label(dialog, text="Scanning image…", width=60)
        label.pack(padx=15, pady=(15, 5), anchor="w")
        bar = ttk.Progressbar(dialog, length=420, mode="indeterminate")
        bar.pack(padx=15)
        bar.start(12)
        counter = ttk.Label(dialog, text="")
        counter.pack(padx=15, pady=(5, 5), anchor="w")
        cancel_button = ttk.Button(dialog, text="Cancel", command=cancel)
        cancel_button.pack(pady=(5, 15))

        dialog.grab_set()
        dialog.update()

        def set_total(total):
            bar.stop()
            bar.config(mode="determinate", maximum=max(total, 1), value=0)
            label.config(text="Removing ._ files…")

        def step(done, total, name):
            bar["value"] = done
            counter.config(text=f"{done} of {total}")
            shown = name if len(name) <= 60 else "…" + name[-59:]
            label.config(text=shown)
            dialog.update()

        def pump():
            dialog.update()

        def close():
            bar.stop()
            dialog.grab_release()
            dialog.destroy()

        return {
            "cancelled": cancelled,
            "pump": pump,
            "set_total": set_total,
            "step": step,
            "close": close,
        }

    def find_macos_metadata(self, folder, found, errors, progress=None):
        """Collect ._ files under folder recursively as (kind, name, path)."""
        if progress:
            progress["pump"]()
            if progress["cancelled"][0]:
                return

        directories, files, error = self.list_image_directory(folder)
        if error:
            errors.append(f"{folder}: {error}")
            return

        base = folder.rstrip("/")
        for name in files:
            if self.is_macos_metadata(name):
                found.append(("file", name, base + "/" + name))

        for name in directories:
            if progress and progress["cancelled"][0]:
                return
            self.find_macos_metadata(
                base + "/" + name, found, errors, progress
            )
    def clean_macos_metadata(self):
        if not self.image_ready():
            return

        found = []
        errors = []
        scan = self.open_cleanup_progress("Scanning for ._ Files")
        try:
            self.find_macos_metadata("/", found, errors, scan)
        finally:
            scan["close"]()

        if scan["cancelled"][0]:
            messagebox.showinfo(
                "Clean ._ Files",
                f"Scan cancelled. {len(found)} ._ file(s) found so far; "
                "nothing was removed.",
                parent=self.root
            )
            return

        if not found:
            if errors:
                messagebox.showwarning(
                    "Clean ._ Files", "\n".join(errors[:10]), parent=self.root
                )
            else:
                messagebox.showinfo(
                    "Clean ._ Files",
                    "No macOS ._ files were found on the image.",
                    parent=self.root
                )
            return

        listed = "\n".join(f"• {target}" for _, _, target in found[:10])
        if len(found) > 10:
            listed += f"\n…and {len(found) - 10} more"

        if not messagebox.askyesno(
            "Clean ._ Files",
            f"Delete {len(found)} macOS ._ file(s)?\n\n{listed}\n\n"
            "This deletion can be undone once. You can cancel while "
            "it runs.",
            icon="warning",
            parent=self.root
        ):
            return

        backup = tempfile.TemporaryDirectory(prefix="fat32-clean-undo-")
        steps = []
        removed = 0
        processed = 0
        progress = self.open_cleanup_progress("Removing ._ Files")
        progress["set_total"](len(found))

        try:
            for index, (_, name, target) in enumerate(found):
                if progress["cancelled"][0]:
                    break
                progress["step"](index, len(found), target)
                processed += 1
                if self.remove_one_metadata_file(
                    index, name, target, backup, steps, errors
                ):
                    removed += 1
                progress["pump"]()
        finally:
            progress["close"]()

        if progress["cancelled"][0]:
            errors.append(
                f"Cancelled: {len(found) - processed} file(s) were "
                "left on the image."
            )

        self.refresh()
        if steps:
            self.record_undo(
                f"Removed {removed} macOS ._ file(s)", steps, backup
            )
        else:
            backup.cleanup()

        if errors:
            messagebox.showwarning(
                "Some ._ Files Could Not Be Removed",
                f"Removed {removed} file(s).\n\n" + "\n".join(errors[:10]),
                parent=self.root
            )
        else:
            messagebox.showinfo(
                "Clean ._ Files",
                f"Removed {removed} macOS ._ file(s).",
                parent=self.root
            )

    def remove_one_metadata_file(
        self, index, name, target, backup, steps, errors
    ):
        """Back up one ._ file and delete it. Returns True when removed."""
        backup_dir = os.path.join(backup.name, str(index))
        local_backup = os.path.join(backup_dir, name)
        try:
            os.makedirs(backup_dir, exist_ok=True)
            backup_error = self.backup_image_file(target, local_backup)
        except OSError as exc:
            backup_error = str(exc)

        if backup_error:
            errors.append(f"{target}: could not back up: {backup_error}")
            return False

        result = self.run_mtools("mdel", self.image_path_argument(target))
        if result.returncode != 0:
            errors.append(f"{target}: {self.error_text(result)}")
            return False

        steps.append({
            "kind": "restore_file",
            "path": target,
            "backup_path": local_backup
        })
        return True


