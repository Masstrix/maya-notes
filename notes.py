"""
#################################################################

Maya Notes

TODO - Have notes based on scene, project, or object.
TODO - Make a wrapper of QWidget that enables animation.
TODO - Allow tab indenting of checklists to create a "checklist group" so
TODO   you can have a sub tasks kind of setup.
TODO - Fix flickering of notes when searching.

This is a small script that impliments note taking into maya with a
simple to use interface. Notes can have checklists.

Requires Maya 2022 or newer for python 3
Author: Matthew Denton

#################################################################
"""
import os, json
from os.path import join, dirname

# Load the current package data.
package_json = None
with open(join(dirname(__file__), 'package.json')) as file:
    package_json = json.loads(file.read())

if package_json:
    __version__ = package_json['version']
    __author__ = package_json['author']

from dataclasses import dataclass
from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QDialog, QCheckBox, QLineEdit, QLabel, QPlainTextEdit, QSpacerItem, QSizePolicy, QToolButton, QScrollArea
from shiboken2 import wrapInstance
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya import cmds, OpenMayaUI
from maya.OpenMaya import MSceneMessage
from datetime import datetime, timedelta
from math import floor


WTITLE = 'Notes'
WOBJ = 'notes'
META_NODE = 'notesCache'
META_TAG = 'notes-meta'

notes = []  # Stores all notes currently loaded.


def save_notes():
    '''
    Saves all currently cached notes.
    '''
    notes_array = []

    # Convert all the notes into a json string to cache
    for note in notes:
        notes_array.append(note.serialize())

    # Create cache node if it does not exist in the scene already.
    if not cmds.objExists(META_NODE):
        cmds.createNode('unknown', name=META_NODE)
        cmds.addAttr(META_NODE, ln='data', dt='string')

    cmds.setAttr(f'{META_NODE}.data', json.dumps(notes_array), type='string')


def load_notes():
    '''
    Loads notes for the currently open scene.
    '''
    notes.clear()
    if not cmds.objExists(META_NODE):
        return # Don't even bother

    try:
        # try and load the data from the cahce node.
        data = json.loads(cmds.getAttr(f'{META_NODE}.data'))

        # Create a new Note pbject for every cached note.
        for noteData in data:
            noteMeta = json.loads(noteData)

            checklist = []
            for checkJson in noteMeta['checklist']:
                check = json.loads(checkJson)
                checklist.append(NoteCheck(check['text'], check['checked']))

            Note(
                title=noteMeta['title'],
                text=noteMeta['text'],
                created_date=datetime.strptime(noteMeta['created_date'], '%Y-%m-%d %H:%M:%S.%f'), # 2022-01-20 23:00:00.00
                author=noteMeta['author'],
                pinned=noteMeta['pinned'],
                checklist=checklist
            )
    except Exception:
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


def format_time(date: timedelta):
    '''
    Returns a timedelta in either just it's seconds, miniutes, hours or
    days time, only ever returing the largets time unit.
    '''
    seconds = date.seconds
    miniutes = floor(seconds / 60)
    hours = floor(miniutes / 60)
    days = date.days
    if days >= 1:
        return f'{days}d'
    if hours >= 1:
        return f'{hours}h'
    if miniutes >= 1:
        return f'{miniutes}m'
    return f'{seconds}s'


@dataclass
class NoteCheck:
    '''
    Simple note check that stores the check value of a note and the text assosiated 
    with the checkbox.

    A check can also have children added to it. If this has children then this will act as
    a main checked. The checked state of this would then only ever be true if all of the
    children are checked.
    '''
    text: str = ''
    checked: bool = False
    children: list = None

    def add_child(self, check):
        if self.children is None:
            self.children = []
        self.children.append(check)

    def serialize(self) -> str:
        json_data = {
            'checked': self.checked,
            'text': self.text
        }
        if self.children is not None and len(self.children) > 0:
            children = []
            for child in self.children:
                children.append(child.serialize())
            json_data['children'] = children
        return json.dumps(json_data)


@dataclass
class Note:
    """
    Stores information for a note.
    """
    title: str = ''
    text: str = ''
    created_date: datetime = None
    author: str = ''
    checklist: list = None
    linked_objects: list = None
    pinned: bool = False
    # date: InitVar[datetime] = None

    def __post_init__(self):
        if self.created_date is None:
            self.created_date = datetime.utcnow()
        if self.checklist is None:
            self.checklist = []

        # Save this newly created note to the scene.
        notes.append(self)

    def add_check(self, check: NoteCheck):
        if self.checklist is None:
            self.checklist = []
        self.checklist.append(check)

    def is_linked(self):
        return self.linked_objects is not None and len(self.linked_objects) > 0

    def has_checklist(self):
        
        count = len(self.checklist)
        if self.checklist is None or count == 0:
            return False
        return count > 1 or self.checklist[0].text != ''

    def serialize(self) -> str:
        json_data = {
            'title': self.title,
            'text': self.text,
            'created_date': str(self.created_date),
            'author': self.author,
            'pinned': self.pinned,
            'checklist': [],
            'linked_objects': []
        }
        if self.checklist is not None:
            checks = []
            for check in self.checklist:
                if check.text is not None and check.text != '':
                    checks.append(check.serialize())
            json_data['checklist'] = checks
        return json.dumps(json_data)


class WrappedTextWidget(QPlainTextEdit):
    '''
    Wrapper for QPlainTextEdit to create a version of the widget that verticly fits to
    the contained document text.
    '''
    focusOut = QtCore.Signal()
    focusIn = QtCore.Signal()
    tabPressed = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super(WrappedTextWidget, self).__init__(*args, **kwargs)
        self.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.preventTab = False

    def setPreventTab(self, override: bool):
        self.preventTab = override

    def paintEvent(self, event):
        super().paintEvent(event)
        document = self.document()
        font = self.fontMetrics()
        margins = self.contentsMargins()
        height = (document.lineCount() + 1) * font.lineSpacing()
        self.setFixedHeight(height + margins.top() + margins.bottom())

    def focusOutEvent(self, event):
        if self.preventTab and event.reason() == QtCore.Qt.TabFocusReason:
            return
        super().focusOutEvent(event)
        self.focusOut.emit()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focusIn.emit()

    def keyPressEvent(self, event):
        if self.preventTab and event.key() == QtCore.Qt.Key_Tab:
            self.tabPressed.emit()
        else:
            super().keyPressEvent(event)


class IconButton(QToolButton):

    def __init__(self, icon, hoverIcon: str = None, activeIcon: str = None, tip: str = None, **kwargs):
        super(IconButton, self).__init__(**kwargs)

        if tip is not None:
            self.setToolTip(tip)
            self.setStatusTip(tip)

        self._icon = icon
        self._hover_icon = hoverIcon
        self._active_icon = activeIcon
        self.setIcon(icon)

    def enterEvent(self, event):
        if self._hover_icon:
            self.setIcon(self._hover_icon)

    def leaveEvent(self, event):
        self.setIcon(self._icon)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self._active_icon:
            self.setIcon(self._active_icon)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._hover_icon:
            self.setIcon(self._hover_icon)
        else:
            self.setIcon(self._icon)


class TimerLabelWidget(QLabel):
    '''
    A simple Qt label that is rendered to display the time difference.
    '''

    def __init__(self, date: datetime, prefix: str = '', suffix: str = '', **kwargs):
        super(TimerLabelWidget, self).__init__(**kwargs)
        self.date = date
        self.prefix = prefix
        self.suffix = suffix

        timer = QtCore.QTimer(self)
        timer.timeout.connect(self._update_display)
        timer.start(1000)

        self._update_display()

    def setPrefix(self, prefix):
        self.prefix = prefix

    def setSuffix(self, suffix):
        self.suffix = suffix

    def _update_display(self):
        now = datetime.utcnow()
        self.setText(
            f'{self.prefix}{format_time(now - self.date)}{self.suffix}')


class NoteCheckWidget(QWidget):
    # tabbed = QtCore.Signal(object)

    def __init__(self, noteCheck: NoteCheck, note: Note):
        super(NoteCheckWidget, self).__init__()
        self.note_check = noteCheck
        self.note = note

        # Set the widgets layout
        self._layout = QHBoxLayout()
        self.setLayout(self._layout)
        self._layout.setSpacing(0)
        self.setContentsMargins(0, 0, 0, 0)

        # Create needed widgets
        self.checkbox = QCheckBox(checked=noteCheck.checked)
        self.text = WrappedTextWidget(noteCheck.text)
        self.text.setPlaceholderText('Add another item..')

        self.checkbox.stateChanged.connect(self._update_checked_status)
        self.text.textChanged.connect(self._update_text)
        self.text.setPreventTab(True)

        self._construct()

    def _construct(self):
        self._layout.addWidget(self.checkbox)
        self._layout.addWidget(self.text)

    def _update_text(self):
        self.note_check.text = self.text.toPlainText()
        save_notes()

    def _update_checked_status(self):
        self.note_check.checked = self.checkbox.isChecked()
        save_notes()

    def get_text(self) -> str:
        return self.note_check.text

    def is_checked(self) -> bool:
        return self.note_check.checked


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
    emptied = QtCore.Signal()

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

    def is_empty(self):
        # Return if the checklist is empty
        return len(self.items) == 0

    def _empty_item(self):
        # Return a new empty note check.
        check = NoteCheck()
        self.note.add_check(check)
        return NoteCheckWidget(check, self.note)

    def _load_items(self):
        # Loads all the checklist items from the note object in as a widget.
        if self.note.checklist is not None:
            for check in self.note.checklist:
                self.append(NoteCheckWidget(check, self.note))
        # if not self.items[-1].note_check.text == '':
        self.append(self._empty_item())

    def append(self, check: NoteCheckWidget):
        '''Append a new note check to the checklist'''
        self.items.append(check)
        self._layout.addWidget(check)

        # Connect signals
        check.text.focusOut.connect(lambda: self._lose_focus(check))
        check.text.textChanged.connect(lambda: self._update_text(check))

    def pop(self, index: int):
        widget = self.items.pop(index)
        self._layout.removeWidget(widget)
        self.note.checklist.remove(widget.note_check)
        widget.deleteLater()

    def remove(self, check: NoteCheckWidget):
        self.items.remove(check)
        self._layout.removeWidget(check)
        self.note.checklist.remove(check.note_check)
        check.deleteLater()

    def _update_text(self, check: NoteCheckWidget):
        index = self.items.index(check)
        size = len(self.items) - 1
        if index == size:
            if len(check.get_text()) > 0:
                self.append(self._empty_item())

        elif index < size and len(self.items[index + 1].get_text()) == 0 and len(check.get_text()) == 0:
            self.pop(-1)

    def _lose_focus(self, check: NoteCheckWidget):
        text = check.text.toPlainText()
        index = self.items.index(check)
        if len(text) == 0 and not (index == len(self.items) - 1 and len(self.items) > 1):
            self.remove(check)
        if self.is_empty():
            self.emptied.emit()
            self.append(self._empty_item())


class NoteWidget(QWidget):
    '''
    A widget to represent a Note object.
    '''

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
        self.title = WrappedTextWidget(
            note.title, placeholderText='Untiled Note')
        self.text = WrappedTextWidget(
            note.text, placeholderText='Write something here...')
        self.checklist = NoteChecklistWidget(note)

        self._construct()
        self._connect_signals()

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
        self._archive_btn = IconButton(icon('archive.svg'), icon(
            'archive-hover.svg'), icon('archive-active.svg'), tip='Archive this note')
        self._pin_btn = IconButton(icon('pin.svg'), icon(
            'pin-hover.svg'), icon('pin-active.svg'), tip='Delete this note')
        self._delete_btn = IconButton(icon('delete.svg'), icon(
            'delete-hover.svg'), icon('delete-active.svg'), tip='Pin this note to the top')
        self._listadd_btn = IconButton(icon('listadd.svg'), icon(
            'listadd-hover.svg'), icon('listadd-active.svg'), tip='Create a checklist')
        self._linked_icon = QToolButton(
            icon=icon('linked-object.svg'), visible=self.note.is_linked())

        tools.addStretch()
        tools.addWidget(self._actions_widget)
        # actions.addWidget(archive_btn)
        actions.addWidget(self._delete_btn)
        actions.addWidget(self._listadd_btn)
        actions.addWidget(self._pin_btn)
        tools.addWidget(self._linked_icon)

        self._tools_widget.setProperty('toolbar', '')
        self._tools_widget.setLayout(tools)

        # Data widgets in the center
        self._layout.addWidget(self.title)
        self._layout.addWidget(self.text)
        self._layout.addWidget(self.checklist)

        self.checklist.setVisible(self.note.has_checklist())
        self._listadd_btn.setVisible(not self.note.has_checklist())

        # Extra info widgets at the bottom
        self.info = TimerLabelWidget(
            self.note.created_date, suffix=f' ago    {self.note.author}')
        self._layout.addWidget(self.info)

        # Set the data tags for styling
        self.title.setProperty('tag', 'title')
        self.text.setProperty('tag', 'text')
        self.info.setProperty('tag', 'info')

    def _connect_signals(self):
        self._delete_btn.clicked.connect(self.delete)
        self._listadd_btn.clicked.connect(self.add_checklist)
        self._pin_btn.clicked.connect(self.pin)

        # Checklist connections
        self.checklist.emptied.connect(self.remove_checklist)

        # Text update connections
        self.title.textChanged.connect(self._update_title)
        self.text.textChanged.connect(self._update_text)

    def _update_title(self):
        self.note.title = self.title.toPlainText()
        save_notes()

    def _update_text(self):
        self.note.text = self.text.toPlainText()
        save_notes()

    def pin(self):
        self.note.pinned = True
        save_notes()

    def unpin(self):
        self.note.pinned = False
        save_notes()

    def delete(self):
        notes.remove(self.note)
        self.setParent(None)
        self.deleteLater()
        save_notes()

    def add_checklist(self):
        self.checklist.setVisible(True)
        self._listadd_btn.setVisible(False)
        save_notes()

    def remove_checklist(self):
        self.checklist.setVisible(False)
        self._listadd_btn.setVisible(True)
        save_notes()

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


class NotesUI(MayaQWidgetDockableMixin, QDialog):

    def __init__(self, parent=_maya_main_window()):
        super(NotesUI, self).__init__(parent)

        # make sure all the notes are loaded.
        load_notes()

        # an array of all the notes currently loaded in the UI
        self._note_widgets = []
        self.callbacks = []

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
        self._connect_signals()
        self.refresh_ui()
        self._create_callbacks()

    def _construct_ui(self):
        '''Construct all the elements needed to display the content.'''

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

    def _connect_signals(self):
        '''Connects all signals for the base ui'''
        self.create_btn.clicked.connect(self.create_new_note)
        self.search_input.textChanged.connect(self._update_search)

    def _create_callbacks(self):
        '''
        Create any and all callbacks needed to keep the ui up to date
        with the currently open scene.
        '''
        self.callbacks.append(MSceneMessage.addCallback(
            MSceneMessage.kAfterNew,
            self._reload_all
        ))
        self.callbacks.append(MSceneMessage.addCallback(
            MSceneMessage.kAfterOpen,
            self._reload_all
        ))

    def _reload_all(self, *args):
        '''Reloads all notes'''
        load_notes()
        self.refresh_ui()

    def hideEvent(self, event):
        '''
        Called when the window is closed. Maya just hides and dosn't actually call
        closeEvent so hideEvent is used instead.
        '''
        super().hideEvent(event)
        # Unregister all callbacks when window is closed.
        for callback in self.callbacks:
            MSceneMessage.removeCallback(callback)


    def resizeEvent(self, event):
        # Reposition the create notes button to be fixed to the windows bottom right.
        self.create_btn.move(
            self.width() - self.create_btn.width() - 20,
            self.height() - self.create_btn.height() - 20
        )

    def create_new_note(self):
        note = Note()
        widget = NoteWidget(note)
        self._add_note(widget)

    def refresh_ui(self):
        for widget in self._note_widgets:
            if widget is None: continue
            widget.setParent(None)
            widget.deleteLater()
        self._note_widgets.clear()
        for note in notes:
            self._add_note(NoteWidget(note))

    def _update_search(self):
        '''
        Update the current search input. This will hide any notes that
        don't match the current search.
        '''
        search = self.search_input.text().lower()
        for note_widget in self._note_widgets:
            note = note_widget.note
            in_text = search in note.text.lower()
            in_title = search in note.title.lower()
            note_widget.setVisible(in_text or in_title)

    def _add_note(self, widget: NoteWidget):
        self._note_widgets.append(widget)
        self._notes_layout.addWidget(widget)


def run_main(**kwargs):
    _maya_delete_ui(WTITLE, WOBJ)
    _maya_delete_workspace(WOBJ)

    noteui = NotesUI()
    noteui.show(dockable=True)

    if "dockable" in kwargs and kwargs["dockable"]:
        _maya_update_workspace(WOBJ)


if __name__ == '__main__':
    run_main()
