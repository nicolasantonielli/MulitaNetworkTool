import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// Confirmacion para acciones irreversibles. `countdown` > 0 revierte solo al vencer.
Popup {
    id: root

    property string title: ""
    property string message: ""
    property string kind: "danger"
    property string confirmText: "Confirmar"
    property string cancelText: "Cancelar"
    property int countdown: 0
    property int remaining: 0
    property var confirmAction: null
    property var cancelAction: null

    function ask(options) {
        title = options.title || ""
        message = options.message || ""
        kind = options.kind || "danger"
        confirmText = options.confirmText || "Confirmar"
        cancelText = options.cancelText || "Cancelar"
        countdown = options.countdown || 0
        remaining = countdown
        confirmAction = options.confirmAction || null
        cancelAction = options.cancelAction || null
        open()
    }

    function finish(confirmed) {
        var action = confirmed ? confirmAction : cancelAction
        confirmAction = null
        cancelAction = null
        close()
        if (action)
            action()
    }

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(parent.width - ui.padding * 4, ui.mm * 100)
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape
    padding: Math.round(ui.padding * 1.3)

    background: Rectangle {
        color: ui.surface
        radius: ui.radius * 1.6
        border.width: 1
        border.color: ui.border
    }

    Overlay.modal: Rectangle { color: "#A0000000" }

    contentItem: ColumnLayout {
        spacing: ui.gap

        Text {
            Layout.fillWidth: true
            text: root.title
            color: ui.text
            font.pixelSize: ui.fontTitle
            font.weight: Font.Bold
            wrapMode: Text.Wrap
        }
        Text {
            Layout.fillWidth: true
            text: root.countdown > 0 ? root.message + "\n\nSe revierte en " + root.remaining + " s." : root.message
            color: ui.textMuted
            font.pixelSize: ui.fontBody
            wrapMode: Text.Wrap
        }
        RowLayout {
            Layout.topMargin: ui.gap
            spacing: ui.gap

            TouchButton {
                Layout.fillWidth: true
                text: root.cancelText
                kind: "neutral"
                onClicked: root.finish(false)
            }
            TouchButton {
                Layout.fillWidth: true
                text: root.confirmText
                kind: root.kind
                onClicked: root.finish(true)
            }
        }
    }

    Timer {
        interval: 1000
        repeat: true
        running: root.opened && root.countdown > 0
        onTriggered: {
            root.remaining -= 1
            if (root.remaining <= 0)
                root.finish(false)
        }
    }
}
