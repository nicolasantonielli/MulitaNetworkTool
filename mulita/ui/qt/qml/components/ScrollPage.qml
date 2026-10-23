import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// Contenido que puede no entrar en pantallas chicas: se desplaza con el dedo.
Flickable {
    id: root

    default property alias content: column.data
    property alias spacing: column.spacing

    clip: true
    contentWidth: width
    contentHeight: column.height
    boundsBehavior: Flickable.StopAtBounds

    ColumnLayout {
        id: column
        // StackLayout deja en ancho 0 las secciones que nunca se mostraron.
        width: Math.max(root.width, ui.touch * 6)
        spacing: ui.gap
    }

    ScrollBar.vertical: ScrollBar { }
}
