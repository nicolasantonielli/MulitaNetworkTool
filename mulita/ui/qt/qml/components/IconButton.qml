import QtQuick 2.15

Rectangle {
    id: root

    property string icon: ""
    property color iconColor: ui.text
    signal clicked()

    implicitWidth: ui.touch
    implicitHeight: ui.touch
    radius: ui.radius
    color: area.pressed ? ui.surfaceHigh : "transparent"

    Icon {
        anchors.centerIn: parent
        name: root.icon
        color: root.iconColor
    }

    MouseArea {
        id: area
        anchors.fill: parent
        onClicked: root.clicked()
    }
}
