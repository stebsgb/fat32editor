"""User-triggered file operations and result reporting."""

from tkinter import messagebox, simpledialog


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
        if check.returncode == 0 and (
            old_name.casefold() != new_name.casefold()
        ):
            messagebox.showerror(
                "Name already exists",
                f"A file or folder named '{new_name}' already exists."
            )
            return

        result = self.rename_image_entry(old_path, new_path)
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
