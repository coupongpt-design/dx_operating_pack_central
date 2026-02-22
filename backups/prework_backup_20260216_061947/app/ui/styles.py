class DarkTheme:
    # Color Palette (VS Code Dark inspired)
    BG_MAIN = "#1E1E1E"
    BG_PANEL = "#252526"
    BG_INPUT = "#3C3C3C"
    BG_HOVER = "#2A2D2E"
    BG_SELECTED = "#37373D"
    
    TEXT_PRIMARY = "#CCCCCC"
    TEXT_SECONDARY = "#858585"
    TEXT_DISABLED = "#666666"
    
    ACCENT = "#007ACC"
    ACCENT_HOVER = "#0098FF"
    ACCENT_PRESSED = "#005A9E"
    
    BORDER = "#3E3E42"
    BORDER_FOCUS = "#007ACC"
    
    SUCCESS = "#4EC9B0"
    ERROR = "#F44747"
    WARNING = "#CCA700"

    @classmethod
    def get_stylesheet(cls):
        return f"""
        /* Global Reset */
        QWidget {{
            background-color: {cls.BG_MAIN};
            color: {cls.TEXT_PRIMARY};
            font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
            font-size: 13px;
        }}

        /* Main Window & Panels */
        QMainWindow, QDialog {{
            background-color: {cls.BG_MAIN};
        }}
        QGroupBox {{
            background-color: {cls.BG_PANEL};
            border: 1px solid {cls.BORDER};
            border-radius: 4px;
            margin-top: 1.2em;
            padding-top: 10px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            color: {cls.TEXT_SECONDARY};
            font-weight: bold;
        }}

        /* Buttons */
        QPushButton {{
            background-color: {cls.BG_INPUT};
            border: 1px solid {cls.BG_INPUT};
            border-radius: 3px;
            padding: 5px 12px;
            color: {cls.TEXT_PRIMARY};
        }}
        QPushButton:hover {{
            background-color: {cls.BG_HOVER};
            border-color: {cls.BORDER};
        }}
        QPushButton:pressed {{
            background-color: {cls.ACCENT_PRESSED};
            border-color: {cls.ACCENT_PRESSED};
        }}
        QPushButton:checked {{
            background-color: {cls.ACCENT};
            border-color: {cls.ACCENT};
            color: white;
        }}
        QPushButton:disabled {{
            background-color: {cls.BG_MAIN};
            color: {cls.TEXT_DISABLED};
            border-color: {cls.BORDER};
        }}

        /* Inputs */
        QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QTimeEdit {{
            background-color: {cls.BG_INPUT};
            border: 1px solid {cls.BG_INPUT};
            border-radius: 2px;
            padding: 3px;
            color: {cls.TEXT_PRIMARY};
            selection-background-color: {cls.ACCENT};
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTimeEdit:focus {{
            border: 1px solid {cls.BORDER_FOCUS};
        }}

        /* Lists & Tables */
        QListWidget, QTableWidget {{
            background-color: {cls.BG_PANEL};
            border: 1px solid {cls.BORDER};
            border-radius: 2px;
            outline: none;
        }}
        QListWidget::item, QTableWidget::item {{
            padding: 4px;
            border-bottom: 1px solid {cls.BG_MAIN};
        }}
        QListWidget::item:selected, QTableWidget::item:selected {{
            background-color: {cls.BG_SELECTED};
            color: white;
            border-left: 2px solid {cls.ACCENT};
        }}
        QListWidget::item:hover, QTableWidget::item:hover {{
            background-color: {cls.BG_HOVER};
        }}

        /* Tabs */
        QTabWidget::pane {{
            border: 1px solid {cls.BORDER};
            background-color: {cls.BG_PANEL};
        }}
        QTabBar::tab {{
            background-color: {cls.BG_MAIN};
            color: {cls.TEXT_SECONDARY};
            padding: 8px 16px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        QTabBar::tab:selected {{
            background-color: {cls.BG_PANEL};
            color: {cls.ACCENT};
            border-bottom: 2px solid {cls.ACCENT};
        }}
        QTabBar::tab:hover {{
            color: {cls.TEXT_PRIMARY};
            background-color: {cls.BG_HOVER};
        }}

        /* Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background: {cls.BG_MAIN};
            width: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {cls.BG_INPUT};
            min-height: 20px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {cls.TEXT_DISABLED};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        /* Labels */
        QLabel {{
            color: {cls.TEXT_PRIMARY};
        }}
        
        /* Checkbox */
        QCheckBox {{
            spacing: 5px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            background: {cls.BG_INPUT};
            border: 1px solid {cls.BORDER};
            border-radius: 2px;
        }}
        QCheckBox::indicator:checked {{
            background: {cls.ACCENT};
            border: 1px solid {cls.ACCENT};
            image: url(none); /* Custom icon needed for checkmark if not using default */
        }}
        
        /* Splitter */
        QSplitter::handle {{
            background-color: {cls.BG_MAIN};
        }}
        QSplitter::handle:horizontal {{
            width: 2px;
        }}
        QSplitter::handle:vertical {{
            height: 2px;
        }}
        QSplitter::handle:hover {{
            background-color: {cls.ACCENT};
        }}

        /* Toolbar */
        QToolBar {{
            background: {cls.BG_PANEL};
            border-bottom: 1px solid {cls.BORDER};
            spacing: 5px;
            padding: 5px;
        }}
        QToolBar::separator {{
            background-color: {cls.BORDER};
            width: 1px;
            margin: 0 5px;
        }}
        QToolButton {{
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 3px;
            padding: 5px;
            color: {cls.TEXT_PRIMARY};
        }}
        QToolButton:hover {{
            background-color: {cls.BG_HOVER};
            border: 1px solid {cls.BORDER};
        }}
        QToolButton:pressed {{
            background-color: {cls.ACCENT_PRESSED};
        }}
        """
