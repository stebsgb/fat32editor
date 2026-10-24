"""User-triggered folder operations."""

import os
import subprocess
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog


class FolderOperationsMixin:
    def create_folder_at(self, parent, name):
        if not self.valid_name(name):
            messagebox.showerror(
                "Invalid folder name",
                "Enter a valid FAT32 folder name."
            )
            return False

        target = parent.rstrip("/") + "/" + name

        if not target.startswith("/"):
            target = "/" + target

        check = self.run_mtools("mdir", "::" + target)

        if check.returncode == 0:
            messagebox.showerror(
                "Folder already exists",
                f"The folder {target} already exists."
            )
            return False

        result = self.run_mtools("mmd", "::" + target)

        if result.returncode != 0:
            messagebox.showerror(
                "Cannot create folder",
                self.error_text(result)
            )
            return False

        return True

    def create_folder(self):
        if not self.image_ready():
            return

        name = simpledialog.askstring(
            "New Folder",
            f"Enter a folder name inside {self.folder}:",
            parent=self.root
        )

        if name is None:
            return

        name = name.strip()

        if self.create_folder_at(self.folder, name):
            self.refresh()
            target = self.folder.rstrip("/") + "/" + name
            self.record_undo(
                f"Created folder {name}",
                [{"kind": "delete_folder", "path": target}]
            )

    def rename_folder(self):
        if not self.image_ready():
            return

        selected = self.folders.curselection()

        if not selected:
            messagebox.showinfo(
                "Rename Folder",
                "Select a folder first."
            )
            return

        old_name = self.folders.get(selected[0])

        if old_name == "..":
            messagebox.showinfo(
                "Rename Folder",
                "Select a folder, not '..'."
            )
            return

        new_name = simpledialog.askstring(
            "Rename Folder",
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
                "Enter a valid folder name."
            )
            return

        if old_name == new_name:
            return

        old_path = (
            self.folder.rstrip("/") + "/" + old_name
        )
        new_path = (
            self.folder.rstrip("/") + "/" + new_name
        )

        check = self.run_mtools(
            "mdir", "::" + new_path
        )

        if check.returncode == 0:
            messagebox.showerror(
                "Name already exists",
                f"A folder named '{new_name}' already exists."
            )
            return

        result = self.run_mtools(
            "mren",
            "::" + old_path,
            "::" + new_path
        )

        if result.returncode != 0:
            messagebox.showerror(
                "Cannot rename folder",
                self.error_text(result)
            )
            return

        self.refresh()
        self.record_undo(
            f"Renamed folder {old_name} to {new_name}",
            [{
                "kind": "rename",
                "source": new_path,
                "destination": old_path,
                "entry_type": "directory"
            }]
        )

    def delete_folder(self):
        if not self.image_ready():
            return

        selected = self.folders.curselection()

        if not selected:
            messagebox.showinfo(
                "Delete Folder",
                "Select a folder first."
            )
            return

        name = self.folders.get(selected[0])

        if name == "..":
            messagebox.showinfo(
                "Delete Folder",
                "You cannot delete '..'."
            )
            return

        target = self.folder.rstrip("/") + "/" + name

        confirmed = messagebox.askyesno(
            "Confirm Folder Deletion",
            f"Delete '{target}' and ALL files and "
            "subfolders inside it?\n\n"
            "This deletion can be undone once.",
            icon="warning"
        )

        if not confirmed:
            return

        backup = tempfile.TemporaryDirectory(
            prefix="fat32-folder-undo-"
        )
        local_backup = os.path.join(backup.name, name)
        try:
            backup_error = self.backup_folder_contents(
                target, local_backup
            )
        except OSError as exc:
            backup.cleanup()
            messagebox.showerror(
                "Cannot prepare folder undo",
                str(exc)
            )
            return

        if backup_error:
            backup.cleanup()
            messagebox.showerror(
                "Cannot prepare folder undo",
                backup_error
            )
            return

        result = self.run_mtools(
            "mdeltree", self.image_path_argument(target)
        )

        if result.returncode != 0:
            restore_error = self.apply_undo_step({
                "kind": "restore_folder",
                "path": target,
                "backup_path": local_backup
            })
            backup.cleanup()
            error = self.error_text(result)
            if restore_error:
                error += f"\nCould not restore deleted data: {restore_error}"
            messagebox.showerror(
                "Cannot delete folder",
                error
            )
            return

        self.refresh()
        self.record_undo(
            f"Deleted folder {target}",
            [{
                "kind": "restore_folder",
                "path": target,
                "backup_path": local_backup
            }],
            backup
        )

    def add_folder(self):
        if not self.image_ready():
            return

        source = filedialog.askdirectory(
            title="Choose a folder to copy into the image"
        )

        if not source:
            return

        folder_name = os.path.basename(
            source.rstrip(os.sep)
        )

        if not self.valid_name(folder_name):
            messagebox.showerror(
                "Invalid folder name",
                "The source folder name is invalid for FAT32."
            )
            return

        target = (
            self.folder.rstrip("/") + "/" + folder_name
            if self.folder != "/"
            else "/" + folder_name
        )

        check = self.run_mtools("mdir", "::" + target)

        if check.returncode == 0:
            messagebox.showerror(
                "Folder already exists",
                f"{target} already exists in the image."
            )
            return

        result = self.run_mtools("mmd", "::" + target)

        if result.returncode != 0:
            messagebox.showerror(
                "Cannot create folder",
                self.error_text(result)
            )
            return

        errors = []
        count = 0

        for current, dirs, files in os.walk(source):
            dirs.sort()
            files.sort()

            relative = os.path.relpath(current, source)
            remote_dir = target

            if relative != ".":
                remote_dir += "/" + relative.replace(
                    os.sep, "/"
                )

            # Create subfolders, including empty folders.
            for dirname in dirs:
                child = remote_dir + "/" + dirname

                result = self.run_mtools(
                    "mmd", "::" + child
                )

                if result.returncode != 0:
                    errors.append(
                        f"Folder {child}: "
                        + self.error_text(result)
                    )

            # Copy files into their corresponding directories.
            for filename in files:
                local_path = os.path.join(
                    current, filename
                )

                result = self.run_mtools(
                    "mcopy",
                    "-o",
                    local_path,
                    "::" + remote_dir + "/"
                )

                if result.returncode != 0:
                    errors.append(
                        f"{local_path}: "
                        + self.error_text(result)
                    )
                else:
                    count += 1

        self.refresh()
        self.record_undo(
            f"Added folder {target}",
            [{"kind": "delete_folder", "path": target}]
        )
        self.show_result("Copy Folder", count, errors)

    def open_image_folder(self):
        if not os.path.isfile(self.image):
            messagebox.showerror(
                "Image not found",
                "Choose a valid disk image first."
            )
            return

        subprocess.run([
            "open",
            os.path.dirname(self.image) or "."
        ])
