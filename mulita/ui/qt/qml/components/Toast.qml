import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root

    property bool shown: false
    property string kind: "info"
    property string title: ""
    property string message: ""
    readonly property color accent: kind === "error" ? ui.danger : kind === "success" ? ui.success : ui.primary

    width: Math.min(parent.width - ui.padding * 2, ui.mm * 110)
    height: content.implicitHeight + ui.padding * 1.4
    anchors.horizontalCenter: parent.horizontalCenter
    y: shown ? ui.gap : -height
    opacity: shown ? 1 : 0
    visible: opacity > 0
    z: 50
    radius: ui.radius * 1.4
    color: ui.surfaceHigh
    border.width: 1
    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.6)

    Behavior on y { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
    Behavior on opacity { NumberAnimation { duration: 200 } }

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.margins: ui.gap * 0.6
        width: Math.max(3, ui.mm * 1)
        radius: width / 2
        color: root.accent
    }

    ColumnLayout {
        id: content
        anchors.verticalCenter: parent.verticalCenter
        x: ui.padding * 1.4
        width: root.width - ui.padding * 2.4
        spacing: Math.round(ui.gap * 0.3)

        Text {
            visible: root.title !== ""
            text: root.title
            color: ui.text
            font.pixelSize: ui.fontBody
            font.weight: Font.Bold
        }
        Text {
            Layout.fillWidth: true
            text: root.message
            color: ui.textMuted
            font.pixelSize: ui.fontSmall
            wrapMode: Text.Wrap
            maximumLineCount: 4
            elide: Text.ElideRight
        }
    }

    TouchArea {
        onTapped: root.shown = false
    }

    Timer {
        id: hideTimer
        interval: 4500
        onTriggered: root.shown = false
    }

    Connections {
        target: notifier

        function onNotified(kind, title, message) {
            root.kind = kind
            root.title = title
            root.message = message
            root.shown = true
            hideTimer.restart()
        }
    }
}
