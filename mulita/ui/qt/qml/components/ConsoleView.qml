import QtQuick 2.15
import QtQuick.Controls 2.15

// Salida de comandos con auto-desplazamiento. Se arrastra con el dedo en ambos ejes.
Rectangle {
    id: root

    property QtObject source: null
    property string placeholder: ""
    readonly property bool verticalOverflow: flick.contentHeight > flick.height + 1
    readonly property bool horizontalOverflow: flick.contentWidth > flick.width + 1

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
        anchors.rightMargin: 1 + (root.verticalOverflow ? verticalBar.width + ui.gap : 0)
        anchors.bottomMargin: 1 + (root.horizontalOverflow ? horizontalBar.height + ui.gap : 0)
        boundsBehavior: Flickable.StopAtBounds

        TextArea.flickable: TextArea {
            id: area
            readOnly: true
            selectByMouse: true
            persistentSelection: true
            activeFocusOnPress: false
            onSelectedTextChanged: if (selectedText.length > 0) copy()
            wrapMode: TextEdit.NoWrap
            color: ui.consoleText
            font.family: ui.monoFamily
            font.pixelSize: ui.fontSmall
            placeholderText: root.placeholder
            placeholderTextColor: ui.textMuted
            padding: ui.gap
            background: null
        }

        ScrollBar.vertical: ScrollBar {
            id: verticalBar
            parent: root
            x: root.width - width - 1
            y: 1
            height: flick.height
        }
        ScrollBar.horizontal: ScrollBar {
            id: horizontalBar
            parent: root
            x: 1
            y: root.height - height - 1
            width: flick.width
        }
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
