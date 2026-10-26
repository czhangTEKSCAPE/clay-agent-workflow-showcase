"""Locate the Clay CLI binary.

Shared by every script in this repo so the lookup logic lives in one place.
"""
import glob
import os
import shutil
import sys
from typing import Optional

PLUGIN_GLOB = "~/.claude/plugins/cache/clay-plugins/clay/*/bin/clay"


def plugin_clay() -> Optional[str]:
    """Newest plugin-pinned launcher (survives plugin updates), or None."""
    candidates = glob.glob(os.path.expanduser(PLUGIN_GLOB))
    return max(candidates, key=os.path.getmtime) if candidates else None


def find_clay() -> Optional[str]:
    """Resolve the Clay CLI: PATH first, then ~/.local/bin, then the plugin cache. None if not found."""
    found = shutil.which("clay")
    if found:
        return found
    local = os.path.expanduser("~/.local/bin/clay")
    if os.path.exists(local):
        return local
    return plugin_clay()


def require_clay() -> str:
    """Like find_clay, but exits with a clear message when the CLI is missing."""
    path = find_clay()
    if not path:
        sys.exit("clay CLI not found: install it and run `clay whoami`")
    return path
