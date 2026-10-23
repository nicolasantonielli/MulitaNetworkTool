import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root

    property string title: ""
    property bool showBack: false
    property bool showShare: false
    signal back()
    signal share()

    implicitHeight: ui.header
    color: ui.surface

    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: ui.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: root.showBack ? Math.round(ui.gap * 0.5) : ui.padding
        anchors.rightMargin: ui.padding
        spacing: ui.gap

        IconButton {
            visible: root.showBack
            icon: "back"
            onClicked: root.back()
        }

        RowLayout {
            visible: !root.showBack
            spacing: Math.round(ui.gap * 0.7)

            Rectangle {
                Layout.preferredWidth: Math.round(ui.header * 0.66)
                Layout.preferredHeight: Layout.preferredWidth
                radius: ui.radius
                color: ui.primary

                Icon {
                    anchors.centerIn: parent
                    name: "logo"
                    color: ui.onAccent
                    size: Math.round(parent.width * 0.7)
                }
            }
            Text {
                text: "MULITA"
                color: ui.text
                font.pixelSize: ui.fontTitle
                font.weight: Font.Bold
                font.letterSpacing: ui.mm * 0.4
            }
            Text {
                text: "Network Tool"
                color: ui.textMuted
                font.pixelSize: ui.fontSmall
                Layout.alignment: Qt.AlignVCenter
            }
        }

        Text {
            Layout.fillWidth: true
            visible: root.showBack
            text: root.title
            color: ui.text
            font.pixelSize: ui.fontTitle
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Item {
            Layout.fillWidth: true
            visible: !root.showBack
        }

        IconButton {
            visible: root.showShare
            icon: "share"
            onClicked: root.share()
        }

        RowLayout {
            spacing: Math.round(ui.gap * 0.4)

            Icon {
                name: network.primaryAddress !== "" ? "network" : "network-off"
                color: network.primaryAddress !== "" ? ui.success : ui.textMuted
                size: Math.round(ui.icon * 0.8)
            }
            Text {
                text: network.primaryAddress !== "" ? network.primaryAddress : "Sin red"
                color: ui.textMuted
                font.pixelSize: ui.fontSmall
            }
        }

        Text {
            id: clock
            text: Qt.formatTime(new Date(), "HH:mm")
            color: ui.text
            font.pixelSize: ui.fontBody
            font.weight: Font.DemiBold
            font.family: ui.monoFamily

            Timer {
                interval: 1000
                repeat: true
                running: true
                onTriggered: clock.text = Qt.formatTime(new Date(), "HH:mm")
            }
        }
    }
}
