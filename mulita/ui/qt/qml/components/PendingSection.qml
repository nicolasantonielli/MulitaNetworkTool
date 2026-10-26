import QtQuick 2.15
import QtQuick.Layouts 1.15

ScrollPage {
    id: root

    property string title: ""
    property string icon: ""
    signal goHome()

    Card {
        Layout.fillWidth: true
        title: root.title
        titleIcon: root.icon

        Text {
            Layout.fillWidth: true
            text: i18n.pack.pending
            color: ui.textMuted
            font.pixelSize: ui.fontBody
            wrapMode: Text.Wrap
        }
        TouchButton {
            text: i18n.pack.backHome
            icon: "back"
            kind: "neutral"
            onClicked: root.goHome()
        }
    }
}
