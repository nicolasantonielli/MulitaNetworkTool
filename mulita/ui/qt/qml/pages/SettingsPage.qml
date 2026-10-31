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
            visible: currentIndex !== 5 && currentIndex !== 6
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
                    title: i18n.pack.tileOrderTitle
                    titleIcon: "display"

                    Text {
                        Layout.fillWidth: true
                        text: i18n.pack.tileOrderHint
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        wrapMode: Text.Wrap
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: i18n.pack.tileOrderOpen
                        icon: "play"
                        kind: "neutral"
                        onClicked: nav.currentIndex = 6
                    }
                }
                Card {
                    Layout.fillWidth: true
                    title: i18n.pack.language
                    titleIcon: "globe"

                    ComboBox {
                        id: languageMenu
                        Layout.fillWidth: true
                        implicitHeight: ui.touch
                        model: settings.languages
                        textRole: "label"
                        font.pixelSize: ui.fontBody
                        palette.button: ui.surfaceAlt
                        palette.buttonText: ui.text
                        palette.base: ui.surface
                        palette.text: ui.text
                        palette.highlight: ui.primary
                        palette.highlightedText: ui.onAccent
                        currentIndex: {
                            for (var i = 0; i < model.length; ++i)
                                if (model[i].value === settings.language)
                                    return i
                            return -1
                        }
                        onActivated: settings.setLanguage(model[index].value)
                        delegate: ItemDelegate {
                            width: languageMenu.width
                            height: ui.touch
                            text: modelData.label
                            font.pixelSize: ui.fontBody
                            highlighted: languageMenu.highlightedIndex === index
                        }
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
                    title: i18n.pack.resizeTiles
                    titleIcon: "display"
                    Switch {
                        text: i18n.pack.resizeTiles
                        checked: settings.resizeTiles
                        onToggled: settings.setResizeTiles(checked)
                        palette.windowText: ui.text
                        implicitHeight: ui.touch
                    }
                    Text {
                        Layout.fillWidth: true
                        text: i18n.pack.resizeTilesHint
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        wrapMode: Text.Wrap
                    }
                }
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

                property bool advanced: false
                property bool ipSettings: false
                readonly property var saved: {
                    try { return JSON.parse(wifi.savedJson) }
                    catch (e) { return [] }
                }

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
                        confirmAction: function() { wifi.connectRemembered(ssid, secure) }
                    })
                }

                function afterConfirm(ssid, secure) {
                    wifiKeyField.text = ""
                    wifiKeyField.revealed = false
                    wifiKey.ssid = ssid
                    wifiKey.secure = secure
                    wifiKey.open()
                }

                Connections {
                    target: wifi
                    function onPasswordRequested(ssid, secure) {
                        wifiPage.afterConfirm(ssid, secure)
                    }
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

            ScrollPage {
                id: wifiIpPage
                anchors.fill: parent
                    TouchButton {
                        text: i18n.pack.wifiBack
                        icon: "back"
                        enabled: !wifiIp.busy
                        onClicked: { wifiPage.ipSettings = false; wifi.refresh() }
                    }
                visible: wifiPage.ipSettings

                function apply() {
                    wifiIp.apply((wifiStaticSwitch.checked ? "static" : "dhcp"), wifiAddressField.text, wifiMaskField.text, wifiGatewayField.text, wifiDnsField.text)
                }

                function showStatic(address, netmask, gatewayAddress, dnsAddress) {
                    if (address)
                        wifiAddressField.text = address
                    if (netmask)
                        wifiMaskField.text = netmask
                    wifiGatewayField.text = gatewayAddress || ""
                    wifiDnsField.text = dnsAddress || ""
                }

                Card {
                    Layout.fillWidth: true
                    title: i18n.pack.mode
                    titleIcon: "wifi"

                    Text {
                        Layout.fillWidth: true
                        text: wifiIp.interfaceName + " · " + wifiIp.summary
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }
                    Switch {
                        id: wifiStaticSwitch
                        Layout.fillWidth: true
                        implicitHeight: ui.touch
                        enabled: !wifiIp.busy
                        checked: wifiIp.mode === "static"
                        text: checked ? i18n.pack.modeStatic : i18n.pack.modeDhcp
                        font.pixelSize: ui.fontBody
                        palette.windowText: ui.text
                        onToggled: {
                            if (checked)
                                wifiIpPage.showStatic(wifiIp.address, wifiIp.netmask, wifiIp.gateway, wifiIp.dns)
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: wifiStaticSwitch.checked
                              ? i18n.pack.modeStaticHint
                              : i18n.pack.modeDhcpHint
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        wrapMode: Text.Wrap
                    }
                }

                Card {
                    Layout.fillWidth: true
                    visible: !wifiStaticSwitch.checked
                    title: i18n.pack.gotAddress
                    titleIcon: "info"

                    Text { text: i18n.pack.ipAddress; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    SelectableText { text: wifiIp.address || i18n.pack.noAddress }
                    Text { text: i18n.pack.netmask; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    SelectableText { text: wifiIp.netmask || i18n.pack.noNetmask }
                    Text { text: i18n.pack.gateway; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    SelectableText { text: wifiIp.gateway || i18n.pack.noGateway }
                    Text { text: i18n.pack.dns; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    SelectableText { text: wifiIp.dns || i18n.pack.noDns }
                }

                Card {
                    Layout.fillWidth: true
                    visible: wifiStaticSwitch.checked
                    title: i18n.pack.staticAddress
                    titleIcon: "settings"

                    Text { text: i18n.pack.ipAddress; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: wifiAddressField; Layout.fillWidth: true; Component.onCompleted: text = "192.168.1.10" }
                    Text { text: i18n.pack.netmask; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: wifiMaskField; Layout.fillWidth: true; Component.onCompleted: text = "255.255.255.0" }
                    Text { text: i18n.pack.gateway; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: wifiGatewayField; Layout.fillWidth: true; Component.onCompleted: text = "192.168.1.1" }
                    Text { text: i18n.pack.dns; color: ui.textMuted; font.pixelSize: ui.fontSmall }
                    Field { id: wifiDnsField; Layout.fillWidth: true; Component.onCompleted: text = "8.8.8.8" }
                }

                RowLayout {
                    BusyIndicator {
                        running: wifiIp.busy
                        visible: running
                        Layout.preferredWidth: ui.touch
                        Layout.preferredHeight: ui.touch
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: i18n.pack.apply
                        icon: "check"
                        kind: "success"
                        enabled: !wifiIp.busy
                        onClicked: dialog.ask({
                            title: i18n.pack.wifiIp,
                            kind: "warning",
                            message: wifiStaticSwitch.checked
                                     ? i18n.pack.assignStatic.replace("{ip}", wifiAddressField.text).replace("{iface}", wifiIp.interfaceName)
                                     : i18n.pack.assignDhcp.replace("{iface}", wifiIp.interfaceName),
                            confirmText: i18n.pack.apply,
                            confirmAction: wifiIpPage.apply
                        })
                    }
                }

                Connections {
                    target: wifiIp
                    function onLoaded() {
                        wifiStaticSwitch.checked = wifiIp.mode === "static"
                        if (wifiIp.mode !== "static")
                            return
                        wifiIpPage.showStatic(wifiIp.address, wifiIp.netmask, wifiIp.gateway, wifiIp.dns)
                    }
                }
            }

                ColumnLayout {
                    anchors.fill: parent
                    visible: wifiPage.advanced && !wifiPage.ipSettings
                    spacing: ui.gap
                    RowLayout {
                        Layout.fillWidth: true
                        TouchButton {
                            text: i18n.pack.wifiBack
                            icon: "back"
                            kind: "neutral"
                            enabled: !wifi.busy
                            onClicked: {
                                wifiPage.advanced = false
                                wifi.refresh()
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: i18n.pack.wifiAdvanced + " · " + i18n.pack.wifiSaved
                            color: ui.text
                            font.pixelSize: ui.fontBody
                            wrapMode: Text.Wrap
                        }
                        IconButton {
                            icon: "refresh"
                            enabled: !wifi.busy
                            onClicked: wifi.loadSaved()
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: ui.surface
                        radius: ui.radius
                        border.color: ui.border
                        ListView {
                            id: savedWifiList
                            anchors.fill: parent
                            anchors.margins: ui.gap
                            clip: true
                            spacing: ui.gap
                            model: wifiPage.saved
                            ScrollBar.vertical: ScrollBar {}
                            delegate: Rectangle {
                                id: savedWifiRow
                                readonly property string profileUuid: modelData.uuid
                                readonly property string profileName: modelData.name
                                width: savedWifiList.width
                                height: ui.touch
                                color: ui.surfaceAlt
                                radius: ui.radius
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: ui.padding
                                    Text {
                                        Layout.fillWidth: true
                                        text: savedWifiRow.profileName
                                        color: ui.text
                                        font.pixelSize: ui.fontBody
                                        elide: Text.ElideRight
                                    }
                                    IconButton {
                                        icon: "trash"
                                        iconColor: ui.danger
                                        enabled: !wifi.busy
                                        onClicked: {
                                            var uuid = savedWifiRow.profileUuid
                                            var name = savedWifiRow.profileName
                                            dialog.ask({
                                                title: i18n.pack.wifiForget + " · " + name,
                                                message: i18n.pack.wifiSavedConfirm,
                                                confirmText: i18n.pack.wifiForget,
                                                cancelText: i18n.pack.cancel,
                                                confirmAction: function() { wifi.forgetSaved(uuid) }
                                            })
                                        }
                                    }
                                }
                            }
                        }
                        Text {
                            anchors.centerIn: parent
                            width: parent.width - ui.padding * 2
                            visible: wifiPage.saved.length === 0
                            text: wifi.busy ? i18n.pack.reading : i18n.pack.wifiSavedEmpty
                            color: ui.textMuted
                            font.pixelSize: ui.fontBody
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                        }
                    }
                }

                ColumnLayout {
                    anchors.fill: parent
                    visible: !wifiPage.advanced && !wifiPage.ipSettings
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

                    TouchButton {
                        text: i18n.pack.wifiIp
                        kind: "neutral"
                        enabled: !wifi.busy && wifi.activeName !== ""
                        onClicked: { wifiPage.ipSettings = true; wifiIp.refresh() }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: ui.gap
                        TouchButton {
                            text: i18n.pack.wifiDisconnect
                            kind: "neutral"
                            enabled: !wifi.busy && wifi.activeName !== ""
                            onClicked: wifi.disconnect()
                        }
                        TouchButton {
                            text: i18n.pack.wifiAdvanced
                            kind: "neutral"
                            enabled: !wifi.busy
                            onClicked: {
                                wifiPage.advanced = true
                                wifi.loadSaved()
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: ui.gap

                        ListView {
                            id: wifiList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            interactive: contentHeight > height + 1
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
                    interna.applyVlan((ethernetStaticSwitch.checked ? "static" : "dhcp"), ip.text, mask.text, gateway.text, dns.text, vlanSwitch.checked, vlanNumber.text)
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
                    title: i18n.pack.vlanTitle
                    titleIcon: "ethernet"
                    Switch {
                        id: vlanSwitch
                        text: i18n.pack.vlanTitle
                        checked: interna.vlanId > 0
                        enabled: !interna.busy
                        implicitHeight: ui.touch
                        palette.windowText: ui.text
                        font.pixelSize: ui.fontBody
                    }
                    Text {
                        Layout.fillWidth: true
                        text: i18n.pack.vlanNumber
                        visible: vlanSwitch.checked
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                    }
                    Field {
                        id: vlanNumber
                        numericKeyboard: true
                        Layout.fillWidth: true
                        visible: vlanSwitch.checked
                        enabled: !interna.busy
                        text: interna.vlanId > 0 ? String(interna.vlanId) : "1"
                        inputMethodHints: Qt.ImhDigitsOnly
                        validator: IntValidator { bottom: 1; top: 4094 }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: i18n.pack.vlanHint
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }
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
                    Switch {
                        id: ethernetStaticSwitch
                        Layout.fillWidth: true
                        implicitHeight: ui.touch
                        enabled: !interna.busy
                        checked: interna.mode === "static"
                        text: checked ? i18n.pack.modeStatic : i18n.pack.modeDhcp
                        font.pixelSize: ui.fontBody
                        palette.windowText: ui.text
                        onToggled: {
                            if (checked)
                                internaPage.showStatic(interna.address, interna.netmask, interna.gateway, interna.dns)
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: ethernetStaticSwitch.checked
                              ? i18n.pack.modeStaticHint
                              : i18n.pack.modeDhcpHint
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        wrapMode: Text.Wrap
                    }
                }

                Card {
                    Layout.fillWidth: true
                    visible: !ethernetStaticSwitch.checked
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
                    visible: ethernetStaticSwitch.checked
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
                            message: (vlanSwitch.checked ? i18n.pack.vlanTitle + " " + vlanNumber.text : i18n.pack.vlanUntagged) + "\n\n" + (ethernetStaticSwitch.checked
                                     ? i18n.pack.assignStatic.replace("{ip}", ip.text).replace("{iface}", interna.interfaceName)
                                     : i18n.pack.assignDhcp.replace("{iface}", interna.interfaceName)),
                            confirmText: i18n.pack.apply,
                            confirmAction: internaPage.apply
                        })
                    }
                }

                Connections {
                    target: interna
                    function onLoaded() {
                        vlanSwitch.checked = interna.vlanId > 0
                        vlanNumber.text = interna.vlanId > 0 ? String(interna.vlanId) : "1"
                        ethernetStaticSwitch.checked = interna.mode === "static"
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
            TileOrderPage { onGoBack: nav.currentIndex = 0 }
        }
    }
}
