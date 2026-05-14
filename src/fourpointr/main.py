import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

#import pyvisa

import sys
import serial.tools.list_ports
import numpy as np
import pandas as pd
from time import sleep
from thermocouples_reference import thermocouples

from pymeasure.display.Qt import QtWidgets
from pymeasure.experiment import Procedure, Results
from pymeasure.experiment.parameters import Metadata
from pymeasure.instruments.keithley import Keithley2400
from pymeasure.display.windows import ManagedWindow

from PyQt5.QtGui import QFont

from window import FourPointWindow
from display_parameter import DisplayListParameter, DisplayIntegerParameter, DisplayFloatParameter


class FourPointOne(Procedure):

    # sourcemeter_address = 'ASRL5::INSTR' # necessary for the TempScheduler
    reference_temperature = 22 #oC

    max_current = DisplayFloatParameter('Maximum Current', units='mA', default=10, maximum=1050, minimum=0, orientation='v', tooltip='Select a value between 0 and 1050 mA')
    min_current = DisplayFloatParameter('Minimum Current', units='mA', default=-10, maximum=0, minimum=-1050, orientation='v', tooltip='Select a value between -1050 and 0 mA')
    current_step = DisplayFloatParameter('Current Step', units='mA', default=1, orientation='v', tooltip='Step size between current values')
    compliance_voltage = DisplayFloatParameter('Compliance Voltage', units='V', default=100, maximum=210, minimum=0, orientation='v', tooltip='Maximum value is 210 V')
    acquisition_time = DisplayListParameter('Acquisition Time', units='ms', choices=[2, 20, 200], default=20, orientation='v', tooltip='Voltage measurement time per datapoint; fast, balanced, precise')
    buffer = DisplayIntegerParameter('Buffer Size', default=3, maximum=10, minimum=3, orientation='v', tooltip='Number of measurements averaged into a single datapoint, minimum 3')
    delay = DisplayFloatParameter('Delay Time', units='ms', default=20, minimum=20, orientation='v', tooltip='Time delay between measurements')

    starting_temperature = Metadata('Starting temperature', fget='initial_temp', units='oC')

    DATA_COLUMNS = ['Current (A)', 'Voltage (V)', 'Voltage STD', 'Resistance']

    def find_device_address(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "ATEN USB to Serial Bridge" in port.description:
                com_port_number = int(port.device[3:])
                visa_address = f'ASRL{com_port_number}::INSTR'
                return visa_address
        return None

    def startup(self):
        log.info("Setting up instruments")
        self.sourcemeter = Keithley2400(self.find_device_address())
        self.initial_temp = self.save_temp_to_header()

        self.sourcemeter.reset()
        self.sourcemeter.use_rear_terminals()
        self.sourcemeter.apply_current(current_range=self.max_current*1e-3, compliance_voltage=self.compliance_voltage)
        self.sourcemeter.measure_voltage(nplc=self.acquisition_time/20, voltage=self.compliance_voltage, auto_range=True)
        sleep(0.1)
        self.sourcemeter.stop_buffer()
        self.sourcemeter.disable_buffer()


    def execute(self):
        currents_up = np.arange(0, self.max_current, self.current_step)
        # print(self.current_step, currents_up)
        currents_down = np.arange(self.max_current, self.min_current, -self.current_step)
        currents_back_up = np.arange(self.min_current, 0, self.current_step)
        currents = np.concatenate((currents_up, currents_down, currents_back_up))  # Include the reverse
        currents *= 1e-3  # to mA from A
        steps = len(currents) # calculate steps for progress bar estimate

        log.info("Starting current sweep")
        self.sourcemeter.enable_source()

        for i, current in enumerate(currents):
            log.debug("Measuring current: %g mA" % current)

            self.sourcemeter.config_buffer(points=self.buffer, delay=0)
            self.sourcemeter.source_current = current
            self.sourcemeter.start_buffer()
            self.sourcemeter.wait_for_buffer()

            voltage = self.sourcemeter.means[0]
            sleep(1.0)
            voltage_std = self.sourcemeter.standard_devs[0]

            if abs(current) <= 1e-10:
                resistance = np.nan
            else:
                resistance = voltage / current
            data = {
                'Current (A)': current,
                'Voltage (V)': voltage,
                'Voltage STD': voltage_std,
                'Resistance': resistance
            }
            self.emit('results', data)
            self.emit('progress', 100. * i / steps)
            if self.should_stop():
                log.warning("Catch stop command in procedure")
                break

    def shutdown(self):
        try:
            self.sourcemeter.reset()
            sleep(1)
            self.sourcemeter.shutdown()
            self.sourcemeter = None
            log.info("Measurement finished; sourcemeter shut down.")
        except:
            log.info('Shutdown failed')
            self.sourcemeter = None

    def save_temp_to_header(self):
        self.sourcemeter.reset()
        self.sourcemeter.apply_current(current_range=0.001, compliance_voltage=1)
        self.sourcemeter.source_current = 0

        self.sourcemeter.measure_voltage(nplc=1, voltage=1, auto_range=True)

        self.sourcemeter.use_front_terminals()

        self.sourcemeter.enable_source()
        sleep(1)

        typeK = thermocouples['K'] # thermocouple output converter between mV and deg C
        temperatures = np.zeros(5)

        for _ in range(5):
            voltage = self.sourcemeter.voltage
            temperature = typeK.inverse_CmV(voltage*1000, Tref=22.0)
            temperatures = np.roll(temperatures, -1)
            temperatures[-1] = temperature
            sleep(1)
        average_temperature = np.mean(temperatures)
        rounded_avg_temp = round(average_temperature, 2)
        return rounded_avg_temp



class MainWindow(FourPointWindow):
    def __init__(self, **kwargs):
        super().__init__(
            procedure_class=FourPointOne,
            inputs=['max_current', 'min_current', 'current_step', 'compliance_voltage', 'buffer', 'acquisition_time', 'delay'],
            displays=['max_current', 'min_current', 'current_step'],
            x_axis='Current (A)',
            y_axis='Voltage (V)',
            directory_input = True,
            **kwargs,
        )
        self.setWindowTitle('Four-point resistance measurements')


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    # Set a default font for the entire application
    default_font = QFont()
    default_font.setPointSize(10)  # Set the default font size here
    app.setFont(default_font)

    app.setStyle('qt5-style')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())