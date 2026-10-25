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
        { title: "Inicio", share: false },
        { title: "Captura de paquetes", share: true },
        { title: "Trazas", share: true },
        { title: "TAP", share: true },
        { title: "Escaneo", share: true },
        { title: "Herramientas", share: true },
        { title: "Configuración", share: false }
    ]
    property int currentPage: 0

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

            HomePage { onOpen: window.navigate(page) }
            CapturePage { }
            TracesPage { }
            TapPage { }
            ScanPage { }
            ToolsPage { }
            SettingsPage { onGoHome: window.navigate(0) }

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

    Timer {
        interval: 15000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: network.refresh()
    }

    Loader {
        id: keyboard
        // Encima del aviso modal, para poder escribir la clave del Wi-Fi.
        parent: Overlay.overlay
        z: 1000
        width: parent.width
        anchors.bottom: parent.bottom
        source: ui.virtualKeyboard ? "components/KeyboardPanel.qml" : ""
        onStatusChanged: if (status === Loader.Error) console.warn("Teclado virtual no disponible")
    }
}
