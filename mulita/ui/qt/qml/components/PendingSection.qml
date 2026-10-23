import QtQuick 2.15
import QtQuick.Layouts 1.15

ScrollPage {
    id: root

    property string title: ""
    property string icon: ""
    signal goHome()

    Card {
        Layout.fillWidth: true
        title: root.title
        titleIcon: root.icon

        Text {
            Layout.fillWidth: true
            text: "La configuración de esta interfaz estará disponible en una próxima versión."
            color: ui.textMuted
            font.pixelSize: ui.fontBody
            wrapMode: Text.Wrap
        }
        TouchButton {
            text: "Volver al inicio"
            icon: "back"
            kind: "neutral"
            onClicked: root.goHome()
        }
    }
}
