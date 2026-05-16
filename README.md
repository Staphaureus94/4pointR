# 4PointR

Graphical acquisition software for automated four-point resistance measurements
using a Keithley 2400 sourcemeter and a temperature-controlled tube furnace.

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

## Detailed operation

The software uses both the front and back terminals of the Keithley
to not only measure the IV characteristics of the sample
but also automatically schedule the measurements without the need to connect it to the furnace control unit.

The back terminals are used for the four point resistance measurements via IV scans.
The software allows setting the extremal current values and current step
and performs a scan in the following order: 0 -> max -> min -> 0.

When no scans are running, the software uses the Keithley's front terminals
to read out the K-type thermocouple in the furnace and determine the temperature stability.
If the temperature gradient in the previous rolling 60 s is less than the preset value (default 0.5 K/min)
the temperature is determined as 'stable' and the scans are scheduled
after a 'delay' which allows time to settle at a new temperature point and subsequently
after every 'interval' until temperature stability is broken, indicating that the furnace is
moving to the next preset temperature point. The automated scans stop when a stable temperature
is reached below a set limit, default 200 °C.


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
