import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Popup {
    id: root
    objectName: "textCopyMenu"
    property string value: ""
    property real targetX: 0
    property real targetY: 0

    function place() {
        var point = parent.mapFromGlobal(targetX, targetY)
        x = Math.max(ui.gap, Math.min(point.x, parent.width - width - ui.gap))
        var top = point.y - height - ui.gap
        if (top < ui.gap)
            top = point.y + ui.gap
        y = Math.max(ui.gap, Math.min(top, parent.height - height - ui.gap))
    }

    parent: Overlay.overlay
    z: 2000000
    modal: true
    dim: false
    focus: false
    closePolicy: Popup.CloseOnPressOutside | Popup.CloseOnEscape
    padding: Math.round(ui.gap * 0.5)
    width: Math.min(parent.width - ui.gap * 2, Math.max(ui.touch * 2.5, copyButton.implicitWidth + padding * 2))

    onAboutToShow: textCopy.setMenuVisible(true)
    onHeightChanged: if (visible) place()
    onWidthChanged: if (visible) place()
    onClosed: {
        value = ""
        textCopy.setMenuVisible(false)
    }

    background: Rectangle {
        color: ui.surface
        border.color: ui.border
        radius: ui.radius
    }
    contentItem: ColumnLayout {
        spacing: Math.round(ui.gap * 0.5)
        TouchButton {
            id: copyButton
            objectName: "textCopyAction"
            Layout.fillWidth: true
            visible: root.value.length > 0
            text: i18n.pack.copy
            kind: "neutral"
            onClicked: {
                var chosen = root.value
                root.close()
                system.copyText(chosen)
            }
        }
        TouchButton {
            objectName: "textPasteAction"
            Layout.fillWidth: true
            visible: textCopy.editable
            enabled: textCopy.canPaste
            text: i18n.pack.kbPaste
            kind: "neutral"
            onClicked: {
                textCopy.paste()
                root.close()
            }
        }
    }
    Connections {
        target: textCopy
        function onRequested(text, screenX, screenY) {
            root.value = text
            root.targetX = screenX
            root.targetY = screenY
            root.place()
            root.open()
        }
    }
}
