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
                        onAccepted: if (!wakeOnLan.busy) wakeOnLan.wake(text)
                    }
                    TouchButton {
                        text: i18n.pack.wake
                        icon: "power"
                        enabled: !wakeOnLan.busy
                        onClicked: wakeOnLan.wake(mac.text)
                    }
                }
                ConsoleView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: wakeOnLan.console
                    placeholder: i18n.pack.wolEmpty
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
                spacing: ui.gap

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
                        enabled: !speedTest.busy
                        onClicked: speedTest.measure()
                    }
                }
            }

            // IP publica
            ColumnLayout {
                spacing: ui.gap

                StatCard {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    label: i18n.pack.publicIp
                    icon: "globe"
                    value: publicIp.address
                }
                RowLayout {
                    Text {
                        Layout.fillWidth: true
                        text: publicIp.status
                        color: ui.danger
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }
                    TouchButton {
                        text: publicIp.busy ? i18n.pack.lookingUp : i18n.pack.lookup
                        icon: "refresh"
                        kind: "neutral"
                        enabled: !publicIp.busy
                        onClicked: publicIp.lookup()
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
                        text: wifi.busy ? i18n.pack.reading : i18n.pack.refresh
                        icon: "refresh"
                        kind: "neutral"
                        enabled: !wifi.busy
                        onClicked: wifi.loadLink()
                    }
                }

                ScrollPage {
                    Card {
                        Layout.fillWidth: true
                        title: i18n.pack.wifiInfo
                        titleIcon: "wifi"

                        Text {
                            visible: wifiInfo.linkFacts.length === 0
                            text: wifi.deviceName === "" ? i18n.pack.noWifiIface : i18n.pack.noLink
                            color: ui.textMuted
                            font.pixelSize: ui.fontBody
                            wrapMode: Text.Wrap
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: ui.gap
                            rowSpacing: Math.round(ui.gap * 0.45)

                            Repeater {
                                model: wifiInfo.linkFacts

                                delegate: ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0

                                    Text {
                                        text: modelData.label
                                        color: ui.textMuted
                                        font.pixelSize: ui.fontSmall
                                    }
                                        SelectableText { text: modelData.value }
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

                property string chosenPlace: ""
                property string chosenName: ""
                property string chosenDrive: ""
                property string action: ""

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

                function begin(kind) {
                    if (chosenName === "")
                        return
                    action = kind
                    chosenDrive = ""
                    if (kind === "export") {
                        files.refreshDrives()
                        return
                    }
                    newName.text = kind === "copy" ? baseName(chosenName) + i18n.pack.copySuffix : baseName(chosenName)
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
                            readonly property bool selected: filesPage.chosenPlace === modelData.place
                                                             && filesPage.chosenName === modelData.name

                            Layout.fillWidth: true
                            Layout.preferredHeight: ui.touch
                            radius: ui.radius
                            color: selected ? ui.primary : (area.pressed ? ui.surfaceHigh : ui.surfaceAlt)
                            border.width: 1
                            border.color: selected ? ui.primary : ui.border

                            Text {
                                anchors.fill: parent
                                anchors.leftMargin: ui.padding
                                anchors.rightMargin: ui.padding
                                verticalAlignment: Text.AlignVCenter
                                text: (modelData.place === "captura" ? i18n.pack.placeCapture
                                      : modelData.place === "tap" ? i18n.pack.placeTap
                                      : modelData.place === "traza" ? i18n.pack.placeTrace
                                      : modelData.place === "ping" ? i18n.pack.placePing
                                      : modelData.placeLabel) + "   " + modelData.name
                                      + "   " + modelData.size + "   " + modelData.modified
                                color: selected ? ui.onAccent : ui.text
                                font.pixelSize: ui.fontSmall
                                elide: Text.ElideRight
                            }
                            TouchArea {
                                id: area
                                onTapped: {
                                    filesPage.chosenPlace = modelData.place
                                    filesPage.chosenName = modelData.name
                                    filesPage.action = ""
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    spacing: ui.gap
                    enabled: filesPage.chosenName !== "" && !files.busy

                    TouchButton {
                        Layout.fillWidth: true
                        text: i18n.pack.rename
                        kind: "neutral"
                        enabled: parent.enabled
                        onClicked: filesPage.begin("rename")
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: i18n.pack.copy
                        kind: "neutral"
                        enabled: parent.enabled
                        onClicked: filesPage.begin("copy")
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: i18n.pack.export
                        kind: "neutral"
                        enabled: parent.enabled
                        onClicked: filesPage.begin("export")
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: i18n.pack.delete
                        kind: "danger"
                        enabled: parent.enabled
                        onClicked: dialog.ask({
                            title: i18n.pack.deleteTitle,
                            kind: "danger",
                            message: i18n.pack.deleteBody.replace("{name}", filesPage.chosenName),
                            confirmText: i18n.pack.delete,
                            confirmAction: function() {
                                files.remove(filesPage.chosenPlace, filesPage.chosenName)
                                filesPage.chosenName = ""
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
                                files.rename(filesPage.chosenPlace, filesPage.chosenName, newName.text)
                            else if (filesPage.action === "copy")
                                files.copyFile(filesPage.chosenPlace, filesPage.chosenName, newName.text)
                            else
                                files.exportFile(filesPage.chosenPlace, filesPage.chosenName, filesPage.chosenDrive)
                        }
                    }
                }
            }
        }
    }
}
