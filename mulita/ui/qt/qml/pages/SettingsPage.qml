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
            onCurrentIndexChanged: {
                if (currentIndex === 2 && !wifi.busy)
                    wifi.refresh()
                if (currentIndex === 3 && !interna.busy)
                    interna.refresh()
            }
            items: [
                { label: "General", icon: "info" },
                { label: "Pantalla", icon: "display" },
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

            // Pantalla
            ScrollPage {
                Card {
                    Layout.fillWidth: true
                    title: "Tamaño"
                    titleIcon: "display"

                    Text {
                        Layout.fillWidth: true
                        text: "Agrandá o achicá letras e íconos juntos. La resolución del panel no cambia."
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        wrapMode: Text.Wrap
                    }
                    LabeledSlider {
                        Layout.fillWidth: true
                        label: "Escala"
                        from: 0.5
                        to: 1.25
                        stepSize: 0.05
                        initial: settings.uiScale
                        valueText: Math.round(value * 100) + " %"
                        onValueChanged: settings.setScale(value)
                    }
                }
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
            }

            // Wi-Fi
            ScrollPage {
                id: wifiPage

                property string chosen: ""
                property bool chosenSecure: false

                function pick(ssid, secure) {
                    chosen = ssid
                    chosenSecure = secure
                    wifiPassword.text = ""
                    if (!secure)
                        dialog.ask({
                            title: "Conectar a " + ssid,
                            kind: "success",
                            message: "La red no pide clave.",
                            confirmText: "Conectar",
                            confirmAction: function() { wifi.connectTo(ssid, "", false) }
                        })
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: wifi.deviceName === "" ? "No hay Wi-Fi"
                              : (wifi.activeName === "" ? "Sin conexión" : "Conectada: " + wifi.activeName)
                        color: ui.text
                        font.pixelSize: ui.fontBody
                        elide: Text.ElideRight
                    }
                    TouchButton {
                        text: wifi.busy ? "Buscando…" : "Buscar"
                        icon: "refresh"
                        kind: "neutral"
                        enabled: !wifi.busy && wifi.deviceName !== ""
                        onClicked: wifi.refresh()
                    }
                }

                Repeater {
                    model: wifi.networks

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: ui.touch
                        radius: ui.radius
                        color: modelData.active ? ui.primary : (area.pressed ? ui.surfaceHigh : ui.surfaceAlt)
                        border.width: 1
                        border.color: modelData.active ? ui.primary : ui.border

                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: ui.padding
                            anchors.rightMargin: ui.padding
                            verticalAlignment: Text.AlignVCenter
                            text: modelData.ssid + "   " + modelData.signal + "%   " + modelData.security
                            color: modelData.active ? ui.onAccent : ui.text
                            font.pixelSize: ui.fontBody
                            elide: Text.ElideRight
                        }
                        TouchArea {
                            id: area
                            onTapped: wifiPage.pick(modelData.ssid, modelData.secure)
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    visible: wifiPage.chosen !== "" && wifiPage.chosenSecure
                    spacing: ui.gap

                    Text {
                        Layout.fillWidth: true
                        text: "Clave de " + wifiPage.chosen
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        elide: Text.ElideRight
                    }
                    Field {
                        id: wifiPassword
                        Layout.fillWidth: true
                        echoMode: TextInput.Password
                        placeholderText: "Clave"
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: "Conectar"
                        icon: "wifi"
                        enabled: !wifi.busy
                        onClicked: wifi.connectTo(wifiPage.chosen, wifiPassword.text, true)
                    }
                }
            }

            // Ethernet interna
            ScrollPage {
                id: internaPage

                function apply() {
                    interna.apply(modeChips.value, ip.text, mask.text, gateway.text, dns.text)
                }

                function showStatic(address, netmask, gatewayAddress, dnsAddress) {
                    if (address)
                        ip.text = address
                    if (netmask)
                        mask.text = netmask
                    if (gatewayAddress)
                        gateway.text = gatewayAddress
                    if (dnsAddress)
                        dns.text = dnsAddress
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
                        onActivated: {
                            modeChips.value = value
                            if (value === "static")
                                internaPage.showStatic(interna.address, interna.netmask, interna.gateway, interna.dns)
                        }
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
                    visible: modeChips.value !== "static"
                    title: "Dirección obtenida"
                    titleIcon: "info"

                    Text { text: "Dirección IP"; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Text {
                        Layout.fillWidth: true
                        text: interna.address || "Sin dirección"
                        color: ui.text
                        font.pixelSize: ui.fontBody
                        wrapMode: Text.Wrap
                    }
                    Text { text: "Máscara"; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Text {
                        Layout.fillWidth: true
                        text: interna.netmask || "Sin máscara"
                        color: ui.text
                        font.pixelSize: ui.fontBody
                    }
                    Text { text: "Puerta de enlace"; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Text {
                        Layout.fillWidth: true
                        text: interna.gateway || "Sin puerta de enlace"
                        color: ui.text
                        font.pixelSize: ui.fontBody
                    }
                    Text { text: "DNS"; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Text {
                        Layout.fillWidth: true
                        text: interna.dns || "Sin DNS"
                        color: ui.text
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
                    Field { id: ip; Layout.fillWidth: true; Component.onCompleted: text = "192.168.1.10" }
                    Text { text: "Máscara"; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: mask; Layout.fillWidth: true; Component.onCompleted: text = "255.255.255.0" }
                    Text { text: "Puerta de enlace"; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: gateway; Layout.fillWidth: true; Component.onCompleted: text = "192.168.1.1" }
                    Text { text: "DNS"; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: dns; Layout.fillWidth: true; Component.onCompleted: text = "8.8.8.8" }
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
                                     ? "Se asigna " + ip.text + " a " + interna.interfaceName + "."
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
                        if (interna.mode !== "static")
                            return
                        internaPage.showStatic(interna.address, interna.netmask, interna.gateway, interna.dns)
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
