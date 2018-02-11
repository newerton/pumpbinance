from distutils.core import setup
import py2exe

setup(windows = [{ 
"script": "pump_ui.py", 
"icon_resources": [(1, "bitcoin.ico")],
"dest_base" : "Binance P&D"
}])