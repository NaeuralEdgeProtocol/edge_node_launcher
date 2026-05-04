import math

from PyQt5.QtCore import QSize, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QLabel


class LoadingIndicator(QLabel):
    """Small animated spinner used by loading dialogs and sidebar status panels."""

    def __init__(self, parent=None, size=40):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.setFixedSize(QSize(size, size))
        self._size = size
        self._color = QColor("#4CAF50")

    def start(self):
        """Start the loading animation."""
        self.show()
        self.timer.start(50)

    def stop(self):
        """Stop the loading animation."""
        self.timer.stop()
        self.hide()

    def rotate(self):
        """Rotate the spinner by 30 degrees."""
        self.angle = (self.angle + 30) % 360
        self.update()

    def setColor(self, color):
        """Set the color of the spinner."""
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        """Paint the spinning indicator."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = self.rect().center()
        radius = (min(self.width(), self.height()) - 4) / 2

        pen = QPen(self._color)
        pen.setWidth(3)
        painter.setPen(pen)

        for i in range(8):
            opacity = 1.0 - (i * 0.1)
            self._color.setAlphaF(opacity)
            pen.setColor(self._color)
            painter.setPen(pen)

            angle_rad = math.radians(self.angle + (i * 45))
            start_x = center.x() + (radius * 0.5 * math.cos(angle_rad))
            start_y = center.y() + (radius * 0.5 * math.sin(angle_rad))
            end_x = center.x() + (radius * math.cos(angle_rad))
            end_y = center.y() + (radius * math.sin(angle_rad))

            painter.drawLine(int(start_x), int(start_y), int(end_x), int(end_y))
