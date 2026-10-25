import QtQuick 2.15

// Toque tolerante para el panel ft5x06: el dedo se mueve al apoyar y el driver
// a veces manda una coordenada imposible justo antes de soltar. Un toque corto
// cuenta siempre; uno largo cuenta si el dedo no se arrastro.
MouseArea {
    id: area

    signal tapped()

    readonly property real slop: ui.mm * 8
    readonly property int quickTapMs: 450
    property real originX: 0
    property real originY: 0
    property double pressedAt: 0
    property bool armed: false

    function finish(reason, dx, dy) {
        if (!armed)
            return
        armed = false
        var elapsed = Date.now() - pressedAt
        var still = dx * dx + dy * dy <= slop * slop
        var accepted = elapsed <= quickTapMs || still
        console.log("tactil", reason, accepted ? "aceptado" : "descartado",
                    "ms", elapsed, "dx", dx.toFixed(0), "dy", dy.toFixed(0))
        if (accepted)
            area.tapped()
    }

    anchors.fill: parent
    preventStealing: true

    onPressed: {
        originX = mouse.x
        originY = mouse.y
        pressedAt = Date.now()
        armed = true
        console.log("tactil press", mouse.x.toFixed(0), mouse.y.toFixed(0))
    }
    onReleased: finish("release", mouse.x - originX, mouse.y - originY)
    onCanceled: armed = false
}
