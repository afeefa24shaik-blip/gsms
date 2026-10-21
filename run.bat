@echo off
title LuxeGifts - Gift Shop Management System (GSMS)
echo ========================================================
echo  Starting LuxeGifts Studio & Boutique - GSMS Dev Server
echo ========================================================
echo.
echo Local URL: http://127.0.0.1:8000/
echo Login URL: http://127.0.0.1:8000/login/
echo.
echo Demo Accounts (Password: [username]123):
echo   - Admin:      admin
echo   - Manager:    manager
echo   - Cashier:    cashier
echo   - Inventory:  inventory
echo.
echo Press Ctrl+C to stop the server.
echo.
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
pause
