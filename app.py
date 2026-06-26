import streamlit as st
import dlisio
import lasio
import numpy as np
import pandas as pd
import io
import os
import tempfile
from pathlib import Path
import re

# إعداد الصفحة
st.set_page_config(page_title="PetroLog Converter Pro", layout="wide")
st.title("🛢️ PetroLog Converter Pro")
st.markdown("محول احترافي لملفات LIS/DLIS مع دعم كامل لمعايير NSTA")

# ============================================================
# المحرك الاحترافي: فك تشفير البيانات الثنائية
# ============================================================
def process_file(file_bytes, file_name, new_well_name):
    # 1. إنشاء ملف مؤقت للتعامل مع dlisio (يحل مشكلة OSError)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.dlis')
    temp_file.write(file_bytes)
    temp_file.close()
    
    curves, metadata = {}, {}
    well_info = {'well_name': new_well_name}
    
    try:
        # 2. تحميل الملف
        files = dlisio.load(temp_file.name)
        parsed_files = list(files) if isinstance(files, tuple) else [files]
        
        for f in parsed_files:
            # استخراج المنحنيات والـ Pads (DIPLOG Support)
            if hasattr(f, 'log_passes'): # LIS logic
                for p in f.log_passes():
                    pass_data = p.curves()
                    if isinstance(pass_data, np.ndarray) and pass_data.dtype.names:
                        for name in pass_data.dtype.names:
                            data = np.squeeze(pass_data[name])
                            if data.ndim == 2: # تفكيك الـ Pads
                                for i in range(data.shape[1]):
                                    curves[f"{name}_P{i+1}"] = data[:, i]
                            else:
                                curves[name] = data
            elif hasattr(f, 'frames'): # DLIS logic
                for frame in f.frames:
                    for curve in frame.curves():
                        data = np.squeeze(curve.curves())
                        if data.ndim == 2:
                            for i in range(data.shape[1]):
                                curves[f"{curve.name}_P{i+1}"] = data[:, i]
                        else:
                            curves[curve.name] = data

        if not curves: return None, "لم يتم العثور على منحنيات."

        # 3. التحويل لـ LAS
        las = lasio.LASFile()
        las.well['WELL'] = lasio.HeaderItem('WELL', value=new_well_name)
        
        # محاذاة البيانات (توحيد الأطوال)
        min_len = min(len(d) for d in curves.values())
        
        # إضافة العمق
        depth_name = next((k for k in curves.keys() if k.upper() in ['DEPT', 'DEPTH', 'ADEPT']), None)
        if depth_name:
            las.append_curve('DEPT', curves[depth_name][:min_len], unit='m')
        else:
            las.append_curve('DEPT', np.arange(min_len) * 0.1524, unit='m')

        # إضافة باقي المنحنيات
        for name, data in curves.items():
            if name == depth_name: continue
            las.append_curve(name, data[:min_len], unit='')
            
        output = io.StringIO()
        las.write(output, version=2)
        return output.getvalue().encode('utf-8'), None
        
    except Exception as e:
        return None, str(e)
    finally:
        if os.path.exists(temp_file.name): os.remove(temp_file.name)

# ============================================================
# الواجهة
# ============================================================
uploaded_file = st.file_uploader("ارفعي ملف LIS أو DLIS", type=['lis', 'dlis'])
new_name = st.text_input("اسم البئر الجديد (معيار NSTA):", "110/13-12")

if uploaded_file and st.button("بدء التحويل"):
    with st.spinner("جاري فك الشفرة والتحويل..."):
        res, err = process_file(uploaded_file.read(), uploaded_file.name, new_name)
        if res:
            st.success("تم التحويل بنجاح!")
            st.download_button("تحميل ملف الـ LAS النظيف", res, f"{new_name}.las")
        else:
            st.error(f"حدث خطأ أثناء المعالجة: {err}")
