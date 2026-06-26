import streamlit as st
import dlisio
import lasio
import numpy as np
import pandas as pd
import io
import tempfile
from pathlib import Path
import zipfile
from datetime import datetime
import re
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# إعداد الصفحة
st.set_page_config(page_title="PetroLog Converter", layout="wide")

st.title("🛢️ PetroLog Converter Pro")
st.markdown("تحويل ملفات LIS/DLIS إلى LAS بدقة عالية مع معالجة ملفات DIPLOG")

# ============================================================
# المحرك الاحترافي لقراءة LIS/DLIS
# ============================================================
def read_well_file_pro(file_bytes, file_name):
    tmp_path = None
    with tempfile.NamedTemporaryFile(delete=False, suffix='.lis') as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    curves, metadata = {}, {}
    well_info = {'well_name': 'UNKNOWN', 'method': 'UNKNOWN'}
    
    try:
        files = dlisio.load(tmp_path)
        parsed_files = list(files) if isinstance(files, tuple) else [files]
        
        for f in parsed_files:
            well_info['method'] = "LIS/DLIS (Logical Parser)"
            # استخراج اسم البئر من النصوص (Header)
            if hasattr(f, 'text'):
                for text_record in f.text:
                    txt = text_record.text.decode('ascii', errors='ignore').strip()
                    match = re.search(r'(?:WN|WELL|WELLNAME)\s+([A-Za-z0-9\-\/]+)', txt)
                    if match: well_info['well_name'] = match.group(1).strip()
            
            # استخراج المنحنيات
            log_passes = f.log_passes() if hasattr(f, 'log_passes') else []
            for p in log_passes:
                pass_data = p.curves()
                if isinstance(pass_data, np.ndarray) and pass_data.dtype.names:
                    for name in pass_data.dtype.names:
                        unit = ""
                        for spec in p.data_specs:
                            if spec.mnemonic == name:
                                unit = getattr(spec, 'units', '')
                                break
                        data = np.squeeze(pass_data[name])
                        if data.ndim == 2: # تفكيك الـ Pads
                            for i in range(data.shape[1]):
                                curves[f"{name}_P{i+1}"] = data[:, i]
                                metadata[f"{name}_P{i+1}"] = unit
                        else:
                            curves[name] = data
                            metadata[name] = unit
        
        if not curves: return None, None, None, "لم يتم العثور على منحنيات."
        return curves, metadata, well_info, None
    except Exception as e:
        return None, None, None, str(e)
    finally:
        if tmp_path: Path(tmp_path).unlink()

# ============================================================
# دالة التحويل (مع محاذاة البيانات وتعديل الاسم)
# ============================================================
def convert_to_las(file_bytes, file_name, new_well_name):
    try:
        curves, metadata, well_info, error = read_well_file_pro(file_bytes, file_name)
        if error: return None, error
        
        # محاذاة الأطوال
        min_len = min(len(d) for d in curves.values())
        las = lasio.LASFile()
        las.well['WELL'] = lasio.HeaderItem('WELL', value=new_well_name)
        
        # إضافة العمق
        depth_keys = [k for k in curves.keys() if k.upper() in ['DEPT', 'DEPTH', 'ADEPT', 'MD']]
        depth_name = depth_keys[0] if depth_keys else None
        
        if depth_name:
            las.append_curve('DEPT', curves[depth_name][:min_len], unit=metadata[depth_name])
        else:
            las.append_curve('DEPT', np.arange(min_len) * 0.1524, unit='m')
            
        for name, data in curves.items():
            if name == depth_name: continue
            las.append_curve(name, data[:min_len], unit=metadata.get(name, ''))
            
        output = io.StringIO()
        las.write(output, version=2)
        return output.getvalue().encode('utf-8'), None
    except Exception as e:
        return None, str(e)

# ============================================================
# واجهة المستخدم
# ============================================================
uploaded_file = st.file_uploader("ارفعي ملف LIS/DLIS", type=['lis', 'dlis'])
new_name = st.text_input("أدخلي اسم البئر الجديد (NSTA Convention):", "110/13-12")

if uploaded_file and st.button("تحويل"):
    with st.spinner("جاري التحويل..."):
        res, err = convert_to_las(uploaded_file.read(), uploaded_file.name, new_name)
        if res:
            st.success("تم التحويل بنجاح!")
            st.download_button("تحميل ملف LAS", res, file_name=f"{new_name}.las")
        else:
            st.error(f"خطأ: {err}")
