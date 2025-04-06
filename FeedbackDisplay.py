import os

from cura.CuraApplication import CuraApplication
from UM.Logger import Logger

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, QTimer
from PyQt6.QtQuick import QQuickItem

DEBUG_MODE = False

def log(level: str, message: str) -> None:
    """Wrapper function for logging messages using Cura's Logger, but with debug mode so as not to spam you."""
    if level == "d" and DEBUG_MODE:
        Logger.log("d", message)
    elif level == "dd":
        Logger.log("d", message)
    elif level == "i":
        Logger.log("i", message)
    elif level == "w":
        Logger.log("w", message)
    elif level == "e":
        Logger.log("e", message)
    elif DEBUG_MODE:
        Logger.log("w", f"Invalid log level: {level} for message {message}")

class FeedbackDisplay(QObject):
    
    def __init__(self, parent = None):
        super().__init__(parent)
        log("d", "FeedbackDisplay __init__() just passed super()")
        self._message = ""
        self._timeout = 0
        self._visible = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.hide_feedback)
        log("d", f"feedbackDisplay __init__() just created QTimer {repr(self._timer)}")
        
        self._display_ui = None
        self._display_qml = os.path.abspath(os.path.join(os.path.dirname(__file__), "qml", "FeedbackDisplay.qml"))
        log("d", f"FeedbackDisplay __init__() display_qml = {self._display_qml} at end")
        
    def _show_ui(self) -> None:
        log("d", f"_show_ui start and display_ui = {self._display_ui}")
        if self._display_ui is None:
            self._create_ui()
        log("d", f"_show_ui ran create_ui and display_ui = {self._display_ui}")
        self.setVisible(True)
        log("d", f"_show_ui is at end")
    
    def _create_ui(self) -> None:
        log("d", f"_create_ui start and display_ui = {self._display_ui}")
        try:
            ui_context = {
                "feedbackObject": self,
            }
            self._display_ui = CuraApplication.getInstance().createQmlComponent(self._display_qml, ui_context)
            log("d", f"_create_ui just made display_ui = {self._display_ui}")
        except Exception as e:
            log("e", e)

        log("d", f"_create_ui ending after showing {self._display_ui}")
    
    messageChanged = pyqtSignal(str)
    
    def setMessage(self, value: str) -> None:
        log("d", f"setMessage start with self._message = {self._message} and value = {value}")
        self._message = value
        self.messageChanged.emit(self._message)
        log("d", f"setMessage ending with self._message = {self._message}")
        
    @pyqtProperty(str, fset=setMessage, notify=messageChanged)
    def message(self) -> str:
        log("d", f"message getter ran with self._message = {self._message}")
        return self._message
    
    timeoutChanged = pyqtSignal(int)
    
    def setTimeout(self, value: int) -> None:
        log("d", f"setTimeout start with self._timeout = {self._timeout} and value = {value}")
        self._timeout = value
        self.timeoutChanged.emit(self._timeout)
        self._timer.start(self._timeout)
        log("d", f"setTimeout ending with self._timeout = {self._timeout} and self._timer = {self._timer}")
    
    @pyqtProperty(str, fset=setTimeout, notify=timeoutChanged)
    def timeout(self) -> int:
        log("d", f"timeout getter ran with self._timeout= {self._timeout}")
        return self._timeout
    
    visibleChanged = pyqtSignal(bool)
    
    def setVisible(self, value: bool) -> None:
        log("d", f"setVisible start with self._visible = {self._visible} and value = {value}")
        self._visible = value
        self.visibleChanged.emit(self._visible)
        if self.visible:
            self._display_ui.show()
        else:
            self._display_ui.close()
        #log("d", f"setVisible ending with self._visible = {self._visible}")

    @pyqtProperty(bool, fset=setVisible, notify=visibleChanged)
    def visible(self) -> bool:
        #log("d", f"visible getter ran with self._visible = {self._visible}")
        return self._visible
    
    def hide_feedback(self):
        log("d", f"hide_feedback starting")
        self.setVisible(False)
        self._display_ui.close()
        log("d", f"hide_feedback just used setVisible() - self._visible = {self._visible}")
        self._timer.stop()
        log("d", f"hide_feedback ending by stopping timer, self._timer = {repr(self._timer)}")
        
    def show_feedback(self, message, timeout=15000) -> None:
        log("d", f"show_feedback run with message {message} and timeout {timeout}")
        self.setMessage(message)
        log("d", f"show_feedback just ran self.setMessage() - self._message = {self._message}")
        self.setTimeout(timeout)
        log("d", f"show_feedback just ran setTimeout(). self._timeout = {self.timeout}")
        if self._display_ui is not None:
            self._display_ui.destroy()
        if self._display_ui is None:
            log("d", f"show_feedback in display_ui is None block")
            self._show_ui()
            log("d", f"show_feedback just created display_ui = {self._display_ui}")
        self._display_ui.show()
        log("d", f"show_feedback ending")
