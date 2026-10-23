import QtQuick 2.15
import QtQuick.Layouts 1.15

// Valor numerico con botones grandes; mantener presionado acelera el cambio.
// Emite `edited` con el valor nuevo y quien lo usa actualiza `value`.
RowLayout {
    id: root

    property string label: ""
    property string suffix: ""
    property real value: 0
    property real from: 0
    property real to: 100
    property real step: 1
    property int decimals: 0
    signal edited(real newValue)

    spacing: ui.gap

    function change(direction) {
        var next = Math.round((value + direction * step) / step) * step
        edited(Math.min(to, Math.max(from, Number(next.toFixed(decimals)))))
    }

    Text {
        Layout.fillWidth: true
        text: root.label
        color: ui.text
        font.pixelSize: ui.fontBody
        elide: Text.ElideRight
    }
    TouchButton {
        icon: "minus"
        kind: "neutral"
        autoRepeat: true
        enabled: root.value > root.from
        onClicked: root.change(-1)
    }
    Text {
        Layout.preferredWidth: ui.mm * 22
        horizontalAlignment: Text.AlignHCenter
        text: root.value.toFixed(root.decimals) + root.suffix
        color: ui.text
        font.pixelSize: ui.fontTitle
        font.weight: Font.DemiBold
        font.family: ui.monoFamily
    }
    TouchButton {
        icon: "plus"
        kind: "neutral"
        autoRepeat: true
        enabled: root.value < root.to
        onClicked: root.change(1)
    }
}
