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
    property var availableDays: []
    property string exportDay: ""
    readonly property var drives: JSON.parse(files.drivesJson)

    function refresh() {
        if (!visible || !root.journal) return
        root.journal.refresh(root.selectedDay)
    }
    function applySnapshot() {
        var days = root.journal.days
        if (days.join() !== availableDays.join()) availableDays = days
        selectedDay = root.journal.day
        if (days.indexOf(exportDay) < 0) exportDay = ""
        report = root.journal.report
    }
    onVisibleChanged: refresh()
    Timer {
        interval: 3000
        running: root.visible
        repeat: true
        onTriggered: root.refresh()
    }
    Connections {
        target: root.journal
        function onChanged() { root.applySnapshot() }
        function onInvalidated() { root.refresh() }
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
            enabled: !root.journal.busy && root.report.length > 0
            onClicked: system.copyText(root.report)
        }
        TouchButton {
            text: i18n.pack.export + (root.technical ? " CSV" : "")
            enabled: !files.busy && !root.journal.busy
            onClicked: { root.exportDay = root.selectedDay; files.refreshDrives() }
        }
        TouchButton {
            text: i18n.pack.delete
            kind: "danger"
            enabled: !root.journal.busy
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
            text: i18n.pack.export + (root.technical ? " CSV" : "")
            visible: root.drives.length > 0
            enabled: !files.busy && !root.journal.busy && usb.currentIndex >= 0
            onClicked: {
                if (root.technical) files.exportJournalCsv(root.exportDay, root.drives[usb.currentIndex].value)
                else files.exportFile("actividad", root.exportDay + root.suffix, root.drives[usb.currentIndex].value)
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
    ListView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.leftMargin: ui.padding
        Layout.rightMargin: ui.padding
        visible: root.technical && count > 0
        clip: true
        model: root.technical ? root.journal.entries : []
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { minimumSize: 0.1 }
        delegate: Item {
            id: entry
            width: ListView.view.width
            height: Math.max(card.height, clock.implicitHeight) + ui.gap
            readonly property color accent: modelData.phase === "failed" ? ui.danger :
                (modelData.phase === "completed" ? ui.success : (modelData.phase === "stop" ? ui.warning : ui.primary))
            readonly property real railX: ui.fontSmall * 6.4
            Column {
                id: clock
                width: entry.railX - ui.gap
                spacing: ui.gap / 3
                Text { width: parent.width; text: modelData.time; color: ui.text; font.pixelSize: ui.fontBody; font.bold: true; textFormat: Text.PlainText }
                Text { width: parent.width; text: modelData.date; color: ui.textMuted; font.pixelSize: ui.fontSmall * 0.85; textFormat: Text.PlainText }
            }
            Rectangle { x: entry.railX; width: 1; height: parent.height; color: ui.border }
            Rectangle {
                x: entry.railX - width / 2; y: ui.gap / 2
                width: ui.fontSmall; height: width; radius: width / 2
                color: ui.background; border.width: Math.max(2, ui.mm * 0.7); border.color: entry.accent
            }
            Rectangle {
                id: card
                x: entry.railX + ui.gap * 1.5
                width: Math.max(0, parent.width - x - ui.gap)
                height: cardBody.implicitHeight + ui.gap * 2
                color: ui.surface; radius: ui.radius; border.color: ui.border
                Column {
                    id: cardBody
                    x: ui.gap; y: ui.gap; width: parent.width - ui.gap * 2
                    spacing: ui.gap * 0.7
                    Rectangle {
                        width: Math.min(cardBody.width, badge.implicitWidth + ui.gap * 2)
                        height: badge.implicitHeight + ui.gap
                        color: ui.surfaceHigh
                        radius: ui.radius
                        border.color: entry.accent
                        Text {
                            id: badge
                            x: ui.gap; y: ui.gap / 2; width: parent.width - ui.gap * 2
                            text: modelData.kind || i18n.pack.journalLegacy
                            color: ui.text; font.pixelSize: ui.fontSmall; font.bold: true
                            wrapMode: Text.Wrap; textFormat: Text.PlainText
                        }
                    }
                    Text {
                        width: parent.width; visible: text.length > 0
                        text: modelData.text; color: ui.text; font.pixelSize: ui.fontBody
                        wrapMode: Text.WrapAnywhere; textFormat: Text.PlainText
                    }
                    Text {
                        width: parent.width; visible: modelData.results.length > 0
                        text: i18n.pack.journalResults; color: ui.textMuted; font.pixelSize: ui.fontSmall; font.bold: true
                    }
                    Text {
                        width: parent.width; visible: text.length > 0
                        text: modelData.results; color: ui.text; font.pixelSize: ui.fontSmall
                        wrapMode: Text.WrapAnywhere; textFormat: Text.PlainText
                    }
                }
            }
        }
    }
    ScrollPage {
        visible: !root.technical || root.journal.entries.length === 0
        Layout.leftMargin: ui.padding
        Layout.rightMargin: ui.padding
        Text {
            Layout.fillWidth: true
            text: root.journal.busy && root.selectedDay !== root.journal.day ? i18n.pack.journalLoading :
                  (root.report || (root.journal.busy ? i18n.pack.journalLoading :
                  ((root.technical ? i18n.pack.journalEmpty : i18n.pack.activityEmpty) + (root.recording ? "" : " " + i18n.pack.activityEnableHint))))
            textFormat: Text.PlainText
            wrapMode: Text.WrapAnywhere
            color: ui.text
            font.pixelSize: ui.fontSmall
        }
    }
}
