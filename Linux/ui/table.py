from PySide6.QtWidgets import QTableWidget
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu


class DownloadTable(QTableWidget):
    def __init__(self, rows, columns, parent=None):
        super().__init__(rows, columns, parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_context_menu)

    def open_context_menu(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return

        row = index.row()
        menu = QMenu(self)

        resume = menu.addAction("▶ Resume")
        pause = menu.addAction("⏸ Pause")
        delete = menu.addAction("🗑 Delete")
        open_file = menu.addAction("📂 Open File")

        action = menu.exec_(self.mapToGlobal(pos))

        if action == resume:
            print(f"[Row {row}] Resume clicked")
        elif action == pause:
            print(f"[Row {row}] Pause clicked")
        elif action == delete:
            print(f"[Row {row}] Delete clicked")
        elif action == open_file:
            print(f"[Row {row}] Open File clicked")


