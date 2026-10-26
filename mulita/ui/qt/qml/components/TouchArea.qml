import QtQuick 2.15

// Distingue una pulsacion de un arrastre y permite que la pagina tome el gesto
// para desplazarse, incluso cuando el dedo empieza sobre un boton.
MouseArea {
    id: area

    signal tapped()

    readonly property real slop: Math.max(6, ui.mm * 2)
    property real originX: 0
    property real originY: 0
    property bool armed: false

    function finish(dx, dy) {
        if (!armed)
            return
        armed = false
        var still = dx * dx + dy * dy <= slop * slop
        if (still)
            area.tapped()
    }

    anchors.fill: parent
    preventStealing: false

    onPressed: {
        originX = mouse.x
        originY = mouse.y
        armed = true
    }
    onPositionChanged: {
        var dx = mouse.x - originX
        var dy = mouse.y - originY
        if (pressed && dx * dx + dy * dy > slop * slop)
            armed = false
    }
    onReleased: finish(mouse.x - originX, mouse.y - originY)
    onCanceled: armed = false
}
