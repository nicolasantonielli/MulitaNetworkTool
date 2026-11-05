import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

ColumnLayout {
    id: root
    objectName: "activityPage"
    spacing: ui.gap
    property string selectedDay: ""
    property string report: ""
    property var availableDays: []
    property string exportDay: ""
    readonly property var drives: JSON.parse(files.drivesJson)

    function refresh() {
        if (!visible) return
        var days = activity.days
        if (days.join() !== availableDays.join()) availableDays = days
        if (days.indexOf(selectedDay) < 0) selectedDay = days.length ? days[0] : ""
        if (days.indexOf(exportDay) < 0) exportDay = ""
        report = activity.read(selectedDay)
    }
    onVisibleChanged: refresh()
    Timer {
        interval: 3000
        running: root.visible
        repeat: true
        onTriggered: {
            if (activity.days.join() !== root.availableDays.join()) root.refresh()
        }
    }
    Connections {
        target: activity
        function onChanged() { root.refresh() }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: ui.padding
        Layout.rightMargin: ui.padding
        Layout.topMargin: ui.gap
        Text {
            Layout.fillWidth: true
            text: settings.activityLogging ? i18n.pack.activityOn : i18n.pack.activityOff
            color: settings.activityLogging ? ui.success : ui.textMuted
            font.pixelSize: ui.fontSmall
            wrapMode: Text.Wrap
        }
        ComboBox {
            implicitHeight: ui.touch
            model: root.availableDays
            visible: count > 0
            currentIndex: model.indexOf(root.selectedDay)
            onActivated: { root.exportDay = ""; root.selectedDay = currentText; root.refresh() }
        }
    }
    RowLayout {
        Layout.leftMargin: ui.padding
        Layout.rightMargin: ui.padding
        visible: root.selectedDay !== ""
        TouchButton {
            text: i18n.pack.copy
            icon: "file"
            enabled: root.report.length > 0
            onClicked: system.copyText(root.report)
        }
        TouchButton {
            text: i18n.pack.export
            enabled: !files.busy
            onClicked: { root.exportDay = root.selectedDay; files.refreshDrives() }
        }
        TouchButton {
            text: i18n.pack.delete
            kind: "danger"
            onClicked: {
                var day = root.selectedDay
                confirmation.ask({title: i18n.pack.delete, message: i18n.pack.deleteBody.replace("{name}", day + ".log"),
                    confirmText: i18n.pack.delete, cancelText: i18n.pack.cancel,
                    confirmAction: function() { activity.deleteDay(day) }})
            }
        }
    }
    RowLayout {
        visible: root.exportDay !== ""
        Layout.leftMargin: ui.padding
        Layout.rightMargin: ui.padding
        Text {
            visible: root.drives.length === 0
            text: files.busy ? i18n.pack.searching : i18n.pack.noUsb
            color: ui.textMuted
            font.pixelSize: ui.fontSmall
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
        ComboBox {
            id: usb
            visible: root.drives.length > 0
            implicitHeight: ui.touch
            model: root.drives
            textRole: "label"
            Layout.fillWidth: true
        }
        TouchButton {
            text: i18n.pack.export
            visible: root.drives.length > 0
            enabled: !files.busy && usb.currentIndex >= 0
            onClicked: {
                files.exportFile("actividad", root.exportDay + ".log", root.drives[usb.currentIndex].value)
                root.exportDay = ""
            }
        }
        TouchButton {
            text: i18n.pack.cancel
            kind: "neutral"
            onClicked: root.exportDay = ""
        }
    }
    ConfirmDialog { id: confirmation }
    ScrollPage {
        Layout.leftMargin: ui.padding
        Layout.rightMargin: ui.padding
        Text {
            Layout.fillWidth: true
            text: root.report || (i18n.pack.activityEmpty + (settings.activityLogging ? "" : " " + i18n.pack.activityEnableHint))
            textFormat: Text.PlainText
            wrapMode: Text.WrapAnywhere
            color: ui.text
            font.pixelSize: ui.fontSmall
        }
    }
}
