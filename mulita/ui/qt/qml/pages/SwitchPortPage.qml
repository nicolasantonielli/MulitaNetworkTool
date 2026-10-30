import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root
    readonly property var report: JSON.parse(switchPort.reportJson)
    readonly property var neighbors: report.neighbors || []
    readonly property var interfaces: network.interfaces.filter(function (item) {
        return item.value !== "lo" && item.value.indexOf("wl") !== 0
    })

    function shown(value) {
        return value === undefined || value === null || value === "" ? i18n.pack.switchUnknown : String(value)
    }
    function vlans(items) {
        return (items || []).map(function (item) {
            return String(item.id) + (item.name ? " · " + item.name : "")
        }).join(", ")
    }
    function fields(row) {
        return [
            [i18n.pack.switchName, row.name || row.chassis],
            [i18n.pack.switchPort, row.port],
            [i18n.pack.switchPvid, row.pvid],
            [i18n.pack.switchVoice, vlans(row.voice)],
            [i18n.pack.switchDescription, row.description],
            [i18n.pack.switchSystem, row.system],
            [i18n.pack.switchAddress, (row.addresses || []).join(", ")],
            [i18n.pack.switchNamedVlans, vlans(row.vlans)],
            [i18n.pack.switchSource, row.protocol + " · " + row.source],
            [i18n.pack.switchLastSeen, row.lastSeen]
        ]
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        RowLayout {
            Layout.fillWidth: true
            ComboBox {
                id: iface
                objectName: "switchInterface"
                Layout.fillWidth: true
                Layout.preferredHeight: ui.touch
                model: root.interfaces
                textRole: "label"
                enabled: !switchPort.running
            }
            ComboBox {
                id: duration
                Layout.preferredWidth: ui.touch * 1.5
                Layout.preferredHeight: ui.touch
                model: [15, 30, 60, 120, 180]
                currentIndex: 2
                displayText: currentText + " s"
                enabled: !switchPort.running
            }
            TouchButton {
                text: switchPort.running ? i18n.pack.stop : i18n.pack.start
                icon: switchPort.running ? "stop" : "search"
                kind: switchPort.running ? "danger" : "success"
                enabled: switchPort.running || iface.currentIndex >= 0
                onClicked: {
                    if (switchPort.running) switchPort.stop()
                    else switchPort.start(root.interfaces[iface.currentIndex].value, Number(duration.currentText))
                }
            }
            TouchButton {
                objectName: "switchClear"
                text: i18n.pack.clear
                kind: "neutral"
                enabled: !switchPort.running && (!!root.report.interface || switchPort.status !== "")
                onClicked: switchPort.clear()
            }
            TouchButton {
                text: i18n.pack.save
                icon: "file"
                enabled: !switchPort.running && !!root.report.interface
                onClicked: switchPort.save()
            }
        }

        ScrollPage {
            id: results
            Text {
                Layout.fillWidth: true
                visible: switchPort.simulated
                text: i18n.pack.switchDemo
                color: ui.warning
                font.pixelSize: ui.fontBody
                wrapMode: Text.Wrap
            }
            Text {
                Layout.fillWidth: true
                text: switchPort.status || i18n.pack.switchHint
                textFormat: Text.PlainText
                color: ui.text
                font.pixelSize: ui.fontBody
                wrapMode: Text.Wrap
            }
            Repeater {
                model: root.neighbors
                Rectangle {
                    id: neighbor
                    readonly property var row: modelData
                    Layout.fillWidth: true
                    implicitHeight: details.implicitHeight + ui.padding * 2
                    radius: ui.radius
                    color: ui.surface
                    border.color: ui.border
                    ColumnLayout {
                        id: details
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: ui.padding
                        spacing: ui.gap
                        Repeater {
                            model: root.fields(neighbor.row)
                            Text {
                                Layout.fillWidth: true
                                text: modelData[0] + ": " + root.shown(modelData[1])
                                textFormat: Text.PlainText
                                color: index < 3 ? ui.primary : ui.text
                                font.pixelSize: index < 3 ? ui.fontBody : ui.fontSmall
                                font.bold: index < 3
                                wrapMode: Text.Wrap
                            }
                        }
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                visible: !!root.report.interface
                text: i18n.pack.switchStats.replace("{elapsed}", root.report.elapsed || 0).replace("{frames}", root.report.frames || 0)
                color: ui.textMuted
                font.pixelSize: ui.fontSmall
            }
            Text {
                Layout.fillWidth: true
                visible: !!root.report.link
                readonly property var link: root.report.link || ({})
                text: i18n.pack.switchLink + ": "
                    + (link.carrier === "1" ? i18n.pack.switchUp : link.carrier === "0" ? i18n.pack.switchDown : i18n.pack.switchUnknown)
                    + (link.speed ? " · " + link.speed + " Mb/s" : "")
                    + (link.duplex ? " · " + link.duplex : "")
                    + "\nMAC: " + root.shown(link.mac)
                    + " · " + i18n.pack.switchErrors + ": " + root.shown(link.rxErrors) + " / " + root.shown(link.txErrors)
                textFormat: Text.PlainText
                color: ui.text
                font.pixelSize: ui.fontBody
                wrapMode: Text.Wrap
            }
            Text {
                Layout.fillWidth: true
                text: i18n.pack.switchObserved + ": " + ((root.report.vlans || []).join(", ") || i18n.pack.switchNoTags)
                textFormat: Text.PlainText
                color: ui.primary
                font.pixelSize: ui.fontBody
                wrapMode: Text.Wrap
            }
            Text {
                Layout.fillWidth: true
                visible: root.neighbors.length === 0
                text: i18n.pack.switchMissing
                color: ui.textMuted
                font.pixelSize: ui.fontBody
                wrapMode: Text.Wrap
            }
            Text {
                Layout.fillWidth: true
                text: i18n.pack.switchLimit
                color: ui.textMuted
                font.pixelSize: ui.fontSmall
                wrapMode: Text.Wrap
            }
        }
    }
}
