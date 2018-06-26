#!/usr/bin/python

# Display Manager, version 1.0.0

# Programmatically manages Mac displays
# Can set screen resolution, color depth, refresh rate, screen mirroring, and brightness


import argparse         # read in command-line execution
import objc             # access Objective-C functions and variables
import sys              # exit script with the right codes
import CoreFoundation   # work with Objective-C data types
import Quartz           # work with system graphics


# Configured for global usage; otherwise, must be re-instantiated each time
iokit = None


class Display(object):
    """
    Contains properties regarding display information for a given physical display, along with a few
    useful helper functions.
    """

    # todo: start bringing in width/height stuff?
    def __init__(self, displayID):
        self.displayID = displayID

    @property
    def isMain(self):
        """
        :return: Boolean for whether this display is the main display
        """
        return Quartz.CGDisplayIsMain(self.displayID)

    @property
    def rotation(self):
        """
        :return: Rotation of this display, in degrees.
        """
        return int(Quartz.CGDisplayRotation(self.displayID))

    @property
    def brightness(self):
        """
        :return: Brightness of this display, from 0 to 1.
        """
        service = self.servicePort
        (error, brightness) = iokit["IODisplayGetFloatParameter"](service, 0,
                                                                          iokit["kDisplayBrightness"], None)
        if error:
            return None
        else:
            return brightness

    @property
    def currentMode(self):
        """
        :return: The current Quartz "DisplayMode" interface for this display.
        """
        return DisplayMode(Quartz.CGDisplayCopyDisplayMode(self.displayID))

    @property
    def allModes(self):
        """
        :return: All possible Quartz "DisplayMode" interfaces for this display.
        """
        modes = []
        for mode in Quartz.CGDisplayCopyAllDisplayModes(self.displayID, None):
            modes.append(DisplayMode(mode))
        return modes

    @property
    def highestMode(self):
        """
        :return: The Quartz "DisplayMode" interface with the highest display resolution for this display.
        """
        highest = (None, 0)
        for mode in self.allModes:
            if mode.width * mode.height > highest[1]:
                highest = (mode, mode.width * mode.height)
        return highest[0]

    @property
    def servicePort(self):
        """
        :return: The integer representing this display's service port.
        """
        vendor = Quartz.CGDisplayVendorNumber(self.displayID)
        model = Quartz.CGDisplayModelNumber(self.displayID)
        serial = Quartz.CGDisplaySerialNumber(self.displayID)

        matching = iokit["IOServiceMatching"]("IODisplayConnect")
        error, iterator = iokit["IOServiceGetMatchingServices"](iokit["kIOMasterPortDefault"], matching, None)

        if error:
            return 0

        service = iokit["IOIteratorNext"](iterator)
        matching_service = 0

        def cfEquals(a, b):  # necessary because sometimes CoreFoundation returns Nones in the place of 0s
            if a == b:
                return True
            elif a is None:
                return b == 0
            elif b is None:
                return a == 0
            else:
                return False

        # iterate through the iokit's listed services until desired service is found
        while service != 0:
            info = iokit["IODisplayCreateInfoDictionary"](service, iokit["kIODisplayNoProductName"])

            vendorID = CoreFoundation.CFDictionaryGetValue(info, CoreFoundation.CFSTR(iokit["kDisplayVendorID"]))
            productID = CoreFoundation.CFDictionaryGetValue(info, CoreFoundation.CFSTR(iokit["kDisplayProductID"]))
            serialNumber = CoreFoundation.CFDictionaryGetValue(info,
                                                               CoreFoundation.CFSTR(iokit["kDisplaySerialNumber"]))

            if cfEquals(vendorID, vendor) and cfEquals(productID, model) and cfEquals(serialNumber, serial):
                matching_service = service
                break

            service = iokit["IOIteratorNext"](iterator)

        return matching_service

    def exactMode(self, width, height, depth=32, refresh=0):
        """
        :param width: Desired width
        :param height: Desired height
        :param depth: Desired pixel depth
        :param refresh: Desired refresh rate
        :return: The Quartz "DisplayMode" interface matching the description, if it exists; otherwise, None.
        """
        for mode in self.allModes:
            if mode.width == width and mode.height == height and mode.depth == depth and mode.refresh == refresh:
                return mode
        return None

    def closestMode(self, width, height, depth=32, refresh=0):
        """
        :param width: Desired width
        :param height: Desired height
        :param depth: Desired pixel depth
        :param refresh: Desired refresh rate
        :return: The closest Quartz "DisplayMode" interface possible for this display.
        """
        whd = None
        wh = None

        for mode in self.allModes:
            widthMatch = mode.width == width
            heightMatch = mode.height == height
            depthMatch = mode.depth == depth
            refreshMatch = mode.refresh == refresh

            if widthMatch and heightMatch and depthMatch and refreshMatch:
                return mode
            elif widthMatch and heightMatch and depthMatch:
                whd = mode
            elif widthMatch and heightMatch:
                wh = mode

        if whd:
            return whd
        elif wh:
            return wh
        else:
            return None

    def setMode(self, mode):
        """
        :param mode: The Quartz "DisplayMode" interface to set this display to.
        """
        (error, configRef) = Quartz.CGBeginDisplayConfiguration(None)
        if error:
            print("Could not begin display configuration: error {}".format(error))
            sys.exit(1)

        error = Quartz.CGConfigureDisplayWithDisplayMode(configRef, self.displayID, mode.raw, None)
        if error:
            print("Failed to set display configuration: error {}".format(error))
            error = Quartz.CGCancelDisplayConfiguration(configRef)
            sys.exit(1)

        Quartz.CGCompleteDisplayConfiguration(configRef, Quartz.kCGConfigurePermanently)

    def setMirror(self, mirrorDisplay):
        """
        :param mirrorDisplay: The display which will mirror this display.
            Input a NoneType to stop mirroring.
        """
        (error, configRef) = Quartz.CGBeginDisplayConfiguration(None)
        if error:
            print("Could not begin display configuration: error {}".format(error))
            sys.exit(1)

        if mirrorDisplay is not None and mirrorDisplay.displayID != self.displayID:
            Quartz.CGConfigureDisplayMirrorOfDisplay(configRef, self.displayID, mirrorDisplay.displayID)
        else:
            Quartz.CGConfigureDisplayMirrorOfDisplay(configRef, self.displayID, Quartz.kCGNullDirectDisplay)

        Quartz.CGCompleteDisplayConfiguration(configRef, Quartz.kCGConfigurePermanently)


# todo: rename
class DisplayMode(object):
    """
    Represents a DisplayMode as implemented in Quartz.
    """

    def __init__(self, mode):
        # Low-hanging fruit
        self.width = Quartz.CGDisplayModeGetWidth(mode)
        self.height = Quartz.CGDisplayModeGetHeight(mode)
        self.depth = getPixelDepth(Quartz.CGDisplayModeCopyPixelEncoding(mode))
        self.refresh = Quartz.CGDisplayModeGetRefreshRate(mode)
        self.raw = mode

        # Hidpi scalar
        raw_width = Quartz.CGDisplayModeGetPixelWidth(mode)
        raw_height = Quartz.CGDisplayModeGetPixelHeight(mode)
        res_width = Quartz.CGDisplayModeGetWidth(mode)
        res_height = Quartz.CGDisplayModeGetHeight(mode)
        if raw_width == res_width and raw_height == res_height:
            self.hidpi = None
        else:
            if raw_width / res_width == raw_height / res_height:
                self.hidpi = raw_width / raw_height
            else:
                self.hidpi = None

    def __str__(self):
        return "resolution: {width}x{height}, pixel depth: {depth}, refresh rate: {refresh}".format(**{
            "width": self.width, "height": self.height, "depth": self.depth, "refresh": self.refresh
        })


# todo: remove deprecated
# class DisplayMode(object):
#     """
#     Represents a DisplayMode as implemented in Quartz.
#     """
#
#     def __init__(self, mode=None, width=None, height=None, bpp=None, refresh=None):
#         if mode:
#             self.width      = Quartz.CGDisplayModeGetWidth(mode)
#             self.height     = Quartz.CGDisplayModeGetHeight(mode)
#             self.bpp        = getPixelDepth(Quartz.CGDisplayModeCopyPixelEncoding(mode))
#             self.refresh    = Quartz.CGDisplayModeGetRefreshRate(mode)
#             self.raw_mode   = mode
#             self.dpi_scalar = getHidpiScalar(mode)
#         else:
#             for element in [width, height, bpp, refresh]:
#                 if element is None:
#                     raise ValueError("Must give all of width, height, bits per pixel, and refresh rate to construct DisplayMode.")
#             self.width      = width
#             self.height     = height
#             self.bpp        = bpp
#             self.refresh    = refresh
#             self.raw_mode   = None
#             self.dpi_scalar = None
#         self.pixels = self.width * self.height
#         self.ratio  = float(self.width) / float(self.height)
#
#     def __str__(self):
#         return "{width}x{height}; pixel depth: {bpp}; refresh rate: {refresh}; ratio: {ratio:.2f}:1{hidpi}".format(
#             width   = self.width,
#             height  = self.height,
#             bpp     = self.bpp,
#             refresh = self.refresh,
#             ratio   = self.ratio,
#             hidpi   = "; [HiDPI: x{}]".format(self.dpi_scalar) if self.dpi_scalar else "")
#
#     def __repr__(self):
#         return self.__str__()
#
#     def __eq__(self, other):
#         return (isinstance(other, self.__class__) and
#             self.width      == other.width        and
#             self.height     == other.height       and
#             self.bpp        == other.bpp          and
#             self.refresh    == other.refresh      and
#             self.dpi_scalar == other.dpi_scalar)
#
#     def __ne__(self, other):
#         return not self.__eq__(other)


def getIOKit():
    """
    This handles the importing of specific functions and variables from the
    IOKit framework. IOKit is not natively bridged in PyObjC, so the methods
    must be found and encoded manually to gain their functionality in Python.

    :return: A dictionary containing several IOKit functions and variables.
    """
    global iokit
    if not iokit:
        # The dictionary which will contain all of the necessary functions and variables from IOKit
        iokit = {}

        # Retrieve the IOKit framework
        iokitBundle = objc.initFrameworkWrapper(
            "IOKit",
            frameworkIdentifier="com.apple.iokit",
            frameworkPath=objc.pathForFramework("/System/Library/Frameworks/IOKit.framework"),
            globals=globals()
            )

        # The IOKit functions to be retrieved
        functions = [
            ("IOServiceGetMatchingServices", b"iI@o^I"),
            ("IODisplayCreateInfoDictionary", b"@II"),
            ("IODisplayGetFloatParameter", b"iII@o^f"),
            ("IODisplaySetFloatParameter", b"iII@f"),
            ("IOServiceMatching", b"@or*", "", dict(
                # This one is obnoxious. The "*" gets pythonified as a char, not a
                # char*, so we have to make it interpret as a string.
                arguments=
                {
                    0: dict(type=objc._C_PTR + objc._C_CHAR_AS_TEXT,
                            c_array_delimited_by_null=True,
                            type_modifier=objc._C_IN)
                }
            )),
            ("IOServiceRequestProbe", b"iII"),
            ("IOIteratorNext", b"II")
        ]

        # The IOKit variables to be retrieved
        variables = [
            ("kIODisplayNoProductName", b"I"),
            ("kIOMasterPortDefault", b"I"),
            ("kIODisplayBrightnessKey", b"*"),
            ("kDisplayVendorID", b"*"),
            ("kDisplayProductID", b"*"),
            ("kDisplaySerialNumber", b"*")
        ]

        # Load functions from IOKit into the global namespace
        objc.loadBundleFunctions(iokitBundle, iokit, functions)
        objc.loadBundleVariables(iokitBundle, globals(), variables)  # bridge won't put straight into iokit, so globals()
        # Move only the desired variables into iokit
        for var in variables:
            key = "{}".format(var[0])
            if key in globals():
                iokit[key] = globals()[key]

        iokit["kDisplayBrightness"] = CoreFoundation.CFSTR(iokit["kIODisplayBrightnessKey"])
        iokit["kDisplayUnderscan"] = CoreFoundation.CFSTR("pscn")

        return iokit


def getHidpiValue(no_hidpi, only_hidpi):
    """
    :param no_hidpi: Whether to exclude HiDPI modes from the search.
    :param only_hidpi: Whether to only include HiDPI modes.
    :return: An integer describing the combination of these.
    """
    if no_hidpi and not only_hidpi:
        return 0
    elif not no_hidpi and not only_hidpi:
        return 1
    elif not no_hidpi and only_hidpi:
        return 2
    else:
        raise ValueError("Error: Cannot require both no HiDPI and only HiDPI. Make up your mind.")


# todo: move deprecated into new DisplayMode
def getPixelDepth(encoding):
    """
    Takes a pixel encoding and returns an integer representing that encoding.

    :param encoding: A pixel encoding from Quartz's method
        CGDisplayModeCopyPixelEncoding.
    :return: An integer representing the pixel depth of that encoding.
    """
    if encoding == "PPPPPPPP":
        return 8
    elif encoding == "-RRRRRGGGGGBBBBB":
        return 16
    elif encoding == "--------RRRRRRRRGGGGGGGGBBBBBBBB":
        return 32
    elif encoding == "--RRRRRRRRRRGGGGGGGGGGBBBBBBBBBB":
        return 30
    else:
        raise RuntimeError("Unknown pixel encoding: {}".format(encoding))


# todo: remove deprecated
# def getCurrentMode(display):
#     """
#     Gets the current display currentMode for a given display.
#
#     :param: The identifier of the desired display.
#     :return: The current DisplayMode used by that display.
#     """
#     return DisplayMode(mode=Quartz.CGDisplayCopyDisplayMode(display))


# def getClosestMode(modes, width, height, depth, refresh):
#     """
#     Given a set of values and a list of available modes, attempts to find the
#     closest matching supported currentMode in the list. "Closest matching" is
#     determined as follows:
#
#     1. Is the desired currentMode in the list exactly?
#     2. If not, is there a currentMode with the desired resolution and bit depth?
#       a. Find the closest matching refresh rate available.
#     3. If not, is there a currentMode with the desired resolution?
#       a. Find the closest matching bit depth available.
#     4. If not, is there a currentMode with the desired Width:Height ratio?
#       a. Find the closest resolution available.
#     5. If not...
#       a. Find the closest aspect ratio.
#       b. Find the closest resolution.
#     6. If there is still nothing, return None.
#
#     :param modes: A list containing DisplayMode objects.
#     :param width: An integer for display width.
#     :param height: An integer for display height.
#     :param depth: The pixel depth for the display.
#     :param refresh: The refresh rate for the display.
#     :return: The DisplayMode from the list that matches the values best.
#     """
#     # Check we don't have an empty list of modes.
#     if not modes:
#         return None
#
#     match_mode = DisplayMode(width=width, height=height, bpp=depth, refresh=refresh)
#     match_ratio = width / height
#     match_pixels = width * height
#     # Search for an exact match.
#     for mode in modes:
#         if mode == match_mode:
#             return mode
#
#     # No exact match, so let's check if there's a resolution and bit depth match.
#     close_matches = []
#     for mode in modes:
#         if mode.width == width and mode.height == height and mode.bpp == depth:
#             # Found one with the correct resolution.
#             close_matches.append(mode)
#     if close_matches:
#         # There's at least one match at the correct resolution and bit depth.
#         close_matches.sort(key = lambda mode: mode.refresh, reverse = True)
#         larger = None
#         smaller = None
#         # Find the two closest matches by refresh rate.
#         for match in close_matches:
#             if match.refresh > refresh:
#                 larger = match
#             else:
#                 smaller = match
#                 break
#         # Check some edge cases.
#         if smaller and not larger:
#             # All the available refresh rates are lesser than the desired.
#             return smaller
#         if larger and not smaller:
#             # There's only one element in the list, and it's larger than we
#             # ideally wanted. Oh well.
#             return larger
#         # Okay, now we have two elements, and neither is perfect.
#         # Find the closer of the two.
#         larger_dif = abs(larger.refresh - refresh)
#         smaller_dif = abs(smaller.refresh - refresh)
#         if smaller_dif < larger_dif:
#             return smaller
#         else:
#             return larger
#
#     # No matches for WHD, so let's check that bit depth.
#     for mode in modes:
#         if mode.width == width and mode.height == height:
#             # Found one with the right resolution.
#             close_matches.append(mode)
#     if close_matches:
#         # We have the correct resolution. Let's find the closest bit depth.
#         close_matches.sort(key = lambda mode: mode.bpp, reverse = True)
#         larger = None
#         smaller = None
#         # Find the two closest matches by bit depth.
#         for match in close_matches:
#             if match.bpp > depth:
#                 larger = match
#             else:
#                 smaller = match
#                 break
#         # Check some edge cases.
#         if smaller and not larger:
#             # All the available bit depths are lesser than the desired.
#             return smaller
#         if larger and not smaller:
#             # There's only one element in the list, and it's larger than we
#             # ideally wanted. Oh well.
#             return larger
#         # Okay, now we have two elements, and neither is perfect.
#         # Find the closer of the two.
#         larger_dif = abs(larger.bpp - depth)
#         smaller_dif = abs(smaller.bpp - depth)
#         if smaller_dif < larger_dif:
#             return smaller
#         else:
#             return larger
#
#     # At this point, we don't even have a good resolution match.
#     # Let's find all the modes with the appropriate ratio, and then find the
#     # closest total pixel count.
#     for mode in modes:
#         if mode.ratio == match_ratio:
#             # Got the right width:height ratio.
#             close_matches.append(mode)
#     if close_matches:
#         # Sort by total pixels.
#         close_matches.sort(key = lambda mode: mode.pixels, reverse = True)
#         larger = None
#         smaller = None
#         # Find the closest matches by pixel count.
#         for match in close_matches:
#             if match.pixels > match_pixels:
#                 larger = match
#             else:
#                 smaller = match
#                 break
#         # Check some edge cases.
#         if smaller and not larger:
#             # All the available pixel counts are lesser than the desired.
#             return smaller
#         if larger and not smaller:
#             # There's only one element in the list, and it's larger than we
#             # ideally wanted. Oh well.
#             return larger
#         # Okay, now we have two elements, and neither is perfect.
#         # Find the closer of the two.
#         larger_dif = abs(larger.pixels - match_pixels)
#         smaller_dif = abs(smaller.pixels - match_pixels)
#         if smaller_dif < larger_dif:
#             return smaller
#         else:
#             return larger
#
#     # Still no good matches. Okay, now we're really reaching.
#     # Let's try to find all of the displays with a sort-of-close aspect ratio,
#     # and then find the one in there that has the closest total pixel count.
#     ratios = []
#     for mode in modes:
#         ratios.append(mode.ratio)
#     ratios = list(set(ratios))
#     ratios.sort(reverse = True)
#     larger_ratio = None
#     smaller_ratio = None
#     # todo: remove unnecessary?
#     # ideal_ratio = None
#
#     #####################################################################
#     # TODO: FIGURE THE NEXT SIX LINES OUT; THEY'RE PROBABLY THE PROBLEM #
#     for ratio in ratios:
#         if ratio > match_ratio:
#             larger_ratio = ratio
#         else:
#             smaller_ratio = ratio
#             break
#     #                                                                   #
#     #####################################################################
#
#     if smaller_ratio and not larger_ratio:
#         ideal_ratio = smaller_ratio
#     elif larger_ratio and not smaller_ratio:
#         ideal_ratio = larger_ratio
#     else:
#         larger_dif = abs(larger_ratio - match_ratio)
#         smaller_dif = abs(smaller_ratio - match_ratio)
#         if smaller_dif < larger_dif:
#             ideal_ratio = smaller_ratio
#         else:
#             ideal_ratio = larger_ratio
#
#     # Now find all the matches with the ideal ratio.
#     for mode in modes:
#         if mode.ratio == ideal_ratio:
#             close_matches.append(mode)
#     # And now we look through those for the closest match in pixel count.
#     if close_matches:
#         # Sort by total pixels.
#         close_matches.sort(key = lambda mode: mode.pixels, reverse = True)
#         larger = None
#         smaller = None
#         # Find the closest matches by pixel count.
#         for match in close_matches:
#             if match.pixels > match_pixels:
#                 larger = match
#             else:
#                 smaller = match
#                 break
#         # Check some edge cases.
#         if smaller and not larger:
#             # All the available pixel counts are lesser than the desired.
#             return smaller
#         if larger and not smaller:
#             # There's only one element in the list, and it's larger than we
#             # ideally wanted. Oh well.
#             return larger
#         # Okay, now we have two elements, and neither is perfect.
#         # Find the closer of the two.
#         larger_dif = abs(larger.pixels - match_pixels)
#         smaller_dif = abs(smaller.pixels - match_pixels)
#         if smaller_dif < larger_dif:
#             return smaller
#         else:
#             return larger
#
#     # We don't have any good resolutions available.
#     return None


# todo: remove deprecated


def getAllDisplays():
    """
    :return: A list containing all currently-online displays.
    """
    displays = []
    for displayID in getAllDisplayIDs():
        displays.append(Display(displayID))
    return displays


# todo: remove deprecated
# def getAllModes(display, hidpi=1):
#     """
#     Given a display, this finds all of the available supported display modes.
#     The resulting list is sorted so that the highest resolution, highest pixel
#     depth, highest refresh rate modes are at the top.
#
#     :param display: The identifier of the desired display.
#     :param hidpi: The HiDPI usage currentMode, specified by getHidpiValue().
#     :return: A list of DisplayMode objects, sorted.
#     """
#     # Specifically, it includes not just HiDPI settings, but also settings for
#     # different pixel encodings than the standard 8-, 16-, and 32-bit.
#     # Unfortunately, the CGDisplayModeCopyPixelEncoding method cannot see other
#     # encodings, leading to apparently-duplicated values. Not ideal.
#     if hidpi:
#         modes = [DisplayMode(mode=mode) for mode in Quartz.CGDisplayCopyAllDisplayModes(display, {Quartz.kCGDisplayShowDuplicateLowResolutionModes: Quartz.kCFBooleanTrue})]
#     else:
#         modes = [DisplayMode(mode=mode) for mode in Quartz.CGDisplayCopyAllDisplayModes(display, None)]
#     if hidpi == 2:
#         # This removes extra modes, so only HiDPI-scaled modes are displayed.
#         modes = [mode for mode in modes if mode.dpi_scalar is not None]
#     # Sort the modes!
#     modes.sort(key = lambda mode: mode.refresh, reverse = True)
#     modes.sort(key = lambda mode: mode.bpp, reverse = True)
#     modes.sort(key = lambda mode: mode.pixels, reverse = True)
#     return modes


# def getAllModesAllDisplays(hidpi=1):
#     """
#     Gets a list of displays and all available modes for each display.
#
#     :param hidpi: Whether to include additional, "duplicate" modes.
#     :return: A list of tuples as:
#         (display identifier, [all valid DisplayModes for that display])
#     """
#     modes = []
#     for display in getAllDisplayIDs():
#         modes.append((display, getAllModes(display, hidpi)))
#     return modes


def getMainDisplayID():
    """
    :return: DisplayID of the main display
    """
    return Quartz.CGMainDisplayID()


def getAllDisplayIDs():
    """
    :return: A tuple containing all currently-online displays.
        Each object in the tuple is a display identifier (as an integer).
    """
    (error, online_displays, displays_count) = Quartz.CGGetOnlineDisplayList(32, None, None)  # max 32 displays
    if error:
        raise RuntimeError("Unable to get displays list.")
    return online_displays


## Subcommand handlers
def setHandler(command, width, height, depth=32, refresh=0, displayID=getMainDisplayID(), hidpi=1):
    """
    Handles all of the options for the "set" subcommand.

    :param command: The command passed in.
    :param width: Desired width.
    :param height: Desired height.
    :param depth: Desired pixel depth.
    :param refresh: Desired refresh rate.
    :param displayID: Specific display to configure.
    :param hidpi: Description of HiDPI settings from getHidpiValue().
    """
    # Set defaults if they're not given (defaults in function definition overridden in certain cases)
    if depth is None:
        depth = 32
    if refresh is None:
        refresh = 0
    if displayID is None:
        displayID = getMainDisplayID()
    if hidpi is None:
        hidpi = 1

    display = Display(displayID)

    if command == "closest":
        for element in [width, height]:
            if element is None:
                usage("set")
                print("Must have both width and height for closest setting.")
                sys.exit(1)

        closest = display.closestMode(width, height, depth, refresh)
        if closest:
            display.setMode(closest)
        else:
            print("No close match was found.")

    elif command == "highest":
        display.setMode(display.highestMode)

    elif command == "exact":
        exact = display.exactMode(width, height, depth, refresh)
        if exact:
            display.setMode(exact)
        else:
            print("No exact match was found.")
            sys.exit(1)


def showHandler(command, width, height, depth=32, refresh=0, displayID=getMainDisplayID(), hidpi=1):
    """
    Handles all the options for the "show" subcommand.

    :param command: The command passed in.
    :param width: Desired width.
    :param height: Desired height.
    :param depth: Desired pixel depth.
    :param refresh: Desired refresh rate.
    :param displayID: Specific display to configure.
    :param hidpi: Description of HiDPI settings from getHidpiValue().
    """
    # Set defaults if they're not given (function definition overridden in certain cases)
    if depth is None:
        depth = 32
    if refresh is None:
        refresh = 0
    if displayID is None:
        displayID = getMainDisplayID()
    if hidpi is None:
        hidpi = 1

    display = Display(displayID)

    if command == "all":
        for display in getAllDisplays():
            print("Display: {0} {1}".format(str(display.displayID), " (Main Display)" if display.isMain else ""))

            for mode in display.allModes:
                print("    {}".format(mode))

    elif command == "closest":
        for element in [width, height]:
            if element is None:
                usage("show")
                print("Must have both width and height for closest matching.")
                sys.exit(1)

        closest = display.closestMode(width, height, depth, refresh)
        if closest:
            print(closest)
        else:
            print("No close match was found.")

    elif command == "highest":
        print(display.highestMode)

    elif command == "current":
        for display in getAllDisplays():
            print("Display: {0} {1}".format(str(display.displayID), " (Main Display)" if display.isMain else ""))
            print("    {}".format(display.currentMode))

    elif command == "displays":
        for display in getAllDisplays():
            print("Display: {0} {1}".format(str(display.displayID), " (Main Display)" if display.isMain else ""))


def brightnessHandler(command, brightness=1, displayID=getMainDisplayID()):
    """
    Handles all the options for the "brightness" subcommand.

    :param command: The command passed in.
    :param brightness: The level of brightness to change to.
    :param displayID: Specific display to configure.
    """
    # Set defaults if they're not given (function definition overridden in certain cases)
    if displayID is None:
        displayID = getMainDisplayID()

    display = Display(displayID)

    if command == "show":
        for display in getAllDisplays():
            if display.brightness:
                print("Display: {}{}".format(displayID, " (Main Display)" if display.isMain else ""))
                print("    {:.2f}%".format(display.brightness * 100))
            else:
                print("Failed to get brightness of display {}".format(display.displayID))

    elif command == "set":
        service = display.servicePort
        error = iokit["IODisplaySetFloatParameter"](service, 0, iokit["kDisplayBrightness"], brightness)
        if error:
            print("Failed to set brightness of display {}; error {}".format(display.displayID, error))
            # External display brightness probably can't be managed this way
            print("External displays may not be compatible with Display Manager. \n"
                  "If this is an external display, try setting manually on device hardware.")


def rotateHandler(command, angle=0, displayID=getMainDisplayID()):
    """
    Handles all the options for the "rotation" subcommand.

    :param command: The command passed in.
    :param angle: The display to configure rotation on.
    :param displayID: The display to configure rotation on.
    """
    # Set defaults if they're not given (function definition overridden in certain cases)
    if displayID is None:
        displayID = getMainDisplayID()

    display = Display(displayID)

    if command == "show":
        for display in getAllDisplays():
            print("Display: {0} {1}".format(str(display.displayID), " (Main Display)" if display.isMain else ""))
            print("    Rotation: {0} degrees".format(str(int(display.rotation))))

    elif command == "set":
        # Get rotation "options", per user input
        angleCodes = {0: 0, 90: 48, 180: 96, 270: 80}
        rotateCode = 1024
        if angle % 90 != 0:  # user entered inappropriate angle, so we quit
            print("Can only rotate by multiples of 90 degrees.")
            sys.exit(1)
        # "or" the rotate code with the right angle code (which is being moved to the right part of the 32-bit word)
        options = rotateCode | (angleCodes[angle % 360] << 16)

        # Actually rotate the screen
        iokit["IOServiceRequestProbe"](display.servicePort, options)


def underscanHandler(command, underscan=1, displayID=getMainDisplayID()):
    """
    Handles all the options for the "underscan" subcommand.

    :param command: The command passed in.
    :param underscan: The value to set on the underscan slider.
    :param displayID: Specific display to configure.
    """
    # Set defaults if they're not given (function definition overridden in certain cases)
    if displayID is None:
        displayID = getMainDisplayID()

    display = Display(displayID)

    if command == "show":
        for display in getAllDisplays():
            (error, display_underscan) = iokit["IODisplayGetFloatParameter"](display.servicePort, 0,
                                                                             iokit["kDisplayUnderscan"], None)
            if error:
                print("Failed to get underscan value of display {}; error {}".format(display.displayID, error))
                continue
            print("Display: {}{}".format(display.displayID, " (Main Display)" if display.isMain else ""))
            print("    {:.2f}%".format(display_underscan * 100))

    elif command == "set":
        error = iokit["IODisplaySetFloatParameter"](display.servicePort, 0, iokit["kDisplayUnderscan"], underscan)
        if error:
            print("Failed to set underscan of display {}; error {}".format(display.displayID, error))
        print("Display: {}{}".format(displayID, " (Main Display)" if display.isMain else ""))
        print("    {:.2f}%".format(underscan * 100))


def mirroringHandler(command, displayID, mirrorDisplayID=getMainDisplayID()):
    """
    Handles all the options for the "mirroring" subcommand.

    :param command: The command passed in.
    :param displayID: The display to configure mirroring on.
    :param mirrorDisplayID: The display to become a mirror of.
    """
    # Set defaults if they're not given (function definition overridden in certain cases)
    if mirrorDisplayID is None:
        mirrorDisplayID = getMainDisplayID()

    mirrorDisplay = Display(mirrorDisplayID)
    display = Display(displayID)

    if command == "enable":
        mirrorDisplay.setMirror(display)

    if command == "disable":
        for display in getAllDisplays():
            display.setMirror(None)


## main() and its helper functions
def earlyExit():
    """
    Exits early in specific cases; exit return value sensitive to specific conditions
    """
    # If they don't include enough arguments, show help and exit with error
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    # Still show help, but do not exit with error
    elif len(sys.argv) == 2 and sys.argv[1] == '--help':
        usage()
        sys.exit(0)


def parse():
    # Do actual argument parsing
    parser = argparse.ArgumentParser(add_help=False)

    # Isolate parser args
    args = parser.parse_known_args()

    # Add the subparsers.
    subparsers = parser.add_subparsers(dest='subcommand')

    # Subparser for 'help'
    parser_help = subparsers.add_parser('help', add_help=False)
    parser_help.add_argument(
        'command',
        choices=['set', 'show', 'brightness', 'underscan', 'mirroring'],
        nargs='?',
        default=None
    )

    # Subparser for 'set'
    parser_set = subparsers.add_parser('set', add_help=False)
    parser_set.add_argument(
        'command',
        choices=['help', 'closest', 'highest', 'exact'],
        nargs='?',
        default='closest'
    )

    # Subparser for 'show'
    parser_show = subparsers.add_parser('show', add_help=False)
    parser_show.add_argument(
        'command',
        choices=['help', 'all', 'closest', 'highest', 'current', 'displays'],
        nargs='?',
        default='all'
    )

    # Subparser for 'brightness'
    parser_brightness = subparsers.add_parser('brightness', add_help=False)
    parser_brightness.add_argument('command', choices=['help', 'show', 'set'])
    parser_brightness.add_argument('brightness', type=float, nargs='?')

    # Subparser for 'rotate'
    parser_rotate = subparsers.add_parser('rotate', add_help=False)
    parser_rotate.add_argument(
        'command',
        choices=['help', 'set', 'show'],
        nargs='?',
        default='show'
    )
    parser_rotate.add_argument(
        'rotation',
        type=int,
        default=0,
        nargs='?'
    )

    # Subparser for 'underscan'
    parser_underscan = subparsers.add_parser('underscan', add_help=False)
    parser_underscan.add_argument('command', choices=['help', 'show', 'set'])
    parser_underscan.add_argument('underscan', type=float, nargs='?')

    # Subparser for 'mirroring'
    parser_mirroring = subparsers.add_parser('mirroring', add_help=False)
    parser_mirroring.add_argument('command', choices=['help', 'enable', 'disable'])
    parser_mirroring.add_argument('--mirror', type=int, default=getMainDisplayID())

    # All of the subcommands have some similar arguments
    for subparser in [parser_set, parser_show, parser_brightness, parser_underscan, parser_mirroring, parser_rotate]:
        subparser.add_argument('--help', action='store_true')
        subparser.add_argument('--display', type=int)

    # These two subparsers have similar arguments
    for subparser in [parser_set, parser_show]:
        subparser.add_argument('-w', '--width', type=int)
        subparser.add_argument('-h', '--height', type=int)
        subparser.add_argument('-d', '--depth', type=int)
        subparser.add_argument('-r', '--refresh', type=int)
        subparser.add_argument('--no-hidpi', action='store_true')
        subparser.add_argument('--only-hidpi', action='store_true')

    # Parse the arguments
    # Note that we have to use the leftover arguments from the parser.parse_known_args() call up above
    return parser.parse_args(args[1])


def usage(command=None):
    """
    Prints out the usage information.

    :param command: The subcommand to print information for.
    """
    # Give the version information always.
    print("Display Manager, version 1.0.0")

    information = {}

    information['set'] = '\n'.join([
        "usage: display_manager.py set {{ help | closest | highest | exact }}",
        "    [-w width] [-h height] [-d depth] [-r refresh]",
        "    [--display display] [--nohidpi]",
        "",
        "SUBCOMMANDS",
        "    help        Print this help information.",
        "    closest     Set the display settings to the supported resolution that is",
        "                closest to the specified values.",
        "    highest     Set the display settings to the highest supported resolution.",
        "    exact       Set the display settings to the specified values if they are",
        "                supported. If they are not, don't change the display.",
        "",
        "OPTIONS",
        "    -w width            Resolution width.",
        "    -h height           Resolution height.",
        "    -d depth            Pixel color depth (default: 32).",
        "    -r refresh          Refresh rate (default: 0).",
        "    --display display   Specify a particular display (default: main display).",
        "    --no-hidpi          Don't show HiDPI settings.",
        "    --only-hidpi        Only show HiDPI settings.",
        "",
    ])

    information['show'] = '\n'.join([
        "usage: display_manager.py show {{ help | all | closest | highest | current }}",
        "    [-w width] [-h height] [-d depth] [-r refresh]",
        "    [--display display] [--nohidpi]",
        "",
        "SUBCOMMANDS",
        "    help        Print this help information.",
        "    all         Show all supported resolutions for the display.",
        "    closest     Show the closest matching supported resolution to the specified",
        "                values.",
        "    highest     Show the highest supported resolution.",
        "    current       Show the current display configuration.",
        "    displays    Just list the current displays and their IDs.",
        "",
        "OPTIONS",
        "    -w width            Resolution width.",
        "    -h height           Resolution height.",
        "    -d depth            Pixel color depth (default: 32).",
        "    -r refresh          Refresh rate (default: 32).",
        "    --display display   Specify a particular display (default: main display).",
        "    --no-hidpi          Don't show HiDPI settings.",
        "    --only-hidpi        Only show HiDPI settings.",
        "",
    ])

    information['brightness'] = '\n'.join([
        "usage: display_manager.py brightness {{ help | show | set [value] }}",
        "    [--display display]",
        "",
        "SUBCOMMANDS",
        "    help        Print this help information.",
        "    show        Show the current brightness setting(s).",
        "    set [value] Sets the brightness to the given value. Must be between 0 and 1.",
        "",
        "OPTIONS",
        "    --display display   Specify a particular display (default: main display).",
        "",
    ])

    information['rotate'] = '\n'.join([
        "usage: display_manager.py rotate {{ help | show | set }}"
        "    [--display display]",
        "SUBCOMMANDS",
        "    help        Print this help information.",
        "    show        Show the current display rotation.",
        "    set [value] Set the rotation to the given value (in degrees). Must be a multiple of 90.",
        "",
        "OPTIONS",
        "    --display display   Specify a particular display (default: main display).",
        ""
    ])

    information['underscan'] = '\n'.join([
        "usage: display_manager.py underscan {{ help | show | set [value] }}",
        "    [--display display]",
        "",
        "SUBCOMMANDS",
        "    help        Print this help information.",
        "    show        Show the current underscan setting(s).",
        "    set [value] Sets the underscan to the given value. Must be between 0 and 1.",
        "",
        "NOTES",
        "    The underscan setting is provided for by a private Apple API. This means that,",
        "    while it works fine for now, they could change the functionality at any point",
        "    without warning.",
        "",
    ])

    information['mirroring'] = '\n'.join([
        "usage: display_manager.py brightness {{ help | enable | disable }}",
        "    [--diplay display] [--mirror display]",
        "",
        "SUBCOMMANDS",
        "    help        Print this help information.",
        "    enable      Activate mirroring.",
        "    disable     Deactivate all mirroring.",
        "",
        "OPTIONS",
        "    --display display               Change mirroring settings for 'display'.",
        "    --mirror display                Set the display to mirror 'display' (default: main display).",
        "",
    ])

    if command in information:
        print(information[command])
    else:
        print('\n'.join([
            "usage: display_manager.py {{ help | set | show | mirroring | brightness | rotate }}",
            "",
            "Use any of the subcommands with 'help' to get more information:",
            "    help        Show this help information.",
            "    set         Set the display configuration.",
            "    show        Show available display configurations.",
            "    brightness  Show or set the current display brightness.",
            "    rotate      Show or set display rotation.",
            "    underscan   Show or set the current display underscan.",
            "    mirroring   Set mirroring configuration.",
            "",
        ]))


def main():
    earlyExit()  # exits if the user didn't give enough information, or just wanted help
    args = parse()  # returns parsed args

    # If they used the 'help' subcommand, display that subcommand's help information
    if args.subcommand == 'help':
        usage(command=args.command)
        sys.exit(0)

    # Check if they wanted help with the subcommand.
    if args.command == 'help' or args.help:
        usage(command=args.subcommand)
        sys.exit(0)

    # todo: remove deprecated
    # try:
    #     hidpi = getHidpiValue(args.no_hidpi, args.only_hidpi)
    # except AttributeError:
    #     pass

    getIOKit()
    hidpi = 1

    if args.subcommand == 'set':
        setHandler(args.command, args.width, args.height, args.depth, args.refresh, args.display, hidpi)
    elif args.subcommand == 'show':
        showHandler(args.command, args.width, args.height, args.depth, args.refresh, args.display, hidpi)
    elif args.subcommand == 'brightness':
        brightnessHandler(args.command, args.brightness, args.display)
    elif args.subcommand == 'underscan':
        underscanHandler(args.command, args.underscan, args.display)
    elif args.subcommand == 'mirroring':
        mirroringHandler(args.command, args.display, args.mirror)
    elif args.subcommand == 'rotate':
        rotateHandler(args.command, args.rotation, args.display)


if __name__ == '__main__':
    main()
