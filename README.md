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

**Folders** (left panel)
- **New Folder…** creates a folder in the current location
- **Rename Folder…** renames the selected folder
- **Delete Folder** deletes the selected folder and its contents (with confirmation)

**Files** (right panel, multi-select supported)
- **Add Files…** copies one or more files from your Mac into the current folder. You can optionally enter a name to create a new destination folder first
- **Add Folder…** copies an entire folder from your Mac, including its contents, into the image
- **Rename File…** renames the selected file
- **Delete Selected File(s)** deletes the selected files (with confirmation)

**Undo**
- **Undo** reverts the most recent change (single level). Undo is cleared when you switch images

Names are checked for FAT32 validity, and existing names are never silently overwritten.

## Requirements

- macOS with Python 3.13 (Tkinter included)
- mtools: `brew install mtools`

## Download

Grab `FAT32-Image-Editor-macOS.zip` from the [Releases](https://github.com/stebsgb/fat32editor/releases) page, unzip it and drag **FAT32 Image Editor.app** into Applications.

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

- `fat32_editor/`: application package (window, file and folder operations, undo, mtools wrapper, preferences)
- `fat32_image_editor.py`, `fat32_image_editor_flat.py`: single-file variants
- `build_mac_app.sh`, `generate_app_icon.swift`: app bundle and icon build
