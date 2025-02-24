# -*- coding: utf-8 -*-
"""
Created on Fri Feb 19 17:28:21 2021

@author: ATOMICS-Steuerung, Daniel Derr
"""

from .UnitConversionBase import *
import numpy as np

class LogAmp_PD(UnitConversion):
    base_unit = "V"
    derived_units = ["log_amp_PD_mW"]

    def __init__(self, calibration_parameters=None):
        # These parameters are loaded from a globals.h5 type file automatically
        if calibration_parameters is None:
            calibration_parameters = {}
        self.parameters = calibration_parameters

        # Saturates at saturation Volts
        self.parameters.setdefault("prefactor", 1) # V
        self.parameters.setdefault("offset", 0) # V
        self.parameters.setdefault("powershift",0)
        self.parameters.setdefault("saturation", 10) # V

        UnitConversion.__init__(self,self.parameters)

    def log_amp_PD_mW_to_base(self, log_amp_PD_mW):
        U_control = self.parameters["prefactor"] * np.log(log_amp_PD_mW*1e-3 + self.parameters["powershift"]) + self.parameters["offset"] # V
        U_control = np.minimum(U_control, self.parameters["saturation"])
        return U_control

    def log_amp_PD_mW_from_base(self, U_control):
        U_control = np.minimum(U_control, self.parameters["saturation"])
        log_amp_PD_mW = (np.exp((U_control - self.parameters["offset"])/self.parameters["prefactor"]) - self.parameters["powershift"]) * 1e3# mV
        return log_amp_PD_mW
