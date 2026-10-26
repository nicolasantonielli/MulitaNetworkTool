import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    ConfirmDialog { id: dialog }

    Component.onCompleted: climate.refresh()

    RowLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        SideNav {
            id: nav
            Layout.preferredWidth: Math.round(root.width * 0.27)
            Layout.fillHeight: true
            onCurrentIndexChanged: {
                if (currentIndex === 4 && !wifi.busy)
                    wifi.loadLink()
                if (currentIndex === 6 && !files.busy)
                    files.refresh()
            }
            items: [
                { label: i18n.pack.toolWol, icon: "wake" },
                { label: i18n.pack.toolClimate, icon: "thermometer" },
                { label: i18n.pack.toolSpeed, icon: "gauge" },
                { label: i18n.pack.toolPublicIp, icon: "globe" },
                { label: i18n.pack.toolWifi, icon: "wifi" },
                { label: i18n.pack.toolMac, icon: "info" },
                { label: i18n.pack.toolFiles, icon: "file" }
            ]
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: nav.currentIndex

            // Wake on LAN
            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    spacing: ui.gap

                    Field {
                        id: mac
                        Layout.fillWidth: true
                        placeholderText: i18n.pack.macDest
                        font.family: ui.monoFamily
                        onAccepted: if (!wakeOnLan.busy) wakeOnLan.wake(text)

                        property bool formatting: false
                        property string lastMac: ""

                        function isHex(ch) {
                            return (ch >= "0" && ch <= "9") || (ch >= "A" && ch <= "F")
                        }

                        function groupedMac(raw) {
                            var hex = raw.toUpperCase().replace(/[^0-9A-F]/g, "").substring(0, 12)
                            var out = ""
                            for (var i = 0; i < hex.length; ++i) {
                                if (i > 0 && i % 2 === 0)
                                    out += ":"
                                out += hex.charAt(i)
                            }
                            return out
                        }

                        onTextChanged: {
                            if (formatting)
                                return
                            var source = text
                            var digits = 0
                            var end = Math.min(cursorPosition, text.length)
                            var removedColon = lastMac.length === text.length + 1
                                    && cursorPosition < lastMac.length
                                    && lastMac.charAt(cursorPosition) === ":"
                            if (removedColon) {
                                var before = 0
                                for (var j = 0; j < cursorPosition; ++j) {
                                    if (isHex(lastMac.charAt(j).toUpperCase()))
                                        before++
                                }
                                var oldHex = lastMac.toUpperCase().replace(/[^0-9A-F]/g, "")
                                if (before > 0)
                                    source = oldHex.substring(0, before - 1) + oldHex.substring(before)
                                digits = Math.max(0, before - 1)
                            } else {
                                for (var i = 0; i < end; ++i) {
                                    if (isHex(text.charAt(i).toUpperCase()))
                                        digits++
                                }
                            }
                            var next = groupedMac(source)
                            if (next === text) {
                                lastMac = text
                                return
                            }
                            var colons = digits > 0 ? Math.floor((digits - 1) / 2) : 0
                            formatting = true
                            text = next
                            cursorPosition = Math.min(next.length, digits + colons)
                            lastMac = next
                            formatting = false
                        }
                    }
                    TouchButton {
                        text: i18n.pack.wake
                        icon: "power"
                        enabled: !wakeOnLan.busy
                        onClicked: wakeOnLan.wake(mac.text)
                    }
                }
                Item {
                    id: wolStage
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    property bool celebrate: false
                    readonly property bool waving: wakeOnLan.phase === "sending" || celebrate
                    property real wave: 0

                    NumberAnimation on wave {
                        running: wolStage.waving
                        from: 0
                        to: 1
                        duration: 1800
                        loops: Animation.Infinite
                    }

                    Timer {
                        id: wolSettle
                        interval: 2100
                        onTriggered: wolStage.celebrate = false
                    }

                    Connections {
                        target: wakeOnLan
                        function onChanged() {
                            if (wakeOnLan.phase === "sent") {
                                wolStage.celebrate = true
                                wolSettle.restart()
                            } else if (wakeOnLan.phase !== "sending") {
                                wolStage.celebrate = false
                            }
                        }
                    }

                    Item {
                        id: orb
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top
                        anchors.topMargin: ui.gap
                        width: Math.min(parent.width * 0.46, ui.mm * 38)
                        height: width

                        Repeater {
                            model: 3
                            delegate: Rectangle {
                                property real shift: (wolStage.wave + index / 3) % 1
                                anchors.centerIn: parent
                                width: parent.width
                                height: width
                                radius: width / 2
                                color: "transparent"
                                border.width: Math.max(1, ui.mm * 0.4)
                                border.color: wakeOnLan.phase === "sent" ? ui.success : ui.primary
                                visible: wolStage.waving
                                scale: 0.34 + shift * 1.2
                                opacity: (1 - shift) * 0.75
                            }
                        }

                        Rectangle {
                            anchors.centerIn: parent
                            width: parent.width * 0.42
                            height: width
                            radius: width / 2
                            color: wakeOnLan.phase === "error" ? ui.danger
                                 : wakeOnLan.phase === "sent" ? ui.success
                                 : wakeOnLan.phase === "sending" ? ui.primary
                                 : ui.surfaceHigh

                            Icon {
                                anchors.centerIn: parent
                                name: "power"
                                size: parent.width * 0.46
                                color: wakeOnLan.phase === "" ? ui.textMuted : ui.onAccent
                            }

                            SequentialAnimation on scale {
                                running: wolStage.waving
                                loops: Animation.Infinite
                                NumberAnimation { from: 1; to: 1.08; duration: 420; easing.type: Easing.InOutQuad }
                                NumberAnimation { from: 1.08; to: 1; duration: 420; easing.type: Easing.InOutQuad }
                            }
                        }
                    }

                    Column {
                        anchors.top: orb.bottom
                        anchors.topMargin: ui.gap
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: parent.width
                        spacing: Math.round(ui.gap * 0.45)

                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            text: wakeOnLan.mac !== "" ? wakeOnLan.mac : i18n.pack.wolEmpty
                            color: ui.text
                            font.pixelSize: wakeOnLan.mac !== "" ? ui.fontTitle : ui.fontBody
                            font.family: wakeOnLan.mac !== "" ? ui.monoFamily : ""
                            font.weight: Font.DemiBold
                            wrapMode: Text.Wrap
                            elide: Text.ElideRight
                        }
                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            visible: wakeOnLan.phase !== ""
                            text: wakeOnLan.phase === "sending" ? i18n.pack.wolSending
                                : wakeOnLan.phase === "sent" ? i18n.pack.wolSent
                                : wakeOnLan.detail
                            color: wakeOnLan.phase === "error" ? ui.danger
                                 : wakeOnLan.phase === "sent" ? ui.success
                                 : ui.primary
                            font.pixelSize: ui.fontBody
                            wrapMode: Text.Wrap
                        }
                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            visible: wakeOnLan.phase === "sent" && wakeOnLan.target !== ""
                            text: i18n.pack.wolVia.replace("{target}", wakeOnLan.target).replace("{port}", wakeOnLan.port)
                            color: ui.textMuted
                            font.pixelSize: ui.fontBody
                            font.family: ui.monoFamily
                        }
                    }
                }
            }

            // Temperatura ambiente
            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: ui.gap

                    StatCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        label: i18n.pack.temperature
                        icon: "thermometer"
                        tone: ui.warning
                        value: climate.temperature
                    }
                    StatCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        label: i18n.pack.humidity
                        icon: "droplet"
                        tone: ui.primary
                        value: climate.humidity
                    }
                }
                RowLayout {
                    Text {
                        Layout.fillWidth: true
                        text: climate.status
                        color: ui.danger
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }
                    TouchButton {
                        text: climate.busy ? i18n.pack.reading : i18n.pack.refresh
                        icon: "refresh"
                        kind: "neutral"
                        enabled: !climate.busy
                        onClicked: climate.refresh()
                    }
                }
            }

            // Test de velocidad
            ColumnLayout {
                id: speedPage
                spacing: ui.gap

                property string selectedInterface: ""

                readonly property var speedInterfaces: {
                    var rows = network.interfaces
                    var found = []
                    for (var i = 0; i < rows.length; ++i) {
                        var row = rows[i]
                        var name = typeof row === "string" ? row : row.value
                        if (name !== "lo")
                            found.push(typeof row === "string"
                                       ? { label: name, value: name, linked: false, address: "" }
                                       : row)
                    }
                    return found
                }

                readonly property string selectedAddress: {
                    for (var i = 0; i < speedInterfaces.length; ++i) {
                        if (speedInterfaces[i].value === selectedInterface)
                            return speedInterfaces[i].address || ""
                    }
                    return ""
                }

                function keepSpeedSelection() {
                    var rows = speedInterfaces
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
                    function onInterfacesChanged() { speedPage.keepSpeedSelection() }
                }

                Component.onCompleted: keepSpeedSelection()

                ChoiceChips {
                    Layout.fillWidth: true
                    model: speedPage.speedInterfaces
                    value: speedPage.selectedInterface
                    enabled: !speedTest.busy
                    onActivated: speedPage.selectedInterface = value
                }
                Text {
                    Layout.fillWidth: true
                    text: speedPage.speedInterfaces.length === 0
                          ? i18n.pack.noIfaces
                          : (speedPage.selectedAddress !== ""
                             ? speedPage.selectedAddress
                             : i18n.pack.speedNoIpv4)
                    color: speedPage.selectedAddress !== "" ? ui.text : ui.textMuted
                    font.pixelSize: ui.fontBody
                    font.family: speedPage.selectedAddress !== "" ? ui.monoFamily : ""
                    wrapMode: Text.Wrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: ui.gap

                    StatCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        label: i18n.pack.download
                        icon: "download"
                        tone: ui.success
                        value: speedTest.download
                        unit: "Mbps"
                    }
                    StatCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        label: i18n.pack.upload
                        icon: "upload"
                        tone: ui.primary
                        value: speedTest.upload
                        unit: "Mbps"
                    }
                }
                RowLayout {
                    spacing: ui.gap

                    BusyIndicator {
                        running: speedTest.busy
                        visible: running
                        Layout.preferredWidth: ui.touch
                        Layout.preferredHeight: ui.touch
                    }
                    Text {
                        Layout.fillWidth: true
                        text: speedTest.status
                        color: speedTest.busy ? ui.textMuted : ui.danger
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }
                    TouchButton {
                        text: speedTest.busy ? i18n.pack.measuring : i18n.pack.startTest
                        icon: "gauge"
                        kind: "success"
                        enabled: !speedTest.busy && speedPage.selectedAddress !== ""
                        onClicked: speedTest.measure(speedPage.selectedInterface)
                    }
                }
            }

            // IP publica
            ColumnLayout {
                id: publicPage
                spacing: ui.gap

                readonly property var facts: {
                    try { return JSON.parse(publicIp.factsJson) }
                    catch (e) { return [] }
                }
                readonly property var columns: [
                    { key: "label", share: 40 },
                    { key: "value", share: 60 }
                ]

                function columnWidth(share) {
                    var bar = publicTable.overflowing ? Math.round(ui.mm * 4) : 0
                    return Math.max(1, (publicTable.width - bar) * share / 100)
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: publicIp.busy ? i18n.pack.lookingUp : i18n.pack.pubTitle
                        color: ui.text
                        font.pixelSize: ui.fontBody
                        elide: Text.ElideRight
                    }
                    TouchButton {
                        text: i18n.pack.save
                        icon: "file"
                        kind: "success"
                        enabled: !publicIp.busy && publicPage.facts.length > 0
                        onClicked: publicIp.save()
                    }
                    TouchButton {
                        text: publicIp.busy ? i18n.pack.lookingUp : i18n.pack.lookup
                        icon: "refresh"
                        kind: "neutral"
                        enabled: !publicIp.busy
                        onClicked: publicIp.lookup()
                    }
                }

                Text {
                    Layout.fillWidth: true
                    visible: publicIp.status !== ""
                    text: publicIp.status
                    color: ui.danger
                    font.pixelSize: ui.fontSmall
                    wrapMode: Text.Wrap
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
                        visible: publicPage.facts.length === 0
                        text: publicIp.busy ? i18n.pack.lookingUp : i18n.pack.pubEmpty
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Math.round(ui.gap * 0.6)
                        visible: publicPage.facts.length > 0
                        spacing: Math.round(ui.gap * 0.3)

                        ScrollPage {
                            id: publicTable
                            spacing: 1

                            Repeater {
                                model: publicPage.facts
                                delegate: Rectangle {
                                    id: publicRow
                                    readonly property var fact: modelData
                                    Layout.fillWidth: true
                                    implicitHeight: Math.round(ui.fontSmall * 2.15)
                                    color: index % 2 === 0 ? "transparent" : ui.surfaceAlt
                                    Row {
                                        anchors.fill: parent
                                        Repeater {
                                            model: publicPage.columns
                                            delegate: CopyableCell {
                                                width: publicPage.columnWidth(modelData.share)
                                                height: publicRow.height
                                                text: publicRow.fact[modelData.key] === undefined
                                                      ? "" : String(publicRow.fact[modelData.key])
                                                color: ui.text
                                                font.pixelSize: ui.fontSmall
                                                font.family: modelData.key === "value" ? ui.monoFamily : ""
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

            // Info Wi-Fi
            ColumnLayout {
                id: wifiInfo
                spacing: ui.gap

                readonly property var linkFacts: {
                    try { return JSON.parse(wifi.linkJson) }
                    catch (e) { return [] }
                }
                readonly property var columns: [
                    { key: "label", share: 40 },
                    { key: "value", share: 60 }
                ]

                function columnWidth(share) {
                    var bar = wifiTable.overflowing ? Math.round(ui.mm * 4) : 0
                    return Math.max(1, (wifiTable.width - bar) * share / 100)
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: wifi.busy ? i18n.pack.readingLink
                              : (wifi.deviceName === "" ? i18n.pack.noWifi : wifi.deviceName)
                        color: ui.text
                        font.pixelSize: ui.fontBody
                        elide: Text.ElideRight
                    }
                    TouchButton {
                        text: i18n.pack.save
                        icon: "file"
                        kind: "success"
                        enabled: !wifi.busy && wifiInfo.linkFacts.length > 0
                        onClicked: wifi.saveLink()
                    }
                    TouchButton {
                        text: wifi.busy ? i18n.pack.reading : i18n.pack.refresh
                        icon: "refresh"
                        kind: "neutral"
                        enabled: !wifi.busy
                        onClicked: wifi.loadLink()
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
                        visible: wifiInfo.linkFacts.length === 0
                        text: wifi.deviceName === "" ? i18n.pack.noWifiIface : i18n.pack.noLink
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Math.round(ui.gap * 0.6)
                        visible: wifiInfo.linkFacts.length > 0
                        spacing: Math.round(ui.gap * 0.3)

                        ScrollPage {
                            id: wifiTable
                            spacing: 1

                            Repeater {
                                model: wifiInfo.linkFacts
                                delegate: Rectangle {
                                    id: wifiRow
                                    readonly property var fact: modelData
                                    Layout.fillWidth: true
                                    implicitHeight: Math.round(ui.fontSmall * 2.15)
                                    color: index % 2 === 0 ? "transparent" : ui.surfaceAlt
                                    Row {
                                        anchors.fill: parent
                                        Repeater {
                                            model: wifiInfo.columns
                                            delegate: CopyableCell {
                                                width: wifiInfo.columnWidth(modelData.share)
                                                height: wifiRow.height
                                                text: wifiRow.fact[modelData.key] === undefined
                                                      ? "" : String(wifiRow.fact[modelData.key])
                                                color: ui.text
                                                font.pixelSize: ui.fontSmall
                                                font.family: modelData.key === "value" ? ui.monoFamily : ""
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

            // MAC vendors
            ColumnLayout {
                spacing: ui.gap

                Field {
                    id: vendorMac
                    Layout.fillWidth: true
                    placeholderText: i18n.pack.macField
                    onAccepted: if (!macVendor.busy) macVendor.lookup(text)
                }
                Card {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    title: i18n.pack.vendor
                    titleIcon: "info"

                    SelectableText {
                        text: macVendor.vendor
                        font.pixelSize: ui.fontTitle
                        font.weight: Font.DemiBold
                    }
                }
                RowLayout {
                    Text {
                        Layout.fillWidth: true
                        text: macVendor.status
                        color: ui.danger
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }
                    TouchButton {
                        text: macVendor.busy ? i18n.pack.lookingUp : i18n.pack.lookup
                        icon: "refresh"
                        kind: "neutral"
                        enabled: !macVendor.busy
                        onClicked: macVendor.lookup(vendorMac.text)
                    }
                }
            }

            // Gestión de archivos
            ColumnLayout {
                id: filesPage
                spacing: ui.gap

                property var picked: []
                property string chosenDrive: ""
                property string action: ""

                readonly property string activePlace: picked.length === 1 ? picked[0].place : ""
                readonly property string activeName: picked.length === 1 ? picked[0].name : ""

                readonly property var drives: {
                    try { return JSON.parse(files.drivesJson) }
                    catch (e) { return [] }
                }

                readonly property var rows: {
                    try { return JSON.parse(files.filesJson) }
                    catch (e) { return [] }
                }

                function baseName(name) {
                    return name.replace(/\.(pcap|csv|txt)$/i, "")
                }

                function isPicked(place, name) {
                    for (var i = 0; i < picked.length; ++i) {
                        if (picked[i].place === place && picked[i].name === name)
                            return true
                    }
                    return false
                }

                function togglePick(place, name) {
                    var next = []
                    var found = false
                    for (var i = 0; i < picked.length; ++i) {
                        if (picked[i].place === place && picked[i].name === name)
                            found = true
                        else
                            next.push(picked[i])
                    }
                    if (!found)
                        next.push({ place: place, name: name })
                    picked = next
                    if (next.length !== 1)
                        action = ""
                }

                function begin(kind) {
                    if (kind !== "export" && picked.length !== 1)
                        return
                    if (picked.length === 0)
                        return
                    action = kind
                    chosenDrive = ""
                    if (kind === "export") {
                        files.refreshDrives()
                        return
                    }
                    newName.text = kind === "copy"
                            ? baseName(activeName) + i18n.pack.copySuffix
                            : baseName(activeName)
                }

                onRowsChanged: {
                    var next = []
                    for (var i = 0; i < picked.length; ++i) {
                        var item = picked[i]
                        for (var j = 0; j < rows.length; ++j) {
                            if (rows[j].place === item.place && rows[j].name === item.name) {
                                next.push(item)
                                break
                            }
                        }
                    }
                    if (next.length !== picked.length)
                        picked = next
                }

                function cancel() {
                    action = ""
                    chosenDrive = ""
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: i18n.pack.fileManager
                        color: ui.text
                        font.pixelSize: ui.fontBody
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                    TouchButton {
                        text: files.busy ? i18n.pack.reading : i18n.pack.refresh
                        icon: "refresh"
                        kind: "neutral"
                        enabled: !files.busy
                        onClicked: files.refresh()
                    }
                }

                ScrollPage {
                    Text {
                        Layout.fillWidth: true
                        visible: filesPage.rows.length === 0
                        text: i18n.pack.noFiles
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                    }
                    Repeater {
                        model: filesPage.rows

                        delegate: Rectangle {
                            readonly property bool picked: filesPage.isPicked(modelData.place, modelData.name)

                            Layout.fillWidth: true
                            Layout.preferredHeight: ui.touch
                            radius: ui.radius
                            color: picked ? ui.primary : (area.pressed ? ui.surfaceHigh : ui.surfaceAlt)
                            border.width: 1
                            border.color: picked ? ui.primary : ui.border

                            Rectangle {
                                anchors.left: parent.left
                                anchors.leftMargin: ui.gap
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.round(ui.touch * 0.46)
                                height: width
                                radius: ui.radius * 0.4
                                color: picked ? ui.onAccent : "transparent"
                                border.width: 2
                                border.color: picked ? ui.onAccent : ui.border

                                Text {
                                    anchors.centerIn: parent
                                    visible: picked
                                    text: "✓"
                                    color: ui.primary
                                    font.pixelSize: ui.fontBody
                                    font.weight: Font.Bold
                                }
                            }
                            Text {
                                anchors.fill: parent
                                anchors.leftMargin: ui.touch * 0.85
                                anchors.rightMargin: ui.padding
                                verticalAlignment: Text.AlignVCenter
                                text: (modelData.place === "captura" ? i18n.pack.placeCapture
                                      : modelData.place === "tap" ? i18n.pack.placeTap
                                      : modelData.place === "traza" ? i18n.pack.placeTrace
                                      : modelData.place === "ping" ? i18n.pack.placePing
                                      : modelData.place === "publica" ? i18n.pack.placePublic
                                      : modelData.place === "wifi" ? i18n.pack.placeWifi
                                      : modelData.place === "escaneo" ? i18n.pack.placeScan
                                      : modelData.place === "descubrimiento" ? i18n.pack.placeDiscover
                                      : modelData.placeLabel) + "   " + modelData.name
                                      + "   " + modelData.size + "   " + modelData.modified
                                color: picked ? ui.onAccent : ui.text
                                font.pixelSize: ui.fontSmall
                                elide: Text.ElideRight
                            }
                            TouchArea {
                                id: area
                                onTapped: filesPage.togglePick(modelData.place, modelData.name)
                            }
                        }
                    }
                }

                RowLayout {
                    spacing: ui.gap

                    TouchButton {
                        Layout.fillWidth: true
                        text: i18n.pack.rename
                        kind: "neutral"
                        enabled: !files.busy && filesPage.picked.length === 1
                        onClicked: filesPage.begin("rename")
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: i18n.pack.copy
                        kind: "neutral"
                        enabled: !files.busy && filesPage.picked.length === 1
                        onClicked: filesPage.begin("copy")
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: i18n.pack.export
                        kind: "neutral"
                        enabled: !files.busy && filesPage.picked.length > 0
                        onClicked: filesPage.begin("export")
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: i18n.pack.delete
                        kind: "danger"
                        enabled: !files.busy && filesPage.picked.length > 0
                        onClicked: dialog.ask({
                            title: i18n.pack.deleteTitle,
                            kind: "danger",
                            message: filesPage.picked.length > 1
                                     ? i18n.pack.deleteMany.replace("{count}", filesPage.picked.length)
                                     : i18n.pack.deleteBody.replace("{name}", filesPage.activeName),
                            confirmText: i18n.pack.delete,
                            confirmAction: function() {
                                files.removeMany(JSON.stringify(filesPage.picked))
                                filesPage.action = ""
                            }
                        })
                    }
                }

                ColumnLayout {
                    visible: filesPage.action === "export"
                    spacing: ui.gap

                    Text {
                        Layout.fillWidth: true
                        text: filesPage.drives.length === 0
                              ? i18n.pack.noUsb
                              : i18n.pack.pickUsb
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        wrapMode: Text.Wrap
                    }
                    ChoiceChips {
                        Layout.fillWidth: true
                        visible: filesPage.drives.length > 0
                        model: filesPage.drives
                        value: filesPage.chosenDrive
                        enabled: !files.busy
                        onActivated: filesPage.chosenDrive = value
                    }
                    TouchButton {
                        text: files.busy ? i18n.pack.searching : i18n.pack.findUsb
                        icon: "refresh"
                        kind: "neutral"
                        enabled: !files.busy
                        onClicked: files.refreshDrives()
                    }
                }

                RowLayout {
                    visible: filesPage.action === "rename" || filesPage.action === "copy"
                             || filesPage.action === "export"
                    spacing: ui.gap

                    Field {
                        id: newName
                        Layout.fillWidth: true
                        visible: filesPage.action !== "export"
                        placeholderText: i18n.pack.newName
                        enabled: !files.busy
                    }
                    TouchButton {
                        text: i18n.pack.cancel
                        kind: "neutral"
                        enabled: !files.busy
                        onClicked: filesPage.cancel()
                    }
                    TouchButton {
                        text: i18n.pack.apply
                        icon: "check"
                        kind: "success"
                        enabled: !files.busy && (filesPage.action === "export"
                                 ? filesPage.chosenDrive !== "" : true)
                        onClicked: {
                            if (filesPage.action === "rename")
                                files.rename(filesPage.activePlace, filesPage.activeName, newName.text)
                            else if (filesPage.action === "copy")
                                files.copyFile(filesPage.activePlace, filesPage.activeName, newName.text)
                            else
                                files.exportMany(JSON.stringify(filesPage.picked), filesPage.chosenDrive)
                        }
                    }
                }
            }
        }
    }
}
