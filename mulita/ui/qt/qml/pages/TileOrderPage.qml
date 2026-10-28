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
    // Copia propia. La lista que viene de la configuracion no se usa como modelo
    // mientras el dedo la arrastra: si no, la vista la reconstruye y los cuadros se van.
    property var rows: []

    readonly property var order: {
        var stored = settings.tileOrder || ({})
        var list = stored[group]
        return list && list.length ? list : []
    }

    function readOrder() {
        var copy = []
        for (var i = 0; i < order.length; ++i)
            copy.push(String(order[i]))
        return copy
    }

    onOrderChanged: if (!dragging) rows = readOrder()
    onGroupChanged: Qt.callLater(function() { if (!root.dragging) root.rows = root.readOrder() })
    Component.onCompleted: rows = readOrder()

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
        if (from === to || from < 0 || to < 0 || from >= rows.length || to >= rows.length)
            return
        var next = []
        for (var i = 0; i < rows.length; ++i)
            next.push(rows[i])
        var moved = next.splice(from, 1)[0]
        next.splice(to, 0, moved)
        rows = next
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

    Item {
        id: board

        readonly property real gap: Math.round(ui.gap * 0.35)
        readonly property real rowHeight: root.rows.length > 0 ? height / root.rows.length : ui.touch

        Layout.fillWidth: true
        Layout.fillHeight: true

        Column {
            id: column
            width: parent.width

            Repeater {
                id: orderTiles
                objectName: "orderTiles"
                model: root.rows

                delegate: Item {
                    id: slot

                    objectName: "orderRow"
                    width: column.width
                    height: board.rowHeight
                    z: dragArea.pressed ? 2 : 0

                    Rectangle {
                        id: card

                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: Math.max(ui.fontBody * 1.8, parent.height - board.gap)
                        radius: ui.radius
                        color: dragArea.pressed ? ui.surfaceHigh : ui.surface
                        border.width: dragArea.pressed ? 2 : 1
                        border.color: dragArea.pressed ? ui.primary : ui.border

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

                            property real origin: 0
                            readonly property real slop: Math.max(8, ui.mm * 2)

                            anchors.fill: parent
                            preventStealing: true

                            onPressed: {
                                origin = mapToItem(column, mouse.x, mouse.y).y
                                root.dragging = true
                            }
                            onPositionChanged: {
                                if (!pressed)
                                    return
                                var delta = mapToItem(column, mouse.x, mouse.y).y - origin
                                var minY = -index * slot.height
                                var maxY = (root.rows.length - 1 - index) * slot.height
                                card.y = Math.max(minY, Math.min(maxY, delta))
                            }
                            onReleased: finish()
                            onCanceled: finish()

                            function finish() {
                                var step = slot.height
                                var slots = step > 0 && Math.abs(card.y) >= slop
                                        ? Math.round(card.y / step) : 0
                                var destination = Math.max(0, Math.min(root.rows.length - 1, index + slots))
                                card.y = 0
                                root.dragging = false
                                root.moveTile(index, destination)
                            }
                        }
                    }
                }
            }
        }
    }
}
