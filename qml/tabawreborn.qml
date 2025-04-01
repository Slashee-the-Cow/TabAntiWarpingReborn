//-----------------------------------------------------------------------------
// Tab+ Anti-Warping Copyright (c) 2022 5@xes
// Reborn version copyright Slashee the Cow 2025-
// proterties values
//   "TabSize"      : Tab Size in mm
//   "XYDistance"   : X/Y distance from model in mm
//   "AsDish"       : Use dish shape
//   "LayerCount"   : Number of layers for tab
//
//-----------------------------------------------------------------------------

import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Layouts 6.0

import UM 1.6 as UM
import Cura 1.1 as Cura

Item {
    id: base

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

    width: childrenRect.width
    height: childrenRect.height
    UM.I18nCatalog { id: catalog; name: "tabawreborn"}
    
    property int localwidth:70

    ColumnLayout {
        id: mainColumn
        anchors.left: parent.left
        anchors.top: parent.top
    
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
                width: localwidth
                height: UM.Theme.getSize("setting_control").height
                unit: "mm"
                text: getProperty("TabSize")
                validator: DoubleValidator {
                    decimals: 2
                    bottom: 0.1
                }

                onEditingFinished: {
                    let modified_text = text.replace(",", ".");
                    setProperty("TabSize", modified_text);
                }
            }
            
            UM.Label {
                text: catalog.i18nc("@label", "X/Y Distance")
            }

            UM.TextFieldWithUnit {
                id: offsetTextField
                width: localwidth
                height: UM.Theme.getSize("setting_control").height
                unit: "mm"
                text: getProperty("XYDistance")
                validator: DoubleValidator {
                    top: 1
                    decimals: 2
                }

                onEditingFinished: {
                    var modified_text = text.replace(",", "."); // User convenience. We use dots for decimal values
                    setProperty("XYDistance", modified_text);
                }
            }

            UM.Label {
                text: catalog.i18nc("@label", "Number of layers")
            }

            UM.TextFieldWithUnit
            {
                id: numberlayerTextField
                width: localwidth
                height: UM.Theme.getSize("setting_control").height
                text: UM.ActiveTool.properties.getValue("LayerCount")
                validator: IntValidator {
                    bottom: 1
                    top: 100
                }

                onEditingFinished: {
                    setProperty("LayerCount", text)
                }
            }

            UM.CheckBox {
                id: asDishCheckbox
                text: catalog.i18nc("@label","Dish shape")
                checked: getProperty("AsDish")
                onClicked: setProperty("AsDish", checked)
            }

            /*UM.SimpleButton
            {
                id: helpButton
                width: UM.Theme.getSize("save_button_specs_icons").width
                height: UM.Theme.getSize("save_button_specs_icons").height
                iconSource: UM.Theme.getIcon("Help")
                hoverColor: UM.Theme.getColor("small_button_text_hover")
                color:  UM.Theme.getColor("small_button_text")
                
                onClicked:
                {
                Qt.openUrlExternally(getlinkCurrent)
                }
            }*/
        }

        Rectangle {
            id: topRect
            anchors.top: textfields.bottom 
            //color: UM.Theme.getColor("toolbar_background")
            color: "#00000000"
            width: UM.Theme.getSize("setting_control").width * 1.3
            height: UM.Theme.getSize("setting_control").height 
            anchors.left: parent.left
            anchors.topMargin: UM.Theme.getSize("default_margin").height
        }

        Cura.SecondaryButton
        {
            id: removeAllButton
            anchors.centerIn: topRect
            spacing: UM.Theme.getSize("default_margin").height
            width: UM.Theme.getSize("setting_control").width
            height: UM.Theme.getSize("setting_control").height    
            text: catalog.i18nc("@label", "Remove all tabs")
            onClicked: triggerAction("removeAllSupportMesh")
        }

        Rectangle {
            id: bottomRect
            anchors.top: topRect.bottom
            //color: UM.Theme.getColor("toolbar_background")
            color: "#00000000"
            width: UM.Theme.getSize("setting_control").width * 1.3
            height: UM.Theme.getSize("setting_control").height 
            anchors.left: parent.left
            anchors.topMargin: UM.Theme.getSize("default_margin").height
        }

        Cura.SecondaryButton
        {
            id: addAllButton
            anchors.centerIn: bottomRect
            spacing: UM.Theme.getSize("default_margin").height
            width: UM.Theme.getSize("setting_control").width
            height: UM.Theme.getSize("setting_control").height    
            text: catalog.i18nc("@label", "Automatic Addition")
            onClicked: triggerAction("addAutoSupportMesh")
        }
    }
}
