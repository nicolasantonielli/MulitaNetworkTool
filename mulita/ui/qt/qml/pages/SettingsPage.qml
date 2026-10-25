import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    signal goHome()

    ConfirmDialog { id: dialog }

    RowLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        SideNav {
            id: nav
            Layout.preferredWidth: Math.round(root.width * 0.27)
            Layout.fillHeight: true
            onCurrentIndexChanged: if (currentIndex === 2 && !interna.busy) interna.refresh()
            items: [
                { label: "General", icon: "theme" },
                { label: "Wi-Fi", icon: "wifi" },
                { label: "Ethernet interna", icon: "ethernet" },
                { label: "Ethernet externa", icon: "ethernet" },
                { label: "Mantenimiento", icon: "wrench" }
            ]
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: nav.currentIndex

            // General
            ScrollPage {
                Card {
                    Layout.fillWidth: true
                    title: "Tema"
                    titleIcon: "theme"

                    ChoiceChips {
                        Layout.fillWidth: true
                        model: settings.themes
                        value: settings.theme
                        onActivated: settings.setTheme(value)
                    }
                }
                Card {
                    Layout.fillWidth: true
                    title: "Acerca de"
                    titleIcon: "info"

                    Text {
                        text: "Mulita Network Tool"
                        color: ui.text
                        font.pixelSize: ui.fontTitle
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: "Versión " + system.version
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                    }
                }
            }

            // Wi-Fi
            PendingSection { title: "Wi-Fi"; icon: "wifi"; onGoHome: root.goHome() }

            // Ethernet interna
            ScrollPage {
                id: internaPage

                function apply() {
                    interna.apply(modeChips.value, ip.text, mask.text, gateway.text, dns.text)
                }

                Card {
                    Layout.fillWidth: true
                    title: "Modo"
                    titleIcon: "ethernet"

                    Text {
                        Layout.fillWidth: true
                        text: interna.interfaceName + " · " + interna.summary
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }
                    ChoiceChips {
                        id: modeChips
                        Layout.fillWidth: true
                        enabled: !interna.busy
                        model: interna.modes
                        value: interna.mode
                        onActivated: modeChips.value = value
                    }
                    Text {
                        Layout.fillWidth: true
                        text: modeChips.value === "static"
                              ? "La dirección queda fija en el puerto."
                              : "El puerto pide la dirección por DHCP."
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        wrapMode: Text.Wrap
                    }
                }

                Card {
                    Layout.fillWidth: true
                    visible: modeChips.value === "static"
                    title: "Dirección estática"
                    titleIcon: "settings"

                    Text { text: "Dirección IP"; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: ip; Layout.fillWidth: true; placeholderText: "192.168.1.10" }
                    Text { text: "Máscara"; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: mask; Layout.fillWidth: true; placeholderText: "255.255.255.0" }
                    Text { text: "Puerta de enlace"; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: gateway; Layout.fillWidth: true; placeholderText: "192.168.1.1" }
                    Text { text: "DNS"; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: dns; Layout.fillWidth: true; placeholderText: "8.8.8.8" }
                }

                RowLayout {
                    BusyIndicator {
                        running: interna.busy
                        visible: running
                        Layout.preferredWidth: ui.touch
                        Layout.preferredHeight: ui.touch
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: "Aplicar"
                        icon: "check"
                        kind: "success"
                        enabled: !interna.busy
                        onClicked: dialog.ask({
                            title: "Ethernet interna",
                            kind: "warning",
                            message: modeChips.value === "static"
                                     ? "Se asigna " + (ip.text || "la dirección ingresada") + " a " + interna.interfaceName + "."
                                     : interna.interfaceName + " pedirá una dirección por DHCP.",
                            confirmText: "Aplicar",
                            confirmAction: internaPage.apply
                        })
                    }
                }

                Connections {
                    target: interna
                    function onLoaded() {
                        modeChips.value = interna.mode
                        ip.text = interna.address
                        mask.text = interna.netmask
                        gateway.text = interna.gateway
                        dns.text = interna.dns
                    }
                }
            }

            // Ethernet externa
            PendingSection { title: "Ethernet externa"; icon: "ethernet"; onGoHome: root.goHome() }

            // Mantenimiento
            ScrollPage {
                Card {
                    Layout.fillWidth: true
                    title: "Sistema"
                    titleIcon: "info"

                    RowLayout {
                        Text {
                            Layout.fillWidth: true
                            text: "Versión " + system.version
                            color: ui.text
                            font.pixelSize: ui.fontTitle
                            font.weight: Font.DemiBold
                        }
                        BusyIndicator {
                            running: system.busy
                            visible: running
                            Layout.preferredWidth: ui.touch
                            Layout.preferredHeight: ui.touch
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    rowSpacing: ui.gap
                    columnSpacing: ui.gap

                    TouchButton {
                        Layout.fillWidth: true
                        text: "Actualizar"
                        icon: "download"
                        kind: "success"
                        enabled: !system.busy
                        onClicked: dialog.ask({ title: "Actualizar Mulita", kind: "success",
                                                message: "Se descarga la rama v3 del repositorio. Reinicie la aplicación para aplicarla.",
                                                confirmText: "Actualizar", confirmAction: system.update })
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: "Reiniciar app"
                        icon: "restart"
                        kind: "warning"
                        enabled: !system.busy
                        onClicked: dialog.ask({ title: "Reiniciar la aplicación", kind: "warning",
                                                message: "Se detienen las capturas y pruebas en curso.",
                                                confirmText: "Reiniciar", confirmAction: system.reset })
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: "Apagar equipo"
                        icon: "power"
                        kind: "danger"
                        onClicked: dialog.ask({ title: "Apagar el equipo", kind: "danger",
                                                message: "El equipo se apaga por completo.",
                                                confirmText: "Apagar", confirmAction: system.poweroff })
                    }
                }
            }
        }
    }
}
