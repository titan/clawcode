"""Draggable grip between chat area and right info/plan panel."""

from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widget import Widget


class RightPanelWidthDrag(Message):
    """Live width update while dragging (cells)."""

    def __init__(self, width: int) -> None:
        self.width = width
        super().__init__()


class RightPanelWidthCommit(Message):
    """Final width after mouse release; persist this."""

    def __init__(self, width: int) -> None:
        self.width = width
        super().__init__()


class RightPanelGrip(Widget):
    """One-column hit target; drag horizontally to resize the right panel."""

    DEFAULT_CSS = """
    RightPanelGrip {
        width: 1;
        height: 1fr;
        min-height: 1;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._dragging = False
        self._start_screen_x: int = 0
        self._start_width: int = 36

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button != 1:
            return
        try:
            rpc = self.screen.query_one("#right_panel_container")
            self._start_width = int(rpc.size.width)
        except Exception:
            self._start_width = 36
        self._start_screen_x = int(event.screen_x)
        self._dragging = True
        self.capture_mouse()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._dragging:
            return
        dx = self._start_screen_x - int(event.screen_x)
        new_w = self._start_width + dx
        self.post_message(RightPanelWidthDrag(new_w))

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self.release_mouse()
        try:
            rpc = self.screen.query_one("#right_panel_container")
            final_w = int(rpc.size.width)
        except Exception:
            final_w = self._start_width
        self.post_message(RightPanelWidthCommit(final_w))


__all__ = [
    "RightPanelGrip",
    "RightPanelWidthCommit",
    "RightPanelWidthDrag",
]
