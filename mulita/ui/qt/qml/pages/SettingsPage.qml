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
            objectName: "settingsNav"
            visible: currentIndex !== 5
            Layout.preferredWidth: Math.round(root.width * 0.27)
            Layout.fillHeight: true
            onCurrentIndexChanged: {
                if (currentIndex === 2 && !wifi.busy)
                    wifi.refresh()
                if (currentIndex === 3 && !interna.busy)
                    interna.refresh()
            }
            items: [
                { label: i18n.pack.navGeneral, icon: "info" },
                { label: i18n.pack.navDisplay, icon: "display" },
                { label: i18n.pack.navWifi, icon: "wifi" },
                { label: i18n.pack.navEthIn, icon: "ethernet" },
                { label: i18n.pack.navMaint, icon: "wrench" }
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
                    title: i18n.pack.about
                    titleIcon: "info"

                    Text {
                        text: "Mulita Network Tool"
                        color: ui.text
                        font.pixelSize: ui.fontTitle
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: i18n.pack.version + " " + system.version
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                    }
                }
                Card {
                    Layout.fillWidth: true
                    title: i18n.pack.language
                    titleIcon: "globe"

                    ChoiceChips {
                        Layout.fillWidth: true
                        model: settings.languages
                        value: settings.language
                        onActivated: settings.setLanguage(value)
                    }
                    Text {
                        Layout.fillWidth: true
                        text: i18n.pack.languageHint
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        wrapMode: Text.Wrap
                    }
                }
            }

            // Pantalla
            ScrollPage {
                Card {
                    Layout.fillWidth: true
                    title: i18n.pack.displaySize
                    titleIcon: "display"

                    Text {
                        Layout.fillWidth: true
                        text: i18n.pack.scaleHint
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        wrapMode: Text.Wrap
                    }
                    LabeledSlider {
                        Layout.fillWidth: true
                        label: i18n.pack.scale
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
                    title: i18n.pack.brightness
                    titleIcon: "display"

                    Text {
                        Layout.fillWidth: true
                        text: settings.brightnessReady ? i18n.pack.brightnessHint : i18n.pack.noBacklight
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        wrapMode: Text.Wrap
                    }
                    LabeledSlider {
                        Layout.fillWidth: true
                        enabled: settings.brightnessReady
                        label: i18n.pack.brightness
                        from: 1
                        to: 100
                        stepSize: 1
                        initial: settings.brightness
                        valueText: Math.round(value) + " %"
                        onValueChanged: settings.setBrightness(value)
                    }
                }
                Card {
                    Layout.fillWidth: true
                    title: i18n.pack.theme
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
                    title: i18n.pack.touchTest
                    titleIcon: "display"

                    TouchButton {
                        Layout.fillWidth: true
                        text: i18n.pack.start
                        icon: "play"
                        kind: "neutral"
                        onClicked: nav.currentIndex = 5
                    }
                }
            }

            // Wi-Fi
            Item {
                id: wifiPage

                property string chosen: ""
                property bool chosenSecure: false
                readonly property var networks: {
                    try { return JSON.parse(wifi.networksJson) }
                    catch (e) { return [] }
                }

                function pick(ssid, secure) {
                    chosen = ssid
                    chosenSecure = secure
                    dialog.ask({
                        title: ssid,
                        kind: "success",
                        message: i18n.pack.connectTitle,
                        confirmText: i18n.pack.connect,
                        cancelText: i18n.pack.cancel,
                        confirmAction: function() { wifiPage.afterConfirm(ssid, secure) }
                    })
                }

                function afterConfirm(ssid, secure) {
                    wifiKeyField.text = ""
                    wifiKeyField.revealed = false
                    wifiKey.ssid = ssid
                    wifiKey.secure = secure
                    wifiKey.open()
                }

                Popup {
                    id: wifiKey

                    property string ssid: ""
                    property bool secure: true

                    parent: Overlay.overlay
                    // Sin velo modal: ese velo se queda con el toque y las teclas no responden.
                    modal: false
                    focus: true
                    closePolicy: Popup.CloseOnEscape
                    padding: Math.round(ui.padding * 1.3)
                    width: Math.min(parent.width - ui.padding * 4, ui.mm * 110)
                    x: Math.max(0, (parent.width - width) / 2)
                    y: ui.padding
                    onOpened: Qt.callLater(function() { wifiKeyField.forceActiveFocus() })
                    onClosed: wifiKeyField.focus = false

                    background: Rectangle {
                        color: ui.surface
                        radius: ui.radius * 1.6
                        border.width: 1
                        border.color: ui.border
                    }
                    contentItem: ColumnLayout {
                        spacing: ui.gap

                        Text {
                            Layout.fillWidth: true
                            text: i18n.pack.wifiKeyOf + " " + wifiKey.ssid
                            color: ui.text
                            font.pixelSize: ui.fontTitle
                            font.weight: Font.Bold
                            wrapMode: Text.Wrap
                        }
                        Field {
                            id: wifiKeyField

                            property bool revealed: false

                            symbolKeys: true
                            Layout.fillWidth: true
                            echoMode: revealed ? TextInput.Normal : TextInput.Password
                            placeholderText: i18n.pack.password
                            accessoryWidth: ui.touch
                            // Los puntos no deben destaparse al tocar Mayus.
                            Component.onCompleted: contentItem.passwordMaskDelay = 0

                            IconButton {
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                icon: wifiKeyField.revealed ? "eye-off" : "eye"
                                iconColor: ui.textMuted
                                onClicked: wifiKeyField.revealed = !wifiKeyField.revealed
                            }
                        }
                        RowLayout {
                            Layout.topMargin: ui.gap
                            spacing: ui.gap

                            TouchButton {
                                Layout.fillWidth: true
                                text: i18n.pack.cancel
                                kind: "neutral"
                                onClicked: wifiKey.close()
                            }
                            TouchButton {
                                Layout.fillWidth: true
                                text: i18n.pack.accept
                                kind: "success"
                                enabled: !wifi.busy
                                onClicked: {
                                    var secret = wifiKeyField.text
                                    var name = wifiKey.ssid
                                    wifiKey.close()
                                    wifi.connectTo(name, secret, wifiKey.secure)
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    visible: wifiKey.opened
                    color: "#A0000000"
                    z: 20
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: ui.gap

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            text: wifi.deviceName === "" ? i18n.pack.noWifi
                                  : (wifi.activeName === "" ? i18n.pack.noConnection : i18n.pack.connected + " " + wifi.activeName)
                            color: ui.text
                            font.pixelSize: ui.fontBody
                            elide: Text.ElideRight
                        }
                        TouchButton {
                            text: wifi.busy ? i18n.pack.searchingWifi : i18n.pack.search
                            icon: "refresh"
                            kind: "neutral"
                            enabled: !wifi.busy
                            onClicked: wifi.refresh()
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: Math.round(ui.gap * 0.5)

                        ListView {
                            id: wifiList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            interactive: false
                            spacing: Math.round(ui.gap * 0.4)
                            boundsBehavior: Flickable.StopAtBounds
                            model: wifiPage.networks

                            delegate: Rectangle {
                                readonly property string ssid: modelData.ssid || ""
                                readonly property bool secure: modelData.secure === true
                                readonly property bool activeNet: modelData.active === true
                                readonly property bool selected: wifiPage.chosen === ssid

                                width: wifiList.width
                                height: ui.touch
                                radius: ui.radius
                                color: activeNet ? ui.primary
                                       : (selected || area.pressed ? ui.surfaceHigh : ui.surfaceAlt)
                                border.width: selected ? 2 : 1
                                border.color: selected || activeNet ? ui.primary : ui.border

                                Text {
                                    anchors.fill: parent
                                    anchors.leftMargin: ui.padding
                                    anchors.rightMargin: ui.padding
                                    verticalAlignment: Text.AlignVCenter
                                    text: ssid + "   " + modelData.signal + "%   " + modelData.security
                                    color: activeNet ? ui.onAccent : ui.text
                                    font.pixelSize: ui.fontBody
                                    font.weight: selected ? Font.DemiBold : Font.Normal
                                    elide: Text.ElideRight
                                }
                                TouchArea {
                                    id: area
                                    onTapped: wifiPage.pick(ssid, secure)
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillHeight: true
                            Layout.preferredWidth: wifiList.contentHeight > wifiList.height + 1 ? Math.round(ui.mm * 4) : 0
                            visible: Layout.preferredWidth > 0
                            radius: ui.radius
                            color: ui.surfaceHigh
                            border.width: 1
                            border.color: ui.border

                            Rectangle {
                                readonly property real maxY: Math.max(0, wifiList.contentHeight - wifiList.height)
                                readonly property real handleHeight: Math.max(ui.touch * 0.6,
                                        parent.height * wifiList.height / Math.max(wifiList.contentHeight, 1))
                                x: 2
                                width: Math.max(0, parent.width - 4)
                                height: handleHeight
                                y: maxY <= 0 ? 0 : (parent.height - height) * (wifiList.contentY / maxY)
                                radius: width / 2
                                color: ui.primary
                            }
                            MouseArea {
                                anchors.fill: parent
                                onPressed: {
                                    var maxY = Math.max(0, wifiList.contentHeight - wifiList.height)
                                    var fraction = Math.max(0, Math.min(1, mouse.y / Math.max(1, height)))
                                    wifiList.contentY = fraction * maxY
                                }
                            }
                        }
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
                    title: i18n.pack.mode
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
                        model: [
                            { label: i18n.pack.modeDhcp, value: "dhcp" },
                            { label: i18n.pack.modeStatic, value: "static" }
                        ]
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
                              ? i18n.pack.modeStaticHint
                              : i18n.pack.modeDhcpHint
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        wrapMode: Text.Wrap
                    }
                }

                Card {
                    Layout.fillWidth: true
                    visible: modeChips.value !== "static"
                    title: i18n.pack.gotAddress
                    titleIcon: "info"

                    Text { text: i18n.pack.ipAddress; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    SelectableText { text: interna.address || i18n.pack.noAddress }
                    Text { text: i18n.pack.netmask; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    SelectableText { text: interna.netmask || i18n.pack.noNetmask }
                    Text { text: i18n.pack.gateway; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    SelectableText { text: interna.gateway || i18n.pack.noGateway }
                    Text { text: i18n.pack.dns; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    SelectableText { text: interna.dns || i18n.pack.noDns }
                }

                Card {
                    Layout.fillWidth: true
                    visible: modeChips.value === "static"
                    title: i18n.pack.staticAddress
                    titleIcon: "settings"

                    Text { text: i18n.pack.ipAddress; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: ip; Layout.fillWidth: true; Component.onCompleted: text = "192.168.1.10" }
                    Text { text: i18n.pack.netmask; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: mask; Layout.fillWidth: true; Component.onCompleted: text = "255.255.255.0" }
                    Text { text: i18n.pack.gateway; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: gateway; Layout.fillWidth: true; Component.onCompleted: text = "192.168.1.1" }
                    Text { text: i18n.pack.dns; color: ui.textMuted; font.pixelSize: ui.fontSmall }
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
                        text: i18n.pack.apply
                        icon: "check"
                        kind: "success"
                        enabled: !interna.busy
                        onClicked: dialog.ask({
                            title: i18n.pack.ethInternal,
                            kind: "warning",
                            message: modeChips.value === "static"
                                     ? i18n.pack.assignStatic.replace("{ip}", ip.text).replace("{iface}", interna.interfaceName)
                                     : i18n.pack.assignDhcp.replace("{iface}", interna.interfaceName),
                            confirmText: i18n.pack.apply,
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

            // Mantenimiento
            ScrollPage {
                Card {
                    Layout.fillWidth: true
                    title: i18n.pack.system
                    titleIcon: "info"

                    RowLayout {
                        Text {
                            Layout.fillWidth: true
                            text: i18n.pack.version + " " + system.version
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
                        text: i18n.pack.update
                        icon: "download"
                        kind: "success"
                        enabled: !system.busy
                        onClicked: dialog.ask({ title: i18n.pack.updateTitle, kind: "success",
                                                message: i18n.pack.updateBody,
                                                confirmText: i18n.pack.update, confirmAction: system.update })
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: i18n.pack.restartApp
                        icon: "restart"
                        kind: "warning"
                        enabled: !system.busy
                        onClicked: dialog.ask({ title: i18n.pack.restartTitle, kind: "warning",
                                                message: i18n.pack.restartBody,
                                                confirmText: i18n.pack.restart, confirmAction: system.reset })
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: i18n.pack.powerOff
                        icon: "power"
                        kind: "danger"
                        onClicked: dialog.ask({ title: i18n.pack.powerTitle, kind: "danger",
                                                message: i18n.pack.powerBody,
                                                confirmText: i18n.pack.power, confirmAction: system.poweroff })
                    }
                }
            }

            TouchTestPage { onGoBack: nav.currentIndex = 1 }
        }
    }
}
