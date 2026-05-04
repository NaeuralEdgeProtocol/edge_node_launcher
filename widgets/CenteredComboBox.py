from PyQt5.QtWidgets import QApplication, QComboBox, QSizePolicy, QStyledItemDelegate
from PyQt5.QtCore import Qt, QObject, QEvent, QTimer, QRect, QSize
from PyQt5.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPen
from utils.const import DARK_STYLESHEET, DARK_COLORS, LIGHT_COLORS


_COMBO_THEME_COLORS = {
    False: {
        "surface": "#F8FAFC",
        "surface_hover": "#FFFFFF",
        "border": "#CBD5E1",
        "border_focus": "#1B47F7",
        "text": "#1F2937",
        "arrow": "#5F6B7A",
        "popup_bg": LIGHT_COLORS["combobox_popup_bg_color"],
        "popup_border": LIGHT_COLORS["combobox_popup_border_color"],
        "popup_hover": LIGHT_COLORS["combo_hover_bg"],
        "popup_selected_bg": LIGHT_COLORS["combobox_popup_item_selected_bg"],
        "popup_selected_text": LIGHT_COLORS["combobox_popup_item_selected_text"],
    },
    True: {
        "surface": "#151A23",
        "surface_hover": "#202734",
        "border": "#445164",
        "border_focus": "#4EA3FF",
        "text": "#E8EEF8",
        "arrow": "#A9B7C9",
        "popup_bg": DARK_COLORS["combobox_popup_bg_color"],
        "popup_border": DARK_COLORS["combobox_popup_border_color"],
        "popup_hover": "#202734",
        "popup_selected_bg": DARK_COLORS["combobox_popup_item_selected_bg"],
        "popup_selected_text": DARK_COLORS["combobox_popup_item_selected_text"],
    },
}

_SELECTED_TEXT_MARGIN = 36


def _combo_stylesheet(colors):
    return f"""
QComboBox {{
    combobox-popup: 1;
    background-color: {colors["surface"]};
    color: {colors["text"]};
    border: 1px solid {colors["border"]};
    border-radius: 16px;
    padding: 0px 34px 0px 12px;
    min-height: 34px;
    font-weight: normal;
}}
QComboBox:hover {{
    background-color: {colors["surface_hover"]};
    border-color: {colors["border_focus"]};
}}
QComboBox:focus {{
    border-color: {colors["border_focus"]};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: right center;
    width: 30px;
    border: none;
    background: transparent;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0px;
    height: 0px;
}}
"""


def _line_edit_stylesheet(colors):
    return f"""
QLineEdit {{
    background: transparent;
    color: transparent;
    selection-color: transparent;
    selection-background-color: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}}
"""


def _popup_stylesheet(colors):
    return f"""
QListView {{
    border: 1px solid {colors["popup_border"]};
    border-radius: 8px;
    background-color: {colors["popup_bg"]};
    outline: none;
    padding: 8px;
}}
QListView::item {{
    border-radius: 6px;
    padding: 6px;
    margin: 2px;
    color: {colors["text"]};
    text-align: center;
}}
QListView::item:hover {{
    background-color: {colors["popup_hover"]};
}}
QListView::item:selected {{
    background-color: {colors["popup_selected_bg"]};
    color: {colors["popup_selected_text"]};
}}
QComboBox QAbstractItemView::item {{
    text-align: center;
}}
"""

class NoDecorationsDelegate(QStyledItemDelegate):
    """A delegate that removes all decorations and indicators from combo box items"""
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # Remove all decorations and icons
        option.icon = QIcon()  # Use empty QIcon instead of None
        option.decorationSize = QSize(0, 0)  # Use QSize instead of Qt.Size
        # option.features = None  # Reset all features to remove decorations

class ClickToOpenFilter(QObject):
    def __init__(self, combo):
        super().__init__(combo)
        self.combo = combo

    def eventFilter(self, obj, event):
        try:
            if obj == self.combo.lineEdit() and event.type() == QEvent.MouseButtonPress:
                self.combo.showPopup()
                return True
            return super().eventFilter(obj, event)
        except RuntimeError:
            # Handle case where the C/C++ object has been deleted
            return False

class CenteredComboBox(QComboBox):
    """A QComboBox that centers both the dropdown items and the selected item."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Set up a delegate to center the items in the view and remove decorations
        delegate = NoDecorationsDelegate(self)
        self.setItemDelegate(delegate)

        # Make editable to get the line edit for centering
        self.setEditable(True)

        # Disable editing by setting read-only
        self.lineEdit().setReadOnly(True)

        # Center the text in the line edit
        self.lineEdit().setAlignment(Qt.AlignCenter)

        # Make the line edit behave like selected combo text.
        self.lineEdit().setFrame(False)
        self.lineEdit().hide()
        self.lineEdit().setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.lineEdit().installEventFilter(ClickToOpenFilter(self))
        # Disable all text interactions:
        self.lineEdit().setFocusPolicy(Qt.NoFocus)

        # (Optional) Change the cursor so it doesn't look like an I-beam:
        self.lineEdit().setCursor(Qt.ArrowCursor)

        self.setMinimumHeight(36)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(1)

        # Make sure the popup is also properly styled
        self.view().parentWidget().setStyleSheet("background: transparent;")
        
        # Ensure combo box popup items are centered as well
        for i in range(self.count()):
            self.setItemData(i, Qt.AlignCenter, Qt.TextAlignmentRole)
            
        # Apply the default theme
        self.apply_default_theme()

        self.setMaxVisibleItems(10)
        
    def paintEvent(self, event):
        """Draw the themed combo, selected text, and dropdown chevron."""
        super().paintEvent(event)

        colors = _COMBO_THEME_COLORS[self.is_dark_theme()]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        text_rect = self.rect().adjusted(
            _SELECTED_TEXT_MARGIN,
            0,
            -_SELECTED_TEXT_MARGIN,
            0,
        )
        painter.setPen(QColor(colors["text"]))
        selected_text = QFontMetrics(self.font()).elidedText(
            self.currentText(),
            Qt.ElideMiddle,
            text_rect.width(),
        )
        painter.drawText(text_rect, Qt.AlignCenter | Qt.AlignVCenter, selected_text)

        pen = QPen(QColor(colors["arrow"]), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        center_y = self.height() // 2
        center_x = self.width() - 17
        painter.drawLine(center_x - 5, center_y - 2, center_x, center_y + 3)
        painter.drawLine(center_x, center_y + 3, center_x + 5, center_y - 2)

    def apply_default_theme(self):
        """Apply appropriate styling for the current theme when the widget is first created"""
        colors = _COMBO_THEME_COLORS[self.is_dark_theme()]
        self.setStyleSheet(_combo_stylesheet(colors))
        self.lineEdit().setStyleSheet(_line_edit_stylesheet(colors))
        self.lineEdit().setTextMargins(28, 0, 28, 0)
        self.lineEdit().hide()
        self.update()

    def addItem(self, text, userData=None):
        """Override addItem to ensure new items are center-aligned"""
        super().addItem(text, userData)
        self.setItemData(self.count() - 1, Qt.AlignCenter, Qt.TextAlignmentRole)
        # Remove any decoration or icon
        self.setItemData(self.count() - 1, None, Qt.DecorationRole)

    def insertItem(self, index, text, userData=None):
        """Override insertItem to ensure new items are center-aligned"""
        super().insertItem(index, text, userData)
        self.setItemData(index, Qt.AlignCenter, Qt.TextAlignmentRole)
        # Remove any decoration or icon
        self.setItemData(index, None, Qt.DecorationRole)

    def is_dark_theme(self):
        """Detect if dark theme is currently active based on main window's stylesheet"""
        # If we have a stored theme value, use it first
        if hasattr(self, '_is_dark_theme') and self._is_dark_theme is not None:
            return self._is_dark_theme
        
        # Legacy approach (as fallback)
        # Get the main window
        parent = self.parent()
        while parent is not None:
            # Check if this parent has the _current_stylesheet attribute 
            if hasattr(parent, '_current_stylesheet'):
                return parent._current_stylesheet == DARK_STYLESHEET
            parent = parent.parent()
        
        # Fallback to the application palette check if we can't find the main window
        app = QApplication.instance()
        if app:
            bg_color = app.palette().color(app.palette().Window)
            return bg_color.lightness() < 128
            
        return True  # Default to dark theme if can't determine

    def set_theme(self, is_dark):
        """Set the theme directly from the parent component"""
        self._is_dark_theme = bool(is_dark)
        self.apply_default_theme()

    def showPopup(self):
        """Override showPopup to ensure all items are center-aligned and have rounded corners with theme awareness"""
        for i in range(self.count()):
            self.setItemData(i, Qt.AlignCenter, Qt.TextAlignmentRole)
            # Remove any decoration or icon
            self.setItemData(i, None, Qt.DecorationRole)

        colors = _COMBO_THEME_COLORS[self.is_dark_theme()]
        self.view().setStyleSheet(_popup_stylesheet(colors))

        # Set window flags to remove frame and shadow
        self.view().window().setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)

        # Make the background translucent
        self.view().window().setAttribute(Qt.WA_TranslucentBackground)

        # Call the parent implementation to show the popup
        super().showPopup()
        
        # Now center the popup by finding and repositioning it
        # We need to use a slight delay to ensure the popup has been fully created and sized
        QTimer.singleShot(10, self._center_popup)
        
    def _center_popup(self):
        """Center the popup under the combobox after it has been shown"""
        # First, try to get the popup directly as a child of the combobox
        popup = None
        
        # Try the standard method first - look for the popup view's parent widget
        popup_view = self.view()
        if popup_view and popup_view.parent():
            popup = popup_view.parent()
            if popup.isVisible() and (popup.windowFlags() & Qt.Popup):
                # This is likely our popup
                self._apply_centering(popup)
                return
                
        # Try the second method - look for all popups and find the closest one
        popups = [w for w in QApplication.allWidgets() if w.isVisible() and 
                 (w.windowFlags() & Qt.Popup) and
                 w != self]
                 
        # Find the popup that's closest to our combobox (likely to be our dropdown)
        if popups:
            # Convert combobox rect to global coordinates
            combobox_rect = QRect(self.mapToGlobal(self.rect().topLeft()), 
                                  self.mapToGlobal(self.rect().bottomRight()))
            
            # Find the closest popup
            closest_popup = None
            min_distance = float('inf')
            
            for popup in popups:
                popup_pos = popup.pos()
                # Calculate distance from popup to combobox bottom
                dist = abs(popup_pos.y() - combobox_rect.bottom())
                if dist < min_distance:
                    min_distance = dist
                    closest_popup = popup
            
            # If we found a popup that's close to our combobox, center it
            if closest_popup and min_distance < 50:  # Only reposition if it's close
                self._apply_centering(closest_popup)
    
    def _apply_centering(self, popup):
        """Apply centering to the identified popup"""
        # Convert combobox rect to global coordinates
        combobox_rect = QRect(self.mapToGlobal(self.rect().topLeft()), 
                              self.mapToGlobal(self.rect().bottomRight()))
                              
        popup_width = popup.width()
        combobox_width = self.width()
        
        # Calculate the center position of the combobox in global coordinates
        combobox_center_x = combobox_rect.left() + combobox_rect.width() // 2
        
        # Calculate new popup position
        new_x = combobox_center_x - popup_width // 2
        
        # Make sure the popup doesn't go off-screen
        screen = self._popup_screen_geometry()
        if new_x < screen.left():
            new_x = screen.left()
        elif (new_x + popup_width) > screen.right():
            new_x = screen.right() - popup_width
        
        # Reposition the popup
        popup.move(new_x, popup.y())

    def _popup_screen_geometry(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            return screen.geometry()

        desktop = QApplication.desktop()
        return desktop.screenGeometry(self)
