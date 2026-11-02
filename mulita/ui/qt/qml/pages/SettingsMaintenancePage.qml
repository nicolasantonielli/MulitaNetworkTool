import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

ScrollPage {
    property var dialog
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
