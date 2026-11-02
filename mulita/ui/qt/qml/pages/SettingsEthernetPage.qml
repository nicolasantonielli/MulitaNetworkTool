import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

ScrollPage {
    id: internaPage
    property var dialog

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

    IPv4Form {
        controller: interna
        dialog: internaPage.dialog
        icon: "ethernet"
        confirmationTitle: i18n.pack.ethInternal
        confirmationPrefix: (vlanSwitch.checked ? i18n.pack.vlanTitle + " " + vlanNumber.text : i18n.pack.vlanUntagged) + "\n\n"
        onApplyRequested: interna.applyVlan(mode, address, netmask, gateway, dns, vlanSwitch.checked, vlanNumber.text)
    }
    Connections {
        target: interna
        function onLoaded() {
            vlanSwitch.checked = interna.vlanId > 0
            vlanNumber.text = interna.vlanId > 0 ? String(interna.vlanId) : "1"
        }
    }
}
