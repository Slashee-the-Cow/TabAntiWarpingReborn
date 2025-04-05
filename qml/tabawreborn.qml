//-----------------------------------------------------------------------------
// Tab+ Anti-Warping Copyright (c) 2022 5@xes
// Reborn version copyright Slashee the Cow 2025-
// proterties values
//   "TabSize"      : Tab Size in mm
//   "XYDistance"   : X/Y distance from model in mm
//   "AsDish"       : Use dish shape
//   "LayerCount"   : Number of layers for tab
//   "FeedbackText" : Message to show user (in place of toast)
//   "FeedbackTimer": Timeout for feedback message
//
//-----------------------------------------------------------------------------

import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Layouts 6.0

import UM 1.6 as UM
import Cura 1.1 as Cura

Item {
    id: tabRebornPanel

    function getCuraVersion(){
        if(CuraApplication.version){
            return CuraApplication.version();
        } else {
            return UM.Application.version;
        }
    }

    function compareVersions(version1, version2) {
        const v1 = String(version1).split(".");
        const v2 = String(version2).split(".");

        for (let i = 0; i < Math.max(v1.length, v2.length); i++) {
            const num1 = parseInt(v1[i] || 0); // Handle missing components
            const num2 = parseInt(v2[i] || 0);

            if (num1 < num2) return -1;
            if (num1 > num2) return 1;
        }
        return 0; // Versions are equal
    }

    function isVersion57OrGreater(){
        //let version = CuraApplication ? CuraApplication.version() : (UM.Application ? UM.Application.version : null);
        let version = getCuraVersion()
        if(version){
            return compareVersions(version, "5.7.0") >= 0;
        } else {
            return False;
        }        
    }
    

    function getProperty(propertyName){
        if(isVersion57OrGreater()){
            return UM.Controller.properties.getValue(propertyName);
        } else {
            return UM.ActiveTool.properties.getValue(propertyName);
        }
    }

    function setProperty(propertyName, value){
        if(isVersion57OrGreater()){
            return UM.Controller.setProperty(propertyName, value);
        } else {
            return UM.ActiveTool.setProperty(propertyName, value);
        }
    }

    function triggerAction(action){
        if(isVersion57OrGreater()){
            return UM.Controller.triggerAction(action);
        } else {
            return UM.ActiveTool.triggerAction(action);
        }
    }

    function triggerActionWithData(action, data){
        if(isVersion57OrGreater()){
            return UM.Controller.triggerActionWithData(action, data);
        } else {
            return UM.ActiveTool.triggerActionWithData(action, data);
        }
    }

    function validateInt(test, min_value = -Infinity, max_value = Infinity){
        if (test === ""){return false;}
        let intTest = parseInt(test);
        if (isNaN(intTest)){return false;}
        if (intTest < min_value){return false;}
        if (intTest > max_value){return false;}
        return true;
    }

    function validateFloat(test, min_value = -Infinity, max_value = Infinity){
        if (test === ""){return false;}
        test = test.replace(",","."); // Use decimal separator computer understands
        let floatTest = parseFloat(test);
        if (isNaN(floatTest)){return false;}
        if (floatTest < min_value){return false;}
        if (floatTest > max_value){return false;}
        return true;
    }

    property var default_field_background: UM.Theme.getColor("detail_background")
    property var error_field_background: UM.Theme.getColor("setting_validation_error_background")

    function getBackgroundColour(valid){
        return valid ? default_field_background : error_field_background
    }

    function validateInputs(){
        let message = "";
        let tab_size_valid = true;
        let xy_distance_valid = true;
        let layer_count_valid = true;

        if (!validateFloat(tabSize, 0.1)){
            tab_size_valid = false;
            message += catalog.i18nc("tab_size_invalid", "Tab size must be at least 0.1mm\n");
        }
        if (!validateFloat(xyDistance, 0.01, 1)){
            xy_distance_valid = false;
            message += catalog.i18nc("xy_distance_invalid", "X/Y Distance must be between 0.01 and 1mm\n");
        }
        if (!validateInt(layerCount, 1, 100)){
            layer_count_valid = false;
            message += catalog.i18nc("layer_count_invalid", "Layer count must be between 1 and 100\n")
        }

        if (tab_size_valid && xy_distance_valid && layer_count_valid){
            setProperty("TabSize", parseFloat(tabSize))
            setProperty("XYDistance", parseFloat(xyDistance))
            setProperty("LayerCount", parseInt(layerCount))
            inputsValid = true
            setProperty("InputsValid", inputsValid)
        } else {
            inputsValid = false
            setProperty("InputsValid", inputsValid)
        }
        errorMessage =  message
        sizeTextField.background.color = getBackgroundColour(tab_size_valid)
        xyDistanceTextField.background.color = getBackgroundColour(xy_distance_valid)
        layerCountTextField.background.color = getBackgroundColour(layer_count_valid)
    }

    width: childrenRect.width
    height: childrenRect.height
    UM.I18nCatalog { id: catalog; name: "tabawreborn"}

    property string tabSize: ""
    property string xyDistance: ""
    property string layerCount: ""
    property bool asDishProp: false
    
    property bool inputsValid: false

    property string feedbackMessage: ""
    property int feedbackTimeout: 0

    property int localwidth:UM.Theme.getSize("setting_control").width

    property string errorMessage: ""

    property int textFieldMinWidth: 75

    Component.onCompleted: {
        tabSize = getProperty("TabSize")
        xyDistance = getProperty("XYDistance")
        layerCount = getProperty("LayerCount")
        asDishProp = getProperty("AsDish")
        Qt.callLater(validateInputs)
        if(isVersion57OrGreater()) {
            UM.Controller.propertiesChanged.connect(handlePropertiesChanged);
        } else {
            UM.ActiveTool.propertiesChanged.connect(handlePropertiesChanged);
        }
        updateFeedback(); //Initialize the view with the current value.
        updateTimeout(); //Initialize the view with the current value.
    }

    function handlePropertiesChanged() {
        let feedbackMessageChange = isVersion57OrGreater() ? UM.Controller.properties.getValue("FeedbackMessage") : UM.ActiveTool.properties.getValue("FeedbackMessage");
        let feedbackTimeoutChange = isVersion57OrGreater() ? UM.Controller.properties.getValue("FeedbackTimeout") : UM.ActiveTool.properties.getValue("FeedbackTimeout");
        let functionRunMessage = "handlePropertiesChanged called"
        if (feedbackMessage !== "") {
            Qt.callLater(function() { updateFeedback(feedbackMessage); }); // Delay message display
        }
        if (feedbackTimeout !== 0) {
            Qt.callLater(function() { updateTimeout(feedbackTimeout); }); // Delay timeout reset
        }
    }

    function updateFeedback() {
        feedbackLabel.text = getProperty("FeedbackMessage");
        setProperty("LogMessage", "updateFeedback running with getProperty('FeedbackMessage') " + getProperty("FeedbackMessage"))
        setProperty("FeedbackMessage", "")
        setProperty("LogMessage", "updateFeedback set FeedbackMessage to " + getProperty("FeedbackMessage"))
        if (feedbackTimeout > 0) {
            feedbackTimer.interval = feedbackTimeout;
            feedbackTimer.restart();
        }
    }

    function updateTimeout() {
        feedbackTimeout = getProperty("FeedbackTimeout")
        setProperty("LogMessage", "updateTimeout running with getProperty('FeedbackTimeout') " + getProperty("FeedbackTimeout"))
        setProperty("FeedbackTimeout", 0)
        setProperty("LogMessage", "updateTimeout set FeedbackTimeout to " + getProperty("FeedbackTimeout"))
        if (feedbackTimeout > 0 && feedbackLabel.text !== "") {
            feedbackTimer.interval = feedbackTimeout;
            feedbackTimer.restart();
        }
    }

    RowLayout{
        id: layoutBase
        anchors.left: parent.left
        anchors.top: parent.top

        ColumnLayout {
            id: mainColumn
            //anchors.left: parent.left
            //anchors.top: parent.top
            UM.Label {
                Layout.fillWidth: true
                Layout.maximumWidth: 175
                visible: tabRebornPanel.errorMessage != ""
                id: error_text
                text: tabRebornPanel.errorMessage
                color: UM.Theme.getColor("error")
                wrapMode: TextInput.Wrap
            }
        
            GridLayout {
                id: controlLayout

                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop

                columns: 2
                columnSpacing: UM.Theme.getSize("default_margin").width
                rowSpacing: UM.Theme.getSize("default_margin").height

                UM.Label {
                    text: catalog.i18nc("@label", "Size")
                }

                UM.TextFieldWithUnit {
                    id: sizeTextField
                    Layout.minimumWidth: textFieldMinWidth
                    height: UM.Theme.getSize("setting_control").height
                    unit: "mm"
                    text: tabSize
                    validator: DoubleValidator {
                        decimals: 2
                        bottom: 0.1
                    }

                    onTextChanged: {
                        tabSize = text
                        Qt.callLater(validateInputs)
                    }
                }
                
                UM.Label {
                    text: catalog.i18nc("@label", "X/Y Distance")
                }

                UM.TextFieldWithUnit {
                    id: xyDistanceTextField
                    Layout.minimumWidth: textFieldMinWidth
                    height: UM.Theme.getSize("setting_control").height
                    unit: "mm"
                    text: xyDistance
                    validator: DoubleValidator {
                        top: 1
                        bottom: 0.01
                        decimals: 2
                    }
                    onTextChanged: {
                        xyDistance = text
                        Qt.callLater(validateInputs)
                    }
                }

                UM.Label {
                    text: catalog.i18nc("@label", "Number of layers")
                }

                UM.TextFieldWithUnit{
                    id: layerCountTextField
                    Layout.minimumWidth: textFieldMinWidth
                    height: UM.Theme.getSize("setting_control").height
                    text: layerCount
                    validator: IntValidator {
                        bottom: 1
                        top: 100
                    }
                    onTextChanged: {
                        layerCount = text
                        Qt.callLater(validateInputs)
                    }
                }

                UM.CheckBox {
                    id: asDishCheckbox
                    Layout.columnSpan: 2
                    text: catalog.i18nc("@label","Use Dish Shape")
                    checked: asDishProp
                    onClicked: {
                        asDishProp = checked
                        setProperty("AsDish", checked)
                    }
                }
            }

            Cura.TertiaryButton{
                id: removeAllButton
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                spacing: UM.Theme.getSize("default_margin").height
                width: UM.Theme.getSize("setting_control").width
                height: UM.Theme.getSize("setting_control").height    
                text: catalog.i18nc("@label", "Remove All Tabs")
                onClicked: triggerAction("removeAllSupportMesh")
            }
            Cura.SecondaryButton{
                id: addAllButton
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                spacing: UM.Theme.getSize("default_margin").height
                width: UM.Theme.getSize("setting_control").width
                height: UM.Theme.getSize("setting_control").height    
                text: catalog.i18nc("@label", "Add Automatically")
                //onClicked: triggerAction("addAutoSupportMesh")
                onClicked: automaticAddDensity.open()
                Menu{
                    id: automaticAddDensity
                    MenuItem{
                        text: catalog.i18nc("density_menu", "More tabs (may overlap)")
                        onClicked: {
                            validateInputs()
                            triggerActionWithData("addAutoSupportMesh", {dense: true})
                        }
                    }
                    MenuItem{
                        text: catalog.i18nc("density_menu", "Less tabs (may miss points)")
                        onClicked: {
                            validateInputs()
                            triggerActionWithData("addAutoSupportMesh", {dense: false})
                        }
                    }
                }
            }
        }

        ColumnLayout {
            id: feedbackColumn
            
            UM.Label {
                id: feedbackLabel
                font.weight: Font.Bold
                font.pointSize: 12
                text: ""
                visible: text !== ""
                wrapMode: Text.Wrap
                Layout.preferredWidth: 200
            }

            Timer {
                id: feedbackTimer
                interval: 0 // Will be set from Python
                running: false
                onTriggered: {
                    feedbackLabel.text = "";
                }
            }
        }
    }
}
