"""Application paths and disk image configuration."""

import os
import sys

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
