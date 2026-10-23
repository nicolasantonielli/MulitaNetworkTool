import QtQuick 2.15
import QtQuick.Layouts 1.15

Image {
    id: root

    property string name: ""
    property color color: ui.text
    property int size: ui.icon

    width: size
    height: size
    Layout.preferredWidth: size
    Layout.preferredHeight: size
    sourceSize.width: size
    sourceSize.height: size
    fillMode: Image.PreserveAspectFit
    smooth: true
    source: name !== "" ? "image://icon/" + name + "/" + String(color).replace("#", "") : ""
}
