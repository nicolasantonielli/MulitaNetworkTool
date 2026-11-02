import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    signal goHome()
    readonly property var pages: ["general", "display", "wifi", "ethernet", "maintenance", "interface", "touch", "tiles"]
    property string currentPage: "general"
    function navigate(page) {
        currentPage = page
        var index = pages.indexOf(page)
        if (index < nav.items.length) nav.currentIndex = index
    }

    ConfirmDialog { id: confirmationDialog }

    RowLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        SideNav {
            id: nav
            objectName: "settingsNav"
            visible: root.currentPage !== "touch" && root.currentPage !== "tiles"
            Layout.preferredWidth: Math.round(root.width * 0.27)
            Layout.fillHeight: true
            onCurrentIndexChanged: {
                root.currentPage = root.pages[currentIndex]
                if (root.currentPage === "wifi" && !wifi.busy)
                    wifi.refresh()
                if (root.currentPage === "ethernet" && !interna.busy)
                    interna.refresh()
            }
            items: [
                { label: i18n.pack.navGeneral, icon: "info" },
                { label: i18n.pack.navDisplay, icon: "display" },
                { label: i18n.pack.navWifi, icon: "wifi" },
                { label: i18n.pack.navEthIn, icon: "ethernet" },
                { label: i18n.pack.navMaint, icon: "wrench" },
                { label: i18n.pack.navInterface, icon: "settings" }
            ]
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.pages.indexOf(root.currentPage)

            SettingsGeneralPage {}
            SettingsDisplayPage { onOpenTouchTest: root.navigate("touch") }
            SettingsWifiPage { dialog: confirmationDialog }
            SettingsEthernetPage { dialog: confirmationDialog }
            SettingsMaintenancePage { dialog: confirmationDialog }
            SettingsInterfacePage { onOpenTileOrder: root.navigate("tiles") }
            TouchTestPage { onGoBack: root.navigate("display") }
            TileOrderPage { onGoBack: root.navigate("interface") }
        }
    }
}
