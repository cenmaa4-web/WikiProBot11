@echo off
echo بدء تشغيل بوت تليجرام لتحميل الفيديوهات...

:: التحقق من وجود Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python غير مثبت. الرجاء تثبيت Python 3.8 أو أحدث
    pause
    exit /b
)

:: إنشاء بيئة افتراضية
if not exist "venv" (
    echo إنشاء بيئة افتراضية...
    python -m venv venv
)

:: تفعيل البيئة الافتراضية
call venv\Scripts\activate.bat

:: تثبيت المتطلبات
echo تثبيت المكتبات المطلوبة...
pip install -r requirements.txt

:: إنشاء مجلد التحميلات
if not exist "downloads" mkdir downloads

:: تشغيل البوت
echo البوت يعمل الآن...
python bot.py
pause
