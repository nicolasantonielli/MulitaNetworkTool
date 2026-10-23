import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root

    property string title: ""
    property string titleIcon: ""
    default property alias content: body.data

    implicitHeight: column.implicitHeight + margin * 2
    readonly property int margin: Math.round(ui.gap * 1.1)

    color: ui.surface
    radius: ui.radius * 1.4
    border.width: 1
    border.color: ui.border

    ColumnLayout {
        id: column
        x: root.margin
        y: root.margin
        width: Math.max(0, root.width - root.margin * 2)
        height: Math.max(0, root.height - root.margin * 2)
        spacing: Math.round(ui.gap * 0.7)

        RowLayout {
            visible: root.title !== ""
            spacing: Math.round(ui.gap * 0.5)

            Icon {
                visible: root.titleIcon !== ""
                name: root.titleIcon
                color: ui.textMuted
                size: Math.round(ui.fontSmall * 1.3)
            }
            Text {
                text: root.title.toUpperCase()
                color: ui.textMuted
                font.pixelSize: ui.fontSmall
                font.weight: Font.DemiBold
                font.letterSpacing: ui.mm * 0.2
            }
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Math.round(ui.gap * 0.7)
        }
    }
}
