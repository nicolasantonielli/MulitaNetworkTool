import QtQuick 2.15

// Boton tactil: area minima de 9 mm, respuesta visual inmediata y repeticion opcional al mantener.
Rectangle {
    id: root

    property string text: ""
    property string icon: ""
    property string kind: "primary"   // primary | success | danger | warning | neutral | ghost
    property bool autoRepeat: false
    signal clicked()

    readonly property color baseColor: kind === "success" ? ui.success
                                     : kind === "danger" ? ui.danger
                                     : kind === "warning" ? ui.warning
                                     : kind === "neutral" ? ui.surfaceHigh
                                     : kind === "ghost" ? "transparent"
                                     : ui.primary
    readonly property color foreground: kind === "neutral" || kind === "ghost" ? ui.text : ui.onAccent
    property bool _repeated: false

    readonly property int iconSize: Math.round(ui.icon * 0.9)
    readonly property int spacing: Math.round(ui.gap * 0.6)

    implicitHeight: ui.touch
    implicitWidth: Math.max(ui.touch, ui.padding * 2
                            + (icon !== "" ? iconSize : 0)
                            + (text !== "" ? label.implicitWidth : 0)
                            + (icon !== "" && text !== "" ? spacing : 0))
    radius: ui.radius
    color: area.pressed ? Qt.darker(baseColor, kind === "ghost" ? 1 : 1.18) : baseColor
    border.width: kind === "ghost" ? 1 : 0
    border.color: ui.border
    opacity: enabled ? 1 : 0.45
    scale: area.pressed ? 0.97 : 1

    Behavior on scale { NumberAnimation { duration: 90 } }
    Behavior on color { ColorAnimation { duration: 120 } }

    Row {
        anchors.centerIn: parent
        spacing: root.spacing

        Icon {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.icon !== ""
            name: root.icon
            color: root.foreground
            size: root.iconSize
        }
        Text {
            id: label
            anchors.verticalCenter: parent.verticalCenter
            visible: root.text !== ""
            text: root.text
            color: root.foreground
            font.pixelSize: ui.fontBody
            font.weight: Font.DemiBold
        }
    }

    MouseArea {
        id: area
        anchors.fill: parent
        enabled: root.enabled
        onPressed: root._repeated = false
        onClicked: if (!root._repeated) root.clicked()
    }

    Timer {
        id: repeater
        interval: 450
        repeat: true
        running: root.autoRepeat && area.pressed
        onTriggered: {
            interval = 60
            root._repeated = true
            root.clicked()
        }
        onRunningChanged: if (!running) interval = 450
    }
}
