#!/bin/bash

echo "🚀 بدء تشغيل بوت تليجرام لتحميل الفيديوهات..."

# التحقق من وجود Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python غير مثبت. الرجاء تثبيت Python 3.8 أو أحدث"
    exit 1
fi

# إنشاء بيئة افتراضية
if [ ! -d "venv" ]; then
    echo "📦 إنشاء بيئة افتراضية..."
    python3 -m venv venv
fi

# تفعيل البيئة الافتراضية
source venv/bin/activate

# تثبيت المتطلبات
echo "📦 تثبيت المكتبات المطلوبة..."
pip install -r requirements.txt

# إنشاء مجلد التحميلات
mkdir -p downloads

# تشغيل البوت
echo "✅ البوت يعمل الآن..."
python3 bot.py
