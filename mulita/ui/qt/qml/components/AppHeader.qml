import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root

    property string title: ""
    property bool showBack: false
    property bool showShare: false
    readonly property bool narrow: width < ui.mm * 85
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
        spacing: root.narrow ? Math.round(ui.gap * 0.4) : ui.gap

        IconButton {
            visible: root.showBack
            icon: "back"
            onClicked: root.back()
        }

        RowLayout {
            Layout.fillWidth: true
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
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.maximumWidth: implicitWidth
                elide: Text.ElideRight
                text: "MULITA"
                color: ui.text
                font.pixelSize: ui.fontTitle
                font.weight: Font.Bold
                font.letterSpacing: ui.mm * 0.4
            }
            Text {
                visible: root.width > ui.mm * 150
                text: "Network Tool"
                color: ui.textMuted
                font.pixelSize: ui.fontSmall
                Layout.alignment: Qt.AlignVCenter
            }
            Item { Layout.fillWidth: true }
        }

        Text {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            visible: root.showBack
            text: root.title
            color: ui.text
            font.pixelSize: ui.fontTitle
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }

        IconButton {
            visible: root.showShare
            icon: "share"
            onClicked: root.share()
        }

        RowLayout {
            spacing: root.narrow ? 2 : ui.gap

            Repeater {
                model: ["wifi", "ethernet"]
                RowLayout {
                    readonly property string address: modelData === "wifi" ? network.wifiAddress : network.ethernetAddress
                    spacing: Math.round(ui.gap * 0.4)
                    Icon {
                        name: modelData
                        color: address ? ui.success : ui.textMuted
                        size: Math.round(ui.icon * (root.narrow ? 0.5 : 0.8))
                    }
                    Text {
                        text: address || "—"
                        color: ui.textMuted
                        Layout.preferredWidth: Math.min(implicitWidth, root.width * (root.narrow ? 0.21 : 0.22))
                        font.pixelSize: ui.fontSmall
                        fontSizeMode: Text.HorizontalFit
                        minimumPixelSize: 6
                    }
                }
            }
        }

        Text {
            id: clock
            Layout.preferredWidth: root.narrow ? Math.min(implicitWidth, root.width * 0.1) : implicitWidth
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: 8
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
