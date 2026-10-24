"""User-triggered folder operations."""

import os
import subprocess
from tkinter import messagebox, simpledialog


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

        if check.returncode == 0 and (
            old_name.casefold() != new_name.casefold()
        ):
            messagebox.showerror(
                "Name already exists",
                f"A folder named '{new_name}' already exists."
            )
            return

        result = self.rename_image_entry(old_path, new_path)

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
