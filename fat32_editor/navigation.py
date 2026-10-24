"""Directory listing and navigation actions."""

import os
import tkinter as tk

class NavigationMixin:
    def refresh(self):
        self.folders.delete(0, tk.END)
        self.files.delete(0, tk.END)

        self.path_label.config(
            text=f"Location: {self.folder}"
        )

        if not os.path.isfile(self.image):
            self.status.config(
                text="Image not found. Click Choose Image… to select it."
            )
            return

        result = self.run_mtools(
            "mdir", "-b", self.directory_argument()
        )

        if result.returncode != 0:
            self.status.config(
                text="Could not read directory: "
                + self.error_text(result)
            )
            return

        directories, files = self.get_entries(result.stdout)

        if self.folder != "/":
            self.folders.insert(tk.END, "..")

        for name in directories:
            self.folders.insert(tk.END, name)

        for name in files:
            self.files.insert(tk.END, name)

        self.status.config(
            text=f"{len(directories)} folder(s), "
                 f"{len(files)} file(s)."
        )

    def open_folder(self, event=None):
        selected = self.folders.curselection()

        if not selected:
            return

        name = self.folders.get(selected[0])

        if name == "..":
            self.go_up()
            return

        if self.folder == "/":
            self.folder = "/" + name
        else:
            self.folder = (
                self.folder.rstrip("/") + "/" + name
            )

        self.refresh()

    def go_up(self):
        if self.folder != "/":
            self.folder = (
                self.folder.rsplit("/", 1)[0] or "/"
            )
            self.refresh()
