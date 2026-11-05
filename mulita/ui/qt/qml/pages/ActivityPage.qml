import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

ColumnLayout {
    id: root
    property bool technical: false
    readonly property var journal: technical ? technicalJournal : activity
    readonly property bool recording: technical ? settings.technicalJournal : settings.activityLogging
    readonly property string suffix: technical ? ".txt" : ".log"
    objectName: technical ? "technicalJournalPage" : "activityPage"
    spacing: ui.gap
    property string selectedDay: ""
    property string report: ""
    property string fileRevision: ""
    property var availableDays: []
    property string exportDay: ""
    readonly property var drives: JSON.parse(files.drivesJson)

    function refresh() {
        if (!visible || !root.journal) return
        var days = root.journal.days
        if (days.join() !== availableDays.join()) availableDays = days
        if (days.indexOf(selectedDay) < 0) selectedDay = days.length ? days[0] : ""
        if (days.indexOf(exportDay) < 0) exportDay = ""
        fileRevision = root.journal.revision(selectedDay)
        report = root.journal.read(selectedDay)
    }
    onVisibleChanged: refresh()
    Timer {
        interval: 3000
        running: root.visible
        repeat: true
        onTriggered: {
            if (root.journal.days.join() !== root.availableDays.join() ||
                    root.journal.revision(root.selectedDay) !== root.fileRevision) root.refresh()
        }
    }
    Connections {
        target: root.journal
        function onChanged() { root.refresh() }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: ui.padding
        Layout.rightMargin: ui.padding
        Layout.topMargin: ui.gap
        Text {
            Layout.fillWidth: true
            text: root.recording ? i18n.pack.activityOn : i18n.pack.activityOff
            color: root.recording ? ui.success : ui.textMuted
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
                confirmation.ask({title: i18n.pack.delete, message: i18n.pack.deleteBody.replace("{name}", day + root.suffix),
                    confirmText: i18n.pack.delete, cancelText: i18n.pack.cancel,
                    confirmAction: function() { root.journal.deleteDay(day) }})
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
                files.exportFile(root.technical ? "bitacora" : "actividad", root.exportDay + root.suffix, root.drives[usb.currentIndex].value)
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
            text: root.report || ((root.technical ? i18n.pack.journalEmpty : i18n.pack.activityEmpty) + (root.recording ? "" : " " + i18n.pack.activityEnableHint))
            textFormat: Text.PlainText
            wrapMode: Text.WrapAnywhere
            color: ui.text
            font.pixelSize: ui.fontSmall
        }
    }
}
