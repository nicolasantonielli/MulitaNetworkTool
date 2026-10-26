import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        PageTabs {
            id: tabs
            Layout.fillWidth: true
            tabs: [i18n.pack.scanPorts, i18n.pack.scanDiscover]
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            // Escaneo de puertos (nmap)
            ColumnLayout {
                id: scanPage
                spacing: ui.gap

                readonly property var ports: {
                    try { return JSON.parse(portScan.portsJson) }
                    catch (e) { return [] }
                }
                readonly property var columns: [
                    { title: i18n.pack.scanHost, key: "host", share: 28 },
                    { title: i18n.pack.scanPort, key: "port", share: 12 },
                    { title: i18n.pack.scanProto, key: "protocol", share: 14 },
                    { title: i18n.pack.scanState, key: "state", share: 16 },
                    { title: i18n.pack.scanService, key: "service", share: 30 }
                ]

                function columnWidth(share) {
                    var bar = scanTable.overflowing ? Math.round(ui.mm * 4) : 0
                    return Math.max(1, (scanTable.width - bar) * share / 100)
                }

                function stateColor(state) {
                    if (state === "open")
                        return ui.success
                    if (state.indexOf("filtered") >= 0)
                        return ui.warning
                    if (state === "closed")
                        return ui.textMuted
                    return ui.text
                }

                RowLayout {
                    spacing: ui.gap

                    Field {
                        id: scanTarget
                        Layout.fillWidth: true
                        placeholderText: i18n.pack.scanArgs
                        onAccepted: if (!portScan.busy) portScan.scan(text)
                    }
                    TouchButton {
                        text: portScan.busy ? i18n.pack.scanning : i18n.pack.scan
                        icon: "scan"
                        enabled: !portScan.busy
                        onClicked: portScan.scan(scanTarget.text)
                    }
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
                        visible: scanPage.ports.length === 0
                        text: portScan.busy ? i18n.pack.scanning : i18n.pack.scanEmpty
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Math.round(ui.gap * 0.6)
                        visible: scanPage.ports.length > 0
                        spacing: Math.round(ui.gap * 0.3)

                        ScrollPage {
                            id: scanTable
                            spacing: 1

                            Row {
                                Layout.fillWidth: true
                                Repeater {
                                    model: scanPage.columns
                                    delegate: Text {
                                        width: scanPage.columnWidth(modelData.share)
                                        text: modelData.title
                                        color: ui.textMuted
                                        font.pixelSize: ui.fontSmall
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                        horizontalAlignment: modelData.key === "host" || modelData.key === "service"
                                                              ? Text.AlignLeft : Text.AlignHCenter
                                    }
                                }
                            }

                            Repeater {
                                model: scanPage.ports
                                delegate: Rectangle {
                                    id: portRow
                                    readonly property var finding: modelData
                                    Layout.fillWidth: true
                                    implicitHeight: Math.round(ui.fontSmall * 2.15)
                                    color: index % 2 === 0 ? "transparent" : ui.surfaceAlt
                                    Row {
                                        anchors.fill: parent
                                        Repeater {
                                            model: scanPage.columns
                                            delegate: Text {
                                                width: scanPage.columnWidth(modelData.share)
                                                height: portRow.height
                                                text: portRow.finding[modelData.key] === undefined
                                                      ? "" : String(portRow.finding[modelData.key])
                                                color: modelData.key === "state"
                                                       ? scanPage.stateColor(portRow.finding.state)
                                                       : ui.text
                                                font.pixelSize: ui.fontSmall
                                                font.family: ui.monoFamily
                                                verticalAlignment: Text.AlignVCenter
                                                elide: Text.ElideRight
                                                horizontalAlignment: modelData.key === "host" || modelData.key === "service"
                                                                      ? Text.AlignLeft : Text.AlignHCenter
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    spacing: ui.gap

                    Field {
                        id: scanFile
                        Layout.fillWidth: true
                        text: "escaneo"
                        placeholderText: i18n.pack.fileName
                        enabled: !portScan.busy
                    }
                    Text {
                        text: ".csv"
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                    }
                    TouchButton {
                        text: i18n.pack.clear
                        kind: "neutral"
                        enabled: !portScan.busy && scanPage.ports.length > 0
                        onClicked: portScan.clear()
                    }
                    TouchButton {
                        text: i18n.pack.save
                        icon: "file"
                        kind: "success"
                        enabled: !portScan.busy && scanPage.ports.length > 0
                        onClicked: portScan.save(scanFile.text)
                    }
                }
            }

            // Descubrimiento IP (netdiscover)
            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    spacing: ui.gap

                    Text {
                        Layout.fillWidth: true
                        text: i18n.pack.discoverHint
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        elide: Text.ElideRight
                    }
                    StatusPill {
                        text: discovery.running ? i18n.pack.listening : i18n.pack.discoverStopped
                        tone: discovery.running ? ui.success : ui.textMuted
                        pulsing: discovery.running
                    }
                    TouchButton {
                        Layout.preferredWidth: ui.mm * 34
                        text: discovery.running ? i18n.pack.stop : i18n.pack.discover
                        icon: discovery.running ? "stop" : "play"
                        kind: discovery.running ? "danger" : "success"
                        onClicked: discovery.running ? discovery.stop() : discovery.start()
                    }
                }

                ConsoleView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: discovery.console
                    placeholder: i18n.pack.discoverEmpty
                }
            }
        }
    }
}
