import QtQuick 6.0
import QtQuick.Controls 6.0

import UM 1.5

Rectange {
    id: feedbackRect
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: 100
    width: parent.width * 0.5
    height: 100
    color: UM.Theme.getColor("detail_background")
    visible: feedbackObject.visible

    UM.Label {
        id: feedbackLabel
        anchors.centerIn: parent
        text: feedbackObject.message
        font.weight: Font.Bold
        font.pointSize: 12
        wrapMode: Text.Wrap
    }
}