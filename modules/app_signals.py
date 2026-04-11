from PySide6.QtCore import QObject, Signal

class AppSignals(QObject):
    force_exit_for_update = Signal()

app_signals = AppSignals()
