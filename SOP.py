SOP_text = '''
    Standard Operations Manual:

    A) Sample mounting:
        1) For sample preparation, see the separate printed manual.
        2) Ensure that nothing is blocking the sample holder rails and pull the sample holder out of the furnace.
        3) Attach the outer pair of wires to the connectors marked as 'I' (current).
        4) Attach the inner pair of wires to the connectors marked as 'V' (voltage).
        5) Push the sample holder back into the furnace.
            (Mind the furnace's internal thermocouple as it may strike an incorrectly positioned sample)
        6) If using a gas other than the ambient air, ensure that a gasket is placed on the sample holder's flange
            and insert and tighten all the nuts and bolts on the flange.

    B) Furnace settings:
        1) !!! Ensure that cooling water is TURNED ON !!!
        2) Turn on the furnace using the large red switch next to the control panel.
        3) Set up the temperature profile on the furnace control panel.
            Refer to the SOP for the furnace control panel in case of difficulties.
        5) Start the furnace program after checking that cooling water is flowing
            (the metal ring connecting to the glass tube will feel cold to the touch).

    C) Software settings:
        1) Set up parameters of the IV measurements in the Measurement tab and press 'Set values'.
        2) Set up scheduler parameters in the Scheduler tab and press 'Set values'.
        3) Choose a Directory where your data should be saved (click on the folder icon to open a browser window).
        4) Provide the Experiment Name - this will be used to create this experiment's directory and data files within.
        5) Ensure that the Keithley sourcemeter is switched on before you start the experiment.
        6) Click the 'Start Experiment' button to start the scheduler.

    D) Detailed explanation of setup parameters: (Tips are also available on mouseover)
        1) Measurement tab:
            Measurements tab allows setting up the parameters for a single IV measurement, which starts at the midpoint 
                between minimum and maximum currents, then goes stepwise to maximum current,
                down to minimum current and back to the midpoint.
            At the bottom of this tab is a 'Run test measurement' button, which you may use to check the electrical connections
            to your sample before running an experiment

            Maximum and Minimum Current - determines the range of current steps between which measurements are taken.
            Current Step - step size between data points. Determines number of points between maximum and minimum.
            Compliance Voltage - maximum voltage that will be applied to try to achieve the requested current.
            Buffer Size - number of voltage measurements averaged into a single data point at every current step.
            Acquisition Time - time interval over which a single voltage measurement is taken.
            Delay Time - time between consecutive measurements within a single data point (within a buffer)

        2) Scheduler tab:
            Scheduler manages the automatic data acquisition. Once an experiment is started, the scheduler records
                and processes temperature readouts until it determines that a stable temperature has been reached
                (the furnace has transitioned from a ramp step to a dwell step).
            Once a stable temperature is reached, a delay starts to allow the sample's temperature to equilibrate
                with the furnace.
            After the delay elapses, an interval timer starts, at the end of which an IV measurement is performed.
            After the measurement, the interval timer restarts and this cycle of timer - measurement is repeated until
                a change in temperature is detected, i.e., the furnace moves on to the next temperature level.
            When the temperature stabilises again, the delay timer is reset and everything is repeated.
            Each IV measurement is saved as a separate CSV file in a directory with the name provided by the user.
                (See Experiment tab for details)
            The measurements are finished when the furnace reaches a stable temperature below the minimum temperature
                specified by the user.

            Temperature gradient threshold - defines what is considered a 'stable temperature'.
            Delay - time allowed for the system to reach an equilibrium after a stable temperature is achieved.
            Measurement Interval - time between consecutive IV measurements, starts when delay elapses.
            Minimum Temperature - Temperature below which the scheduler will terminate if stability is achieved.
            TC Reference Temperature - Temperature of the reference junction for the scheduler's thermocouple

        3) Experiment Control Panel:
            The Experiment Control Panel's main purpose is to start an experiment (and possibly abort it, if needed).
            In order to start an experiment, i.e. a series of IV measurements at one or more temperature levels,
                provide a path to the directory where your data should be saved, for example, a folder with your name.
            Subsequently, provide the Experiment Name, which is a name for the data files and the enclosing folder
                to be created by the software for this experiment.
            At the end of the experiment, in the Directory you provided, you will find a folder with the Experiment name
                containing the temperature profile of the furnace throughout the experiment and all the IV measurements,
                each as a separate CSV file, named in the following format: EXPERIMENT-NAME_TEMPERATURE_#.
            Finally, the 'RT Measurement' button allows the user to run a single IV measurement without starting the scheduler.
                This function is meant to be used for tests at room temperature which do not involve awaiting
                temperature stabilisation.

            Directory - path to the folder where the experiment data should be saved.
            Experiment Name - name for the IV Measurement data files and the enclosing folder.
            Start experiment - Starts the scheduler that carries out the measurements at stable temperatures.
            Abort experiment - Stops the scheduler and any measurements currently running.
            RT measurement - runs a single IV measurement without starting the scheduler.

'''