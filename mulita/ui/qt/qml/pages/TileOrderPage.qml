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
    property bool animateMoves: true
    property int dragFrom: -1
    property int hover: -1
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
                    z: index === root.dragFrom ? 2 : 0

                    // Las filas que no se arrastran se corren un lugar para abrir el hueco.
                    readonly property real shift: {
                        if (root.dragFrom < 0 || index === root.dragFrom)
                            return 0
                        if (root.dragFrom < root.hover && index > root.dragFrom && index <= root.hover)
                            return -height
                        if (root.hover < root.dragFrom && index >= root.hover && index < root.dragFrom)
                            return height
                        return 0
                    }
                    property real slide: 0
                    onShiftChanged: slide = shift

                    Behavior on slide {
                        enabled: root.animateMoves
                        NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
                    }

                    Rectangle {
                        id: card

                        anchors.left: parent.left
                        anchors.right: parent.right
                        y: index === root.dragFrom ? dragArea.offset : slot.slide
                        height: Math.max(ui.fontBody * 1.8, parent.height - board.gap)
                        radius: ui.radius
                        color: index === root.dragFrom ? ui.surfaceHigh : ui.surface
                        border.width: index === root.dragFrom ? 2 : 1
                        border.color: index === root.dragFrom ? ui.primary : ui.border

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
                            property real offset: 0

                            anchors.fill: parent
                            preventStealing: true

                            onPressed: {
                                origin = mapToItem(column, mouse.x, mouse.y).y
                                offset = 0
                                root.dragFrom = index
                                root.hover = index
                                root.dragging = true
                            }
                            onPositionChanged: {
                                if (!pressed || slot.height <= 0)
                                    return
                                var delta = mapToItem(column, mouse.x, mouse.y).y - origin
                                var minY = -index * slot.height
                                var maxY = (root.rows.length - 1 - index) * slot.height
                                offset = Math.max(minY, Math.min(maxY, delta))
                                var destination = Math.round(index + offset / slot.height)
                                root.hover = Math.max(0, Math.min(root.rows.length - 1, destination))
                            }
                            onReleased: finish()
                            onCanceled: finish()

                            function finish() {
                                var from = index
                                var destination = root.hover < 0 ? from : root.hover
                                root.animateMoves = false
                                offset = 0
                                root.dragFrom = -1
                                root.hover = -1
                                root.dragging = false
                                root.moveTile(from, destination)
                                Qt.callLater(function() { root.animateMoves = true })
                            }
                        }
                    }
                }
            }
        }
    }
}
