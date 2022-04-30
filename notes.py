"""

    Maya Notes

    TODO - Have notes based on scene, project, or object.
    TODO - Make a wrapper of QWidget that enables animation.

    Object notes:
    If a note is linked to an object then if that object or any children of
    that object are selected, the note will be visible.

    Scene Notes:
    Scene notes are linked to specific scenes and cn only be edited when that
    scene is open.

    Project Notes:
    Project notes are always visible.

    Requires Maya 2022 or newer for python 3
    Author: Matthew Denton
"""

from dataclasses import dataclass
from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QDialog, QCheckBox, QLineEdit, QLabel, QPushButton, QPlainTextEdit, QSpacerItem, QSizePolicy, QToolButton, QStyleOption
from shiboken2 import wrapInstance
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya import cmds
from maya import OpenMayaUI
import os


WTITLE = 'Notes'
WOBJ = 'notes'

notes = []  # Stores all notes currently loaded.


def save_notes():
    '''
    Saves all currently cached notes.
    '''
    pass


def load_notes():
    '''
    Loads notes for the currently open scene.
    '''
    pass


def _maya_main_window():
    """Return mayas main window"""
    return wrapInstance(OpenMayaUI.MQtUtil.mainWindow(), QWidget)


def _maya_delete_ui(window_title, window_object):
    """Delete an exisiting window"""
    if cmds.window(window_object, q=True, exists=True):
        cmds.deleteUI(window_object)  # Delete window
    if cmds.dockControl("MayaWindow|" + window_title, q=True, exists=True):
        cmds.deleteUI("MayaWindow|" + window_title)  # Delete docked window


def _maya_delete_workspace(window_object):
    """Delete existing workspace in maya"""
    control = window_object + "WorkspaceControl"
    if cmds.workspaceControl(control, q=True, exists=True):
        cmds.workspaceControl(control, e=True, close=True)
        cmds.deleteUI(control, control=True)


def _maya_update_workspace(window_object):
    """Updates existing workspace in Maya"""
    control = window_object + "WorkspaceControl"
    if cmds.workspaceControl(control, q=True, exists=True):
        cmds.workspaceControl(
            control,
            e=True,
            restore=True,
            retain=True,
            # # options below
            # dockToMainWindow=("left", -1),
            # tabToControl=("ChannelBoxLayerEditor", -1),
            # tabToControl=("Outliner", -1),
            tabToControl=("AttributeEditor", -1),
        )


def _qt_seperator(vertical: bool = False):
    if vertical:
        return QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
    return QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)


def stylesheet(fileName: str) -> str:
    '''
    Gets a stylesheet file and returns it as a string to be assigned to a widget.
    If the file is not found or fails to load then an empty string is returned.
    '''
    path = os.path.realpath(__file__)
    path = os.path.abspath(os.path.join(path, os.path.pardir))
    STYLE_DIR = path
    try:
        with open(os.path.join(STYLE_DIR, fileName), 'r') as file:
            return file.read()
    except Exception:
        print(f'Failed to load stylesheet {fileName} in {__file__}')
    return ''


def icon(fileName: str) -> QtGui.QIcon:
    path = os.path.realpath(__file__)
    path = os.path.abspath(os.path.join(path, os.path.pardir))
    ICON_DIR = os.path.join(path, 'icons')
    return QtGui.QIcon(os.path.join(ICON_DIR, fileName))


@dataclass
class NoteCheck:
    '''
    Simple note check that stores the check value of a note and the text assosiated 
    with the checkbox.

    A check can also have children added to it. If this has children then this will act as
    a main checked. The checked state of this would then only ever be true if all of the
    children are checked.
    '''
    text: str
    checked: bool = False
    children: list = None

    def add_child(self, check):
        if self.children is None:
            self.children = []
        self.children.append(check)


@dataclass
class Note:
    """
    Stores information for a note.
    """
    title: str
    text: str
    created_date: str = ''
    author: str = ''
    chesklist: list = None

    def add_check(self, check: NoteCheck):
        if self.chesklist is None:
            self.chesklist = []
        self.chesklist.append(check)


class NoteCheckWidget(QWidget):

    def __init__(self, noteCheck: NoteCheck):
        super(NoteCheckWidget, self).__init__()
        self.note_check = noteCheck

        # Set the widgets layout
        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        # Create needed widgets
        self.checkbox = QCheckBox()
        self.text = QLineEdit()

        self._construct()

    def _construct(self):
        self._layout.addWidget(self.checkbox)
        self._layout.addWidget(self.text)


class NoteCheckListWidget(QWidget):

    def __init__(self):
        super(NoteCheckListWidget, self).__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.items = []

    def append(self, check: NoteCheckWidget):
        self.items.append(check)
        self._layout.addWidget(check)

    def pop(self, index: int):
        widget = self.items.pop(index)
        self._layout.removeWidget(widget)
        widget.deleteLater()


class NoteWidget(QWidget):

    def __init__(self, note: Note):
        super(NoteWidget, self).__init__()
        self.note = note

        # Set the widgets layout
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        # Make the background styled
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setContentsMargins(20, 15, 20, 10)

        # Create needed widgets
        self.title = QLineEdit(note.title)
        self.text = QLineEdit(note.text)
        self.checklist = NoteCheckListWidget()

        self._del_btn = QPushButton()

        self._construct()

    def _construct(self):
        # Action/Toolbar widgets
        tools = QHBoxLayout()
        actions = QHBoxLayout()
        self._tools_widget = QWidget(parent=self, fixedHeight=35)
        self._actions_widget = QWidget(visible=False)
        self._actions_widget.setLayout(actions)

        tools.setContentsMargins(0, 0, 0, 0)
        actions.setContentsMargins(0, 0, 0, 0)

        # TODO make wrapper of button to enable opacity animation when hover, pressed etc
        archive_btn = QToolButton(icon=icon('archive.svg'))
        delete_btn = QToolButton(icon=icon('delete.svg'))
        linked_icon = QToolButton(icon=icon('linked-object.svg'))

        tools.addStretch()
        tools.addWidget(self._actions_widget)
        actions.addWidget(archive_btn)
        actions.addWidget(delete_btn)
        tools.addWidget(linked_icon)

        self._tools_widget.setProperty('toolbar', '')
        self._tools_widget.setLayout(tools)

        # Data widgets in the center
        self._layout.addWidget(self.title)
        self._layout.addWidget(self.text)
        self._layout.addWidget(self.checklist)

        # Extra info widgets at the bottom
        self.info = QLabel(f'{self.note.created_date}         {self.note.author}')
        self._layout.addWidget(self.info)

        # Set the data tags for styling
        self.title.setProperty('tag', 'title')
        self.text.setProperty('tag', 'text')
        self.info.setProperty('tag', 'info')

    def resizeEvent(self, event):
        # Reposition the create notes button to be fixed to the windows bottom right.
        self._tools_widget.move(
            self.width() - self._tools_widget.width() - 20,
            0
        )

    def enterEvent(self, event):
        self._actions_widget.setVisible(True)

    def leaveEvent(self, event):
        self._actions_widget.setVisible(False)

    def refresh(self):
        ''' Refresh the notes data and widgets '''
        pass

    def _update_title(self):
        pass

    def _update_text(self):
        pass


class NotesUI(MayaQWidgetDockableMixin, QDialog):

    def __init__(self, parent=_maya_main_window()):
        super(NotesUI, self).__init__(parent)

        # an array of all the notes currently loaded in the UI
        self._note_widgets = []

        # All pet rocks need to have a name.
        self.setObjectName(WOBJ)
        self.setWindowTitle(WTITLE)

        self.setMinimumSize(300, 200)

        self.setWindowFlags(QtCore.Qt.Window)
        self.setStyleSheet(stylesheet('notes.qss'))
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        # Make maya handle some magic
        self.setProperty('saveWindowPref', True)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._construct_ui()
        self.refresh_ui()
        self.show(dockable=True)

    def _construct_ui(self):

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit(minimumWidth=250)
        # self.search_input.setMinimumWidth()
        self.search_widget = QWidget(objectName='search', layout=search_layout)

        search_layout.addStretch()
        search_layout.addWidget(QToolButton(icon=icon('search.svg')))
        search_layout.addWidget(self.search_input)
        search_layout.addStretch()
        self._layout.addWidget(self.search_widget)

        self._notes_layout = QVBoxLayout()
        self._layout.addLayout(self._notes_layout)
        self._layout.addStretch()

        # Create the floating button to create new notes.
        # TODO add the add icon into it with correct alignment. Might need to make a subclass of
        # TODO QPushButton with a custom draw function.
        self.create_btn = QToolButton(text='Create Note',
                                      objectName='create-note-btn',
                                      parent=self,
                                      #   icon=icon('add.svg'),
                                      #   layoutDirection=QtCore.Qt.LeftToRight,
                                      toolButtonStyle=QtCore.Qt.ToolButtonTextBesideIcon
                                      )
        self.create_btn.setFixedSize(120, 40)
        self.create_btn.setProperty('btn-solid', '')

    def resizeEvent(self, event):
        # Reposition the create notes button to be fixed to the windows bottom right.
        self.create_btn.move(
            self.width() - self.create_btn.width() - 20,
            self.height() - self.create_btn.height() - 20
        )

    def _add_note(self, widget: NoteWidget):
        self._note_widgets.append(widget)
        self._notes_layout.addWidget(widget)

    def refresh_ui(self):
        for note in self._note_widgets:
            note.setParent(None)
            note.deleteLater()

        print(notes)

        for note in notes:
            self._add_note(NoteWidget(note))


test_note = Note('This is a title', 'Some text...', '32m ago', 'Matthew')

test_note.add_check(NoteCheck('some test checkbox'))
test_note.add_check(NoteCheck('another checkbox'))

notes.append(test_note)


def run_main(**kwargs):
    _maya_delete_ui(WTITLE, WOBJ)
    _maya_delete_workspace(WOBJ)

    NotesUI()

    if "dockable" in kwargs and kwargs["dockable"]:
        _maya_update_workspace(WOBJ)


if __name__ == '__main__':
    run_main()
