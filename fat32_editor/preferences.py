"""Remember and select the active disk image."""

import os
from tkinter import filedialog, messagebox

from .config import DEFAULT_IMAGE, IMAGE_PREFERENCE

class PreferencesMixin:
    def update_image_label(self):
        self.image_label.config(text=f"Image: {self.image}")

    def load_last_image(self):
        try:
            with open(IMAGE_PREFERENCE, encoding="utf-8") as preference:
                path = preference.read().strip()
        except FileNotFoundError:
            return DEFAULT_IMAGE
        except OSError as exc:
            messagebox.showwarning(
                "Could not load saved image",
                f"The saved image preference could not be read:\n{exc}",
                parent=self.root
            )
            return DEFAULT_IMAGE

        return path if path and os.path.isfile(path) else DEFAULT_IMAGE

    def remember_image(self, path):
        try:
            os.makedirs(os.path.dirname(IMAGE_PREFERENCE), exist_ok=True)
            with open(IMAGE_PREFERENCE, "w", encoding="utf-8") as preference:
                preference.write(path)
        except OSError as exc:
            messagebox.showwarning(
                "Could not save image preference",
                f"The selected image will be used for this session, "
                f"but could not be saved as the default:\n{exc}",
                parent=self.root
            )

    def choose_image(self):
        initial_dir = os.path.dirname(self.image)
        if not os.path.isdir(initial_dir):
            initial_dir = os.path.expanduser("~")

        path = filedialog.askopenfilename(
            parent=self.root,
            title="Select FAT32 disk image",
            initialdir=initial_dir,
            initialfile=os.path.basename(self.image),
            filetypes=[
                ("Disk images", "*.img"),
                ("All files", "*.*")
            ]
        )

        if path:
            if path != self.image:
                self.clear_undo()
            self.image = path
            self.remember_image(path)
            self.folder = "/"
            self.update_image_label()
            self.refresh()
