import QtQuick 2.15

// Qt transforma tambien las coordenadas del mouse y del tactil de los hijos.
Item {
    property int angle: 0
    readonly property bool portrait: angle === 90 || angle === 270
    width: parent ? (portrait ? parent.height : parent.width) : 0
    height: parent ? (portrait ? parent.width : parent.height) : 0
    x: parent ? (parent.width - width) / 2 : 0
    y: parent ? (parent.height - height) / 2 : 0
    rotation: angle
    transformOrigin: Item.Center
}
