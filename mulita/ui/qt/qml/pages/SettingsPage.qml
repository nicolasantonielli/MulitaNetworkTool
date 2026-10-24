import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15
import "../components"

Item {
    id: root

    signal goHome()

    // Borrador de pantalla: se edita libremente y se aplica con confirmacion.
    property int draftWidth: settings.width
    property int draftHeight: settings.height
    property real draftDiagonal: settings.diagonal
    property bool draftFullscreen: settings.fullscreen
    property real draftScale: settings.uiScale
    readonly property real draftPpi: Math.sqrt(draftWidth * draftWidth + draftHeight * draftHeight) / draftDiagonal
    readonly property real draftPxPerMm: draftPpi / 25.4 * draftScale
    readonly property bool draftChanged: draftWidth !== settings.width || draftHeight !== settings.height
                                         || Math.abs(draftDiagonal - settings.diagonal) > 0.001
                                         || draftFullscreen !== settings.fullscreen
                                         || Math.abs(draftScale - settings.uiScale) > 0.001

    function loadDraft() {
        draftWidth = settings.width
        draftHeight = settings.height
        draftDiagonal = settings.diagonal
        draftFullscreen = settings.fullscreen
        draftScale = settings.uiScale
    }

    function applyDraft() {
        var previous = [settings.width, settings.height, settings.diagonal, settings.fullscreen, settings.uiScale]
        if (!settings.applyDisplay(draftWidth, draftHeight, draftDiagonal, draftFullscreen, draftScale))
            return
        dialog.ask({
            title: "¿Mantener esta pantalla?",
            message: "La interfaz ya usa la nueva configuración.",
            kind: "success",
            confirmText: "Mantener",
            cancelText: "Revertir",
            countdown: 15,
            cancelAction: function () {
                settings.applyDisplay(previous[0], previous[1], previous[2], previous[3], previous[4])
                root.loadDraft()
            }
        })
    }

    ConfirmDialog { id: dialog }

    RowLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        SideNav {
            id: nav
            Layout.preferredWidth: Math.round(root.width * 0.27)
            Layout.fillHeight: true
            items: [
                { label: "General", icon: "theme" },
                { label: "Pantalla", icon: "display" },
                { label: "Wi-Fi", icon: "wifi" },
                { label: "Ethernet interna", icon: "ethernet" },
                { label: "Ethernet externa", icon: "ethernet" },
                { label: "Mantenimiento", icon: "wrench" }
            ]
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: nav.currentIndex

            // General
            ScrollPage {
                Card {
                    Layout.fillWidth: true
                    title: "Tema"
                    titleIcon: "theme"

                    ChoiceChips {
                        Layout.fillWidth: true
                        model: settings.themes
                        value: settings.theme
                        onActivated: settings.setTheme(value)
                    }
                }
                Card {
                    Layout.fillWidth: true
                    title: "Acerca de"
                    titleIcon: "info"

                    Text {
                        text: "Mulita Network Tool"
                        color: ui.text
                        font.pixelSize: ui.fontTitle
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: "Versión " + system.version
                        color: ui.textMuted
                        font.pixelSize: ui.fontBody
                    }
                }
            }

            // Pantalla
            ScrollPage {
                Card {
                    Layout.fillWidth: true
                    title: "Paneles comunes"
                    titleIcon: "display"

                    ChoiceChips {
                        Layout.fillWidth: true
                        model: settings.presets.map(function (preset, index) { return { label: preset.label, value: String(index) } })
                        value: {
                            for (var i = 0; i < settings.presets.length; ++i) {
                                var preset = settings.presets[i]
                                if (preset.width === root.draftWidth && preset.height === root.draftHeight
                                        && Math.abs(preset.diagonal - root.draftDiagonal) < 0.001)
                                    return String(i)
                            }
                            return ""
                        }
                        onActivated: {
                            var preset = settings.presets[Number(value)]
                            root.draftWidth = preset.width
                            root.draftHeight = preset.height
                            root.draftDiagonal = preset.diagonal
                        }
                    }
                }

                Card {
                    Layout.fillWidth: true
                    title: "Medidas del panel"
                    titleIcon: "settings"

                    Stepper {
                        Layout.fillWidth: true
                        label: "Ancho"
                        suffix: " px"
                        from: 320; to: 3840; step: 1
                        value: root.draftWidth
                        onEdited: root.draftWidth = newValue
                    }
                    Stepper {
                        Layout.fillWidth: true
                        label: "Alto"
                        suffix: " px"
                        from: 240; to: 2160; step: 1
                        value: root.draftHeight
                        onEdited: root.draftHeight = newValue
                    }
                    Stepper {
                        Layout.fillWidth: true
                        label: "Diagonal"
                        suffix: " \""
                        from: 3; to: 32; step: 0.1; decimals: 1
                        value: root.draftDiagonal
                        onEdited: root.draftDiagonal = newValue
                    }
                    LabeledSlider {
                        Layout.fillWidth: true
                        label: "Escala de la interfaz"
                        from: 0.75; to: 1.5; stepSize: 0.05
                        initial: root.draftScale
                        valueText: Math.round(value * 100) + " %"
                        onValueChanged: root.draftScale = Math.round(value * 100) / 100
                    }
                    RowLayout {
                        Text {
                            Layout.fillWidth: true
                            text: "Pantalla completa"
                            color: ui.text
                            font.pixelSize: ui.fontBody
                        }
                        Switch {
                            implicitHeight: ui.touch
                            implicitWidth: Math.round(ui.touch * 1.7)
                            checked: root.draftFullscreen
                            onToggled: root.draftFullscreen = checked
                        }
                    }
                    TouchButton {
                        text: "Usar resolución detectada (" + Screen.width + "×" + Screen.height + ")"
                        icon: "display"
                        kind: "neutral"
                        onClicked: {
                            root.draftWidth = Screen.width
                            root.draftHeight = Screen.height
                        }
                    }
                }

                Card {
                    Layout.fillWidth: true
                    title: "Resultado"
                    titleIcon: "info"

                    Text {
                        Layout.fillWidth: true
                        text: root.draftPpi.toFixed(0) + " ppi · 1 mm = " + root.draftPxPerMm.toFixed(1)
                              + " px · botón táctil = " + Math.round(9 * root.draftPxPerMm) + " px"
                        color: ui.text
                        font.pixelSize: ui.fontBody
                        wrapMode: Text.Wrap
                    }
                    RowLayout {
                        spacing: ui.gap

                        TouchButton {
                            Layout.fillWidth: true
                            text: "Descartar"
                            kind: "neutral"
                            enabled: root.draftChanged
                            onClicked: root.loadDraft()
                        }
                        TouchButton {
                            Layout.fillWidth: true
                            text: "Aplicar"
                            icon: "check"
                            kind: "success"
                            enabled: root.draftChanged
                            onClicked: root.applyDraft()
                        }
                    }
                }
            }

            // Wi-Fi, Ethernet interna y Ethernet externa
            PendingSection { title: "Wi-Fi"; icon: "wifi"; onGoHome: root.goHome() }
            PendingSection { title: "Ethernet interna"; icon: "ethernet"; onGoHome: root.goHome() }
            PendingSection { title: "Ethernet externa"; icon: "ethernet"; onGoHome: root.goHome() }

            // Mantenimiento
            ScrollPage {
                Card {
                    Layout.fillWidth: true
                    title: "Sistema"
                    titleIcon: "info"

                    RowLayout {
                        Text {
                            Layout.fillWidth: true
                            text: "Versión " + system.version
                            color: ui.text
                            font.pixelSize: ui.fontTitle
                            font.weight: Font.DemiBold
                        }
                        BusyIndicator {
                            running: system.busy
                            visible: running
                            Layout.preferredWidth: ui.touch
                            Layout.preferredHeight: ui.touch
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    rowSpacing: ui.gap
                    columnSpacing: ui.gap

                    TouchButton {
                        Layout.fillWidth: true
                        text: "Actualizar"
                        icon: "download"
                        kind: "success"
                        enabled: !system.busy
                        onClicked: dialog.ask({ title: "Actualizar Mulita", kind: "success",
                                                message: "Se descarga la última versión. Reinicie la aplicación para aplicarla.",
                                                confirmText: "Actualizar", confirmAction: system.update })
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: "Reiniciar app"
                        icon: "restart"
                        kind: "warning"
                        enabled: !system.busy
                        onClicked: dialog.ask({ title: "Reiniciar la aplicación", kind: "warning",
                                                message: "Se detienen las capturas y pruebas en curso.",
                                                confirmText: "Reiniciar", confirmAction: system.reset })
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: "Cerrar app"
                        icon: "logout"
                        kind: "neutral"
                        onClicked: dialog.ask({ title: "Cerrar la aplicación", kind: "danger",
                                                message: "Se detienen las capturas y pruebas en curso.",
                                                confirmText: "Cerrar", confirmAction: system.quit })
                    }
                    TouchButton {
                        Layout.fillWidth: true
                        text: "Apagar equipo"
                        icon: "power"
                        kind: "danger"
                        onClicked: dialog.ask({ title: "Apagar el equipo", kind: "danger",
                                                message: "El equipo se apaga por completo.",
                                                confirmText: "Apagar", confirmAction: system.poweroff })
                    }
                }
            }
        }
    }
}
