import QtQuick 2.15
import QtQuick.Controls 2.15

TabBar {
    id: root

    readonly property bool allowsTextCopy: false

    property var tabs: []

    implicitHeight: ui.touch
    background: Rectangle {
        color: "transparent"
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: ui.border
        }
    }

    Repeater {
        model: root.tabs

        TabButton {
            text: modelData
            implicitHeight: ui.touch
            font.pixelSize: ui.fontBody
            font.weight: root.currentIndex === index ? Font.DemiBold : Font.Normal
        }
    }
}
