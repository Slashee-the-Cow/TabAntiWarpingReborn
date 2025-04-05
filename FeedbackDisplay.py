import os

from cura.CuraApplication import CuraApplication

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, QTimer

class FeedbackDisplay(QObject):
    
    def __init__(self, parent = None):
        super().__init__(parent)
        
        self._message = ""
        self._timeout = 0
        self._visible = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.hide_feedback)
        
        self._display_ui = None
        self._display_qml = os.path.abspath(os.path.join(os.path.dirname(__file__), "qml", "FeedbackDisplay.qml"))
        
    def _show_ui(self) -> None:
        if self.display_ui is None:
            self._create_ui()
        self.setVisible(True)
    
    def _create_ui(self) -> None:
        ui_context = {
            "feedbackObject": self
        }
        self._display_ui = CuraApplication.getInstance().createQmlComponent(self._display_qml, ui_context)
        self._display_ui.setParent(CuraApplication.getInstance().getMainWindow())
    
    messageChanged = pyqtSignal(str)
    
    def setMessage(self, value: str) -> None:
        self._message = value
        self.messageChanged.emit(self._message)
        
    @pyqtProperty(str, fset=setMessage, notify=messageChanged)
    def message(self) -> str:
        return self._message
    
    timeoutChanged = pyqtSignal(int)
    
    def setTimeout(self, value: int) -> None:
        self._timeout = value
        self.timeoutChanged.emit(self._timeout)
        self._timer.start(self._timeout)
    
    @pyqtProperty(str, fset=setTimeout, notify=timeoutChanged)
    def timeout(self) -> int:
        return self._timeout
    
    visibleChanged = pyqtSignal(bool)
    
    def setVisible(self, value: bool) -> None:
        self._visible = value
        self.visibleChanged.emit(self._visible)

    @pyqtProperty(bool, fset=setVisible, notify=visibleChanged)
    def visible(self) -> bool:
        return self._visible
    
    def hide_feedback(self):
        self.setVisible(False)
        self._timer.stop()
        
    def show_feedback(self, message, timeout=15000) -> None:
        self._message = message
        self.setTimeout(timeout)
        if self._display_ui is None:
            self.show_ui()
