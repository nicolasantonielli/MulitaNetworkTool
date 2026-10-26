import QtQuick 2.15

// Mantener copia el valor completo; arrastrar sigue desplazando la tabla.
Text {
    id: root
    objectName: "copyableCell"
    textFormat: Text.PlainText

    MouseArea {
        anchors.fill: parent
        enabled: root.text.length > 0
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        preventStealing: false
        pressAndHoldInterval: 600
        onPressAndHold: if (mouse.button === Qt.LeftButton) system.copyText(root.text)
        onClicked: if (mouse.button === Qt.RightButton) system.copyText(root.text)
    }
}
