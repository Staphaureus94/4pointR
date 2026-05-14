import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
from time import sleep
import os
import tempfile
import csv

import serial.tools.list_ports

from PyQt5.QtCore import pyqtSignal, QObject, QThread, Qt

from pymeasure.display.manager import Manager
from pymeasure.display.Qt import QtCore, QtWidgets
from pymeasure.display.curves import ResultsCurve
from pymeasure.display.widgets import (
    PlotWidget,
    BrowserWidget,
    LogWidget,
    DirectoryLineEdit
)
from pymeasure.display.windows import ManagedWindowBase
from pymeasure.experiment.results import Results
from pymeasure.instruments.keithley import Keithley2400

from display import (
    AlteredPlotWidget,
    HelpWidget,
    TempScheduler,
    SchedulerWidget,
    SchedulerPlot,
    Separator,
    MeasurementWidget,
)


class FourPointWindow(ManagedWindowBase):
    await_next_measurement = pyqtSignal()

    def __init__(self, 
                 procedure_class, 
                 widget_list=..., #define within __init__
                 inputs=..., # pass at instance creation
                 displays=..., # pass at instance creation
                 log_channel='', ##### Dealt with below
                 log_level=logging.INFO, 
                 parent=None, 

                 # Additional example keyword agruments
                 x_axis=None,
                 y_axis=None,
                 linewidth=1,
                 **kwargs
                 ):
        
        self._inputs = inputs
        self.inputs_in_scrollarea=True
        self.x_axis = x_axis
        self.y_axis = y_axis
        self.experiment_running = False # bool keeping track of whether an experiment is running, 
                                        # keeps the program from continuing after finishing a test measurement initiated by the 'Run test measurement' button

        #start scheduler before super().__init() to add SchedulerPlot to tabs
        self._setup_scheduler()

        # instantiate TabWidgets before super().__init__()
        self.temp_widget = SchedulerPlot('Temperature Plot', self.scheduler)
        self.help_widget = HelpWidget('Help')
        self.log_widget = LogWidget("Experiment Log")
        self.plot_widget = AlteredPlotWidget("IV Plot", procedure_class.DATA_COLUMNS, self.x_axis,
                                      self.y_axis, linewidth=linewidth, symbol='o')
        self.plot_widget.setMinimumSize(100, 200)
        if "widget_list" not in kwargs:
            kwargs["widget_list"] = ()
        kwargs["widget_list"] = kwargs["widget_list"] + (self.plot_widget, self.temp_widget, self.log_widget, self.help_widget)
        
        #_setup_ui() executed by super().__init__
        super().__init__(procedure_class, **kwargs)

        # must be after QMainWindow init
        self.await_next_measurement.connect(self.scheduler.start_temp_loop, Qt.QueuedConnection)


        self.resize(1200, 800)
        self.browser_widget.browser.measured_quantities = [self.x_axis, self.y_axis]

        logging.getLogger().addHandler(self.log_widget.handler)  # needs to be in Qt context?
        log.setLevel(self.log_level)
        log.info("GUI connected to logging")

    ### GUI Setup - create widgets and organise them in layouts
    def _setup_ui(self):
        self._setup_dock_widget()
        self._setup_main_widget()

        self.manager = Manager(self.widget_list,
                               self.browser,
                               log_level=self.log_level,
                               parent=self)
        self.manager.abort_returned.connect(self.abort_returned)
        self.manager.queued.connect(self.queued)
        self.manager.running.connect(self.running)
        self.manager.finished.connect(self.finished)
        self.manager.failed.connect(self.measurement_failed)
        self.manager.log.connect(self.log.handle)


    def _setup_scheduler(self):
        # Start scheduler to connect its result to the SchedulerPlot before it is added to the TabWidget
        self.scheduler = TempScheduler()
        self.scheduler.queue_IV_measurement.connect(self._scheduler_queue)
        self.scheduler.measurements_finished.connect(self.experiment_finished)

    def _layout(self): 
        # This just overrides the _layout function of the ManagedWindowBase
        # which is not currently used as its tasks are handled by other methods
        # Perhaps in future separate widget setup from layout setup
        # and then use it.
        pass

    def _setup_dock_widget(self):
        # Dock widget, encompassing all dock tabs
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        tab_widget = QtWidgets.QTabWidget()
        layout.addWidget(tab_widget)
        widget.setFixedWidth(250)

        self.measurements_tab = MeasurementWidget(self.procedure_class, inputs=self._inputs, test_button_function=self.test_queue)
        tab_widget.addTab(self.measurements_tab, 'Measurement')

        self.scheduler_tab = SchedulerWidget(self.scheduler)
        tab_widget.addTab(self.scheduler_tab, 'Scheduler')

        layout.addStretch()
        sep = Separator('h')
        layout.addWidget(sep)
        layout.addWidget(QtWidgets.QLabel('Experiment Control Panel'))

        self.setup_tab = self._setup_experiment_tab()
        layout.addWidget(self.setup_tab)

        dock = QtWidgets.QDockWidget('Setup')
        dock.setWidget(widget)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        
    def _setup_experiment_tab(self): # widgets and layout, returns a ready widget
        # Tab for starting experiment and choosing directories
        widget = QtWidgets.QFrame() 
        widget.setFrameShape(QtWidgets.QFrame.Box)
        widget.setFrameShadow(QtWidgets.QFrame.Raised)
        widget.setLineWidth(2)
        layout = QtWidgets.QVBoxLayout()

        self.directory_label = QtWidgets.QLabel(self)
        self.directory_label.setText('Directory')
        self.directory_line = DirectoryLineEdit(parent=self)
        self.directory_line.setText('C:/Users/Public/4PRM Data')
        # self.directory_line.setText('C:/Users/stefa/OneDrive/Desktop/pymeasure_test_data')
        layout.addWidget(self.directory_label)
        layout.addWidget(self.directory_line)

        self.exp_name_label = QtWidgets.QLabel('Experiment Name')
        self.exp_name_line = QtWidgets.QLineEdit()
        # self.exp_name_line.setText('test')
        layout.addWidget(self.exp_name_label)
        layout.addWidget(self.exp_name_line)


        separator2 = Separator('h')
        layout.addWidget(separator2)

        # Not currently used, but may be returned in the future?
        # self.scans_label = QtWidgets.QLabel('Number of scans per level')
        # self.scans_combo = QtWidgets.QComboBox()
        # self.scans_combo.addItems([f'{i+1}' for i in range(5)])
        # layout.addWidget(self.scans_label)
        # layout.addWidget(self.scans_combo)


        # separator3 = Separator('h')
        # layout.addWidget(separator3)        

        self.start_button = QtWidgets.QPushButton('Start experiment')
        self.start_button.clicked.connect(self.start_experiment)
        layout.addWidget(self.start_button)

        self.my_abort_button = QtWidgets.QPushButton('Abort experiment')
        self.my_abort_button.clicked.connect(self.request_meas_abort)
        self.my_abort_button.setEnabled(False)
        layout.addWidget(self.my_abort_button)

        # layout.addStretch()

        separator3 = Separator('h')
        layout.addWidget(separator3)

        self.room_temp_start_button = QtWidgets.QPushButton('RT measurement')
        self.room_temp_start_button.clicked.connect(self.room_temp_measurement)
        layout.addWidget(self.room_temp_start_button)



        # Can't be currently used, needs to be adapted or made anew
        self.abort_button = QtWidgets.QPushButton('Abort')
        self.abort_button.setEnabled(False)
        self.abort_button.clicked.connect(self.abort)
        # layout.addWidget(self.abort_button)

        self.queue_button = QtWidgets.QPushButton('Obsolete')
        # self.queue_button.clicked.connect(self.test_queue)
        #layout.addWidget(self.queue_button)
        
        #layout.addStretch()
        widget.setLayout(layout)

        return widget
    
    def _setup_main_widget(self):
        self.tabs = QtWidgets.QTabWidget()
        for wdg in self.widget_list:
            self.tabs.addTab(wdg, wdg.name)

        self.browser_widget = BrowserWidget(
            self.procedure_class,
            self.displays,
            [],  # This value will be patched by subclasses, if needed
            parent=self
        )
        self.browser_widget.show_button.clicked.connect(self.show_experiments)
        self.browser_widget.hide_button.clicked.connect(self.hide_experiments)
        self.browser_widget.clear_button.clicked.connect(self.clear_experiments)
        self.browser_widget.open_button.clicked.connect(self.open_experiment)
        self.browser = self.browser_widget.browser
        self.browser.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.browser.customContextMenuRequested.connect(self.browser_item_menu)
        self.browser.itemChanged.connect(self.browser_item_changed)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.addWidget(self.tabs)
        splitter.addWidget(self.browser_widget)
        
        self.setCentralWidget(splitter)

    ### Scheduling and queueing measurements    
    def _scheduler_queue(self, suffix): # called when level reached, queues n measurements based on sweep count
        # since self.scans_combo is not currently used, the for loop has been commented out. Uncomment if self.scans_combo returned
        # for i in range(self.scans_combo.currentIndex()+1):
        self.queue(suffix=suffix) # add tab here when uncommenting the above
            # sleep(0.1)

    def queue(self, suffix=''): # queue a measurement, called by the scheduler_queue
        filename = self.unique_filename(self.exp_directory, prefix='IV_meas', suffix=suffix)
        procedure = self.make_procedure()
        results = Results(procedure, filename)
        experiment = self.new_experiment(results)
        self.manager.queue(experiment)
        if not self.manager.is_running(): # restarts manager if a previous measurement was aborted
            self.manager.resume()

    def test_queue(self): # add a test measurement to the queue
        if self.test_sourcemeter_connection is None:
            QtWidgets.QMessageBox.critical(None, 'Sourcemeter not connected!', 'Check if sourcemeter is switched on.')
            return            
        filename = tempfile.mktemp()
        procedure = self.make_procedure()
        results = Results(procedure, filename)
        experiment = self.new_experiment(results)
        self.manager.queue(experiment)
        self.my_abort_button.setEnabled(True)
        self.start_button.setEnabled(False)
        if not self.manager.is_running(): # restarts manager if a previous measurement was aborted
            self.manager.resume()
   
    def start_experiment(self): # perform initial checks, lock inputs and buttons and starts the scheduler
        # Read the directory from the input and check its validity
        directory = self.directory_line.text()
        if not os.path.isdir(directory):
            QtWidgets.QMessageBox.critical(None, 'Invalid directory!', 'Provide a valid directory to save data')
            return
        
        # Read the experiment directory name and check its validity
        exp_name = self.exp_name_line.text()
        if exp_name == '':
            QtWidgets.QMessageBox.critical(None, 'No experiment name!', 'Provide a name for the experiment directory')
            return
        illegal_chars = ['/', '#', '\\']
        if any(char in exp_name for char in illegal_chars):
            QtWidgets.QMessageBox.critical(None, 'Illegal character detected!', f'Avoid using any of the following characters:\n{illegal_chars}')
            return

        # create experiment directory, add '_#' at the end if one exists already
        self.exp_directory = os.path.join(directory, exp_name)
        if os.path.exists(self.exp_directory):
            i=1
            new_directory = '%s_%d' % (self.exp_directory, i)
            while os.path.exists(new_directory):
                i+=1
                new_directory = '%s_%d' % (self.exp_directory, i)
            self.exp_directory = new_directory

        # Try creating the experiment directory
        try:
            os.makedirs(self.exp_directory)
        except:
            QtWidgets.QMessageBox.critical(None, 'Invalid file name!', 'Choose a different file name.')
            return

        # Check if inputs and levels are set
        message_string = ''
        if not self.measurements_tab._values_set:
            message_string += 'Set values in the Measurement tab\n'
        if not self.scheduler_tab._values_set:
            message_string += 'Set values in the Scheduler tab'
        if message_string!='':
            QtWidgets.QMessageBox.critical(None, 'Values not set!', message_string)
            return
        
        if self.test_sourcemeter_connection() is None:
            QtWidgets.QMessageBox.critical(None, 'Sourcemeter not connected!', 'Check if sourcemeter is switched on.')
            return
        
        log.info('Starting temperature-scheduled experiments')
        self.scheduler.writer.start_writer(self.exp_directory)
        self._lock_entries(True)
        self.experiment_running = True
        # self.my_abort_button.setEnabled(True)
        self.await_next_measurement.emit()

    def room_temp_measurement(self):
        # Read the directory from the input and check its validity
        directory = self.directory_line.text()
        if not os.path.isdir(directory):
            QtWidgets.QMessageBox.critical(None, 'Invalid directory!', 'Provide a valid directory to save data')
            return
        
        # Read the experiment directory name and check its validity
        exp_name = self.exp_name_line.text()
        if exp_name == '':
            QtWidgets.QMessageBox.critical(None, 'No experiment name!', 'Provide a name for the experiment directory')
            return
        illegal_chars = ['/', '#', '\\']
        if any(char in exp_name for char in illegal_chars):
            QtWidgets.QMessageBox.critical(None, 'Illegal character detected!', f'Avoid using any of the following characters:\n{illegal_chars}')
            return
        
        exp_name += '.csv'
        exp_path = os.path.join(directory, exp_name)
        if os.path.exists(exp_path):
            reply = QtWidgets.QMessageBox.question(
                None, 
                'File already exists?',
                'Are you sure you want to overwrite it?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return
            
        procedure = self.make_procedure()
        results = Results(procedure, exp_path)
        experiment = self.new_experiment(results)
        self.manager.queue(experiment)
        # self.my_abort_button.setEnabled(True)
        # self.start_button.setEnabled(False)
        # self.room_temp_start_button.setEnabled(False)
        self._lock_entries(True)
        if not self.manager.is_running(): # restarts manager if a previous measurement was aborted
            self.manager.resume()        

    def request_meas_abort(self):
        if self.scheduler.is_running:
            self.scheduler.abort()
        if self.manager.is_running():
            try:
                self.manager.abort()
                self._lock_entries(False)
                # self.my_abort_button.setEnabled(False)
                self.experiment_running = False
            except:
                print('Manager abort failed')
        else:
            self._lock_entries(False)
            # self.my_abort_button.setEnabled(False)
            self.experiment_running = False

    def experiment_finished(self):
        self._lock_entries(False)
        self.measurements_tab.set_values()
        self.scheduler_tab.set_values()
        self.experiment_running = False



    ### Signalling and utility functions
    def _lock_entries(self, bool): # Lock/Unlock inputs and buttons when experiment is running
        self.start_button.setEnabled(not bool)
        self.room_temp_start_button.setEnabled(not bool)
        self.my_abort_button.setEnabled (bool)

        self.measurements_tab.button.setEnabled(not bool)
        self.scheduler_tab.button.setEnabled(not bool)
        self.directory_line.setEnabled(not bool)
        self.exp_name_line.setEnabled(not bool)
        # self.scans_combo.setEnabled(not bool) not currently used, so commented out

    def measurement_failed(self):
        logging.info('Measurement failed. Attempting to continue experiment')
        print('Meas failed')
        # THIS MUST SORT OUT CURRENTLY QUEUED MEASUREMENTS!!!
        # OR THEY WILL RUN AT THE NEXT LEVEL
        if not self.experiment_running:
            self.start_button.setEnabled(True)
        if self.manager.experiments.has_next():
            self.manager.resume()
        else:
            self.await_next_measurement.emit()

    def finished(self, experiment):     # Overridden method from ManagedWindow
        if not self.manager.experiments.has_next():
            if self.experiment_running:
                self.browser_widget.clear_button.setEnabled(True)
                self.await_next_measurement.emit() # added this to start awaiting next temperature level
            else:
                self.my_abort_button.setEnabled(False)
                self.start_button.setEnabled(True)

    def make_procedure(self): # obtains an instance of the procedure class with updated parameter values
        if not isinstance(self.measurements_tab, MeasurementWidget):
            raise Exception("ManagedWindow can not make a Procedure"
                            " without a InputsWidget type")
        return self.measurements_tab.get_procedure()

    def unique_filename(self, # created unique names for measurement files
                        directory, prefix='DATA', suffix='', ext='csv',
                        dated_folder=False, index=True, datetimeformat="%Y-%m-%d",
                        procedure=None):
        """ Returns a unique filename based on the directory and prefix
        """
        # now = datetime.datetime.now()
        directory = os.path.abspath(directory)

        if not os.path.exists(directory):
            os.makedirs(directory)

        i = 1
        basepath = os.path.join(directory, prefix)
        filename = "%s_%s_%d.%s" % (basepath, suffix, i, ext)
        while os.path.exists(filename):
            i += 1
            filename = "%s_%s_%d.%s" % (basepath, suffix, i, ext)
        return filename
    
    def test_sourcemeter_connection(self):
        try:
            self.sourcemeter = Keithley2400(self.find_device_address())
            logging.info('Connected to Keithley')
            id = self.sourcemeter.id
            logging.info(f'Sourcemeter ID: {id}')
            self.sourcemeter.shutdown()
            self.sourcemeter = None
            logging.info('Sourcemeter shutdown after testing connection')
            return id
        except Exception as e:
            self.sourcemeter = None
            logging.error(f'Failed to test connection with sourcemeter. Error: {e}')
            return None

    def find_device_address(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "ATEN USB to Serial Bridge" in port.description:
                com_port_number = int(port.device[3:])
                visa_address = f'ASRL{com_port_number}::INSTR'
                return visa_address
        return None
