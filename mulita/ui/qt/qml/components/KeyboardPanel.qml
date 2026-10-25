import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

// Teclado dentro de la misma ventana. El plugin Qt Virtual Keyboard abre otra
// ventana y EGLFS aborta con "OpenGL windows cannot be mixed with others".
Rectangle {
    id: root

    property Item field: null
    property bool caps: false
    readonly property bool active: field !== null
    readonly property int keyHeight: Math.round(ui.touch * 0.82)

    onFieldChanged: if (!field) caps = false

    function shown(letter) {
        if (!caps || letter < "a" || letter > "z")
            return letter
        return letter.toUpperCase()
    }

    function accepts(item) {
        return item && item.insert !== undefined && item.cursorPosition !== undefined
    }

    function keyboardItem(item) {
        var current = item
        while (current) {
            if (current.takesKeyboard === true)
                return current
            current = current.parent
        }
        return null
    }

    function isInside(item) {
        var current = item
        while (current) {
            if (current === root)
                return true
            current = current.parent
        }
        return false
    }

    function follow(item) {
        if (!item || isInside(item))
            return
        var target = keyboardItem(item)
        field = target
    }

    function remember() {
        var win = Window.window
        if (win)
            follow(win.activeFocusItem)
    }

    function type(text) {
        var item = field
        if (!accepts(item))
            return
        item.forceActiveFocus()
        item.insert(item.cursorPosition, text)
    }

    function backspace() {
        var item = field
        if (!accepts(item))
            return
        item.forceActiveFocus()
        if (item.selectionStart !== undefined && item.selectionStart !== item.selectionEnd)
            item.remove(item.selectionStart, item.selectionEnd)
        else if (item.cursorPosition > 0)
            item.remove(item.cursorPosition - 1, item.cursorPosition)
    }

    color: ui.surface
    border.color: ui.border
    border.width: active ? 1 : 0
    visible: active
    // Un toque en un hueco del teclado no debe llegar al ojo de la clave.
    MouseArea {
        anchors.fill: parent
        z: -1
        onPressed: mouse.accepted = true
    }
    implicitHeight: active ? column.implicitHeight + ui.gap : 0
    height: implicitHeight

    Component.onCompleted: remember()
    Connections {
        target: Window.window
        onActiveFocusItemChanged: root.remember()
    }

    ColumnLayout {
        id: column
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Math.round(ui.gap * 0.4)
        spacing: Math.round(ui.gap * 0.35)
        visible: root.active

        Repeater {
            // El modelo no cambia con Mayus: si se reconstruye, el toque inserta otra cosa.
            model: ["1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm.-_"]

            delegate: RowLayout {
                Layout.fillWidth: true
                spacing: Math.round(ui.gap * 0.3)

                Repeater {
                    model: modelData.split("")

                    delegate: TouchButton {
                        readonly property string letter: modelData

                        Layout.fillWidth: true
                        Layout.preferredHeight: root.keyHeight
                        text: root.shown(letter)
                        kind: "neutral"
                        onClicked: root.type(root.shown(letter))
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Math.round(ui.gap * 0.3)

            TouchButton {
                Layout.preferredWidth: ui.touch * 1.7
                Layout.preferredHeight: root.keyHeight
                text: "Mayús"
                kind: root.caps ? "success" : "neutral"
                onClicked: root.caps = !root.caps
            }
            TouchButton {
                Layout.preferredWidth: ui.touch * 1.4
                Layout.preferredHeight: root.keyHeight
                icon: "back"
                kind: "neutral"
                onClicked: root.backspace()
            }
            TouchButton {
                Layout.fillWidth: true
                Layout.preferredHeight: root.keyHeight
                text: "espacio"
                kind: "neutral"
                onClicked: root.type(" ")
            }
            TouchButton {
                Layout.preferredWidth: ui.touch * 1.2
                Layout.preferredHeight: root.keyHeight
                text: "/"
                kind: "neutral"
                onClicked: root.type("/")
            }
            TouchButton {
                Layout.preferredWidth: ui.touch * 1.2
                Layout.preferredHeight: root.keyHeight
                text: ":"
                kind: "neutral"
                onClicked: root.type(":")
            }
            TouchButton {
                Layout.preferredWidth: ui.touch * 1.7
                Layout.preferredHeight: root.keyHeight
                icon: "close"
                kind: "neutral"
                onClicked: {
                    if (root.field)
                        root.field.focus = false
                    root.field = null
                }
            }
        }
    }
}
