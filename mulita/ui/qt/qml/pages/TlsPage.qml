import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

// Analisis de certificados TLS con testssl.sh: destino, tipo de analisis,
// resultado agrupado por seccion y la salida del programa.
Item {
    id: root

    readonly property var rows: {
        try { return JSON.parse(tls.rowsJson) }
        catch (e) { return [] }
    }
    readonly property var summary: {
        try { return JSON.parse(tls.summaryJson) }
        catch (e) { return [] }
    }
    readonly property var modes: {
        try { return JSON.parse(tls.modesJson) }
        catch (e) { return ({ "default": "", items: [] }) }
    }
    property string mode: modes["default"]

    function tone(name) {
        return name === "danger" ? ui.danger
             : name === "warning" ? ui.warning
             : name === "success" ? ui.success : ui.textMuted
    }

    function modeOptions() {
        var list = []
        for (var i = 0; i < modes.items.length; ++i)
            list.push({ label: i18n.pack[modes.items[i].title], value: modes.items[i].id })
        return list
    }

    function columnWidth(share) {
        return Math.max(1, table.viewportWidth * share / 100)
    }

    function begin() {
        if (!tls.running && hostField.text.trim() !== "")
            tls.start(hostField.text, root.mode)
    }

    Connections {
        target: tls

        function onRunningChanged() {
            tabs.currentIndex = tls.running ? 2 : 1
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        RowLayout {
            spacing: ui.gap

            PageTabs {
                id: tabs
                objectName: "tlsTabs"
                Layout.fillWidth: true
                tabs: [i18n.pack.tlsScan, i18n.pack.tlsResult, i18n.pack.tlsOutput]
            }
            TouchButton {
                Layout.preferredWidth: ui.mm * 34
                text: tls.running ? i18n.pack.stop : i18n.pack.start
                icon: tls.running ? "stop" : "play"
                kind: tls.running ? "danger" : "success"
                enabled: tls.running || hostField.text.trim() !== ""
                onClicked: tls.running ? tls.stop() : root.begin()
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            // Analisis: destino y tipo
            ColumnLayout {
                spacing: ui.gap

                Field {
                    id: hostField
                    Layout.fillWidth: true
                    placeholderText: i18n.pack.tlsTarget
                    enabled: !tls.running
                    inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText | Qt.ImhUrlCharactersOnly
                    onAccepted: root.begin()
                }
                ChoiceChips {
                    Layout.fillWidth: true
                    model: root.modeOptions()
                    value: root.mode
                    enabled: !tls.running
                    onActivated: root.mode = value
                }
                Text {
                    Layout.fillWidth: true
                    text: i18n.pack.tlsHint
                    color: ui.textMuted
                    font.pixelSize: ui.fontSmall
                    wrapMode: Text.Wrap
                }
                Item {
                    Layout.fillHeight: true
                }
            }

            // Resultado
            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    Layout.fillWidth: true
                    visible: root.rows.length > 0
                    spacing: Math.round(ui.gap * 0.6)

                    Text {
                        Layout.fillWidth: true
                        text: tls.target
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        font.family: ui.monoFamily
                        elide: Text.ElideRight
                    }
                    Repeater {
                        model: root.summary
                        delegate: StatusPill {
                            text: modelData.label + "  " + modelData.count
                            tone: root.tone(modelData.tone)
                        }
                    }
                    TouchButton {
                        text: i18n.pack.save
                        icon: "file"
                        kind: "success"
                        enabled: !tls.running
                        onClicked: tls.save()
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
                        visible: root.rows.length === 0
                        text: tls.running ? i18n.pack.tlsWaiting : i18n.pack.tlsEmpty
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Math.round(ui.gap * 0.6)
                        visible: root.rows.length > 0
                        spacing: Math.round(ui.gap * 0.3)

                        ScrollPage {
                            id: table
                            spacing: 1

                            Row {
                                Layout.fillWidth: true

                                Text {
                                    width: root.columnWidth(15)
                                    text: i18n.pack.tlsSeverity
                                    color: ui.textMuted
                                    font.pixelSize: ui.fontSmall
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Text {
                                    width: root.columnWidth(27)
                                    text: i18n.pack.tlsTest
                                    color: ui.textMuted
                                    font.pixelSize: ui.fontSmall
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Text {
                                    width: root.columnWidth(58)
                                    text: i18n.pack.tlsResult
                                    color: ui.textMuted
                                    font.pixelSize: ui.fontSmall
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                            }

                            Repeater {
                                model: root.rows.length

                                delegate: Rectangle {
                                    id: line

                                    readonly property var entry: root.rows[index] || ({})
                                    readonly property bool header: entry.header === true
                                    readonly property int pad: Math.round(ui.gap * 0.4)

                                    Layout.fillWidth: true
                                    implicitHeight: header
                                                    ? Math.round(ui.fontSmall * 2.3)
                                                    : Math.max(Math.round(ui.fontSmall * 2.15),
                                                               Math.max(resultText.implicitHeight,
                                                                        testText.implicitHeight) + pad * 2)
                                    color: header ? ui.surfaceHigh
                                                  : (index % 2 === 0 ? "transparent" : ui.surfaceAlt)

                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.left: parent.left
                                        anchors.leftMargin: line.pad
                                        visible: line.header
                                        text: line.entry.title || ""
                                        color: ui.primary
                                        font.pixelSize: ui.fontSmall
                                        font.weight: Font.Bold
                                    }

                                    Row {
                                        anchors.fill: parent
                                        visible: !line.header

                                        Text {
                                            width: root.columnWidth(15)
                                            height: line.height
                                            text: line.entry.severity || ""
                                            color: root.tone(line.entry.tone)
                                            font.pixelSize: ui.fontSmall
                                            font.weight: Font.DemiBold
                                            verticalAlignment: Text.AlignVCenter
                                            leftPadding: line.pad
                                            elide: Text.ElideRight
                                        }
                                        CopyableCell {
                                            id: testText
                                            width: root.columnWidth(27)
                                            height: line.height
                                            text: line.entry.test || ""
                                            color: ui.text
                                            font.pixelSize: ui.fontSmall
                                            verticalAlignment: Text.AlignVCenter
                                            wrapMode: Text.Wrap
                                        }
                                        CopyableCell {
                                            id: resultText
                                            width: root.columnWidth(58)
                                            height: line.height
                                            text: line.entry.result || ""
                                            color: ui.text
                                            font.pixelSize: ui.fontSmall
                                            font.family: ui.monoFamily
                                            verticalAlignment: Text.AlignVCenter
                                            wrapMode: Text.Wrap
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

            }

            // Salida de testssl.sh
            ConsoleView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                source: tls.console
                placeholder: i18n.pack.tlsOutputEmpty
            }
        }
    }
}
