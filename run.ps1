# LuxeGifts - Gift Shop Management System PowerShell Launcher
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " Starting LuxeGifts Studio & Boutique - GSMS Dev Server" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Local URL: http://127.0.0.1:8000/" -ForegroundColor Green
Write-Host "Login URL: http://127.0.0.1:8000/login/" -ForegroundColor Green
Write-Host ""
Write-Host "Demo Accounts (Password: [username]123):" -ForegroundColor Yellow
Write-Host "  - Admin:      admin"
Write-Host "  - Manager:    manager"
Write-Host "  - Cashier:    cashier"
Write-Host "  - Inventory:  inventory"
Write-Host ""
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Gray
Write-Host ""

& ".\venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
