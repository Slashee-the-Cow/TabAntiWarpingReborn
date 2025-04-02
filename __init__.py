# Copyright (c) 2022 5@xes
# Based on the TabAntiWarping plugin  and licensed under LGPLv3 or higher.

   
from . import TabAntiWarpingReborn

from UM.i18n import i18nCatalog
i18n_catalog = i18nCatalog("tabawreborn")

def getMetaData():
    qml_file="qml/tabawreborn.qml"
        
    return {
        "tool": {
            "name": i18n_catalog.i18nc("@label", "Tab Anti-Warping Reborn"),
            "description": i18n_catalog.i18nc("@info:tooltip", "Add tabs to object bases to prevent warping."),
            "icon": "tool_icon.svg",
            "tool_panel": qml_file,
            "weight": 11
        }
    }

def register(app):
    return { "tool": TabAntiWarpingReborn.TabAnitWarpingReborn() }
