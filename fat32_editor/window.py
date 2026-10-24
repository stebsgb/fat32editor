"""Tkinter window and application entry point."""

import os
import subprocess
import tkinter as tk
from tkinter import ttk

from .batch_operations import BatchOperationsMixin
from .config import DEFAULT_IMAGE
from .file_operations import FileOperationsMixin
from .folder_operations import FolderOperationsMixin
from .mtools import MtoolsMixin
from .navigation import NavigationMixin
from .preferences import PreferencesMixin
from .undo import UndoMixin


def is_dark_mode():
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.stdout.strip().lower() == "dark"


class FAT32Editor(
    UndoMixin, PreferencesMixin, NavigationMixin,
    BatchOperationsMixin, FileOperationsMixin, FolderOperationsMixin, MtoolsMixin
):
    def __init__(self, root):
        self.root = root
        self.root.title("FAT32 Image Editor")
        self.root.geometry("1000x650")
        self.root.minsize(780, 320)
        self.image = DEFAULT_IMAGE
        self.folder = "/"
        self.undo_action = None
        self.undo_tempdir = None

        dark = is_dark_mode()
        folder_bg, file_bg, bar_bg, folder_fg, file_fg, list_bg, list_fg = (
            ("#2b3440", "#262c33", "#20262c", "#e6edf3", "#e6edf3",
             "#1e2329", "#e6edf3")
            if dark else
            ("#eaf2f8", "#f2f4f6", "#e4ebf1", "#18344d", "#253747",
             "#ffffff", "#000000")
        )
        self.list_colors = {
            "background": list_bg,
            "foreground": list_fg,
            "selectbackground": "#3b6ea5" if dark else "#c5dcf2",
            "selectforeground": "#ffffff" if dark else "#000000",
            "highlightthickness": 0
        }

        style = ttk.Style(root)
        style.configure("FolderPanel.TFrame", background=folder_bg)
        style.configure("FilePanel.TFrame", background=file_bg)
        style.configure("ActionBar.TFrame", background=bar_bg)
        style.configure(
            "FolderHeading.TLabel",
            background=folder_bg,
            foreground=folder_fg,
            font=("TkDefaultFont", 10, "bold")
        )
        style.configure(
            "FileHeading.TLabel",
            background=file_bg,
            foreground=file_fg,
            font=("TkDefaultFont", 10, "bold")
        )

        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")

        self.image_label = ttk.Label(top, text="", wraplength=700)
        self.image_label.pack(side="left", fill="x", expand=True)

        ttk.Button(
            top, text="▣ Choose Image…", command=self.choose_image
        ).pack(side="right")

        main = ttk.Frame(root, padding=(10, 0, 10, 10))
        main.pack(fill="both", expand=True)

        left = ttk.Frame(
            main, padding=10, style="FolderPanel.TFrame"
        )
        left.pack(side="left", fill="both", padx=(0, 12))

        ttk.Label(
            left,
            text="Folders (double-click to open)",
            style="FolderHeading.TLabel"
        ).pack(anchor="w", pady=(0, 5))

        folder_frame = ttk.Frame(left, style="FolderPanel.TFrame")
        folder_frame.pack(fill="both", expand=True)

        self.folders = tk.Listbox(
            folder_frame, width=27, height=5, exportselection=False,
            selectmode=tk.EXTENDED, **self.list_colors
        )
        self.folders.pack(side="left", fill="both", expand=True)
        folder_scrollbar = ttk.Scrollbar(
            folder_frame, orient="vertical", command=self.folders.yview
        )
        folder_scrollbar.pack(side="right", fill="y")
        self.folders.config(yscrollcommand=folder_scrollbar.set)
        self.folders.bind("<Double-Button-1>", self.open_folder)

        folder_buttons = ttk.Frame(
            left, style="FolderPanel.TFrame"
        )
        folder_buttons.pack(
            fill="x", pady=(6, 0), side="bottom", before=folder_frame
        )

        ttk.Button(
            folder_buttons, text="＋ New Folder…",
            command=self.create_folder
        ).pack(fill="x", pady=2)

        ttk.Button(
            folder_buttons, text="✎ Rename Folder…",
            command=self.rename_folder
        ).pack(fill="x", pady=2)


        right = ttk.Frame(
            main, padding=10, style="FilePanel.TFrame"
        )
        right.pack(side="left", fill="both", expand=True)

        self.path_label = ttk.Label(
            right, text="Location: /", style="FileHeading.TLabel"
        )
        self.path_label.pack(anchor="w", pady=(0, 5))

        ttk.Label(
            right, text="Files", style="FileHeading.TLabel"
        ).pack(anchor="w")

        file_frame = ttk.Frame(right, style="FilePanel.TFrame")
        file_frame.pack(fill="both", expand=True)

        self.files = tk.Listbox(
            file_frame,
            height=5,
            exportselection=False,
            selectmode=tk.EXTENDED,
            **self.list_colors
        )
        self.files.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            file_frame, orient="vertical", command=self.files.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.files.config(yscrollcommand=scrollbar.set)

        file_buttons = ttk.Frame(right, style="FilePanel.TFrame")
        file_buttons.pack(
            fill="x", pady=(6, 0), side="bottom", before=file_frame
        )

        ttk.Button(
            file_buttons, text="✎ Rename File…",
            command=self.rename_file
        ).pack(side="left")

        buttons = ttk.Frame(
            root,
            padding=(10, 8, 10, 10),
            style="ActionBar.TFrame"
        )

        ttk.Button(
            buttons, text="↑ Up", command=self.go_up
        ).pack(side="left", padx=(0, 5))

        ttk.Button(
            buttons, text="＋ Add Files & Folders…",
            command=self.add_items
        ).pack(side="left", padx=5)

        ttk.Button(
            buttons, text="− Delete Selected",
            command=self.delete_selected
        ).pack(side="left", padx=5)

        ttk.Button(
            buttons, text="⟳ Refresh", command=self.refresh
        ).pack(side="left", padx=5)

        self.undo_button = ttk.Button(
            buttons, text="↶ Undo", command=self.undo, state=tk.DISABLED
        )
        self.undo_button.pack(side="left", padx=5)

        ttk.Button(
            buttons, text="▣ Open Image Folder",
            command=self.open_image_folder
        ).pack(side="right")

        self.status = ttk.Label(root, text="Ready", padding=10)
        self.status.pack(fill="x", side="bottom", before=main)
        buttons.pack(fill="x", side="bottom", before=main)

        self.image = self.load_last_image()
        self.update_image_label()
        self.refresh()
        if not os.path.isfile(self.image):
            self.root.update()
            self.root.after(300, self.choose_image)


def main():
    root = tk.Tk()
    FAT32Editor(root)
    root.mainloop()
