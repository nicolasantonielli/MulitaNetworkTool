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
            tabs: ["Escaneo de puertos", "Descubrimiento IP"]
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
                        placeholderText: "Destino y opciones (ej: -p 22,80 192.168.0.0/24)"
                        onAccepted: if (!portScan.busy) portScan.scan(text)
                    }
                    TouchButton {
                        text: portScan.busy ? "Escaneando…" : "Escanear"
                        icon: "scan"
                        enabled: !portScan.busy
                        onClicked: portScan.scan(scanTarget.text)
                    }
                }

                ConsoleView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: portScan.console
                    placeholder: "Los puertos abiertos aparecen aquí"
                }
            }

            // Descubrimiento IP (netdiscover)
            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    spacing: ui.gap

                    Text {
                        Layout.fillWidth: true
                        text: "Detecta equipos de la red local por ARP"
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        elide: Text.ElideRight
                    }
                    StatusPill {
                        text: discovery.running ? "Escuchando" : "Detenido"
                        tone: discovery.running ? ui.success : ui.textMuted
                        pulsing: discovery.running
                    }
                    TouchButton {
                        Layout.preferredWidth: ui.mm * 34
                        text: discovery.running ? "Detener" : "Descubrir"
                        icon: discovery.running ? "stop" : "play"
                        kind: discovery.running ? "danger" : "success"
                        onClicked: discovery.running ? discovery.stop() : discovery.start()
                    }
                }

                ConsoleView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: discovery.console
                    placeholder: "Los equipos detectados aparecen aquí"
                }
            }
        }
    }
}
