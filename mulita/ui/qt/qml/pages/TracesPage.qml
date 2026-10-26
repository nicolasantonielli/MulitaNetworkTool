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
        { title: i18n.pack.hop, key: "hop", share: 8 },
        { title: i18n.pack.address, key: "address", share: 24 },
        { title: i18n.pack.loss, key: "loss", share: 11 },
        { title: i18n.pack.sent, key: "sent", share: 9 },
        { title: i18n.pack.last, key: "last", share: 10 },
        { title: i18n.pack.average, key: "average", share: 10 },
        { title: i18n.pack.best, key: "best", share: 9 },
        { title: i18n.pack.worst, key: "worst", share: 9 },
        { title: i18n.pack.deviation, key: "deviation", share: 10 }
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
            tabs: [i18n.pack.tabTraces, i18n.pack.tabPing]
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
                        placeholderText: i18n.pack.dest
                        onAccepted: if (!trace.busy) trace.trace(text)
                    }
                    TouchButton {
                        text: trace.busy ? i18n.pack.tracing : i18n.pack.trace
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
                        text: trace.busy ? i18n.pack.tracing : i18n.pack.traceEmpty
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
                            text: i18n.pack.traceTimes
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
                        placeholderText: i18n.pack.fileName
                        enabled: !trace.busy
                    }
                    Text {
                        text: ".csv"
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                    }
                    TouchButton {
                        text: i18n.pack.clear
                        kind: "neutral"
                        enabled: !trace.busy && root.hops.length > 0
                        onClicked: trace.clear()
                    }
                    TouchButton {
                        text: i18n.pack.save
                        icon: "file"
                        kind: "success"
                        enabled: !trace.busy && root.hops.length > 0
                        onClicked: trace.save(traceFile.text)
                    }
                }
            }

            // Ping
            ColumnLayout {
                id: pingPage
                spacing: ui.gap

                readonly property var replies: {
                    try { return JSON.parse(ping.repliesJson) }
                    catch (e) { return [] }
                }
                readonly property var summary: {
                    if (!ping.summaryJson)
                        return null
                    try { return JSON.parse(ping.summaryJson) }
                    catch (e) { return null }
                }
                readonly property var columns: [
                    { title: i18n.pack.pingSeq, key: "seq", share: 12 },
                    { title: i18n.pack.pingFrom, key: "source", share: 34 },
                    { title: i18n.pack.pingTtl, key: "ttl", share: 12 },
                    { title: i18n.pack.pingTime, key: "time", share: 18 },
                    { title: i18n.pack.pingState, key: "status", share: 24 }
                ]

                function columnWidth(share) {
                    var bar = pingTable.overflowing ? Math.round(ui.mm * 4) : 0
                    return Math.max(1, (pingTable.width - bar) * share / 100)
                }

                function statusText(reply) {
                    if (reply.status === "ok")
                        return i18n.pack.pingOk
                    if (reply.status === "dup")
                        return i18n.pack.pingDup
                    return reply.detail || i18n.pack.pingFail
                }

                function noteText() {
                    var item = summary
                    if (!item)
                        return ""
                    var lines = []
                    if (item.target)
                        lines.push(i18n.pack.pingNoteTitle.replace("{target}", item.target))
                    function add(label, value) {
                        if (value)
                            lines.push(label + ": " + value)
                    }
                    add(i18n.pack.pingSentLabel, item.transmitted)
                    add(i18n.pack.pingReceivedLabel, item.received)
                    add(i18n.pack.pingLossLabel, item.loss)
                    add(i18n.pack.pingElapsedLabel, item.elapsed)
                    add(i18n.pack.pingMinLabel, item.minimum ? item.minimum + " ms" : "")
                    add(i18n.pack.pingAvgLabel, item.average ? item.average + " ms" : "")
                    add(i18n.pack.pingMaxLabel, item.maximum ? item.maximum + " ms" : "")
                    add(i18n.pack.pingDevLabel, item.deviation ? item.deviation + " ms" : "")
                    return lines.join("\n")
                }

                RowLayout {
                    spacing: ui.gap

                    Field {
                        id: pingTarget
                        Layout.fillWidth: true
                        placeholderText: i18n.pack.dest
                        enabled: !ping.running
                    }
                    TouchButton {
                        Layout.preferredWidth: ui.mm * 30
                        text: ping.running ? i18n.pack.stop : i18n.pack.tabPing
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
                        label: i18n.pack.sent
                        from: ping.limits.count.min
                        to: ping.limits.count.max
                        stepSize: 1
                        initial: ping.limits.count.default
                        valueText: Math.round(value) === 0 ? i18n.pack.pingContinuous : Math.round(value) + " " + i18n.pack.pingSends
                    }
                    LabeledSlider {
                        id: pingInterval
                        Layout.fillWidth: true
                        label: i18n.pack.interval
                        from: ping.limits.interval.min
                        to: ping.limits.interval.max
                        stepSize: 0.1
                        initial: ping.limits.interval.default
                        valueText: value.toFixed(1) + " s"
                    }
                    LabeledSlider {
                        id: pingSize
                        Layout.fillWidth: true
                        label: i18n.pack.size
                        from: ping.limits.size.min
                        to: ping.limits.size.max
                        stepSize: 8
                        initial: ping.limits.size.default
                        valueText: Math.round(value) + " bytes"
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
                        visible: pingPage.replies.length === 0
                        text: ping.running ? i18n.pack.pingRunning : i18n.pack.pingEmpty
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Math.round(ui.gap * 0.6)
                        visible: pingPage.replies.length > 0
                        spacing: Math.round(ui.gap * 0.3)

                        Row {
                            Layout.fillWidth: true
                            spacing: 0
                            Repeater {
                                model: pingPage.columns
                                delegate: Text {
                                    width: pingPage.columnWidth(modelData.share)
                                    text: modelData.title
                                    color: ui.textMuted
                                    font.pixelSize: ui.fontSmall
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                    horizontalAlignment: modelData.key === "source"
                                                          ? Text.AlignLeft : Text.AlignHCenter
                                }
                            }
                        }

                        ScrollPage {
                            id: pingTable
                            spacing: 1
                            Repeater {
                                model: pingPage.replies
                                delegate: Rectangle {
                                    id: pingRow
                                    readonly property var reply: modelData
                                    Layout.fillWidth: true
                                    implicitHeight: Math.round(ui.fontSmall * 2.15)
                                    color: index % 2 === 0 ? "transparent" : ui.surfaceAlt
                                    Row {
                                        anchors.fill: parent
                                        Repeater {
                                            model: pingPage.columns
                                            delegate: Text {
                                                width: pingPage.columnWidth(modelData.share)
                                                height: pingRow.height
                                                text: modelData.key === "status"
                                                      ? pingPage.statusText(pingRow.reply)
                                                      : (pingRow.reply[modelData.key] === undefined
                                                         ? "" : String(pingRow.reply[modelData.key]))
                                                color: pingRow.reply.status === "fail" ? ui.danger
                                                       : pingRow.reply.status === "dup" ? ui.warning : ui.text
                                                font.pixelSize: ui.fontSmall
                                                font.family: ui.monoFamily
                                                verticalAlignment: Text.AlignVCenter
                                                elide: Text.ElideRight
                                                horizontalAlignment: modelData.key === "source"
                                                                      ? Text.AlignLeft : Text.AlignHCenter
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                ColumnLayout {
                    visible: pingPage.summary && pingPage.summary.ready
                    spacing: Math.round(ui.gap * 0.25)

                    Text {
                        text: i18n.pack.pingNote
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        font.weight: Font.DemiBold
                    }
                    Text {
                        Layout.fillWidth: true
                        text: pingPage.noteText()
                        color: ui.text
                        font.pixelSize: ui.fontSmall
                        font.family: ui.monoFamily
                        wrapMode: Text.Wrap
                    }
                }

                RowLayout {
                    spacing: ui.gap

                    Field {
                        id: pingFile
                        Layout.fillWidth: true
                        text: "ping"
                        placeholderText: i18n.pack.fileName
                        enabled: !ping.running
                    }
                    Text {
                        text: ".csv"
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                    }
                    TouchButton {
                        text: i18n.pack.clear
                        kind: "neutral"
                        enabled: !ping.running && (pingPage.replies.length > 0
                                 || (pingPage.summary && pingPage.summary.ready))
                        onClicked: ping.clear()
                    }
                    TouchButton {
                        text: i18n.pack.save
                        icon: "file"
                        kind: "success"
                        enabled: !ping.running && (pingPage.replies.length > 0
                                 || (pingPage.summary && pingPage.summary.ready))
                        onClicked: ping.save(pingFile.text)
                    }
                }
            }
        }
    }
}
