import QtQuick 2.15
import QtQuick.Controls 2.15

Popup {
    id: root
    objectName: "textCopyMenu"
    property string value: ""

    parent: Overlay.overlay
    z: 2000000
    modal: true
    dim: false
    focus: false
    closePolicy: Popup.CloseOnPressOutside | Popup.CloseOnEscape
    padding: Math.round(ui.gap * 0.5)
    width: Math.min(parent.width - ui.gap * 2, Math.max(ui.touch * 2.5, copyButton.implicitWidth + padding * 2))

    onAboutToShow: textCopy.setMenuVisible(true)
    onClosed: {
        value = ""
        textCopy.setMenuVisible(false)
    }

    background: Rectangle {
        color: ui.surface
        border.color: ui.border
        radius: ui.radius
    }
    contentItem: TouchButton {
        id: copyButton
        objectName: "textCopyAction"
        text: i18n.pack.copy
        kind: "neutral"
        onClicked: {
            var chosen = root.value
            root.close()
            system.copyText(chosen)
        }
    }
    Connections {
        target: textCopy
        function onRequested(text, screenX, screenY) {
            root.value = text
            var point = root.parent.mapFromGlobal(screenX, screenY)
            root.x = Math.max(ui.gap, Math.min(point.x, root.parent.width - root.width - ui.gap))
            var top = point.y - root.height - ui.gap
            if (top < ui.gap)
                top = point.y + ui.gap
            root.y = Math.max(ui.gap, Math.min(top, root.parent.height - root.height - ui.gap))
            root.open()
        }
    }
}
