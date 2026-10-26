import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

TextField {
    id: root

    // El teclado de la ventana busca esta marca en el foco o en sus padres.
    readonly property bool takesKeyboard: true
    // La clave cambia el teclado a signos. Una direccion no los necesita.
    property bool symbolKeys: false
    // Ancho reservado a la derecha para otro icono, como el ojo de la clave.
    property real accessoryWidth: 0

    implicitHeight: ui.touch
    Layout.preferredHeight: ui.touch
    Layout.minimumHeight: ui.touch
    font.pixelSize: ui.fontBody
    color: ui.text
    placeholderTextColor: ui.textMuted
    selectionColor: ui.primary
    selectedTextColor: ui.onAccent
    leftPadding: ui.padding
    rightPadding: ui.padding + (clearButton.visible ? ui.touch : 0) + accessoryWidth
    topPadding: 0
    bottomPadding: 0
    verticalAlignment: TextInput.AlignVCenter
    selectByMouse: true
    persistentSelection: true
    inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText

    // El menu compartido ofrece copiar al terminar una seleccion.

    TapHandler {
        // Un arrastre selecciona. Solo un toque quieto enfoca el campo.
        gesturePolicy: TapHandler.DragThreshold
        onTapped: root.forceActiveFocus()
    }

    IconButton {
        id: clearButton
        visible: !root.readOnly && root.length > 0
        anchors.right: parent.right
        anchors.rightMargin: root.accessoryWidth
        anchors.verticalCenter: parent.verticalCenter
        icon: "close"
        iconColor: ui.textMuted
        onClicked: {
            root.clear()
            root.forceActiveFocus()
        }
    }

    background: Rectangle {
        implicitWidth: 120
        implicitHeight: ui.touch
        radius: ui.radius
        color: ui.surfaceAlt
        border.width: root.activeFocus ? 2 : 1
        border.color: root.activeFocus ? ui.primary : ui.border
    }
}
