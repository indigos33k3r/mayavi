"""A simple filter that thresholds on input data.

"""
# Author: Prabhu Ramachandran <prabhu_r@users.sf.net>
# Copyright (c) 2005, Enthought, Inc.
# Author: Gael Varoquaux <gael.varoquaux@normalesup.org>
# Copyright (c) 2010, Enthought, Inc.
# License: BSD Style.

import numpy as np

# Enthought library imports.
from traits.api import Instance, Range, Float, Bool, \
                                 Property, Enum
from traitsui.api import View, Group, Item
from tvtk.api import tvtk

# Local imports
from mayavi.core.filter import Filter
from mayavi.core.pipeline_info import PipelineInfo
from mayavi.core.common import is_old_pipeline


######################################################################
# `Threshold` class.
######################################################################
class Threshold(Filter):

    # The version of this class.  Used for persistence.
    __version__ = 0

    # The threshold filter used.
    threshold_filter = Property(Instance(tvtk.Object, allow_none=False), record=True)

    # The filter type to use, specifies if the cells or the points are
    # cells filtered via a threshold.
    filter_type = Enum('cells', 'points',
                       desc='if thresholding is done on cells or points')

    # Lower threshold (this is a dynamic trait that is changed when
    # input data changes).
    lower_threshold = Range(value=-1.0e20,
                            low='_data_min',
                            high='_data_max',
                            enter_set=True,
                            auto_set=False,
                            desc='the lower threshold of the filter')

    # Upper threshold (this is a dynamic trait that is changed when
    # input data changes).
    upper_threshold = Range(value=1.0e20,
                            low='_data_min',
                            high='_data_max',
                            enter_set=True,
                            auto_set=False,
                            desc='the upper threshold of the filter')

    # Automatically reset the lower threshold when the upstream data
    # changes.
    auto_reset_lower = Bool(True, desc='if the lower threshold is '
                            'automatically reset when upstream '
                            'data changes')

    # Automatically reset the upper threshold when the upstream data
    # changes.
    auto_reset_upper = Bool(True, desc='if the upper threshold is '
                            'automatically reset when upstream '
                            'data changes')

    input_info = PipelineInfo(datasets=['any'],
                              attribute_types=['any'],
                              attributes=['any'])

    output_info = PipelineInfo(datasets=['poly_data',
                                         'unstructured_grid'],
                               attribute_types=['any'],
                               attributes=['any'])

    # Our view.
    view = View(Group(Group(Item(name='filter_type'),
                            Item(name='lower_threshold'),
                            Item(name='auto_reset_lower'),
                            Item(name='upper_threshold'),
                            Item(name='auto_reset_upper')),
                      Item(name='_'),
                      Group(Item(name='threshold_filter',
                                 show_label=False,
                                 visible_when='object.filter_type == "cells"',
                                 style='custom', resizable=True)),
                      ),
                resizable=True
                )

    ########################################
    # Private traits.

    # These traits are used to set the limits for the thresholding.
    # They store the minimum and maximum values of the input data.
    _data_min = Float(-1e20)
    _data_max = Float(1e20)

    # The threshold filter for cell based filtering
    _threshold = Instance(tvtk.Threshold, args=(), allow_none=False)

    # The threshold filter for points based filtering.
    _threshold_points = Instance(tvtk.ThresholdPoints, args=(), allow_none=False)

    # Internal data to
    _first = Bool(True)

    ######################################################################
    # `object` interface.
    ######################################################################
    def __get_pure_state__(self):
        d = super(Threshold, self).__get_pure_state__()
        # These traits are dynamically created.
        for name in ('_first', '_data_min', '_data_max'):
            d.pop(name, None)

        return d

    ######################################################################
    # `Filter` interface.
    ######################################################################
    def setup_pipeline(self):
        attrs = ['all_scalars', 'attribute_mode',
                 'component_mode', 'selected_component']
        self._threshold.on_trait_change(self._threshold_filter_edited,
                                        attrs)

    def update_pipeline(self):
        """Override this method so that it *updates* the tvtk pipeline
        when data upstream is known to have changed.

        This method is invoked (automatically) when the input fires a
        `pipeline_changed` event.
        """
        if len(self.inputs) == 0:
            return

        # By default we set the input to the first output of the first
        # input.
        fil = self.threshold_filter
        if self.inputs[0].has_output_port():
            fil.input_connection = self.inputs[0].get_output_object()
        else:
            if is_old_pipeline():
                fil.input = self.inputs[0].outputs[0]
            else:
                fil.set_input_data(self.inputs[0].outputs[0])

        self._update_ranges()
        self._set_outputs([self.threshold_filter.output])

    def update_data(self):
        """Override this method to do what is necessary when upstream
        data changes.

        This method is invoked (automatically) when any of the inputs
        sends a `data_changed` event.
        """
        if len(self.inputs) == 0:
            return

        self._update_ranges()

        # Propagate the data_changed event.
        self.data_changed = True

    ######################################################################
    # Non-public interface
    ######################################################################
    def _lower_threshold_changed(self, new_value):
        fil = self.threshold_filter
        fil.threshold_between(new_value, self.upper_threshold)
        fil.update()
        self.data_changed = True

    def _upper_threshold_changed(self, new_value):
        fil = self.threshold_filter
        fil.threshold_between(self.lower_threshold, new_value)
        fil.update()
        self.data_changed = True

    def _update_ranges(self):
        """Updates the ranges of the input.
        """
        data_range = self._get_data_range()
        if len(data_range) > 0:
            dr = data_range
            if self._first:
                self._data_min, self._data_max = dr
                self.set(lower_threshold = dr[0], trait_change_notify=False)
                self.upper_threshold = dr[1]
                self._first = False
            else:
                if self.auto_reset_lower:
                    self._data_min = dr[0]
                    notify = not self.auto_reset_upper
                    self.set(lower_threshold = dr[0],
                             trait_change_notify=notify)
                if self.auto_reset_upper:
                    self._data_max = dr[1]
                    self.upper_threshold = dr[1]

    def _get_data_range(self):
        """Returns the range of the input scalar data."""
        input = self.inputs[0].outputs[0]
        data_range = []
        ps = input.point_data.scalars
        cs = input.cell_data.scalars

        # FIXME: need to be able to handle cell and point data
        # together.
        if ps is not None:
            data_range = list(ps.range)
            if np.isnan(data_range[0]):
                data_range[0] = float(np.nanmin(ps.to_array()))
            if np.isnan(data_range[1]):
                data_range[1] = float(np.nanmax(ps.to_array()))
        elif cs is not None:
            data_range = cs.range
            if np.isnan(data_range[0]):
                data_range[0] = float(np.nanmin(cs.to_array()))
            if np.isnan(data_range[1]):
                data_range[1] = float(np.nanmax(cs.to_array()))
        return data_range

    def _auto_reset_lower_changed(self, value):
        if len(self.inputs) == 0:
            return
        if value:
            dr = self._get_data_range()
            self._data_min = dr[0]
            self.lower_threshold = dr[0]

    def _auto_reset_upper_changed(self, value):
        if len(self.inputs) == 0:
            return
        if value:
            dr = self._get_data_range()
            self._data_max = dr[1]
            self.upper_threshold = dr[1]

    def _get_threshold_filter(self):
        if self.filter_type == 'cells':
            return self._threshold
        else:
            return self._threshold_points

    def _filter_type_changed(self, value):
        if value == 'cells':
            old = self._threshold_points
            new = self._threshold
        else:
            old = self._threshold
            new = self._threshold_points
        self.trait_property_changed('threshold_filter', old, new)

    def _threshold_filter_changed(self, old, new):
        if len(self.inputs) == 0:
            return
        fil = new
        if self.inputs[0].has_output_port():
            fil.input_connection = self.inputs[0].get_output_object()
        else:
            fil.input = self.inputs[0].outputs[0]
        fil.threshold_between(self.lower_threshold,
                              self.upper_threshold)
        fil.update()
        self._set_outputs([fil.output])

    def _threshold_filter_edited(self):
        self.threshold_filter.update()
        self.data_changed = True
