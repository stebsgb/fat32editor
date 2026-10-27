"""Combined add (merge) and delete operations for files and folders."""

import os
import subprocess
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Tk's folder dialog picks one folder only; this allows several.
CHOOSE_FOLDERS_SCRIPT = """
set chosen to choose folder with prompt "Choose folders to add" with multiple selections allowed
set output to ""
repeat with item_ in chosen
    set output to output & POSIX path of item_ & linefeed
end repeat
return output
"""


class BatchOperationsMixin:
    def pick_folders(self, parent):
        try:
            result = subprocess.run(
                ["osascript", "-e", CHOOSE_FOLDERS_SCRIPT],
                capture_output=True,
                text=True
            )
        except OSError:
            result = None

        if result is not None and result.returncode == 0:
            return [line for line in result.stdout.splitlines() if line]
        if result is not None and "-128" in result.stderr:
            return []

        folder = filedialog.askdirectory(
            title="Choose a folder to add", parent=parent
        )
        return [folder] if folder else []

    def choose_items_to_add(self):
        """Collect any number of files and folders; [] means cancelled."""
        paths = []
        confirmed = []

        dialog = tk.Toplevel(self.root)
        dialog.title("Add Files & Folders")
        dialog.transient(self.root)
        dialog.resizable(True, True)

        listbox = tk.Listbox(
            dialog, width=70, height=12, selectmode=tk.EXTENDED,
            exportselection=False, **self.list_colors
        )

        def include(new_paths):
            for path in new_paths:
                path = path.rstrip(os.sep) or path
                if path not in paths:
                    paths.append(path)
                    listbox.insert(
                        tk.END,
                        ("▣ " if os.path.isdir(path) else "• ") + path
                    )

        def choose_files():
            include(filedialog.askopenfilenames(
                title="Choose files to add", parent=dialog
            ))

        def choose_folders():
            include(self.pick_folders(dialog))

        def remove_selected():
            for index in reversed(listbox.curselection()):
                listbox.delete(index)
                del paths[index]

        def accept():
            confirmed.append(True)
            dialog.destroy()

        ttk.Label(
            dialog,
            text="Choose any number of files and folders, then press Add."
        ).pack(anchor="w", padx=10, pady=(10, 5))
        listbox.pack(fill="both", expand=True, padx=10)

        row = ttk.Frame(dialog)
        row.pack(fill="x", padx=10, pady=10)
        ttk.Button(
            row, text="＋ Files…", command=choose_files
        ).pack(side="left")
        ttk.Button(
            row, text="＋ Folders…", command=choose_folders
        ).pack(side="left", padx=5)
        ttk.Button(
            row, text="Remove", command=remove_selected
        ).pack(side="left")
        ttk.Button(
            row, text="Add", command=accept
        ).pack(side="right")
        ttk.Button(
            row, text="Cancel", command=dialog.destroy
        ).pack(side="right", padx=5)

        dialog.bind("<Escape>", lambda event: dialog.destroy())
        dialog.grab_set()
        self.root.wait_window(dialog)

        return list(paths) if confirmed else []

    def add_items(self):
        if not self.image_ready():
            return

        paths = self.choose_items_to_add()
        if not paths:
            return

        context = {
            "steps": [],
            "errors": [],
            "count": 0,
            "backup": None,
            "backup_count": 0
        }
        progress = self.open_progress(self.count_local_items(paths))
        context["progress"] = progress
        try:
            self.merge_entries(paths, self.folder, context, False)
        finally:
            progress["close"]()

        self.refresh()
        self.record_undo(
            "Added items", context["steps"], context["backup"]
        )
        self.show_result("Add", context["count"], context["errors"])

    def count_local_items(self, paths):
        total = 0
        for path in paths:
            if self.is_macos_metadata(os.path.basename(path.rstrip(os.sep))):
                continue
            total += 1
            if os.path.isdir(path) and not os.path.islink(path):
                for _, dirs, files in os.walk(path):
                    total += (
                        len([d for d in dirs if not self.is_macos_metadata(d)])
                        + len([f for f in files if not self.is_macos_metadata(f)])
                    )
        return total

    def open_progress(self, total):
        dialog = tk.Toplevel(self.root)
        dialog.title("Adding…")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)

        label = ttk.Label(dialog, text="Preparing…", width=60)
        label.pack(padx=15, pady=(15, 5), anchor="w")
        bar = ttk.Progressbar(
            dialog, length=420, maximum=max(total, 1)
        )
        bar.pack(padx=15)
        counter = ttk.Label(dialog, text=f"0 of {total}")
        counter.pack(padx=15, pady=(5, 15), anchor="w")

        dialog.grab_set()
        dialog.update()
        done = [0]

        def step(name):
            done[0] += 1
            shown = name if len(name) <= 60 else "…" + name[-59:]
            label.config(text=shown)
            bar["value"] = done[0]
            counter.config(text=f"{done[0]} of {total}")
            dialog.update()

        def close():
            dialog.grab_release()
            dialog.destroy()

        return {"step": step, "close": close}

    def merge_entries(self, local_paths, remote_dir, context, inside_new):
        """Merge local files/folders into remote_dir, overwriting files."""
        directories, files, error = self.list_image_directory(remote_dir)
        if error:
            context["errors"].append(f"{remote_dir}: {error}")
            return

        directory_names = {name.casefold(): name for name in directories}
        file_names = {name.casefold(): name for name in files}

        for path in local_paths:
            name = os.path.basename(path.rstrip(os.sep))
            if self.is_macos_metadata(name):
                # Never copy macOS ._ sidecar files onto the SD card.
                continue
            key = name.casefold()

            if os.path.isdir(path):
                if os.path.islink(path):
                    context["errors"].append(
                        f"{name}: skipped linked folder"
                    )
                    continue
                if key in file_names:
                    context["errors"].append(
                        f"{name}: a file with this name already exists"
                    )
                    continue

                context["progress"]["step"](path)
                created = key not in directory_names
                folder_name = directory_names.get(key, name)
                child_dir = remote_dir.rstrip("/") + "/" + folder_name

                if created:
                    if not self.valid_name(name):
                        context["errors"].append(
                            f"{name}: invalid FAT32 folder name"
                        )
                        continue
                    result = self.run_mtools(
                        "mmd", self.image_path_argument(child_dir)
                    )
                    if result.returncode != 0:
                        context["errors"].append(
                            f"{child_dir}: {self.error_text(result)}"
                        )
                        continue
                    directory_names[key] = name
                    if not inside_new:
                        context["steps"].append(
                            {"kind": "delete_folder", "path": child_dir}
                        )

                try:
                    children = sorted(
                        os.path.join(path, child)
                        for child in os.listdir(path)
                    )
                except OSError as exc:
                    context["errors"].append(f"{path}: {exc}")
                    continue

                self.merge_entries(
                    children, child_dir, context, inside_new or created
                )
                continue

            if key in directory_names:
                context["errors"].append(
                    f"{name}: a folder with this name already exists"
                )
                continue

            existing = file_names.get(key)
            if self.copy_file_over(
                path, remote_dir, existing, context, inside_new
            ):
                file_names[key] = existing or name

    def copy_file_over(
        self, path, remote_dir, existing, context, inside_new
    ):
        name = os.path.basename(path)
        context["progress"]["step"](path)
        image_path = remote_dir.rstrip("/") + "/" + (existing or name)
        backup_path = None

        if existing:
            try:
                if context["backup"] is None:
                    context["backup"] = tempfile.TemporaryDirectory(
                        prefix="fat32-file-undo-"
                    )
                context["backup_count"] += 1
                backup_dir = os.path.join(
                    context["backup"].name, str(context["backup_count"])
                )
                os.makedirs(backup_dir, exist_ok=True)
                backup_path = os.path.join(backup_dir, existing)
                backup_error = self.backup_image_file(
                    image_path, backup_path
                )
            except OSError as exc:
                backup_error = str(exc)

            if backup_error:
                context["errors"].append(
                    f"{name}: could not back up the existing file: "
                    f"{backup_error}"
                )
                return False

        destination = self.directory_argument(remote_dir)
        if not destination.endswith("/"):
            destination += "/"
        result = self.run_mtools("mcopy", "-o", path, destination)

        step = (
            {
                "kind": "restore_file",
                "path": image_path,
                "backup_path": backup_path
            }
            if backup_path
            else {"kind": "delete_file", "path": image_path}
        )

        if result.returncode != 0:
            failure = f"{name}: {self.error_text(result)}"
            rollback_error = self.apply_undo_step(step)
            if rollback_error:
                context["steps"].append(step)
                failure += f"\nRollback failed: {rollback_error}"
            context["errors"].append(failure)
            return False

        # Files inside a newly created folder are removed with the folder.
        if backup_path or not inside_new:
            context["steps"].append(step)
        context["count"] += 1
        return True

    def delete_selected(self):
        if not self.image_ready():
            return

        base = self.folder.rstrip("/")
        items = [
            ("directory", name, base + "/" + name)
            for name in (
                self.folders.get(index)
                for index in self.folders.curselection()
            )
            if name != ".."
        ] + [
            ("file", name, base + "/" + name)
            for name in (
                self.files.get(index)
                for index in self.files.curselection()
            )
        ]

        if not items:
            messagebox.showinfo(
                "Delete",
                "Select one or more files or folders first.",
                parent=self.root
            )
            return

        listed = "\n".join(
            f"• {target}"
            + (" (folder and contents)" if kind == "directory" else "")
            for kind, name, target in items[:10]
        )
        if len(items) > 10:
            listed += f"\n…and {len(items) - 10} more"

        if not messagebox.askyesno(
            "Confirm Deletion",
            f"Delete {len(items)} selected item(s)?\n\n{listed}\n\n"
            "This deletion can be undone once.",
            icon="warning",
            parent=self.root
        ):
            return

        backup = tempfile.TemporaryDirectory(prefix="fat32-delete-undo-")
        steps = []

        for index, (kind, name, target) in enumerate(items):
            backup_dir = os.path.join(backup.name, str(index))
            local_backup = os.path.join(backup_dir, name)
            try:
                os.makedirs(backup_dir, exist_ok=True)
                backup_error = (
                    self.backup_folder_contents(target, local_backup)
                    if kind == "directory"
                    else self.backup_image_file(target, local_backup)
                )
            except OSError as exc:
                backup_error = str(exc)

            if backup_error:
                backup.cleanup()
                messagebox.showerror(
                    "Cannot prepare undo",
                    f"Could not back up '{target}':\n{backup_error}",
                    parent=self.root
                )
                return

            steps.append({
                "kind": (
                    "restore_folder" if kind == "directory"
                    else "restore_file"
                ),
                "path": target,
                "backup_path": local_backup
            })

        undo_steps = []
        errors = []

        for (kind, name, target), step in zip(items, steps):
            result = self.run_mtools(
                "mdeltree" if kind == "directory" else "mdel",
                self.image_path_argument(target)
            )
            if result.returncode == 0:
                undo_steps.append(step)
                continue

            error = self.error_text(result)
            restore_error = self.apply_undo_step(step)
            if restore_error:
                undo_steps.append(step)
                error += f"\nCould not restore: {restore_error}"
            errors.append(f"{target}: {error}")

        self.refresh()
        if undo_steps:
            self.record_undo(
                f"Deleted {len(undo_steps)} item(s)", undo_steps, backup
            )
        else:
            backup.cleanup()

        if errors:
            messagebox.showwarning(
                "Some Items Could Not Be Deleted",
                "\n".join(errors[:10]),
                parent=self.root
            )
