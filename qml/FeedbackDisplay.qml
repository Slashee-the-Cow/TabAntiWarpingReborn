import QtQuick 6.0
import QtQuick.Controls 6.0

import UM 1.5 as UM
import Cura 1.1 as Cura

UM.Dialog {
    id: feedbackDialog
    minimumWidth: 300
    width: 300
    maximumWidth: 500
    height: childrenRect.height
    maximumHeight: 200
    x: 200
    y: 300
    color: UM.Theme.getColor("detail_background")
    modality: Qt.NonModal
    flags: Qt.Widget | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus | Qt.WindowStaysOnTopHint

    UM.Label {
        id: feedbackLabel
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: implicitHeight
        text: feedbackObject.message
        font.weight: Font.Bold
        font.pointSize: 14
        wrapMode: Text.Wrap
    }
}