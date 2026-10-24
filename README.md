# FAT32 Image Editor

A small Tkinter desktop app for browsing and editing files inside a FAT32 disk image (such as a CSpect / ZX Spectrum Next SD card image) without mounting it. It drives the [mtools](https://www.gnu.org/software/mtools/) utilities under the hood.

## Supported platform

- **macOS only** (Apple Silicon, with Homebrew at `/opt/homebrew`). The build script, app bundle, icon generation and preference storage all use macOS-specific tools and paths.

## Supported file type

- **Raw disk image files (`.img`)** containing a FAT32 partition.
- The partition is assumed to start at byte offset `32256` (sector 63), the classic MBR layout used by CSpect Next images.
- The default image is `~/.jnext/sdcard/cspect-next-1gb-fixed.img`. Use **Choose Image…** to open another `.img`; the last choice is remembered.

## Features

**Image**
- **Choose Image…** selects the `.img` file to edit (the choice is remembered; prompted if the default is missing)
- **Open Image Folder** reveals the image's folder in Finder

**Navigation**
- Double-click a folder in the left-hand **Folders** list to open it
- **Up** moves to the parent folder; the current location is shown above the file list
- **Refresh** reloads the listing from the image

**Folders** (left panel, multi-select supported for deleting)
- **New Folder…** creates a folder in the current location
- **Rename Folder…** renames the selected folder (one at a time)

**Files** (right panel, multi-select supported)
- **Rename File…** renames the selected file

**Action bar**
- **Add Files & Folders…** opens a list where you use **＋ Files…** and **＋ Folders…** as often as you like (each allows multi-select), then press **Add**. A progress bar shows each item as it is copied. Items are merged into the current folder: existing folders are merged into (matched case-insensitively), and existing files are always overwritten
- **Delete Selected** deletes every selected file and folder (folders with their contents) after a single confirmation. Hidden folders are listed too

**Undo**
- **Undo** reverts the most recent change (single level), including restoring overwritten files and deleted items. Undo is cleared when you switch images

Names are checked for FAT32 validity. A file and a folder with the same name are never mixed up (such clashes are reported and skipped). File and folder renames can change letter case only (e.g. `readme.txt` to `README.TXT`) without being mistaken for an existing destination.

The interface follows the macOS light/dark appearance.

## Requirements

- macOS with Python 3.13 (Tkinter included)
- mtools: `brew install mtools`

## Download

Grab `FAT32-Image-Editor-macOS-<version>.zip` from the [Releases](https://github.com/stebsgb/fat32editor/releases) page, unzip it and drag **FAT32 Image Editor.app** into Applications.

The app is not notarized by Apple (that needs a paid Apple Developer account), so macOS will block the first launch. Either:

- Right-click (or Control-click) the app, choose **Open**, then click **Open** again; or
- Open **System Settings → Privacy & Security**, scroll down and click **Open Anyway**; or
- Remove the quarantine flag in Terminal:

  ```bash
  xattr -dr com.apple.quarantine "/Applications/FAT32 Image Editor.app"
  ```

The release build is for Apple Silicon Macs.

## Run from source

```bash
python3 -m fat32_editor
```

## Build the macOS app

```bash
python3 -m pip install -r requirements-build.txt
./build_mac_app.sh
```

This bundles Python, Tk and the required mtools binaries (`mdir`, `mcopy`, `mdel`, `mdeltree`, `mmd`, `mren`) into `~/Applications/FAT32 Image Editor.app`.

## Project layout

- `fat32_editor/`: application package (window, file and folder operations, combined add/delete in `batch_operations.py`, undo, mtools wrapper, preferences)
- `fat32_image_editor.py`: small launcher for the package (also the app build's entry point)
- `fat32_image_editor_flat.py`: legacy standalone single-file version, kept in sync with the package
- `build_mac_app.sh`, `generate_app_icon.swift`: app bundle and icon build
