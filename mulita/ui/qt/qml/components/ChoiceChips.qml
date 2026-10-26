import QtQuick 2.15
import QtQuick.Layouts 1.15

// Seleccion unica tactil. El modelo acepta textos o objetos {label, value}.
// No guarda la seleccion: emite `activated` y quien lo usa actualiza `value`.
Flow {
    id: root

    readonly property bool allowsTextCopy: false

    property var model: []
    property string value: ""
    property bool clearable: false
    signal activated(string value)

    spacing: Math.round(ui.gap * 0.6)
    opacity: enabled ? 1 : 0.5

    Repeater {
        model: root.model

        delegate: Rectangle {
            id: chip

            readonly property string chipValue: typeof modelData === "string" ? modelData : modelData.value
            readonly property string chipLabel: typeof modelData === "string" ? modelData : modelData.label
            readonly property bool selected: root.value === chipValue
            readonly property bool linked: modelData.linked === true
            readonly property color linkFill: "#B9E8F8"
            readonly property color linkInk: "#083044"

            height: ui.touch
            width: Math.max(ui.touch * 1.5, label.implicitWidth + ui.padding * 2)
            radius: height / 2
            color: linked ? linkFill
                          : (selected ? ui.primary : (area.pressed ? ui.surfaceHigh : ui.surfaceAlt))
            border.width: selected ? 3 : 1
            border.color: selected ? ui.primary : (linked ? "#3AA8D8" : ui.border)

            Behavior on color { ColorAnimation { duration: 120 } }

            Text {
                id: label
                anchors.centerIn: parent
                text: chip.chipLabel
                color: chip.linked ? chip.linkInk : (chip.selected ? ui.onAccent : ui.text)
                font.pixelSize: ui.fontBody
                font.weight: chip.selected ? Font.DemiBold : Font.Normal
            }

            TouchArea {
                id: area
                enabled: root.enabled
                onTapped: root.activated(root.clearable && chip.selected ? "" : chip.chipValue)
            }
        }
    }
}
