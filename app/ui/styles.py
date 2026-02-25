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
            border: 1px solid #444444;
            border-radius: 2px;
            padding: 1px 3px;
            font-size: 9pt;
            min-width: 0px;
            color: {cls.TEXT_PRIMARY};
        }}
        QPushButton:hover {{
            background-color: {cls.BG_HOVER};
            border-color: #5a5a5a;
        }}
        QPushButton:pressed {{
            background-color: #3b434c;
            border-color: #626a74;
        }}
        QPushButton:checked {{
            background-color: #54606f;
            border-color: #6a7687;
            color: white;
        }}
        QPushButton:disabled {{
            background-color: {cls.BG_MAIN};
            color: {cls.TEXT_DISABLED};
            border-color: #3a3a3a;
        }}
        QPushButton[class="left-primary"] {{
            background-color: #34495a;
            border-color: #4a6276;
        }}
        QPushButton[class="left-secondary"] {{
            background-color: #3f4b55;
            border-color: #596673;
        }}
        QPushButton[class="left-capture"] {{
            background-color: #425463;
            border-color: #5d7488;
        }}
        QPushButton[class="left-run"] {{
            background-color: #3a5770;
            border-color: #567590;
            color: #f2f7fb;
            font-weight: 600;
        }}
        QPushButton[class="left-run-paused"] {{
            background-color: #8a7243;
            border-color: #b08d4c;
            color: #f5efdc;
            font-weight: 600;
        }}
        QPushButton[class="left-stop"] {{
            background-color: #5c3a40;
            border-color: #7a5058;
            color: #f7e9eb;
            font-weight: 600;
        }}
        QPushButton[class="left-record"] {{
            background-color: #694246;
            border-color: #88595e;
        }}
        QPushButton[class="left-wizard"] {{
            background-color: #514a42;
            border-color: #6b6258;
        }}
        QPushButton[class="left-sim"] {{
            background-color: #3f5552;
            border-color: #5f7370;
        }}
        QPushButton[class="left-neutral"] {{
            background-color: #40454c;
            border-color: #5b616a;
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

        /* Option toolbar groups */
        QWidget#optTargetGroup, QWidget#optFlagsGroup, QWidget#optExcelGroup {{
            border: 1px solid {cls.BORDER};
            border-radius: 4px;
        }}
        QWidget#optExcelGroup {{
            background-color: rgba(64, 110, 78, 45);
            border: 1px solid rgba(96, 150, 112, 180);
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

        /* Menu bar */
        QMenuBar {{
            background-color: {cls.BG_PANEL};
            color: {cls.TEXT_PRIMARY};
            border-bottom: 1px solid #383c40;
            padding: 2px 4px;
            font-size: 9.5pt;
        }}
        QMenuBar::item {{
            background: transparent;
            padding: 4px 8px;
            border-radius: 3px;
        }}
        QMenuBar::item:selected {{
            background-color: {cls.BG_HOVER};
            color: {cls.TEXT_PRIMARY};
        }}
        QMenu {{
            background-color: {cls.BG_PANEL};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid #444444;
        }}
        QMenu::item {{
            padding: 5px 18px;
        }}
        QMenu::item:selected {{
            background-color: {cls.BG_HOVER};
            color: {cls.TEXT_PRIMARY};
        }}
        QMenu::separator {{
            height: 1px;
            background: #3b3f43;
            margin: 4px 6px;
        }}

        /* Toolbar */
        QToolBar {{
            background: {cls.BG_PANEL};
            border-bottom: 1px solid #383c40;
            spacing: 4px;
            padding: 2px;
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
