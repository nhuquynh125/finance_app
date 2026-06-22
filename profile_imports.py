import time

print("Profiling imports...")
t0 = time.time()
from PyQt6.QtWidgets import QApplication
print("QApplication:", time.time() - t0)

t0 = time.time()
from app.core.theme_engine import theme_engine
print("theme_engine:", time.time() - t0)

t0 = time.time()
from app.data.models import init_auth_database
print("init_auth_database:", time.time() - t0)

t0 = time.time()
from app.ui.login_window import LoginWindow
print("LoginWindow:", time.time() - t0)

t0 = time.time()
from app.ui.main_window import MainWindow
print("MainWindow:", time.time() - t0)
