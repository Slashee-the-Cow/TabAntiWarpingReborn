#--------------------------------------------------------------------------------------------
# Based on the SupportBlocker plugin by Ultimaker B.V., and licensed under LGPLv3 or higher.
# https://github.com/Ultimaker/Cura/tree/master/plugins/SupportEraser
# Tab+ Anti Warping Copyright (c) 2022 5axes https://github.com/5axes/TabPlus
# Tab Anti-Warping Reborn by Slashee the Cow copyright 2025-
#--------------------------------------------------------------------------------------------
# Changelog (Reborn version)
#
# v1.0.0
# - Renamed everything inside and out, so it won't interfere with other versions if installed side by side. Also so that it has the new name.
# - Took out Qt 5 support resulting in requiring Cura 5.0 or higher. If this affects you, you probably should have upgraded quite a while ago.
# - Removed "set on adhesion area" option. I honestly can't understand why it existed. If there's something I'm missing, by all means get in touch.
# - Renamed "capsule" to "dish". Not my first choice but the inner construction brick afficionado won't let me call something that isn't flat "plate".
# - Hopefully stopped the "remove all" button from removing things which aren't tabs. This might cause it to miss things which are tabs. I find this tradeoff acceptable.
# - Cleaned up A LOT of code. When was the last time someone *cough* dusted this place?
# - Refactor might be a bit of an understatement. I actually had to use AI to figure out what some of the code was or some of the variable names meant. Hopefully you don't.
# - Redid the layout for the UI. Hopefully it doesn't look too different. Hopefully it's easier to maintain. That factor may be less important to you.
# - Made the UI more responsive because there's lots of things neither of us have time for... I assume.
# - Added copious amounts of input validation to the UI. Sorry if you were having fun trying to make tabs with invalid settings.
# - Squashed a large quantity of bugs. My fingers are crossed that I missed the "fix one bug, add two more" paradigm.
# - Implemented more checks to make sure Cura's settings are what they need to be for the plugin to work.
# - Implemented UI explanations for why those settings need to be what they are for the plugin to work.
# - Optimised some of the code. This may literally save you nanoseconds.
# - Got rid of a whole bunch of docstrings that took up a lot of space but had very little to say in them. My linter is quite displeased with me.
# - Tried to improve the linter's mood by type hinting a bunch of stuff. I don't think it's any more impressed.
# - Put in a bunch of logging so when it inevitably fails hopefully I'll be able to figure out why.
# - Had to put a Cura version check and add wrapper functions in the QML because in 5.7 they deprecated the way a tool accesses the backend in favour of a different way introduced in 5.7.
# - Choice of density of auto generated tabs (minimum distance being radius or diameter) for those into Feng Shui and don't want clutter.
# - Added checks to make sure a tab isn't created off the build plate, or too close to edge, since Cura's aim sucks and tries to put tabs way off in the distance sometimes.
#--------------------------------------------------------------------------------------------
# There seems to be a bug with UM.Message.Message that makes PickingPass go wildly off course if there's one on screen.
# Hence why I rolled my own.

import math
import os.path
import time
from typing import List

import numpy
from cura.CuraApplication import CuraApplication
from cura.Operations.SetParentOperation import SetParentOperation
from cura.PickingPass import PickingPass
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from cura.Scene.CuraSceneNode import CuraSceneNode
from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator
from PyQt6.QtCore import Qt, QTimer, QVariant
from PyQt6.QtQml import QJSValue
from PyQt6.QtWidgets import QApplication
from UM.Event import Event, MouseEvent
from UM.i18n import i18nCatalog
from UM.Logger import Logger
from UM.Math.Vector import Vector
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Message import Message
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Operations.GroupedOperation import GroupedOperation
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from UM.Operations.TranslateOperation import TranslateOperation
from UM.Resources import Resources
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.Scene.SceneNode import SceneNode
from UM.Scene.Selection import Selection
from UM.Settings.SettingInstance import SettingInstance
from UM.Tool import Tool

Resources.addSearchPath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)))
)  # Plugin translation file import

catalog = i18nCatalog("tabawreborn")

if catalog.hasTranslationLoaded():
    Logger.log("i", "Tab Anti-Warping Reborn plugin translation loaded")

DEBUG_MODE = True

def log(level: str, message: str) -> None:
    """Wrapper function for logging messages using Cura's Logger, but with debug mode so as not to spam you."""
    if level == "d" and DEBUG_MODE:
        Logger.log("d", message)
    elif level == "dd":
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

    def __init__(self) -> None:
        super().__init__()
        
        # List of tabs we've created
        self._scene_tabs = []
        
        # variable for menu dialog
        self._tab_size: float = 0.0
        self._xy_distance: float = 0.0
        self._as_dish: bool = False
        self._layer_count: int = 1
        self._inputs_valid: bool = False
        
        self._any_as_dish = False # Track if any dish supports have been created

        # Shortcut
        self._shortcut_key = Qt.Key.Key_J
        self._controller = self.getController()
        self._selection_pass = None
        self._application = CuraApplication.getInstance()
        
        self.setExposedProperties("TabSize", "XYDistance", "AsDish", "LayerCount", "InputsValid", "LogMessage")
        
        CuraApplication.getInstance().globalContainerStackChanged.connect(self._updateEnabled)
        
         
        # Note: if the selection is cleared with this tool active, there is no way to switch to
        # another tool than to reselect an object (by clicking it) because the tool buttons in the
        # toolbar will have been disabled. That is why we need to ignore the first press event
        # after the selection has been cleared.
        Selection.selectionChanged.connect(self._onSelectionChanged)
        self._had_selection: bool = False
        self._skip_press: bool = False

        self._had_selection_timer = QTimer()
        self._had_selection_timer.setInterval(0)
        self._had_selection_timer.setSingleShot(True)
        self._had_selection_timer.timeout.connect(self._selectionChangeDelay)
        
        # set the preferences to store the default value
        self._preferences = CuraApplication.getInstance().getPreferences()
        self._preferences.addPreference("tabawreborn/tab_size", 10)
        self._preferences.addPreference("tabawreborn/xy_distance", 0.16)
        self._preferences.addPreference("tabawreborn/create_dish", False)
        self._preferences.addPreference("tabawreborn/layer_count", 1)
        
        self._tab_size = float(self._preferences.getValue("tabawreborn/tab_size"))
        self._xy_distance = float(self._preferences.getValue("tabawreborn/xy_distance"))
        self._as_dish = bool(self._preferences.getValue("tabawreborn/create_dish"))
        self._layer_count = int(self._preferences.getValue("tabawreborn/layer_count"))
        
    def event(self, event) -> None:
        super().event(event)
        modifiers = QApplication.keyboardModifiers()
        ctrl_is_active = modifiers & Qt.KeyboardModifier.ControlModifier

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
            log("d", f"picked_node = {picked_node}")
            if not self._inputs_valid:
                log("d", "Tried to create tab with invalid inputs")
                #Message(text = catalog.i18nc("add_tab_invalid_input", "Cannot create a tab while some of the settings are not valid. Please check the tool's settings."),
                #        title = catalog.i18nc("add_tab_invalid_input_title", "Tab Anti-Warping Reborn")).show()
                return
            
            node_world_transform = picked_node.getWorldTransformation()
            if node_world_transform:
                node_position = node_world_transform.getTranslation()
                log("dd", f"picked_node world position = {node_position}")
            else:
                log("d", "picked_node has no world transformation")

            node_stack = picked_node.callDecoration("getStack")


            if node_stack:
                if node_stack.getProperty("support_mesh", "value"):
                    self._removeSupportMesh(picked_node)
                    return
                if node_stack.getProperty("anti_overhang_mesh", "value") or node_stack.getProperty("infill_mesh", "value") or node_stack.getProperty("support_mesh", "value"):
                    # Only "normal" meshes can have support_mesh added to them
                    return
            #Message("You just added a tab!", title="Grats!").show()

            # Create a pass for picking a world-space location from the mouse location
            #log("d", "PICKING: About to get active camera")
            active_camera = self._controller.getScene().getActiveCamera()
            #log("d", f"All about active_camera: -- Parent: {active_camera.getParent()} -- Mirror: {active_camera.getMirror()} -- BoundingBoxMesh: {active_camera.getBoundingBoxMesh()} -- Decorators: {active_camera.getDecorators()} -- Name: {active_camera.getName()} -- ID: {active_camera.getId()} -- Depth: {active_camera.getDepth()} -- isVisible: {active_camera.isVisible()} -- MeshData: {active_camera.getMeshData()} -- MeshDataTransformed: {active_camera.getMeshDataTransformed()} -- MeshDataTransformed.toString(): {active_camera.getMeshDataTransformed().toString()} -- MeshDataTransformedVertices: {active_camera.getMeshDataTransformedVertices()} -- MeshDataTransformedNormals: {active_camera.getMeshDataTransformedNormals()} -- Children: {active_camera.getChildren()} -- AllChildren: {active_camera.getAllChildren()} -- CachedNormalMatrix: {active_camera.getCachedNormalMatrix()} -- WorldTransformation: {active_camera.getWorldTransformation()} -- LocalTransform: {active_camera.getLocalTransformation()} -- Orientation: {active_camera.getOrientation()} -- WorldOrientation: {active_camera.getWorldOrientation()} -- Scale: {active_camera.getScale()} -- WorldScale: {active_camera.getWorldScale()} -- Position: {active_camera.getPosition()} -- WorldPosition: {active_camera.getWorldPosition()} -- isEnabled: {active_camera.isEnabled()} -- isSelectable: {active_camera.isSelectable()} -- BoundingBox: {active_camera.getBoundingBox()} -- Shear: {active_camera.getShear()} -- AutoAdjustViewport: {active_camera.getAutoAdjustViewPort()} -- DefaultZoomFactor: {active_camera.getDefaultZoomFactor()} -- ZoomFactor: {active_camera.getZoomFactor()} -- ProjectionMatrix: {active_camera.getProjectionMatrix()} -- ViewportWidth: {active_camera.getViewportWidth()} -- ViewportHeight: {active_camera.getViewportHeight()} -- ViewProjectionMatrix: {active_camera.getViewProjectionMatrix()} -- WindowSize: {active_camera.getWindowSize()} -- InverseWorldTransformation: {active_camera.getInverseWorldTransformation()} -- CameraLightPosition: {active_camera.getCameraLightPosition()} -- isPerspective: {active_camera.isPerspective()} -- ")
            #log("d", "PICKING: About to create PickingPass instance")
            picking_pass = PickingPass(active_camera.getViewportWidth(), active_camera.getViewportHeight())
            #log("d", "PICKING: About to render pass")
            picking_pass.render()
            #log("d", "PICKING: Just rendered pass.")

            log("dd", f"event.x = {event.x}, event.y = {event.y}")
            picked_position = picking_pass.getPickedPosition(event.x, event.y)

            log("dd", f"repr(picked_position) = {repr(picked_position)}")
            if not self._check_valid_tab_placement(picked_position):
                return
                            
            # Add the tab at the picked location
            self._createSupportMesh(picked_node, picked_position)

    def _createSupportMesh(self, parent: CuraSceneNode, position: Vector):
        node = CuraSceneNode()

        node.setName("Tab")
            
        node.setSelectable(True)
        
        # long=Support Height
        tab_start_y=position.y

        global_stack = CuraApplication.getInstance().getGlobalContainerStack()

        extruder_stack = CuraApplication.getInstance().getExtruderManager().getActiveExtruderStacks()[0]
        
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
        
        tab_total_height = (layer_height_0 * 1.2) + (layer_height * (self._layer_count -1))
        tab_line_width = line_width * 1.2
        
        if self._as_dish:
             # Capsule creation Diameter , Increment angle 10°, length, layer_height_0*1.2 , line_width
            mesh = self._create_dish(self._tab_size, 10, tab_start_y, tab_total_height, tab_line_width)
            self._any_as_dish = True
        else:
            # Cylinder creation Diameter , Increment angle 10°, length, layer_height_0*1.2
            mesh = self._createCylinder(self._tab_size, 10, tab_start_y, tab_total_height)

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
        if self._any_as_dish or self._as_dish:
            support_type_key="support_type"
            support_placement = global_stack.getProperty(support_type_key, "value")
            #log("d", f"BEFORE: global stack support_type = {support_placement}")
            if support_placement == "buildplate":
                message_string = catalog.i18nc("@info:support_placement_modified", "Support placement has been set to Everywhere to ensure dish tabs work correctly.")
                #Message(text = message_string, title = catalog.i18nc("@info:setting_modification_title", "Tab Anti-Warping Reborn - Setting Modification")).show()
                global_stack.setProperty(support_type_key, "value", "everywhere")
                #log("d", f"AFTER: global stack support_type = {global_stack.getProperty(support_type_key, 'value')}")
               
        # Define support_xy_distance
        definition = stack.getSettingDefinition("support_xy_distance")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", self._xy_distance)
        # new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)

        # Fix some settings in Cura to get a better result
        #extruder = global_container_stack.extruderList[int(id_ex)]

        support_xy_key="support_xy_distance"
        stack_xy_distance = global_stack.getProperty(support_xy_key, "value")
        log("d", f"BEFORE: global stack {support_xy_key} = {stack_xy_distance}")
        if self._xy_distance != stack_xy_distance:
            message_string = f'{catalog.i18nc("@info:support_xy_modified", "Support X/Y distance has been changed to match tab tool settings of")} {str(self._xy_distance)}mm.'
            #Message(text = message_string, title = catalog.i18nc("@info:setting_modification_title", "Tab Anti-Warping Reborn - Setting Modification")).show()
            global_stack.setProperty(support_xy_key, "value", self._xy_distance)
            log("d", f"AFTER: global stack {support_xy_key} = {global_stack.getProperty(support_xy_key, 'value')}")

        # Support infill (more than 1 layer needs to be solid)
        if self._layer_count > 1:
            support_infill_key="support_infill_rate"
            support_infill = float(extruder_stack.getProperty(support_infill_key, "value"))
            #log("d", f"BEFORE: global stack support_infill = {support_infill}")
            if support_infill < 100.0:
                message_string = catalog.i18nc("@info:support_infill_modified", "Support density has been set to 100% to ensure tabs over 1 layer high are solid.")
                #Message(text = message_string , title = catalog.i18nc("@info:setting_modification_title", "Tab Anti-Warping Reborn - Setting Modification")).show()
                global_stack.setProperty(support_infill_key, "value", 100.0)
                #log("d", f"AFTER: global stack support_infill = {extruder_stack.getProperty(support_infill_key, 'value')}")
                
        
        scene_op = GroupedOperation()
        # First add node to the scene at the correct position/scale, before parenting, so the support mesh does not get scaled with the parent
        scene_op.addOperation(AddSceneNodeOperation(node, self._controller.getScene().getRoot()))
        scene_op.addOperation(SetParentOperation(node, parent))
        scene_op.addOperation(TranslateOperation(node, position, set_position = True))
        scene_op.push()
        self._scene_tabs.append(node)
        self.propertyChanged.emit()
        
        CuraApplication.getInstance().getController().getScene().sceneChanged.emit(node)

    def _check_valid_tab_placement(self, picked_position) -> bool:
        # Check to see if Cura picked a spot off the build plate
        global_stack = CuraApplication.getInstance().getGlobalContainerStack()
        machine_width = float(global_stack.getProperty("machine_width", "value"))
        machine_depth = float(global_stack.getProperty("machine_depth", "value"))
        log("d", f"machine width = {machine_width}, depth = {machine_depth}")
        if (picked_position.x < -(machine_width / 2)
            or picked_position.x > (machine_width / 2)
            or picked_position.z < -(machine_depth / 2)
            or picked_position.z > (machine_depth / 2)
        ):
            #Message(
            #    text = catalog.i18nc("tab_off_build_plate", "Oops! Looks like Cura picked an invalid position for the tab :( Please try again."),
            #    title = catalog.i18nc("@message:title", "Tab Anti-Warping Reborn")).show()
            return False

        left_edge: float = -(machine_width / 2) + (self._tab_size / 2)
        right_edge: float = (machine_width / 2) - (self._tab_size / 2)
        front_edge: float = (-machine_depth / 2) + (self._tab_size / 2)
        rear_edge: float = (machine_depth / 2) + (self._tab_size / 2)
        log("d", f"left_edge = {left_edge}, right_edge = {right_edge}, front_edge = {front_edge}, rear_edge = {rear_edge}")
        if(
            picked_position.x < left_edge
            or picked_position.x > right_edge
            or picked_position.z < front_edge
            or picked_position.z > rear_edge
        ):
            #Message(
            #    text = catalog.i18nc("tab_on_plate_edge", "A tab can't be that close to edge of the build plate. You should move your object in a bit."),
            #    title= catalog.i18nc("@message:title", "Tab Anti-Warping Reborn")).show()
            return False
        
        #TODO: Use SceneNode.collidesWithBbox()
        return True
    
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
        """Run when global container stack changes to make sure settings we need are still applied"""
        plugin_enabled = False
        global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()

        if global_container_stack:
            # Check if any support meshes (tabs) exist in the scene.
            nodes_list = self._getAllSelectedNodes()
            if not nodes_list:
                nodes_list = DepthFirstIterator(self._application.getController().getScene().getRoot())

            for node in nodes_list:
                if node.callDecoration("isSliceable"):
                    node_stack = node.callDecoration("getStack")
                    if node_stack and node_stack.getProperty("support_mesh", "value"):
                        plugin_enabled = True #Enable plugin if support meshes exist.
                        if not global_container_stack.getProperty("support_mesh", "enabled"):
                            global_container_stack.setProperty("support_mesh", "enabled", True)
                            #Message(text = catalog.i18nc("@info:label", "Support was re-enabled because tabs are present in the scene."), title = catalog.i18nc("@info:title", "Tab Anti-Warping Reborn")).show() #Show toast message.
                        break

            else:
                plugin_enabled = global_container_stack.getProperty("support_mesh", "enabled") #Use global setting, when no support meshes exist.

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
    def _create_dish(self, base_diameter: float, segments: int , height: float, top_height: float, line_width: float):
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
        for i in range(0, total, 3):
            indices.append([i, i+1, i+2])
        mesh.setIndices(numpy.asarray(indices, dtype=numpy.int32))

        mesh.calculateNormals()
        return mesh

    # Cylinder creation
    def _createCylinder(self, base_diameter: float, segments: int, start_y: float, cylinder_height: float):
        mesh = MeshBuilder()
        # Per-vertex normals require duplication of vertices
        base_radius = base_diameter / 2
        # First layer length
        max_y = -start_y + cylinder_height
        min_y = -start_y
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
        for i in range(0, total, 3):
            indices.append([i, i+1, i+2])
        mesh.setIndices(numpy.asarray(indices, dtype=numpy.int32))

        mesh.calculateNormals()
        return mesh
 
    def removeAllSupportMesh(self):
        if self._scene_tabs:
            for node in self._scene_tabs:
                if node:
                    node_stack = node.callDecoration("getStack")
                    if node_stack.getProperty("support_mesh", "value"):
                        self._removeSupportMesh(node)
            self._scene_tabs.clear()
            self._any_as_dish = False
            self.propertyChanged.emit()
            #Message(text = catalog.i18nc("remove_all_text", "All tabs which the plugin has tracked have been deleted.\nSome may have lost tracking and need to be deleted manually."), title=catalog.i18nc("remove_all_title", "Tab Anti-Warping Reborn"))
 
    # Source code from MeshTools Plugin 
    # Copyright (c) 2020 Aldo Hoeben / fieldOfView
    def _getAllSelectedNodes(self) -> List[SceneNode]:
        selection = Selection.getAllSelectedObjects()
        if selection:
            deep_selection: List[SceneNode] = []
            for selected_node in selection:
                if selected_node.hasChildren():
                    deep_selection = deep_selection + selected_node.getAllChildren()
                if selected_node.getMeshData() is not None:
                    deep_selection.append(selected_node)
            if deep_selection:
                return deep_selection

        # Message(catalog.i18nc("@info:status", "Please select one or more models first"))

        return []

    # Automatic creation
    def addAutoSupportMesh(self, data:QJSValue) -> None:
        log("d", f"addAutoSupportMesh got data {repr(data)}")
        dense = True
        # Make sure data is the right type before we mess with it:
        if data is not None and isinstance(data, QJSValue):
            # Convert it to a QVariant
            variant = data.toVariant()
            # Hope our QVariant is a dict like we passed
            if isinstance(variant, dict):
                dense = variant.get("dense", True)
                log("d", f"addAutoSupportMesh from QVariant {variant} got dense {dense}")
            else:
                log("d", f"addAutoSupportMesh got QVariant {variant} which isn't a dict")
        else:
            log("d", f"addAutoSupportMesh did not get a QJSValue passed to it. It got {data}")
        
        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            nodes_list = DepthFirstIterator(self._application.getController().getScene().getRoot())

        for node in nodes_list:
            if not node.callDecoration("isSliceable"):
                continue
            log("d", f"{node.getName()} is sliceable")
            node_stack=node.callDecoration("getStack")
            if not node_stack:
                continue
            type_infill_mesh = node_stack.getProperty("infill_mesh", "value")
            type_cutting_mesh = node_stack.getProperty("cutting_mesh", "value")
            type_support_mesh = node_stack.getProperty("support_mesh", "value")
            type_anti_overhang_mesh = node_stack.getProperty("anti_overhang_mesh", "value") 

            if any((type_infill_mesh, type_cutting_mesh, type_support_mesh, type_anti_overhang_mesh)):
                continue
            log("d", f"{node.getName()} is a valid mesh")

            hull_polygon = node.callDecoration("_compute2DConvexHull")

            # Make sure it's a valid polygon
            if len(hull_polygon.getPoints()) < 3:
                log("w", f"{node.getName()} didn't produce a valid convex hull")
                continue

            points=hull_polygon.getPoints()
            minimum_distance = self._tab_size * 0.5 if dense else self._tab_size

            last_tab_position = None
            first_point = Vector(points[0][0], 0, points[0][1])

            for i, point in enumerate(points):
                new_position = Vector(point[0], 0, point[1])
                difference_vector = last_tab_position - new_position if last_tab_position else Vector(0,0,0)
                # Guarantee distance will always be large enough even if previous position not set
                difference_length = difference_vector.length() if last_tab_position else self._tab_size * 2

                first_to_last_length = (first_point - new_position).length() if i == len(points) - 1 else 0
                if difference_length >= minimum_distance or first_to_last_length >= minimum_distance:
                    self._createSupportMesh(node, new_position)
                    last_tab_position = new_position
        
        # Switch to translate tool because you're probably not going to want to create/remoge tabs straight away.
        self._controller.setActiveTool("TranslateTool")
        #Message(
        #    text = catalog.i18nc("auto_tab_switch_tool","Automatic tab creation finished. Switching to move tool."),
        #    title = catalog.i18nc("@message:title", "Tab Anti-Warping Reborn"),
        #    lifetime = 15).show()

    def getTabSize(self) -> float:
        #log("d", f"getTabSize accessed with self._tab_size = {self._tab_size}")
        return self._tab_size
  
    def setTabSize(self, TabSize: str) -> None:
        #log("d", f"setTabSize run with {TabSize}")
        try:
            float_value = float(TabSize)
        except ValueError:
            #log("e", "setTabSize was passed something that could not be cast to a float")
            return

        if float_value <= 0:
            return

        self._tab_size = float_value
        self._preferences.setValue("tabawreborn/tab_size", float_value)
 
    def getLayerCount(self) -> int:
        #log("d", f"getLayerCount accessed with self._layer_count = {self._layer_count}")
        return self._layer_count
  
    def setLayerCount(self, count: str) -> None:
        #log("d", f"setLayerCount run with {count}")
        try:
            int_value = int(count)
            
        except ValueError:
            #log("e", "setLayerCount was passed something that could not be cast to a int")
            return
 
        if int_value < 1:
            return

        self._layer_count = int_value
        self._preferences.setValue("tabawreborn/layer_count", int_value)
        
    def getXYDistance(self) -> float:
        #log("d", f"getXYDistance accessed with self._xy_distance = {self._xy_distance}")
        return self._xy_distance
  
    def setXYDistance(self, XYDistance: str) -> None:
        #log("d", f"setXYDistance run with {XYDistance}")
        try:
            float_value = float(XYDistance)
        except ValueError:
            #log("e", "setXYDistance was passed something that could not be cast to a float")
            return

        self._xy_distance = float_value
        self._preferences.setValue("tabawreborn/xy_distance", float_value)

    def getAsDish(self) -> bool:
        #log("d", f"getAsDish accessed with self._as_dish = {self._as_dish} of type {type(self._as_dish)}")
        return self._as_dish

    def setAsDish(self, AsDish: bool) -> None:
        #log("d", f"setAsDish run with {AsDish}")
        self._as_dish = AsDish
        self._preferences.setValue("tabawreborn/create_dish", AsDish)

    def getInputsValid(self) -> bool:
        #log("d", f"getInputsValid accessed with self._inputs_valid = {self._inputs_valid}")
        return self._inputs_valid

    def setInputsValid(self, InputValid: bool) -> None:
        #log("d", f"setInputsValid run with {InputValid}")
        self._inputs_valid = InputValid

    def getLogMessage(self) -> str:
        """ This is just here so I can use the setter to log stuff. """
        return ""

    def setLogMessage(self, message: str) -> None:
        log("d", f"TabAntiWarpingReborn QML Log: {message}")
