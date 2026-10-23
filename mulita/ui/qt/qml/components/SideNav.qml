import QtQuick 2.15
import QtQuick.Layouts 1.15

// Navegacion lateral de secciones: filas grandes, faciles de tocar.
ColumnLayout {
    id: root

    property var items: []        // [{label, icon}]
    property int currentIndex: 0

    Layout.fillWidth: false
    spacing: Math.round(ui.gap * 0.4)

    Repeater {
        model: root.items

        delegate: Rectangle {
            id: row

            readonly property bool selected: index === root.currentIndex

            Layout.fillWidth: true
            implicitHeight: ui.touch
            radius: ui.radius
            color: selected ? ui.surfaceHigh : (area.pressed ? ui.surfaceAlt : "transparent")

            Rectangle {
                visible: row.selected
                width: Math.max(3, ui.mm * 0.8)
                height: parent.height * 0.55
                radius: width / 2
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                color: ui.primary
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: ui.padding
                anchors.rightMargin: ui.gap
                spacing: Math.round(ui.gap * 0.7)

                Icon {
                    name: modelData.icon
                    color: row.selected ? ui.primary : ui.textMuted
                    size: Math.round(ui.icon * 0.85)
                }
                Text {
                    Layout.fillWidth: true
                    text: modelData.label
                    color: row.selected ? ui.text : ui.textMuted
                    font.pixelSize: ui.fontBody
                    font.weight: row.selected ? Font.DemiBold : Font.Normal
                    elide: Text.ElideRight
                }
            }

            MouseArea {
                id: area
                anchors.fill: parent
                onClicked: root.currentIndex = index
            }
        }
    }

    Item { Layout.fillHeight: true }
}
