from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication

from utils.screen_geometry import (
  available_screen_geometry,
  screen_for_widget,
  screen_geometry,
)


class FakeScreen:
  def __init__(self, geometry, available_geometry):
    self._geometry = geometry
    self._available_geometry = available_geometry

  def geometry(self):
    return QRect(self._geometry)

  def availableGeometry(self):
    return QRect(self._available_geometry)


class FakeWidget:
  def __init__(self, screen):
    self._screen = screen

  def screen(self):
    return self._screen


class DeletedWidget:
  def screen(self):
    raise RuntimeError("wrapped C/C++ object has been deleted")


def test_screen_geometry_prefers_widget_screen(monkeypatch):
  widget_screen = FakeScreen(QRect(10, 20, 300, 240), QRect(12, 24, 280, 200))
  primary_screen = FakeScreen(QRect(500, 600, 700, 800), QRect(520, 620, 640, 720))
  monkeypatch.setattr(QApplication, "primaryScreen", lambda: primary_screen)

  widget = FakeWidget(widget_screen)

  assert screen_for_widget(widget) is widget_screen
  assert screen_geometry(widget) == QRect(10, 20, 300, 240)
  assert available_screen_geometry(widget) == QRect(12, 24, 280, 200)


def test_screen_geometry_uses_primary_screen_when_widget_has_no_screen(monkeypatch):
  primary_screen = FakeScreen(QRect(50, 60, 900, 700), QRect(70, 80, 860, 640))
  monkeypatch.setattr(QApplication, "primaryScreen", lambda: primary_screen)

  widget = FakeWidget(None)

  assert screen_for_widget(widget) is primary_screen
  assert screen_geometry(widget) == QRect(50, 60, 900, 700)
  assert available_screen_geometry(widget) == QRect(70, 80, 860, 640)


def test_screen_geometry_returns_copied_fallback_when_screens_are_unavailable(monkeypatch):
  monkeypatch.setattr(QApplication, "primaryScreen", lambda: None)
  fallback = QRect(3, 4, 500, 400)

  geometry = screen_geometry(DeletedWidget(), fallback=fallback)
  available_geometry = available_screen_geometry(DeletedWidget(), fallback=fallback)

  assert screen_for_widget(DeletedWidget()) is None
  assert geometry == fallback
  assert available_geometry == fallback

  geometry.moveLeft(99)
  available_geometry.moveTop(88)

  assert fallback == QRect(3, 4, 500, 400)
