#####################################################################################
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

#   © 2024 Emmanuel Gyimah Annor. All rights reserved.
#####################################################################################

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel


class MarqueeLabel(QLabel):
    """
    An auto-scrolling QLabel for handling long text strings.

    Used primarily in menu actions or file lists where full filenames
    exceed available space. Scrolling activates on mouse hover and
    resets to the original state when the mouse leaves the widget area.
    """

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.full_text = text
        self.offset = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.scroll_text)
        self.setText(text)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def enterEvent(self, event):
        """Initiates the scrolling animation when the mouse enters the widget."""
        self.timer.start(100)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Stops the animation and resets text position when mouse leaves."""
        self.timer.stop()
        self.offset = 0
        self.setText(self.full_text)
        super().leaveEvent(event)

    def scroll_text(self):
        """Circularly shifts the text string to create a marquee effect."""
        if len(self.full_text) <= 30:
            return
        self.offset = (self.offset + 1) % len(self.full_text)
        text = self.full_text[self.offset:] + "   " + self.full_text[:self.offset]
        self.setText(text)
