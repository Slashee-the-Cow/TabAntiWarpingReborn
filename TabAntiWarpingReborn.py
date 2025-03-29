#--------------------------------------------------------------------------------------------
# Initial Copyright(c) 2018 Ultimaker B.V.
# Copyright (c) 2022 5axes
#--------------------------------------------------------------------------------------------
# Based on the SupportBlocker plugin by Ultimaker B.V., and licensed under LGPLv3 or higher.
#
#  https://github.com/Ultimaker/Cura/tree/master/plugins/SupportEraser
#
# All modification 5@xes
# First release  03-06-2022  First proof of concept
# Second release 04-06-2022  New dev and add scripts
#------------------------------------------------------------------------------------------------------------------
# V1.0.3 21-06-2022    : Automatic addition can be only on selected element
# V1.0.4 05-07-2022    : Use "grouped" operation for adding tab; similar to this issue : https://github.com/5axes/NameIt/issues/14
# V1.0.5 11-07-2022    : Change Style of Button for Cura 5.0 5.1
# V1.1.0 18-01-2023    : Integrate translation + French translation
#------------------------------------------------------------------------------------------------------------------
# Reborn version by Slashee the Cow 2025-

from PyQt6.QtCore import Qt, QTimer, pyqtProperty, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtWidgets import QApplication

from typing import Optional, List

from cura.CuraApplication import CuraApplication

from UM.Resources import Resources
from UM.Logger import Logger
from UM.Message import Message
from UM.Math.Vector import Vector
from UM.Tool import Tool
from UM.Event import Event, MouseEvent
from UM.Mesh.MeshBuilder import MeshBuilder

from cura.PickingPass import PickingPass

from cura.CuraVersion import CuraVersion  # type: ignore
from UM.Version import Version

from UM.Operations.GroupedOperation import GroupedOperation
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from cura.Operations.SetParentOperation import SetParentOperation

from UM.Settings.SettingInstance import SettingInstance

from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from cura.Scene.CuraSceneNode import CuraSceneNode
from UM.Scene.Selection import Selection
from UM.Scene.SceneNode import SceneNode
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.Scene.ToolHandle import ToolHandle
from UM.Tool import Tool

import os.path 
import math
import numpy

from UM.Resources import Resources
from UM.i18n import i18nCatalog

fdmprinter_i18n = i18nCatalog("fdmprinter.def.json")

Resources.addSearchPath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)))
)  # Plugin translation file import

catalog = i18nCatalog("tabawreborn")

if catalog.hasTranslationLoaded():
    Logger.log("i", "Tab Anti Warping Reborn plugin translation loaded")
    
DEBUG_MODE = True

def log(level, message):
    """Wrapper function for logging messages using Cura's Logger, but with debug mode so as not to spam you."""
    if level == "d" and DEBUG_MODE:
        Logger.log("d", message)
    elif level == "i":
        Logger.log("i", message)
    elif level == "w":
        Logger.log("w", message)
    elif level == "e":
        Logger.log("e", message)
    elif DEBUG_MODE:
        Logger.log("w", f"Invalid log level: {level} for message {message}")
    
class TabAnitWarpingReborn(Tool):
    def __init__(self):
        super().__init__()
        
        # Stock Data  
        self._all_picked_node = []
        
        
        # variable for menu dialog        
        self._tab_size = 0.0
        self._xy_offset = 0.0
        self._dish = False
        self._adhesion_area = False
        self._layer_count = 1
        self._SMsg = catalog.i18nc("@message", "Remove All") 
        self._Mesg1 = False
        self._Mesg2 = False
        self._Mesg3 = False


        # Shortcut
        self._shortcut_key = Qt.Key_J
            
        self._controller = self.getController()

        self._selection_pass = None
        
        self._application = CuraApplication.getInstance()

        # Suggested solution from fieldOfView . in this discussion solved in Cura 4.9
        # https://github.com/5axes/Calibration-Shapes/issues/1
        # Cura are able to find the scripts from inside the plugin folder if the scripts are into a folder named resources
        Resources.addSearchPath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources"))        

        
        # Logger.log('d', "Info Version CuraVersion --> " + str(Version(CuraVersion)))
        #log('d', "Info CuraVersion --> " + str(CuraVersion))
        
        self.setExposedProperties("SSize", "SOffset", "SCapsule", "LayerCount", "SMsg" ,"SArea" )
        
        CuraApplication.getInstance().globalContainerStackChanged.connect(self._updateEnabled)
        
         
        # Note: if the selection is cleared with this tool active, there is no way to switch to
        # another tool than to reselect an object (by clicking it) because the tool buttons in the
        # toolbar will have been disabled. That is why we need to ignore the first press event
        # after the selection has been cleared.
        Selection.selectionChanged.connect(self._onSelectionChanged)
        self._had_selection = False
        self._skip_press = False

        self._had_selection_timer = QTimer()
        self._had_selection_timer.setInterval(0)
        self._had_selection_timer.setSingleShot(True)
        self._had_selection_timer.timeout.connect(self._selectionChangeDelay)
        
        # set the preferences to store the default value
        self._preferences = CuraApplication.getInstance().getPreferences()
        self._preferences.addPreference("tabawreborn/tab_size", 10)
        self._preferences.addPreference("tabawreborn/xy_offset", 0.16)
        self._preferences.addPreference("tabawreborn/create_dish", False)
        self._preferences.addPreference("tabawreborn/adhesion_area", False)
        self._preferences.addPreference("tabawreborn/layer_count", 1)
        
        self._tab_size = float(self._preferences.getValue("tabawreborn/tab_size"))
        self._xy_offset = float(self._preferences.getValue("tabawreborn/xy_offset"))
        self._dish = bool(self._preferences.getValue("tabawreborn/create_dish")) 
        self._adhesion_area = bool(self._preferences.getValue("tabawreborn/adhesion_area"))
        self._layer_count = int(self._preferences.getValue("tabawreborn/layer_count"))


    def event(self, event):
        super().event(event)
        modifiers = QApplication.keyboardModifiers()
        ctrl_is_active = modifiers & Qt.ControlModifier

        if event.type == Event.MousePressEvent and MouseEvent.LeftButton in event.buttons and self._controller.getToolsEnabled():
            if ctrl_is_active:
                self._controller.setActiveTool("TranslateTool")
                return

            if self._skip_press:
                # The selection was previously cleared, do not add/remove an support mesh but
                # use this click for selection and reactivating this tool only.
                self._skip_press = False
                return

            if self._selection_pass is None:
                # The selection renderpass is used to identify objects in the current view
                self._selection_pass = CuraApplication.getInstance().getRenderer().getRenderPass("selection")
            picked_node = self._controller.getScene().findObject(self._selection_pass.getIdAtPosition(event.x, event.y))
            if not picked_node:
                # There is no slicable object at the picked location
                return

            node_stack = picked_node.callDecoration("getStack")

            
            if node_stack:
            
                if node_stack.getProperty("support_mesh", "value"):
                    self._removeSupportMesh(picked_node)
                    return

                elif node_stack.getProperty("anti_overhang_mesh", "value") or node_stack.getProperty("infill_mesh", "value") or node_stack.getProperty("support_mesh", "value"):
                    # Only "normal" meshes can have support_mesh added to them
                    return

            # Create a pass for picking a world-space location from the mouse location
            active_camera = self._controller.getScene().getActiveCamera()
            picking_pass = PickingPass(active_camera.getViewportWidth(), active_camera.getViewportHeight())
            picking_pass.render()

            picked_position = picking_pass.getPickedPosition(event.x, event.y)

            log("d", f"picked_position = X{picked_position.x} Y{picked_position.y}")

    def _createSupportMesh(self, parent: CuraSceneNode, position: Vector):
        node = CuraSceneNode()

        node.setName("RoundTab")
            
        node.setSelectable(True)
        
        # long=Support Height
        tab_height=position.y
        
        # This function can be triggered in the middle of a machine change, so do not proceed if the machine change
        # has not done yet.
        global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        #extruder = global_container_stack.extruderList[int(_id_ex)] 
        extruder_stack = CuraApplication.getInstance().getExtruderManager().getActiveExtruderStacks()[0]     
        extruder_count=global_container_stack.getProperty("machine_extruder_count", "value") 
        #Logger.log('d', "Info Extruder_count --> " + str(extruder_count))   
        
        # Reasonable defaults for the "standard" 0.4mm nozzle
        layer_height_0: float = 0.3
        layer_height: float = 0.2
        line_width: float = 0.4
        
        try:
            layer_height_0 = float(extruder_stack.getProperty("layer_height_0", "value"))
            layer_height = float(extruder_stack.getProperty("layer_height", "value"))
            line_width = float(extruder_stack.getProperty("line_width", "value"))
        except ValueError as e:
            log("e", f"Error encountered getting properties from the extruder_stack: {e}")
        
        tab_layer_height = (layer_height_0 * 1.2) + (layer_height * (self._layer_count -1))
        tab_line_width = line_width * 1.2
        
        if self._dish:
             # Capsule creation Diameter , Increment angle 10°, length, layer_height_0*1.2 , line_width
            mesh = self._create_dish(self._tab_size, 10, tab_height, tab_layer_height, tab_line_width)
        else:
            # Cylinder creation Diameter , Increment angle 10°, length, layer_height_0*1.2
            mesh = self._createCylinder(self._tab_size, 10, tab_height, tab_layer_height)
        
        
        node.setMeshData(mesh.build())

        active_build_plate = CuraApplication.getInstance().getMultiBuildPlateModel().activeBuildPlate
        node.addDecorator(BuildPlateDecorator(active_build_plate))
        node.addDecorator(SliceableObjectDecorator())

        stack = node.callDecoration("getStack") # created by SettingOverrideDecorator that is automatically added to CuraSceneNode
        settings = stack.getTop()

        # support_mesh type
        definition = stack.getSettingDefinition("support_mesh")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", True)
        new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)

        definition = stack.getSettingDefinition("support_mesh_drop_down")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", False)
        new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)
 
        # Define support_type
        if self._dish:
            key="support_type"
            s_p = global_container_stack.getProperty(key, "value")
            if s_p ==  'buildplate' and not self._Mesg1 :
                definition_key=key + " label"
                untranslated_label=extruder_stack.getProperty(key,"label")
                translated_label=fdmprinter_i18n.i18nc(definition_key, untranslated_label)
                Format_String = catalog.i18nc("@info:label", "Info modification current profile '") + translated_label  + catalog.i18nc("@info:label", "' parameter\nNew value : ") + catalog.i18nc("@info:label", "Everywhere")
                Message(text = Format_String, title = catalog.i18nc("@info:setting_modification_title", "Tab Anti Warping Reborn - Setting Modification")).show()
                Logger.log('d', 'support_type different : ' + str(s_p))
                # Define support_type=everywhere
                global_container_stack.setProperty(key, "value", 'everywhere')
                self._Mesg1 = True
               
        # Define support_xy_distance
        definition = stack.getSettingDefinition("support_xy_distance")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", self._xy_offset)
        # new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)

        # Fix some settings in Cura to get a better result
        global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        extruder_stack = CuraApplication.getInstance().getExtruderManager().getActiveExtruderStacks()[0]
        #extruder = global_container_stack.extruderList[int(id_ex)]
        
        # Hop to fix it in a futur release
        # https://github.com/Ultimaker/Cura/issues/9882
        key="support_xy_distance"
        _xy_distance = extruder_stack.getProperty(key, "value")
        if self._xy_offset !=  _xy_distance and not self._Mesg2 :
            _msg = "New value : %8.3f" % (self._xy_offset) 
            definition_key=key + " label"
            untranslated_label=extruder_stack.getProperty(key,"label")
            translated_label=fdmprinter_i18n.i18nc(definition_key, untranslated_label) 
            Format_String = catalog.i18nc("@info:label", "Info modification current profile '") + "%s" + catalog.i18nc("@info:label", "' parameter\nNew value : ") + "%8.3f"
            Message(text = Format_String % (translated_label, self._xy_offset), title = catalog.i18nc("@info:setting_modification_title", "Tab Anti Warping Reborn - Setting Modification")).show()
            Logger.log('d', 'support_xy_distance different : ' + str(_xy_distance))
            # Define support_xy_distance
            if extruder_count > 1 :
                global_container_stack.setProperty("support_xy_distance", "value", self._xy_offset)
            else:
                extruder_stack.setProperty("support_xy_distance", "value", self._xy_offset)
            
            self._Mesg2 = True
 
        if self._layer_count >1 :
            key="support_infill_rate"
            s_p = int(extruder_stack.getProperty(key, "value"))
            Logger.log('d', 'support_infill_rate actual : ' + str(s_p))
            if s_p < 99 and not self._Mesg3 :
                definition_key=key + " label"
                untranslated_label=extruder_stack.getProperty(key,"label")
                translated_label=fdmprinter_i18n.i18nc(definition_key, untranslated_label)     
                Format_String = catalog.i18nc("@info:label", "Info modification current profile '") + translated_label + catalog.i18nc("@info:label", "' parameter\nNew value : ")+ catalog.i18nc("@info:label", "100%")                
                Message(text = Format_String , title = catalog.i18nc("@info:setting_modification_title", "Tab Anti Warping Reborn - Setting Modification")).show()
                Logger.log('d', 'support_infill_rate different : ' + str(s_p))
                # Define support_infill_rate=100%
                if extruder_count > 1 :
                    global_container_stack.setProperty("support_infill_rate", "value", 100)
                else:
                    extruder_stack.setProperty("support_infill_rate", "value", 100)
                
                self._Mesg3 = True
        
        scene_op = GroupedOperation()
        # First add node to the scene at the correct position/scale, before parenting, so the support mesh does not get scaled with the parent
        scene_op.addOperation(AddSceneNodeOperation(node, self._controller.getScene().getRoot()))
        scene_op.addOperation(SetParentOperation(node, parent))
        scene_op.push()
        node.setPosition(position, CuraSceneNode.TransformSpace.World)
        self._all_picked_node.append(node)
        self._SMsg = catalog.i18nc("@message", "Remove Last") 
        self.propertyChanged.emit()
        
        CuraApplication.getInstance().getController().getScene().sceneChanged.emit(node)

    def _removeSupportMesh(self, node: CuraSceneNode):
        parent = node.getParent()
        if parent == self._controller.getScene().getRoot():
            parent = None

        op = RemoveSceneNodeOperation(node)
        op.push()

        if parent and not Selection.isSelected(parent):
            Selection.add(parent)

        CuraApplication.getInstance().getController().getScene().sceneChanged.emit(node)

    def _updateEnabled(self):
        plugin_enabled = False

        global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        if global_container_stack:
            plugin_enabled = global_container_stack.getProperty("support_mesh", "enabled")

        CuraApplication.getInstance().getController().toolEnabledChanged.emit(self._plugin_id, plugin_enabled)
    
    def _onSelectionChanged(self):
        # When selection is passed from one object to another object, first the selection is cleared
        # and then it is set to the new object. We are only interested in the change from no selection
        # to a selection or vice-versa, not in a change from one object to another. A timer is used to
        # "merge" a possible clear/select action in a single frame
        if Selection.hasSelection() != self._had_selection:
            self._had_selection_timer.start()

    def _selectionChangeDelay(self):
        has_selection = Selection.hasSelection()
        if not has_selection and self._had_selection:
            self._skip_press = True
        else:
            self._skip_press = False

        self._had_selection = has_selection
 
    # Capsule creation
    def _create_dish(self, base_diameter, segments , height, top_height, line_width):
        """Create a "dish" style adhesion tab"""
        mesh = MeshBuilder()
        # Per-vertex normals require duplication of vertices
        base_radius = base_diameter / 2
        # First layer length
        max_y = -height + top_height
        if self._layer_count >1 :
            cap_height = -height + (top_height * 2)
        else:
            cap_height = -height + (top_height * 3)
        min_y = -height
        segment_angle = int(360 / segments)
        segment_radians = math.radians(segments)

        cap_radius=math.tan(math.radians(45))*(top_height * 3)+base_radius
        # Top inside radius 
        inner_radius_cap=cap_radius-(1.8*line_width)
        # Top radius 
        inner_radius_base=base_radius-(1.8*line_width)
            
        vertices = []
        for i in range(0, segment_angle):
            # Top
            vertices.append([inner_radius_cap*math.cos(i*segment_radians), cap_height, inner_radius_cap*math.sin(i*segment_radians)])
            vertices.append([cap_radius*math.cos((i+1)*segment_radians), cap_height, cap_radius*math.sin((i+1)*segment_radians)])
            vertices.append([cap_radius*math.cos(i*segment_radians), cap_height, cap_radius*math.sin(i*segment_radians)])
            
            vertices.append([inner_radius_cap*math.cos((i+1)*segment_radians), cap_height, inner_radius_cap*math.sin((i+1)*segment_radians)])
            vertices.append([cap_radius*math.cos((i+1)*segment_radians), cap_height, cap_radius*math.sin((i+1)*segment_radians)])
            vertices.append([inner_radius_cap*math.cos(i*segment_radians), cap_height, inner_radius_cap*math.sin(i*segment_radians)])

            #Side 1a
            vertices.append([cap_radius*math.cos(i*segment_radians), cap_height, cap_radius*math.sin(i*segment_radians)])
            vertices.append([cap_radius*math.cos((i+1)*segment_radians), cap_height, cap_radius*math.sin((i+1)*segment_radians)])
            vertices.append([base_radius*math.cos((i+1)*segment_radians), min_y, base_radius*math.sin((i+1)*segment_radians)])
            
            #Side 1b
            vertices.append([base_radius*math.cos((i+1)*segment_radians), min_y, base_radius*math.sin((i+1)*segment_radians)])
            vertices.append([base_radius*math.cos(i*segment_radians), min_y, base_radius*math.sin(i*segment_radians)])
            vertices.append([cap_radius*math.cos(i*segment_radians), cap_height, cap_radius*math.sin(i*segment_radians)])
 
            #Side 2a
            vertices.append([inner_radius_base*math.cos((i+1)*segment_radians), max_y, inner_radius_base*math.sin((i+1)*segment_radians)])
            vertices.append([inner_radius_cap*math.cos((i+1)*segment_radians), cap_height, inner_radius_cap*math.sin((i+1)*segment_radians)])
            vertices.append([inner_radius_cap*math.cos(i*segment_radians), cap_height, inner_radius_cap*math.sin(i*segment_radians)])
            
            #Side 2b
            vertices.append([inner_radius_cap*math.cos(i*segment_radians), cap_height, inner_radius_cap*math.sin(i*segment_radians)])
            vertices.append([inner_radius_base*math.cos(i*segment_radians), max_y, inner_radius_base*math.sin(i*segment_radians)])
            vertices.append([inner_radius_base*math.cos((i+1)*segment_radians), max_y, inner_radius_base*math.sin((i+1)*segment_radians)])
                
            #Bottom Top
            vertices.append([0, max_y, 0])
            vertices.append([inner_radius_base*math.cos((i+1)*segment_radians), max_y, inner_radius_base*math.sin((i+1)*segment_radians)])
            vertices.append([inner_radius_base*math.cos(i*segment_radians), max_y, inner_radius_base*math.sin(i*segment_radians)])
            
            #Bottom 
            vertices.append([0, min_y, 0])
            vertices.append([base_radius*math.cos(i*segment_radians), min_y, base_radius*math.sin(i*segment_radians)])
            vertices.append([base_radius*math.cos((i+1)*segment_radians), min_y, base_radius*math.sin((i+1)*segment_radians)]) 
            
            
        mesh.setVertices(numpy.asarray(vertices, dtype=numpy.float32))

        indices = []
        # for every angle increment 24 Vertices
        total = segment_angle * 24
        for i in range(0, total, 3): # 
            indices.append([i, i+1, i+2])
        mesh.setIndices(numpy.asarray(indices, dtype=numpy.int32))

        mesh.calculateNormals()
        return mesh
        
    # Cylinder creation
    def _createCylinder(self, base_diameter, segments, height, top_height):
        mesh = MeshBuilder()
        # Per-vertex normals require duplication of vertices
        base_radius = base_diameter / 2
        # First layer length
        max_y = -height + top_height
        min_y = -height
        segment_angle = int(360 / segments)
        segment_radians = math.radians(segments)
        
        vertices = []
        for i in range(0, segment_angle):
            # Top
            vertices.append([0, max_y, 0])
            vertices.append([base_radius*math.cos((i+1)*segment_radians), max_y, base_radius*math.sin((i+1)*segment_radians)])
            vertices.append([base_radius*math.cos(i*segment_radians), max_y, base_radius*math.sin(i*segment_radians)])
            #Side 1a
            vertices.append([base_radius*math.cos(i*segment_radians), max_y, base_radius*math.sin(i*segment_radians)])
            vertices.append([base_radius*math.cos((i+1)*segment_radians), max_y, base_radius*math.sin((i+1)*segment_radians)])
            vertices.append([base_radius*math.cos((i+1)*segment_radians), min_y, base_radius*math.sin((i+1)*segment_radians)])
            #Side 1b
            vertices.append([base_radius*math.cos((i+1)*segment_radians), min_y, base_radius*math.sin((i+1)*segment_radians)])
            vertices.append([base_radius*math.cos(i*segment_radians), min_y, base_radius*math.sin(i*segment_radians)])
            vertices.append([base_radius*math.cos(i*segment_radians), max_y, base_radius*math.sin(i*segment_radians)])
            #Bottom 
            vertices.append([0, min_y, 0])
            vertices.append([base_radius*math.cos(i*segment_radians), min_y, base_radius*math.sin(i*segment_radians)])
            vertices.append([base_radius*math.cos((i+1)*segment_radians), min_y, base_radius*math.sin((i+1)*segment_radians)])          
            
        mesh.setVertices(numpy.asarray(vertices, dtype=numpy.float32))

        indices = []
        # for every angle increment 12 Vertices
        total = segment_angle * 12
        for i in range(0, total, 3): # 
            indices.append([i, i+1, i+2])
        mesh.setIndices(numpy.asarray(indices, dtype=numpy.int32))

        mesh.calculateNormals()
        return mesh
 
    def removeAllSupportMesh(self):
        if self._all_picked_node:
            for node in self._all_picked_node:
                node_stack = node.callDecoration("getStack")
                if node_stack.getProperty("support_mesh", "value"):
                    self._removeSupportMesh(node)
            self._all_picked_node = []
            self._SMsg = catalog.i18nc("@message", "Remove All") 
            self.propertyChanged.emit()
        else:        
            for node in DepthFirstIterator(self._application.getController().getScene().getRoot()):
                if node.callDecoration("isSliceable"):
                    # N_Name=node.getName()
                    # Logger.log('d', 'isSliceable : ' + str(N_Name))
                    node_stack=node.callDecoration("getStack")           
                    if node_stack:        
                        if node_stack.getProperty("support_mesh", "value"):
                            # N_Name=node.getName()
                            # Logger.log('d', 'support_mesh : ' + str(N_Name)) 
                            self._removeSupportMesh(node)
 
    # Source code from MeshTools Plugin 
    # Copyright (c) 2020 Aldo Hoeben / fieldOfView
    def _getAllSelectedNodes(self) -> List[SceneNode]:
        selection = Selection.getAllSelectedObjects()
        if selection:
            deep_selection: List[SceneNode] = []
            for selected_node in selection:
                if selected_node.hasChildren():
                    deep_selection = deep_selection + selected_node.getAllChildren()
                if selected_node.getMeshData() != None:
                    deep_selection.append(selected_node)
            if deep_selection:
                return deep_selection

        # Message(catalog.i18nc("@info:status", "Please select one or more models first"))

        return []

    # Automatic creation
    def addAutoSupportMesh(self) -> int:
        nb_Tab=0
        act_position = Vector(99999.99,99999.99,99999.99)
        first_pt=Vector

        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            nodes_list = DepthFirstIterator(self._application.getController().getScene().getRoot())
        
        scene_op = GroupedOperation()   
        for node in nodes_list:
            if node.callDecoration("isSliceable"):
                Logger.log('d', "isSliceable : {}".format(node.getName()))
                node_stack=node.callDecoration("getStack")           
                if node_stack: 
                    type_infill_mesh = node_stack.getProperty("infill_mesh", "value")
                    type_cutting_mesh = node_stack.getProperty("cutting_mesh", "value")
                    type_support_mesh = node_stack.getProperty("support_mesh", "value")
                    type_anti_overhang_mesh = node_stack.getProperty("anti_overhang_mesh", "value") 
                    
                    if not type_infill_mesh and not type_support_mesh and not type_anti_overhang_mesh :
                    # and Selection.isSelected(node)
                        Logger.log('d', "Mesh : {}".format(node.getName()))
                        
                        #hull_polygon = node.callDecoration("getConvexHull")
                        if self._adhesion_area :
                            hull_polygon = node.callDecoration("getAdhesionArea")
                        else:
                            # hull_polygon = node.callDecoration("getConvexHull")
                            # hull_polygon = node.callDecoration("getConvexHullBoundary")
                            hull_polygon = node.callDecoration("_compute2DConvexHull")
                                   
                        if not hull_polygon or hull_polygon.getPoints is None:
                            Logger.log("w", "Object {} cannot be calculated because it has no convex hull.".format(node.getName()))
                            continue
                            
                        points=hull_polygon.getPoints()
                        # nb_pt = point[0] / point[1] must be divided by 2
                        nb_pt=points.size*0.5
                        Logger.log('d', "Size pt : {}".format(nb_pt))
                        
                        for point in points:
                            nb_Tab+=1
                            # Logger.log('d', "Nb_Tab : {}".format(nb_Tab))
                            if nb_Tab == 1:
                                first_pt = Vector(point[0], 0, point[1])
                                # Logger.log('d', "First X : {}".format(point[0]))
                                # Logger.log('d', "First Y : {}".format(point[1]))
                                
                            # Logger.log('d', "X : {}".format(point[0]))
                            # Logger.log('d', "Y : {}".format(point[1]))
                            new_position = Vector(point[0], 0, point[1])
                            lg=act_position-new_position
                            lght = lg.length()
                            # Logger.log('d', "Length : {}".format(lght))
                            # Add a tab if the distance between 2 tabs are more than a Tab Radius
                            # We have to tune this parameter or algorythm in the futur
                            if nb_Tab == nb_pt:
                                lgfl=(first_pt-new_position).length()
                                 
                                # Logger.log('d', "Length First Last : {}".format(lgfl))
                                if lght >= (self._tab_size*0.5) and lgfl >= (self._tab_size*0.5) :
                                    self._createSupportMesh(node, new_position)
                                    act_position = new_position                               
                            else:
                                if lght >= (self._tab_size*0.5) :
                                    self._createSupportMesh(node, new_position)
                                    act_position = new_position
                                 
                            # Useless but I keep it for the code example
                            # Using findObject(id(node))
                            # act_node = self._controller.getScene().findObject(id(node))
                            # if act_node:
                            #     Logger.log('d', "Mesh To Add : {}".format(act_node.getName()))
                            #     self._createSupportMesh(act_node, Vector(point[0], 0, point[1]))  
        scene_op.push()
        return nb_Tab

    def getSMsg(self) -> bool:
        """ 
            return: golabl _SMsg  as text paramater.
        """ 
        return self._SMsg
    
    def setSMsg(self, SMsg: str) -> None:
        """
        param SType: SMsg as text paramater.
        """
        self._SMsg = SMsg
        
    def getSSize(self) -> float:
        """ 
            return: golabl _UseSize  in mm.
        """           
        return self._tab_size
  
    def setSSize(self, SSize: str) -> None:
        """
        param SSize: Size in mm.
        """
 
        try:
            s_value = float(SSize)
        except ValueError:
            return

        if s_value <= 0:
            return      
        #Logger.log('d', 's_value : ' + str(s_value))        
        self._tab_size = s_value
        self._preferences.setValue("tabawreborn/tab_size", s_value)
 
    def getLayerCount(self) -> int:
        """Tool getter for layer count"""
        return self._layer_count
  
    def setLayerCount(self, value: str) -> None:
        """Tool setter for layer count"""
        try:
            int_value = int(value)
            
        except ValueError:
            return  
 
        if int_value < 1:
            return
        
        self._Mesg3 = False
        #Logger.log('d', 'i_value : ' + str(i_value))        
        self._layer_count = int_value
        self._preferences.setValue("tabawreborn/layer_count", int_value)
        
    def getSOffset(self) -> float:
        """ 
            return: golabl _UseOffset  in mm.
        """           
        return self._xy_offset
  
    def setSOffset(self, SOffset: str) -> None:
        """
        param SOffset: SOffset in mm.
        """
 
        try:
            s_value = float(SOffset)
        except ValueError:
            return
        
        #Logger.log('d', 's_value : ' + str(s_value)) 
        self._Mesg2 = False        
        self._xy_offset = s_value
        self._preferences.setValue("tabawreborn/xy_offset", s_value)

    def getSCapsule(self) -> bool:
        """ 
            return: golabl _AsCapsule  as boolean
        """           
        return self._dish
  
    def setSCapsule(self, SCapsule: bool) -> None:
        """
        param SCapsule: as boolean.
        """
        self._Mesg1 = False
        self._dish = SCapsule
        self._preferences.setValue("tabawreborn/create_dish", SCapsule)
        
    def getSArea(self) -> bool:
        """ 
            return: golabl _SArea  as boolean
        """           
        return self._adhesion_area
  
    def setSArea(self, SArea: bool) -> None:
        """
        param SArea: as boolean.
        """
        self._adhesion_area = SArea
        self._preferences.setValue("tabawreborn/adhesion_area", SArea)

