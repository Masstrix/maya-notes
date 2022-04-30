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

__version__ = (0, 1, 0)
__author__ = 'Matthew Denton'

from dataclasses import dataclass
from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QDialog, QCheckBox, QLineEdit, QLabel, QPushButton, QPlainTextEdit, QSpacerItem, QSizePolicy, QToolButton, QStyleOption, QScrollArea
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
    return wrapInstance(int(OpenMayaUI.MQtUtil.mainWindow()), QWidget)


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
    linked_objects: list = None

    def add_check(self, check: NoteCheck):
        if self.chesklist is None:
            self.chesklist = []
        self.chesklist.append(check)

    def is_linked(self):
        return self.linked_objects is not None and len(self.linked_objects) > 0


class WrappedTextWidget(QPlainTextEdit):
    '''
    Wrapper for QPlainTextEdit to create a version of the widget that verticly fits to
    the contained document text.
    '''

    def __init__(self, *args, **kwargs):
        super(WrappedTextWidget, self).__init__(*args, **kwargs)
        self.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

    def paintEvent(self, event):
        super().paintEvent(event)
        document = self.document()
        font = self.fontMetrics()
        margins = self.contentsMargins()
        height = (document.lineCount() + 1) * font.lineSpacing()
        self.setFixedHeight(height + margins.top() + margins.bottom())


class NoteCheckWidget(QWidget):

    def __init__(self, noteCheck: NoteCheck):
        super(NoteCheckWidget, self).__init__()
        self.note_check = noteCheck

        # Set the widgets layout
        self._layout = QHBoxLayout()
        self.setLayout(self._layout)
        self._layout.setSpacing(0)
        self.setContentsMargins(0, 0, 0, 0)

        # Create needed widgets
        self.checkbox = QCheckBox(checked=noteCheck.checked)
        self.text = WrappedTextWidget(noteCheck.text)

        self._construct()

    def _construct(self):
        self._layout.addWidget(self.checkbox)
        self._layout.addWidget(self.text)


class NoteChecklistWidget(QWidget):
    '''

    TODO handle the updating of the notes list within here.
        - Connect typing to check text input. If this is the last check append a
        new empty disabled check to add a new item to, this should not be saved as a
        new item until text is added to it. Otherwise if it's not the
        last element just update the notes data.

    TODO handle when the text of a note is empty, and focus is lost from the check,
        remove it from the checklist.
    '''

    def __init__(self, note: Note):
        '''
        note    :Note:  an instance of the note object this checklist is for.
        '''
        super(NoteChecklistWidget, self).__init__()

        # Keep the note handy so it can easily be updated and saved when
        # any of the checks are edited.
        self.note = note

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.setSpacing(0)

        self.items = []

        self._load_items()

    def _load_items(self):
        # Loads all the checklist items from the note object in as a widget.
        for check in self.note.chesklist:
            self.append(NoteCheckWidget(check))

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
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        # Create needed widgets
        self.title = WrappedTextWidget(note.title)
        self.text = WrappedTextWidget(note.text)
        self.checklist = NoteChecklistWidget(note)

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
        linked_icon = QToolButton(
            icon=icon('linked-object.svg'), visible=self.note.is_linked())

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
        self.info = QLabel(
            f'{self.note.created_date}         {self.note.author}')
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

        # Create and add the search bar widgets
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit(minimumWidth=250)
        # self.search_input.setMinimumWidth()
        self.search_widget = QWidget(objectName='search', layout=search_layout)

        search_layout.addStretch()
        search_layout.addWidget(QToolButton(icon=icon('search.svg')))
        search_layout.addWidget(self.search_input)
        search_layout.addStretch()
        self._layout.addWidget(self.search_widget)

        # Add the notes widget as in a scroll area.
        self._notes_layout = QVBoxLayout()
        self._notes_widget = QWidget(layout=self._notes_layout)
        self._notes_widget.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Maximum)
        self._layout.addWidget(QScrollArea(
            widgetResizable=True, widget=self._notes_widget))

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

        self._notes_widget.stackUnder(self.create_btn)

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

        for note in notes:
            self._add_note(NoteWidget(note))


test_note = Note('This is a title', 'Some text...', '32m ago',
                 'Matthew', linked_objects='Testing')
test_note.add_check(NoteCheck('some test checkbox'))
test_note.add_check(NoteCheck('another checkbox', True))
notes.append(test_note)


test_note_b = Note('testing everything on a note that can be tested.', 'This is a longer description that should take up multiple lines when the window is not to wide.', '32m ago')
test_note_b.add_check(NoteCheck('Singleton checkbox', True))
test_note_b.add_check(NoteCheck('')) # Empty checkbox'x should be ignred
test_note_b.add_check(NoteCheck('There was an empty checkbox above that was ignored.'))
test_note_b.add_check(NoteCheck('I have more...', children=[NoteCheck('Like meeeeee', True), NoteCheck('And me!')]))
test_note_b.add_check(NoteCheck('This is a longer task that should easily take up multiple lines to allow for checking of text wrapping.'))
notes.append(test_note_b)


def run_main(**kwargs):
    _maya_delete_ui(WTITLE, WOBJ)
    _maya_delete_workspace(WOBJ)

    NotesUI()

    if "dockable" in kwargs and kwargs["dockable"]:
        _maya_update_workspace(WOBJ)


if __name__ == '__main__':
    run_main()
