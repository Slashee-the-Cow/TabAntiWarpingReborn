#--------------------------------------------------------------------------------------------
# Based on the SupportBlocker plugin by Ultimaker B.V., and licensed under LGPLv3 or higher.
# https://github.com/Ultimaker/Cura/tree/master/plugins/SupportEraser
# Tab+ Anti Warping Copyright (c) 2022 5axes https://github.com/5axes/TabPlus
#
# Tab Anti-Warping Reborn by Slashee the Cow copyright 2025-
#--------------------------------------------------------------------------------------------
# Changelog (Reborn version)
#
# v1.1.0
#   - Copied my patent-not-pending BaseDetect™ system over from Spoon Anti-Warping Reborn to place tabs around the object base, not the convex hull.
#   - Fixed a couple of minor bugs which wouldn't have been there if I was paying attention in the first place.
# v1.0.1
#   - Rolled my own notification UI as part of the tool control panel since UM.Messages hate both me and the support blocker tool.
# v1.0.0
#   - Renamed everything inside and out, so it won't interfere with other versions if installed side by side. Also so that it has the new name.
#   - Took out Qt 5 support resulting in requiring Cura 5.0 or higher. If this affects you, you probably should have upgraded quite a while ago.
#   - Removed "set on adhesion area" option. I honestly can't understand why it existed. If there's something I'm missing, by all means get in touch.
#   - Renamed "capsule" to "dish". Not my first choice but the inner construction brick afficionado won't let me call something that isn't flat "plate".
#   - Hopefully stopped the "remove all" button from removing things which aren't tabs. This might cause it to miss things which are tabs. I find this tradeoff acceptable.
#   - Cleaned up A LOT of code. When was the last time someone *cough* dusted this place?
#   - Refactor might be a bit of an understatement. I actually had to use AI to figure out what some of the code was or some of the variable names meant. Hopefully you don't.
#   - Redid the layout for the UI. Hopefully it doesn't look too different. Hopefully it's easier to maintain. That factor may be less important to you.
#   - Made the UI more responsive because there's lots of things neither of us have time for... I assume.
#   - Added copious amounts of input validation to the UI. Sorry if you were having fun trying to make tabs with invalid settings.
#   - Squashed a large quantity of bugs. My fingers are crossed that I missed the "fix one bug, add two more" paradigm.
#   - Implemented more checks to make sure Cura's settings are what they need to be for the plugin to work.
#   - Implemented UI explanations for why those settings need to be what they are for the plugin to work.
#   - Optimised some of the code. This may literally save you nanoseconds.
#   - Got rid of a whole bunch of docstrings that took up a lot of space but had very little to say in them. My linter is quite displeased with me.
#   - Tried to improve the linter's mood by type hinting a bunch of stuff. I don't think it's any more impressed.
#   - Put in a bunch of logging so when it inevitably fails hopefully I'll be able to figure out why.
#   - Had to put a Cura version check and add wrapper functions in the QML because in 5.7 they deprecated the way a tool accesses the backend in favour of a different way introduced in 5.7.
#   - Choice of density of auto generated tabs (minimum distance being radius or diameter) for those into Feng Shui and don't want clutter.
#   - Added checks to make sure a tab isn't created off the build plate, or too close to edge, since Cura's aim sucks and tries to put tabs way off in the distance sometimes.
#--------------------------------------------------------------------------------------------
# There seems to be a bug with UM.Message.Message that makes PickingPass go wildly off course if there's one on screen.
# Hence why I rolled my own. It's much inferior, except that it doesn't seem to break things.

from dataclasses import dataclass
import math
import os.path
from typing import List

import numpy as np
from scipy.spatial import ConvexHull
import trimesh
from cura.CuraApplication import CuraApplication
from cura.Operations.SetParentOperation import SetParentOperation
from cura.PickingPass import PickingPass
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from cura.Scene.CuraSceneNode import CuraSceneNode
from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtQml import QJSValue
from PyQt6.QtWidgets import QApplication
from UM.Event import Event, MouseEvent
from UM.i18n import i18nCatalog
from UM.Logger import Logger
from UM.Math.Polygon import Polygon
from UM.Math.Vector import Vector
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Mesh.MeshData import MeshData
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

@dataclass
class Notification:
    """Holds info for a notification message since I can't use UM.Message"""
    text: str  # If I need to explain this you're probably not qualified to work with this code.
    lifetime: float  # Notification lifetime in seconds
    id: int  # Becasue we've all gotten our notifications mixed up while out shopping... right?

Resources.addSearchPath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)))
)  # Plugin translation file import

catalog = i18nCatalog("tabawreborn")

if catalog.hasTranslationLoaded():
    Logger.log("i", "Tab Anti-Warping Reborn plugin translation loaded")

DEBUG_MODE = False

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
        self._hide_toasts: bool = True

        self._any_as_dish = False # Track if any dish supports have been created

        # Shortcut
        self._shortcut_key = Qt.Key.Key_J
        self._controller = self.getController()
        self._selection_pass = None
        self._application = CuraApplication.getInstance()

        self.setExposedProperties("TabSize", "XYDistance", "AsDish", "LayerCount", "InputsValid", "Notifications", "LogMessage")

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

        # Hold variables needed for the deferred PickingPass
        self._last_picked_node: CuraSceneNode = None
        self._last_event: Event = None

        self._are_messages_hidden: bool = False
        self._hidden_messages: list[Message] = []

        self._default_message_title = catalog.i18nc("@message:title", "Tab Anti-Warping Reborn")

        self._notifications: list[Notification] = []
        self._notification_next_id: int = 0
        self._notifications_string: str = ""

    def event(self, event) -> None:
        super().event(event)
        modifiers = QApplication.keyboardModifiers()
        ctrl_is_active = modifiers & Qt.KeyboardModifier.ControlModifier

        if event.type == Event.MousePressEvent and MouseEvent.LeftButton in event.buttons and self._controller.getToolsEnabled():
            if ctrl_is_active:
                self._controller.setActiveTool("TranslateTool")
                return

            log("d", "You clicked!")
            #Message(text = "You clicked!", title = "Grats!").show()


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
                self._notification_add(catalog.i18nc("add_tab_invalid_input", "Cannot create a tab while some of the settings are not valid. Please check the tool's settings."), 10)
                return

            log("d", "event() just got past valid input check")
            self._last_picked_node = picked_node
            self._last_event = event

            # Hide all currently shown messages
            if self._hide_toasts:
                try:  # In a try...except for now at least, just to make sure anything gets caught
                    self._hide_messages()
                except Exception as e:
                    log("e", f"_hide_messages raised {e}")
            # Defer PickingPass until the next event loop
            QTimer.singleShot(250 if self._are_messages_hidden else 0, self._picking_pass)
            log("d", "event() set the timer")
            return

    def _picking_pass(self):
        log("d", "_picking_pass is just getting started")
        picked_node = self._last_picked_node
        event = self._last_event
        log("d", f"_picking_pass working on picked_node {picked_node}")


        node_world_transform = picked_node.getWorldTransformation()
        if node_world_transform:
            node_position = node_world_transform.getTranslation()
            log("d", f"picked_node world position = {node_position}")
        else:
            log("d", "picked_node has no world transformation")

        node_stack = picked_node.callDecoration("getStack")


        if node_stack:
            if node_stack.getProperty("support_mesh", "value"):
                self._removeSupportMesh(picked_node)
                log("d", f"_picking_pass just found that picked_node was support and removed it")
                # Show previously hidden Messages
                log("d", f"_picking_pass about to run _show_messages while _hidden_messages is {self._hidden_messages}")
                try:
                    self._show_messages()
                except Exception as e:
                    log("e", f"_show_messages raised {e}")
                return
            if node_stack.getProperty("anti_overhang_mesh", "value") or node_stack.getProperty("infill_mesh", "value") or node_stack.getProperty("support_mesh", "value"):
                # Only "normal" meshes can have support_mesh added to them
                log("d", f"_picking_pass found that picked_node {picked_node} is the wrong kind of mesh")
                # Show previously hidden Messages
                log("d", f"_picking_pass about to run _show_messages while _hidden_messages is {self._hidden_messages}")
                try:
                    self._show_messages()
                except Exception as e:
                    log("e", f"_show_messages raised {e}")
                return

        # Create a pass for picking a world-space location from the mouse location
        active_camera = self._controller.getScene().getActiveCamera()
        picking_pass = PickingPass(active_camera.getViewportWidth(), active_camera.getViewportHeight())
        log("d", f"_picking_pass: active_camera.getViewportWidth() = {active_camera.getViewportWidth()} and active_camera.getViewportHeight = {active_camera.getViewportHeight()}")
        picking_pass.render()

        log("d", f"event.x = {event.x}, event.y = {event.y}")
        picked_position = picking_pass.getPickedPosition(event.x, event.y)
        #self._notification_add(repr(picked_position), 5)

        log("dd", f"repr(picked_position) = {repr(picked_position)}")
        if not self._check_valid_tab_placement(picked_position):
            log("d", f"picked_position {picked_position} deemed invalid")
            # Show previously hidden Messages
            log("d", f"_picking_pass about to run _show_messages while _hidden_toasts is {self._hidden_messages}")
            try:
                self._show_messages()
            except Exception as e:
                log("e", f"_show_messages raised {e}")
            return

        # Add the tab at the picked location
        self._createSupportMesh(picked_node, picked_position)

        # Show previously hidden Messages
        log("d", f"_picking_pass about to run _show_messages while _hidden_toasts is {self._hidden_messages}")
        try:
            self._show_messages()
        except Exception as e:
            log("e", f"_show_messages raised {e}")

    def _hide_messages(self):
        log("d", f"_hide_messages is running with an _application.getVisibleMessages() of {self._application.getVisibleMessages()}")
        message_count = len(self._application.getVisibleMessages())
        if message_count == 0:
            self._are_messages_hidden = False
            return

        self._are_messages_hidden = True
        self._notification_add("<font color='red'>Do not move the camera until the click location is recorded.</font>", 1)
        self._hidden_messages = list(self._application.getVisibleMessages())
        log("d", f"_hide_messages just set _hidden_messages to {self._hidden_messages}")
        for message in self._hidden_messages:
            message.hide()

    def _show_messages(self):
        if not self._are_messages_hidden:
            return

        self._notification_add("<font color='green'>Click position has been recorded.</font>", 3)
        for message in self._hidden_messages:
            message.show()

        self._are_messages_hidden = False
        self._hidden_messages = []

    def _notification_add(self, text: str, lifetime: float) -> None:
        notification = Notification(text, lifetime, self._notification_next_id)
        self._notifications.append(notification)
        self._notification_next_id += 1
        self._notifications_set_property()
        QTimer.singleShot(int(lifetime * 1000), lambda: self._notification_remove(notification))

    def _notification_remove(self, notification: Notification) -> None:
        if notification in self._notifications:
            self._notifications.remove(notification)
            self._notifications_set_property()
        else:
            log("d", f"_notification_remove could not find notification with text {notification.text} and ID {notification.id}")

    def _notifications_set_property(self) -> None:
        self._notifications_string = "<br><br>".join(notification.text for notification in self._notifications)
        self.propertyChanged.emit()

    def _createSupportMesh(self, parent: CuraSceneNode, position: Vector):
        node = CuraSceneNode()

        node.setName("AdhesionTab")

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
                self._notification_add(message_string, 10)
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
        #log("d", f"BEFORE: global stack {support_xy_key} = {stack_xy_distance}")
        if self._xy_distance != stack_xy_distance:
            global_stack.setProperty(support_xy_key, "value", self._xy_distance)
            if self._xy_distance == global_stack.getProperty(support_xy_key, "value"):
                # Successfully changed property
                message_string = f'{catalog.i18nc("@info:support_xy_modified", "Support X/Y distance has been changed to match tab tool settings of")} {str(self._xy_distance)}mm.'
                self._notification_add(message_string, 10)
            else:
                message_string = f'{catalog.i18nc("@info:support_xy_blocked", "Support X/Y distance has been manually set different to the tab tool setting of")} {str(self._xy_distance)}mm.'
                self._notification_add(message_string, 10)
            #log("d", f"AFTER: global stack {support_xy_key} = {global_stack.getProperty(support_xy_key, 'value')}")

        # Support infill (more than 1 layer needs to be solid)
        if self._layer_count > 1:
            support_infill_key="support_infill_rate"
            support_infill = float(extruder_stack.getProperty(support_infill_key, "value"))
            #log("d", f"BEFORE: global stack support_infill = {support_infill}")
            if support_infill < 100.0:
                message_string = catalog.i18nc("@info:support_infill_modified", "Support density has been set to 100% to ensure tabs over 1 layer high are solid.")
                self._notification_add(message_string, 10)
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
            self._notification_add(catalog.i18nc("tab_off_build_plate", "Oops! Looks like Cura picked an invalid position for the tab :( Please try again."), 7.5)
            return False

        left_edge: float = -(machine_width / 2) + (self._tab_size / 2)
        right_edge: float = (machine_width / 2) - (self._tab_size / 2)
        front_edge: float = (-machine_depth / 2) + (self._tab_size / 2)
        rear_edge: float = (machine_depth / 2) - (self._tab_size / 2)
        log("d", f"left_edge = {left_edge}, right_edge = {right_edge}, front_edge = {front_edge}, rear_edge = {rear_edge}")
        if(
            picked_position.x < left_edge
            or picked_position.x > right_edge
            or picked_position.z < front_edge
            or picked_position.z > rear_edge
        ):
            self._notification_add(catalog.i18nc("tab_on_plate_edge", "A tab can't be that close to edge of the build plate. You should move your object in a bit."), 7.5)
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
                            self._notification_add(catalog.i18nc("@info:label", "Support was re-enabled because tabs are present in the scene."), 5)
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

        mesh.setVertices(np.asarray(vertices, dtype=np.float32))

        indices = []
        # for every angle increment 24 Vertices
        total = segment_angle * 24
        for i in range(0, total, 3):
            indices.append([i, i+1, i+2])
        mesh.setIndices(np.asarray(indices, dtype=np.int32))

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

        mesh.setVertices(np.asarray(vertices, dtype=np.float32))

        indices = []
        # for every angle increment 12 Vertices
        total = segment_angle * 12
        for i in range(0, total, 3):
            indices.append([i, i+1, i+2])
        mesh.setIndices(np.asarray(indices, dtype=np.int32))

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
            self._notification_add(catalog.i18nc("remove_all_text", "All tabs which the plugin has tracked have been deleted.\nSome may have lost tracking and need to be deleted manually."), 10)

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

    # Used to compare union convex hulls to allow for floating point inaccuracies
    def _compare_polygons_with_tolerance(self, poly1: Polygon, poly2: Polygon, tolerance=1e-6):
        points1 = poly1.getPoints()
        points2 = poly2.getPoints()

        if points1 is None and points2 is None:
            return True
        if points1 is None or points2 is None or len(points1) != len(points2):
            return False

        # Sort the points before comparison to handle different vertex order
        sorted_points1 = np.sort(points1, axis=0)
        sorted_points2 = np.sort(points2, axis=0)

        return np.allclose(sorted_points1, sorted_points2, atol=tolerance, rtol=tolerance)

    # Automatic creation
    def addAutoTabMesh(self, data:QJSValue) -> None:
        log("d", f"addAutoTabMesh got data {repr(data)}")
        dense = True
        # Make sure data is the right type before we mess with it:
        if data is not None and isinstance(data, QJSValue):
            # Convert it to a QVariant
            variant = data.toVariant()
            # Hope our QVariant is a dict like we passed
            if isinstance(variant, dict):
                dense = variant.get("dense", True)
                log("d", f"addAutoTabMesh from QVariant {variant} got dense {dense}")
            else:
                log("d", f"addAutoTabMesh got QVariant {variant} which isn't a dict")
        else:
            log("d", f"addAutoTabMesh did not get a QJSValue passed to it. It got {data}")

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

            shapes: list[np.ndarray] = None
            try:
                shapes = self._get_base_convex_hulls(node)
            except Exception as e:
                log("e", f"Exception in _get_base_convex_hulls: {e}")
            if shapes is not None:
                for shape in shapes:
                    log("d", f"addAutoTabMesh: just got base convex hulls {shape}")

                # Filter out any hulls completely inside one another
                if len(shapes) > 1:
                    filtered_hulls = []
                    log("d", "Filtering hulls")
                    true_element = True
                    false_element = False
                    is_base = [true_element for _ in range(len(shapes))]
                    is_child = [false_element for _ in range(len(shapes))]
                    for a, hull_a in enumerate(shapes):
                        for b, hull_b in enumerate(shapes):
                            if a == b:
                                continue
                            if is_child[a] or is_child[b]:
                                continue
                            try:
                                union_hull = hull_a.unionConvexHulls(hull_b)
                            except Exception as e:
                                log("e", f"Couldn't create union hull for overlap test: {e}")
                            log("d", f"union_hull = {union_hull}")
                            if self._compare_polygons_with_tolerance(union_hull, hull_a):
                                # b is fully contained within a
                                is_base[b] = False
                                is_child[b] = True
                            if self._compare_polygons_with_tolerance(union_hull, hull_b):
                                # a is fully contained within b
                                is_base[a] = False
                                is_child[a] = True
                                break
                    log("d", f"Looped through hulls, is_base = {is_base}, is_child = {is_child}")
                    for i, hull in enumerate(shapes):
                        if is_base[i]:
                            filtered_hulls.append(hull)
                    shapes = filtered_hulls

            # If the complicated way doesn't work fall back to the regular way
            if shapes is None or len(shapes) == 0:
                log("i", "addAutoTabMesh: falling back to regular hull")
                hull_polygon: Polygon = node.callDecoration("getConvexHullBoundary")
                if hull_polygon is None:
                    hull_polygon = node.callDecoration("getConvexHull")

                if not hull_polygon or not hull_polygon.isValid():
                    log("w", f"Object {node.getName()} cannot be calculated because it has no convex hull.")
                    continue
                shapes = [hull_polygon]

            minimum_gap = self._tab_size * 0.5 if dense else self._tab_size

            for shape in shapes:
                shape_points = shape.getPoints()
                if shape_points is None:
                    continue
                    
                log("d", "addAutoTabMesh: in loop for each shape")
                last_tab_position = None
                first_point = Vector(shape_points[0][0], 0, shape_points[0][1])

                for i, point in enumerate(shape_points):
                    new_position = Vector(point[0], 0, point[1])
                    difference_vector = last_tab_position - new_position if last_tab_position else Vector(0,0,0)
                    # Guarantee distance will always be large enough even if previous position not set
                    difference_length = difference_vector.length() if last_tab_position else minimum_gap * 2

                    first_to_last_distance = (first_point - new_position).length() if i == len(shape_points) - 1 else 0
                    if (first_to_last_distance == 0 and difference_length >= minimum_gap) or (first_to_last_distance >= minimum_gap and difference_length >= minimum_gap):
                        self._createSupportMesh(node, new_position)
                        last_tab_position = new_position

        # Switch to translate tool because you're probably not going to want to create/remove tabs straight away.
        self._controller.setActiveTool("TranslateTool")
        Message(text=catalog.i18nc("auto_tab_switch_tool","Automatic tab creation finished. Switching to move tool."), lifetime=15, title=self._default_message_title).show()

    def _get_base_convex_hulls(self, node: CuraSceneNode, height: float = 0.2) -> list[np.ndarray]:
        if not node:
            return None
        trimesh_mesh = self._toTriMesh(node.getMeshDataTransformed())
        log("d", f"_get_base_convex_hulls using trimesh = {trimesh_mesh}")
        log("d", f"_get_base_convex_hulls trimesh is watertight? {trimesh_mesh.is_watertight}")
        min_y = trimesh_mesh.bounds[0][1]
        slice_y = min_y + height

        plane_origin = np.array([0, slice_y, 0])
        plane_normal = np.array([0, 1, 0])

        section = trimesh_mesh.section(plane_normal=plane_normal, plane_origin=plane_origin)
        if section is not None:
            if hasattr(section, 'discrete'):  # It's a Path3D (series of contours)
                uranium_polygons = []
                for contour in section.discrete:
                    vertices_2d = np.array([[point[0], point[2]] for point in contour])
                    if vertices_2d.shape[0] >= 3:
                        hull = ConvexHull(vertices_2d)
                        hull_points = vertices_2d[hull.vertices]
                        uranium_polygon = Polygon(hull_points)
                        uranium_polygons.append(uranium_polygon)
                return uranium_polygons
            if hasattr(section, 'vertices'): # It's a Trimesh (intersection is a face)
                vertices_2d = section.vertices[:, [0,2]]
                if vertices_2d.shape[0] >= 3:
                    hull = ConvexHull(vertices_2d)
                    hull_points = vertices_2d[hull.vertices]
                    return [Polygon(hull_points)]
                return []
            return []
        return []


    #----------------------------------------
    # Initial Source code from  fieldOfView
    #----------------------------------------
    def _toTriMesh(self, mesh_data: MeshData) -> trimesh.base.Trimesh:
        if not mesh_data:
            return trimesh.base.Trimesh()

        indices = mesh_data.getIndices()
        if indices is None:
            # some file formats (eg 3mf) don't supply indices, but have unique vertices per face
            indices = np.arange(mesh_data.getVertexCount()).reshape(-1, 3)

        return trimesh.base.Trimesh(vertices=mesh_data.getVertices(), faces=indices)

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

    def getNotifications(self) -> str:
        return self._notifications_string

    def setNotifications(self, notifications: str) -> None:
        """The front end should never change this. So it can't."""
        log("d", "Something tried to call setNotifications")
        return

    def getLogMessage(self) -> str:
        """ This is just here so I can use the setter to log stuff. """
        log("d", "Something tried to call getLogMessage")
        return ""

    def setLogMessage(self, message: str) -> None:
        log("d", f"TabAntiWarpingReborn QML Log: {message}")
