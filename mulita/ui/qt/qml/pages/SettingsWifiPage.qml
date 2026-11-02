import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: wifiPage
    property var dialog

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

    IPv4Form {
        controller: wifiIp
        dialog: wifiPage.dialog
        confirmationTitle: i18n.pack.wifiIp
        onApplyRequested: wifiIp.apply(mode, address, netmask, gateway, dns)
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
