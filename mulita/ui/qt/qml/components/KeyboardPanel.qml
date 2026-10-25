import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

// Teclado dentro de la misma ventana. El plugin Qt Virtual Keyboard abre otra
// ventana y EGLFS aborta con "OpenGL windows cannot be mixed with others".
Rectangle {
    id: root

    property Item field: null
    property bool caps: false
    property bool symbols: false
    property bool typing: false
    property double typedAt: 0
    readonly property bool active: field !== null
    readonly property bool symbolField: field && field.symbolKeys === true
    readonly property int keyHeight: Math.round(ui.touch * 0.82)
    readonly property var letterKeys: [
        "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
        "q", "w", "e", "r", "t", "y", "u", "i", "o", "p",
        "a", "s", "d", "f", "g", "h", "j", "k", "l", "",
        "z", "x", "c", "v", "b", "n", "m", ".", "-", "_"
    ]
    readonly property var symbolKeys: [
        "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
        "!", "@", "#", "$", "%", "^", "&", "*", "(", ")",
        "'", "\"", "`", "~", "=", "+", "[", "]", "{", "}",
        "\\", "|", ";", ":", "<", ">", ",", ".", "/", "?"
    ]
    readonly property var keys: symbolField && symbols ? symbolKeys : letterKeys

    onFieldChanged: {
        caps = false
        symbols = false
    }

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
        if (typing)
            return
        if (item && isInside(item))
            return
        var target = item ? keyboardItem(item) : null
        if (target) {
            field = target
            return
        }
        if (field)
            dismiss()
    }

    function dismiss() {
        caps = false
        var item = field
        field = null
        if (item)
            item.focus = false
    }

    // El toque llega al velo que tapa la ventana. Hay que mirar tambien lo que
    // queda debajo (un rectangulo no se queda el toque) para no cerrar cuando
    // ahi hay un campo de texto.
    function itemUnder(x, y) {
        var hits = []
        var overlay = Overlay.overlay
        collect(overlay, x, y, hits)
        var page = overlay.parent
        var mapped = overlay.mapToItem(page, x, y)
        collect(page, mapped.x, mapped.y, hits)
        var fallback = null
        for (var i = 0; i < hits.length; ++i) {
            var hit = hits[i]
            if (hit === overlay || hit === page)
                continue
            if (!fallback)
                fallback = hit
            if (isInside(hit) || keyboardItem(hit))
                return hit
        }
        return fallback
    }

    function collect(item, x, y, hits) {
        if (!item || !item.visible)
            return
        var stacked = []
        var kids = item.children
        for (var i = 0; i < kids.length; ++i) {
            var child = kids[i]
            if (!child || child === outside || child === Overlay.overlay || !child.visible)
                continue
            if (child.width <= 0 || child.height <= 0)
                continue
            var point = child.mapFromItem(item, x, y)
            if (point.x < 0 || point.y < 0 || point.x >= child.width || point.y >= child.height)
                continue
            stacked.push({ item: child, x: point.x, y: point.y, z: child.z, index: i })
        }
        stacked.sort(function(a, b) {
            if (a.z !== b.z)
                return b.z - a.z
            return b.index - a.index
        })
        for (var n = 0; n < stacked.length; ++n)
            collect(stacked[n].item, stacked[n].x, stacked[n].y, hits)
        hits.push(item)
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

    function copySelection() {
        var item = field
        if (!item || !item.copy || !item.text)
            return
        var hadSelection = item.selectedText && item.selectedText.length > 0
        if (!hadSelection && item.selectAll)
            item.selectAll()
        item.copy()
        if (!hadSelection && item.deselect)
            item.deselect()
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

    // Por encima de los avisos y por debajo de las teclas: un toque fuera de
    // un campo cierra el teclado y el toque sigue hasta el boton de abajo.
    MouseArea {
        id: outside
        parent: Overlay.overlay
        anchors.fill: parent
        z: 1000000
        visible: root.active
        enabled: root.active
        propagateComposedEvents: true
        onPressed: {
            var hit = root.itemUnder(mouse.x, mouse.y)
            if (!root.isInside(hit) && !root.keyboardItem(hit))
                root.dismiss()
            mouse.accepted = false
        }
        onReleased: mouse.accepted = false
        onClicked: mouse.accepted = false
    }

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

        RowLayout {
            Layout.fillWidth: true
            spacing: Math.round(ui.gap * 0.3)

            TouchButton {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.round(root.keyHeight * 0.72)
                text: "Copiar"
                kind: "neutral"
                onClicked: root.copySelection()
            }
            TouchButton {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.round(root.keyHeight * 0.72)
                text: "Pegar"
                kind: "neutral"
                onClicked: if (root.field && root.field.paste) root.field.paste()
            }
        }

        Item {
            id: keyGrid
            Layout.fillWidth: true
            readonly property real gap: Math.round(ui.gap * 0.3)
            readonly property real cell: Math.max(1, (width - 9 * gap) / 10)
            implicitHeight: root.keyHeight * 4 + gap * 3
            height: implicitHeight

            Repeater {
                model: root.keys

                delegate: Rectangle {
                    readonly property string letter: modelData
                    readonly property int slot: index

                    visible: letter !== ""
                    x: (slot % 10) * (keyGrid.cell + keyGrid.gap)
                    y: Math.floor(slot / 10) * (root.keyHeight + keyGrid.gap)
                    width: keyGrid.cell
                    height: root.keyHeight
                    radius: ui.radius
                    clip: true
                    color: keyArea.pressed ? ui.surfaceHigh : ui.surfaceAlt

                    Text {
                        anchors.centerIn: parent
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: root.caps && letter >= "a" && letter <= "z" ? letter.toUpperCase() : letter
                        color: ui.text
                        font.pixelSize: Math.min(ui.fontBody, root.keyHeight * 0.55)
                        font.weight: Font.DemiBold
                    }
                    TouchArea {
                        id: keyArea
                        enabled: letter !== ""
                        onPressed: {
                            var ch = letter
                            if (root.caps && ch >= "a" && ch <= "z")
                                ch = ch.toUpperCase()
                            root.type(ch)
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
                visible: root.symbolField
                Layout.preferredWidth: ui.touch * 2
                Layout.preferredHeight: root.keyHeight
                text: root.symbols ? "Letras" : "Signos"
                kind: root.symbols ? "success" : "neutral"
                onClicked: {
                    if (Date.now() - root.typedAt < 500)
                        return
                    root.symbols = !root.symbols
                    root.caps = false
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
                // En la clave estos signos estan en la pagina Signos.
                visible: !root.symbolField
                Layout.preferredWidth: ui.touch * 1.2
                Layout.preferredHeight: root.keyHeight
                text: "/"
                kind: "neutral"
                onClicked: root.type("/")
            }
            TouchButton {
                visible: !root.symbolField
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
