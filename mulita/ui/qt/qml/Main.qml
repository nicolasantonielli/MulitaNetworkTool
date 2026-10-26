import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Controls.Material 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15
import "components"
import "pages"

ApplicationWindow {
    id: window

    readonly property var pages: [
        { title: i18n.pack.pageHome, share: false },
        { title: i18n.pack.pageCapture, share: true },
        { title: i18n.pack.pageTraces, share: true },
        { title: i18n.pack.pageTap, share: true },
        { title: i18n.pack.pageScan, share: true },
        { title: i18n.pack.pageTools, share: true },
        { title: i18n.pack.pageSettings, share: false },
        { title: window.cyberTools[window.cyberTool].title, share: false }
    ]
    property int currentPage: 0

    readonly property int cyberPage: 7
    readonly property var cyberTools: [
        { tool: 0, icon: "bug", title: i18n.pack.cyberVuln, subtitle: i18n.pack.cyberVulnSub },
        { tool: 1, icon: "wifi", title: i18n.pack.cyberWifi, subtitle: i18n.pack.cyberWifiSub },
        { tool: 2, icon: "shield", title: i18n.pack.cyberArp, subtitle: i18n.pack.cyberArpSub },
        { tool: 3, icon: "ethernet", title: i18n.pack.cyberDhcp, subtitle: i18n.pack.cyberDhcpSub },
        { tool: 4, icon: "lock", title: i18n.pack.cyberTls, subtitle: i18n.pack.cyberTlsSub },
        { tool: 5, icon: "globe", title: i18n.pack.cyberDns, subtitle: i18n.pack.cyberDnsSub }
    ]
    property int cyberTool: 0

    readonly property real keyboardHeight: keyboard.item && keyboard.item.active ? keyboard.item.height : 0
    readonly property real contentShift: {
        if (keyboardHeight <= 0 || !activeFocusItem)
            return 0
        var bottom = activeFocusItem.mapToItem(viewport, 0, activeFocusItem.height).y
        return Math.max(0, bottom - (viewport.height - keyboardHeight) + ui.gap)
    }

    function navigate(index) {
        currentPage = index
    }

    onActiveFocusItemChanged: if (keyboard.item) keyboard.item.follow(activeFocusItem)

    function placeKeyboard() {
        if (!keyboard.item)
            return
        var top = keyboard.item.active
        var next = top ? Overlay.overlay : contentItem
        if (keyboard.parent !== next)
            keyboard.parent = next
        // El aviso modal queda cerca de 100000. El teclado tiene que quedar encima
        // para que las teclas reciban el toque.
        keyboard.z = top ? 1000001 : 100
    }

    width: ui.windowWidth
    height: ui.windowHeight
    visible: true
    visibility: ui.fullscreen ? Window.FullScreen : Window.Windowed
    title: "Mulita " + system.version
    color: ui.background
    font.pixelSize: ui.fontBody

    Material.theme: ui.dark ? Material.Dark : Material.Light
    Material.accent: ui.primary
    Material.background: ui.surface
    Material.foreground: ui.text

    header: AppHeader {
        title: window.pages[window.currentPage].title
        showBack: window.currentPage !== 0
        showShare: window.pages[window.currentPage].share
        onBack: window.navigate(0)
        onShare: system.share(title)
    }

    Item {
        id: viewport
        anchors.fill: parent
        clip: true

        StackLayout {
            id: stack
            width: parent.width
            height: parent.height
            y: -window.contentShift
            currentIndex: window.currentPage

            Behavior on y { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

            HomePage {
                cyberTools: window.cyberTools
                onOpen: window.navigate(page)
                onOpenTool: {
                    window.cyberTool = tool
                    window.navigate(window.cyberPage)
                }
            }
            CapturePage { }
            TracesPage { }
            TapPage { }
            ScanPage { }
            ToolsPage { }
            SettingsPage { onGoHome: window.navigate(0) }
            CyberPage { tool: window.cyberTools[window.cyberTool] }

            onCurrentIndexChanged: pageFade.restart()
        }

        NumberAnimation {
            id: pageFade
            target: stack
            property: "opacity"
            from: 0.35
            to: 1
            duration: 160
            easing.type: Easing.OutCubic
        }
    }

    Toast { }
    CopyMenu { }

    Timer {
        interval: 15000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: network.refresh()
    }

    Loader {
        id: keyboard
        z: 100
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        source: ui.virtualKeyboard ? "components/KeyboardPanel.qml" : ""
        onStatusChanged: {
            if (status === Loader.Error)
                console.warn("Teclado virtual no disponible")
            if (status === Loader.Ready)
                window.placeKeyboard()
        }
    }

    Connections {
        target: keyboard.item
        onActiveChanged: window.placeKeyboard()
    }
}
