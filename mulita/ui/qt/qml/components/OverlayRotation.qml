import QtQuick 2.15

// Qt puede restablecer la geometria del overlay al redimensionar la ventana.
// Reaplicar despues del cambio evita que los popups pierdan el giro.
Item {
    id: root
    property Item overlay: null
    property Item surface: null

    function synchronize() {
        if (!overlay || !surface)
            return
        if (overlay.width !== surface.width) overlay.width = surface.width
        if (overlay.height !== surface.height) overlay.height = surface.height
        if (overlay.x !== surface.x) overlay.x = surface.x
        if (overlay.y !== surface.y) overlay.y = surface.y
        if (overlay.transformOrigin !== Item.Center) overlay.transformOrigin = Item.Center
        if (overlay.rotation !== surface.rotation) overlay.rotation = surface.rotation
    }

    function schedule() { Qt.callLater(root.synchronize) }
    onOverlayChanged: schedule()
    onSurfaceChanged: schedule()
    Component.onCompleted: schedule()

    Connections {
        target: root.overlay
        function onWidthChanged() { root.schedule() }
        function onHeightChanged() { root.schedule() }
        function onXChanged() { root.schedule() }
        function onYChanged() { root.schedule() }
        function onRotationChanged() { root.schedule() }
        function onTransformOriginChanged() { root.schedule() }
        function onVisibleChanged() { root.schedule() }
    }
    Connections {
        target: root.surface
        function onWidthChanged() { root.schedule() }
        function onHeightChanged() { root.schedule() }
        function onXChanged() { root.schedule() }
        function onYChanged() { root.schedule() }
        function onRotationChanged() { root.schedule() }
    }
}
