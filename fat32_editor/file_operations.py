"""User-triggered file operations and result reporting."""

import os
import subprocess
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog


class FileOperationsMixin:
    def rename_file(self):
        if not self.image_ready():
            return

        selected = self.files.curselection()
        if not selected:
            messagebox.showinfo(
                "Rename File",
                "Select a file first."
            )
            return

        old_name = self.files.get(selected[0])
        new_name = simpledialog.askstring(
            "Rename File",
            f"New name for '{old_name}':",
            initialvalue=old_name,
            parent=self.root
        )
        if new_name is None:
            return

        new_name = new_name.strip()
        if not self.valid_name(new_name):
            messagebox.showerror(
                "Invalid name",
                "Enter a valid file name."
            )
            return
        if old_name == new_name:
            return

        old_path = self.folder.rstrip("/") + "/" + old_name
        new_path = self.folder.rstrip("/") + "/" + new_name
        check = self.run_mtools(
            "mdir", self.image_path_argument(new_path)
        )
        if check.returncode == 0:
            messagebox.showerror(
                "Name already exists",
                f"A file or folder named '{new_name}' already exists."
            )
            return

        result = self.run_mtools(
            "mren",
            self.image_path_argument(old_path),
            self.image_path_argument(new_path)
        )
        if result.returncode != 0:
            messagebox.showerror(
                "Cannot rename file",
                self.error_text(result)
            )
            return

        self.refresh()
        self.record_undo(
            f"Renamed file {old_name} to {new_name}",
            [{
                "kind": "rename",
                "source": new_path,
                "destination": old_path,
                "entry_type": "file"
            }]
        )

    def add_files(self):
        if not self.image_ready():
            return

        paths = filedialog.askopenfilenames(
            title="Choose files to add"
        )

        if not paths:
            return

        create_name = simpledialog.askstring(
            "Choose Destination",
            "Destination folder name:\n\n"
            f"Current folder: {self.folder}\n\n"
            "Leave blank to add files here, or enter a name "
            "to create a new folder here.",
            initialvalue="",
            parent=self.root
        )

        if create_name is None:
            return

        create_name = create_name.strip()
        destination_folder = self.folder
        undo_steps = []
        undo_backup = None

        if create_name:
            if not self.create_folder_at(
                self.folder, create_name
            ):
                return

            destination_folder = (
                "/" + create_name
                if self.folder == "/"
                else self.folder.rstrip("/") + "/" + create_name
            )
            undo_steps.append({
                "kind": "delete_folder",
                "path": destination_folder
            })

        destination = self.directory_argument(
            destination_folder
        )

        errors = []
        count = 0

        for index, path in enumerate(paths):
            file_name = os.path.basename(path)
            directories, files, listing_error = (
                self.list_image_directory(destination_folder)
            )
            if listing_error:
                errors.append(f"{file_name}: {listing_error}")
                continue

            existing_name = next(
                (
                    existing for existing in files
                    if existing.casefold() == file_name.casefold()
                ),
                None
            )
            backup_path = None
            image_path = (
                destination_folder.rstrip("/") + "/" +
                (existing_name or file_name)
            )
            if existing_name:
                try:
                    if undo_backup is None:
                        undo_backup = tempfile.TemporaryDirectory(
                            prefix="fat32-file-undo-"
                        )
                    backup_dir = os.path.join(
                        undo_backup.name, str(index)
                    )
                    os.makedirs(backup_dir, exist_ok=True)
                    backup_path = os.path.join(
                        backup_dir, existing_name
                    )
                    backup_error = self.backup_image_file(
                        image_path, backup_path
                    )
                except OSError as exc:
                    errors.append(
                        f"{file_name}: could not back up the "
                        f"existing file: {exc}"
                    )
                    continue

                if backup_error:
                    errors.append(
                        f"{file_name}: could not back up the "
                        f"existing file: {backup_error}"
                    )
                    continue

            result = self.run_mtools(
                "mcopy", "-o", path, destination
            )

            if result.returncode != 0:
                failure = (
                    os.path.basename(path)
                    + ": "
                    + self.error_text(result)
                )
                undo_step = (
                    {
                        "kind": "restore_file",
                        "path": image_path,
                        "backup_path": backup_path
                    }
                    if backup_path
                    else {"kind": "delete_file", "path": image_path}
                )
                rollback_error = self.apply_undo_step(undo_step)
                if rollback_error:
                    undo_steps.append(undo_step)
                    failure += f"\nRollback failed: {rollback_error}"
                errors.append(failure)
            else:
                undo_steps.append(
                    {
                        "kind": "restore_file",
                        "path": image_path,
                        "backup_path": backup_path
                    }
                    if backup_path
                    else {"kind": "delete_file", "path": image_path}
                )
                count += 1

        self.refresh()
        self.record_undo(
            "Added files",
            undo_steps,
            undo_backup
        )
        self.show_result("Add Files", count, errors)

    def delete_file(self):
        if not self.image_ready():
            return

        selected = self.files.curselection()
        if not selected:
            messagebox.showinfo(
                "Delete File",
                "Select one or more files first."
            )
            return

        names = [self.files.get(index) for index in selected]
        targets = [
            self.folder.rstrip("/") + "/" + name
            for name in names
        ]
        listed_targets = "\n".join(
            f"• {target}" for target in targets[:10]
        )
        if len(targets) > 10:
            listed_targets += f"\n…and {len(targets) - 10} more"

        confirmed = messagebox.askyesno(
            "Confirm File Deletion",
            f"Delete {len(targets)} selected file(s)?\n\n"
            f"{listed_targets}\n\n"
            "This deletion can be undone once.",
            icon="warning",
            parent=self.root
        )
        if not confirmed:
            return

        backup = tempfile.TemporaryDirectory(prefix="fat32-file-undo-")
        undo_steps = []
        errors = []
        deleted_count = 0

        for index, target in enumerate(targets):
            name = names[index]
            backup_dir = os.path.join(backup.name, str(index))
            local_backup = os.path.join(backup_dir, name)
            try:
                os.makedirs(backup_dir, exist_ok=True)
                backup_error = self.backup_image_file(
                    target, local_backup
                )
            except OSError as exc:
                backup.cleanup()
                messagebox.showerror(
                    "Cannot prepare file undo",
                    str(exc),
                    parent=self.root
                )
                return

            if backup_error:
                backup.cleanup()
                messagebox.showerror(
                    "Cannot prepare file undo",
                    f"Could not back up '{target}':\n{backup_error}",
                    parent=self.root
                )
                return

        for index, target in enumerate(targets):
            step = {
                "kind": "restore_file",
                "path": target,
                "backup_path": os.path.join(
                    backup.name, str(index), names[index]
                )
            }
            result = self.run_mtools(
                "mdel", self.image_path_argument(target)
            )
            if result.returncode == 0:
                undo_steps.append(step)
                deleted_count += 1
                continue

            error = self.error_text(result)
            restore_error = self.apply_undo_step(step)
            if restore_error:
                undo_steps.append(step)
                error += f"\nCould not restore file: {restore_error}"
            errors.append(f"{target}: {error}")

        self.refresh()
        if undo_steps:
            self.record_undo(
                f"Deleted {deleted_count} file(s)",
                undo_steps,
                backup
            )
        else:
            backup.cleanup()

        if errors and undo_steps:
            messagebox.showwarning(
                "Some Files Could Not Be Deleted",
                f"Deleted {deleted_count} file(s). "
                "Some selections could not be deleted or restored."
                "\nUndo is available.\n\n"
                + "\n".join(errors[:10]),
                parent=self.root
            )
        elif errors:
            messagebox.showerror(
                "Cannot Delete Files",
                "\n".join(errors[:10]),
                parent=self.root
            )
            return

        if not errors:
            messagebox.showinfo(
                "Delete Files",
                f"Deleted {len(targets)} file(s). Undo is available.",
                parent=self.root
            )

    def show_result(self, title, count, errors):
        if errors:
            messagebox.showwarning(
                title,
                f"Successfully copied {count} file(s).\n\n"
                f"Errors ({len(errors)} total; up to 10 shown):\n"
                + "\n".join(errors[:10])
            )
        else:
            messagebox.showinfo(
                title,
                f"Successfully copied {count} file(s)."
            )
