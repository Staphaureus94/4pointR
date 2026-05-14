import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from pymeasure.display.curves import ResultsCurve
from pymeasure.display.widgets import TabWidget, PlotWidget
from pymeasure.display.Qt import QtCore, QtWidgets

from pymeasure.instruments.keithley import Keithley2400

import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QTimer, QThread, QMetaObject

import numpy as np
import os
import csv
import pandas as pd
from time import sleep
from datetime import datetime, timedelta
import re
import serial.tools.list_ports
from thermocouples_reference import thermocouples

from display_parameter import DisplayIntegerParameter, DisplayFloatParameter

from SOP import SOP_text

from scipy.stats import linregress

class AlteredPlotWidget(PlotWidget):
    def __init__(self, name, columns, x_axis=None, y_axis=None, refresh_time=0.2,
                 check_status=True, linewidth=1, symbol=None, parent=None, **kwargs):
        super().__init__(name, columns, x_axis=x_axis, y_axis=y_axis, refresh_time=refresh_time,
                         check_status=check_status, linewidth=linewidth, parent=parent, **kwargs)
        self.symbol = symbol

    def new_curve(self, results, color=pg.intColor(0), **kwargs):
        if 'pen' not in kwargs:
            kwargs['pen'] = pg.mkPen(color=color, width=self.linewidth)
        if 'antialias' not in kwargs:
            kwargs['antialias'] = False
        # if 'symbol' not in kwargs:
        #     kwargs['symbol'] = self.symbol  # Set the symbol parameter here
        curve = ResultsCurve(results,
                             x=self.plot_frame.x_axis,
                             y=self.plot_frame.y_axis,
                             **kwargs
                             )
        curve.setSymbol('s')
        curve.setSymbolBrush(pg.mkBrush(color=color))
        curve.setSymbolSize(5)
        return curve
    

class HelpWidget(TabWidget, QtWidgets.QWidget):
    help_text = SOP_text
    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        layout = QtWidgets.QVBoxLayout()
        help_text_field = QtWidgets.QTextEdit()
        help_text_field.setFontPointSize(12)
        help_text_field.setText(self.help_text)
        help_text_field.setReadOnly(True)
        layout.addWidget(help_text_field)

        self.setLayout(layout)

class SchedulerPlot(TabWidget, QtWidgets.QWidget):

    class Plot(pg.PlotWidget):
        def __init__(self, scheduler, title=None):

            super().__init__()
            if title is not None:
                self.setTitle(title)
            self.setBackground('w')
            self.setLabel('left', 'Temperature', color='k')
            #self.setLabel('bottom', 'Time', color='k')
            self.showGrid(x=False, y=True)

            x_axis = pg.DateAxisItem(orientation='bottom')
            x_axis.setLabel(text='Time', format='%H:%M:%S')
            self.setAxisItems({'bottom': x_axis})

            self.addLegend()

            self.curve = SchedulerPlot.Curve('Temperature', scheduler, (255, 0, 0))
            self.addItem(self.curve)

            self.gradient = SchedulerPlot.GradientLine(scheduler)
            self.addItem(self.gradient)
        
        def update(self, unnecessary_string): # other slots need the string
            try:
                self.curve.update()
                self.gradient.update()
            except Exception as e:
                print(f'Plot update failed: {e}')

    class GradientLine(pg.PlotDataItem):
        def __init__(self, scheduler):
            self.scheduler = scheduler
            self.x_axis = 'Time'
            self.pen = pg.mkPen(
                color='#0000ff',
                width=3
            )
            self.brush = pg.mkBrush(color='#0000ff')
            super().__init__(
                name='Best Fit Line',
                pen=self.pen,
                symbol='o',
                symbolBrush = self.brush,
                symbolSize = 5
            )

        def update(self):
            if self.scheduler.last_fit_line is not None:
                x, y = self.scheduler.last_fit_line
                self.setData(x, y)

    class Curve(pg.PlotDataItem):
        def __init__(self, name, scheduler, colour):
            self.scheduler = scheduler
            self.x_axis = 'Time'
            self.pen = pg.mkPen(
                color=colour,
                width=3
            )
            self.brush = pg.mkBrush(color=colour)
            super().__init__(
                name=name,
                pen=self.pen,
                symbol='o',
                symbolBrush = self.brush,
                symbolSize = 5
            )

        def update(self):
            self.setData(self.scheduler.df[self.x_axis], self.scheduler.df[self.name()])

    def __init__(self, name, scheduler):
        super().__init__(name)
        self.scheduler = scheduler
        self._setup_ui()
        self._layout()


    def _setup_ui(self):
        self.plot = SchedulerPlot.Plot(self.scheduler, 'Temperature')
        self.scheduler.new_temp_available.connect(self.plot.update)

    def _layout(self):
        vbox = QtWidgets.QVBoxLayout(self)
        vbox.addWidget(self.plot)

class TempScheduler(QtCore.QObject):
    queue_IV_measurement = QtCore.pyqtSignal(str) # str contains the temperature to 0 d.p.
    measurements_finished = QtCore.pyqtSignal() # should be obsolete as measurements run indefinitely
    status_update = QtCore.pyqtSignal(str) # updates the scheduler status display
    new_temp_available = QtCore.pyqtSignal(str) # updates temperature display and plot
    new_gradient_available = QtCore.pyqtSignal(str) # updates gradient display
    stability_signal = QtCore.pyqtSignal(str) # updates stability label in SchedulerPlot

    '''
    Since the temperature may become temporarily unstable due to a small random fluctuation,
    the stability may be unnecessarily broken unless a grace period is instituted. When the gradient is
    evaluated as unstable, the counter will increase by one until it reaches unstability_grace,
    at which point temperature_stable changes to False and the counter resets. The counter also resets
    if gradient evaluates as stable.
    '''
    unstability_grace = 60
    unstability_counter = 0

    _temperature_stable = False
    _scheduler_running = False
    _TC_disconnected = False

    @property
    def temperature_stable(self):
        return self._temperature_stable
    
    @temperature_stable.setter
    def temperature_stable(self, bool):
        self._temperature_stable = bool
        if self.temperature_stable:
            self.stability_signal.emit('Stable')
            logging.info('Stable temperature achieved.')
            self.delay_counter = self.delay
            self.delay_ticker.start(1000)

        elif not self.temperature_stable:
            self.stability_signal.emit('Unstable')
            logging.info('Temperature unstable Restarting delay timer.')
            self.status_update.emit('Awaiting temperature stabilisation\n')
            if self.delay_ticker.isActive():
                self.delay_ticker.stop()
            if self.interval_ticker.isActive():
                self.interval_ticker.stop()

    @property
    def is_running(self):
        return self._scheduler_running

    def __init__(self):
        super().__init__()
        # self.columns = ['Time', 'Temperature'] # if the line below works then this is obsolete
        self.df = pd.DataFrame(columns = ['Time', 'Temperature'])
        self.gradient_threshold = None # maximum T change rate [K/min] considered stable
        self.minimum_T = None # IV measurements will not be carried out below this temperature, scheduler will terminate
        self.t_ref = None # temperature of the thermocouple's reference junction
        
        self.typeK = thermocouples['K'] # thermocouple output converter between mV and deg C

        self.temp_loop_ticker = QTimer() # measures T every second
        self.temp_loop_ticker.timeout.connect(self.temp_measurement_loop)

        self.delay_ticker = QTimer() # delay between stable temperature and interval timer start
        self.delay_ticker.timeout.connect(self.delay_counter_function)
        self.delay = None

        self.interval_ticker = QTimer() # counts down to the measurement after reaching temperature stability
        self.interval_ticker.timeout.connect(self.interval_counter_function)
        self.interval = None

        self.writer = CSVWriter()

        self.last_fit_line = None

        

    def set_parameters(self, gradient_threshold, delay, interval, min_temperature, reference_temperature):
        #convert min to seconds
        self.gradient_threshold = gradient_threshold/60
        self.delay = int(delay*60) #in s
        self.interval = int(interval*60) #in s
        self.gradient_period = 60 #in s
        self.minimum_T = min_temperature # in oC
        self.t_ref = reference_temperature

    def find_device_address(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "ATEN USB to Serial Bridge" in port.description:
                com_port_number = int(port.device[3:])
                visa_address = f'ASRL{com_port_number}::INSTR'
                return visa_address

        return None    

    def initialise_sourcemeter(self):
        self.sourcemeter = Keithley2400(self.find_device_address())
        self.sourcemeter.reset()
        self.sourcemeter.apply_current()
        self.sourcemeter.source_current_range = 0.001
        self.sourcemeter.source_current = 0
        self.sourcemeter.compliance_voltage = 1

        self.sourcemeter.measure_voltage()
        self.sourcemeter.voltage_range = 0.5
        self.sourcemeter.voltage_nplc = 1

        self.sourcemeter.use_front_terminals()

        self.sourcemeter.enable_source()
        sleep(1)

    def shutdown_sourcemeter(self):
        if hasattr(self, 'sourcemeter'):
            if self.sourcemeter is not None:
                self.sourcemeter.shutdown()
                self.sourcemeter = None

    @pyqtSlot()        
    def start_temp_loop(self):
        self.initialise_sourcemeter()
        self.temp_loop_ticker.start(1000)
        self._scheduler_running = True
        self.status_update.emit('Collecting minimum temperature\ndata points\n')

    def temp_measurement_loop(self):
        success = self.take_temp_measurement()
        if not success or len(self.df) < self.gradient_period * 0.5:
            return
        gradient = self.calculate_gradient()
        self.new_gradient_available.emit(f'{round(gradient*60, 2)} °C/min')
        if abs(gradient) < abs(self.gradient_threshold):
            if not self.temperature_stable: # if gradient below threshold and not set to stable then change to stable
                self.temperature_stable = True
            if not self.delay_ticker.isActive() and not self.interval_ticker.isActive(): # this condition should start
                                        # the delay_counter upon subsequent scheduler cycles at the same temperature step
                                        # (i.e. temperature_stable condition is unbroken)
                self.delay_ticker.start(1000)
            self.unstability_counter = 0
        elif abs(gradient) >= self.gradient_threshold and self.temperature_stable is not False: # if gradient above threshold and set to stable then change to unstable
            # adding unstability grace period for temporary random fluctuations
            self.unstability_counter += 1
            
            if self.unstability_counter == self.unstability_grace:
                self.unstability_counter = 0
                self.temperature_stable = False

    def take_temp_measurement(self):
        voltage = self.sourcemeter.voltage
        try: # Prevents errors caused by disconnected thermocouple
            temperature = self.typeK.inverse_CmV(voltage*1000, Tref=self.t_ref) # move Tref selection to the window
            if self._TC_disconnected: # if previous step works and disconnected flag is up, means that TC was reconnected so lower the flag
                self._TC_disconnected = False
                self.status_update.emit('TC reconnected. Resuming measurements')

        except Exception as e:
            if not self._TC_disconnected: # tasks to do if this is the first failure
                logging.error(f'An error occured when attempting to measure the temperature: {e}')
                logging.error('Thermocouple disconnected. Please check connection')
                self._TC_disconnected = True
                if self.delay_ticker.isActive():
                    self.delay_ticker.stop()
                if self.interval_ticker.isActive():
                    self.interval_ticker.stop()
                self.status_update.emit('TC disconnected\nChecking if reconnected.')
                QtWidgets.QMessageBox.critical(None, 'Thermocouple disconnected!', 'Check thermocouple connection.\nSoftware will continue when TC is reconnected')
            return False

        time = datetime.now().timestamp()
        new_data = pd.DataFrame({'Time': time, 'Temperature': temperature}, index=[0])
        self.df = pd.concat([self.df, new_data], ignore_index=True)
        date = datetime.fromtimestamp(time).strftime('%Y-%m-%d %H:%M:%S')
        self.writer.save_data({
            'Timestamp': time,
            'Date': date,
            'Temperature': temperature
        })
        self.new_temp_available.emit(f'{round(temperature, 2)} °C')
        return True

    def old_calculate_gradient(self): ### Obsolete, kept for now for reference
        last_row = len(self.df)-1
        self.df.loc[last_row, 'delta_time'] = self.df.loc[last_row, 'Time'] - self.df.loc[last_row-1, 'Time']
        self.df.loc[last_row, 'delta_temp'] = self.df.loc[last_row, 'Temperature'] - self.df.loc[last_row-1, 'Temperature']
        recent_df = self.df.tail(self.gradient_period)
        avg_gradient = round(recent_df['delta_temp'].mean()/recent_df['delta_time'].mean(), 3)
        return avg_gradient
    
    def calculate_gradient(self):
        # Select the recent data points for gradient calculation
        recent_df = self.df.tail(self.gradient_period)
        
        # Get the index (time) and temperature columns for regression
        x = recent_df['Time'].values
        y = recent_df['Temperature'].values
        
        # Perform linear regression to calculate the slope (gradient)
        slope, intercept, r_value, p_value, std_err = linregress(x, y)

        fit_y = slope * x + intercept
        self.last_fit_line = (x, fit_y)
        
        # Return the slope as the average gradient, rounded to 2 decimal places
        #avg_gradient = round(slope, 2)
        
        return slope # because otherwise gradient in deg/min jumps by 0.6

    def delay_counter_function(self):
        if self.delay_counter == 0:
            self.delay_ticker.stop()
            self.interval_counter = self.interval
            self.interval_ticker.start(1000)
            return
        if self.unstability_counter == 0:
            self.status_update.emit(f'Temperature stable,\nremaining delay: {self.delay_counter} s')
            self.delay_counter += -1
        else:
            self.status_update.emit(f'Temperature unstability detected,\ngrace time remaining: {self.unstability_grace-self.unstability_counter} s')

    def interval_counter_function(self):
        if self.interval_counter == 0:
            self.interval_ticker.stop()
            self.request_measurement()
            return
        if self.unstability_counter == 0:
            self.status_update.emit(f'Temperature stable,\nmeasurement scheduled in {self.interval_counter} s')
            self.interval_counter += -1
        else:
            self.status_update.emit(f'Temperature unstability detected,\ngrace time remaining: {self.unstability_grace-self.unstability_counter} s')

    def terminate_temp_loop(self):
        self.temp_loop_ticker.stop()
        self.shutdown_sourcemeter()
        
    def reset(self):
        self.df = self.df.iloc[0:0] # empty the dataframe
        self.temperature_stable = None
        self._scheduler_running = False

    def abort(self):
        self.terminate_temp_loop()
        self.reset()
        if self.delay_ticker.isActive():
            self.delay_ticker.stop()
        if self.interval_ticker.isActive():
            self.interval_ticker.stop()
        self.status_update.emit('Scheduler aborted.')



    def request_measurement(self):
        self.terminate_temp_loop()
        if self.df.loc[len(self.df)-1, 'Temperature'] >= self.minimum_T:
            self.queue_IV_measurement.emit(str(int(self.df.loc[len(self.df)-1, 'Temperature'])))
            self.status_update.emit('IV measurement requested,\nscheduler suspended')
        else:
            self.measurements_finished.emit()
            self.reset()
            self.status_update.emit('IV measurements finished,\nsystem idle.')
        

class SchedulerWidget(QtWidgets.QWidget):

    class SchedulerDisplay(QtWidgets.QFrame):
        def __init__(self, name: str, signal: pyqtSignal, dict_key = None, unit=None):
            self.name = name
            super().__init__()

            vbox = QtWidgets.QVBoxLayout(self)
            self.label = QtWidgets.QLabel(self.name)
            self.output = QtWidgets.QLabel('---')
            self.dict_key = dict_key
            self.unit = unit
            vbox.addWidget(self.label)
            vbox.addWidget(self.output)

            self.update_text()
            self.setFrameStyle(QtWidgets.QLabel.StyledPanel | QtWidgets.QLabel.Sunken)
            signal.connect(self.update_text)

        def update_text(self, text=None):
            if text is None:
                new_text = '---'
            elif isinstance(text, str):
                new_text = text
            # elif isinstance(text, dict):
            #     try:
            #         new_text = f'{text.get(self.dict_key)}'
            #     except:
            #         new_text = f'Dict reading failed'
            if self.unit is not None:
                new_text = f'{new_text} {self.unit}'
            self.output.setText(new_text)

    def __init__(self, scheduler):
        super().__init__()
        self.scheduler = scheduler
        self._values_set = False
        self.parameters = []
        self._setup_ui()
        self._layout()

    def _setup_ui(self):
        self.status = SchedulerWidget.SchedulerDisplay(
            'Status',
            self.scheduler.status_update    
        )
        self.display_current_temperature = SchedulerWidget.SchedulerDisplay(
            'Current temperature', 
            self.scheduler.new_temp_available,
            dict_key = 'Temperature'
        )
        self.display_current_gradient = SchedulerWidget.SchedulerDisplay(
            'Current temperature gradient', 
            self.scheduler.new_gradient_available
        )
        self.stability_label = SchedulerWidget.SchedulerDisplay(
            'Temperature stability',
            self.scheduler.stability_signal
        )

        self.gradient_threshold = DisplayFloatParameter(
            'Temperature Gradient Threshold',
            units='°C/min',
            default=0.5,
            maximum=5,
            minimum=0.5,
            orientation='v',
            tooltip=f'Maximum temperature gradient considered stable,\nRange from 0.5 to 5 °C/min'
        )
        self.gradient_threshold.start_displayer()
        self.parameters.append(self.gradient_threshold)

        self.delay = DisplayFloatParameter(
            'Delay',
            units='min',
            default=15,
            maximum=120,
            minimum = 1,
            orientation='v',
            tooltip='Delay between temperature stabilisation and measurements\nRange from 1 to 120 min'
        )
        self.delay.start_displayer()
        self.parameters.append(self.delay)

        self.interval = DisplayFloatParameter(
            'Measurement Interval',
            units='min',
            default=5,
            maximum=30,
            minimum=0.5,
            orientation='v',
            tooltip='Time interval at which subsequent measurements are scheduled\nRange from 0.5 to 30 min'
        )
        self.interval.start_displayer()
        self.parameters.append(self.interval)

        self.minimum_T = DisplayFloatParameter(
            'Minimum Temperature',
            units='°C',
            default=50,
            maximum=300,
            minimum=30,
            orientation='v',
            tooltip='Temperature threshold below which scheduler will terminate if a stable temperature is achieved.\nRange from 30 to 300 °C'
        )
        self.minimum_T.start_displayer()
        self.parameters.append(self.minimum_T)

        self.reference_T = DisplayFloatParameter(
            'TC Reference Temperature',
            units='°C',
            default=22.0,
            maximum=35,
            minimum=15,
            orientation='v',
            tooltip="Temperature of the thermocouple's reference temperature, ambient temperature."
        )
        self.reference_T.start_displayer()
        self.parameters.append(self.reference_T)

        self.button = QtWidgets.QPushButton('Set values')
        self.button.clicked.connect(self.set_values)


    def _layout(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5,5,5,5)

        layout.addWidget(self.status)
        layout.addWidget(self.display_current_temperature)
        layout.addWidget(self.display_current_gradient)
        layout.addWidget(self.stability_label)

        sep = Separator('h')
        layout.addWidget(sep)

        layout.addWidget(self.gradient_threshold.displayer)
        layout.addWidget(self.delay.displayer)
        layout.addWidget(self.interval.displayer)
        layout.addWidget(self.minimum_T.displayer)
        layout.addWidget(self.reference_T.displayer)

        layout.addStretch()
        layout.addWidget(self.button)

    def set_values(self):
        if not self._values_set:
            for parameter in self.parameters:
                parameter.displayer.entry.update_parameter()
                parameter.lock_input(True)
            self.scheduler.set_parameters(
                self.gradient_threshold.value,
                self.delay.value,
                self.interval.value,
                self.minimum_T.value,
                self.reference_T.value
            )
            self.button.setText('Edit values')
            self._values_set = True

        else:
            for parameter in self.parameters:
                parameter.lock_input(False)
            self.button.setText('Set values')
            self._values_set = False

class CSVWriter: # Add Time as a readable string, currently it is Epoch Time
    def __init__(self):
        self.filepath = None
        self.columns = ['Timestamp', 'Date', 'Temperature']

    def start_writer(self, filepath):
        self.filepath = os.path.join(filepath, 'SchedulerTemperature.csv')
        self.write_line(self.columns)

    def save_data(self, data: dict):
        # print(data)
        new_row = [data[column] for column in self.columns]
        self.write_line(new_row)

    def write_line(self, row: list):
        if self.filepath is None:
            print('CSVWriter: Filepath is None')
            return
        try:
            with open(self.filepath, mode='a', newline='') as csv_file:
                writer = csv.writer(csv_file, delimiter=';')
                writer.writerow(row)
        except:
            print('Writing to csv failed')

        

class MeasurementWidget(QtWidgets.QWidget):
    def __init__(self, procedure_class, inputs = [], test_button_function=None):
        super().__init__()
        self._procedure_class = procedure_class
        self._procedure = procedure_class()
        self._inputs = inputs # Parameter instance names (not display names), passed at instantiation
        self._values_set = False

        self._setup_widgets(test_button_function)
        self._setup_layout()
        self._create_input_field()

        
    def _setup_widgets(self, test_button_function):

        # Setup scroll widget for displaying parameters
        self.scrollArea = QtWidgets.QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        self.scrollAreaWidget = QtWidgets.QWidget()
        self.scrollAreaLayout = QtWidgets.QVBoxLayout(self.scrollAreaWidget)
        self.scrollAreaLayout.setContentsMargins(5,5,5,5)
        self.scrollArea.setWidget(self.scrollAreaWidget)
        
        # Setup 'Set values' button
        self.button = QtWidgets.QPushButton('Set values')
        self.button.clicked.connect(self.set_values)

        if test_button_function is not None:
            self.test_button = QtWidgets.QPushButton('Run test measurement')
            self.test_button.clicked.connect(test_button_function)

    def _setup_layout(self):
        layout = QtWidgets.QVBoxLayout(self)
        if hasattr(self, 'combo'):
            layout.addWidget(self.combo)
        layout.addWidget(self.scrollArea)
        layout.addWidget(self.button)
        if hasattr(self, 'test_button'):
            layout.addWidget(self.test_button)
        if hasattr(self, 'output_field'):
            layout.addWidget(self.output_field)

    def _create_input_field(self): # for when a list of inputs is provided, 
        parameter_dict = self._procedure.parameter_objects()
        for name in self._inputs:
            try: # this should catch all non-Display parameters
                parameter = parameter_dict[name]
                parameter.start_displayer()
                self.scrollAreaLayout.addWidget(parameter.displayer)
                #setattr(self, name, parameter.displayer.entry)
                setattr(self, name, parameter)
            except:
                log.error('Could not start displayer')

                    
        spacer_item = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.scrollAreaLayout.addItem(spacer_item)           

    def set_values(self):
        # If this has any issues, look into InputsWidget class definition. 
        # Specifically, the set_parameters method, which was not implemented here
        # as it looks kind of pointless

        if not self._values_set:
            for name in self._inputs:
                parameter = getattr(self, name)
                parameter.update_parameter()
                parameter.lock_input(True)

            self.button.setText('Edit values')
            self._values_set = True

        else:
            for name in self._inputs:
                parameter = getattr(self, name)
                parameter.lock_input(False)

            self.button.setText('Set values')
            self._values_set = False

    def get_procedure(self):
        """ Returns the current procedure """
        self._procedure = self._procedure_class()
        parameter_values = {}
        for name in self._inputs:
            parameter = getattr(self, name)
            parameter.update_parameter()
            parameter_values[name] = parameter.value
        self._procedure.set_parameters(parameter_values)
        return self._procedure



class Separator(QtWidgets.QFrame):
    def __init__(self, direction = ''):
        super().__init__()
        if direction == 'h':
            self.setFrameShape(QtWidgets.QFrame.HLine)
        elif direction == 'v':
            self.setFrameShape(QtWidgets.QFrame.VLine)
        else:
            self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)



'''
class OldTempScheduler(QtCore.QObject):

    class TempCurveSim:
        def __init__(self, heating_rate, set_temp):
            self.heating_rate = heating_rate
            self.set_temp = set_temp
            self.width = np.random.uniform(0.05, 0.1)
            self.offset = np.random.uniform(0, 40)
            self.x_axis_offset = 20

        def start_measurements(self):
            self.start_time = datetime.now().timestamp()

        def sim_measurement(self):
            current_time = datetime.now().timestamp()
            x = current_time-self.start_time-self.x_axis_offset
            expression_a = self.heating_rate*x
            expression_b = expression_a/(np.e**(self.width*(self.offset-x))+1)
            temperature = round(expression_a-expression_b+self.set_temp, 2)
            
            return current_time, temperature

    queue_IV_measurement = QtCore.pyqtSignal(str) # str contains the temperature to 0 d.p.
    measurements_finished = QtCore.pyqtSignal() # should be obsolete as measurements run indefinitely
    status_update = QtCore.pyqtSignal(str) # informs of the current state of the scheduler
    new_temp_available = QtCore.pyqtSignal(dict) # updates temperature display and plot
    stability_signal = QtCore.pyqtSignal(str) # updates stability label in SchedulerPlot

    _temperature_stable = False

    @property
    def temperature_stable(self):
        return self._temperature_stable
    
    @temperature_stable.setter
    def temperature_stable(self, bool):
        self._temperature_stable = bool
        if self.temperature_stable:
            self.stability_signal.emit('Stable')
        else:
            self.stability_signal.emit('Unstable')


    def __init__(self):
        super().__init__()
        self.columns = ['Time', 'Temperature']
        self.df = pd.DataFrame(columns = self.columns)
        self.gradient_threshold = None
        self.minimum_T = 100

        self.measurement_timer = QTimer(parent=self)
        self.measurement_timer.timeout.connect(self.temp_measurement_loop)

        self.delay_timer = QTimer(parent=self)
        self.delay_timer.timeout.connect(self.delay_finished)
        self.delay = None

        self.interval_timer = QTimer(parent=self) # counts down to the measurement after reaching temperature stability
        self.interval_timer.timeout.connect(self.interval_counter)
        self.interval = None
        

        #for testing - now replaced by actual data collection
        #self.level_list = [500, 200, 25]

    def set_parameters(self, gradient_threshold, delay, interval):
        #convert min to seconds
        self.gradient_threshold = gradient_threshold/60
        self.delay = int(delay*60*1000) #in ms
        self.interval = int(interval*60) #in s
        self.gradient_period = 30 #in s

    def find_device_address(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "ATEN USB to Serial Bridge" in port.description:
                com_port_number = int(port.device[3:])
                visa_address = f'ASRL{com_port_number}::INSTR'
                return visa_address
        return None

    @pyqtSlot()        
    def start_scheduler(self):
        self.sourcemeter = Keithley2400(self.find_device_address())
        self.sourcemeter.reset()
        self.sourcemeter.apply_current()
        self.sourcemeter.source_current_range = 0.001
        self.sourcemeter.source_current = 0
        self.sourcemeter.compliance_voltage = 1

        self.sourcemeter.measure_voltage()
        self.sourcemeter.voltage_range = 0.5
        self.sourcemeter.voltage_nplc = 1

        self.sourcemeter.use_front_terminals()

        self.sourcemeter.enable_source()
        sleep(1)

        self.typeK = thermocouples['K'] # thermocouple output converter between mV and deg C


        #for testing - now replaced by actual data collection
        # level = self.level_list.pop(0)
        # self.temp_simulator = TempScheduler.TempCurveSim(0.25, level)
        # self.temp_simulator.start_measurements()


        self.measurement_timer.start(1000)
        self.status_update.emit('Awaiting temperature stabilisation\n')

    def temp_measurement_loop(self):
        self.take_temp_measurement()
        if len(self.df) < self.gradient_period:
            return
        gradient = self.calculate_gradient()
        if abs(gradient) < abs(self.gradient_threshold):
            self.temperature_stable_logic()
        elif abs(gradient) >= self.gradient_threshold:
            self.temperature_unstable_logic()

    def take_temp_measurement(self):
        voltage = self.sourcemeter.voltage
        temperature = self.typeK.inverse_CmV(voltage*1000, Tref=22.0) # move Tref selection to the window
        time = datetime.now().timestamp()
        new_data = pd.DataFrame({'Time': time, 'Temperature': temperature}, index=[0])
        self.df = pd.concat([self.df, new_data], ignore_index=True)
        date = datetime.fromtimestamp(time).strftime('%Y-%m-%d %H:%M:%S')
        self.new_temp_available.emit({'Timestamp': time, 'Date': date, 'Temperature': round(temperature, 2)})

    def calculate_gradient(self):
        last_row = len(self.df)-1
        self.df.loc[last_row, 'delta_time'] = self.df.loc[last_row, 'Time'] - self.df.loc[last_row-1, 'Time']
        self.df.loc[last_row, 'delta_temp'] = self.df.loc[last_row, 'Temperature'] - self.df.loc[last_row-1, 'Temperature']
        recent_df = self.df.tail(self.gradient_period)
        avg_gradient = round(recent_df['delta_temp'].mean()/recent_df['delta_time'].mean(), 3)
        return avg_gradient
    
    def temperature_stable_logic(self):
        self.temperature_stable = True
        if not self.delay_timer.isActive():
            self.delay_timer.start(int(self.delay))
            self.status_update.emit(f'Stable temperature reached.\nDelay of {self.delay/60000} min started.')

    def temperature_unstable_logic(self):
        self.temperature_stable = False
        if self.delay_timer.isActive():
            self.delay_timer.stop()
        if self.interval_timer.isActive():
            self.interval_timer.stop()
        self.status_update.emit('Awaiting temperature stabilisation\n')
    
    def delay_finished(self):
        self.counter = int(self.interval)
        self.interval_timer.start(1000)
        self.interval_counter()

    def interval_counter(self):
        if self.counter == 0:
            self.emit_queue_IV_meas()
            return
        self.status_update.emit(f'Temperature stable,\nmeasurement scheduled in {self.counter} s')
        self.counter += -1

    def emit_queue_IV_meas(self):
        print('Queue IV measurement signal emitted.')
        self.terminate_scheduler()
        print('Scheduler terminated')
        if self.df.loc[len(self.df)-1, 'Temperature'] >= self.minimum_T:
            self.queue_IV_measurement.emit(str(int(self.df.loc[len(self.df)-1, 'Temperature'])))
            self.status_update.emit('IV measurement requested,\nscheduler suspended')
        else:
            self.measurements_finished.emit()
            self.status_update.emit('IV measurements finished,\nsystem idle.')

    def abort_scheduler(self):
        self.terminate_scheduler()
        self.status_update.emit('Scheduler aborted,\n system idle')

    def terminate_scheduler(self):
        if hasattr(self, 'sourcemeter'):
            self.sourcemeter.shutdown()
            self.sourcemeter = None
        self.reset_scheduler()
        self.new_temp_available.emit({'Timestamp': None, 'Date': None, 'Temperature': None})
        self.stability_signal.emit('---')
        
    def reset_scheduler(self):
        self.interval_timer.stop()
        self.delay_timer.stop()
        self.temperature_stable = False
        self.measurement_timer.stop()
'''      

