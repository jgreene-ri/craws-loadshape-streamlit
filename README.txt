CRAWS Load Shape Explorer

This is a simple Streamlit app for exploring CRAWS load shape data.

The app uses two 8760 load shape files (kWh and Therms) along with a
building type mapping file to generate interactive charts.

  -------------------
  Project structure
  -------------------

Put the input data files inside a folder called:

Inputs/

  ----------------------
  Install requirements
  ----------------------

Activate your environment and install the required packages:

pip install -r requirements.txt

  -------------
  Run the app
  -------------

From the project folder run:

streamlit run app.py

Streamlit will open the app in your browser.


  -------------------
  What the app does
  -------------------

The app has several views for exploring the load shape data:

Hourly by Building Type Shows the hourly load profile for a selected
building type or the average across all building types.

Hourly by Climate Zone Shows the hourly load profile for a selected
climate zone or the average across all climate zones.

Consumption by Climate Zone Bar chart comparing total consumption across
climate zones and building types.

Consumption by Building Type Bar chart comparing total consumption
across building types and climate zones.

You can switch between kWh and Therms using the control panel.

  -------
  Notes
  -------

All load shapes contain 8760 hourly values (one full year). The bar
charts use summed annual values from those hourly load shapes.
