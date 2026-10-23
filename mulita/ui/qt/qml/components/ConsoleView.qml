import QtQuick 2.15
import QtQuick.Controls 2.15

// Salida de comandos con auto-desplazamiento. Se arrastra con el dedo en ambos ejes.
Rectangle {
    id: root

    property QtObject source: null
    property string placeholder: ""

    color: ui.consoleBackground
    radius: ui.radius
    border.width: 1
    border.color: ui.border
    clip: true

    function scrollToEnd() {
        flick.contentY = Math.max(0, flick.contentHeight - flick.height)
    }

    Flickable {
        id: flick
        anchors.fill: parent
        anchors.margins: 1
        boundsBehavior: Flickable.StopAtBounds

        TextArea.flickable: TextArea {
            id: area
            readOnly: true
            activeFocusOnPress: false
            wrapMode: TextEdit.NoWrap
            color: ui.consoleText
            font.family: ui.monoFamily
            font.pixelSize: ui.fontSmall
            placeholderText: root.placeholder
            placeholderTextColor: ui.textMuted
            padding: ui.gap
            background: null
        }

        ScrollBar.vertical: ScrollBar { }
        ScrollBar.horizontal: ScrollBar { }
    }

    Connections {
        target: root.source
        ignoreUnknownSignals: true

        function onAppended(text) {
            area.insert(area.length, text)
            Qt.callLater(root.scrollToEnd)
        }

        function onCleared() {
            area.clear()
        }
    }
}
