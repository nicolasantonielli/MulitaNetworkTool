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
                id: discoverPage
                spacing: ui.gap

                property string selectedInterface: ""

                readonly property var discoverInterfaces: {
                    var rows = network.interfaces
                    var found = []
                    for (var i = 0; i < rows.length; ++i) {
                        var row = rows[i]
                        var name = typeof row === "string" ? row : row.value
                        if (name !== "lo")
                            found.push(typeof row === "string"
                                       ? { label: name, value: name, linked: false }
                                       : row)
                    }
                    return found
                }

                function keepDiscoverSelection() {
                    var rows = discoverInterfaces
                    for (var i = 0; i < rows.length; ++i) {
                        if (rows[i].value === selectedInterface && selectedInterface !== "")
                            return
                    }
                    var chosen = ""
                    for (var j = 0; j < rows.length; ++j) {
                        if (rows[j].value === "eth0")
                            chosen = "eth0"
                    }
                    if (!chosen && rows.length)
                        chosen = rows[0].value
                    selectedInterface = chosen
                }

                Connections {
                    target: network
                    function onInterfacesChanged() { discoverPage.keepDiscoverSelection() }
                }

                Component.onCompleted: keepDiscoverSelection()

                readonly property var hosts: {
                    try { return JSON.parse(discovery.hostsJson) }
                    catch (e) { return [] }
                }
                readonly property var columns: [
                    { title: i18n.pack.discoverIp, key: "ip", share: 24 },
                    { title: i18n.pack.discoverMac, key: "mac", share: 28 },
                    { title: i18n.pack.discoverCount, key: "count", share: 16 },
                    { title: i18n.pack.discoverVendor, key: "vendor", share: 32 }
                ]

                function columnWidth(share) {
                    var bar = discoverTable.overflowing ? Math.round(ui.mm * 4) : 0
                    return Math.max(1, (discoverTable.width - bar) * share / 100)
                }

                ChoiceChips {
                    Layout.fillWidth: true
                    model: discoverPage.discoverInterfaces
                    value: discoverPage.selectedInterface
                    enabled: !discovery.running
                    onActivated: discoverPage.selectedInterface = value
                }

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
                        enabled: discovery.running || discoverPage.selectedInterface !== ""
                        onClicked: discovery.running
                                  ? discovery.stop()
                                  : discovery.start(discoverPage.selectedInterface)
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
                        visible: discoverPage.hosts.length === 0
                        text: discovery.running ? i18n.pack.listening : i18n.pack.discoverEmpty
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Math.round(ui.gap * 0.6)
                        visible: discoverPage.hosts.length > 0
                        spacing: Math.round(ui.gap * 0.3)

                        ScrollPage {
                            id: discoverTable
                            spacing: 1

                            Row {
                                Layout.fillWidth: true
                                Repeater {
                                    model: discoverPage.columns
                                    delegate: Text {
                                        width: discoverPage.columnWidth(modelData.share)
                                        text: modelData.title
                                        color: ui.textMuted
                                        font.pixelSize: ui.fontSmall
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                        horizontalAlignment: modelData.key === "vendor"
                                                              ? Text.AlignLeft : Text.AlignHCenter
                                    }
                                }
                            }

                            Repeater {
                                model: discoverPage.hosts
                                delegate: Rectangle {
                                    id: hostRow
                                    readonly property var host: modelData
                                    Layout.fillWidth: true
                                    implicitHeight: Math.round(ui.fontSmall * 2.15)
                                    color: index % 2 === 0 ? "transparent" : ui.surfaceAlt
                                    Row {
                                        anchors.fill: parent
                                        Repeater {
                                            model: discoverPage.columns
                                            delegate: Text {
                                                width: discoverPage.columnWidth(modelData.share)
                                                height: hostRow.height
                                                text: hostRow.host[modelData.key] === undefined
                                                      ? "" : String(hostRow.host[modelData.key])
                                                color: ui.text
                                                font.pixelSize: ui.fontSmall
                                                font.family: ui.monoFamily
                                                verticalAlignment: Text.AlignVCenter
                                                elide: Text.ElideRight
                                                horizontalAlignment: modelData.key === "vendor"
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
                        id: discoverFile
                        Layout.fillWidth: true
                        text: "descubrimiento"
                        placeholderText: i18n.pack.fileName
                        enabled: !discovery.running
                    }
                    Text {
                        text: ".csv"
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                    }
                    TouchButton {
                        text: i18n.pack.clear
                        kind: "neutral"
                        enabled: !discovery.running && discoverPage.hosts.length > 0
                        onClicked: discovery.clear()
                    }
                    TouchButton {
                        text: i18n.pack.save
                        icon: "file"
                        kind: "success"
                        enabled: !discovery.running && discoverPage.hosts.length > 0
                        onClicked: discovery.save(discoverFile.text)
                    }
                }
            }
        }
    }
}
