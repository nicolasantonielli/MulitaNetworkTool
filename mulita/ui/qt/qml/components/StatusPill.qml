import QtQuick 2.15

Rectangle {
    id: root

    property string text: ""
    property color tone: ui.textMuted
    property bool pulsing: false

    implicitHeight: Math.round(ui.touch * 0.62)
    implicitWidth: row.implicitWidth + ui.padding * 1.2
    radius: height / 2
    color: Qt.rgba(tone.r, tone.g, tone.b, 0.16)

    onPulsingChanged: if (!pulsing) dot.opacity = 1

    Row {
        id: row
        anchors.centerIn: parent
        spacing: Math.round(ui.gap * 0.5)

        Rectangle {
            id: dot
            anchors.verticalCenter: parent.verticalCenter
            width: Math.round(ui.mm * 1.8)
            height: width
            radius: width / 2
            color: root.tone

            SequentialAnimation on opacity {
                running: root.pulsing
                loops: Animation.Infinite
                NumberAnimation { to: 0.25; duration: 650; easing.type: Easing.InOutQuad }
                NumberAnimation { to: 1; duration: 650; easing.type: Easing.InOutQuad }
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            color: root.tone
            font.pixelSize: ui.fontSmall
            font.weight: Font.DemiBold
        }
    }
}
