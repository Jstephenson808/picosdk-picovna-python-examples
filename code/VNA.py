from VNA_calibration import VnaCalibration
from VNA_data import VnaData

import os
import win32com.client

from datetime import datetime, timedelta
import pandas as pd

from VNA_enums import (
    MeasurementFormat,
    SParam,
    MeasureSParam,
    DateFormats,
)
from VNA_exceptions import *
from VNA_utils import (
    get_data_path,
    get_root_folder_path,
    countdown_timer
)



class VNA:

    @staticmethod
    def file_label_input() -> str:
        file_label = input(
            "Input label for file (no spaces) or press enter for no label:"
        )
        while (file_label != "") and not VnaData.test_file_name(file_label):
            file_label = input("Incorrect format try again or enter to skip:")
        return file_label

    def __init__(
        self,
        calibration: VnaCalibration,
        vna_data: VnaData,
        vna_string="PicoControl2.PicoVNA_2",
    ):
        self.calibration = calibration
        self.vna_object = win32com.client.gencache.EnsureDispatch(vna_string)
        self.output_data = vna_data


    def connect(self):
        print("Connecting VNA")
        search_vna = self.vna_object.FND()
        if search_vna == 0:
            raise VNAError("Connection Failed, do you have Pico VNA Open?")
        print(f"VNA {str(search_vna)} Loaded,\n\rif you stop the program without closing the connection you will need to restart the VNA")

    def close_connection(self):
        self.vna_object.CloseVNA()
        print("VNA Closed")

    def load_cal(self):
        """
        loads the calibration which is stored in object
        :return:
        """
        print("Loading Calibration")
        ans = self.vna_object.LoadCal(self.calibration.calibration_path)
        if ans != "OK":
            raise VNAError(f"Calibration Failure {ans}")
        print(f"Result {ans}")

    def get_data(
        self, s_parameter: SParam, data_format: MeasurementFormat, point=0
    ) -> str:
        """
        wrapper for getting data from the VNA after measurement
        :param s_parameter: S Param data to be returned
        :param data_format: measurement requested
        :param point:
        :return: data string which is ',' separted in the format "freq, measurement_value_at_freq, freq, measurement_value_at_freq,..."
        """
        return self.vna_object.GetData(s_parameter.value, data_format.value, point)



    def generate_output_path(
        self,
        output_folder: str,
        s_params_saved: SParam,
        run_time: timedelta,
        fname="",
        label="",
    ):
        """
        Utility function to generate file name and join it to path
        :param s_params_measure: measured s parameteres
        :param run_time:
        :param fname:
        :return:
        """
        if fname != "" and label != "":
            label_fname = ("_").join((fname, label))
        else:
            label_fname = ("").join((fname, label))

        if label == "":
            label = datetime.now().strftime(DateFormats.DATE_FOLDER.value)

        if label_fname != "":
            label_fname += "_"

        s_params = ("_").join([s_param.value for s_param in s_params_saved])
        filename = f"{label_fname}{datetime.now().strftime(DateFormats.CURRENT.value)}_{s_params}_{run_time.seconds}_secs.csv"
        return os.path.join(get_root_folder_path(), output_folder, label, filename)



    # add in timer logging
    def measure_wrapper(self, str):
        return self.vna_object.Measure(str)

    #@timer_func
    def take_measurement(
        self,
        s_params_measure: MeasureSParam,
        s_params_output: [SParam],
        elapsed_time: timedelta,
        label: str,
        id,
    ):
        """
        Takes measurement on the VNA, processes it and appends it to the output_data.data_frame
        df
        :param s_params_measure: The S params for the VNA to measure, using
        :param s_params_output:
        :param elapsed_time:
        """

        self.measure_wrapper(s_params_measure.value)

        for s_param in s_params_output:
            self.get_data(s_param, MeasurementFormat.LOGMAG)
            self.get_data(s_param, MeasurementFormat.PHASE)
            self.output_data.add_measurement_to_data_frame(
                s_param, elapsed_time, label, id
            )

    def input_movement_label(self) -> str:
        label = input("Provide gesture label or leave blank for none:")
        return label

    def measure(
        self,
        run_time: timedelta,
        s_params_measure: MeasureSParam = MeasureSParam.ALL,
        s_params_output: [SParam] = None,
        file_name: str = "",
        output_dir=get_data_path(),
        label=None,
        *,
        print_countdown=False,
    ) -> VnaData:

        # label = 'test'
        if label is None:
            label = self.input_movement_label()

        if s_params_output == None:
            s_params_output = [SParam.S11]


        self.connect()
        self.load_cal()

        self.output_data.csv_path = self.generate_output_path(output_dir, s_params_output, run_time, file_name, label)
        os.makedirs(os.path.dirname(self.output_data.csv_path), exist_ok=True)
        print(f"Saving to {self.output_data.csv_path}")
        countdown_timer(2)
        start_time = datetime.now()
        finish_time = start_time + run_time
        current_time = datetime.now()
        measurement_number = 0
        while current_time < finish_time:
            current_time = datetime.now()
            elapsed_time = current_time - start_time
            if print_countdown:
                print(f"Running for another {(run_time - elapsed_time)}")
            self.take_measurement(
                s_params_measure,
                s_params_output,
                elapsed_time,
                label,
                id=start_time.strftime(DateFormats.CURRENT.value),
            )
            measurement_number += 1
            if measurement_number % 10 == 0:

                self.output_data.data_frame.to_csv(
                    self.output_data.csv_path, index=False
                )

        self.output_data.data_frame.to_csv(self.output_data.csv_path, index=False)

        self.vna_object.CloseVNA()
        print("VNA Closed")
        return self.output_data

    def measure_n_times(
            self,
            *,
            run_time: timedelta,
            n_measures=1,
            print_elapsed_time=False,
            s_params_measure: MeasureSParam = MeasureSParam.ALL,
            s_params_output: [SParam] = None,
            file_name: str = "",
            output_dir=get_data_path(),
            label=None,
            countdown_seconds=2,
            save_interval = 10
    ):
        """
        nb * means these are key word args only, this is for clarity

        Measures from the VNA for the provided run time, this is then repeated n_measures times.
        The provided label is added to the data in the data frame, label should be the gesture in most instances.

        s_param_measure is the data which the VNA will capture, the parameters which are then saved is s_param_output.
        These are two different processes, the measurement and retrival of the data. Both of these are enum types which evaluate to strings which are
        eventually passed to the VNA to capture/return the data.

        File name can be passed but if none is passed then the user is prompted.

        Output dir can be specified but is defaulted to the data_path.

        :param run_time:
        :param s_params_measure:
        :param s_params_output:
        :param file_name:
        :param output_dir:
        :param label:
        :param countdown_seconds:
        :param print_elapsed_time:
        :param n_measures:
        :param save_interval:
        """

        # prompt for label
        if label is None:
            label = self.input_movement_label()

        # this the output s parameter, which is RETRIEVED from the VNA
        if s_params_output == None:
            s_params_output = [SParam.S11]

        # connect and load calibration
        self.connect()
        self.load_cal()

        for i in range(n_measures):
            # Each file is a single measurement for a given amount of time
            # so for each of the measurements a new .csv is created

            self.output_data.csv_path = self.generate_output_path(
                output_dir, s_params_output, run_time, file_name, label
            )

            # just make dir if it doesn't exist
            os.makedirs(os.path.dirname(self.output_data.csv_path), exist_ok=True)

            print(f"Saving to {self.output_data.csv_path}")
            print(f"Measurement {i+1} of {n_measures}")

            # makes more sense for the whole thing to be a single df
            # each of them being a .csv
            self.output_data.data_frame = None
            countdown_timer(countdown_seconds)
            start_time = datetime.now()
            finish_time = start_time + run_time
            current_time = datetime.now()
            measurement_number = 0
            while current_time < finish_time:
                current_time = datetime.now()
                elapsed_time = current_time - start_time
                if print_elapsed_time:
                    print(f"Running for another {(run_time - elapsed_time)}")
                # method to take measurements and add them to the data frame
                self.take_measurement(
                    s_params_measure,
                    s_params_output,
                    elapsed_time,
                    label,
                    id=start_time.strftime(DateFormats.CURRENT.value),
                )
                measurement_number += 1
                if measurement_number % save_interval == 0:
                    self.output_data.data_frame.to_csv(
                        self.output_data.csv_path, index=False
                    )

        self.output_data.data_frame.to_csv(self.output_data.csv_path, index=False)

        self.close_connection()