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
                                model: network.interfaces
                                value: group.value
                                enabled: !tap.running
                                onActivated: group.value = value
                            }
                            Item { Layout.fillHeight: true }
                        }
                    }
                }

                RowLayout {
                    spacing: ui.gap

                    TouchButton {
                        text: "Actualizar interfaces"
                        icon: "refresh"
                        kind: "neutral"
                        enabled: !tap.running
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
                                               : tap.start(groups.itemAt(0).value, groups.itemAt(1).value, groups.itemAt(2).value)
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
