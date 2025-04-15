import wx
import wx.adv
import struct
from enum import Enum

class EXCLTextColor(Enum):
    White = 0
    Black = 1
    Red = 2
    LightBlue = 3
    Orange = 4
    Pink = 6
    Gray = 7

class EXCLEntry:
    def __init__(self):
        self.unk0 = bytearray(0x28)
        self.unk1 = bytearray(0x50)
        self.content = ""

class EXCL:
    def __init__(self):
        self.clear()

    def clear(self):
        """Очищает все данные файла"""
        self.magic = b'EXCL'
        self.unk0 = 0
        self.trash_padding = bytearray(0xC)
        self.text_color = EXCLTextColor.White
        self.entry_count = 0
        self.entry_offsets = []
        self.unmodified_text_lens = []
        self.entries = []

    def save(self):
        data = bytearray()
        data.extend(self.magic)
        data.extend(struct.pack('<I', self.unk0))
        data.extend(self.trash_padding)
        data.extend(struct.pack('<I', self.text_color.value))
        data.extend(struct.pack('<I', self.entry_count))

        next_entry_modifier = 0
        for i in range(self.entry_count):
            data.extend(struct.pack('<I', self.entry_offsets[i] + next_entry_modifier))
            length_difference = (len(self.entries[i].content) - self.unmodified_text_lens[i]) * 2
            next_entry_modifier += length_difference

        for entry in self.entries:
            data.extend(entry.unk0)
            data.extend(entry.unk1)
            if entry.content:
                data.extend(entry.content.encode('utf-16le'))
            data.extend(b'\x00\x00')

        return data

    def load(self, file_data):
        self.clear()  # Очищаем предыдущие данные

        self.magic = file_data[:4]
        if self.magic != b'EXCL':
            raise ValueError("File is not a valid Rhythm Thief script file")

        self.unk0 = struct.unpack('<I', file_data[4:8])[0]
        if self.unk0 in [6, 4]:
            raise ValueError(f"EXCL{self.unk0} detected. Unsupported EXCL variation.")

        self.trash_padding = file_data[8:20]
        self.text_color = EXCLTextColor(struct.unpack('<I', file_data[20:24])[0])
        self.entry_count = struct.unpack('<I', file_data[24:28])[0]

        offset = 28
        for _ in range(self.entry_count):
            self.entry_offsets.append(struct.unpack('<I', file_data[offset:offset+4])[0])
            offset += 4

        for _ in range(self.entry_count):
            entry = EXCLEntry()
            entry.unk0 = file_data[offset:offset+0x28]
            offset += 0x28
            entry.unk1 = file_data[offset:offset+0x50]
            offset += 0x50

            content = bytearray()
            while True:
                char = file_data[offset:offset+2]
                if char == b'\x00\x00':
                    offset += 2
                    break
                content.extend(char)
                offset += 2

            self.unmodified_text_lens.append(len(content) // 2)
            entry.content = content.decode('utf-16le')
            self.entries.append(entry)

class MainFrame(wx.Frame):
    def __init__(self, *args, **kw):
        super(MainFrame, self).__init__(*args, **kw)
        self.current_file = None
        self.file_modified = False
        self.current_file_path = None
        self.InitUI()

    def InitUI(self):
        menubar = wx.MenuBar()

        # File menu
        fileMenu = wx.Menu()
        open_item = fileMenu.Append(wx.ID_OPEN, "&Open\tCtrl+O", "Open a file")
        save_item = fileMenu.Append(wx.ID_SAVE, "&Save\tCtrl+S", "Save a file")
        save_as_item = fileMenu.Append(wx.ID_SAVEAS, "Save &As...", "Save file as...")
        fileMenu.AppendSeparator()
        exit_item = fileMenu.Append(wx.ID_EXIT, "E&xit\tCtrl+Q", "Quit the program")

        # Edit menu
        editMenu = wx.Menu()
        search_item = editMenu.Append(wx.ID_FIND, "&Search\tCtrl+F", "Search text")
        mass_replace_item = editMenu.Append(wx.ID_REPLACE, "&Mass Replace", "Mass replace text")

        # Tools menu
        toolsMenu = wx.Menu()
        export_item = toolsMenu.Append(wx.ID_ANY, "&Export as TXT", "Export as TXT")
        import_item = toolsMenu.Append(wx.ID_ANY, "&Import TXT", "Import TXT")

        # Help menu
        helpMenu = wx.Menu()
        about_item = helpMenu.Append(wx.ID_ABOUT, "&About", "About the program")

        menubar.Append(fileMenu, "&File")
        menubar.Append(editMenu, "&Edit")
        menubar.Append(toolsMenu, "&Tools")
        menubar.Append(helpMenu, "&Help")

        self.SetMenuBar(menubar)

        # Bind events
        self.Bind(wx.EVT_MENU, self.OnOpen, open_item)
        self.Bind(wx.EVT_MENU, self.OnSave, save_item)
        self.Bind(wx.EVT_MENU, self.OnSaveAs, save_as_item)
        self.Bind(wx.EVT_MENU, self.OnExit, exit_item)
        self.Bind(wx.EVT_MENU, self.OnSearch, search_item)
        self.Bind(wx.EVT_MENU, self.OnMassReplace, mass_replace_item)
        self.Bind(wx.EVT_MENU, self.OnExport, export_item)
        self.Bind(wx.EVT_MENU, self.OnImport, import_item)
        self.Bind(wx.EVT_MENU, self.OnAbout, about_item)

        # Create text control
        self.text_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE|wx.TE_RICH2)
        self.text_ctrl.Bind(wx.EVT_TEXT, self.OnTextChange)

        # Status bar
        self.CreateStatusBar()
        self.SetStatusText("Ready")

        # Layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.text_ctrl, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.SetSize((800, 600))
        self.SetTitle("Rhythm Script Text Editor")
        self.Centre()

        # Enable Drag and Drop
        self.SetDropTarget(FileDropTarget(self))

    def clear_current_file(self):
        """Очищает текущий файл и связанные данные"""
        self.current_file = None
        self.current_file_path = None
        self.file_modified = False
        self.text_ctrl.Clear()

    def OnOpen(self, event, file_path=None):
        if self.file_modified:
            response = self.prompt_save_changes()
            if response == wx.ID_CANCEL:
                return
            elif response == wx.ID_YES:
                if not self.OnSave(event):
                    return

        if file_path is None:
            with wx.FileDialog(self, "Open file", wildcard="Rhythm Thief Script File (*.bin)|*.bin",
                             style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST) as dlg:
                if dlg.ShowModal() == wx.ID_CANCEL:
                    return

                file_path = dlg.GetPath()

        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()

            # Создаем новый экземпляр файла
            new_file = EXCL()
            new_file.load(file_data)

            # Обновляем состояние программы
            self.clear_current_file()
            self.current_file = new_file
            self.current_file_path = file_path
            self.text_ctrl.SetValue("\n".join([entry.content for entry in self.current_file.entries]))
            self.file_modified = False
            self.SetStatusText(f"Opened: {file_path}")
            self.SetTitle(f"Rhythm Thief Script Editor - {file_path}")

        except Exception as e:
            wx.MessageBox(f"Error loading file: {str(e)}", "Error", wx.OK|wx.ICON_ERROR)

    def OnSave(self, event):
        if not self.current_file:
            wx.MessageBox("No file is currently open!", "Error", wx.OK|wx.ICON_ERROR)
            return False

        if not self.current_file_path:
            return self.OnSaveAs(event)

        return self.save_to_file(self.current_file_path)

    def OnSaveAs(self, event):
        if not self.current_file:
            wx.MessageBox("No file is currently open!", "Error", wx.OK|wx.ICON_ERROR)
            return False

        with wx.FileDialog(self, "Save file", wildcard="Rhythm Thief Script File (*.bin)|*.bin",
                         style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return False

            pathname = dlg.GetPath()
            return self.save_to_file(pathname)

    def save_to_file(self, path):
        try:
            # Обновляем содержимое текущего файла
            lines = self.text_ctrl.GetValue().split('\n')
            if len(lines) != len(self.current_file.entries):
                wx.MessageBox("Number of entries cannot be changed!", "Error", wx.OK|wx.ICON_ERROR)
                return False

            for i, line in enumerate(lines):
                self.current_file.entries[i].content = line

            # Сохраняем файл
            with open(path, 'wb') as f:
                f.write(self.current_file.save())

            self.file_modified = False
            self.current_file_path = path
            self.SetStatusText(f"Saved: {path}")
            self.SetTitle(f"Rhythm Thief Script Editor - {path}")
            return True

        except Exception as e:
            wx.MessageBox(f"Error saving file: {str(e)}", "Error", wx.OK|wx.ICON_ERROR)
            return False

    def prompt_save_changes(self):
        """Спрашивает пользователя о сохранении изменений"""
        dlg = wx.MessageDialog(self,
                             "Do you want to save changes to the current file?",
                             "Save Changes",
                             wx.YES_NO|wx.CANCEL|wx.ICON_QUESTION)
        result = dlg.ShowModal()
        dlg.Destroy()
        return result

    def OnSearch(self, event):
        search_term = wx.GetTextFromUser("Enter search term:", "Search")
        if not search_term:
            return

        text = self.text_ctrl.GetValue()
        if search_term not in text:
            wx.MessageBox("Text not found!", "Search", wx.OK|wx.ICON_INFORMATION)
            return

        # Подсветка найденного текста
        self.text_ctrl.SetFocus()
        self.text_ctrl.SetSelection(-1, -1)  # Сброс предыдущего выделения

        start_pos = text.find(search_term)
        if start_pos != -1:
            end_pos = start_pos + len(search_term)
            self.text_ctrl.SetSelection(start_pos, end_pos)
            self.text_ctrl.ShowPosition(start_pos)

    def OnMassReplace(self, event):
        dlg = wx.TextEntryDialog(self, "Enter text to replace:", "Mass Replace")
        if dlg.ShowModal() != wx.ID_OK:
            return
        old_text = dlg.GetValue()
        dlg.Destroy()

        dlg = wx.TextEntryDialog(self, f"Replace '{old_text}' with:", "Mass Replace")
        if dlg.ShowModal() != wx.ID_OK:
            return
        new_text = dlg.GetValue()
        dlg.Destroy()

        current_text = self.text_ctrl.GetValue()
        new_text = current_text.replace(old_text, new_text)
        self.text_ctrl.SetValue(new_text)
        self.file_modified = True

    def OnExport(self, event):
        if not self.current_file:
            wx.MessageBox("No file is currently open!", "Error", wx.OK|wx.ICON_ERROR)
            return

        with wx.FileDialog(self, "Export as TXT", wildcard="Text Files (*.txt)|*.txt",
                         style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return

            pathname = dlg.GetPath()
            try:
                with open(pathname, 'w', encoding='utf-8') as f:
                    f.write(self.text_ctrl.GetValue())
                wx.MessageBox("Export completed successfully!", "Export", wx.OK|wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"Error exporting file: {str(e)}", "Error", wx.OK|wx.ICON_ERROR)

    def OnImport(self, event):
        if self.file_modified:
            response = self.prompt_save_changes()
            if response == wx.ID_CANCEL:
                return
            elif response == wx.ID_YES:
                if not self.OnSave(event):
                    return

        with wx.FileDialog(self, "Import TXT", wildcard="Text Files (*.txt)|*.txt",
                         style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return

            pathname = dlg.GetPath()
            try:
                with open(pathname, 'r', encoding='utf-8') as f:
                    content = f.read()

                self.text_ctrl.SetValue(content)
                self.file_modified = True
                wx.MessageBox("Import completed successfully!", "Import", wx.OK|wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"Error importing file: {str(e)}", "Error", wx.OK|wx.ICON_ERROR)

    def OnAbout(self, event):
        image_path = "BPFC.jpg"
        image = wx.Image(image_path, wx.BITMAP_TYPE_ANY)
        width = 300
        height = 300
        image.Rescale(width, height, wx.IMAGE_QUALITY_HIGH)
        info = wx.adv.AboutDialogInfo()
        info.SetName("Rhythm Thief Script Editor")
        info.SetVersion("1.0")
        info.SetDescription("Editor for Rhythm Thief game script files")
        info.SetCopyright('© 2025 FILLDOR, FILLDOR\'s team, Бюро переводов \"Феникс и Ко\". All rights reserved.')
        info.SetDevelopers(["FILLDOR"])
        if image.IsOk():
            icon = wx.Icon()
            icon.CopyFromBitmap(image.ConvertToBitmap())
            info.SetIcon(icon)
        wx.adv.AboutBox(info)

    def OnExit(self, event):
        if self.file_modified:
            response = self.prompt_save_changes()
            if response == wx.ID_CANCEL:
                return
            elif response == wx.ID_YES:
                if not self.OnSave(event):
                    return

        self.Destroy()

    def OnTextChange(self, event):
        if not self.file_modified:
            self.file_modified = True
            if self.current_file_path:
                self.SetTitle(f"Rhythm Thief Script Editor - {self.current_file_path} *")

class FileDropTarget(wx.DropTarget):
    def __init__(self, main_frame):
        wx.DropTarget.__init__(self)
        self.main_frame = main_frame
        self.data_object = wx.FileDataObject()
        self.SetDataObject(self.data_object)

    def OnData(self, x, y, d):
        if self.GetData():
            file_path = self.data_object.GetFilenames()[0]
            self.main_frame.OnOpen(file_path=file_path)
        return d

def main():
    app = wx.App(False)
    frame = MainFrame(None)
    frame.Show(True)
    app.MainLoop()

if __name__ == "__main__":
    main()
