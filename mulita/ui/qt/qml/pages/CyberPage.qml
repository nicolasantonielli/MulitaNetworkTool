import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../components"

// Plantilla comun de las herramientas de ciberseguridad: encabezado, objetivo,
// tabla de resultados y acciones. Cada herramienta reemplaza el contenido real.
Item {
    id: root

    property var tool: ({})

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ui.padding
        spacing: ui.gap

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: heading.implicitHeight + ui.padding * 2
            radius: ui.radius * 1.4
            color: ui.surface
            border.width: 1
            border.color: ui.border

            RowLayout {
                id: heading
                anchors.fill: parent
                anchors.margins: ui.padding
                spacing: ui.gap

                Rectangle {
                    Layout.preferredWidth: Math.round(ui.touch * 1.05)
                    Layout.preferredHeight: Layout.preferredWidth
                    radius: ui.radius * 1.3
                    color: Qt.rgba(ui.primary.r, ui.primary.g, ui.primary.b, 0.15)

                    Icon {
                        anchors.centerIn: parent
                        name: root.tool.icon || ""
                        color: ui.primary
                        size: Math.round(ui.icon * 1.1)
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0

                    Text {
                        Layout.fillWidth: true
                        text: root.tool.title || ""
                        color: ui.text
                        font.pixelSize: ui.fontTitle
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: root.tool.subtitle || ""
                        color: ui.textMuted
                        font.pixelSize: ui.fontSmall
                        elide: Text.ElideRight
                    }
                }
                StatusPill {
                    text: i18n.pack.cyberSoon
                    tone: ui.warning
                }
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
                text: i18n.pack.cyberEmpty
                color: ui.textMuted
                font.pixelSize: ui.fontBody
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
            }
        }

        RowLayout {
            spacing: ui.gap

            Field {
                Layout.fillWidth: true
                placeholderText: i18n.pack.cyberTarget
                enabled: false
            }
            TouchButton {
                text: i18n.pack.clear
                kind: "neutral"
                enabled: false
            }
            TouchButton {
                text: i18n.pack.save
                icon: "file"
                kind: "success"
                enabled: false
            }
            TouchButton {
                text: i18n.pack.start
                icon: "play"
                kind: "success"
                enabled: false
            }
        }
    }
}
