import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    property string selectedInterface: ""
    property string selectedDirection: "inout"
    property int elapsed: 0
    readonly property var captureInterfaces: {
        var rows = network.interfaces
        var found = []
        for (var i = 0; i < rows.length; ++i) {
            var row = rows[i]
            var name = typeof row === "string" ? row : row.value
            if (name !== "lo")
                found.push(typeof row === "string" ? { label: name, value: name, linked: false } : row)
        }
        return found
    }

    function interfaceList() {
        var parts = []
        for (var i = 0; i < captureInterfaces.length; ++i)
            parts.push(captureInterfaces[i].value)
        return parts.join("  ·  ")
    }

    function keepSelection() {
        var rows = captureInterfaces
        for (var i = 0; i < rows.length; ++i) {
            if (rows[i].value === selectedInterface && selectedInterface !== "")
                return
        }
        var chosen = ""
        for (var j = 0; j < rows.length; ++j) {
            if (rows[j].value === "eth0")
                chosen = "eth0"
        }
        if (!chosen && rows.length)
            chosen = rows[0].value
        selectedInterface = chosen
    }

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

    Connections {
        target: network
        function onInterfacesChanged() { root.keepSelection() }
    }

    Component.onCompleted: keepSelection()

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
                    model: root.captureInterfaces
                    value: root.selectedInterface
                    enabled: !capture.running
                    onActivated: root.selectedInterface = value
                }
                Text {
                    Layout.fillWidth: true
                    text: root.captureInterfaces.length === 0
                          ? "No se detectaron interfaces de red"
                          : root.interfaceList()
                    color: ui.text
                    font.pixelSize: ui.fontBody
                    wrapMode: Text.Wrap
                }
                TouchButton {
                    Layout.fillWidth: true
                    text: network.refreshing ? "Leyendo…" : "Recargar interfaces"
                    icon: "refresh"
                    kind: network.refreshing ? "success" : "neutral"
                    enabled: !capture.running && !network.refreshing
                    onClicked: network.refresh()
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
