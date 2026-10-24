import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ColumnLayout {
    id: root

    property string label: ""
    property string valueText: ""
    property real from: 0
    property real to: 1
    property real stepSize: 0
    property real initial: 0
    readonly property real value: slider.value

    spacing: 0

    RowLayout {
        Layout.fillWidth: true

        Text {
            text: root.label
            color: ui.textMuted
            font.pixelSize: ui.fontSmall
        }
        Item { Layout.fillWidth: true }
        Text {
            text: root.valueText
            color: ui.text
            font.pixelSize: ui.fontBody
            font.weight: Font.DemiBold
        }
    }

    Slider {
        id: slider
        Layout.fillWidth: true
        implicitHeight: ui.touch
        from: root.from
        to: root.to
        stepSize: root.stepSize
        value: root.initial
        snapMode: Slider.SnapAlways

        background: Rectangle {
            x: slider.leftPadding
            y: slider.topPadding + slider.availableHeight / 2 - height / 2
            width: slider.availableWidth
            height: Math.max(4, ui.mm * 1.2)
            radius: height / 2
            color: ui.surfaceHigh

            Rectangle {
                width: slider.visualPosition * parent.width
                height: parent.height
                radius: height / 2
                color: ui.primary
            }
        }

        handle: Rectangle {
            x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
            y: slider.topPadding + slider.availableHeight / 2 - height / 2
            width: Math.round(ui.touch * 0.9)
            height: width
            radius: width / 2
            color: slider.pressed ? Qt.lighter(ui.primary, 1.2) : ui.primary
            border.width: Math.max(2, ui.mm * 0.6)
            border.color: ui.surface
        }
    }
}
