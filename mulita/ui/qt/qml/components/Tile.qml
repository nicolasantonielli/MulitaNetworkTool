import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root

    property string icon: ""
    property string title: ""
    property string subtitle: ""
    property bool active: false
    signal clicked()

    radius: ui.radius * 1.6
    color: area.pressed ? ui.surfaceHigh : ui.surface
    border.width: active ? 2 : 1
    border.color: active ? ui.success : ui.border
    scale: area.pressed ? 0.97 : 1

    Behavior on scale { NumberAnimation { duration: 90 } }
    Behavior on color { ColorAnimation { duration: 120 } }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Math.round(ui.padding * 1.1)
        spacing: Math.round(ui.gap * 0.4)

        RowLayout {
            Layout.fillWidth: true

            Rectangle {
                Layout.preferredWidth: Math.round(ui.touch * 1.05)
                Layout.preferredHeight: Layout.preferredWidth
                radius: ui.radius * 1.3
                color: Qt.rgba(ui.primary.r, ui.primary.g, ui.primary.b, 0.15)

                Icon {
                    anchors.centerIn: parent
                    name: root.icon
                    color: ui.primary
                    size: Math.round(ui.icon * 1.1)
                }
            }
            Item { Layout.fillWidth: true }
            StatusPill {
                visible: root.active
                text: "En curso"
                tone: ui.success
                pulsing: root.active
            }
        }

        Item { Layout.fillHeight: true }

        Text {
            Layout.fillWidth: true
            text: root.title
            color: ui.text
            font.pixelSize: ui.fontTitle
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Text {
            Layout.fillWidth: true
            text: root.subtitle
            color: ui.textMuted
            font.pixelSize: ui.fontSmall
            elide: Text.ElideRight
        }
    }

    TouchArea {
        id: area
        onTapped: root.clicked()
    }
}
