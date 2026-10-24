import os
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

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

        style = ttk.Style(root)
        style.configure(
            "FolderPanel.TFrame",
            background="#eaf2f8"
        )
        style.configure(
            "FilePanel.TFrame",
            background="#f2f4f6"
        )
        style.configure(
            "ActionBar.TFrame",
            background="#e4ebf1"
        )
        style.configure(
            "FolderHeading.TLabel",
            background="#eaf2f8",
            foreground="#18344d",
            font=("TkDefaultFont", 10, "bold")
        )
        style.configure(
            "FileHeading.TLabel",
            background="#f2f4f6",
            foreground="#253747",
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
            left, width=27, height=22, exportselection=False
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

        ttk.Button(
            folder_buttons, text="− Delete Folder",
            command=self.delete_folder
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
            selectmode=tk.EXTENDED
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
            file_buttons, text="− Delete Selected File(s)",
            command=self.delete_file
        ).pack(side="left")

        ttk.Button(
            file_buttons, text="✎ Rename File…",
            command=self.rename_file
        ).pack(side="left", padx=(5, 0))

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
            buttons, text="＋ Add Files…", command=self.add_files
        ).pack(side="left", padx=5)

        ttk.Button(
            buttons, text="▣ Add Folder…", command=self.add_folder
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

            result = self.run_mtools(
                "mren",
                self.image_path_argument(source),
                self.image_path_argument(destination)
            )
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

    # Delete folders recursively

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

    # Add files to the current folder or a new folder

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
# Copy an entire local folder into the disk image

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

    # Delete files

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
