import time
from PyQt6.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)

t0 = time.time()
print("Importing DashboardFrame...")
from app.ui.dashboard_frame import DashboardFrame
print("Import time:", time.time() - t0)

t0 = time.time()
print("Initializing DashboardFrame...")
frame = DashboardFrame()
print("Init time:", time.time() - t0)
