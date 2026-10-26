import QtQuick 2.15
import QtQuick.Layouts 1.15

Card {
    id: root

    property string label: ""
    property string value: ""
    property string unit: ""
    property string icon: ""
    property color tone: ui.primary

    RowLayout {
        spacing: ui.gap

        Rectangle {
            Layout.preferredWidth: ui.touch
            Layout.preferredHeight: ui.touch
            radius: ui.radius
            color: Qt.rgba(root.tone.r, root.tone.g, root.tone.b, 0.15)

            Icon {
                anchors.centerIn: parent
                name: root.icon
                color: root.tone
            }
        }
        Text {
            Layout.fillWidth: true
            text: root.label.toUpperCase()
            color: ui.textMuted
            font.pixelSize: ui.fontSmall
            font.weight: Font.DemiBold
            font.letterSpacing: ui.mm * 0.2
            elide: Text.ElideRight
        }
    }

    Item { Layout.fillHeight: true }

    RowLayout {
        spacing: Math.round(ui.gap * 0.5)

        TextEdit {
            readOnly: true
            selectByMouse: true
            persistentSelection: true
            text: root.value
            color: ui.text
            font.pixelSize: ui.fontDisplay
            font.weight: Font.Bold
            wrapMode: TextEdit.NoWrap
            selectionColor: ui.primary
            selectedTextColor: ui.onAccent
            height: contentHeight
            Layout.fillWidth: true
            Layout.maximumWidth: Math.max(40, root.width - ui.padding * 2)
        }
        Text {
            visible: root.unit !== ""
            text: root.unit
            color: ui.textMuted
            font.pixelSize: ui.fontTitle
            Layout.alignment: Qt.AlignBaseline
        }
    }
}
