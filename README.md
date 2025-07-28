# Hydro Scope

Hydrological model evaluation

## Installation


## Run

You can run the GUI called hydroscope.exe that should be installed with the above
installer.

## Other installation methods

If you have python installed you can install the requirements.pip with pip and
run the GUI program [bin/hydroscope.pyw](bin/hydroscope.pyw)

## GUI build instructions

I use pyinstaller to make a single executable (or a folder with an executable in
it).  Then inno to turn this into a MSI installer.

1. Download and install Python 3.13

2. Make a virtual environment and install packages
    ```
    python -m venv ~/Documents/venvs/hydroscope
    . ~/Documents/venvs/hydroscope/Scripts/activate
    pip install --upgrade pip
    pip install -r requirements.pip
    ```

3. To build dist/hydroscope/hydroscope.exe run
   ```
   pyinstaller -y hydroscope.spec
   ```

4. If you want to rebuild the hydroscope.spec file run
   ```
   pyinstaller -y bin/hydroscope.pyw --onedir --noconsole --hidden-import netCDF4 --add-data="bin/version.txt;." --add-data="bin/help.html;." --icon="etc/hydroscope.ico" --add-data="etc/hydroscope.ico;."
   ```
   Using --onefile makes a single executable hydroscope.exe which is neat and tidy
   but it is slower to run than having the entire directory, so --onedir is the
   way to go.  We use inno anyway to turn that directory into a MSI installer anyway.
 
5. The directory `dist/hydroscope` can be turned into a proper MSI Windows Setup
   file using inno and the setup file [inno.iss](inno.iss)


