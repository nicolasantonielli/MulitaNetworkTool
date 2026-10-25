import QtQuick 2.15
import QtQuick.Layouts 1.15

// El alto lo fija quien contiene la pagina. El contenido, si no entra, se mueve
// tocando la barra: el panel no entrega un arrastre continuo, solo toques.
Item {
    id: root

    default property alias content: column.data
    property alias spacing: column.spacing

    Layout.fillWidth: true
    Layout.fillHeight: true
    clip: true

    readonly property bool overflowing: flick.contentHeight > flick.height + 1

    Flickable {
        id: flick

        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: bar.left
        clip: true
        // El dedo tiene que llegar al campo. El desplazamiento va por la barra.
        interactive: false
        flickableDirection: Flickable.VerticalFlick
        boundsBehavior: Flickable.StopAtBounds
        contentWidth: width
        contentHeight: column.implicitHeight

        ColumnLayout {
            id: column
            width: flick.width
            height: implicitHeight
            spacing: ui.gap
        }
    }

    Rectangle {
        id: bar

        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: root.overflowing ? Math.round(ui.mm * 4) : 0
        visible: width > 0
        radius: ui.radius
        color: ui.surfaceHigh
        border.width: 1
        border.color: ui.border

        readonly property real maxY: Math.max(0, flick.contentHeight - flick.height)
        readonly property real handleHeight: Math.max(ui.touch, height * flick.height / Math.max(flick.contentHeight, 1))
        readonly property real handleY: maxY <= 0 ? 0
                : (height - handleHeight) * (flick.contentY / maxY)

        Rectangle {
            x: 2
            y: bar.handleY
            width: Math.max(0, bar.width - 4)
            height: bar.handleHeight
            radius: width / 2
            color: ui.primary
        }

        MouseArea {
            anchors.fill: parent
            enabled: root.overflowing
            onPressed: {
                var fraction = Math.max(0, Math.min(1, mouse.y / Math.max(1, height)))
                flick.contentY = fraction * bar.maxY
            }
        }
    }
}
