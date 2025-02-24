# -*- coding: utf-8 -*-
"""
Created on Fri Feb 19 17:28:21 2021

@author: ATOMICS-Steuerung, Daniel Derr
"""

from .UnitConversionBase import *
import numpy as np

class LogAmplifier_old(UnitConversion):
    base_unit = "V"
    derived_units = ["logAmp_mV"]

    def __init__(self, calibration_parameters=None):
        # These parameters are loaded from a globals.h5 type file automatically
        if calibration_parameters is None:
            calibration_parameters = {}
        self.parameters = calibration_parameters

        # V[V] = slope * log(V[logAmp_mV*1e-3]) + shift
        # Saturates at saturation Volts
        self.parameters.setdefault("slope", 1) # A/V
        self.parameters.setdefault("shift", 0) # A
        self.parameters.setdefault("saturation", 10) # V

        UnitConversion.__init__(self,self.parameters)
        # We should probably also store some hardware limits here, and use them accordingly
        # (or maybe load them from a globals file, or specify them in the connection table?)

    def logAmp_mV_to_base(self, log_m_volts):
        #here is the calibration code that may use self.parameters
        volts = self.parameters["slope"] * np.log(log_m_volts*1e-3) + self.parameters["shift"]
        return volts

    def logAmp_mV_from_base(self, volts):
        volts = np.minimum(volts, self.parameters["saturation"])
        log_m_volts = np.exp((volts - self.parameters["shift"])/self.parameters["slope"]) * 1e3
        return log_m_volts
