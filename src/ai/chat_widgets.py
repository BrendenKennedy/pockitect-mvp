"""Chat UI widgets for the AI Assistant tab."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout, QVBoxLayout, QWidget


@dataclass
class ChatMessage:
    role: str  # "user", "assistant", "tool"
    text: str
    timestamp: datetime
    tool_name: Optional[str] = None


class MessageBubble(QFrame):
    def __init__(self, text: str, role: str = "assistant", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("role", role)
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self._label)

    def set_text(self, text: str) -> None:
        self._label.setText(text)


class ToolCallBadge(QFrame):
    def __init__(self, tool_name: str, status: str = "running", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "tool")
        self._label = QLabel(self._format_text(tool_name, status))
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.addWidget(self._label)

    def update_status(self, tool_name: str, status: str) -> None:
        self._label.setText(self._format_text(tool_name, status))

    @staticmethod
    def _format_text(tool_name: str, status: str) -> str:
        status_text = "running" if status == "running" else "done"
        return f"Tool: {tool_name} ({status_text})"


class TypingIndicator(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "typing")
        self._label = QLabel("...")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.addWidget(self._label)

        self._dots = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._dots = 0
        self._timer.start(450)

    def stop(self) -> None:
        self._timer.stop()
        self._label.setText("...")

    def _tick(self) -> None:
        self._dots = (self._dots + 1) % 4
        self._label.setText("." * max(1, self._dots))
