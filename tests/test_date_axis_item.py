from pyqtgraph import AxisItem

from app_forms.frm_utils import DateAxisItem


def test_date_axis_item_ignores_late_paint_after_qt_teardown(qapp, monkeypatch):
    axis = DateAxisItem(orientation="bottom")

    def fail_late_paint(*args, **kwargs):
        raise RuntimeError("wrapped C/C++ object of type DateAxisItem has been deleted")

    monkeypatch.setattr(AxisItem, "paint", fail_late_paint)

    assert axis.paint(None) is None


def test_date_axis_item_returns_empty_rect_after_qt_teardown(qapp, monkeypatch):
    axis = DateAxisItem(orientation="bottom")

    def fail_late_bounding_rect(*args, **kwargs):
        raise RuntimeError("wrapped C/C++ object of type DateAxisItem has been deleted")

    monkeypatch.setattr(AxisItem, "boundingRect", fail_late_bounding_rect)

    assert axis.boundingRect().isNull()
