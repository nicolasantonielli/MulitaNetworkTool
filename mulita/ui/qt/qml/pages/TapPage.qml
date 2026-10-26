import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    function fileName() {
        return tapFile.text.replace(/\.pcap$/i, "") + ".pcap"
    }

    // Misma lista que la captura: sin lo, y celeste si hay cable.
    readonly property var tapInterfaces: {
        var rows = network.interfaces
        var found = []
        for (var i = 0; i < rows.length; ++i) {
            var row = rows[i]
            var name = typeof row === "string" ? row : row.value
            if (name !== "lo")
                found.push(typeof row === "string" ? { label: name, value: name, linked: false } : row)
        }
        return found
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        PageTabs {
            id: tabs
            Layout.fillWidth: true
            tabs: [i18n.pack.tapConfig, i18n.pack.tapScreen]
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: ui.gap

                    Repeater {
                        id: groups
                        model: [
                            { id: "in", icon: "download" },
                            { id: "mirror", icon: "tap" },
                            { id: "out", icon: "upload" }
                        ]

                        Card {
                            id: group

                            property string value: ""

                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.preferredWidth: 1
                            title: modelData.id === "in" ? i18n.pack.tapIn
                                   : modelData.id === "out" ? i18n.pack.tapOut : "Mirror"
                            titleIcon: modelData.icon

                            ChoiceChips {
                                Layout.fillWidth: true
                                clearable: modelData.id === "mirror"
                                model: root.tapInterfaces
                                value: group.value
                                enabled: !tap.running
                                onActivated: group.value = value
                            }
                            Connections {
                                target: network
                                function onInterfacesChanged() {
                                    var rows = root.tapInterfaces
                                    for (var i = 0; i < rows.length; ++i) {
                                        if (rows[i].value === group.value)
                                            return
                                    }
                                    group.value = ""
                                }
                            }
                            Item { Layout.fillHeight: true }
                        }
                    }
                }

                Card {
                    Layout.fillWidth: true
                    title: i18n.pack.captureFile
                    titleIcon: "file"

                    RowLayout {
                        spacing: ui.gap

                        Field {
                            id: tapFile
                            Layout.fillWidth: true
                            text: tap.defaultFilename
                            enabled: !tap.running
                            placeholderText: i18n.pack.fileName
                        }
                        Text {
                            text: ".pcap"
                            color: ui.textMuted
                            font.pixelSize: ui.fontBody
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: tap.running && tap.activeFile !== "" ? tap.activeFile : root.fileName()
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        font.family: ui.monoFamily
                        wrapMode: Text.WrapAnywhere
                    }
                }

                RowLayout {
                    spacing: ui.gap

                    TouchButton {
                        text: network.refreshing ? i18n.pack.reading : i18n.pack.updateIfaces
                        icon: "refresh"
                        kind: network.refreshing ? "success" : "neutral"
                        enabled: !tap.running && !network.refreshing
                        onClicked: network.refresh()
                    }
                    Item { Layout.fillWidth: true }
                    StatusPill {
                        text: tap.running ? i18n.pack.active : i18n.pack.inactive
                        tone: tap.running ? ui.success : ui.textMuted
                        pulsing: tap.running
                    }
                    TouchButton {
                        Layout.preferredWidth: ui.mm * 34
                        text: tap.running ? i18n.pack.stop : i18n.pack.start
                        icon: tap.running ? "stop" : "play"
                        kind: tap.running ? "danger" : "success"
                        onClicked: tap.running ? tap.stop()
                                               : tap.start(groups.itemAt(0).value, groups.itemAt(1).value,
                                                           groups.itemAt(2).value, tapFile.text)
                    }
                }
            }

            ColumnLayout {
                id: tapOut
                spacing: ui.gap

                readonly property var lines: {
                    try { return JSON.parse(tap.linesJson) }
                    catch (e) { return [] }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: ui.radius
                    color: ui.surface
                    border.width: 1
                    border.color: ui.border

                    Text {
                        anchors.centerIn: parent
                        width: parent.width - ui.padding * 2
                        visible: tapOut.lines.length === 0
                        text: i18n.pack.tapQuiet
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Math.round(ui.gap * 0.6)
                        visible: tapOut.lines.length > 0
                        spacing: Math.round(ui.gap * 0.3)

                        ScrollPage {
                            id: tapTable
                            spacing: 1

                            Repeater {
                                model: tapOut.lines
                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: Math.round(ui.fontSmall * 2.15)
                                    color: index % 2 === 0 ? "transparent" : ui.surfaceAlt
                                    CopyableCell {
                                        anchors.fill: parent
                                        text: modelData === undefined ? "" : String(modelData)
                                        color: ui.text
                                        font.pixelSize: ui.fontSmall
                                        font.family: ui.monoFamily
                                        verticalAlignment: Text.AlignVCenter
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
