#####################################################################
#                                                                   #
# detuning.py                                                       #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the labscript suite (see                     #
# http://labscriptsuite.org) and is licensed under the Simplified   #
# BSD License. See the license.txt file in the root of the project  #
# for the full license.                                             #
#                                                                   #
#####################################################################
from __future__ import division, unicode_literals, print_function, absolute_import

from .UnitConversionBase import *
from scipy import interpolate
import numpy as np


class offset_frequency(UnitConversion):
    base_unit = 'V'
    # Derived units are: detuning d_MHz, beat frequency b_MHz
    derived_units = ['d_MHz', 'b_MHz']

    def __init__(self, calibration_parameters=None):
        self.parameters = calibration_parameters
        self.parameters.setdefault('offset', 0)
        self.parameters.setdefault('voltages', [0, 10])
        self.parameters.setdefault('frequencies', [0, 10])
        self.parameters.setdefault('f_greater_master', False)

        # store interpolation functions for later use
        self.interpolations = {}
        scale_factor = 1 if self.parameters['f_greater_master'] else -1
        detunings = scale_factor * (np.array(self.parameters['frequencies']) - self.parameters['offset'])
        self.interpolations['d_MHz_to_base'] = self.interpfunc(detunings, self.parameters['voltages'])
        self.interpolations['d_MHz_from_base'] = self.interpfunc(self.parameters['voltages'], detunings)

        self.interpolations['b_MHz_to_base'] = self.interpfunc(self.parameters['frequencies'], self.parameters['voltages'])
        self.interpolations['b_MHz_from_base'] = self.interpfunc(self.parameters['voltages'], self.parameters['frequencies'])

        UnitConversion.__init__(self, self.parameters)

    def interpfunc(self, xs, ys):
        return interpolate.interp1d(xs, ys, assume_sorted=False, bounds_error=False, fill_value='extrapolate')

    def d_MHz_to_base(self, detuning_MHz):
        return self.interpolations['d_MHz_to_base'](detuning_MHz)

    def d_MHz_from_base(self, voltage):
        return self.interpolations['d_MHz_from_base'](voltage)

    def b_MHz_to_base(self, beat_MHz):
        return self.interpolations['b_MHz_to_base'](beat_MHz)

    def b_MHz_from_base(self, voltage):
        return self.interpolations['b_MHz_from_base'](voltage)


class double_pass_frequency(UnitConversion):
    base_unit = 'V'
    # Derived units are: double_pass frequency dp_MHz
    derived_units = ['dp_MHz'] # Use later on 'd_MHz' for detuned MHz. Therefore the offset of the TA-Seed needs to be known.

    def __init__(self, calibration_parameters=None):
        self.parameters = calibration_parameters
        # self.parameters.setdefault('offset', 0)
        self.parameters.setdefault('voltages', [0, 10])
        self.parameters.setdefault('frequencies', [0, 10])
        # self.parameters.setdefault('f_greater_master', False)

        # store interpolation functions for later use
        self.interpolations = {}
        # scale_factor = 1 if self.parameters['f_greater_master'] else -1
        # detunings = scale_factor * (np.array(self.parameters['frequencies']) - self.parameters['offset'])
        # self.interpolations['d_MHz_to_base'] = self.interpfunc(detunings, self.parameters['voltages'])
        # self.interpolations['d_MHz_from_base'] = self.interpfunc(self.parameters['voltages'], detunings)

        # To Get the double pass frequencies, multiply the VCO-frequency by 2:
        self.interpolations['dp_MHz_to_base'] = self.interpfunc(self.parameters['frequencies']*2, self.parameters['voltages'])
        self.interpolations['dp_MHz_from_base'] = self.interpfunc(self.parameters['voltages'], self.parameters['frequencies']*2)

        UnitConversion.__init__(self, self.parameters)

    def interpfunc(self, xs, ys):
        return interpolate.interp1d(xs, ys, assume_sorted=False, bounds_error=False, fill_value='extrapolate')

    # def d_MHz_to_base(self, detuning_MHz):
    #     return self.interpolations['d_MHz_to_base'](detuning_MHz)

    # def d_MHz_from_base(self, voltage):
    #     return self.interpolations['d_MHz_from_base'](voltage)

    def dp_MHz_to_base(self, beat_MHz):
        return self.interpolations['dp_MHz_to_base'](beat_MHz)

    def dp_MHz_from_base(self, voltage):
        return self.interpolations['dp_MHz_from_base'](voltage)