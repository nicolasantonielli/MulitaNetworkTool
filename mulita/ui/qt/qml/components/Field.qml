import QtQuick 2.15
import QtQuick.Controls 2.15

TextField {
    id: root

    implicitHeight: ui.touch
    font.pixelSize: ui.fontBody
    color: ui.text
    placeholderTextColor: ui.textMuted
    selectionColor: ui.primary
    selectedTextColor: ui.onAccent
    leftPadding: ui.padding
    rightPadding: ui.padding
    topPadding: 0
    bottomPadding: 0
    verticalAlignment: TextInput.AlignVCenter
    selectByMouse: true
    inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText

    background: Rectangle {
        radius: ui.radius
        color: ui.surfaceAlt
        border.width: root.activeFocus ? 2 : 1
        border.color: root.activeFocus ? ui.primary : ui.border
    }
}
