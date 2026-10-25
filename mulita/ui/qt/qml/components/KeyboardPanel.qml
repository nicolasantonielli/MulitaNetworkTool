import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

// Teclado dentro de la misma ventana. El plugin Qt Virtual Keyboard abre otra
// ventana y EGLFS aborta con "OpenGL windows cannot be mixed with others".
Rectangle {
    id: root

    property Item field: null
    property bool caps: false
    property bool typing: false
    property double typedAt: 0
    readonly property bool active: field !== null
    readonly property int keyHeight: Math.round(ui.touch * 0.82)
    readonly property var rows: [
        ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
        ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
        ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
        ["z", "x", "c", "v", "b", "n", "m", ".", "-", "_"]
    ]

    function glyph(letter) {
        if (caps && letter >= "a" && letter <= "z")
            return letter.toUpperCase()
        return letter
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
        if (typing || !item || isInside(item))
            return
        var target = keyboardItem(item)
        if (target)
            field = target
    }

    function remember() {
        var win = Window.window
        if (win)
            follow(win.activeFocusItem)
    }

    function type(ch) {
        var item = field
        if (!item || !ch)
            return
        typedAt = Date.now()
        typing = true
        var current = item.text || ""
        var pos = item.cursorPosition
        if (pos === undefined || pos < 0 || pos > current.length)
            pos = current.length
        var next = current.substring(0, pos) + ch + current.substring(pos)
        if (item.insert)
            item.insert(pos, ch)
        if ((item.text || "") === current)
            item.text = next
        if ((item.text || "").charAt(pos) === ch)
            item.cursorPosition = pos + ch.length
        typing = false
    }

    function backspace() {
        var item = field
        if (!item)
            return
        typing = true
        if (item.selectionStart !== undefined && item.selectionStart !== item.selectionEnd)
            item.remove(item.selectionStart, item.selectionEnd)
        else if (item.cursorPosition > 0)
            item.remove(item.cursorPosition - 1, item.cursorPosition)
        typing = false
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
            model: root.rows

            delegate: Row {
                readonly property int row: index
                readonly property var letters: root.rows[row]

                Layout.fillWidth: true
                Layout.preferredHeight: root.keyHeight
                Layout.maximumHeight: root.keyHeight
                spacing: Math.round(ui.gap * 0.3)
                height: root.keyHeight

                Repeater {
                    model: letters

                    delegate: Rectangle {
                        readonly property string letter: modelData

                        width: (parent.width - parent.spacing * (letters.length - 1)) / letters.length
                        height: root.keyHeight
                        radius: ui.radius
                        clip: true
                        color: keyArea.pressed ? ui.surfaceHigh : ui.surfaceAlt

                        Text {
                            anchors.centerIn: parent
                            text: root.glyph(letter)
                            color: ui.text
                            font.pixelSize: Math.min(ui.fontBody, root.keyHeight * 0.55)
                            font.weight: Font.DemiBold
                        }
                        TouchArea {
                            id: keyArea
                            onPressed: root.type(root.glyph(letter))
                        }
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
                onClicked: {
                    if (Date.now() - root.typedAt < 500)
                        return
                    root.caps = !root.caps
                }
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
                    root.caps = false
                    if (root.field)
                        root.field.focus = false
                    root.field = null
                }
            }
        }
    }
}
