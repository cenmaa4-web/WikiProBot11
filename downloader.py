import yt_dlp
import os
import asyncio
from config import TEMP_DIR, MAX_FILE_SIZE

class VideoDownloader:
    def __init__(self):
        # إنشاء مجلد التحميلات إذا لم يكن موجوداً
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)
    
    async def download_video(self, url: str) -> tuple:
        """
        تحميل الفيديو من الرابط
        تعيد: (مسار الملف, اسم الملف, حجم الملف)
        """
        try:
            # إعدادات yt-dlp
            ydl_opts = {
                'format': 'best[filesize<50M]',  # أفضل جودة بحجم أقل من 50 ميجا
                'outtmpl': f'{TEMP_DIR}/%(title)s.%(ext)s',  # قالب اسم الملف
                'quiet': True,  # إخفاء المخرجات
                'no_warnings': True,
                'extract_flat': False,
                'force_generic_extractor': False,
            }
            
            # تشغيل في thread منفصل لمنع حظر الحدث
            loop = asyncio.get_event_loop()
            
            # تحميل معلومات الفيديو
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # استخراج المعلومات
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                
                # التحقق من حجم الفيديو
                if 'filesize' in info and info['filesize'] > MAX_FILE_SIZE:
                    return None, None, "large_file"
                
                # تحميل الفيديو
                await loop.run_in_executor(None, lambda: ydl.download([url]))
                
                # الحصول على اسم الملف المحمل
                filename = ydl.prepare_filename(info)
                
                # التأكد من وجود الملف
                if os.path.exists(filename):
                    file_size = os.path.getsize(filename)
                    return filename, os.path.basename(filename), file_size
                else:
                    # قد يكون الامتداد مختلفاً
                    for file in os.listdir(TEMP_DIR):
                        if info['title'] in file:
                            filepath = os.path.join(TEMP_DIR, file)
                            return filepath, file, os.path.getsize(filepath)
                    
                    return None, None, "not_found"
                    
        except Exception as e:
            print(f"Error downloading video: {str(e)}")
            return None, None, str(e)
    
    def cleanup(self, filepath: str):
        """حذف الملف بعد الإرسال"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Error cleaning up {filepath}: {str(e)}")
