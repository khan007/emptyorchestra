#!/usr/bin/env python

# pycdg - CDG/MP3+G Karaoke Player

# Copyright (C) 2007  Kelvin Lawson (kelvinl@users.sourceforge.net)
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


# OVERVIEW
#
# pycdg is a CDG karaoke player which supports MP3+G and OGG+G tracks.
#
# The player uses the pygame library (www.pygame.org), and can therefore
# run on any operating system that runs pygame (currently Linux, Windows
# and OSX).
#
# You can use this file as a standalone player, or together with
# PyKaraoke. PyKaraoke provides a graphical user interface, playlists,
# searchable song database etc.
#
# For those writing a media player or similar project who would like
# CDG support, this module has been designed to be easily incorporated
# into such projects and is released under the LGPL.


# REQUIREMENTS
#
# pycdg requires the following to be installed on your system:
# . Python (www.python.org)
# . Pygame (www.pygame.org)

# . Numeric module (numpy.sourceforge.net) (actually, this is required
#    only if you do not use the compiled C low-level CDG implementation in
#    _pycdgAux.c)


# USAGE INSTRUCTIONS
#
# To start the player, pass the CDG filename/path on the command line:
#       python pycdg.py /songs/theboxer.cdg
#
# You can also incorporate a CDG player in your own projects by
# importing this module. The class cdgPlayer is exported by the
# module. You can import and start it as follows:
#   import pycdg
#   player = pycdg.cdgPlayer("/songs/theboxer.cdg")
#   player.Play()
# If you do this, you must also arrange to call pycdg.manager.Poll()
# from time to time, at least every 100 milliseconds or so, to allow
# the player to do its work.
#
# The class also exports Close(), Pause(), Rewind(), GetPos().
#
# There are two optional parameters to the initialiser, errorNotifyCallback
# and doneCallback:
#
# errorNotifyCallback, if provided, will be used to print out any error
# messages (e.g. song file not found). This allows the module to fit 
# together well with GUI playlist managers by utilising the same GUI's
# error popup window mechanism (or similar). If no callback is provided,
# errors are printed to stdout. errorNotifyCallback should take one 
# parameter, the error string, e.g.:
#   def errorPopup (ErrorString):
#       msgBox (ErrorString)
#
# doneCallback can be used to register a callback so that the player
# calls you back when the song is finished playing. The callback should
# take no parameters, e.g.:
#   def songFinishedCallback():
#       msgBox ("Song is finished")
#
# To register callbacks, pass the functions in to the initialiser:
#   cdgPlayer ("/songs/theboxer.cdg", errorPopup, songFinishedCallback)
# These parameters are optional and default to None.
#
# If the initialiser fails (e.g. the song file is not present), __init__
# raises an exception.


# IMPLEMENTATION DETAILS
#

# pycdg is implemented as a handful of python modules.  All of the CDG
# decoding is handled in the C module _pycdgAux.c, or in the
# equivalent (but slightly slower) pycdgAux.py if the C module is not
# available for some reason.  This Python implementation of
# pycdgAux.py uses the python Numeric module, which provides fast
# handling of the arrays of pixel data for the display.
#
# Audio playback and video display capabilities come from the pygame
# library.
#
# All of the information on the CDG file format was learned
# from the fabulous "CDG Revealed" tutorial at www.jbum.com.
#

# Previous implementations ran the player within a thread; this is no
# longer the case.  Instead, it is the caller's responsibility to call
# pycdg.manager.Poll() every once in a while to ensure that the player
# gets enough CPU time to do its work.  Ideally, this should be at
# least every 100 milliseconds or so to guarantee good video and audio
# response time.
#
# At each call to Poll(), the player checks the current time in the
# song. It reads the CDG file at the correct location for the current
# position of the song, and decodes the CDG commands stored there. If
# the CDG command requires a screen update, a local array of pixels is
# updated to reflect the new graphic information. Rather than update
# directly to the screen for every command, updates are cached and
# output to the screen a certain number of times per second
# (configurable). Performing the scaling and blitting required for
# screen updates might consume a lot of CPU horsepower, so we reduce
# the load further by dividing the screen into 24 segments. Only those
# segments that have changed are scaled and blitted. If the user
# resizes the window or we get a full-screen modification, the entire
# screen is updated, but during normal CD+G operation only a small
# number of segments are likely to be changed at update time.
#
# NOTE: Pygame does not currently support querying the length
# of an MP3 track, therefore the GetLength() method is not
# currently implemented.
#
# Here follows a description of the important data stored by
# the class:
#
# CdgPacketReader.__cdgColourTable[]
# Store the colours for each colour index (0-15).
# These are set using the load colour look up table commands.
#
# CdgPacketReader.__cdgSurfarray[300][216]
# Surfarray object containing pixel colours for the full 300x216 screen.
# The border area is not actually displayed on the screen, however we
# need to store the pixel colours there as they are set when Scroll
# commands are used. This stores the actual pygame colour value, not
# indeces into our colour table.
#
# CdgPacketReader.__cdgPixelColours[300][216]
# Store the colour index for every single pixel. The values stored
# are indeces into our colour table, rather than actual pygame
# colour representations. It's unfortunate that we need to store 
# all this data, when in fact the pixel colour is available from
# cdgSurfarray, but we need it for the Tile Block XOR command.
# The XOR command performs an XOR of the colour index currently
# at the pixel, with the new colour index. We therefore need to
# know the actual colour index at that pixel - we can't do a 
# get_at() on the screen, or look in cdgSurfarray, and map the RGB
# colour back to a colour index because some CDG files have the 
# same colour in two places in the table, making it impossible to
# determine which index is relevant for the XOR.
#
# CdgPacketReader.__cdgPresetColourIndex 
# Preset Colour (index into colour table)
#
# CdgPacketReader.__cdgPresetColourIndex 
# Border Colour (index into colour table)
#
# CdgPacketReader.__updatedTiles
# Bitmask to mark which screen segments have been updated.
# This is used to reduce the amount of effort required in
# scaling the output video. This is an expensive operation
# which must be done for every screen update so we divide
# the screen into 24 segments and only update those segments
# which have actually been updated.

from mock import Mock

import os
import glob
import tempfile
import shutil
import zipfile

from pykconstants import *
from pykplayer import pykPlayer 
import sys, pygame, os, string, math, time
from pygame.locals import *

if os.name == 'nt':
    os.environ['SDL_VIDEODRIVER'] = 'windib'

# Import the optimised C version if available, or fall back to Python
try:
    import _pycdgAux as aux_c
except ImportError:
    aux_c = None

try:
    import pycdgAux as aux_python
except ImportError:
    aux_python = None

CDG_DISPLAY_WIDTH   = 288
CDG_DISPLAY_HEIGHT  = 192

# Screen tile positions
# The viewable area of the screen (294x204) is divided into 24 tiles
# (6x4 of 49x51 each). This is used to only update those tiles which
# have changed on every screen update, thus reducing the CPU load of
# screen updates. A bitmask of tiles requiring update is held in
# cdgPlayer.UpdatedTiles.  This stores each of the 4 columns in
# separate bytes, with 6 bits used to represent the 6 rows.
TILES_PER_ROW           = 6
TILES_PER_COL           = 4
TILE_WIDTH              = CDG_DISPLAY_WIDTH / TILES_PER_ROW
TILE_HEIGHT             = CDG_DISPLAY_HEIGHT / TILES_PER_COL

# cdgPlayer Class
class cdgPlayer(pykPlayer):
    # Initialise the player instace

    def __init__(
            self, 
            cdgfile,
            size=(640,480),
            fullscreen=False,
            zippath=None,
            offsetTime=0,
            errorNotifyCallback=None,
            doneCallback=None
        ):

        pykPlayer.__init__(self, cdgfile, errorNotifyCallback, doneCallback)

        # With the nomusic option no music will be played.
        soundFileData = None
        self.State = STATE_INIT
        self.InternalOffsetTime = offsetTime
        self.PlayTime = 0
        self.PlayStartTime = 0
        self.PlayFrame = 0
        self.displaySize = size
        self.fullScreen = fullscreen 
        self.tempdir = tempfile.mkdtemp()
        # Check for a matching mp3 or ogg file.  Check extensions
        # in the following order.
        self.validexts = [
            '.wav', '.ogg', '.mp3'
        ]

        print "Get soundFileData"
        if zippath:
            print "Opening zip, %s" % zippath
            cdgfile, soundFilePath = self._extractZipData(cdgfile, zippath)
        else:
            basepath = os.path.splitext(cdgfile)[0]
            soundFilePath = None
            candidates = glob.glob("%s.*" % basepath)
            for candidate in candidates:
                name, ext = os.path.splitext(candidate)
                if ext.lower() in self.validexts:
                    soundFilePath = candidate
                    break

            if not soundFilePath:
                ErrorString = "There is no mp3 or ogg file to match :", cdgfile 
                self.ErrorNotifyCallback (ErrorString)
                raise 'NoSoundFile'

        print "Get cdg file data."
        f = open(cdgfile, 'rb')
        try:
            self.cdgFileData = f.read()
        finally:
            f.close()

        # Handle a bug in pygame (pre-1.7) which means that the position
        # timer carries on even when the song has been paused.
        self.pauseOffsetTime = 0
        self.cdgZoom = 'soft'
        self.displayDepth = 8
        self.displayFlags = pygame.RESIZABLE | pygame.HWSURFACE
        if self.fullScreen:
            self.displayFlags |= pygame.FULLSCREEN

        print "Init player"
        pygame.mixer.pre_init(44100, -16, 2, 4096)    
        pygame.init()
        pygame.mixer.init(44100, -16, 2, 4096)    
        #pygame.mixer.pre_init(44100, -16, 2)    
        pygame.display.init()
        pygame.display.set_caption(cdgfile)
        #pygame.mouse.set_visible(True)
        pygame.mouse.set_visible(False)
        self.display = pygame.display.set_mode(self.displaySize, self.displayFlags)
        self.displayTime = pygame.time.get_ticks()
        self.display.fill((100,100,100))

        print "Fill surface"
        self.surface = pygame.Surface(self.displaySize)
        self.surface.fill((128, 128, 0))
        # A working surface for blitting tiles, one at a time.
        self.workingTile = pygame.Surface((TILE_WIDTH, TILE_HEIGHT),
                                          0, self.surface)

        # A surface that contains the set of all tiles as they are to
        # be assembled onscreen.  This surface is kept at the original
        # scale, then zoomed to display size.  It is only used if
        # settings.CdgZoom == 'soft'.
        self.workingSurface = pygame.Surface((CDG_DISPLAY_WIDTH, CDG_DISPLAY_HEIGHT),
                                             pygame.HWSURFACE,
                                             self.surface)
        #self.workingSurface = self.display
        self.borderColour = None
        print "Compute display size"
        self.computeDisplaySize()
        aux = aux_c
        if not aux: 
            print "Using Python implementation of CDG interpreter."
            aux = aux_python
        else:
            print "Using C based CDG interpreter."
        print "Open cdg and sound files"
        # Open the cdg and sound files
        self.packetReader = aux.CdgPacketReader(self.cdgFileData, self.workingTile)
        print "test for sound file data"
        if soundFilePath:
            print "YES"
            # Play the music normally.
            audioProperties = None
            print "Use mp3 settings?"
            #if manager.settings.UseMp3Settings:
            print "Get audio properties"
            audioProperties = self.getAudioProperties(soundFilePath)
            #    print self.soundFileData
            print audioProperties

            if audioProperties == None:
                print "None audio properties"
                audioProperties = (None, None, None)
            try:
                print "Try open audio"
                #manager.OpenAudio(*audioProperties)
                print "Try music load: ", soundFilePath
                pygame.mixer.music.load(soundFilePath)
                print "OK"
            except:
                print "Oh noes!"
                self.Close()
                raise

            # Set an event for when the music finishes playing
            print "Set end event"
            pygame.mixer.music.set_endevent(pygame.USEREVENT)

        else:
            # Don't play anything.
            self.InternalOffsetTime = 0
            
        print "set to beginning"
        # Set the CDG file at the beginning
        self.cdgReadPackets = 0
        self.cdgPacketsDue = 0
        self.LastPos = self.curr_pos = 0

        # Some session-wide constants.
        self.ms_per_update = (1000.0 / 30)        

    def __del__(self):
        if self.tempdir:
            shutil.rmtree(self.tempdir)
            self.tempdir = None
        pykPlayer.__del__(self)

    def initPlayer(self):
        #pygame.mixer.pre_init(44100, -16, 2, 1024)    
        pygame.init()

    def WaitForPlayer(self):
        while self.State != STATE_CLOSED:
            try:
                self.Poll()
            except RuntimeError:
                self.State = STATE_PLAYING
                ret = pygame.mixer.music.play()
                print "Played ret:", ret

    def handleEvent(self, event):
        # Only handle resize events 250ms after opening the
        # window. This is to handle the bizarre problem of SDL making
        # the window small automatically if you set
        # SDL_VIDEO_WINDOW_POS and move the mouse around while the
        # window is opening. Give: it some time to settle.
        if event.type == pygame.VIDEORESIZE and pygame.time.get_ticks() - self.displayTime > 250:

            # Tell the player we are about to resize. This is required
            # for pympg.
            self.doResizeBegin()
            # Do the resize
            self.displaySize = event.size
            self.WinSize = tuple(self.displaySize)
            pygame.display.set_mode(event.size, self.displayFlags, self.displayDepth)
            self.doResize(event.size)

            # Tell the player we have finished resizing 
            self.doResizeEnd()
        elif event.type == pygame.USEREVENT:
            print "Done playing, exiting..."
            self.Close()
        elif event.type == pygame.QUIT:
            print "pycdg Close"
            self.Close()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.Close()
            elif event.key == pygame.K_PAUSE:
                self.Pause()
            elif event.key == pygame.K_SPACE:
                self.Pause()
            elif event.key == pygame.K_f:
                if self.fullScreen:
                    print "clear fullScreen"
                    self.displayFlags &= ~pygame.FULLSCREEN
                    pygame.display.set_mode(self.displaySize, self.displayFlags, self.displayDepth)
                    self.fullScreen = False
                else:
                    print "set fullScreen"
                    self.displayFlags |= pygame.FULLSCREEN
                    pygame.display.set_mode(self.displaySize, self.displayFlags, self.displayDepth)
                    self.fullScreen = True
            elif event.key == pygame.K_RIGHT:
                self.InternalOffsetTime += 50
                print "Offset:", self.InternalOffsetTime
            elif event.key == pygame.K_LEFT:
                self.InternalOffsetTime -= 50
                print "Offset:", self.InternalOffsetTime
                #pygame.display.toggle_fullscreen()

        #self.handleEvent(event)

    def handleEvents(self):
        for event in pygame.event.get():
            self.handleEvent(event)

    def Poll(self):
        self.handleEvents()
        self.doStuff()
        # Wait a bit to save on wasteful CPU usage.
        pygame.time.wait(1)


    def doPlay(self):
        self.State = STATE_PLAYING
        ret = pygame.mixer.music.play()
        print "Played ret:", ret

    # Pause the song - Use Pause() again to unpause
    def doPause(self):
        pygame.mixer.music.pause()
        self.PauseStartTime = self.GetPos()

    def doUnpause(self):
        self.pauseOffsetTime = self.pauseOffsetTime + (self.GetPos() - self.PauseStartTime)
        pygame.mixer.music.unpause()

    # you must call Play() to restart. Blocks until pygame is initialised
    def doRewind(self):
        # Reset the state of the packet-reading thread
        self.cdgReadPackets = 0
        self.cdgPacketsDue = 0
        self.LastPos = 0
        # No need for the Pause() fix anymore
        self.pauseOffsetTime = 0
        # Move file pointer to the beginning of the file
        self.packetReader.Rewind()

        #if self.soundFileData:
            # Actually stop the audio
        pygame.mixer.music.rewind()
        pygame.mixer.music.stop()

    # Get the current time (in milliseconds). Blocks if pygame is
    # not initialised yet.
    def GetPos(self):
        pos = pygame.mixer.music.get_pos()
        if pos < 0:
            print "Negative GetPOS (%s), this is not normal" % pos
            raise RuntimeError, "GetPOS Failed."
        else:
            return pos

    def SetupOptions(self):
        """ Initialise and return optparse OptionParser object,
        suitable for parsing the command line options to this
        application. """

        parser = pykPlayer.SetupOptions(self, usage = "%prog [options] <CDG file>")

        # Remove irrelevant options.
        parser.remove_option('--font-scale')
        
        return parser


    def shutdown(self):
        # This will be called by the pykManager to shut down the thing
        # immediately.
        #pygame.mixer.music.stop()
        #pygame.mixer.music = None
        pygame.mixer.quit()

        # Make sure our surfaces are deallocated before we call up to
        # CloseDisplay(), otherwise bad things can happen.
        self.workingSurface = None
        self.workingTile = None
        self.packetReader = None
        pykPlayer.shutdown(self)
        pygame.display.quit()
        if self.tempdir:
            shutil.rmtree(self.tempdir)
            self.tempdir = None
            
    def doStuff(self):
        pykPlayer.doStuff(self)
        # Check whether the songfile has moved on, if so
        # get the relevant CDG data and update the screen.
        if self.State == STATE_PLAYING or self.State == STATE_CAPTURING:
            #self.curr_pos = self.GetPos() + self.InternalOffsetTime + manager.settings.SyncDelayMs - self.pauseOffsetTime
            self.curr_pos = self.GetPos() + self.InternalOffsetTime

            self.cdgPacketsDue = int((self.curr_pos * 300) / 1000)
            numPackets = self.cdgPacketsDue - self.cdgReadPackets
            if numPackets > 0:
                if not self.packetReader.DoPackets(numPackets):
                    # End of file.
                    print "End of file on cdg."
                    self.Close()
                self.cdgReadPackets += numPackets

            # Check if any screen updates are now due.
            if (self.curr_pos - self.LastPos) > self.ms_per_update:
                self.cdgDisplayUpdate()
                self.LastPos = self.curr_pos

    #def handleEvent(self, event):
    #    pykPlayer.handleEvent(self, event)

    def doResize(self, newSize):
        print "doResize"
        self.computeDisplaySize()
    
        if self.borderColour != None:
            self.surface.fill(self.borderColour)

        self.packetReader.MarkTilesDirty()

    def computeDisplaySize(self):
        print "ComputeDisplaySize"
        """ Figures out what scale and placement to use for blitting
        tiles to the screen.  This must be called at startup, and
        whenever the window size changes. """
        
        winWidth, winHeight = self.displaySize

        # Compute an appropriate uniform scale to letterbox the image
        # within the window
        scale = min(float(winWidth) / CDG_DISPLAY_WIDTH,
                    float(winHeight) / CDG_DISPLAY_HEIGHT)
        if self.cdgZoom == 'none':
            scale = 1
        elif self.cdgZoom == 'int':
            if scale < 1:
                scale = 1.0/math.ceil(1.0/scale)
            else:
                scale = int(scale)
        self.displayScale = scale

        scaledWidth = int(scale * CDG_DISPLAY_WIDTH)
        scaledHeight = int(scale * CDG_DISPLAY_HEIGHT)

        if self.cdgZoom == 'full':
            # If we are allowing non-proportional scaling, allow
            # scaledWidth and scaledHeight to be independent.
            scaledWidth = winWidth
            scaledHeight = winHeight

        # And the center of the display after letterboxing.
        self.displayRowOffset = (winWidth - scaledWidth) / 2
        self.displayColOffset = (winHeight - scaledHeight) / 2

        # Calculate the scaled width and height for each tile
        if self.cdgZoom == 'soft':
            self.displayTileWidth = CDG_DISPLAY_WIDTH / TILES_PER_ROW
            self.displayTileHeight = CDG_DISPLAY_HEIGHT / TILES_PER_COL
        else:
            self.displayTileWidth = scaledWidth / TILES_PER_ROW
            self.displayTileHeight = scaledHeight / TILES_PER_COL

    def getAudioProperties(self, soundFilePath):
        """ Attempts to determine the samplerate, etc., from the
        specified filename.  It would be nice to know this so we can
        configure the audio hardware to the same properties, to
        minimize run-time resampling. """

        # Ideally, SDL would tell us this (since it knows!), but
        # SDL_mixer doesn't provide an interface to query this
        # information, so we have to open the soundfile separately and
        # try to figure it out ourselves.

        audioProperties = None
        ext = os.path.splitext(soundFilePath)[1]
        print "MP3?", ext
        if ext == '.mp3':
            print "Yes mp3!"
            audioProperties = self.getMp3AudioProperties(soundFilePath)

        return audioProperties

    def getMp3AudioProperties(self, soundFilePath):
        """ Attempts to determine the samplerate, etc., from the
        specified filename, which is known to be an mp3 file. """

        # Hopefully, we have MP3Info.py available.
        try:
            print "Try importing MP3Info"
            import MP3Info
            print "OK"
        except:
            print "FAIL!"
            return None

        import cStringIO
        f = open(soundFilePath, 'rb')
        try:
            data = f.read()
        finally:
            f.close()
        m = MP3Info.MPEG(cStringIO.StringIO(data))

        channels = 1
        if 'stereo' in m.mode:
            channels = 2

        audioProperties = (m.samplerate, -16, channels)
        return audioProperties

    # Actually update/refresh the video output
    def cdgDisplayUpdate(self):
        # This routine is responsible for taking the unscaled output
        # pixel data from self.cdgSurfarray, scaling it and blitting
        # it to the actual display surface. The viewable area of the
        # unscaled surface is 294x204 pixels.  Because scaling and
        # blitting are heavy operations, we divide the screen into 24
        # tiles, and only scale and blit those tiles which have been
        # updated recently.  The CdgPacketReader class
        # (self.packetReader) is responsible for keeping track of
        # which areas of the screen have been modified.

        # There are four different approaches for blitting tiles onto
        # the display:

        # settings.CdgZoom == 'none':
        #   No scaling.  The CDG graphics are centered within the
        #   display.  When a tile is dirty, it is blitted directly to
        #   manager.surface.  After all dirty tiles have been blitted,
        #   we then use display.update to flip only those rectangles
        #   on the screen that have been blitted.

        # settings.CdgZoom = 'quick':
        #   Trivial scaling.  Similar to 'none', but each tile is
        #   first scaled to its target scale using
        #   pygame.transform.scale(), which is quick but gives a
        #   pixelly result.  The scaled tile is then blitted to
        #   manager.surface.

        # settings.CdgZoom = 'int':
        #   The same as 'quick', but the scaling is constrained to be
        #   an integer multiple or divisor of its original size, which
        #   may reduce artifacts somewhat.

        # settings.CdgZoom = 'full':
        #   The same as 'quick', but the scaling is allowed to
        #   completely fill the window in both x and y, regardless of
        #   aspect ratio constraints.

        # settings.CdgZoom = 'soft':
        #   Antialiased scaling.  We blit all tiles onto
        #   self.workingSurface, which is maintained as the non-scaled
        #   version of the CDG graphics, similar to 'none'.  Then,
        #   after all dirty tiles have been blitted to
        #   self.workingSurface, we use pygame.transform.rotozoom() to
        #   make a nice, antialiased scaling of workingSurface to
        #   manager.surface, and then flip the whole display.  (We
        #   can't scale and blit the tiles one a time in this mode,
        #   since that introduces artifacts between the tile edges.)
        
        borderColour = self.packetReader.GetBorderColour()
        if borderColour != self.borderColour:
            # When the border colour changes, blit the whole screen
            # and redraw it.
            self.borderColour = borderColour
            print "BorderColour:", borderColour
            if borderColour != None:
                self.surface.fill(borderColour)
                self.packetReader.MarkTilesDirty()

        dirtyTiles = self.packetReader.GetDirtyTiles()
        if not dirtyTiles:
            # If no tiles are dirty, don't bother.
            return

        # List of update rectangles (in scaled output window)
        rect_list = []

        # Scale and blit only those tiles which have been updated
        for row, col in dirtyTiles:
            self.packetReader.FillTile(self.workingTile, row, col)

            if self.cdgZoom == 'none':
                # The no-scale approach.
                rect = pygame.Rect(self.displayTileWidth * row + self.displayRowOffset,
                                   self.displayTileHeight * col + self.displayColOffset,
                                   self.displayTileWidth, self.displayTileHeight)
                self.surface.blit(self.workingTile, rect)
                self.display.blit(self.workingTile, rect)
                rect_list.append(rect)

            elif self.cdgZoom == 'soft':
                # The soft-scale approach.
                self.workingSurface.blit(self.workingTile, (self.displayTileWidth * row, self.displayTileHeight * col))

            else:
                # The quick-scale approach.
                scaled = pygame.transform.scale(self.workingTile, (self.displayTileWidth,self.displayTileHeight))
                rect = pygame.Rect(self.displayTileWidth * row + self.displayRowOffset,
                                   self.displayTileHeight * col + self.displayColOffset,
                                   self.displayTileWidth, self.displayTileHeight)
                self.surface.blit(scaled, rect)
                self.display.blit(scaled, rect)
                rect_list.append(rect)

        if self.cdgZoom == 'soft':
            # Now scale and blit the whole screen.
            scaled = pygame.transform.rotozoom(self.workingSurface, 0, self.displayScale)
            self.surface.blit(scaled, (self.displayRowOffset, self.displayColOffset))
            self.display.blit(scaled, (self.displayRowOffset, self.displayColOffset))
            pygame.display.flip()
            #pygame.display.update()
        elif len(rect_list) < 24:
            # Only update those areas which have changed
            pygame.display.update(rect_list)
        else:
            pygame.display.flip()
            #pygame.display.update()

        #pygame.display.update()

    def _extractZipData(self, cdgfile, zippath):
        cdgFilePath = None
        soundFilePath = None
        basepath = os.path.splitext(cdgfile)[0]

        zip = zipfile.ZipFile(zippath)
        try:
            namelist = zip.namelist()
            zipSoundFile = None

            if cdgfile not in namelist:
                self.ErrorNotifyCallback("Not cdg match in archive for" % cdgfile)
                raise "NoCDGFile"

            for ext in self.validexts:
                tempsound = "%s%s" % (basepath, ext)
                if tempsound in namelist:
                    zipSoundFile = tempsound
                    break
            if not zipSoundFile:
                ErrorString = "There is no mp3 or ogg file to match :", cdgfile 
                self.ErrorNotifyCallback (ErrorString)
                raise 'NoSoundFile'

            #
            # ZipFile.extract not available pre python 2.6
            #
            zip.extract(cdgfile, self.tempdir)
            zip.extract(zipSoundFile, self.tempdir)
        
            #self._writeZipMember(zippath, cdgfile, self.tempdir)
            #self._writeZipMember(zippath, zipSoundFile, self.tempdir)

            soundFilePath = os.path.join(self.tempdir, zipSoundFile)
            cdgFilePath = os.path.join(self.tempdir, cdgfile)
        finally:
            zip.close()

        return cdgFilePath, soundFilePath

    def _writeZipMember(self, zippath, member, outpath):
        temppath = os.path.join(outpath, member)
        tempdir = os.path.dirname(temppath)
        if not os.path.isdir(tempdir):
            os.makedirs(tempdir)
        f = open(temppath, 'w')
        try:
            zip = zipfile.ZipFile(zippath)
            try:
                data = zip.read(member)
                f.write(data)
            finally:
                zip.close()
        finally:
            f.close()

def defaultErrorPrint(ErrorString):
    print (ErrorString)

# Can be called from the command line with the CDG filepath as parameter
def main():
    player = cdgPlayer(sys.argv[1], None)
    player.Play()
    player.WaitForPlayer()



if __name__ == "__main__":
    sys.exit(main())
    #import profile
    #result = profile.run('main()', 'pycdg.prof')
    #sys.exit(result)
    
