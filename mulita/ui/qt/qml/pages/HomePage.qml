import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    signal open(int page)
    signal openTool(int tool)

    property var cyberTools: []

    readonly property var tiles: [
        { id: "capture", page: 1, icon: "capture", title: i18n.pack.homeCapture, subtitle: i18n.pack.homeCaptureSub },
        { id: "traces", page: 2, icon: "trace", title: i18n.pack.homeTraces, subtitle: i18n.pack.homeTracesSub },
        { id: "tap", page: 3, icon: "tap", title: i18n.pack.homeTap, subtitle: i18n.pack.homeTapSub },
        { id: "scan", page: 4, icon: "scan", title: i18n.pack.homeScan, subtitle: i18n.pack.homeScanSub },
        { id: "tools", page: 5, icon: "tools", title: i18n.pack.homeTools, subtitle: i18n.pack.homeToolsSub },
        { id: "settings", page: 6, icon: "settings", title: i18n.pack.homeSettings, subtitle: i18n.pack.homeSettingsSub }
    ]

    function arrange(catalog, ids) {
        var byId = {}
        var placed = {}
        var result = []
        for (var i = 0; i < catalog.length; ++i)
            byId[catalog[i].id] = catalog[i]
        var wanted = ids || []
        for (var j = 0; j < wanted.length; ++j) {
            var tile = byId[wanted[j]]
            if (tile && !placed[wanted[j]]) {
                result.push(tile)
                placed[wanted[j]] = true
            }
        }
        for (var k = 0; k < catalog.length; ++k) {
            if (!placed[catalog[k].id])
                result.push(catalog[k])
        }
        return result
    }

    readonly property var networkTiles: arrange(tiles, settings.tileOrder.network)
    readonly property var cyberTiles: arrange(cyberTools, settings.tileOrder.cyber)

    readonly property var sections: [
        { title: i18n.pack.homeNetwork, tiles: root.networkTiles },
        { title: i18n.pack.homeCyber, tiles: root.cyberTiles }
    ]

    readonly property int indicatorHeight: ui.padding

    function isActive(page) {
        switch (page) {
        case 1: return capture.running
        case 2: return ping.running || trace.busy
        case 3: return tap.running
        case 4: return discovery.running || portScan.busy
        case 5: return speedTest.busy || wakeOnLan.busy || macVendor.busy || files.busy
        case 8: return servers.anyRunning
        case 9: return tls.running
        case 10: return nmapScan.phase === "running" || nmapScan.phase === "starting"
        default: return false
        }
    }

    ListView {
        id: pager
        anchors.fill: parent
        anchors.margins: ui.padding
        anchors.bottomMargin: root.indicatorHeight
        orientation: ListView.Horizontal
        snapMode: ListView.SnapOneItem
        highlightRangeMode: ListView.StrictlyEnforceRange
        highlightMoveDuration: 260
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        spacing: ui.padding
        model: root.sections

        delegate: GridLayout {
            id: section
            readonly property var group: modelData
            width: pager.width
            height: pager.height
            columns: width >= height ? 3 : 2
            rowSpacing: ui.gap
            columnSpacing: ui.gap

            Repeater {
                model: section.group.tiles

                Tile {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 1
                    icon: modelData.icon
                    title: modelData.title
                    subtitle: modelData.subtitle
                    active: modelData.page !== undefined && root.isActive(modelData.page)
                    onClicked: modelData.tool !== undefined ? root.openTool(modelData.tool)
                                                             : root.open(modelData.page)
                }
            }
        }
    }

    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        spacing: ui.gap

        Repeater {
            model: root.sections

            Item {
                id: marker
                readonly property bool current: pager.currentIndex === index
                width: label.implicitWidth + dot.width + ui.gap * 2
                height: root.indicatorHeight

                Row {
                    anchors.centerIn: parent
                    spacing: Math.round(ui.gap * 0.5)

                    Rectangle {
                        id: dot
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.round(ui.mm * 2.2)
                        height: width
                        radius: width / 2
                        color: marker.current ? ui.primary : ui.border
                    }
                    Text {
                        id: label
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.title
                        color: marker.current ? ui.text : ui.textMuted
                        font.pixelSize: ui.fontSmall
                        font.weight: marker.current ? Font.DemiBold : Font.Normal
                    }
                }

                TouchArea {
                    onTapped: pager.currentIndex = index
                }
            }
        }
    }
}
