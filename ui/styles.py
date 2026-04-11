
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

def get_dark_theme() -> str:
    """Return dark theme QSS stylesheet using colors from `config` when provided."""
    from modules import config
    bg = getattr(config, 'bg_color_dark', '#14161a')
    menu_bg = getattr(config, 'menu_bg', '#1f2227')
    toolbar_bg = getattr(config, 'toolbar_bg', '#1b1e23')
    text = getattr(config, 'text_color', '#e8eaed')
    accent = getattr(config, 'accent_color', '#2b80ff')
    progress_col = getattr(config, 'progress_color', accent)


    _C = {
        "bg":           "#0f1117",   # near-black canvas
        "surface":      "#1a1d27",   # card surface
        "border":       "#2a2e3d",   # subtle borders
        "accent":       "#4f8ef7",   # electric blue CTA
        "accent_dim":   "#1e3a6e",   # muted accent for disabled / hover bg
        "text_primary": "#ffffff",
        "text_muted":   "#6b7280",   # secondary / hint text
        "text_label":   "#9ca3af",   # form labels
        "success":      "#22c55e",   # green confirmations
        "warn":         "#f59e0b",   # amber warnings (auto-captions badge)
        "danger":       "#ef4444",   # destructive actions
        "input_bg":     "#12151f",   # combo / input fill
        "separator":    "#252836",
    }

    css = f"""
        QMainWindow {{
            background-color: #14161a;
        }}
        QMainWindow::separator {{
            background: #14161a;
            width: 1px;
            height: 1px;
            border: none;
        }}
        QMenuBar {{
            background-color: {menu_bg};
            color: {text};
        }}
        QMenuBar::item {{
            background: transparent;
            padding: 4px 12px;
        }}
        QMenu {{
            background-color: #1f2227;
            color: #e8eaed;
            border: 1px solid #2b3138;
        }}
        QMenu::item {{
            padding: 6px;
            padding-left: 4px;
            padding-right: 43px;
        }}
        QMenu::item:selected {{
            background-color: #2b3138;
        }}
        QMenu::icon {{
            padding-right: 4px;
        }}
        QToolBar {{
            background-color: #1b1e23;
            border-bottom: 1px solid #2b3138;
            spacing: 6px;
        }}
        QToolBar::separator {{
            width: 8px;
            background: transparent;
        }}
        QToolButton {{
            background: transparent;
            border-radius: 6px;
            padding: 6px 10px;
            color: #e8eaed;
        }}
        QToolButton:hover {{
            background-color: #2b3138;
        }}
        QLabel {{
            color: #e8eaed;
        }}
        QLabel#PageTitle {{
            font-size: 20px;
            font-weight: 600;
        }}
        QLabel#InfoTitle {{
            font-size: 14px;
            font-weight: 600;
        }}
        QLabel#InfoBody {{
            font-size: 12px;
            color: #c4c7cc;
        }}
        QDockWidget {{
            background-color: #14161a;
        }}
        QDockWidget::title {{
            padding: 6px 10px;
            background-color: #14161a;
            color: #9aa0a6;
        }}
        QListWidget {{
            background-color: #181b20;
            border-radius: 8px;
            padding: 4px;
            border: 1px solid #262a31;
            color: #e8eaed;
        }}
        QListWidget::item {{
            border-radius: 6px;
            padding: 6px 8px;
        }}
        QListWidget::item:selected {{
            background-color: {accent};
            color: white;
        }}
        QListWidget QScrollBar:vertical {{
            background: #202124;
        }}

        QListWidget QScrollBar::add-line:vertical,
        QListWidget QScrollBar::sub-line:vertical {{
            height: 0px;
            background: none;
            border: none;
        }}

        QTableWidget {{
            background-color: #181b20;
            alternate-background-color: #171a1f;
            border: 1px solid #262a31;
            border-radius: 10px;
            color: white
        }}
        QHeaderView::section {{
            background-color: #181b20;
            border: none;
            border-bottom: 1px solid #262a31;
            padding: 8px 6px;
            color: #9aa0a6;
        }}
        QTableView::item:selected {{
            background-color: rgba(43, 128, 255, 0.25);
        }}
        QTableWidget::item:focus {{
            outline: none;
            border: none;
        }}
        QTableWidget QScrollBar:vertical, QScrollBar:horizontal {{
            background: #202124;
        }}
        QTableView QScrollBar::add-line:vertical,
        QTableView QScrollBar::sub-line:vertical {{
            height: 0px;
            background: none;
            border: none;
        }}
        QTableView QScrollBar::add-line:horizontal,
        QTableView QScrollBar::sub-line:horizontal {{
            height: 0px;
            background: none;
            border: none;
        }}

        QTableView::item:selected:active {{
            background-color: rgba(43, 128, 255, 0.25);
        }}


        /* Disable hover highlight */
        QTableView::item:hover {{
            background: transparent;
        }}

        /* Disable current item highlight */
        QTableView::item:selected:!active {{
            background: rgba(43, 128, 255, 0.25);
        }}

        QTableView::item:!selected {{
            background: transparent;
        }}

        /* Remove focus/current cell outline */
        QTableView::item:!active {{
            outline: none;
        }}
        



        QProgressBar[downloadProgress="true"] {{
            border: 1px solid #262a31;
            border-radius: 6px;
            text-align: center;
            background-color: #14161a;
            padding: 1px;
        }}
        QProgressBar[downloadProgress="true"]::chunk {{
            border-radius: 6px;
            background-color: {progress_col};
        }}
        QLineEdit, QComboBox, QTextEdit, QSpinBox,
        QDateTimeEdit, QPlainTextEdit {{
            background-color: #14161a;
            border-radius: 6px;
            border: 1px solid #30343b;
            padding: 6px 8px;
            color: #e8eaed;
            selection-background-color: #2b80ff;
        }}
        QPlainTextEdit {{
            border-radius: 8px;
        }}
        QLineEdit:focus, QComboBox:focus, QTextEdit:focus,
        QSpinBox:focus, QDateTimeEdit:focus {{
            border-color: {accent};
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background-color: #181b20;
            selection-background-color: #2b80ff;
        }}
        QStatusBar {{
            background-color: #1b1e23;
            color: #9aa0a6;
        }}
        QDialog {{
            background-color: #181b20;
        }}
        QPushButton {{
            background-color: {accent};
            color: white;
            padding: 6px 14px;
            border-radius: 6px;
            border: none;
        }}
        QPushButton:hover {{
            background-color: #3b8dff;
        }}
        QPushButton:disabled {{
            background-color: #30343b;
            color: #80868b;
        }}
        QCheckBox {{
            color: #e8eaed;
        }}
 
        
        QTabWidget::pane {{
            border: 1px solid #262a31;
            border-radius: 8px;
            padding: 4px;
            margin-top: -2px;
        }}
        QTabBar::tab {{
            background: #181b20;
            padding: 6px 12px;
            margin-right: 2px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            color: #9aa0a6;
            min-height: 26px;
            border-bottom: none;                
            min-height: 26px;
        }}
        QTabBar::tab:selected {{
            background: #1f2227;
            color: #e8eaed;
            margin-top: 0px;
            font-weight: 600;
            border-color: #1a73e8 #dadce0 #ffffff #dadce0; /* blue top border */
        }}
  



        QTabBar::tab:!selected {{
            margin-top: 2px;                    /* appear slightly "lower" */
        }}

        QTabBar::tab:hover {{
            background-color: #262a31;
        }}

        /* --- Details dialog (dark theme) --- */
        QDialog#DetailsDialog {{
            background-color: #181b20;
            border: 1px solid #262a31;
            border-radius: 10px;
        }}
        QWidget#DetailsHeaderBar {{
            background-color: #1f2227;
            border-radius: 8px;
        }}
        QLabel#DetailsHeaderIcon {{
            font-size: 16px;
        }}
        QLabel#DetailsHeaderTitle {{
            font-size: 13px;
            font-weight: 600;
            color: #e8eaed;
        }}
        /* Metadata labels in details dialog use normal label color (already set),
            but you can slightly dim the value labels if you want via objectName later. */

        /* Combo popup items (dark) */
        QComboBox QAbstractItemView {{
            background-color: #181b20;
            color: #e8eaed;
            selection-background-color: #2b80ff;
            selection-color: #ffffff;
            border: 1px solid #30343b;
        }}
        QTableWidget#DownloadsTable QProgressBar {{
            min-height: 26px;
            max-height: 38px;
        }}

        /* --- IDM-style flat dialog buttons (DARK THEME) --- */

        QWidget#AddDownloadWindow {{
            background-color: #14161a;
        }}

        QWidget#AddDownloadWindow QPushButton {{
            background: #2a2d31;
            color: #e6e6e6;
            border: 1px solid #3a3d42;
            border-radius: 4px;
            padding: 6px 14px;
            min-width: 70px;
            font-size: 13px;
        }}

        /* Hover: slightly brighter grey */
        QWidget#AddDownloadWindow QPushButton:hover {{
            background: #33363b;
            border: 1px solid #4a4d52;
        }}

        /* Pressed: darker grey */
        QWidget#AddDownloadWindow QPushButton:pressed {{
            background: #2a2d31;
            border: 1px solid #3a3d42;
            padding-top: 7px;
        }}

        /* Default/active button = blue border */
        QWidget#AddDownloadWindow QPushButton:default {{
            border: 1px solid {accent};
            color: #bfe0ff;
        }}

        QWidget#AddDownloadWindow, QComboBox:focus, QLineEdit::focus {{
            border-color: {accent};
        }}

    
        QDialog#DownloadProgressDialog QProgressBar::chunk {{
            background-color: {accent};
        }}

       

    
        QDialog QPushButton {{
            background: #2a2d31;
            color: #e6e6e6;
            border: 1px solid #3a3d42;
            border-radius: 4px;
            padding: 6px 14px;
            min-width: 70px;
            font-size: 13px;
        }}

        /* Hover: slightly brighter grey */
        QDialog QPushButton:hover {{
            background: #33363b;
            border: 1px solid #4a4d52;
        }}

        /* Pressed: darker grey */
        QDialog QPushButton:pressed {{
            background: #2a2d31;
            border: 1px solid #3a3d42;
            padding-top: 7px;
        }}

        /* Default/active button = blue border */
        QDialog QPushButton:default {{
            border: 1px solid {accent};
            color: #bfe0ff;
        }}

        QProgressBar {{
            border: none;
            background: transparent;
        }}

        QProgressBar::chunk {{
            background-color: #3b82f6; /* blue */
            border-radius: 3px;
        }}

        QLabel#DownloadThumbnail {{
            border: 1px solid rgba(0,0,0,40); 
            border-radius: 6px;
            background: rgba(0,0,0,5%);
        }}

        QPushButton#AddCategoryButton {{
            border: 1px solid #cfcfcf;
            background: transparent;
            border-radius: 3px;
            font-weight: bold;
            padding: 0px 2px;
        }}

        QPushButton#AddCategoryButton:hover {{
            background: #eaeaea;
        }}


        QDialog#ScheduleDialog {{
            background-color: #14161a;
            border-radius: 10px;
            border: 1px solid #dadce0;
        }}

        QDialog#ScheduleDialog QPushButton {{
            background: #2a2d31;
            color: #e6e6e6;
            border: 1px solid #3a3d42;
            border-radius: 4px;
            padding: 6px 14px;
            min-width: 70px;
            font-size: 13px;
        }}

        QDialog#ScheduleDialog QPushButton:default {{
            border: 1px solid {accent};
            color: #bfe0ff;
        }}






        QDialog#AdvancedMetadataDialog {{
            background-color: {_C['bg']};
            color:            {_C['text_primary']};
            font-family:      "JetBrains Mono", "Fira Code", "Consolas", monospace;
            font-size:        12px;
        }}

        QDialog#AdvancedMetadataDialog QFrame#sidebar {{
            background-color: {_C['bg']};
            border-right: 1px solid;
        }}


        /* Header Styling */
        QDialog#AdvancedMetadataDialog QFrame#header {{
            background-color: {_C['bg']};
            border-bottom: 1px solid rgba(60, 60, 60, 0.5);
            color: white;
        }}

        QWidget#right_content_area {{
            background-color: {_C['bg']};
        }}
        
        /* Footer Styling */
        QDialog#AdvancedMetadataDialog QFrame#footer {{
            background-color: {_C['bg']};
            border-top: 1px solid rgba(60, 60, 60, 0.5);
        }}

        QWidget#scroll_content {{
            background-color: transparent; /* Let the Dialog background show through */
        }}

        /* 4. Ensure the pages inside the stack are also transparent */
        QStackedWidget > QWidget {{
            background-color: transparent;
        }}

        

        QDialog#AdvancedMetadataDialog QFrame {{
            background-color: transparent; /* Allows the Dialog's _C['bg'] to show through */
        }}
        
        
        /* Section cards */
        QDialog#AdvancedMetadataDialog QFrame#card {{
            background-color: {_C['surface']};
            border:           1px solid {_C['border']};
            border-radius:    8px;
        }}


        /* Navigation Buttons */
        QPushButton#nav_button {{
            text-align: left;
            padding: 12px 16px;
            border: none;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            background-color: transparent;
            color: #e0e0e0;
        }}
        
        QPushButton#nav_button:hover {{
            background-color: rgba(255, 255, 255, 0.08);
        }}
        
        QPushButton#nav_button:checked {{
            background-color: {accent};
            color: white;
            font-weight: 600;
        }}

        QDialog#AdvancedMetadataDialog QLabel#title_header{{
            font-size:15px; 
            font-weight:700;
            color: {_C['text_primary']};
        }}

        /* ── Section header labels ───────────────────────────────────────────────── */
        QDialog#AdvancedMetadataDialog QLabel#section_header {{
            color:        {accent};
            font-size:   11px;
            font-weight: 600;
            letter-spacing: 1.5px;
        }}

        /* ── Regular labels ──────────────────────────────────────────────────────── */
        QDialog#AdvancedMetadataDialog QLabel {{
            color:       {_C['text_label']};
            font-size:   12px;
        }}
        QDialog#AdvancedMetadataDialog QLabel#hint {{
            color:     white;
            font-size: 11px;
        }}

        /* ── Combo boxes ─────────────────────────────────────────────────────────── */
        QDialog#AdvancedMetadataDialog QComboBox {{
            background-color: {_C['input_bg']};
            color:            {_C['text_primary']};
            border:           1px solid {_C['border']};
            border-radius:    5px;
            padding:          6px 10px;
            font-size:        12px;
            min-height:       30px;
        }}
        QDialog#AdvancedMetadataDialog QComboBox:hover {{
            border-color:  {accent};
        }}
        QDialog#AdvancedMetadataDialog QComboBox:focus {{
            border-color:  {accent};
            outline: none;
        }}
        QDialog#AdvancedMetadataDialog QComboBox::drop-down {{
            border: none;
            width:  24px;
        }}
        QDialog#AdvancedMetadataDialog QComboBox::down-arrow {{
            image: none;
            border-left:  4px solid transparent;
            border-right: 4px solid transparent;
            border-top:   5px solid {_C['text_muted']};
            margin-right: 6px;
        }}
        QDialog#AdvancedMetadataDialog QComboBox QAbstractItemView {{
            background-color: {_C['surface']};
            color:            {_C['text_primary']};
            border:           1px solid {_C['border']};
            selection-background-color: {_C['accent_dim']};
            selection-color:             {accent};
            outline: none;
            padding: 4px;
        }}

        /* ── Checkboxes ───────────────────────────────────────────────────────────── */
        
        QDialog#AdvancedMetadataDialog QCheckBox {{
            color:       {_C['text_primary']};
            font-size:   13px;
            spacing:     8px;
        }}
        QDialog#AdvancedMetadataDialog QCheckBox::indicator {{
            width:  18px;
            height: 18px;
            border: 1.5px solid {_C['border']};
            border-radius: 4px;
            background-color: {_C['input_bg']};
        }}
        QDialog#AdvancedMetadataDialog QCheckBox::indicator:hover {{
            border-color: {accent};
        }}

        QDialog#AdvancedMetadataDialog QCheckBox::indicator:checked {{
            background-color:  {accent};
            border-color:      {accent};
            image: none;  /* rely on pure CSS fill */
        }}
        QDialog#AdvancedMetadataDialog QCheckBox:disabled {{
            color: {_C['text_muted']};
        }}
        QDialog#AdvancedMetadataDialog QCheckBox::indicator:disabled {{
            border-color:     {_C['border']};
            background-color: {_C['bg']};
        }}

        /* ── Buttons ─────────────────────────────────────────────────────────────── */
         QDialog#AdvancedMetadataDialog QPushButton#btn_cancel {{
            background-color: transparent;
            color:            {_C['text_muted']};
            border:           1px solid {_C['border']};
            border-radius:    6px;
            padding:          8px 20px;
            font-size:        12px;
        }}
        QDialog#AdvancedMetadataDialog QPushButton#btn_cancel:hover {{
            color:        {_C['text_primary']};
            border-color: {_C['text_muted']};
        }}
        QDialog#AdvancedMetadataDialog QPushButton#btn_apply {{
            background-color:  {accent};
            color:            #ffffff;
            border:           none;
            border-radius:    6px;
            padding:          8px 24px;
            font-size:        12px;
            font-weight:      600;
        }}
        QDialog#AdvancedMetadataDialog QPushButton#btn_apply:hover {{
            background-color: #6fa3f9;
        }}
        QDialog#AdvancedMetadataDialog QPushButton#btn_apply:pressed {{
            background-color: #3a74d6;
        }}

        /* ── Horizontal rule ─────────────────────────────────────────────────────── */
        QDialog#AdvancedMetadataDialog QFrame#hr {{
            border:            none;
            border-top:        1px solid {_C['separator']};
            max-height:        1px;
        }}

        /* ── Badge labels ────────────────────────────────────────────────────────── */
        QDialog#AdvancedMetadataDialog QLabel#badge_manual {{
            color:             {accent};
            background-color: {_C['accent_dim']};
            border-radius:    3px;
            padding:          1px 6px;
            font-size:        10px;
            font-weight:      600;
        }}
        QDialog#AdvancedMetadataDialog QLabel#badge_auto {{
            color:            {_C['warn']};
            background-color: rgba(245,158,11,0.18);
            border-radius:    3px;
            padding:          1px 6px;
            font-size:        10px;
            font-weight:      600;
        }}
        QDialog#AdvancedMetadataDialog QLabel#no_subs {{
            color:            {_C['text_muted']};
            font-style:       italic;
            font-size:        12px;
        }}

        
        
        
    """
    return css


def get_light_theme() -> str:
    """Return light theme QSS stylesheet."""

    from modules import config
    bg = getattr(config, 'bg_color_dark', '#14161a')
    menu_bg = getattr(config, 'menu_bg', '#1f2227')
    toolbar_bg = getattr(config, 'toolbar_bg', '#1b1e23')
    text = getattr(config, 'text_color', '#e8eaed')
    accent = getattr(config, 'accent_color', '#2b80ff')
    progress_col = getattr(config, 'progress_color', accent)


    _C = {
        "bg":           "#f8f9fb",   # bright, clean canvas
        "surface":      "#ffffff",   # white card surface
        "border":       "#e2e8f0",   # light grey borders
        "accent":       "#2b6cb0",   # deep professional blue (darker for contrast)
        "accent_dim":   "#ebf8ff",   # very light blue for badges/hover
        "text_primary": "#1a202c",   # dark slate for high-readability
        "text_muted":   "#718096",   # cool grey for hints
        "text_label":   "#4a5568",   # slate for form labels
        "success":      "#38a169",   # forest green
        "warn":         "#dd6b20",   # burnt orange (better contrast on white)
        "danger":       "#e53e3e",   # red
        "input_bg":     "#f1f5f9",   # subtle grey for inputs
        "separator":    "#edf2f7",
    }

    css = f"""


        QDialog#AdvancedMetadataDialog {{
            background-color: {_C['bg']};
            color:            {_C['text_primary']};
            font-family:      "JetBrains Mono", "Fira Code", "Consolas", monospace;
            font-size:        12px;
        }}


        QDialog#AdvancedMetadataDialog QFrame#sidebar {{
            background-color: rgba(245, 247, 250, 0.95);
            border-right: 1px solid;
        }}


        /* Header Styling */
        QDialog#AdvancedMetadataDialog QFrame#header {{
            background-color: {_C['bg']};
            border-bottom: 1px solid rgba(60, 60, 60, 0.5);
            color: white;
        }}

        QWidget#right_content_area {{
            background-color: {_C['bg']};
        }}
        
        /* Footer Styling */
        QDialog#AdvancedMetadataDialog QFrame#footer {{
            background-color: {_C['surface']}; 
            border-top: 1px solid {_C['border']};
        }}

        QWidget#scroll_content {{
            background-color: transparent; /* Let the Dialog background show through */
        }}

        /* 4. Ensure the pages inside the stack are also transparent */
        QStackedWidget > QWidget {{
            background-color: transparent;
        }}

        

        QDialog#AdvancedMetadataDialog QFrame {{
            background-color: transparent; /* Allows the Dialog's _C['bg'] to show through */
        }}

        /* Section cards */
        QDialog#AdvancedMetadataDialog QFrame#card {{
            background-color: {_C['surface']};
            border:           1px solid {accent};
            border-radius:    8px;
        }}


        /* Navigation Buttons */
        QPushButton#nav_button {{
            text-align: left;
            padding: 12px 16px;
            border: none;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            background-color: transparent;
            color: #4a5568;
        }}
        
        QPushButton#nav_button:hover {{
            background-color: rgba(255, 255, 255, 0.08);
        }}
        
        QPushButton#nav_button:checked {{
            background-color: {accent};
            color: white;
            font-weight: 600;
        }}


        QDialog#AdvancedMetadataDialog QFrame#hr {{
            background-color: #edf2f7;
            max-height: 1px;
            border: none;
        }}

        /* ... labels and headers remain functionally identical ... */

        /* ── Section header labels ───────────────────────────────────────────────── */
        QDialog#AdvancedMetadataDialog QLabel#section_header {{
            color:       {accent};
            font-size:   11px;
            font-weight: 600;
            letter-spacing: 1.5px;
        }}

        /* ── Regular labels ──────────────────────────────────────────────────────── */
        QDialog#AdvancedMetadataDialog QLabel#title_header{{
            font-size:15px; 
            font-weight:700;
            color: {_C['text_primary']};
        }}
        
        QDialog#AdvancedMetadataDialog QLabel {{
            color:       {_C['text_label']};
            font-size:   12px;
        }}
        QDialog#AdvancedMetadataDialog QLabel#hint {{
            color:     {_C['text_muted']};
            font-size: 11px;
        }}

        /* ── Combo boxes ─────────────────────────────────────────────────────────── */
        QDialog#AdvancedMetadataDialog QComboBox:hover {{
            border-color:  {accent};
        }}
        QDialog#AdvancedMetadataDialog QComboBox:focus {{
            border-color:  {accent};
            outline: none;
        }}
        
        QDialog#AdvancedMetadataDialog QComboBox {{
            background-color: {_C['input_bg']};
            color:            {_C['text_primary']};
            border:           1px solid {_C['border']};
            border-radius:    5px;
            padding:          6px 10px;
        }}
        QDialog#AdvancedMetadataDialog QComboBox QAbstractItemView {{
            background-color: {_C['surface']};
            color:            {_C['text_primary']};
            border:           1px solid {_C['border']};
            selection-background-color: {_C['accent_dim']};
            selection-color:            {_C['accent']};
            outline: none;
        }}

        /* ── Checkboxes ───────────────────────────────────────────────────────────── */


        QDialog#AdvancedMetadataDialog QCheckBox {{
            color:       {_C['text_primary']};
            font-size:   13px;
            spacing:     8px;
        }}
        QDialog#AdvancedMetadataDialog QCheckBox::indicator {{
            width:  18px;
            height: 18px;
            border: 1.5px solid {_C['border']};
            border-radius: 4px;
            background-color: {_C['input_bg']};
        }}
        QDialog#AdvancedMetadataDialog QCheckBox::indicator:hover {{
            border-color: {accent};
        }}

        QDialog#AdvancedMetadataDialog QCheckBox::indicator:checked {{
            background-color:  {accent};
            border-color:      {accent};
            image: none;  /* rely on pure CSS fill */
        }}
        QDialog#AdvancedMetadataDialog QCheckBox:disabled {{
            color: {_C['text_muted']};
        }}
        QDialog#AdvancedMetadataDialog QCheckBox::indicator:disabled {{
            border-color:     {_C['border']};
            background-color: {_C['bg']};
        }}

        /* ── Buttons ─────────────────────────────────────────────────────────────── */
        QDialog#AdvancedMetadataDialog QPushButton#btn_apply {{
            background-color: {accent};
            color:            #ffffff;
            border-radius:    6px;
            font-weight:      600;
        }}

        QDialog#AdvancedMetadataDialog QPushButton#btn_apply:hover {{
            background-color: #3182ce; /* Slightly brighter than accent */
        }}

        /* ── Badge labels (Optimized for Light Mode) ──────────────────────────────── */
        QDialog#AdvancedMetadataDialog QLabel#badge_manual {{
            color:            {accent};
            background-color: {_C['accent_dim']}; /* Light blue background */
            border:           1px solid rgba(43, 108, 176, 0.2);
            border-radius:    3px;
            padding:          1px 6px;
            font-size:        10px;
        }}
        QDialog#AdvancedMetadataDialog QLabel#badge_auto {{
            color:            {_C['warn']};
            background-color: #fffaf0; /* Very faint orange */
            border:           1px solid rgba(221, 107, 32, 0.2);
            border-radius:    3px;
            padding:          1px 6px;
            font-size:        10px;
        }}
        QDialog#AdvancedMetadataDialog QLabel#no_subs {{
            color:            {_C['text_muted']};
            font-style:       italic;
            font-size:        12px;
        }}

        QDialog#AdvancedMetadataDialog QScrollArea {{
            border: none;
            background-color: transparent;
        }}


        QMainWindow {{
            background-color: #f4f5f7;
        }}
        QMainWindow::separator {{
            background: #f4f5f7;
            width: 1px;
            height: 1px;
            border: none;
        }}
        QMenuBar {{
            background-color: #ffffff;
            color: #202124;
            border-bottom: 1px solid #dadce0;
        }}
        QMenuBar::item {{
            background: transparent;
            padding: 4px 12px;
        }}
        QMenuBar::item:selected {{
            background: #e8eaed;
        }}
        QMenu {{
            background-color: #ffffff;
            color: #202124;
            border: 1px solid #dadce0;
        }}
        QMenu::item:selected {{
            background-color: #e8eaed;
        }}
        QMenu::item {{
            padding: 6px;
            padding-left: 4px;
            padding-right: 43px;
        }}
        QMenu::icon {{
            padding-right: 4px;
        }}
        QToolBar {{
            background-color: #f8f9fa;
            border-bottom: 1px solid #dadce0;
            spacing: 6px;
        }}
        QToolBar::separator {{
            width: 8px;
            background: transparent;
        }}
        QToolButton {{
            background: transparent;
            border-radius: 6px;
            padding: 6px 10px;
            color: #202124;
        }}
        QToolButton:hover {{
            background-color: #e8eaed;
        }}
        QLabel {{
            color: #202124;
        }}
        QLabel#PageTitle {{
            font-size: 20px;
            font-weight: 600;
        }}
        QLabel#InfoTitle {{
            font-size: 14px;
            font-weight: 600;
        }}
        QLabel#InfoBody {{
            font-size: 12px;
            color: #5f6368;
        }}
        QDockWidget {{
            background-color: #f4f5f7;
            color: black;
        }}
        QDockWidget::title {{
            padding: 6px 10px;
            background-color: #f4f5f7;
            color: #5f6368;
        }}
        QListWidget {{
            background-color: #ffffff;
            border-radius: 8px;
            padding: 4px;
            border: 1px solid #dadce0;
            color: #202124;
        }}
        QListWidget::item {{
            border-radius: 6px;
            padding: 6px 8px;
        }}
        QListWidget::item:selected {{
            background-color: {accent};
            color: white;
        }}
        QListWidget QScrollBar:vertical {{
            background: #f1f3f4;
        }}
        QListWidget QScrollBar::add-line:vertical,
        QListWidget QScrollBar::sub-line:vertical {{
            height: 0px;
            background: none;
            border: none;
        }}
        QTableView {{
            color: #202124;
        }}
        QTableWidget {{
            background-color: #ffffff;
            alternate-background-color: #f5f6f8;   /* slightly softer */
            border: 1px solid #dadce0;
            border-radius: 10px;
            color: #202124;
        }}
        QTableWidget::item:focus {{
            outline: none;
            border: none;
        }}
        QTableView::item:selected {{
            background-color: rgba(43, 128, 255, 0.25);
            color: black;
        }}
        QTableView QScrollBar:horizontal, QScrollBar:vertical {{
            background: #f1f3f4;
        }}
        QTableView QScrollBar::add-line:vertical,
        QTableView QScrollBar::sub-line:vertical {{
            height: 0px;
            background: none;
            border: none;
        }}
        QTableView QScrollBar::add-line:horizontal,
        QTableView QScrollBar::sub-line:horizontal {{
            height: 0px;
            background: none;
            border: none;
        }}

        QTableView::item:selected:active {{
            background-color: rgba(43, 128, 255, 0.25);
        }}


        /* Disable hover highlight */
        QTableView::item:hover {{
            background: transparent;
        }}

        /* Disable current item highlight */
        QTableView::item:selected:!active {{
            background: rgba(43, 128, 255, 0.25);
        }}

        QTableView::item:!selected {{
            background: transparent;
        }}

        /* Remove focus/current cell outline */
        QTableView::item:!active {{
            outline: none;
        }}


        QHeaderView::section {{
            background-color: #f8f9fa;
            border: none;
            border-bottom: 1px solid #dadce0;
            padding: 8px 6px;
            color: #5f6368;
        }}
        
        QProgressBar[downloadProgress="true"] {{
            border: 1px solid #dadce0;
            border-radius: 6px;
            text-align: center;
            background-color: #f4f5f7;
            padding: 1px;
        }}
        QProgressBar[downloadProgress="true"]::chunk {{
            border-radius: 6px;
            background-color: #1a73e8;
        }}
        QLineEdit, QComboBox, QTextEdit, QSpinBox,
        QDateTimeEdit, QPlainTextEdit {{
            background-color: #ffffff;
            border-radius: 6px;
            border: 1px solid #dadce0;
            padding: 6px 8px;
            color: #202124;
            selection-background-color: #1a73e8;
            selection-color: #ffffff;
        }}
        QPlainTextEdit {{
            border-radius: 8px;
        }}
        QLineEdit:focus, QComboBox:focus, QTextEdit:focus,
        QSpinBox:focus, QDateTimeEdit:focus {{
            border-color: {accent};
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background-color: #f8f9fa;
            color: #202124;
            selection-background-color: #e8f0fe;
            selection-color: #202124;
            border: 1px solid #dadce0;
        }}

        QStatusBar {{
            background-color: #ffffff;
            color: #5f6368;
        }}
        QDialog {{
            background-color: #fdfdfd;   /* slightly off-white */
        }}
        QPushButton {{
            background-color: {accent};
            color: white;
            padding: 6px 14px;
            border-radius: 6px;
            border: none;
        }}
        QPushButton:hover {{
            background-color: #1765cc;
        }}
        QPushButton:disabled {{
            background-color: #dadce0;
            color: #80868b;
        }}
        QCheckBox {{
            color: #202124;
        }}
        /* Tabs (light theme) – more contrast between active/inactive */
        QTabWidget::pane {{
            border: 1px solid #dadce0;
            border-radius: 8px;
            padding: 4px;
            margin-top: -2px; /* let tabs sit slightly over the pane */
            background-color: #ffffff;
        }}

        QTabBar::tab {{
            background-color: #e8eaed;          /* clearly different from pane */
            color: #5f6368;
            padding: 6px 14px;
            margin-right: 2px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            border: 1px solid #dadce0;
            border-bottom: none;                /* look like it's attached to pane */
            min-height: 26px;
        }}

        QTabBar::tab:selected {{
            background-color: #ffffff;
            color: #202124;
            font-weight: 600;
            border-color: #1a73e8 #dadce0 #ffffff #dadce0; /* blue top border */
            margin-top: 0px;
        }}

        QTabBar::tab:!selected {{
            margin-top: 2px;                    /* appear slightly "lower" */
        }}

        QTabBar::tab:hover {{
            background-color: #f1f3f4;
        }}

        QLineEdit, QComboBox, QTextEdit, QSpinBox,
        QDateTimeEdit, QPlainTextEdit {{
            background-color: #fdfdfd;   /* not pure white */
            border-radius: 6px;
            border: 1px solid #dadce0;
            padding: 6px 8px;
            color: #202124;
            selection-background-color: #1a73e8;
            selection-color: #ffffff;
        }}
        /* --- Details dialog (light theme) --- */
        QDialog#DetailsDialog {{
            background-color: #ffffff;
            border: 1px solid #dadce0;
            border-radius: 10px;
        }}
        QWidget#DetailsHeaderBar {{
            background-color: #f1f3f4;
            border-radius: 8px;
        }}
        QLabel#DetailsHeaderIcon {{
            font-size: 16px;
        }}
        QLabel#DetailsHeaderTitle {{
            font-size: 13px;
            font-weight: 600;
            color: #202124;
        }}
        /* === Schedule dialog (light theme) === */
        QDialog#ScheduleDialog {{
            background-color: #ffffff;
            border-radius: 10px;
            border: 1px solid #dadce0;
        }}

        /* Calendar – make it clearly light */
        QDialog#ScheduleDialog QCalendarWidget {{
            background-color: #ffffff;
            border: 1px solid #dadce0;
            border-radius: 8px;
            selection-background-color: #1a73e8;
            selection-color: #ffffff;
        }}

        /* Calendar header (month/year + arrows) */
        QDialog#ScheduleDialog QCalendarWidget QWidget#qt_calendar_navigationbar {{
            background-color: #f1f3f4;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }}

        QDialog#ScheduleDialog QCalendarWidget QToolButton {{
            background: transparent;
            border: none;
            padding: 2px 6px;
            color: #202124;
        }}
        QDialog#ScheduleDialog QCalendarWidget QToolButton:hover {{
            background-color: #e8eaed;
            border-radius: 4px;
        }}

        /* Calendar day cells */
        QDialog#ScheduleDialog QCalendarWidget QAbstractItemView {{
            background-color: #ffffff;
            color: #202124;
            selection-background-color: #1a73e8;
            selection-color: #ffffff;
            gridline-color: #e0e0e0;
        }}

        /* Summary label under time selector */
        QLabel#ScheduleSummaryLabel {{
            background-color: #f1f3f4;
            border-radius: 6px;
            padding: 6px 10px;
            color: #202124;
            font-size: 12px;
        }}
        /* === What's New dialog (light theme) === */
        QDialog#WhatsNewDialog {{
            background-color: #ffffff;
            border-radius: 10px;
            border: 1px solid #dadce0;
        }}

        QFrame#WhatsNewCard {{
            background-color: #f8f9fa;
            border-radius: 10px;
            border: 1px solid #dadce0;
        }}

        QLabel#WhatsNewTitleLabel {{
            font-size: 14px;
            font-weight: 600;
            color: #202124;
        }}

        QLabel#WhatsNewPositionLabel {{
            font-size: 11px;
            color: #5f6368;
        }}

        QLabel#WhatsNewVersionLabel,
        QLabel#WhatsNewDateLabel {{
            font-size: 12px;
            font-weight: 500;
            color: #202124;
        }}

        QLabel#WhatsNewHighlightsTitle,
        QLabel#WhatsNewDetailsTitle {{
            font-size: 12px;
            font-weight: 600;
            color: #202124;
        }}

        QLabel#WhatsNewHighlightsLabel {{
            font-size: 12px;
            color: #3c4043;
        }}

        QTextEdit#WhatsNewDetailsText {{
            background-color: #ffffff;
            border-radius: 6px;
            border: 1px solid #dadce0;
            font-size: 12px;
            color: #3c4043;
        }}
        QTableWidget#DownloadsTable QProgressBar {{
            min-height: 26px;
            max-height: 38px;
        }}

        /* --- IDM-style flat dialog buttons (LIGHT THEME) --- */

        QWidget#AddDownloadWindow {{
            background-color: #f4f5f7;
        }}

        QWidget#AddDownloadWindow QPushButton {{
            background: #f2f2f2;
            color: #1f1f1f;
            border: 1px solid #c8c8c8;
            border-radius: 4px;
            padding: 6px 14px;
            min-width: 70px;
            font-size: 13px;
        }}

        /* Hover: slightly brighter grey 
        QWidget#AddDownloadWindow QPushButton:hover {{
            background: #33363b;
            border: 1px solid #4a4d52;
        }}
        */

        /* Pressed: darker grey */
        QWidget#AddDownloadWindow QPushButton:pressed {{
            background: #dcdcdc;
            border: 1px solid {accent};
            padding-top: 7px;
        }}

        /* Default/active button = blue border */
        QWidget#AddDownloadWindow QPushButton:default {{
            border: 1px solid {accent};
            color: black;
        }}

        QWidget#AddDownloadWindow, QComboBox:focus, QLineEdit::focus {{
            border-color: {accent};
        }}

    
        QDialog#DownloadProgressDialog QProgressBar::chunk {{
            background-color: {accent};
        }}
        

        QDialog QPushButton {{
            background: #f2f2f2;
            color: #1f1f1f;
            border: 1px solid #c8c8c8;
            border-radius: 4px;
            padding: 6px 14px;
            min-width: 70px;
            font-size: 13px;
        }}

        /* Hover: slightly darker grey */
        QDialog QPushButton:hover {{
            background: #f2f2f2;
            border: 1px solid #b8b8b8;
        }}

        /* Pressed: deeper flat shade */
        QDialog QPushButton:pressed {{
            background: #dcdcdc;
            border: 1px solid #a8a8a8;
            padding-top: 7px;  /* press effect */
        }}

        /* Default/active button = blue border (IDM behavior) */
        QDialog QPushButton:default {{
            border: 1px solid {accent};
            color: black;
        }}

        QProgressBar {{
            border: none;
            background: transparent;
        }}

        QProgressBar::chunk {{
            background-color: #3b82f6; /* blue */
            border-radius: 3px;
        }}

        QLabel#DownloadThumbnail {{
            border: 1px solid rgba(0,0,0,40); 
            border-radius: 6px; "
            background: rgba(0,0,0,5%);
        }}
    
        
    


        
    """

    return css


def get_stylesheet(theme: str = "dark") -> str:
    """
    Get the stylesheet for the given theme.
    
    Args:
        theme: "dark" or "light"
    
    Returns:
        QSS stylesheet string
    """
    if theme.lower() == "light":
        return get_light_theme()
    else:
        return get_dark_theme()