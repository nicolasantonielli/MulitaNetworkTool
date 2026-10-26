import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    property bool captureOn: false

    function fileName() {
        return tapFile.text.replace(/\.pcap$/i, "") + ".pcap"
    }

    // Misma lista que la captura: sin lo, y celeste si hay cable.
    readonly property var tapInterfaces: {
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

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        PageTabs {
            id: tabs
            Layout.fillWidth: true
            tabs: ["Configuración", "Pantalla"]
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: ui.gap

                    Repeater {
                        id: groups
                        model: [
                            { title: "Entrante", icon: "download" },
                            { title: "Mirror", icon: "tap" },
                            { title: "Saliente", icon: "upload" }
                        ]

                        Card {
                            id: group

                            property string value: ""

                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.preferredWidth: 1
                            title: modelData.title
                            titleIcon: modelData.icon

                            ChoiceChips {
                                Layout.fillWidth: true
                                model: root.tapInterfaces
                                value: group.value
                                enabled: !tap.running
                                onActivated: group.value = value
                            }
                            Connections {
                                target: network
                                function onInterfacesChanged() {
                                    var rows = root.tapInterfaces
                                    for (var i = 0; i < rows.length; ++i) {
                                        if (rows[i].value === group.value)
                                            return
                                    }
                                    group.value = ""
                                }
                            }
                            Item { Layout.fillHeight: true }
                        }
                    }
                }

                Card {
                    Layout.fillWidth: true
                    title: "Archivo de captura"
                    titleIcon: "file"

                    RowLayout {
                        spacing: ui.gap

                        Rectangle {
                            Layout.preferredWidth: ui.touch
                            Layout.preferredHeight: ui.touch
                            radius: ui.radius
                            color: root.captureOn ? ui.primary : ui.surfaceAlt
                            border.width: 1
                            border.color: root.captureOn ? ui.primary : ui.border
                            enabled: !tap.running

                            Text {
                                anchors.centerIn: parent
                                visible: root.captureOn
                                text: "✓"
                                color: ui.onAccent
                                font.pixelSize: ui.fontTitle
                                font.weight: Font.Bold
                            }
                            TouchArea {
                                enabled: !tap.running
                                onTapped: root.captureOn = !root.captureOn
                            }
                        }
                        Text {
                            text: "Capturar"
                            color: ui.text
                            font.pixelSize: ui.fontBody
                            font.weight: Font.DemiBold
                        }
                    }
                    RowLayout {
                        spacing: ui.gap
                        enabled: root.captureOn

                        Field {
                            id: tapFile
                            Layout.fillWidth: true
                            text: tap.defaultFilename
                            enabled: root.captureOn && !tap.running
                            placeholderText: "Nombre del archivo"
                        }
                        Text {
                            text: ".pcap"
                            color: ui.textMuted
                            font.pixelSize: ui.fontBody
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: root.captureOn
                        text: tap.running && tap.activeFile !== "" ? tap.activeFile : root.fileName()
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        font.family: ui.monoFamily
                        wrapMode: Text.WrapAnywhere
                    }
                }

                RowLayout {
                    spacing: ui.gap

                    TouchButton {
                        text: network.refreshing ? "Leyendo…" : "Actualizar interfaces"
                        icon: "refresh"
                        kind: network.refreshing ? "success" : "neutral"
                        enabled: !tap.running && !network.refreshing
                        onClicked: network.refresh()
                    }
                    Item { Layout.fillWidth: true }
                    StatusPill {
                        text: tap.running ? "Activo" : "Inactivo"
                        tone: tap.running ? ui.success : ui.textMuted
                        pulsing: tap.running
                    }
                    TouchButton {
                        Layout.preferredWidth: ui.mm * 34
                        text: tap.running ? "Detener" : "Iniciar"
                        icon: tap.running ? "stop" : "play"
                        kind: tap.running ? "danger" : "success"
                        onClicked: tap.running ? tap.stop()
                                               : tap.start(groups.itemAt(0).value, groups.itemAt(1).value,
                                                           groups.itemAt(2).value, root.captureOn, tapFile.text)
                    }
                }
            }

            ConsoleView {
                source: tap.console
                placeholder: "El TAP todavía no genera salida"
            }
        }
    }
}
