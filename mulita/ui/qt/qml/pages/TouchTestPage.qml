import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

ColumnLayout {
    id: root
    objectName: "touchTestPage"
    spacing: ui.gap * 0.5
    property int taps: 0
    property int buttonTaps: 0
    property var zones: ({})
    signal goBack()

    function reset() {
        taps = 0
        buttonTaps = 0
        zones = ({})
        touchTest.clear()
    }

    onVisibleChanged: touchTest.setActive(visible)
    Component.onCompleted: touchTest.setActive(visible)
    Component.onDestruction: touchTest.setActive(false)

    Text {
        Layout.fillWidth: true
        text: i18n.pack.touchTestHint
        color: ui.textMuted
        font.pixelSize: ui.fontSmall
        wrapMode: Text.Wrap
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: ui.gap * 0.5
        IconButton {
            objectName: "touchTestBack"
            icon: "back"
            onClicked: root.goBack()
        }
        TouchButton {
            objectName: "touchTestMode"
            Layout.fillWidth: true
            text: touchTest.bypass ? i18n.pack.touchNative : i18n.pack.touchNormal
            kind: touchTest.bypass ? "warning" : "neutral"
            onClicked: touchTest.setBypass(!touchTest.bypass)
        }
        TouchButton {
            objectName: "touchTestReset"
            text: i18n.pack.clear
            kind: "neutral"
            onClicked: root.reset()
        }
        TouchButton {
            objectName: "touchTestButton"
            text: i18n.pack.touchButtonCount.replace("{count}", root.buttonTaps)
            kind: "success"
            onClicked: root.buttonTaps++
        }
    }

    Text {
        Layout.fillWidth: true
        text: i18n.pack.touchCounts
              .replace("{down}", touchTest.counts.touch_down || 0)
              .replace("{up}", touchTest.counts.touch_up || 0)
              .replace("{cancel}", touchTest.counts.touch_cancel || 0)
              + " · " + i18n.pack.touchMouseCounts
              .replace("{down}", touchTest.counts.mouse_down || 0)
              .replace("{up}", touchTest.counts.mouse_up || 0)
        color: ui.text
        font.pixelSize: ui.fontSmall
        wrapMode: Text.Wrap
    }

    Rectangle {
        id: surface
        objectName: "touchTestSurface"
        readonly property bool allowsTextCopy: false
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: ui.touch
        color: ui.surface
        border.color: ui.border
        clip: true

        Repeater {
            model: 9
            Rectangle {
                x: (index % 3) * surface.width / 3
                y: Math.floor(index / 3) * surface.height / 3
                width: surface.width / 3
                height: surface.height / 3
                color: root.zones[index] ? ui.surfaceHigh : "transparent"
                border.color: ui.border
                Text {
                    anchors.centerIn: parent
                    text: index + 1
                    color: root.zones[index] ? ui.success : ui.textMuted
                    font.pixelSize: ui.fontTitle
                }
            }
        }
        Canvas {
            id: trail
            anchors.fill: parent
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                var events = touchTest.events
                var previous = ({})
                for (var i = 0; i < events.length; ++i) {
                    var e = events[i]
                    var p = trail.mapFromGlobal(e.x, e.y)
                    var key = e.source + ":" + e.id
                    if (p.x < 0 || p.y < 0 || p.x > width || p.y > height) {
                        delete previous[key]
                        continue
                    }
                    ctx.strokeStyle = e.source === "touch" ? ui.success : ui.primary
                    ctx.lineWidth = 2
                    if (previous[key] && e.phase === "move") {
                        ctx.beginPath()
                        ctx.moveTo(previous[key].x, previous[key].y)
                        ctx.lineTo(p.x, p.y)
                        ctx.stroke()
                    }
                    ctx.beginPath()
                    ctx.arc(p.x, p.y, e.phase === "down" ? 6 : 3, 0, Math.PI * 2)
                    ctx.stroke()
                    if (e.phase === "up" || e.phase === "cancel")
                        delete previous[key]
                    else
                        previous[key] = p
                }
            }
        }
        MouseArea {
            anchors.fill: parent
            preventStealing: true
            onClicked: {
                root.taps++
                var picked = Math.min(2, Math.floor(mouse.y * 3 / height)) * 3
                           + Math.min(2, Math.floor(mouse.x * 3 / width))
                var next = root.zones
                next[picked] = true
                root.zones = Object.assign({}, next)
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Text {
            text: i18n.pack.touchAreaCount.replace("{count}", root.taps)
            color: ui.text
            font.pixelSize: ui.fontSmall
        }
        Text {
            Layout.fillWidth: true
            text: touchTest.latest.source
                  ? touchTest.latest.ms + " ms · " + touchTest.latest.source + " / "
                    + touchTest.latest.phase + " · X " + Math.round(touchTest.latest.x)
                    + "  Y " + Math.round(touchTest.latest.y)
                  : i18n.pack.touchWaiting
            color: ui.textMuted
            font.pixelSize: ui.fontSmall
            elide: Text.ElideRight
        }
    }
    Connections {
        target: touchTest
        function onChanged() { trail.requestPaint() }
    }
}
