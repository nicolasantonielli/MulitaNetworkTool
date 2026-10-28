import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

// Reordena los cuadros del inicio arrastrandolos. El cambio se guarda al soltar.
ColumnLayout {
    id: root

    objectName: "tileOrderPage"
    signal goBack()

    property string group: "network"
    property bool dragging: false

    readonly property var order: {
        var stored = settings.tileOrder || ({})
        var list = stored[group]
        return list && list.length ? list : []
    }

    function labelOf(id) {
        var names = {
            capture: i18n.pack.homeCapture,
            traces: i18n.pack.homeTraces,
            tap: i18n.pack.homeTap,
            scan: i18n.pack.homeScan,
            tools: i18n.pack.homeTools,
            settings: i18n.pack.homeSettings,
            vuln: i18n.pack.cyberVuln,
            wifi: i18n.pack.cyberWifi,
            arp: i18n.pack.cyberArp,
            nmap: i18n.pack.cyberNmap,
            tls: i18n.pack.cyberTls,
            servers: i18n.pack.homeServers
        }
        return names[id] || id
    }

    function iconOf(id) {
        var names = {
            capture: "capture", traces: "trace", tap: "tap", scan: "scan",
            tools: "tools", settings: "settings", vuln: "bug", wifi: "wifi",
            arp: "shield", nmap: "scan", tls: "lock", servers: "server"
        }
        return names[id] || "info"
    }

    function moveTile(from, to) {
        if (from === to || from < 0 || to < 0 || from >= order.length || to >= order.length)
            return
        var next = order.slice()
        var moved = next.splice(from, 1)[0]
        next.splice(to, 0, moved)
        settings.setTileOrder(group, JSON.stringify(next))
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: ui.gap

        IconButton {
            icon: "back"
            onClicked: root.goBack()
        }
        Text {
            Layout.fillWidth: true
            text: i18n.pack.tileOrderTitle
            color: ui.text
            font.pixelSize: ui.fontTitle
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        TouchButton {
            text: i18n.pack.tileOrderReset
            icon: "refresh"
            kind: "neutral"
            onClicked: settings.resetTileOrder()
        }
    }

    ChoiceChips {
        Layout.fillWidth: true
        enabled: !root.dragging
        model: [
            { label: i18n.pack.homeNetwork, value: "network" },
            { label: i18n.pack.homeCyber, value: "cyber" }
        ]
        value: root.group
        onActivated: root.group = value
    }

    ListView {
        id: list

        readonly property real rowHeight: {
            if (height < 1 || count < 1)
                return ui.touch
            var gaps = spacing * Math.max(0, count - 1)
            return Math.max(ui.fontBody * 1.9, (height - gaps) / count)
        }

        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        spacing: Math.round(ui.gap * 0.35)
        boundsBehavior: Flickable.StopAtBounds
        interactive: !root.dragging
        model: root.order

        displaced: Transition {
            NumberAnimation { properties: "y"; duration: 140; easing.type: Easing.OutCubic }
        }

        delegate: Rectangle {
            id: row

            width: list.width
            height: list.rowHeight
            radius: ui.radius
            color: dragArea.drag.active ? ui.surfaceHigh : ui.surface
            border.width: dragArea.drag.active ? 2 : 1
            border.color: dragArea.drag.active ? ui.primary : ui.border
            z: dragArea.drag.active ? 2 : 0

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: ui.gap
                anchors.rightMargin: ui.gap
                spacing: ui.gap

                Column {
                    spacing: Math.round(ui.mm * 0.7)
                    Layout.alignment: Qt.AlignVCenter
                    Repeater {
                        model: 3
                        delegate: Rectangle {
                            width: Math.round(ui.mm * 3.2)
                            height: Math.max(2, Math.round(ui.mm * 0.45))
                            radius: height / 2
                            color: ui.textMuted
                        }
                    }
                }
                Icon {
                    name: root.iconOf(modelData)
                    color: ui.primary
                    size: Math.round(ui.icon * 0.85)
                }
                Text {
                    Layout.fillWidth: true
                    text: root.labelOf(modelData)
                    color: ui.text
                    font.pixelSize: ui.fontBody
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
            }

            MouseArea {
                id: dragArea
                anchors.fill: parent
                drag.target: row
                drag.axis: Drag.YAxis
                drag.minimumY: 0
                drag.maximumY: Math.max(0, (list.count - 1) * (row.height + list.spacing))
                preventStealing: true

                onPressed: root.dragging = true
                onReleased: {
                    var step = row.height + list.spacing
                    var destination = step > 0 ? Math.round(row.y / step) : index
                    destination = Math.max(0, Math.min(list.count - 1, destination))
                    row.y = 0
                    root.dragging = false
                    root.moveTile(index, destination)
                }
                onCanceled: {
                    row.y = 0
                    root.dragging = false
                }
            }
        }
    }
}
