# -*- coding: utf-8 -*-

# Copyright (c) 2017-2020, XESS Corp. The MIT License (MIT).

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import re
from builtins import dict, int, str, super
from collections import namedtuple

import IPython.display as DISP
import matplotlib.pyplot as plt
import nbwavedrom
from future import standard_library

from tabulate import tabulate

from .trace import *

standard_library.install_aliases()


# Set this flag to False if using the older Jupyter notebook.
USE_JUPYTERLAB = True


class PeekerBase(object):
    _peekers = dict()  # Global list of all Peekers.

    def __new__(cls, *args, **kwargs):
        # Keep PeekerBase from being instantiated.
        if cls is PeekerBase:
            raise TypeError("PeekerBase class may not be instantiated")
        return object.__new__(cls)

    def __init__(self, signal, name):

        # Create storage for signal trace.
        self.trace = Trace()

        # Assign a unique name to this peeker.
        self.name_dup = False  # Start off assuming the name has no duplicates.
        index = 0  # Starting index for disambiguating duplicates.
        nm = "{name}[{index}]".format(
            **locals()
        )  # Create name with bracketed index.
        # Search through the peeker names for a match.
        while nm in self._peekers:
            # A match was found, so mark the matching names as duplicates.
            self._peekers[nm].name_dup = True
            self.name_dup = True
            # Go to the next index and see if that name is taken.
            index += 1
            nm = "{name}[{index}]".format(**locals())
        self.trace.name = nm  # Assign the unique name.

        # Keep a reference to the signal so we can get info about it later, if needed.
        self.signal = signal

        # Add this peeker to the global list.
        self._peekers[self.trace.name] = self

    @classmethod
    def clear(cls):
        """Clear the global list of Peekers."""
        cls._peekers = dict()

    @classmethod
    def clear_traces(cls):
        """Clear waveform samples from the global list of Peekers."""
        for p in cls._peekers.values():
            p.trace.clear()

    @classmethod
    def peekers(cls):
        """Return a list of all the Peekers."""
        return cls._peekers.values()

    @classmethod
    def start_time(cls):
        """Return the time of the first signal transition captured by the peekers."""
        return min((p.trace.start_time() for p in cls.peekers()))

    @classmethod
    def stop_time(cls):
        """Return the time of the last signal transition captured by the peekers."""
        return max((p.trace.stop_time() for p in cls.peekers()))

    @classmethod
    def _clean_names(cls):
        """
        Remove indices from non-repeated peeker names that don't need them.

        When created, all peekers get an index appended to their name to
        disambiguate any repeated names. If the name isn't actually repeated,
        then the index is removed.
        """

        index_re = "\[\d+\]$"
        for name, peeker in list(cls._peekers.items()):
            if not peeker.name_dup:
                # Base name is not repeated, so remove any index.
                new_name = re.sub(index_re, "", name)
                if new_name != name:
                    # Index got removed so name changed. Therefore,
                    # remove the original entry and replace with
                    # the renamed Peeker.
                    cls._peekers.pop(name)
                    peeker.trace.name = new_name
                    cls._peekers[new_name] = peeker

    @classmethod
    def to_dataframe(cls, *names, **kwargs):
        """
        Convert traces stored in peekers into a Pandas DataFrame of times and trace values.

        Args:
            *names: A list of strings containing the names for the Peekers that
                will be processed. A string may contain multiple,
                space-separated names.

        Keywords Args:
            start_time: The earliest (left-most) time bound for the traces.
            stop_time: The latest (right-most) time bound for the traces.
            step: Set the time increment for filling in between sample times.
                If 0, then don't fill in between sample times.

        Returns:
            A DataFrame with the columns for the named traces and time as the index.
        """

        cls._clean_names()

        if names:
            # Go through the provided names and split any containing spaces
            # into individual names.
            names = [nm for name in names for nm in name.split()]
        else:
            # If no names provided, use all the peekers.
            names = _sort_names(cls._peekers.keys())

        # Collect all the traces for the Peekers matching the names.
        traces = [getattr(cls._peekers.get(name), "trace", None) for name in names]

        return traces_to_dataframe(*traces, **kwargs)

    @classmethod
    def to_table_data(cls, *names, **kwargs):
        """
        Convert traces stored in peekers into a list of times and trace values.

        Args:
            *names: A list of strings containing the names for the Peekers that
                will be processed. A string may contain multiple,
                space-separated names.

        Keywords Args:
            start_time: The earliest (left-most) time bound for the traces.
            stop_time: The latest (right-most) time bound for the traces.
            step: Set the time increment for filling in between sample times.
                If 0, then don't fill in between sample times.

        Returns:
            List of lists containing the time and the value of each trace at that time.
        """

        cls._clean_names()

        if names:
            # Go through the provided names and split any containing spaces
            # into individual names.
            names = [nm for name in names for nm in name.split()]
        else:
            # If no names provided, use all the peekers.
            names = _sort_names(cls._peekers.keys())

        # Collect all the traces for the Peekers matching the names.
        traces = [getattr(cls._peekers.get(name), "trace", None) for name in names]

        return traces_to_table_data(*traces, **kwargs)

    @classmethod
    def to_table(cls, *names, **kwargs):
        format = kwargs.pop("format", "simple")
        table_data, headers = cls.to_table_data(*names, **kwargs)
        return tabulate(tabular_data=table_data, headers=headers, tablefmt=format)

    @classmethod
    def to_text_table(cls, *names, **kwargs):
        if "format" not in kwargs:
            kwargs["format"] = "simple"
        print(cls.to_table(*names, **kwargs))

    @classmethod
    def to_html_table(cls, *names, **kwargs):
        kwargs["format"] = "html"
        tbl_html = cls.to_table(*names, **kwargs)

        # Generate the HTML from the JSON.
        DISP.display_html(DISP.HTML(tbl_html))

    @classmethod
    def to_matplotlib(cls, *names, **kwargs):
        """
        Convert waveforms stored in peekers into a matplotlib plot.

        Args:
            *names: A list of strings containing the names for the Peekers that
                will be displayed. A string may contain multiple,
                space-separated names.

        Keywords Args:
            start_time: The earliest (left-most) time bound for the waveform display.
            stop_time: The latest (right-most) time bound for the waveform display.
            title: String containing the title placed across the top of the display.
            caption: String containing the title placed across the bottom of the display.
            tick: If true, times are shown at the tick marks of the display.
            tock: If true, times are shown between the tick marks of the display.
            width: The width of the waveform display in inches.
            height: The height of the waveform display in inches.

        Returns:
            Nothing.
        """

        cls._clean_names()

        if names:
            # Go through the provided names and split any containing spaces
            # into individual names.
            names = [nm for name in names for nm in name.split()]
        else:
            # If no names provided, use all the peekers.
            names = _sort_names(cls._peekers.keys())

        # Collect all the Peekers matching the names.
        peekers = [cls._peekers.get(name) for name in names]
        traces = [getattr(p, "trace", None) for p in peekers]
        traces_to_matplotlib(*traces, **kwargs)

    @classmethod
    def to_wavejson(cls, *names, **kwargs):
        """
        Convert waveforms stored in peekers into a WaveJSON data structure.

        Args:
            *names: A list of strings containing the names for the Peekers that
                will be displayed. A string may contain multiple,
                space-separated names.

        Keywords Args:
            start_time: The earliest (left-most) time bound for the waveform display.
            stop_time: The latest (right-most) time bound for the waveform display.
            title: String containing the title placed across the top of the display.
            caption: String containing the title placed across the bottom of the display.
            tick: If true, times are shown at the tick marks of the display.
            tock: If true, times are shown between the tick marks of the display.

        Returns:
            A dictionary with the JSON data for the waveforms.
        """

        cls._clean_names()

        if names:
            # Go through the provided names and split any containing spaces
            # into individual names.
            names = [nm for name in names for nm in name.split()]
        else:
            # If no names provided, use all the peekers.
            names = _sort_names(cls._peekers.keys())

        # Collect all the Peekers matching the names.
        peekers = [cls._peekers.get(name) for name in names]
        traces = [getattr(p, "trace", None) for p in peekers]
        return traces_to_wavejson(*traces, **kwargs)

    @classmethod
    def to_wavedrom(cls, *names, **kwargs):
        """
        Display waveforms stored in peekers in Jupyter notebook.

        Args:
            *names: A list of strings containing the names for the Peekers that
                will be displayed. A string may contain multiple,
                space-separated names.

        Keywords Args:
            start_time: The earliest (left-most) time bound for the waveform display.
            stop_time: The latest (right-most) time bound for the waveform display.
            title: String containing the title placed across the top of the display.
            caption: String containing the title placed across the bottom of the display.
            tick: If true, times are shown at the tick marks of the display.
            tock: If true, times are shown between the tick marks of the display.
            width: The width of the waveform display in pixels.
            skin: Selects the set of graphic elements used to create waveforms.

        Returns:
            Nothing.
        """

        # Handle keyword args explicitly for Python 2 compatibility.
        width = kwargs.get("width")
        skin = kwargs.get("skin", "default")

        if USE_JUPYTERLAB:
            # Supports the new Jupyter Lab.
            return nbwavedrom.draw(cls.to_wavejson(*names, **kwargs))
        else:
            # Used with older Jupyter notebooks.
            wavejson_to_wavedrom(
                cls.to_wavejson(*names, **kwargs), width=width, skin=skin
            )

    def delay(self, delta):
        """Return the trace data shifted in time by delta units."""
        return self.trace.delay(delta)

    def binarize(self):
        """Return trace of sample values set to 1 (if true) or 0 (if false)."""
        return self.trace.binarize()

    def __eq__(self, pkr):
        return self.trace == pkr

    def __ne__(self, pkr):
        return self.trace != pkr

    def __le__(self, pkr):
        return self.trace <= pkr

    def __ge__(self, pkr):
        return self.trace >= pkr

    def __lt__(self, pkr):
        return self.trace < pkr

    def __gt__(self, pkr):
        return self.trace > pkr

    def __add__(self, pkr):
        return self.trace + pkr

    def __sub__(self, pkr):
        return self.trace - pkr

    def __mul__(self, pkr):
        return self.trace * pkr

    def __floordiv__(self, pkr):
        return self.trace // pkr

    def __truediv__(self, pkr):
        return self.trace / pkr

    def __mod__(self, pkr):
        return self.trace % pkr

    def __lshift__(self, pkr):
        return self.trace << pkr

    def __rshift__(self, pkr):
        return self.trace >> pkr

    def __and__(self, pkr):
        return self.trace & pkr

    def __or__(self, pkr):
        return self.trace | pkr

    def __xor__(self, pkr):
        return self.trace ^ pkr

    def __pow__(self, pkr):
        return self.trace ** pkr

    def __pos__(self):
        return +self.trace

    def __neg__(self):
        return -self.trace

    def __not__(self):
        return not self.trace

    def __inv__(self):
        return ~self.trace

    def __abs__(self):
        return abs(self.trace)

    def trig_times(self):
        """Return list of times trace value is true (non-zero)."""
        return self.trace.trig_times()


class PeekerGroup(dict):
    def __init__(self, **kwargs):
        super().__init__()
        for name, signal in kwargs.items():
            peeker = Peeker(signal, name)
            self[name] = peeker
            setattr(self, name, peeker)

    def to_table(self, *names, **kwargs):

        format = kwargs.get("format", "simple")

        if names:
            # Go through the provided names and split any containing spaces
            # into individual names.
            names = [nm for name in names for nm in name.split()]
        else:
            # If no names provided, use all the peekers in this group.
            names = self.keys()

        PeekerBase._clean_names()
        peeker_names = [self[n].trace.name for n in names]

        return PeekerBase.to_table(*peeker_names, **kwargs)

    def to_text_table(self, *names, **kwargs):
        if "format" not in kwargs:
            kwargs["format"] = "simple"
        print(self.to_table(*names, **kwargs))

    def to_html_table(self, *names, **kwargs):
        kwargs["format"] = "html"
        tbl_html = self.to_table(*names, **kwargs)

        # Generate the HTML from the JSON.
        DISP.display_html(DISP.HTML(tbl_html))

    def to_matplotlib(self, *names, **kwargs):
        """
        Display waveforms stored in peekers in Jupyter notebook.

        Args:
            *names: A list of strings containing the names for the Peekers that
                will be displayed. A string may contain multiple,
                space-separated names.

        Keywords Args:
            start_time: The earliest (left-most) time bound for the waveform display.
            stop_time: The latest (right-most) time bound for the waveform display.
            title: String containing the title placed across the top of the display.
            caption: String containing the caption placed across the bottom of the display.
            tick: If true, times are shown at the tick marks of the display.
            tock: If true, times are shown between the tick marks of the display.
            width: The width of the waveform display in inches.
            height: The height of the waveform display in inches.

        Returns:
            Nothing.
        """

        if names:
            # Go through the provided names and split any containing spaces
            # into individual names.
            names = [nm for name in names for nm in name.split()]
        else:
            # If no names provided, use all the peekers in this group.
            names = self.keys()

        PeekerBase._clean_names()
        peeker_names = [self[n].trace.name for n in names]
        PeekerBase.to_matplotlib(*peeker_names, **kwargs)

    def to_wavedrom(self, *names, **kwargs):
        """
        Display waveforms stored in peekers in Jupyter notebook.

        Args:
            *names: A list of strings containing the names for the Peekers that
                will be displayed. A string may contain multiple,
                space-separated names.

        Keywords Args:
            start_time: The earliest (left-most) time bound for the waveform display.
            stop_time: The latest (right-most) time bound for the waveform display.
            title: String containing the title placed across the top of the display.
            caption: String containing the caption placed across the bottom of the display.
            tick: If true, times are shown at the tick marks of the display.
            tock: If true, times are shown between the tick marks of the display.
            width: The width of the waveform display in pixels.

        Returns:
            Nothing.
        """

        if names:
            # Go through the provided names and split any containing spaces
            # into individual names.
            names = [nm for name in names for nm in name.split()]
        else:
            # If no names provided, use all the peekers in this group.
            names = self.keys()

        PeekerBase._clean_names()
        peeker_names = [self[n].trace.name for n in names]
        PeekerBase.to_wavedrom(*peeker_names, **kwargs)


def _sort_names(names):
    """
    Sort peeker names by index and alphabetically.

    For example, the peeker names would be sorted as a[0], b[0], a[1], b[1], ...
    """

    def index_key(lbl):
        """Index sorting."""
        m = re.match(".*\[(\d+)\]$", lbl)  # Get the bracketed index.
        if m:
            return int(m.group(1))  # Return the index as an integer.
        return -1  # No index found so it comes before everything else.

    def name_key(lbl):
        """Name sorting."""
        m = re.match("^([^\[]+)", lbl)  # Get name preceding bracketed index.
        if m:
            return m.group(1)  # Return name.
        return ""  # No name found.

    srt_names = sorted(names, key=name_key)
    srt_names = sorted(srt_names, key=index_key)
    return srt_names


def setup(cls, use_wavedrom=False, use_jupyter=True):
    """Setup options and shortcut functions."""

    global clear_traces, show_traces, show_waveforms, show_text_table, show_html_table, export_dataframe

    if use_wavedrom:
        cls.show_waveforms = cls.to_wavedrom
        # PeekerGroup.show_waveforms = PeekerGroup.to_matplotlib
        cls.show_traces = traces_to_wavedrom
    else:
        cls.show_waveforms = cls.to_matplotlib
        # PeekerGroup.show_waveforms = PeekerGroup.to_wavedrom
        cls.show_traces = traces_to_matplotlib

    # Create an intermediary function to call cls.show_waveforms and assign it to show_waveforms.
    # Then if cls.show_waveforms is changed, any calls to show_waveforms will call the changed 
    # function. Directly assigning cls.show_waveforms to show_waveforms would mean any external
    # code that calls show_waveforms() would always call the initially-assigned function even if
    # cls.show_waveforms got a different assignment later.
    def shw_wvfrms(*args, **kwargs):
        cls.show_waveforms(*args, **kwargs)
    show_waveforms = shw_wvfrms

    def shw_trcs(*args, **kwargs):
        cls.show_traces(*args, **kwargs)
    show_traces = shw_trcs

    # These class methods don't change as the options are altered, so just assign them
    # to shortcuts without creating intermediary functions like above.
    clear_traces = cls.clear_traces
    export_dataframe = cls.to_dataframe
    show_text_table = cls.to_text_table
    show_html_table = cls.to_html_table

    global USE_JUPYTERLAB
    USE_JUPYTERLAB = not use_jupyter
