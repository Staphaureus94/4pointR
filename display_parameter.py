from pymeasure.display.inputs import (Input, ScientificInput, IntegerInput, BooleanInput, ListInput, StringInput)
from pymeasure.display.Qt import QtWidgets
from pymeasure.experiment import (Parameter,
                                  IntegerParameter,
                                  BooleanParameter,
                                  FloatParameter,
                                  VectorParameter,
                                  ListParameter
                                  )




class DisplayParameterBase():
    ''' Base class for creating DisplayParameters. Takes as input
    arguments for both the parameter and the desired display layout.
    '''
    class NoWheelCombo(QtWidgets.QComboBox):
        def wheelEvent(self, event):
            # Ignore wheel events
            event.ignore()
    class Displayer(QtWidgets.QWidget):


        def __init__(self, parameter: Parameter, orientation='h', unit_combo={}, lower_combo=True, tooltip=''):
            super().__init__()
            self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
            #self.setMaximumHeight(50)

            self.parameter = parameter

            self._setup_widgets(unit_combo, tooltip)
            self._setup_layout(orientation, lower_combo)

        def _setup_widgets(self, unit_combo, tooltip):
            #Label
            self.label = QtWidgets.QLabel(self.parameter.name)
            self.label.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)

            #Entry
            if isinstance(self.parameter, Parameter):
                if self.parameter.ui_class is not None:
                    element = self.parameter.ui_class(self)

                elif isinstance(self.parameter, FloatParameter):
                    element = ScientificInput(self.parameter)

                elif isinstance(self.parameter, IntegerParameter):
                    element = IntegerInput(self.parameter)

                elif isinstance(self.parameter, BooleanParameter):
                    element = BooleanInput(self.parameter)

                elif isinstance(self.parameter, ListParameter):
                    element = ListInput(self.parameter)

                elif isinstance(self.parameter, Parameter):
                    element = StringInput(self.parameter)

                self.entry = element
                self.entry.set_parameter(self.parameter)
                if len(tooltip) != 0:
                    self.entry.setToolTip(tooltip)
                #print('Testing if parameter is connected:', isinstance(self.entry.parameter, Parameter))
                #self.parameter.ui_class = self.entry
                self.entry.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)

            if unit_combo:
                self.unit_combo = DisplayParameterBase.NoWheelCombo()
                self.unit_combo.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
                self.unit_combo.addItems(*unit_combo.keys())
                self.unit_combo.setCurrentIndex(self.comboUnit.findText(self.parameter.comboUnit[1]))

        def _setup_layout(self, orientation, lower_combo):
            top_hbox = QtWidgets.QHBoxLayout()
            top_hbox.setContentsMargins(0,0,0,0)
            top_hbox.addWidget(self.label)
            if orientation=='v':
                vbox = QtWidgets.QVBoxLayout()
                vbox.addLayout(top_hbox)
                vbox.setContentsMargins(0,0,0,10)

                bottom_line = QtWidgets.QHBoxLayout()
                bottom_line.setContentsMargins(0,0,0,0)
                bottom_line.addWidget(self.entry)
                vbox.addLayout(bottom_line)
            else:
                top_hbox.addWidget(self.entry)
            if hasattr(self, 'unit_combo'):
                if lower_combo and orientation=='v':
                    bottom_line.addWidget(self.comboBox)
                else:
                    top_hbox.addWidget(self.comboBox)
            if orientation=='v':
                self.setLayout(vbox)
            else:
                self.setLayout(top_hbox)        

    def __init__(self, 
                 # Parameter
                 name,

                # DisplayParameterBase
                 orientation='h',
                 unit_combo={},
                 lower_combo=True,
                 tooltip='',

                 **kwargs # for the other parameter keyword arguments
                 ):
        
        super().__init__(name, **kwargs) 
        
        self._layout_dict = {
            'orientation': orientation,
            'unit_combo': unit_combo,
            'lower_combo': lower_combo,
            'tooltip': tooltip
        }


    def start_displayer(self):
        # Displayer takes self (the Parameter) as an argument to sort out the input widget type)
        self.displayer = DisplayParameterBase.Displayer(self, **self._layout_dict)
        # if isinstance(self, ListParameter):
        #     if hasattr(self, 'default'):
        #         index = self.displayer.entry.findText(self.default)
        #         self.displayer.entry.setCurrentIndex(index)

    def lock_input(self, bool):
        self.displayer.setEnabled(not bool)

    def update_parameter(self):
        return self.displayer.entry.update_parameter()


class DisplayParameter(DisplayParameterBase, Parameter):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)


class DisplayIntegerParameter(DisplayParameterBase, IntegerParameter):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)


class DisplayBooleanParameter(DisplayParameterBase, BooleanParameter):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)


class DisplayFloatParameter(DisplayParameterBase, FloatParameter):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)


class DisplayVectorParameter(DisplayParameterBase, VectorParameter):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)


class DisplayListParameter(DisplayParameterBase, ListParameter):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)

