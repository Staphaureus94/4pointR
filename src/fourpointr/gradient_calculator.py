import numpy as np
import pandas as pd
from scipy.stats import linregress
import matplotlib.pyplot as plt

def calculate_gradient(filename):
    # Load data into a pandas DataFrame
    data = pd.read_csv(filename, header=0, delimiter=';')

    # Ensure there are at least 61 lines of data
    if len(data) < 61:
        print("The file must contain at least 61 lines of data.")
        return

    # List to store the calculated gradients
    # gradients = []

    # Loop over the data starting from the 61st line
    for i in range(60, len(data)):
        # Subset of the data (current line and previous 60 lines)
        subset = data.iloc[i-60:i]

        # Extract time and temperature values
        time = subset['Timestamp'].values
        temperature = subset['Temperature'].values

        # Calculate the linear fit (gradient) using linregress
        slope, intercept, r_value, p_value, std_err = linregress(time, temperature)

        # Append the gradient (slope) to the list
        # gradients.append(slope)
        data.at[i, 'Gradient'] = slope *60

        # Print the result
        if slope > 0.5/60:
            print(f"Line {i+1}: Gradient = {slope:.3f}")

    # Plotting the results
    fig, ax1 = plt.subplots()

    # Plot Temperature on the first y-axis
    ax1.plot(data['Timestamp'], data['Temperature'], 'b-', label='Temperature')
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Temperature', color='b')

    # Create a second y-axis to plot Gradient
    ax2 = ax1.twinx()
    ax2.plot(data['Timestamp'], data['Gradient'], 'r-', label='Gradient')
    ax2.set_ylabel('Gradient', color='r')

    ax2.axhline(y=0.5, color='g', linestyle='--', linewidth=1)
    ax2.axhline(y=-0.5, color='g', linestyle='--', linewidth=1)

    # Display the plot
    fig.tight_layout()
    plt.show()
    # return gradients

# Usage example
filename = 'SchedulerTemperature.csv'  # Replace with your file name
calculate_gradient(filename)
