import streamlit as st
import dlisio
import lasio
import numpy as np
import io

def process_dlis_to_las(file_bytes):
    # استخدام مكتبة dlisio الاحترافية لقراءة ملفات DLIS
    f = dlisio.dlis.load(io.BytesIO(file_bytes))
    
    # تحضير ملف LAS جديد
    las = lasio.LASFile()
    
    for lf in f:
        for frame in lf.frames:
            for curve in frame.curves():
                # استخراج البيانات والاسم والوحدة
                name = curve.name
                data = curve.curves()
                unit = curve.units
                
                # إضافة المنحنى لملف الـ LAS
                las.append_curve(name, data, unit=unit)
    
    # تصدير إلى نص
    output = io.StringIO()
    las.write(output)
    return output.getvalue()

# واجهة المستخدم في Streamlit
uploaded_file = st.file_uploader("ارفعي ملف الـ DLIS هنا")
if uploaded_file:
    las_content = process_dlis_to_las(uploaded_file.read())
    st.download_button("حملي ملف الـ LAS النظيف", las_content, "converted.las")
