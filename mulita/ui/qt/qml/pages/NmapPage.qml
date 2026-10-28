import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

// Escaneo Nmap por perfiles. No es una terminal: el comando se ve, se ejecuta y se interpreta.
Item {
    id: root

    property string selected: ""
    property string targets: ""
    property string ports: ""
    property string udpChoice: "top20"
    property string interfaceName: ""
    property string excludeText: ""
    property bool noDns: false
    property bool noDiscovery: false
    property string timing: "T3"
    property string sni: ""
    property var scripts: []
    property string customLine: ""
    property string profileName: ""
    property string profileAbout: ""
    property string fileMode: "list"
    property string filterState: ""
    property string compareA: ""
    property int seconds: 0

    readonly property var profiles: {
        try { return JSON.parse(nmapScan.profilesJson) }
        catch (e) { return [] }
    }
    readonly property var checks: {
        try { return JSON.parse(nmapScan.checksJson) }
        catch (e) { return [] }
    }
    readonly property var profile: {
        for (var i = 0; i < profiles.length; ++i)
            if (profiles[i].id === selected)
                return profiles[i]
        return null
    }
    readonly property var plan: {
        if (selected === "")
            return ({ ok: false, command: "", notes: [], error: "" })
        try { return JSON.parse(nmapScan.commandPreview(payload())) }
        catch (e) { return ({ ok: false, command: "", notes: [], error: "" }) }
    }
    readonly property var hosts: {
        try { return JSON.parse(nmapScan.hostsJson) }
        catch (e) { return [] }
    }
    readonly property var summary: {
        try { return JSON.parse(nmapScan.summaryJson) }
        catch (e) { return ({ hosts: 0, up: 0, open: 0 }) }
    }
    readonly property var progress: {
        try { return JSON.parse(nmapScan.progressJson) }
        catch (e) { return ({}) }
    }
    readonly property var history: {
        try { return JSON.parse(nmapScan.historyJson) }
        catch (e) { return [] }
    }
    readonly property var compared: {
        try { return JSON.parse(nmapScan.compareJson) }
        catch (e) { return ({ ready: false }) }
    }
    readonly property var files: {
        try { return JSON.parse(nmapScan.filesJson) }
        catch (e) { return [] }
    }
    readonly property bool scanning: nmapScan.phase === "running" || nmapScan.phase === "starting"
    readonly property var ifaceRows: {
        var rows = network.interfaces
        var found = profile && profile.needsInterface ? [] : [{ label: i18n.pack.nmapAllIfaces, value: "" }]
        for (var i = 0; i < rows.length; ++i) {
            var row = rows[i]
            var name = typeof row === "string" ? row : row.value
            if (name !== "lo")
                found.push(typeof row === "string" ? { label: name, value: name } : row)
        }
        return found
    }

    function pack(key) {
        var value = i18n.pack[key]
        return value !== undefined ? value : key
    }

    function titleOf(item) {
        return item.builtin ? pack(item.title) : item.title
    }

    function hintOf(item) {
        if (!item.builtin)
            return item.description || pack(item.hint)
        return pack(item.hint)
    }

    function payload() {
        return JSON.stringify({
            profile: selected, targets: targets, ports: ports, udp: udpChoice,
            interface: interfaceName, exclude: excludeText, noDns: noDns,
            noDiscovery: noDiscovery, timing: timing, sni: sni, scripts: scripts,
            custom: customLine, name: profileName, description: profileAbout
        })
    }

    function open(id) {
        var item = null
        for (var i = 0; i < profiles.length; ++i)
            if (profiles[i].id === id)
                item = profiles[i]
        if (!item)
            return
        selected = id
        targets = ""
        excludeText = ""
        sni = ""
        noDns = false
        noDiscovery = false
        timing = "T3"
        udpChoice = "top20"
        interfaceName = item.needsInterface ? defaultInterface() : ""
        ports = item.ports === "previous" && nmapScan.lastPorts !== "" ? nmapScan.lastPorts : (item.portDefault || "")
        customLine = item.arguments || ""
        profileName = item.builtin ? "" : item.title
        profileAbout = item.description || ""
        scripts = []
        filterState = ""
        tabs.currentIndex = 0
        if (item.custom)
            nmapScan.refreshFiles()
    }

    function close() {
        if (!scanning)
            selected = ""
    }

    function defaultInterface() {
        var rows = network.interfaces
        for (var i = 0; i < rows.length; ++i) {
            var name = typeof rows[i] === "string" ? rows[i] : rows[i].value
            if (name === "eth0")
                return "eth0"
        }
        for (var j = 0; j < rows.length; ++j) {
            var other = typeof rows[j] === "string" ? rows[j] : rows[j].value
            if (other !== "lo")
                return other
        }
        return ""
    }

    function clock(total) {
        var minutes = Math.floor(total / 60)
        var rest = total % 60
        return (minutes < 10 ? "0" : "") + minutes + ":" + (rest < 10 ? "0" : "") + rest
    }

    function phaseText(phase) {
        if (phase === "starting") return i18n.pack.nmapStarting
        if (phase === "running") return i18n.pack.running
        if (phase === "ok") return i18n.pack.nmapStatusOk
        if (phase === "partial" || phase === "incomplete") return i18n.pack.nmapStatusPartial
        if (phase === "cancelled") return i18n.pack.nmapStatusCancelled
        if (phase === "error") return i18n.pack.nmapStatusError
        return i18n.pack.nmapIdle
    }

    function phaseTone(phase) {
        if (phase === "running" || phase === "ok" || phase === "starting") return ui.success
        if (phase === "partial" || phase === "incomplete" || phase === "cancelled") return ui.warning
        if (phase === "error") return ui.danger
        return ui.textMuted
    }

    function stateLabel(state) {
        if (state === "open") return i18n.pack.nmapStateOpen
        if (state === "closed") return i18n.pack.nmapStateClosed
        if (state === "filtered") return i18n.pack.nmapStateFiltered
        if (state === "open|filtered") return i18n.pack.nmapStateOpenFiltered
        if (state === "closed|filtered") return i18n.pack.nmapStateClosedFiltered
        if (state === "up") return i18n.pack.nmapStateUp
        if (state === "down") return i18n.pack.nmapStateDown
        return state || ""
    }

    function stateColor(state) {
        if (state === "open" || state === "up") return ui.success
        if (state === "open|filtered" || state === "filtered") return ui.warning
        if (state === "closed" || state === "down") return ui.textMuted
        return ui.text
    }

    function kindLabel(kind) {
        if (kind === "vulnerable") return i18n.pack.nmapKindVulnerable
        if (kind === "ok") return i18n.pack.nmapKindOk
        if (kind === "error") return i18n.pack.nmapKindError
        if (kind === "inconclusive") return i18n.pack.nmapKindInconclusive
        return i18n.pack.nmapKindInfo
    }

    function toggleScript(id) {
        var next = []
        var found = false
        for (var i = 0; i < scripts.length; ++i) {
            if (scripts[i] === id)
                found = true
            else
                next.push(scripts[i])
        }
        if (!found)
            next.push(id)
        scripts = next
    }

    function hasScript(id) {
        return scripts.indexOf(id) >= 0
    }

    function portMatches(port, host) {
        if (filterState !== "" && port.state !== filterState)
            return false
        return textMatches(host.ip + " " + (host.names || []).join(" ") + " " + port.port + " "
                           + port.service + " " + port.product + " " + port.version + " " + port.state
                           + " " + scriptBlob(port.scripts))
    }

    function hostMatches(host) {
        var ports = host.ports || []
        var any = false
        for (var i = 0; i < ports.length; ++i)
            if (portMatches(ports[i], host))
                any = true
        if (ports.length === 0)
            return filterState === "" && textMatches(host.ip + " " + (host.names || []).join(" ")
                                                      + " " + host.mac + " " + host.vendor + " " + host.state)
        return any
    }

    function textMatches(blob) {
        var query = search.text.toLowerCase().trim()
        return query === "" || blob.toLowerCase().indexOf(query) >= 0
    }

    function scriptBlob(items) {
        var text = ""
        for (var i = 0; i < (items || []).length; ++i)
            text += " " + items[i].id + " " + items[i].output
        return text
    }

    function lineValue(line) {
        if (line.label !== "nmapCertDays")
            return line.value
        var days = parseInt(line.value, 10)
        if (days < 0)
            return i18n.pack.nmapCertExpired.replace("{days}", String(-days))
        return i18n.pack.nmapCertDays.replace("{days}", line.value)
    }

    function reuse(command) {
        open("custom")
        var line = command || ""
        if (line.indexOf("nmap ") === 0)
            line = line.substring(5)
        customLine = line
        tabs.currentIndex = 0
    }

    ConfirmDialog { id: dialog }

    Timer {
        interval: 1000
        repeat: true
        running: nmapScan.phase === "running"
        onTriggered: root.seconds++
    }

    Connections {
        target: nmapScan
        function onPhaseChanged() {
            if (nmapScan.phase === "running") {
                root.seconds = 0
                tabs.currentIndex = 1
            } else if (nmapScan.phase === "ok" || nmapScan.phase === "partial"
                       || nmapScan.phase === "cancelled" || nmapScan.phase === "error") {
                tabs.currentIndex = 2
            }
        }
    }

    StackLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        currentIndex: root.profile ? 1 : 0

        ScrollPage {
            GridLayout {
                columns: 2
                Layout.fillWidth: true
                rowSpacing: ui.gap
                columnSpacing: ui.gap

                Repeater {
                    model: root.profiles
                    delegate: Rectangle {
                        readonly property bool own: !modelData.builtin
                        Layout.fillWidth: true
                        Layout.preferredHeight: ui.touch * 1.45
                        radius: ui.radius
                        color: area.pressed ? ui.surfaceHigh : ui.surface
                        border.width: 1
                        border.color: ui.border

                        Column {
                            anchors.fill: parent
                            anchors.margins: ui.gap
                            spacing: 1

                            Text {
                                width: parent.width
                                text: root.titleOf(modelData)
                                color: ui.text
                                font.pixelSize: ui.fontBody
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            Text {
                                width: parent.width
                                text: modelData.builtin ? root.pack(modelData.subtitle) : i18n.pack.nmapProfOwnSub
                                color: ui.textMuted
                                font.pixelSize: ui.fontSmall
                                elide: Text.ElideRight
                            }
                            Text {
                                visible: modelData.recommended || own
                                text: modelData.recommended ? i18n.pack.nmapRecommended : i18n.pack.nmapOwn
                                color: modelData.recommended ? ui.success : ui.primary
                                font.pixelSize: ui.fontSmall
                                font.weight: Font.DemiBold
                            }
                        }
                        TouchArea {
                            id: area
                            onTapped: root.open(modelData.id)
                        }
                    }
                }
            }
        }

        ColumnLayout {
            spacing: ui.gap

            RowLayout {
                spacing: ui.gap

                IconButton {
                    icon: "back"
                    enabled: !root.scanning
                    onClicked: root.close()
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Text {
                        Layout.fillWidth: true
                        text: root.profile ? root.titleOf(root.profile) : ""
                        color: ui.text
                        font.pixelSize: ui.fontTitle
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: nmapScan.version !== "" ? "Nmap " + nmapScan.version : ""
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        elide: Text.ElideRight
                    }
                }
                StatusPill {
                    visible: nmapScan.simulated
                    text: i18n.pack.nmapSimulated
                    tone: ui.warning
                }
                StatusPill {
                    text: root.phaseText(nmapScan.phase)
                    tone: root.phaseTone(nmapScan.phase)
                    pulsing: root.scanning
                }
                TouchButton {
                    Layout.preferredWidth: ui.mm * 34
                    text: root.scanning ? i18n.pack.stop : i18n.pack.start
                    icon: root.scanning ? "stop" : "play"
                    kind: root.scanning ? "danger" : "success"
                    enabled: root.scanning || root.plan.ok
                    onClicked: root.scanning ? nmapScan.stop() : nmapScan.start(root.payload())
                }
            }

            Text {
                Layout.fillWidth: true
                visible: nmapScan.fallback !== ""
                text: i18n.pack.nmapFallback
                color: ui.warning
                font.pixelSize: ui.fontSmall
                wrapMode: Text.Wrap
            }
            TouchButton {
                visible: nmapScan.fallback !== ""
                text: i18n.pack.nmapUseFallback
                kind: "neutral"
                enabled: !root.scanning
                onClicked: root.open(nmapScan.fallback)
            }

            PageTabs {
                id: tabs
                objectName: "nmapTabs"
                Layout.fillWidth: true
                tabs: [i18n.pack.nmapAdjust, i18n.pack.nmapRunTab, i18n.pack.nmapResults, i18n.pack.nmapHistory]
            }

            Text {
                Layout.fillWidth: true
                visible: tabs.currentIndex === 0 && nmapScan.versionError !== ""
                text: nmapScan.versionError
                color: ui.warning
                font.pixelSize: ui.fontSmall
                elide: Text.ElideRight
            }
            Text {
                Layout.fillWidth: true
                text: root.plan.command || root.plan.error
                color: root.plan.ok ? ui.text : ui.danger
                font.pixelSize: ui.fontSmall
                font.family: ui.monoFamily
                elide: Text.ElideRight
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: tabs.currentIndex

                ScrollPage {
                    spacing: ui.gap

                    Text {
                        Layout.fillWidth: true
                        text: root.profile ? root.hintOf(root.profile) : ""
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }
                    Field {
                        Layout.fillWidth: true
                        placeholderText: i18n.pack.nmapTargets
                        text: root.targets
                        enabled: !root.scanning
                        onTextEdited: root.targets = text
                    }
                    ChoiceChips {
                        visible: root.profile && root.profile.ports === "udp"
                        Layout.fillWidth: true
                        enabled: !root.scanning
                        model: [
                            { label: i18n.pack.nmapTop20, value: "top20" },
                            { label: i18n.pack.nmapTop100, value: "top100" },
                            { label: i18n.pack.nmapOwnPorts, value: "custom" }
                        ]
                        value: root.udpChoice
                        onActivated: root.udpChoice = value
                    }
                    Field {
                        visible: root.profile && (root.profile.ports === "list" || root.profile.ports === "previous"
                                 || (root.profile.ports === "udp" && root.udpChoice === "custom"))
                        Layout.fillWidth: true
                        placeholderText: i18n.pack.nmapPorts
                        text: root.ports
                        enabled: !root.scanning
                        onTextEdited: root.ports = text
                    }
                    Text {
                        visible: root.profile && !root.profile.custom
                        Layout.fillWidth: true
                        text: i18n.pack.nmapTiming
                        color: ui.text
                        font.pixelSize: ui.fontBody
                    }
                    ChoiceChips {
                        visible: root.profile && !root.profile.custom
                        Layout.fillWidth: true
                        enabled: !root.scanning
                        model: [{ label: "T2", value: "T2" }, { label: "T3", value: "T3" }, { label: "T4", value: "T4" }]
                        value: root.timing
                        onActivated: root.timing = value
                    }
                    ChoiceChips {
                        visible: root.profile && !root.profile.custom && !root.profile.lockedNoDns
                        Layout.fillWidth: true
                        clearable: true
                        enabled: !root.scanning
                        model: [{ label: i18n.pack.nmapNoDns, value: "1" }]
                        value: root.noDns ? "1" : ""
                        onActivated: root.noDns = value === "1"
                    }
                    ChoiceChips {
                        visible: root.profile && !root.profile.custom
                        Layout.fillWidth: true
                        clearable: true
                        enabled: !root.scanning
                        model: [{ label: i18n.pack.nmapNoDiscovery, value: "1" }]
                        value: root.noDiscovery ? "1" : ""
                        onActivated: root.noDiscovery = value === "1"
                    }
                    ChoiceChips {
                        visible: root.profile && !root.profile.custom
                        Layout.fillWidth: true
                        enabled: !root.scanning
                        model: root.ifaceRows
                        value: root.interfaceName
                        onActivated: root.interfaceName = value
                    }
                    Field {
                        visible: root.profile && !root.profile.custom
                        Layout.fillWidth: true
                        placeholderText: i18n.pack.nmapExclude
                        text: root.excludeText
                        enabled: !root.scanning
                        onTextEdited: root.excludeText = text
                    }
                    Field {
                        visible: root.profile && root.profile.sni
                        Layout.fillWidth: true
                        placeholderText: i18n.pack.nmapSni
                        text: root.sni
                        enabled: !root.scanning
                        onTextEdited: root.sni = text
                    }
                    Repeater {
                        model: root.profile && root.profile.catalog ? root.checks : []
                        delegate: Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.max(ui.touch, label.implicitHeight + ui.gap)
                            radius: ui.radius
                            color: root.hasScript(modelData.id) ? ui.primary : ui.surfaceAlt
                            border.width: 1
                            border.color: root.hasScript(modelData.id) ? ui.primary : ui.border
                            Column {
                                id: label
                                anchors.fill: parent
                                anchors.margins: ui.gap
                                Text {
                                    width: parent.width
                                    text: root.pack(modelData.title) + "  ·  " + root.pack(modelData.services)
                                    color: root.hasScript(modelData.id) ? ui.onAccent : ui.text
                                    font.pixelSize: ui.fontSmall
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Text {
                                    width: parent.width
                                    text: root.pack(modelData.detail) + " " + root.pack(modelData.impact)
                                    color: root.hasScript(modelData.id) ? ui.onAccent : ui.textMuted
                                    font.pixelSize: ui.fontSmall
                                    wrapMode: Text.Wrap
                                }
                            }
                            TouchArea {
                                enabled: !root.scanning
                                onTapped: root.toggleScript(modelData.id)
                            }
                        }
                    }
                    Field {
                        visible: root.profile && root.profile.custom
                        Layout.fillWidth: true
                        placeholderText: i18n.pack.nmapArgLine
                        text: root.customLine
                        enabled: !root.scanning
                        onTextEdited: root.customLine = text
                    }
                    Field {
                        visible: root.profile && root.profile.custom
                        Layout.fillWidth: true
                        placeholderText: i18n.pack.nmapProfileName
                        text: root.profileName
                        enabled: !root.scanning
                        onTextEdited: root.profileName = text
                    }
                    Field {
                        visible: root.profile && root.profile.custom
                        Layout.fillWidth: true
                        placeholderText: i18n.pack.nmapProfileAbout
                        text: root.profileAbout
                        enabled: !root.scanning
                        onTextEdited: root.profileAbout = text
                    }
                    RowLayout {
                        visible: root.profile && root.profile.custom
                        ChoiceChips {
                            Layout.fillWidth: true
                            enabled: !root.scanning
                            model: [
                                { label: i18n.pack.nmapInsertList, value: "list" },
                                { label: i18n.pack.nmapInsertScript, value: "script" }
                            ]
                            value: root.fileMode
                            onActivated: root.fileMode = value
                        }
                    }
                    Repeater {
                        model: root.profile && root.profile.custom ? root.files : []
                        delegate: Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: ui.touch * 0.8
                            radius: ui.radius
                            color: fileArea.pressed ? ui.surfaceHigh : ui.surfaceAlt
                            Text {
                                anchors.fill: parent
                                anchors.leftMargin: ui.gap
                                anchors.rightMargin: ui.gap
                                verticalAlignment: Text.AlignVCenter
                                text: root.pack(modelData.place) + "  ·  " + modelData.name
                                color: ui.text
                                font.pixelSize: ui.fontSmall
                                elide: Text.ElideRight
                            }
                            TouchArea {
                                id: fileArea
                                enabled: !root.scanning
                                onTapped: {
                                    var piece = (root.fileMode === "script" ? "--script " : "-iL ") + modelData.token
                                    root.customLine = root.customLine === "" ? piece : root.customLine + " " + piece
                                }
                            }
                        }
                    }
                    Text {
                        visible: root.profile && root.profile.custom && root.files.length === 0
                        text: i18n.pack.nmapNoFiles
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                    }
                    Text {
                        Layout.fillWidth: true
                        text: i18n.pack.nmapPreview
                        color: ui.text
                        font.pixelSize: ui.fontBody
                        font.weight: Font.DemiBold
                    }
                    Text {
                        Layout.fillWidth: true
                        text: root.plan.command || root.plan.error
                        color: root.plan.ok ? ui.text : ui.danger
                        font.pixelSize: ui.fontSmall
                        font.family: ui.monoFamily
                        wrapMode: Text.Wrap
                    }
                    Repeater {
                        model: root.plan.notes || []
                        delegate: Text {
                            Layout.fillWidth: true
                            text: modelData
                            color: ui.textMuted
                            font.pixelSize: ui.fontSmall
                            wrapMode: Text.Wrap
                        }
                    }
                    RowLayout {
                        visible: root.profile && root.profile.custom
                        spacing: ui.gap
                        TouchButton {
                            text: i18n.pack.nmapSaveProfile
                            icon: "file"
                            kind: "success"
                            enabled: !root.scanning && root.profileName.trim() !== "" && root.customLine.trim() !== ""
                            onClicked: nmapScan.saveProfile(root.payload())
                        }
                        TouchButton {
                            visible: root.profile && !root.profile.builtin
                            text: i18n.pack.nmapDuplicate
                            kind: "neutral"
                            enabled: !root.scanning
                            onClicked: nmapScan.duplicateProfile(root.selected)
                        }
                        TouchButton {
                            visible: root.profile && !root.profile.builtin
                            text: i18n.pack.delete
                            kind: "danger"
                            enabled: !root.scanning
                            onClicked: dialog.ask({
                                title: i18n.pack.delete,
                                kind: "danger",
                                message: i18n.pack.nmapDeleteProfile.replace("{name}", root.profile.title),
                                confirmText: i18n.pack.delete,
                                confirmAction: function() {
                                    nmapScan.deleteProfile(root.selected)
                                    root.selected = ""
                                }
                            })
                        }
                    }
                }

                ColumnLayout {
                    spacing: ui.gap
                    Text {
                        Layout.fillWidth: true
                        text: (nmapScan.started !== "" ? i18n.pack.nmapStartedAt + " " + nmapScan.started + "   " : "")
                              + i18n.pack.nmapElapsed + " " + root.clock(root.seconds)
                              + (root.progress.elapsed ? "   Nmap " + root.progress.elapsed : "")
                        color: ui.text
                        font.pixelSize: ui.fontSmall
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: root.progress.phase !== ""
                        text: i18n.pack.nmapPhase + ": " + root.progress.phase
                              + (root.progress.percent !== "" ? "   " + root.progress.percent + "%" : "")
                              + (root.progress.remaining !== "" ? "   " + root.progress.remaining : "")
                        color: ui.primary
                        font.pixelSize: ui.fontBody
                        font.weight: Font.DemiBold
                        wrapMode: Text.Wrap
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: root.progress.phaseOnly === true
                        text: i18n.pack.nmapPhaseOnly
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }
                    Text {
                        Layout.fillWidth: true
                        text: nmapScan.command
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        font.family: ui.monoFamily
                        wrapMode: Text.Wrap
                    }
                    ConsoleView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        source: nmapScan.console
                        placeholder: i18n.pack.nmapOutputEmpty
                    }
                    TouchButton {
                        text: i18n.pack.nmapRepeat
                        icon: "refresh"
                        kind: "neutral"
                        enabled: !root.scanning && root.plan.ok
                        onClicked: nmapScan.repeat()
                    }
                }

                ColumnLayout {
                    spacing: ui.gap
                    Text {
                        Layout.fillWidth: true
                        visible: nmapScan.partial
                        text: i18n.pack.nmapPartial
                        color: ui.warning
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: root.hosts.length > 0
                        text: root.summary.hosts + "  ·  " + root.summary.up + " " + i18n.pack.nmapStateUp
                              + "  ·  " + root.summary.open + " " + i18n.pack.nmapStateOpen
                        color: ui.text
                        font.pixelSize: ui.fontSmall
                        elide: Text.ElideRight
                    }
                    RowLayout {
                        Field {
                            id: search
                            Layout.fillWidth: true
                            placeholderText: i18n.pack.nmapSearch
                        }
                    }
                    ChoiceChips {
                        Layout.fillWidth: true
                        clearable: true
                        model: [
                            { label: i18n.pack.nmapStateOpen, value: "open" },
                            { label: i18n.pack.nmapStateClosed, value: "closed" },
                            { label: i18n.pack.nmapStateFiltered, value: "filtered" },
                            { label: i18n.pack.nmapStateOpenFiltered, value: "open|filtered" }
                        ]
                        value: root.filterState
                        onActivated: root.filterState = value
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: root.hosts.length > 0
                        text: i18n.pack.nmapResultNote
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        elide: Text.ElideRight
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
                            visible: root.hosts.length === 0
                            text: root.scanning ? i18n.pack.nmapWaiting
                                  : (nmapScan.phase === "ok" ? i18n.pack.nmapNoneUp : i18n.pack.nmapEmpty)
                            color: ui.textMuted
                            font.pixelSize: ui.fontBody
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                        }
                        ScrollPage {
                            anchors.fill: parent
                            anchors.margins: ui.gap
                            visible: root.hosts.length > 0
                            Repeater {
                                model: root.hosts
                                delegate: Column {
                                    id: hostBlock
                                    readonly property var host: modelData
                                    visible: root.hostMatches(host)
                                    Layout.fillWidth: true
                                    width: parent.width
                                    spacing: 2
                                    Rectangle {
                                        width: parent.width
                                        height: ui.touch
                                        color: index % 2 === 0 ? "transparent" : ui.surfaceAlt
                                        Text {
                                            anchors.fill: parent
                                            verticalAlignment: Text.AlignVCenter
                                            text: hostBlock.host.ip
                                                  + (hostBlock.host.names && hostBlock.host.names.length ? "  " + hostBlock.host.names.join(", ") : "")
                                                  + "  " + root.stateLabel(hostBlock.host.state)
                                                  + (hostBlock.host.mac ? "  " + hostBlock.host.mac : "")
                                                  + (hostBlock.host.vendor ? "  " + hostBlock.host.vendor : "")
                                                  + (hostBlock.host.os ? "  " + hostBlock.host.os : "")
                                            color: root.stateColor(hostBlock.host.state)
                                            font.pixelSize: ui.fontSmall
                                            font.family: ui.monoFamily
                                            elide: Text.ElideRight
                                        }
                                    }
                                    Repeater {
                                        model: hostBlock.host.ports || []
                                        delegate: Column {
                                            visible: root.portMatches(modelData, hostBlock.host)
                                            width: parent.width
                                            Text {
                                                width: parent.width
                                                leftPadding: ui.gap
                                                text: modelData.protocol + "/" + modelData.port + "  "
                                                      + root.stateLabel(modelData.state)
                                                      + (modelData.reason ? "  " + modelData.reason : "")
                                                      + (modelData.service ? "  " + modelData.service : "")
                                                      + (modelData.product ? "  " + modelData.product : "")
                                                      + (modelData.version ? "  " + modelData.version : "")
                                                color: root.stateColor(modelData.state)
                                                font.pixelSize: ui.fontSmall
                                                font.family: ui.monoFamily
                                                wrapMode: Text.Wrap
                                            }
                                            Repeater {
                                                model: modelData.scripts || []
                                                delegate: Text {
                                                    width: parent ? parent.width : 0
                                                    leftPadding: ui.gap * 2
                                                    text: modelData.id + "  " + root.kindLabel(modelData.kind)
                                                          + (modelData.note ? "  " + root.pack(modelData.note) : "")
                                                          + "\n" + root.scriptLines(modelData)
                                                    color: modelData.kind === "vulnerable" ? ui.danger
                                                         : modelData.kind === "error" ? ui.warning : ui.text
                                                    font.pixelSize: ui.fontSmall
                                                    wrapMode: Text.Wrap
                                                }
                                            }
                                        }
                                    }
                                    Repeater {
                                        model: hostBlock.host.scripts || []
                                        delegate: Text {
                                            width: parent.width
                                            leftPadding: ui.gap
                                            text: modelData.id + "  " + root.kindLabel(modelData.kind)
                                                  + (modelData.note ? "  " + root.pack(modelData.note) : "")
                                                  + "\n" + root.scriptLines(modelData)
                                            color: modelData.kind === "vulnerable" ? ui.danger : ui.text
                                            font.pixelSize: ui.fontSmall
                                            wrapMode: Text.Wrap
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                ColumnLayout {
                    spacing: ui.gap
                    ScrollPage {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Text {
                            visible: root.history.length === 0
                            text: i18n.pack.nmapHistoryEmpty
                            color: ui.textMuted
                            font.pixelSize: ui.fontBody
                        }
                        Repeater {
                            model: root.history
                            delegate: Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: column.implicitHeight + ui.gap
                                radius: ui.radius
                                color: ui.surfaceAlt
                                border.width: 1
                                border.color: root.compareA === modelData.id ? ui.primary : ui.border
                                Column {
                                    id: column
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.margins: ui.gap
                                    spacing: 2
                                    Text {
                                        width: parent.width
                                        text: (modelData.simulated ? i18n.pack.nmapSimulated + "  " : "")
                                              + root.phaseText(modelData.status) + "  " + (modelData.started || "")
                                        color: root.phaseTone(modelData.status)
                                        font.pixelSize: ui.fontSmall
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        width: parent.width
                                        text: modelData.targets || modelData.command
                                        color: ui.text
                                        font.pixelSize: ui.fontSmall
                                        font.family: ui.monoFamily
                                        elide: Text.ElideRight
                                    }
                                    Row {
                                        spacing: ui.gap
                                        TouchButton {
                                            text: i18n.pack.nmapOpen
                                            kind: "neutral"
                                            enabled: !root.scanning
                                            onClicked: nmapScan.openRun(modelData.id)
                                        }
                                        TouchButton {
                                            text: i18n.pack.nmapReuse
                                            kind: "neutral"
                                            enabled: !root.scanning
                                            onClicked: root.reuse(modelData.command)
                                        }
                                        TouchButton {
                                            text: root.compareA === "" || root.compareA === modelData.id
                                                  ? i18n.pack.nmapCompare : i18n.pack.nmapCompareWith
                                            kind: "neutral"
                                            enabled: !root.scanning
                                            onClicked: {
                                                if (root.compareA === "" || root.compareA === modelData.id)
                                                    root.compareA = modelData.id
                                                else {
                                                    nmapScan.compareRuns(root.compareA, modelData.id)
                                                    root.compareA = ""
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Column {
                        visible: root.compared.ready === true
                        width: parent.width
                        spacing: 2
                        Text { width: parent.width; wrapMode: Text.Wrap; color: ui.textMuted; font.pixelSize: ui.fontSmall; text: root.compared.note || "" }
                        Text { width: parent.width; wrapMode: Text.Wrap; color: ui.text; font.pixelSize: ui.fontSmall; visible: (root.compared.newHosts || []).length > 0; text: i18n.pack.nmapNewHosts + ": " + (root.compared.newHosts || []).join(", ") }
                        Text { width: parent.width; wrapMode: Text.Wrap; color: ui.text; font.pixelSize: ui.fontSmall; visible: (root.compared.goneHosts || []).length > 0; text: i18n.pack.nmapGoneHosts + ": " + (root.compared.goneHosts || []).join(", ") }
                        Text { width: parent.width; wrapMode: Text.Wrap; color: ui.text; font.pixelSize: ui.fontSmall; visible: (root.compared.newPorts || []).length > 0; text: i18n.pack.nmapNewPorts + ": " + (root.compared.newPorts || []).join(", ") }
                        Text { width: parent.width; wrapMode: Text.Wrap; color: ui.text; font.pixelSize: ui.fontSmall; visible: (root.compared.gonePorts || []).length > 0; text: i18n.pack.nmapGonePorts + ": " + (root.compared.gonePorts || []).join(", ") }
                        Text { width: parent.width; wrapMode: Text.Wrap; color: ui.text; font.pixelSize: ui.fontSmall; visible: (root.compared.changes || []).length > 0; text: i18n.pack.nmapServiceChanges + ": " + (root.compared.changes || []).join(" · ") }
                        Text {
                            width: parent.width
                            wrapMode: Text.Wrap
                            color: ui.textMuted
                            font.pixelSize: ui.fontSmall
                            visible: (root.compared.newHosts || []).length + (root.compared.goneHosts || []).length
                                     + (root.compared.newPorts || []).length + (root.compared.gonePorts || []).length
                                     + (root.compared.changes || []).length === 0
                            text: i18n.pack.nmapNoChanges
                        }
                    }
                }
            }
        }
    }

    function scriptLines(item) {
        var lines = item.lines || []
        if (!lines.length)
            return item.output || ""
        var text = ""
        for (var i = 0; i < lines.length; ++i)
            text += (i ? "\n" : "") + root.pack(lines[i].label) + ": " + root.lineValue(lines[i])
        return text
    }

    Component.onCompleted: nmapScan.refresh()
}
