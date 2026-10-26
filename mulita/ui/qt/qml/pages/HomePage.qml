import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    signal open(int page)

    readonly property var tiles: [
        { page: 1, icon: "capture", title: "Captura", subtitle: "Paquetes a archivo .pcap" },
        { page: 2, icon: "trace", title: "Trazas", subtitle: "Ruta, latencia y ping" },
        { page: 3, icon: "tap", title: "TAP", subtitle: "Puente y espejo de puertos" },
        { page: 4, icon: "scan", title: "Escaneo", subtitle: "Puertos y hosts de la red" },
        { page: 5, icon: "tools", title: "Herramientas", subtitle: "WoL, clima, Wi-Fi, MAC" },
        { page: 6, icon: "settings", title: "Configuración", subtitle: "Pantalla, tema y sistema" }
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
