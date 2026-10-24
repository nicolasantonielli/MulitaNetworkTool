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
        console.log("tactil press", mouse.x.toFixed(0), mouse.y.toFixed(0), parent.objectName)
    }
    onReleased: {
        var dx = mouse.x - originX
        var dy = mouse.y - originY
        var accepted = dx * dx + dy * dy <= slop * slop
        console.log("tactil release", accepted ? "aceptado" : "descartado",
                    "dx", dx.toFixed(0), "dy", dy.toFixed(0), parent.objectName)
        if (accepted)
            area.tapped()
    }
}
