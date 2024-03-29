import os
import re
import sys
import glob
import pickle
import locale

import wx
import wx.media
import wx.gizmos as gizmos
import wx.lib.mixins.listctrl  as  listmix
from wx import xrc

import mutagen.id3
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError

class SortVirtList(
    wx.ListCtrl, 
    listmix.ListCtrlAutoWidthMixin, 
    listmix.ColumnSorterMixin,
    ):

    headers = []
    rows = []
    itemDataMap = {}
    scantime = 0

    def __init__(self):
        print "SortVirtList Init"
        p = wx.PreListCtrl()
        self.PostCreate(p)
        self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)

    def OnCreate(self, event):
        print "SortVirtList OnCreate", event
        self.attr1 = wx.ListItemAttr()
        self.attr1.SetBackgroundColour("white")
        listmix.ListCtrlAutoWidthMixin.__init__(self)
        listmix.ColumnSorterMixin.__init__(self, 20)

    def SearchData(self, term, col=None):
        index = -1
        searchData = {}
        for row in self.rows:
            if not col is None:
                coldata = row[col] 
            else:
                coldata = " ".join(row)
            if not coldata:
                continue
            found = True
            terms = term.split()
            try:
                for item in terms:
                    if item.lower() not in coldata.lower():
                        found = False
                        break
            except TypeError:
                print "COLDATA:", coldata
                print "ITEM:", item

            if found:
                index += 1
                searchData[index] = row
                print row

        self.itemDataMap = searchData
        self.itemIndexMap = self.itemDataMap.keys()
        self.SetItemCount(len(self.itemDataMap))

    def ClearSearch(self):
        self.itemDataMap = {}

        for i in range(0, len(self.rows)):
            self.itemDataMap[i] = self.rows[i]

        self.itemIndexMap = self.itemDataMap.keys()
        self.SetItemCount(len(self.itemDataMap))

    def estimateLens(self):
        headers = self.headers
        rows = self.rows
        if not rows:
            return

        buffer = 5
        rowrange = range(len(rows[0]))

        headlens = []
        for head in headers:
            headlens.append(len(headers) + 5)

        rowtots = []
        for i in rowrange:
            rowtots.append(0)

        rownums = []
        for i in rowrange:
            rownums.append(1)

        for row in rows:
            for i in rowrange:
                ilen = len(row[i])
                if ilen > headlens[i]:
                    rowtots[i] += ilen
                    rownums[i] += 1
        
        charWidth = self.GetCharWidth()
        for i in rowrange:
            self.SetColumnWidth(i, (charWidth * max(
                (rowtots[i] / rownums[i]),
                headlens[i]
            )))

    def ClearData(self):
        self.rows = []
        self.headers = []
        self.itemDataMap = {}
        self.scantime = 0

    def SetData(self, headers, rows):
        self.ClearAll()
        self.headers = headers
        self.rows.extend(rows)
        
        for i in range(len(headers)):
            self.InsertColumn(i, headers[i])
            self.SetColumnWidth(i, wx.LIST_AUTOSIZE)
        
        start = len(self.itemDataMap) - 1
        end = start + len(rows)
        for i in range(start, end):
            self.itemDataMap[i] = self.rows[i]
            
        self.itemIndexMap = self.itemDataMap.keys()
        self.SetItemCount(len(self.itemDataMap))
        self.estimateLens()

    def SaveData(self, filename):
        print "Saving %s" % filename
        print "SCANTIME:", self.scantime
        f = open(filename, 'w')
        try:
            pickle.dump((self.scantime, self.headers, self.rows), f)
        finally:
            f.close()

    def LoadData(self, filename):
        if os.path.isfile(filename):
            print "Loading %s" % filename
            f = open(filename)
            try:
                data = pickle.load(f)
                if len(data) == 3:
                    scantime, headers, rows = data 
                elif len(data) == 2:
                    headers, rows = data
                    scantime = 0
                self.SetData(headers, rows)
                print "SCANTIME:", self.scantime
                self.scantime = scantime
            finally:
                f.close()

    def OnColClick(self,event):
        event.Skip()

    def OnItemActivated(self, event):
        self.currentItem = event.m_itemIndex

    def getColumnText(self, index, col):
        item = self.GetItem(index, col)
        return item.GetText()

    def OnItemDeselected(self, evt):
        pass

    #---------------------------------------------------
    # These methods are callbacks for implementing the
    # "virtualness" of the list...

    def OnGetItemText(self, item, col):
        index=self.itemIndexMap[item]
        s = self.itemDataMap[index][col]
        return s

    def OnGetItemAttr(self, item):
        if item % 2 == 1:
            return self.attr1
        else:
            return None


    #---------------------------------------------------
    # Matt C, 2006/02/22
    # Here's a better SortItems() method --
    # the ColumnSorterMixin.__ColumnSorter() method already handles the ascending/descending,
    # and it knows to sort on another column if the chosen columns have the same value.

    def SortItems(self,sorter=cmp):
        print "SortItems"
        items = list(self.itemDataMap.keys())
        #items = list(map(
        #    lambda x: x.lower(),
        #    self.itemDataMap.keys()
        #))
        items.sort(sorter)
        self.itemIndexMap = items
        
        # redraw the list
        self.Refresh()

    def GetColumnSorter(self):
        return self.__InColSorter

    def __InColSorter(self, key1, key2):
        col = self._col
        ascending = self._colSortFlag[col]
        item1 = self.itemDataMap[key1][col].lower()
        item2 = self.itemDataMap[key2][col].lower()

        #--- Internationalization of string sorting with locale module
        if type(item1) == type('') or type(item2) == type(''):
            cmpVal = locale.strcoll(str(item1), str(item2))
        else:
            cmpVal = cmp(item1, item2)
        #---

        # If the items are equal then pick something else to make the sort value unique
        if cmpVal == 0:
            cmpVal = apply(cmp, self.GetSecondarySortValues(col, key1, key2))

        if ascending:
            return cmpVal
        else:
            return -cmpVal

    # Used by the ColumnSorterMixin, see wx/lib/mixins/listctrl.py
    def GetListCtrl(self):
        return self


class EditMediaList(SortVirtList, listmix.TextEditMixin):

    _created = False
    _origdata = None
    _origrow = -1
    _dirty = False
    _tabclose = False
    _rclick_items = []
    _menu_evt = None

    def __init__(self):
        print "EditMediaList Init"
        p = wx.PreListCtrl()
        self.PostCreate(p)
        self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRClick)
        self.AddRclickItem("Play", self._DoPlay)
        self.AddRclickItem("Edit", self.DoEdit)

    def GetSelectedId(self):
        index = -1
        for i in range(self.GetSelectedItemCount()):
            index = self.GetNextItem(
                item=index,
                state=wx.LIST_STATE_SELECTED
            )
            break
        return index

    def OnRClick(self, evt):
        menu = wx.Menu()
        count = 0
        # Kludge since we need to retain the menu evt click in case 
        # we do an edit.
        self._menu_evt = evt
        for title, callback in self._rclick_items:
            count += 1
            menu.Append( count, title )
            wx.EVT_MENU( menu, count, callback )
            #self.Bind(wx.EVT_MENU, callback, count)
        self.PopupMenu( menu, evt.GetPoint() )
        menu.Destroy()

    def OnLeftDown(self, evt=None):
        """ Only select with a single click """
        if self.editor.IsShown():
            self.CloseEditor()
        x,y = evt.GetPosition()
        row,flags = self.HitTest((x,y))
    
        evt.Skip()
        return

    def OnLeftDClick(self, evt):
        """ Call original click routine for double click """
        self.DoPlay(evt)

    def DoEdit(self, evt):
        listmix.TextEditMixin.OnLeftDown(self, self._menu_evt)

    def _DoPlay(self, evt):
        """ _DoPlay Helps the references turn out okay """
        self.DoPlay(evt)

    def DoPlay(self, evt):
        """ DoPlay Empty Method """
        print "EditMediaList.DoPlay"

    def OnCreate(self, event):
        print "EditMediaList OnCreate"
        if not self._created:
            self._created = True
            listmix.TextEditMixin.__init__(self)
            SortVirtList.OnCreate(self, event)

            # TextEditMixin contains bug making it impossible to select row 0.
            # Fix this ...
            self.curRow = -1
            self.curCol = -1

    def OnChar(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_TAB:
            self._tabclose = True
        else:
            self._tabclose = False
        listmix.TextEditMixin.OnChar(self, event)

    def OpenEditor(self, col, row): 
        if row != self._origrow:
            self._origrow = self.itemIndexMap[row]
            self._origdata = str(self.itemDataMap[self._origrow])
        listmix.TextEditMixin.OpenEditor(self, col, row)

    def AddRclickItem(self, title, callback):
        self._rclick_items.append((title, callback))

    def SetVirtualData(self, item, col, data):
        print "Set Virtual Data"
        index=self.itemIndexMap[item]
        self.itemDataMap[index][col] = data
        
        if self._tabclose:
            print "Same row"
            return
        
        if self._origdata == str(self.itemDataMap[index]):
            print "Data did not change."
            return

        print "Data changed!"
        self._dirty = True
        #SortVirtList.SetVirtualData(self, item, col, data)
        #self.SetStringItem(self, item, col, data)
        artist = self.itemDataMap[index][0]
        title = self.itemDataMap[index][1]
        genre = self.itemDataMap[index][2]
        mtype = self.itemDataMap[index][3]
        path = self.itemDataMap[index][4]

        validexts = ['.mp3', '.ogg']
        name, ext = os.path.splitext(path)
        if ext == ".cdg":
            candidates = glob.glob("%s.*" % name)
            for candidate in candidates:
                name, ext = os.path.splitext(candidate)
                if ext in validexts:
                    path = candidate
                    break

        if mtype in ('mp3', '.mp3'):
            m = MP3(path, ID3=EasyID3)
            try:
                m.add_tags(ID3=EasyID3)
            except mutagen.id3.error:
                print "Already has tag"
        elif mtype in ('ogg', 'ogg'):
            m = OggVorbis(path)
        else:
            print "Unrecognized type."
            return

        m['title'] = title
        m['artist'] = artist
        m['genre'] = genre
        m.save()
        print "Updated data."


class MusicList(EditMediaList):
    def setupData(self, datafile):
        self.datafile = datafile
        self.LoadData(datafile) 

    def SetVirtualData(self, *args, **kwds):
        EditMediaList.SetVirtualData(self, *args, **kwds)
        if self._dirty:
            self.SaveData(self.datafile)
        self._dirty = False


class Playlist_list(gizmos.EditableListBox):
#class Playlist_list(wx.ListCtrl):

    singers = {}

    def __init__(self, *args, **kwds):
        gizmos.EditableListBox.__init__(self, *args, **kwds)

    def SetData(self, headers, rows):
        self.ClearAll()
        self.headers = headers
        self.rows.extend(rows)

        for i in range(len(headers)):
            self.InsertColumn(i, headers[i])
            self.SetColumnWidth(i, wx.LIST_AUTOSIZE)
        
        start = len(self.itemDataMap) - 1
        end = start + len(rows)
        for i in range(start, end):
            self.itemDataMap[i] = self.rows[i]

        self.itemIndexMap = self.itemDataMap.keys()
        self.SetItemCount(len(self.itemDataMap))

    def addToList(self, singer, artist, title, filename, archive):
        strings = self.GetStrings()
        if singer != 'local':
            singer_pos = self.singers.get(singer)
            if singer_pos:
                print "Singer found: ", singer
            else:
                singer_pos = len(self.singers)
                self.singers[singer] = singer_pos
                print "Added singer %s at #%s" % (singer, singer_pos)

            for idx in range(len(strings)):
                if strings[idx].split("  |  ")[0] == singer:
                    print "Already had a song, removing."
                    strings.pop(idx)
                    print "Inserting new song..."
                    strings.insert(idx, "  |  ".join((singer, artist, title, filename, archive)))
                    print "Saving data."
                    self.SetStrings(strings)
                    print "All set."
                    return 

        strings.append("  |  ".join((singer, artist, title, filename, archive)))
        self.SetStrings(strings)
        print "Added to list:", self.GetStrings()

    def delItem(self, singer, artist, title, filename, archive):
        strings = self.GetStrings()
        strings.remove("  |  ".join((singer, artist, title, filename, archive)))
        self.SetStrings(strings)
        print "Removed from list:", self.GetStrings()

    def getCurrent(self):
        index = -1
        playlistCtrl = self.GetListCtrl()
        index = playlistCtrl.GetNextItem(
            index,
            state=wx.LIST_STATE_SELECTED
        )
        data = playlistCtrl.GetItem(index).GetText()
        print "Got: ", data
        return data.split("  |  ")
    
    def selectNext(self):
        index = -1
        playlistCtrl = self.GetListCtrl()
        numItems = playlistCtrl.GetItemCount()
        index = playlistCtrl.GetNextItem(
            index,
            state=wx.LIST_STATE_SELECTED
        )
        next = (index + 1) % numItems
        playlistCtrl.SetItemState(
                index, 
                0,
                wx.LIST_STATE_SELECTED
        )
        playlistCtrl.SetItemState(
                next, 
                wx.LIST_STATE_SELECTED,
                wx.LIST_STATE_SELECTED
        )

    def selectPrev(self):
        index = -1
        playlistCtrl = self.GetListCtrl()
        numItems = playlistCtrl.GetItemCount()
        index = playlistCtrl.GetNextItem(
            index,
            state=wx.LIST_STATE_SELECTED
        )

        if index > 0:
            prev = index - 1
        else:
            prev = numItems - 1

        playlistCtrl.SetItemState(
                index, 
                0,
                wx.LIST_STATE_SELECTED
        )
        playlistCtrl.SetItemState(
                prev, 
                wx.LIST_STATE_SELECTED,
                wx.LIST_STATE_SELECTED
        )

