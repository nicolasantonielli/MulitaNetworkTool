import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ColumnLayout {
    id: form
    property var controller
    property var dialog
    property string icon: "wifi"
    property string confirmationTitle: ""
    property string confirmationPrefix: ""
    property alias address: addressField.text
    property alias netmask: maskField.text
    property alias gateway: gatewayField.text
    property alias dns: dnsField.text
    signal applyRequested(string mode, string address, string netmask, string gateway, string dns)
    Layout.fillWidth: true
    spacing: ui.gap
    function load() {
        staticSwitch.checked = controller.mode === "static"
        showStatic(controller.address, controller.netmask, controller.gateway, controller.dns)
    }
    Component.onCompleted: load()
    function apply() {
        form.applyRequested((staticSwitch.checked ? "static" : "dhcp"), addressField.text, maskField.text, gatewayField.text, dnsField.text)
    }

    function showStatic(address, netmask, gatewayAddress, dnsAddress) {
        addressField.text = address || "192.168.1.10"
        maskField.text = netmask || "255.255.255.0"
        gatewayField.text = gatewayAddress || ""
        dnsField.text = dnsAddress || ""
    }

    Card {
        Layout.fillWidth: true
        title: i18n.pack.mode
        titleIcon: form.icon

        Text {
            Layout.fillWidth: true
            text: controller.interfaceName + " · " + controller.summary
            color: ui.textMuted
            font.pixelSize: ui.fontSmall
            wrapMode: Text.Wrap
        }
        Switch {
            id: staticSwitch
            Layout.fillWidth: true
            implicitHeight: ui.touch
            enabled: !controller.busy
            checked: controller.mode === "static"
            text: checked ? i18n.pack.modeStatic : i18n.pack.modeDhcp
            font.pixelSize: ui.fontBody
            palette.windowText: ui.text
            onToggled: {
                if (checked)
                    form.showStatic(controller.address, controller.netmask, controller.gateway, controller.dns)
            }
        }
        Text {
            Layout.fillWidth: true
            text: staticSwitch.checked
                  ? i18n.pack.modeStaticHint
                  : i18n.pack.modeDhcpHint
            color: ui.textMuted
            font.pixelSize: ui.fontBody
            wrapMode: Text.Wrap
        }
    }

    Card {
        Layout.fillWidth: true
        visible: !staticSwitch.checked
        title: i18n.pack.gotAddress
        titleIcon: "info"

        Text { text: i18n.pack.ipAddress; color: ui.textMuted; font.pixelSize: ui.fontSmall }
        SelectableText { text: controller.address || i18n.pack.noAddress }
        Text { text: i18n.pack.netmask; color: ui.textMuted; font.pixelSize: ui.fontSmall }
        SelectableText { text: controller.netmask || i18n.pack.noNetmask }
        Text { text: i18n.pack.gateway; color: ui.textMuted; font.pixelSize: ui.fontSmall }
        SelectableText { text: controller.gateway || i18n.pack.noGateway }
        Text { text: i18n.pack.dns; color: ui.textMuted; font.pixelSize: ui.fontSmall }
        SelectableText { text: controller.dns || i18n.pack.noDns }
    }

    Card {
        Layout.fillWidth: true
        visible: staticSwitch.checked
        title: i18n.pack.staticAddress
        titleIcon: "settings"

        Text { text: i18n.pack.ipAddress; color: ui.textMuted; font.pixelSize: ui.fontSmall }
        Field { id: addressField; Layout.fillWidth: true }
        Text { text: i18n.pack.netmask; color: ui.textMuted; font.pixelSize: ui.fontSmall }
        Field { id: maskField; Layout.fillWidth: true }
        Text { text: i18n.pack.gateway; color: ui.textMuted; font.pixelSize: ui.fontSmall }
        Field { id: gatewayField; Layout.fillWidth: true }
        Text { text: i18n.pack.dns; color: ui.textMuted; font.pixelSize: ui.fontSmall }
        Field { id: dnsField; Layout.fillWidth: true }
    }

    RowLayout {
        BusyIndicator {
            running: controller.busy
            visible: running
            Layout.preferredWidth: ui.touch
            Layout.preferredHeight: ui.touch
        }
        TouchButton {
            Layout.fillWidth: true
            text: i18n.pack.apply
            icon: "check"
            kind: "success"
            enabled: !controller.busy
            onClicked: dialog.ask({
                title: form.confirmationTitle,
                kind: "warning",
                message: form.confirmationPrefix + (staticSwitch.checked
                         ? i18n.pack.assignStatic.replace("{ip}", addressField.text).replace("{iface}", controller.interfaceName)
                         : i18n.pack.assignDhcp.replace("{iface}", controller.interfaceName)),
                confirmText: i18n.pack.apply,
                confirmAction: form.apply
            })
        }
    }

    Connections {
        target: controller
        function onLoaded() { form.load() }
    }
}
