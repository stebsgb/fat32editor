# FAT32 Image Editor

A small Tkinter desktop app for browsing and editing files inside a FAT32 disk image (such as a CSpect / ZX Spectrum Next SD card image) without mounting it. It drives the [mtools](https://www.gnu.org/software/mtools/) utilities under the hood.

## Supported platform

- **macOS only** (Apple Silicon, with Homebrew at `/opt/homebrew`). The build script, app bundle, icon generation and preference storage all use macOS-specific tools and paths.

## Supported file type

- **Raw disk image files (`.img`)** containing a FAT32 partition.
- The partition is assumed to start at byte offset `32256` (sector 63), the classic MBR layout used by CSpect Next images.
- The default image is `~/.jnext/sdcard/cspect-next-1gb-fixed.img`. Use **Choose Image…** to open another `.img`; the last choice is remembered.

## Features

- Browse folders and files in the image
- Add files and whole folders
- Create, rename and delete folders and files
- Undo, refresh, and open the image's folder in Finder

## Requirements

- macOS with Python 3.13 (Tkinter included)
- mtools: `brew install mtools`

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
