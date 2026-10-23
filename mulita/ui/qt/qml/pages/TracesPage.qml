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

                ConsoleView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: trace.console
                    placeholder: "La ruta hacia el destino aparece aquí"
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
