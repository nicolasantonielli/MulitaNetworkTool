import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

ScrollPage {
    signal openTouchTest()
    Card {
        Layout.fillWidth: true
        title: i18n.pack.rotation
        titleIcon: "display"
        ChoiceChips {
            Layout.fillWidth: true
            model: [
                { label: "0°", value: "0" },
                { label: "90°", value: "90" },
                { label: "180°", value: "180" },
                { label: "270°", value: "270" }
            ]
            value: String(settings.rotation)
            onActivated: settings.setRotation(Number(value))
        }
        Text {
            Layout.fillWidth: true
            text: i18n.pack.rotationHint
            color: ui.textMuted
            font.pixelSize: ui.fontSmall
            wrapMode: Text.Wrap
        }
    }


    Card {
        Layout.fillWidth: true
        title: i18n.pack.displaySize
        titleIcon: "display"

        Text {
            Layout.fillWidth: true
            text: i18n.pack.scaleHint
            color: ui.textMuted
            font.pixelSize: ui.fontBody
            wrapMode: Text.Wrap
        }
        LabeledSlider {
            Layout.fillWidth: true
            label: i18n.pack.scale
            from: 0.5
            to: 1.25
            stepSize: 0.05
            initial: settings.uiScale
            valueText: Math.round(value * 100) + " %"
            onValueChanged: settings.setScale(value)
        }
    }
    Card {
        Layout.fillWidth: true
        title: i18n.pack.brightness
        titleIcon: "display"

        Text {
            Layout.fillWidth: true
            text: settings.brightnessReady ? i18n.pack.brightnessHint : i18n.pack.noBacklight
            color: ui.textMuted
            font.pixelSize: ui.fontBody
            wrapMode: Text.Wrap
        }
        LabeledSlider {
            Layout.fillWidth: true
            enabled: settings.brightnessReady
            label: i18n.pack.brightness
            from: 1
            to: 100
            stepSize: 1
            initial: settings.brightness
            valueText: Math.round(value) + " %"
            onValueChanged: settings.setBrightness(value)
        }
    }

    Card {
        Layout.fillWidth: true
        title: i18n.pack.touchTest
        titleIcon: "display"

        TouchButton {
            Layout.fillWidth: true
            text: i18n.pack.start
            icon: "play"
            kind: "neutral"
            onClicked: openTouchTest()
        }
    }
}
