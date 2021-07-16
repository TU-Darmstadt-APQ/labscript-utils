# -*- coding: utf-8 -*-
"""
Created on Thu Apr  1 11:21:46 2021

@author: ATOMICS-Steuerung
"""

from .UnitConversionBase import *
import numpy as np

class LogAmplifier(UnitConversion):
    # U_control[V] = prefactor * ln(U_PD_mV*1e-3) + offset
    base_unit = "V"
    derived_units = ["U_PD_mV"]

    def __init__(self, calibration_parameters=None):
        # These parameters are loaded from a globals.h5 type file automatically
        if calibration_parameters is None:
            calibration_parameters = {}
        self.parameters = calibration_parameters

        # Saturates at saturation Volts
        self.parameters.setdefault("prefactor", 1) # V
        self.parameters.setdefault("offset", 0) # V
        self.parameters.setdefault("saturation", 10) # V

        UnitConversion.__init__(self,self.parameters)

    def U_PD_mV_to_base(self, U_PD_mV):
        U_control = self.parameters["prefactor"] * np.log(U_PD_mV*1e-3) + self.parameters["offset"] # V
        U_control = np.minimum(U_control, self.parameters["saturation"])
        return U_control

    def U_PD_mV_from_base(self, U_control):
        U_control = np.minimum(U_control, self.parameters["saturation"])
        U_PD_mV = np.exp((U_control - self.parameters["offset"])/self.parameters["prefactor"]) * 1e3 # mV
        return U_PD_mV
