import os

import pandas
import win32com.client
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from matplotlib import pyplot as plt
from enum import Enum


def mhz_to_hz(mhz):
    return mhz * 1000000


class TakeMeasurement(Enum):
    S11 = "S11"
    S21 = "S21"
    S11_S21 = "S11+S21"
    ALL = "All"


class GetMeasurement(Enum):
    S11 = "S11"
    S21 = "S21"
    S12 = "S12"
    S22 = "S22"


class MeasurementFormat(Enum):
    LOGMAG = "logmag"
    PHASE = "phase"
    REAL = "real"
    IMAG = "imag"
    SWR = "swr"
    GROUP_DELAY = "gd"
    TIME_DOMAIN = "td"

class DataFrameCols(Enum):
    TIME = "time"
    MEASUREMENT = "measurement"
    MEASUREMENT_FORMAT = "format"
    FREQUENCY = "frequency"
    MAGNITUDE = "magnitude"
    PHASE = "phase"

class VnaCalibration:

    def __init__(self, calibration_path: os.path, number_of_points: int, frequncy_range_hz: (int, int)):
        self.calibration_path = calibration_path
        self.number_of_points = number_of_points
        self.low_freq_hz = frequncy_range_hz[0]
        self.high_freq_hz = frequncy_range_hz[1]


class VNA:

    def __init__(self, calibration: VnaCalibration, vna_string="PicoControl2.PicoVNA_2"):
        self.calibration = calibration
        self.vna_object = win32com.client.gencache.EnsureDispatch(vna_string)
        self.output_df_magnitude = pd.DataFrame(columns=[cols.value for cols in DataFrameCols])

    def connect(self):
        print("Connecting VNA")
        findVNA = self.vna_object.FND()
        print('VNA ' + str(findVNA) + ' Loaded')

    def load_cal(self):
        print("Load Calibration")
        ans = self.vna_object.LoadCal(self.calibration.calibration_path)
        print("Result " + str(ans))

    def get_data(self, parameter: GetMeasurement, data_format: MeasurementFormat, point=0) -> str:
        return self.vna_object.GetData(parameter, data_format, point)

    def data_string_to_df(self,
                          time: datetime, measurement_string: str,
                          parameter: GetMeasurement,
                          data_format: DataFrameCols) -> pandas.DataFrame:
        split_data = measurement_string.split(',')
        frequencies = split_data[::2]
        data = split_data[1::2]
        data_dict = {
            DataFrameCols.TIME.value : [time for _ in frequencies],
            DataFrameCols.MEASUREMENT.value : [parameter for _ in frequencies],
            DataFrameCols.MEASUREMENT_FORMAT.value : [data_format for _ in frequencies],
            DataFrameCols.FREQUENCY.value : frequencies,
            data_format.value : data
        }
        return pd.DataFrame(data)


    # could take in 
    def measure(self, run_time: timedelta, s_params_measure: TakeMeasurement=TakeMeasurement
                .ALL, output_s_param: [GetMeasurement]=[GetMeasurement.S21]):
        self.connect()
        self.load_cal()

        start_time = datetime.now()
        finish_time = start_time + run_time

        while datetime.now() < finish_time:
            elapsed_time = datetime.now() - start_time
            self.vna_object.Measure(s_params_measure)
            for s_param in output_s_param:
                magnitude_df = self.data_string_to_df(
                    elapsed_time,
                    self.get_data(s_param, MeasurementFormat.LOGMAG),
                    DataFrameCols.MAGNITUDE
                )
                phase_df = self.data_string_to_df(
                    elapsed_time,
                    self.get_data(s_param, MeasurementFormat.PHASE),
                    DataFrameCols.PHASE
                )
                # append to df



