import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

ColumnLayout {
    objectName: "journalSettingsPage"
    signal goBack()
    spacing: ui.gap
    RowLayout {
        Layout.fillWidth: true
        TouchButton { icon: "back"; text: i18n.pack.navGeneral; onClicked: goBack() }
        Text {
            Layout.fillWidth: true
            text: i18n.pack.journalTestSettings
            color: ui.text; font.pixelSize: ui.fontTitle; wrapMode: Text.Wrap
        }
    }
    Text {
        Layout.fillWidth: true
        text: i18n.pack.journalTestsHint
        color: ui.textMuted; font.pixelSize: ui.fontSmall; wrapMode: Text.Wrap
    }
    ScrollPage {
        Repeater {
            id: testSwitches
            model: settings.journalTests
            Switch {
                objectName: "journal-test-" + modelData.id
                Layout.fillWidth: true
                implicitHeight: ui.touch
                text: modelData.label
                checked: modelData.enabled
                palette.windowText: ui.text
                font.pixelSize: ui.fontBody
                onToggled: settings.setJournalTest(modelData.id, checked)
            }
        }
    }
}
