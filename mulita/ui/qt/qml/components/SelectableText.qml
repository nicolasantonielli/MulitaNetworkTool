import QtQuick 2.15

// Texto de solo lectura que se puede marcar con el cursor. La seleccion se copia sola.
TextEdit {
    id: root

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

    Layout.fillWidth: true
    height: contentHeight
    implicitHeight: Math.max(contentHeight, font.pixelSize)

    onSelectedTextChanged: if (selectedText.length > 0) copy()
}
