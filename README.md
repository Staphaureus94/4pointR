# 4PointR

Graphical acquisition software for automated four-point resistance measurements
using a Keithley 2400 sourcemeter and a temperature-controlled tube furnace.

The software allows

## Purpose

This software was developed to automate high-temperature four-point resistance
measurements at Forschungszentrum Jülich. It provides a PyQt-based graphical
interface for configuring current sweeps, monitoring thermocouple temperature,
detecting temperature stabilisation, scheduling IV measurements, and saving
measurement data to CSV files.

## Features

- GUI-based configuration of current sweeps
- Automated Keithley 2400 control via PyMeasure
- Temperature monitoring using a K-type thermocouple
- Temperature-stability detection before scheduled measurements
- Automated CSV export of IV sweeps and furnace temperature logs
- Integrated user help / operating procedure

## Hardware setup

- Keithley 2400 sourcemeter
- Tube furnace with electrical feedthroughs
- K-type thermocouple
- USB-to-serial interface, originally tested with an ATEN USB-to-Serial Bridge
- Four-point sample holder for high-temperature measurements

## Status

This is research-lab software developed for a specific experimental setup.
It is shared for transparency and documentation of the instrument-control work,
not as a universally plug-and-play commercial application.


## Safety note

This software controls measurements involving high temperature, electrical
contacts, and laboratory hardware. Users remain responsible for checking cooling
water, furnace configuration, electrical limits, and emergency shutdown procedures.

## Author

Stefan Kucharski
