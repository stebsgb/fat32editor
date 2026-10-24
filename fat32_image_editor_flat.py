import os
import subprocess
import sys
import tempfile
import tkinter as tk
import uuid
from tkinter import ttk, filedialog, messagebox, simpledialog


def is_dark_mode():
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.stdout.strip().lower() == "dark"


# Tk's folder dialog picks one folder only; this allows several.
CHOOSE_FOLDERS_SCRIPT = """
set chosen to choose folder with prompt "Choose folders to add" with multiple selections allowed
set output to ""
repeat with item_ in chosen
    set output to output & POSIX path of item_ & linefeed
end repeat
return output
"""

DEFAULT_IMAGE = os.path.expanduser(
    "~/.jnext/sdcard/cspect-next-1gb-fixed.img"
)
PARTITION_OFFSET = 32256
if getattr(sys, "frozen", False):
    MTOOLS = os.path.join(sys._MEIPASS, "mtools")
else:
    MTOOLS = "/opt/homebrew/bin"
IMAGE_PREFERENCE = os.path.join(
    os.path.expanduser("~"),
    "Library",
    "Application Support",
    "CSpect Next FAT32 Image Editor",
    "last-image.txt"
)


class FAT32Editor:
    def __init__(self, root):
        self.root = root
        self.root.title("FAT32 Image Editor")
        self.root.geometry("1000x650")
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

        self.folders = tk.Listbox(
            left, width=27, height=22, exportselection=False,
            selectmode=tk.EXTENDED,
            **self.list_colors
        )
        self.folders.pack(fill="both", expand=True)
        self.folders.bind("<Double-Button-1>", self.open_folder)

        folder_buttons = ttk.Frame(
            left, style="FolderPanel.TFrame"
        )
        folder_buttons.pack(fill="x", pady=(6, 0))

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
            height=22,
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
        file_buttons.pack(fill="x", pady=(6, 0))

        ttk.Button(
            file_buttons, text="✎ Rename File…",
            command=self.rename_file
        ).pack(side="left")

        buttons = ttk.Frame(
            root,
            padding=(10, 8, 10, 10),
            style="ActionBar.TFrame"
        )
        buttons.pack(fill="x")

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
        self.status.pack(fill="x")

        self.image = self.load_last_image()
        self.update_image_label()
        self.refresh()
        if not os.path.isfile(self.image):
            self.root.update()
            self.root.after(300, self.choose_image)
    # Disk image helpers

    def image_arg(self):
        return f"{self.image}@@{PARTITION_OFFSET}"

    def run_mtools(self, command, *args):
        executable = os.path.join(MTOOLS, command)

        if not os.path.isfile(executable):
            return subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr=f"Cannot find {executable}. Check MTOOLS."
            )

        try:
            return subprocess.run(
                [executable, "-i", self.image_arg(), *args],
                capture_output=True,
                text=True,
                timeout=120
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr=str(exc)
            )

    @staticmethod
    def image_path_argument(path):
        if not path.startswith("/"):
            path = "/" + path
        return "::" + path

    @staticmethod
    def parent_image_path(path):
        return path.rsplit("/", 1)[0] or "/"

    def list_image_directory(self, path):
        result = self.run_mtools(
            "mdir", "-a", "-b", self.directory_argument(path)
        )
        if result.returncode != 0:
            return None, None, self.error_text(result)

        directories, files = self.get_entries(result.stdout)
        return directories, files, None

    def find_image_entry(self, parent, name, entry_type):
        directories, files, error = self.list_image_directory(parent)
        if error:
            return None, error

        names = directories if entry_type == "directory" else files
        match = next(
            (entry for entry in names if entry.casefold() == name.casefold()),
            None
        )
        return match, None

    def rename_image_entry(self, source, destination):
        source_name = source.rsplit("/", 1)[-1]
        destination_name = destination.rsplit("/", 1)[-1]
        source_argument = self.image_path_argument(source)
        destination_argument = self.image_path_argument(destination)

        if source_name.casefold() != destination_name.casefold():
            return self.run_mtools(
                "mren", source_argument, destination_argument
            )

        parent = self.parent_image_path(source)
        directories, files, error = self.list_image_directory(parent)
        if error:
            return subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr=error
            )

        is_directory = any(
            name.casefold() == source_name.casefold()
            for name in directories
        )
        existing_names = directories + files
        while True:
            temporary_name = f"F32REN{uuid.uuid4().hex}"
            if not any(
                name.casefold() == temporary_name.casefold()
                for name in existing_names
            ):
                break

        temporary_path = parent.rstrip("/") + "/" + temporary_name
        temporary_argument = self.image_path_argument(temporary_path)
        result = self.run_mtools(
            "mren", source_argument, temporary_argument
        )
        if result.returncode != 0:
            return result

        result = self.run_mtools(
            "mren", temporary_argument, destination_argument
        )
        if result.returncode == 0:
            if self.image_name_listed(parent, destination_name):
                return result

            # mren keeps the old case flags of all-lower/all-upper names,
            # so move the entry back to its temporary name and recreate it.
            result = self.run_mtools(
                "mren", destination_argument, temporary_argument
            )
            if result.returncode == 0:
                error = self.recreate_image_entry(
                    temporary_path, destination, is_directory
                )
                if not error:
                    return subprocess.CompletedProcess(
                        args=[], returncode=0, stdout="", stderr=""
                    )
                result = subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr=error
                )

        rollback = self.run_mtools(
            "mren", temporary_argument, source_argument
        )
        if rollback.returncode != 0:
            return subprocess.CompletedProcess(
                args=result.args,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=(
                    f"{self.error_text(result)} "
                    "The temporary name could not be rolled back: "
                    f"{self.error_text(rollback)}"
                )
            )

        return result

    def image_name_listed(self, parent, name):
        directories, files, error = self.list_image_directory(parent)
        return not error and name in directories + files

    def recreate_image_entry(self, source, destination, is_directory):
        """Copy an entry out and back in under an exactly-cased name."""
        parent = self.parent_image_path(destination)
        destination_name = destination.rsplit("/", 1)[-1]
        parent_argument = self.directory_argument(parent)
        if not parent_argument.endswith("/"):
            parent_argument += "/"

        try:
            with tempfile.TemporaryDirectory(
                prefix="fat32-rename-"
            ) as work:
                staged = os.path.join(work, "out")
                renamed = os.path.join(work, "in")
                os.makedirs(staged)
                os.makedirs(renamed)
                local = os.path.join(renamed, destination_name)

                if is_directory:
                    result = self.run_mtools(
                        "mcopy", "-s", "-m",
                        self.image_path_argument(source), staged
                    )
                    copied = os.listdir(staged)
                    if result.returncode == 0 and len(copied) == 1:
                        os.rename(
                            os.path.join(staged, copied[0]), local
                        )
                else:
                    result = self.run_mtools(
                        "mcopy", "-m",
                        self.image_path_argument(source), local
                    )
                if result.returncode != 0:
                    return self.error_text(result)
                if not os.path.exists(local):
                    return "Could not copy the entry out of the image."

                result = self.run_mtools(
                    "mcopy", "-s", "-m", local, parent_argument
                )
                if result.returncode != 0 or not self.image_name_listed(
                    parent, destination_name
                ):
                    self.run_mtools(
                        "mdeltree" if is_directory else "mdel",
                        self.image_path_argument(destination)
                    )
                    return (
                        self.error_text(result)
                        if result.returncode != 0
                        else "The new name was not stored with the "
                             "requested letter case."
                    )
        except OSError as exc:
            return str(exc)

        cleanup = self.run_mtools(
            "mdeltree" if is_directory else "mdel",
            self.image_path_argument(source)
        )
        if cleanup.returncode != 0:
            return (
                "Renamed, but could not remove the temporary entry "
                f"'{source}': {self.error_text(cleanup)}"
            )
        return None

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

    def directory_argument(self, folder=None):
        folder = self.folder if folder is None else folder

        if not folder.startswith("/"):
            folder = "/" + folder

        return "::" + folder

    def image_ready(self):
        if not os.path.isfile(self.image):
            messagebox.showerror(
                "Image not found",
                "Choose a valid disk image before editing."
            )
            return False

        return True

    @staticmethod
    def error_text(result):
        return (
            result.stderr.strip()
            or result.stdout.strip()
            or "The operation failed."
        )

    @staticmethod
    def valid_name(name):
        invalid = '<>:"/\\|?*'

        return (
            bool(name)
            and name not in (".", "..")
            and not any(
                ord(char) < 32 or char in invalid
                for char in name
            )
            and not name.endswith((" ", "."))
    )

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

    # List directories and files

    def get_entries(self, output):
        directories = []
        files = []

        for entry in output.splitlines():
            is_directory = entry.endswith("/")
            name = entry.rstrip("/").rsplit("/", 1)[-1]

            if not name or name in (".", ".."):
                continue

            if is_directory:
                directories.append(name)
            else:
                files.append(name)

        return directories, files

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
            "mdir", "-a", "-b", self.directory_argument()
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

    # Navigation

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
# Create folders

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

    # Rename folders

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
            total += 1
            if os.path.isdir(path) and not os.path.islink(path):
                for _, dirs, files in os.walk(path):
                    total += len(dirs) + len(files)
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



    # Display operation results

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

    # Open the directory containing the disk image

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


if __name__ == "__main__":
    root = tk.Tk()
    app = FAT32Editor(root)
    root.mainloop()
