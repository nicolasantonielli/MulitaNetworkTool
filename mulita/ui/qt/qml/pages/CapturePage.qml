import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    property string selectedInterface: ""
    property string selectedDirection: "inout"
    property int elapsed: 0

    function clock(seconds) {
        function two(n) { return n < 10 ? "0" + n : "" + n }
        return two(Math.floor(seconds / 3600)) + ":" + two(Math.floor(seconds / 60) % 60) + ":" + two(seconds % 60)
    }

    Timer {
        interval: 1000
        repeat: true
        running: capture.running
        onTriggered: root.elapsed += 1
    }

    Connections {
        target: capture
        function onRunningChanged() {
            if (capture.running)
                root.elapsed = 0
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        ScrollPage {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Card {
                Layout.fillWidth: true
                title: "Interfaz"
                titleIcon: "ethernet"

                ChoiceChips {
                    Layout.fillWidth: true
                    model: network.interfaces
                    value: root.selectedInterface
                    enabled: !capture.running
                    onActivated: root.selectedInterface = value
                }
                Text {
                    visible: network.interfaces.length === 0
                    text: "No se detectaron interfaces de red"
                    color: ui.textMuted
                    font.pixelSize: ui.fontSmall
                }
            }

            Card {
                Layout.fillWidth: true
                title: "Dirección del tráfico"
                titleIcon: "capture"

                ChoiceChips {
                    Layout.fillWidth: true
                    model: capture.directions
                    value: root.selectedDirection
                    enabled: !capture.running
                    onActivated: root.selectedDirection = value
                }
            }

            Card {
                Layout.fillWidth: true
                title: "Archivo de captura"
                titleIcon: "file"

                RowLayout {
                    spacing: ui.gap

                    Field {
                        id: filename
                        Layout.fillWidth: true
                        text: capture.defaultFilename
                        enabled: !capture.running
                        placeholderText: "Nombre del archivo"
                    }
                    Text {
                        text: ".pcap"
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                    }
                }
            }
        }

        Card {
            Layout.preferredWidth: Math.round(root.width * 0.34)
            Layout.fillHeight: true
            title: "Estado"
            titleIcon: "info"

            StatusPill {
                text: capture.running ? "Capturando" : "Detenida"
                tone: capture.running ? ui.success : ui.textMuted
                pulsing: capture.running
            }
            Text {
                text: root.clock(root.elapsed)
                color: capture.running ? ui.text : ui.textMuted
                font.pixelSize: ui.fontHeading
                font.family: ui.monoFamily
                font.weight: Font.Bold
            }
            Text {
                Layout.fillWidth: true
                text: capture.running ? capture.activeFile
                                      : filename.text.replace(/\.pcap$/i, "") + ".pcap"
                color: ui.textMuted
                font.pixelSize: ui.fontSmall
                font.family: ui.monoFamily
                wrapMode: Text.WrapAnywhere
            }

            Item { Layout.fillHeight: true }

            TouchButton {
                Layout.fillWidth: true
                implicitHeight: Math.round(ui.touch * 1.2)
                text: capture.running ? "Detener" : "Iniciar"
                icon: capture.running ? "stop" : "play"
                kind: capture.running ? "danger" : "success"
                onClicked: capture.running ? capture.stop()
                                           : capture.start(root.selectedInterface, root.selectedDirection, filename.text)
            }
        }
    }
}
