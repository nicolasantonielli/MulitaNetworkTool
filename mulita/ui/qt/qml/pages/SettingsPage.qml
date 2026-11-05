import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    objectName: "settingsPage"
    signal goHome()
    property var pages: [
        { id: "general", label: "navGeneral", icon: "info", component: generalPage },
        { id: "display", label: "navDisplay", icon: "display", component: displayPage },
        { id: "interface", label: "navInterface", icon: "settings", component: interfacePage },
        { id: "wifi", label: "navWifi", icon: "wifi", component: wifiPage },
        { id: "ethernet", label: "navEthIn", icon: "ethernet", component: ethernetPage },
        { id: "maintenance", label: "navMaint", icon: "wrench", component: maintenancePage },
        { id: "touch", component: touchPage },
        { id: "tiles", component: tilesPage },
        { id: "journal", component: journalPage }
    ]
    readonly property var menuPages: pages.filter(function(page) { return !!page.label })
    property string currentPage: "general"
    function pageIndex(page) {
        for (var i = 0; i < pages.length; i++) if (pages[i].id === page) return i
        return -1
    }
    function navigate(page) {
        if (pageIndex(page) < 0) return
        currentPage = page
        for (var i = 0; i < menuPages.length; i++) {
            if (menuPages[i].id === page) { nav.currentIndex = i; break }
        }
    }
    onCurrentPageChanged: {
        if (currentPage === "wifi" && !wifi.busy) wifi.refresh()
        if (currentPage === "ethernet" && !interna.busy) interna.refresh()
    }
    onPagesChanged: navigate(currentPage)

    Component { id: generalPage; SettingsGeneralPage { objectName: "general"; onOpenJournalAdvanced: root.navigate("journal") } }
    Component { id: journalPage; SettingsJournalPage { onGoBack: root.navigate("general") } }
    Component { id: displayPage; SettingsDisplayPage { objectName: "display"; onOpenTouchTest: root.navigate("touch") } }
    Component { id: wifiPage; SettingsWifiPage { objectName: "wifi"; dialog: confirmationDialog } }
    Component { id: ethernetPage; SettingsEthernetPage { objectName: "ethernet"; dialog: confirmationDialog } }
    Component { id: maintenancePage; SettingsMaintenancePage { objectName: "maintenance"; dialog: confirmationDialog } }
    Component { id: interfacePage; SettingsInterfacePage { objectName: "interface"; onOpenTileOrder: root.navigate("tiles") } }
    Component { id: touchPage; TouchTestPage { objectName: "touch"; onGoBack: root.navigate("display") } }
    Component { id: tilesPage; TileOrderPage { objectName: "tiles"; onGoBack: root.navigate("interface") } }

    ConfirmDialog { id: confirmationDialog }

    RowLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        SideNav {
            id: nav
            objectName: "settingsNav"
            visible: root.currentPage !== "touch" && root.currentPage !== "tiles" && root.currentPage !== "journal"
            Layout.preferredWidth: Math.round(root.width * 0.27)
            Layout.fillHeight: true
            onCurrentIndexChanged: {
                if (currentIndex >= 0 && currentIndex < root.menuPages.length)
                    root.navigate(root.menuPages[currentIndex].id)
            }
            items: root.menuPages.map(function(page) {
                return { label: i18n.pack[page.label], icon: page.icon }
            })
        }

        StackLayout {
            id: pageStack
            objectName: "settingsStack"
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.pageIndex(root.currentPage)

            Repeater {
                id: pageRepeater
                model: root.pages
                Loader {
                    objectName: "settings-loader-" + modelData.id
                    sourceComponent: modelData.component
                }
            }
        }
    }
}
