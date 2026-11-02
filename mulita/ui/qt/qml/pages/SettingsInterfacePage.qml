import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

ScrollPage {
    signal openTileOrder()
    Card {
        Layout.fillWidth: true
        title: i18n.pack.tileOrderTitle
        titleIcon: "display"

        Text {
            Layout.fillWidth: true
            text: i18n.pack.tileOrderHint
            color: ui.textMuted
            font.pixelSize: ui.fontBody
            wrapMode: Text.Wrap
        }
        TouchButton {
            Layout.fillWidth: true
            text: i18n.pack.tileOrderOpen
            icon: "play"
            kind: "neutral"
            onClicked: openTileOrder()
        }
    }
    Card {
        Layout.fillWidth: true
        title: i18n.pack.theme
        titleIcon: "theme"

        ChoiceChips {
            Layout.fillWidth: true
            model: settings.themes
            value: settings.theme
            onActivated: settings.setTheme(value)
        }
    }
    Card {
        Layout.fillWidth: true
        title: i18n.pack.resizeTiles
        titleIcon: "display"
        Switch {
            text: i18n.pack.resizeTiles
            checked: settings.resizeTiles
            onToggled: settings.setResizeTiles(checked)
            palette.windowText: ui.text
            implicitHeight: ui.touch
        }
        Text {
            Layout.fillWidth: true
            text: i18n.pack.resizeTilesHint
            color: ui.textMuted
            font.pixelSize: ui.fontBody
            wrapMode: Text.Wrap
        }
    }
}
