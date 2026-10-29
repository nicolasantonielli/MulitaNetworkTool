import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

// Todas las filas juntas. Un separador abre cada pantalla (de 1 a 6 cuadros).
// El más del último separador agrega una pantalla, moviendo allí el último cuadro.
ColumnLayout {
    id: root

    objectName: "tileOrderPage"
    signal goBack()

    property bool dragging: false
    property bool animateMoves: true
    property int dragLine: -1
    property int hover: -1
    property string dragId: ""
    property var screens: []

    readonly property real rowH: Math.round(ui.touch * 0.92)
    readonly property real rowWidth: ui.windowWidth / 2
    readonly property bool canAdd: {
        var last = screens.length ? screens[screens.length - 1] : []
        return last.length >= 2
    }
    readonly property var lines: {
        var out = []
        for (var s = 0; s < screens.length; ++s) {
            out.push({ kind: "separator", screen: s, last: s === screens.length - 1, id: "" })
            var page = screens[s]
            for (var t = 0; t < page.length; ++t)
                out.push({ kind: "tile", screen: s, tileIndex: t, id: page[t], last: false })
        }
        return out
    }

    function copyScreens(source) {
        var stored = source || []
        var next = []
        for (var s = 0; s < stored.length; ++s) {
            var page = []
            var ids = stored[s] || []
            for (var i = 0; i < ids.length; ++i)
                page.push(String(ids[i]))
            if (page.length)
                next.push(page)
        }
        return next
    }

    function reload() {
        if (dragging)
            return
        screens = copyScreens(settings.tileOrder && settings.tileOrder.screens)
    }

    Component.onCompleted: reload()

    Connections {
        target: settings
        function onChanged() { root.reload() }
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
            servers: i18n.pack.homeServers,
            switchport: i18n.pack.switchTitle
        }
        return names[id] || id
    }

    function iconOf(id) {
        var names = {
            capture: "capture", traces: "trace", tap: "tap", scan: "scan",
            tools: "tools", settings: "settings", vuln: "bug", wifi: "wifi",
            arp: "shield", nmap: "scan", tls: "lock", servers: "server", switchport: "ethernet"
        }
        return names[id] || "info"
    }

    function save(next) {
        screens = next
        settings.setHomeScreens(JSON.stringify(next))
    }

    function addScreen() {
        if (!canAdd || dragging)
            return
        var next = copyScreens(screens)
        var last = next[next.length - 1].slice()
        var moved = last.pop()
        next[next.length - 1] = last
        next.push([moved])
        save(next)
        Qt.callLater(function() { flick.contentY = Math.max(0, flick.contentHeight - flick.height) })
    }

    function lineAt(y) {
        var index = Math.floor(y / rowH)
        if (index < 0)
            return 0
        if (index >= lines.length)
            return lines.length - 1
        return index
    }

    function moveTile(fromScreen, fromIndex, toScreen, toIndex) {
        var next = copyScreens(screens)
        if (fromScreen < 0 || toScreen < 0 || fromScreen >= next.length || toScreen >= next.length)
            return
        if (fromIndex < 0 || fromIndex >= next[fromScreen].length)
            return
        if (fromScreen !== toScreen && next[toScreen].length >= 6)
            return
        var page = next[fromScreen].slice()
        var id = page.splice(fromIndex, 1)[0]
        if (fromScreen === toScreen) {
            if (fromIndex < toIndex)
                toIndex -= 1
            toIndex = Math.max(0, Math.min(toIndex, page.length))
            page.splice(toIndex, 0, id)
            next[fromScreen] = page
            save(next)
            return
        }
        if (!page.length)
            next.splice(fromScreen, 1)
        else
            next[fromScreen] = page
        if (toScreen > fromScreen && !page.length)
            toScreen -= 1
        if (toScreen < 0 || toScreen >= next.length)
            return
        var dest = next[toScreen].slice()
        dest.splice(Math.max(0, Math.min(toIndex, dest.length)), 0, id)
        next[toScreen] = dest
        save(next)
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

    Flickable {
        id: flick
        objectName: "orderFlick"

        Layout.fillWidth: true
        Layout.fillHeight: true
        contentWidth: width
        contentHeight: column.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: !root.dragging
        flickableDirection: Flickable.VerticalFlick

        Column {
            id: column
            width: flick.width

            Repeater {
                id: orderTiles
                objectName: "orderTiles"
                model: root.lines

                delegate: Item {
                    id: slot

                    objectName: modelData.kind === "tile" ? "orderRow" : "orderSeparator"
                    width: column.width
                    height: root.rowH
                    z: index === root.dragLine ? 2 : 0

                    // Las filas que no se arrastran se corren para abrir el hueco.
                    readonly property real shift: {
                        if (root.dragLine < 0 || index === root.dragLine)
                            return 0
                        if (root.dragLine < root.hover && index > root.dragLine && index <= root.hover)
                            return -height
                        if (root.hover < root.dragLine && index >= root.hover && index < root.dragLine)
                            return height
                        return 0
                    }
                    property real slide: 0
                    onShiftChanged: slide = shift

                    Behavior on slide {
                        enabled: root.animateMoves
                        NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
                    }

                    Item {
                        id: mover
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: parent.height
                        // El arrastrado sigue el dedo. El resto se corre con slide.
                        y: index === root.dragLine ? dragArea.offset : slot.slide

                    RowLayout {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: ui.padding
                        width: root.rowWidth
                        visible: modelData.kind === "separator"
                        spacing: ui.gap

                        Text {
                            text: String(modelData.screen + 1)
                            color: ui.primary
                            font.pixelSize: ui.fontBody
                            font.weight: Font.Bold
                        }
                        Item { Layout.fillWidth: true }
                        IconButton {
                            visible: modelData.last === true
                            icon: "plus"
                            iconColor: root.canAdd ? ui.primary : ui.textMuted
                            enabled: root.canAdd && !root.dragging
                            onClicked: root.addScreen()
                        }
                    }

                    Rectangle {
                        id: card

                        readonly property real margin: Math.round(root.rowH * 0.14)
                        anchors.left: parent.left
                        anchors.leftMargin: ui.padding
                        width: root.rowWidth
                        y: margin
                        height: parent.height - margin * 2
                        visible: modelData.kind === "tile"
                        radius: ui.radius
                        color: root.dragLine === index ? ui.surfaceHigh : ui.surface
                        border.width: root.dragLine === index ? 2 : 1
                        border.color: root.dragLine === index ? ui.primary : ui.border

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: ui.padding * 2
                            anchors.rightMargin: ui.padding * 2
                            spacing: ui.padding

                            Column {
                                spacing: Math.round(ui.mm * 0.55)
                                Layout.alignment: Qt.AlignVCenter
                                Repeater {
                                    model: 3
                                    delegate: Rectangle {
                                        width: Math.round(ui.mm * 3.2)
                                        height: Math.max(2, Math.round(ui.mm * 0.4))
                                        radius: height / 2
                                        color: ui.textMuted
                                    }
                                }
                            }
                            Icon {
                                name: root.iconOf(modelData.id)
                                color: ui.primary
                                size: Math.round(ui.icon * 0.85)
                            }
                            Text {
                                Layout.fillWidth: true
                                text: root.labelOf(modelData.id)
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
                                root.dragLine = index
                                root.hover = index
                                root.dragId = modelData.id
                                root.dragging = true
                            }
                            onPositionChanged: {
                                if (!pressed)
                                    return
                                var y = mapToItem(column, mouse.x, mouse.y).y
                                var delta = y - origin
                                var minY = -slot.y
                                var maxY = column.height - slot.y - slot.height
                                offset = Math.max(minY, Math.min(maxY, delta))
                                root.hover = root.lineAt(slot.y + offset + slot.height / 2)
                            }
                            onReleased: finish()
                            onCanceled: finish()

                            function finish() {
                                var line = root.lines[root.hover]
                                var fromScreen = modelData.screen
                                var fromIndex = modelData.tileIndex
                                root.animateMoves = false
                                offset = 0
                                root.dragLine = -1
                                root.hover = -1
                                root.dragId = ""
                                root.dragging = false
                                if (line && modelData.kind === "tile") {
                                    var toIndex = line.kind === "separator" ? 0 : line.tileIndex
                                    root.moveTile(fromScreen, fromIndex, line.screen, toIndex)
                                }
                                Qt.callLater(function() { root.animateMoves = true })
                            }
                        }
                    }
                    }
                }
            }
        }
    }
}
