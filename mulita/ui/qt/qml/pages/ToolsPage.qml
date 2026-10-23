import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    Component.onCompleted: climate.refresh()

    RowLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        SideNav {
            id: nav
            Layout.preferredWidth: Math.round(root.width * 0.27)
            Layout.fillHeight: true
            items: [
                { label: "Wake on LAN", icon: "wake" },
                { label: "Temperatura", icon: "thermometer" },
                { label: "Velocidad", icon: "gauge" },
                { label: "IP pública", icon: "globe" }
            ]
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: nav.currentIndex

            // Wake on LAN
            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    spacing: ui.gap

                    Field {
                        id: mac
                        Layout.fillWidth: true
                        placeholderText: "MAC destino (AA:BB:CC:DD:EE:FF)"
                        onAccepted: if (!wakeOnLan.busy) wakeOnLan.wake(text)
                    }
                    TouchButton {
                        text: "Despertar"
                        icon: "power"
                        enabled: !wakeOnLan.busy
                        onClicked: wakeOnLan.wake(mac.text)
                    }
                }
                ConsoleView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: wakeOnLan.console
                    placeholder: "Envía el paquete mágico para encender un equipo"
                }
            }

            // Temperatura ambiente
            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: ui.gap

                    StatCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        label: "Temperatura"
                        icon: "thermometer"
                        tone: ui.warning
                        value: climate.temperature
                    }
                    StatCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        label: "Humedad"
                        icon: "droplet"
                        tone: ui.primary
                        value: climate.humidity
                    }
                }
                RowLayout {
                    Text {
                        Layout.fillWidth: true
                        text: climate.status
                        color: ui.danger
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }
                    TouchButton {
                        text: climate.busy ? "Leyendo…" : "Actualizar"
                        icon: "refresh"
                        kind: "neutral"
                        enabled: !climate.busy
                        onClicked: climate.refresh()
                    }
                }
            }

            // Test de velocidad
            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: ui.gap

                    StatCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        label: "Descarga"
                        icon: "download"
                        tone: ui.success
                        value: speedTest.download
                        unit: "Mbps"
                    }
                    StatCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        label: "Subida"
                        icon: "upload"
                        tone: ui.primary
                        value: speedTest.upload
                        unit: "Mbps"
                    }
                }
                RowLayout {
                    spacing: ui.gap

                    BusyIndicator {
                        running: speedTest.busy
                        visible: running
                        Layout.preferredWidth: ui.touch
                        Layout.preferredHeight: ui.touch
                    }
                    Text {
                        Layout.fillWidth: true
                        text: speedTest.status
                        color: speedTest.busy ? ui.textMuted : ui.danger
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }
                    TouchButton {
                        text: speedTest.busy ? "Midiendo…" : "Iniciar test"
                        icon: "gauge"
                        kind: "success"
                        enabled: !speedTest.busy
                        onClicked: speedTest.measure()
                    }
                }
            }

            // IP publica
            ColumnLayout {
                spacing: ui.gap

                StatCard {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    label: "IP pública"
                    icon: "globe"
                    value: publicIp.address
                }
                RowLayout {
                    Text {
                        Layout.fillWidth: true
                        text: publicIp.status
                        color: ui.danger
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }
                    TouchButton {
                        text: publicIp.busy ? "Consultando…" : "Consultar"
                        icon: "refresh"
                        kind: "neutral"
                        enabled: !publicIp.busy
                        onClicked: publicIp.lookup()
                    }
                }
            }
        }
    }
}
