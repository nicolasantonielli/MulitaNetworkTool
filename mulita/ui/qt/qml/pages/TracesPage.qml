import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    readonly property var hops: {
        try { return JSON.parse(trace.hopsJson) }
        catch (e) { return [] }
    }
    readonly property var columns: [
        { title: "Salto", key: "hop", share: 8 },
        { title: "Dirección", key: "address", share: 24 },
        { title: "Pérdida", key: "loss", share: 11 },
        { title: "Envíos", key: "sent", share: 9 },
        { title: "Último", key: "last", share: 10 },
        { title: "Media", key: "average", share: 10 },
        { title: "Mejor", key: "best", share: 9 },
        { title: "Peor", key: "worst", share: 9 },
        { title: "Desvío", key: "deviation", share: 10 }
    ]

    function columnWidth(share) {
        var bar = traceTable.overflowing ? Math.round(ui.mm * 4) : 0
        return Math.max(1, (traceTable.width - bar) * share / 100)
    }

    function cellColor(hop, key) {
        if (key === "address" && hop.address === "???")
            return ui.textMuted
        if (key === "loss") {
            var loss = parseFloat(hop.loss)
            if (loss >= 100)
                return ui.danger
            if (loss > 0)
                return ui.warning
        }
        return ui.text
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        PageTabs {
            id: tabs
            Layout.fillWidth: true
            tabs: ["Trazas", "Ping"]
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            // Trazas (mtr)
            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    spacing: ui.gap

                    Field {
                        id: traceTarget
                        Layout.fillWidth: true
                        placeholderText: "IP o nombre de destino"
                        onAccepted: if (!trace.busy) trace.trace(text)
                    }
                    TouchButton {
                        text: trace.busy ? "Trazando…" : "Trazar"
                        icon: "trace"
                        enabled: !trace.busy
                        onClicked: trace.trace(traceTarget.text)
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
                        visible: root.hops.length === 0
                        text: trace.busy ? "Trazando…" : "La ruta hacia el destino aparece aquí"
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Math.round(ui.gap * 0.6)
                        visible: root.hops.length > 0
                        spacing: Math.round(ui.gap * 0.3)

                        Text {
                            Layout.fillWidth: true
                            text: "Tiempos en milisegundos"
                            color: ui.textMuted
                            font.pixelSize: ui.fontSmall
                        }

                        ScrollPage {
                            id: traceTable
                            spacing: 1

                            Row {
                                Layout.fillWidth: true
                                spacing: 0

                                Repeater {
                                    model: root.columns

                                    delegate: Text {
                                        width: root.columnWidth(modelData.share)
                                        text: modelData.title
                                        color: ui.textMuted
                                        font.pixelSize: ui.fontSmall
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                        horizontalAlignment: modelData.key === "address"
                                                              ? Text.AlignLeft : Text.AlignHCenter
                                    }
                                }
                            }

                            Repeater {
                                model: root.hops

                                delegate: Rectangle {
                                    id: hopRow
                                    readonly property var hop: modelData

                                    Layout.fillWidth: true
                                    implicitHeight: Math.round(ui.fontSmall * 2.15)
                                    radius: ui.radius * 0.4
                                    color: index % 2 === 0 ? "transparent" : ui.surfaceAlt

                                    Row {
                                        anchors.fill: parent
                                        spacing: 0

                                        Repeater {
                                            model: root.columns

                                            delegate: Text {
                                                width: root.columnWidth(modelData.share)
                                                height: hopRow.height
                                                text: hopRow.hop[modelData.key] === undefined
                                                      ? "" : String(hopRow.hop[modelData.key])
                                                color: root.cellColor(hopRow.hop, modelData.key)
                                                font.pixelSize: ui.fontSmall
                                                font.family: ui.monoFamily
                                                verticalAlignment: Text.AlignVCenter
                                                elide: Text.ElideRight
                                                horizontalAlignment: modelData.key === "address"
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
                        id: traceFile
                        Layout.fillWidth: true
                        text: "traza"
                        placeholderText: "Nombre del archivo"
                        enabled: !trace.busy
                    }
                    Text {
                        text: ".csv"
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                    }
                    TouchButton {
                        text: "Guardar"
                        icon: "file"
                        kind: "success"
                        enabled: !trace.busy && root.hops.length > 0
                        onClicked: trace.save(traceFile.text)
                    }
                }
            }

            // Ping
            ColumnLayout {
                spacing: ui.gap

                RowLayout {
                    spacing: ui.gap

                    Field {
                        id: pingTarget
                        Layout.fillWidth: true
                        placeholderText: "IP o nombre de destino"
                        enabled: !ping.running
                    }
                    TouchButton {
                        Layout.preferredWidth: ui.mm * 30
                        text: ping.running ? "Detener" : "Ping"
                        icon: ping.running ? "stop" : "play"
                        kind: ping.running ? "danger" : "success"
                        onClicked: ping.running ? ping.stop()
                                                : ping.start(pingTarget.text, pingCount.value, pingInterval.value, pingSize.value)
                    }
                }

                RowLayout {
                    spacing: ui.gap * 1.5
                    enabled: !ping.running

                    LabeledSlider {
                        id: pingCount
                        Layout.fillWidth: true
                        label: "Envíos"
                        from: ping.limits.count.min
                        to: ping.limits.count.max
                        stepSize: 1
                        initial: ping.limits.count.default
                        valueText: Math.round(value) === 0 ? "Continuo" : Math.round(value) + " envíos"
                    }
                    LabeledSlider {
                        id: pingInterval
                        Layout.fillWidth: true
                        label: "Intervalo"
                        from: ping.limits.interval.min
                        to: ping.limits.interval.max
                        stepSize: 0.1
                        initial: ping.limits.interval.default
                        valueText: value.toFixed(1) + " s"
                    }
                    LabeledSlider {
                        id: pingSize
                        Layout.fillWidth: true
                        label: "Tamaño"
                        from: ping.limits.size.min
                        to: ping.limits.size.max
                        stepSize: 8
                        initial: ping.limits.size.default
                        valueText: Math.round(value) + " bytes"
                    }
                }

                ConsoleView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: ping.console
                    placeholder: "Las respuestas del ping aparecen aquí"
                }
            }
        }
    }
}
