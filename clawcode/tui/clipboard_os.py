"""OS clipboard bridge for terminal TUI (pyperclip + Windows ctypes fallback)."""

from __future__ import annotations

import sys
from typing import Final

CF_UNICODETEXT: Final[int] = 13
GMEM_MOVEABLE: Final[int] = 0x0002


def _win32_clipboard_read() -> str | None:
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    if not user32.OpenClipboard(None):
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _win32_clipboard_write(text: str) -> bool:
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        encoded = (text + "\0").encode("utf-16-le")
        size = len(encoded)
        hglobal = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not hglobal:
            return False
        ptr = kernel32.GlobalLock(hglobal)
        if not ptr:
            kernel32.GlobalFree(hglobal)
            return False
        try:
            ctypes.memmove(ptr, encoded, size)
        finally:
            kernel32.GlobalUnlock(hglobal)
        if not user32.SetClipboardData(CF_UNICODETEXT, hglobal):
            kernel32.GlobalFree(hglobal)
            return False
        return True
    finally:
        user32.CloseClipboard()


def clipboard_read_text() -> str | None:
    """Read OS clipboard text.

    Returns:
        Clipboard string, or None if the OS clipboard could not be read.
    """
    try:
        import pyperclip

        return pyperclip.paste()
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            return _win32_clipboard_read()
        except Exception:
            pass
    return None


def clipboard_write_text(text: str) -> bool:
    """Write text to the OS clipboard (best-effort).

    Returns:
        True if a write path reported success.
    """
    try:
        import pyperclip

        pyperclip.copy(text)
        return True
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            return _win32_clipboard_write(text)
        except Exception:
            pass
    return False
