import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        PageTabs {
            id: tabs
            Layout.fillWidth: true
            tabs: [i18n.pack.scanPorts, i18n.pack.scanDiscover]
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            // Escaneo de puertos (nmap)
            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    spacing: ui.gap

                    Field {
                        id: scanTarget
                        Layout.fillWidth: true
                        placeholderText: i18n.pack.scanArgs
                        onAccepted: if (!portScan.busy) portScan.scan(text)
                    }
                    TouchButton {
                        text: portScan.busy ? i18n.pack.scanning : i18n.pack.scan
                        icon: "scan"
                        enabled: !portScan.busy
                        onClicked: portScan.scan(scanTarget.text)
                    }
                }

                ConsoleView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: portScan.console
                    placeholder: i18n.pack.scanEmpty
                }
            }

            // Descubrimiento IP (netdiscover)
            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    spacing: ui.gap

                    Text {
                        Layout.fillWidth: true
                        text: i18n.pack.discoverHint
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        elide: Text.ElideRight
                    }
                    StatusPill {
                        text: discovery.running ? i18n.pack.listening : i18n.pack.discoverStopped
                        tone: discovery.running ? ui.success : ui.textMuted
                        pulsing: discovery.running
                    }
                    TouchButton {
                        Layout.preferredWidth: ui.mm * 34
                        text: discovery.running ? i18n.pack.stop : i18n.pack.discover
                        icon: discovery.running ? "stop" : "play"
                        kind: discovery.running ? "danger" : "success"
                        onClicked: discovery.running ? discovery.stop() : discovery.start()
                    }
                }

                ConsoleView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: discovery.console
                    placeholder: i18n.pack.discoverEmpty
                }
            }
        }
    }
}
