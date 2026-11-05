import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

ScrollPage {
    signal openJournalAdvanced()
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
        title: i18n.pack.remoteTitle
        titleIcon: "display"
        Switch {
            text: i18n.pack.remoteTitle
            enabled: remoteControl.available
            checked: remoteControl.enabled
            onToggled: remoteControl.setEnabled(checked)
            palette.windowText: ui.text
            implicitHeight: ui.touch
        }
        Text {
            Layout.fillWidth: true
            text: remoteControl.code ? i18n.pack.remoteCode + " " + remoteControl.code
                                     : (remoteControl.enabled ? i18n.pack.remoteConnected : i18n.pack.remoteHint)
            font.pixelSize: remoteControl.code ? ui.fontTitle : ui.fontSmall
            wrapMode: Text.Wrap
            color: ui.text
        }
    }

    Card {
        Layout.fillWidth: true
        title: i18n.pack.activityTitle
        titleIcon: "file"
        Switch {
            text: i18n.pack.activityRecord
            checked: settings.activityLogging
            onToggled: settings.setActivityLogging(checked)
            palette.windowText: ui.text
            implicitHeight: ui.touch
        }
    }

    Card {
        Layout.fillWidth: true
        title: i18n.pack.journalTitle
        titleIcon: "file"
        Switch {
            text: i18n.pack.journalRecord
            checked: settings.technicalJournal
            onToggled: settings.setTechnicalJournal(checked)
            palette.windowText: ui.text
            implicitHeight: ui.touch
        }
        TouchButton {
            objectName: "journalAdvancedButton"
            text: i18n.pack.journalAdvanced
            onClicked: openJournalAdvanced()
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
