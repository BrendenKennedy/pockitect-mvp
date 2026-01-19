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
    """Chat message bubble with modern styling."""
    
    def __init__(self, text: str, role: str = "assistant", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("role", role)
        self.setMinimumWidth(100)
        self.setMaximumWidth(800)  # Max width for readability
        
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._label.setStyleSheet("""
            QLabel {
                background: transparent;
                color: #eaeaea;
                font-size: 14px;
                line-height: 1.5;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        layout.addWidget(self._label)
        
        # Apply ChatGPT-style rounded corners
        self.setStyleSheet("""
            QFrame[role="user"] {
                background-color: #0f3460;
                border: 1px solid #1a4a7a;
                border-radius: 12px;
            }
            QFrame[role="assistant"] {
                background-color: #16213e;
                border: 1px solid #0f3460;
                border-radius: 12px;
            }
        """)

    def set_text(self, text: str) -> None:
        """Update message text."""
        self._label.setText(text)
        
    def text(self) -> str:
        """Get current message text."""
        return self._label.text()


class ToolCallBadge(QFrame):
    """Badge showing tool call status."""
    
    def __init__(self, tool_name: str, status: str = "running", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "tool")
        self._label = QLabel(self._format_text(tool_name, status))
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._label.setStyleSheet("""
            QLabel {
                background: transparent;
                color: #a0a0a0;
                font-size: 12px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self._label)
        
        self.setStyleSheet("""
            QFrame[role="tool"] {
                background-color: #0f3460;
                border: 1px solid #1a4a7a;
                border-radius: 16px;
            }
        """)

    def update_status(self, tool_name: str, status: str) -> None:
        """Update tool status."""
        self._label.setText(self._format_text(tool_name, status))
        if status == "done":
            self.setStyleSheet("""
                QFrame[role="tool"] {
                    background-color: #1a4a7a;
                    border: 1px solid #0f3460;
                    border-radius: 16px;
                }
            """)

    @staticmethod
    def _format_text(tool_name: str, status: str) -> str:
        """Format tool status text."""
        if status == "running":
            return f"🔧 {tool_name}..."
        return f"✓ {tool_name}"


class TypingIndicator(QWidget):
    """Animated typing indicator."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "typing")
        self._label = QLabel("...")
        self._label.setStyleSheet("""
            QLabel {
                background: transparent;
                color: #888;
                font-size: 24px;
                font-weight: bold;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self._label)
        
        self.setStyleSheet("""
            QWidget[role="typing"] {
                background-color: #16213e;
                border: 1px solid #0f3460;
                border-radius: 12px;
            }
        """)

        self._dots = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        """Start typing animation."""
        self._dots = 0
        self._timer.start(400)
        self.show()

    def stop(self) -> None:
        """Stop typing animation."""
        self._timer.stop()
        self._label.setText("...")
        self.hide()

    def _tick(self) -> None:
        """Update animation frame."""
        self._dots = (self._dots + 1) % 4
        self._label.setText("." * self._dots + " " * (3 - self._dots))
