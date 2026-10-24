import QtQuick 2.15

// El dedo se mueve al apoyar. Un clic estricto no llega a dispararse y el
// tactil parece poco sensible. Se acepta el toque si no hubo un arrastre claro.
MouseArea {
    id: area

    signal tapped()

    readonly property real slop: ui.mm * 8
    property real originX: 0
    property real originY: 0

    anchors.fill: parent
    preventStealing: true

    onPressed: {
        originX = mouse.x
        originY = mouse.y
    }
    onReleased: {
        var dx = mouse.x - originX
        var dy = mouse.y - originY
        if (dx * dx + dy * dy <= slop * slop)
            area.tapped()
    }
}
