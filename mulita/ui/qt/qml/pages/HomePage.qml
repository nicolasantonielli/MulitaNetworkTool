import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    signal open(int page)

    readonly property var tiles: [
        { page: 1, icon: "capture", title: i18n.pack.homeCapture, subtitle: i18n.pack.homeCaptureSub },
        { page: 2, icon: "trace", title: i18n.pack.homeTraces, subtitle: i18n.pack.homeTracesSub },
        { page: 3, icon: "tap", title: i18n.pack.homeTap, subtitle: i18n.pack.homeTapSub },
        { page: 4, icon: "scan", title: i18n.pack.homeScan, subtitle: i18n.pack.homeScanSub },
        { page: 5, icon: "tools", title: i18n.pack.homeTools, subtitle: i18n.pack.homeToolsSub },
        { page: 6, icon: "settings", title: i18n.pack.homeSettings, subtitle: i18n.pack.homeSettingsSub }
    ]

    function isActive(page) {
        switch (page) {
        case 1: return capture.running
        case 2: return ping.running || trace.busy
        case 3: return tap.running
        case 4: return discovery.running || portScan.busy
        case 5: return speedTest.busy || wakeOnLan.busy || macVendor.busy || files.busy
        default: return false
        }
    }

    GridLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        columns: width >= height ? 3 : 2
        rowSpacing: ui.gap
        columnSpacing: ui.gap

        Repeater {
            model: root.tiles

            Tile {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                Layout.preferredHeight: 1
                icon: modelData.icon
                title: modelData.title
                subtitle: modelData.subtitle
                active: root.isActive(modelData.page)
                onClicked: root.open(modelData.page)
            }
        }
    }
}
