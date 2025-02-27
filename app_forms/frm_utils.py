import sys
import base64
import traceback
from datetime import datetime
import random

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QAbstractButton, QCheckBox, QRadioButton
from PyQt5.QtCore import Qt, QRect, QPropertyAnimation, QTimer
from PyQt5.QtGui import QFont, QPixmap, QIcon
from PyQt5.QtGui import QPainter, QColor, QBrush
from pyqtgraph import AxisItem

# List of adjectives and nouns for generating container names
ADJECTIVES = [
    "swift", "bright", "calm", "wise", "bold", 
    "quick", "keen", "brave", "agile", "noble"
]

NOUNS = [
    "falcon", "tiger", "eagle", "wolf", "bear",
    "hawk", "lion", "puma", "lynx", "fox"
]

def generate_container_name(prefix="edge_node_container_"):
    """Generate a random but readable container name"""
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    return f"{prefix}{adj}_{noun}"

def get_volume_name(container_name):
    """Get volume name from container name by replacing container with volume"""
    return container_name.replace("container", "volume")

def get_icon_from_base64(base64_str):
  icon_data = base64.b64decode(base64_str)
  pixmap = QPixmap()
  pixmap.loadFromData(icon_data)
  return QIcon(pixmap)

class DateAxisItem_OLD(AxisItem):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.setLabel(text='Time')
    return

  def tickStrings(self, values, scale, spacing):
    ticks = [datetime.fromtimestamp(value).strftime("%H:%M:%S") for value in values]      
    return ticks


class DateAxisItem(AxisItem):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.setLabel(text='Time')  # Custom label without scientific notation
    self.timestamps = None  # Store actual timestamps from the data
    self.parent = None  # Store the parent widget for debugging
    return

  def setTimestamps(self, timestamps, parent):
    """Store the actual timestamps from the data to map axis values."""
    self.parent = parent
    if isinstance(timestamps[0], str):
      self.timestamps = [datetime.fromisoformat(ts).timestamp() for ts in timestamps]
    else:
      self.timestamps = timestamps
    return

  def tickStrings(self, values, scale, spacing):
    if not self.timestamps or len(self.timestamps) == 0:
      return [""] * len(values)  # Return empty labels if no timestamps available

    # Get the range of actual timestamps
    start_time = self.timestamps[0]
    end_time = self.timestamps[-1]
    time_range = end_time - start_time

    # Map the axis values to actual timestamps
    ticks = []
    for value in values:
      try:
        # Scale the value if it's in the range of the timestamp indices
        if start_time <= value <= end_time:
          ticks.append(datetime.fromtimestamp(value).strftime("%H:%M:%S"))
        else:
          ticks.append("")  # Ignore out-of-range values
      except Exception as e:
        ticks.append("")  # Handle exceptions gracefully    
    # print(f"Ticks for {self.parent}: {ticks}")
    return ticks

  
      
class ToggleButton1(QAbstractButton):
  def __init__(self, parent=None):
    super().__init__(parent)
    self.setCheckable(True)
    self._background_color = QColor(255, 0, 0)
    self._circle_color = QColor(255, 255, 255)
    self._circle_position = 3  # Start position

    self.anim = QPropertyAnimation(self, b"circle_position", self)
    self.anim.setDuration(200)
    self.anim.finished.connect(self.update)  # Ensure we update after animation

    self.setFixedSize(50, 25)

  def paintEvent(self, event):
    rect = self.rect()
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # Draw background
    painter.setBrush(QBrush(self._background_color))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(0, 0, rect.width(), rect.height(), rect.height() // 2, rect.height() // 2)
    
    # Draw circle - position based on checked state if not animating
    if not self.anim.state():
      self._circle_position = self.width() - self.height() + 3 if self.isChecked() else 3
    
    # Draw the circle
    painter.setBrush(QBrush(self._circle_color))
    painter.drawEllipse(self._circle_position, 3, rect.height() - 6, rect.height() - 6)

  def mouseReleaseEvent(self, event):
    if self.rect().contains(event.pos()):
      checked = not self.isChecked()
      self.setChecked(checked)
      
      # Animate the circle
      start_pos = self._circle_position
      end_pos = self.width() - self.height() + 3 if checked else 3
      
      self.anim.setStartValue(start_pos)
      self.anim.setEndValue(end_pos)
      self.anim.start()

  def setBackgroundColor(self, color):
    self._background_color = QColor(color)
    self.update()

  def setCircleColor(self, color):
    self._circle_color = QColor(color)
    self.update()

  def get_circle_position(self):
    return self._circle_position

  def set_circle_position(self, pos):
    self._circle_position = pos
    self.update()

  circle_position = property(get_circle_position, set_circle_position)

