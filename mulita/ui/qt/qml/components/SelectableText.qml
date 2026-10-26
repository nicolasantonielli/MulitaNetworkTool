import QtQuick 2.15
import QtQuick.Layouts 1.15

// Texto de solo lectura seleccionable; la copia se confirma en el menu compartido.
Item {
    id: root

    property alias text: edit.text
    property alias font: edit.font

    Layout.fillWidth: true
    implicitWidth: 10
    implicitHeight: Math.max(edit.contentHeight, edit.font.pixelSize)

    TextEdit {
        id: edit
        anchors.left: parent.left
        anchors.right: parent.right
        height: contentHeight
        readOnly: true
        selectByMouse: true
        selectByKeyboard: true
        persistentSelection: true
        wrapMode: TextEdit.Wrap
        textFormat: TextEdit.PlainText
        color: ui.text
        selectionColor: ui.primary
        selectedTextColor: ui.onAccent
        font.pixelSize: ui.fontBody
    }
}
