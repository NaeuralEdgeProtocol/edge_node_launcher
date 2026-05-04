from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication


FALLBACK_SCREEN_GEOMETRY = QRect(0, 0, 1280, 720)


def screen_for_widget(widget=None):
  if widget is not None:
    screen_getter = getattr(widget, "screen", None)
    if screen_getter is not None:
      try:
        screen = screen_getter()
      except RuntimeError:
        screen = None
      if screen is not None:
        return screen

  return QApplication.primaryScreen()


def screen_geometry(widget=None, fallback: QRect = FALLBACK_SCREEN_GEOMETRY) -> QRect:
  screen = screen_for_widget(widget)
  if screen is not None:
    return QRect(screen.geometry())
  return QRect(fallback)


def available_screen_geometry(widget=None, fallback: QRect = FALLBACK_SCREEN_GEOMETRY) -> QRect:
  screen = screen_for_widget(widget)
  if screen is not None:
    return QRect(screen.availableGeometry())
  return QRect(fallback)
