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

    function refresh() {
        if (!visible) return
        var days = activity.days
        if (days.indexOf(selectedDay) < 0) selectedDay = days.length ? days[0] : ""
        report = activity.read(selectedDay)
    }
    onVisibleChanged: refresh()
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
            model: activity.days
            visible: count > 0
            currentIndex: model.indexOf(root.selectedDay)
            onActivated: { root.selectedDay = currentText; root.refresh() }
        }
        TouchButton {
            text: i18n.pack.copy
            icon: "file"
            enabled: root.report.length > 0
            onClicked: system.copyText(root.report)
        }
    }
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
