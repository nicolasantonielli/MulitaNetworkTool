import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

// Lista de servidores de prueba. Al tocar uno se abre su panel: ajustes y registro.
Item {
    id: root

    readonly property var catalog: {
        try { return JSON.parse(servers.catalogJson) }
        catch (e) { return [] }
    }
    readonly property var states: {
        try { return JSON.parse(servers.statesJson) }
        catch (e) { return ({}) }
    }
    readonly property var rows: {
        try { return JSON.parse(servers.rowsJson) }
        catch (e) { return [] }
    }

    property string selected: ""
    // Ajustes editados por servidor: { iperf: { port: "5202" }, ... }
    property var store: ({})

    readonly property var server: {
        for (var i = 0; i < catalog.length; ++i) {
            if (catalog[i].id === selected)
                return catalog[i]
        }
        return null
    }
    readonly property string state: server ? (states[server.id] || "idle") : "idle"
    readonly property bool busy: state !== "idle"

    function stateOf(id) {
        return states[id] || "idle"
    }

    function open(id) {
        network.refresh()
        selected = id
        servers.select(id)
        tabs.currentIndex = 0
        logFile.text = id + "-registro"
    }

    function close() {
        selected = ""
        servers.select("")
    }

    function interfaceRows() {
        var rows = network.interfaces
        var found = []
        for (var i = 0; i < rows.length; ++i) {
            var row = rows[i]
            var name = typeof row === "string" ? row : row.value
            var address = typeof row === "string" ? "" : (row.address || "")
            if (name !== "lo" && address !== "")
                found.push({ label: name, value: name, linked: row.linked === true, address: address })
        }
        return found
    }

    function defaultInterface() {
        var rows = interfaceRows()
        for (var i = 0; i < rows.length; ++i) {
            if (rows[i].value === "eth0")
                return "eth0"
        }
        return rows.length ? rows[0].value : ""
    }

    function addressOf(name) {
        var rows = interfaceRows()
        for (var i = 0; i < rows.length; ++i) {
            if (rows[i].value === name)
                return rows[i].address
        }
        return ""
    }

    function valueByKey(key) {
        if (!server)
            return ""
        var saved = store[server.id]
        if (saved && saved[key] !== undefined)
            return saved[key]
        for (var i = 0; i < server.fields.length; ++i) {
            var field = server.fields[i]
            if (field.key !== key)
                continue
            return field.kind === "interface" ? defaultInterface() : field.default
        }
        return ""
    }

    function setValue(key, value) {
        var next = {}
        for (var other in store)
            next[other] = store[other]
        var mine = {}
        var old = store[server.id] || {}
        for (var name in old)
            mine[name] = old[name]
        mine[key] = value
        next[server.id] = mine
        store = next
    }

    function shown(field) {
        return !field.when || field.when["in"].indexOf(valueByKey(field.when.key)) >= 0
    }

    function optionsOf(field) {
        var list = []
        if (field.kind === "interface" || field.kind === "interface_any") {
            if (field.kind === "interface_any")
                list.push({ label: i18n.pack.serverAll, value: "" })
            return list.concat(interfaceRows())
        }
        for (var i = 0; i < field.options.length; ++i) {
            var option = field.options[i]
            var text = i18n.pack[option.label]
            list.push({ label: text !== undefined ? text : option.label, value: option.value })
        }
        return list
    }

    function isChoice(field) {
        return field.kind !== "text"
    }

    function payload() {
        var values = {}
        for (var i = 0; i < server.fields.length; ++i)
            values[server.fields[i].key] = valueByKey(server.fields[i].key)
        return JSON.stringify(values)
    }

    function columnWidth(share) {
        return Math.max(1, logTable.viewportWidth * share / 100)
    }

    StackLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        currentIndex: root.server ? 1 : 0

        // Lista de servidores
        GridLayout {
            id: list
            columns: 2
            rowSpacing: ui.gap
            columnSpacing: ui.gap

            Repeater {
                model: root.catalog

                delegate: Rectangle {
                    id: card

                    readonly property bool allowsTextCopy: false
                    readonly property bool active: root.stateOf(modelData.id) !== "idle"

                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 1
                    Layout.columnSpan: index === root.catalog.length - 1 && root.catalog.length % 2 === 1 ? 2 : 1
                    radius: ui.radius * 1.6
                    color: area.pressed ? ui.surfaceHigh : ui.surface
                    border.width: active ? 2 : 1
                    border.color: active ? ui.success : ui.border
                    scale: area.pressed ? 0.98 : 1

                    Behavior on scale { NumberAnimation { duration: 90 } }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: ui.gap
                        spacing: ui.gap

                        Rectangle {
                            Layout.preferredWidth: Math.round(ui.touch * 0.85)
                            Layout.preferredHeight: Layout.preferredWidth
                            radius: ui.radius * 1.2
                            color: Qt.rgba(ui.primary.r, ui.primary.g, ui.primary.b, 0.15)

                            Icon {
                                anchors.centerIn: parent
                                name: modelData.icon
                                color: ui.primary
                                size: Math.round(ui.icon * 0.95)
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0

                            Text {
                                Layout.fillWidth: true
                                text: i18n.pack[modelData.title]
                                color: ui.text
                                font.pixelSize: ui.fontTitle
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                text: i18n.pack[modelData.subtitle]
                                color: ui.textMuted
                                font.pixelSize: ui.fontSmall
                                elide: Text.ElideRight
                            }
                        }
                        StatusPill {
                            visible: card.active
                            text: root.stateOf(modelData.id) === "starting"
                                  ? i18n.pack.serverStarting : i18n.pack.running
                            tone: ui.success
                            pulsing: card.active
                        }
                    }

                    TouchArea {
                        id: area
                        onTapped: root.open(modelData.id)
                    }
                }
            }
        }

        // Panel de un servidor
        ColumnLayout {
            spacing: ui.gap

            RowLayout {
                spacing: ui.gap

                IconButton {
                    icon: "back"
                    onClicked: root.close()
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0

                    Text {
                        Layout.fillWidth: true
                        text: root.server ? i18n.pack[root.server.title] : ""
                        color: ui.text
                        font.pixelSize: ui.fontTitle
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: root.server ? i18n.pack[root.server.subtitle] : ""
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        elide: Text.ElideRight
                    }
                }
                StatusPill {
                    text: root.state === "starting" ? i18n.pack.serverStarting
                          : (root.state === "running" ? i18n.pack.running : i18n.pack.serverStopped)
                    tone: root.busy ? ui.success : ui.textMuted
                    pulsing: root.busy
                }
                TouchButton {
                    Layout.preferredWidth: ui.mm * 34
                    text: root.busy ? i18n.pack.stop : i18n.pack.start
                    icon: root.busy ? "stop" : "play"
                    kind: root.busy ? "danger" : "success"
                    enabled: root.state !== "starting"
                    onClicked: root.busy ? servers.stop(root.selected)
                                         : servers.start(root.selected, root.payload())
                }
            }

            PageTabs {
                id: tabs
                objectName: "serverTabs"
                Layout.fillWidth: true
                tabs: [i18n.pack.serverSettings, i18n.pack.serverLog]
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: tabs.currentIndex

                // Ajustes
                ScrollPage {
                    id: settingsPage
                    spacing: ui.gap

                    Text {
                        Layout.fillWidth: true
                        text: root.server ? i18n.pack[root.server.hint] : ""
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        wrapMode: Text.Wrap
                    }

                    Repeater {
                        model: root.server ? root.server.fields : []

                        delegate: ColumnLayout {
                            id: fieldRow

                            readonly property var field: modelData
                            readonly property bool choice: root.isChoice(field)
                            readonly property string address: field.kind === "text"
                                                              ? "" : root.addressOf(root.valueByKey(field.key))

                            Layout.fillWidth: true
                            visible: root.shown(field)
                            spacing: Math.round(ui.gap * 0.4)

                            Text {
                                Layout.fillWidth: true
                                text: i18n.pack[fieldRow.field.label]
                                      + (fieldRow.address !== "" ? "  ·  " + fieldRow.address : "")
                                color: ui.text
                                font.pixelSize: ui.fontBody
                                elide: Text.ElideRight
                            }
                            ChoiceChips {
                                visible: fieldRow.choice
                                Layout.fillWidth: true
                                model: root.optionsOf(fieldRow.field)
                                value: root.valueByKey(fieldRow.field.key)
                                enabled: !root.busy
                                onActivated: root.setValue(fieldRow.field.key, value)
                            }
                            Field {
                                visible: !fieldRow.choice
                                Layout.fillWidth: true
                                text: root.valueByKey(fieldRow.field.key)
                                enabled: !root.busy
                                placeholderText: fieldRow.field.placeholder !== ""
                                                 ? i18n.pack[fieldRow.field.placeholder] : ""
                                onTextEdited: root.setValue(fieldRow.field.key, text)
                            }
                        }
                    }
                }

                // Registro
                ColumnLayout {
                    spacing: ui.gap

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
                            text: root.busy ? i18n.pack.serverWaiting : i18n.pack.serverEmpty
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
                                id: logTable
                                spacing: 1

                                Row {
                                    Layout.fillWidth: true
                                    Repeater {
                                        model: root.server ? root.server.columns : []
                                        delegate: Text {
                                            width: root.columnWidth(modelData.share)
                                            text: i18n.pack[modelData.title]
                                            color: ui.textMuted
                                            font.pixelSize: ui.fontSmall
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }
                                    }
                                }

                                Repeater {
                                    model: root.rows.length
                                    delegate: Rectangle {
                                        id: logRow
                                        readonly property var entry: root.rows[index] || ({})
                                        Layout.fillWidth: true
                                        implicitHeight: Math.round(ui.fontSmall * 2.15)
                                        color: index % 2 === 0 ? "transparent" : ui.surfaceAlt
                                        Row {
                                            anchors.fill: parent
                                            Repeater {
                                                model: root.server ? root.server.columns : []
                                                delegate: CopyableCell {
                                                    width: root.columnWidth(modelData.share)
                                                    height: logRow.height
                                                    text: logRow.entry[modelData.key] === undefined
                                                          ? "" : String(logRow.entry[modelData.key])
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

                    RowLayout {
                        spacing: ui.gap

                        Field {
                            id: logFile
                            Layout.fillWidth: true
                            placeholderText: i18n.pack.fileName
                        }
                        Text {
                            text: ".csv"
                            color: ui.textMuted
                            font.pixelSize: ui.fontBody
                        }
                        TouchButton {
                            text: i18n.pack.clear
                            kind: "neutral"
                            enabled: root.rows.length > 0
                            onClicked: servers.clear(root.selected)
                        }
                        TouchButton {
                            text: i18n.pack.save
                            icon: "file"
                            kind: "success"
                            enabled: root.rows.length > 0
                            onClicked: servers.save(root.selected, logFile.text)
                        }
                    }
                }
            }
        }
    }
}
