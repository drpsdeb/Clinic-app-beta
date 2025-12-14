import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io
import os
import shutil
import pandas as pd
import json
from datetime import date, datetime
import urllib.parse
from PIL import Image
import signal
import time

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(page_title="Universal EMR", page_icon="⚕️", layout="wide")
CSV_FILE = "patient_records.csv"
BACKUP_FILE = "patient_records.bak"
SETTINGS_FILE = "clinic_settings.json"
SIG_FILE = "signature.png"

# --- 2. SETTINGS MANAGEMENT ---
def load_settings():
    default_settings = {
        "doc_name": "Dr. Your Name",
        "doc_degree": "MBBS, MD",
        "doc_reg": "Reg No: 12345",
        "clinic_name": "My Clinic",
        "address": "Clinic Address City",
        "contact": "Ph: 9876543210"
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except:
            return default_settings
    return default_settings

def save_settings(settings_dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings_dict, f)

if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

# --- 3. SESSION STATE ---
def init_state():
    defaults = {
        "pat_name": "", "pat_age": 0, "pat_sex": "M", "pat_mobile": "",
        "pat_date": date.today(), "pat_diag": "", "pat_meds": "",
        "last_selected_row": None, "table_key": 0
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_state()

# --- 4. DATA FUNCTIONS (Save/Delete/Undo) ---
def create_backup():
    if os.path.exists(CSV_FILE):
        shutil.copyfile(CSV_FILE, BACKUP_FILE)

def undo_last_action():
    if os.path.exists(BACKUP_FILE):
        shutil.copyfile(BACKUP_FILE, CSV_FILE)
        st.toast("✅ Undo successful!")
        st.session_state.table_key += 1

def clear_form():
    st.session_state.pat_name = ""
    st.session_state.pat_age = 0
    st.session_state.pat_sex = "M"
    st.session_state.pat_mobile = ""
    st.session_state.pat_date = date.today()
    st.session_state.pat_diag = ""
    st.session_state.pat_meds = "" 
    st.session_state.last_selected_row = None
    st.session_state.table_key += 1 

def save_patient_data():
    create_backup()
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        if "Mobile" not in df.columns: df["Mobile"] = ""
    else:
        df = pd.DataFrame(columns=["Date", "Name", "Age", "Sex", "Mobile", "Diagnosis", "Medicines"])

    date_str = str(st.session_state.pat_date)
    name_input = st.session_state.pat_name.strip()
    
    if not name_input:
        st.error("Name is required!")
        return

    match_mask = (df['Name'] == name_input) & (df['Date'] == date_str)
    flat_meds = st.session_state.pat_meds.replace('\n', '; ')

    if match_mask.any():
        idx = df.index[match_mask][0]
        df.at[idx, 'Age'] = st.session_state.pat_age
        df.at[idx, 'Sex'] = st.session_state.pat_sex
        df.at[idx, 'Mobile'] = st.session_state.pat_mobile
        df.at[idx, 'Diagnosis'] = st.session_state.pat_diag
        df.at[idx, 'Medicines'] = flat_meds
        st.toast(f"✅ Updated {name_input}")
    else:
        new_row = {"Date": date_str, "Name": name_input, "Age": st.session_state.pat_age,
                   "Sex": st.session_state.pat_sex, "Mobile": st.session_state.pat_mobile,
                   "Diagnosis": st.session_state.pat_diag, "Medicines": flat_meds}
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        st.toast(f"✅ Saved {name_input}")
        
    df.to_csv(CSV_FILE, index=False)

def delete_record():
    create_backup()
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        match_mask = (df['Name'] == st.session_state.pat_name) & (df['Date'] == str(st.session_state.pat_date))
        if match_mask.any():
            df[~match_mask].to_csv(CSV_FILE, index=False)
            st.toast("🗑️ Deleted")
            clear_form()

# --- 5. PDF GENERATOR (MUST BE DEFINED HERE) ---
def generate_pdf():
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    s = st.session_state.settings 
    
    # Header
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, height - 50, s["clinic_name"].upper()) 
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, height - 80, s["doc_name"])
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 95, s["doc_degree"])
    c.drawString(50, height - 110, s["doc_reg"])
    c.drawRightString(width - 50, height - 80, s["address"])
    c.drawRightString(width - 50, height - 95, s["contact"])
    c.setLineWidth(1)
    c.line(50, height - 120, width - 50, height - 120)
    
    # Patient Info
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 150, f"Patient: {st.session_state.pat_name}")
    c.drawRightString(width - 50, height - 150, f"Date: {st.session_state.pat_date.strftime('%d-%b-%Y')}")
    c.drawString(50, height - 170, f"Age: {st.session_state.pat_age}y   Sex: {st.session_state.pat_sex}   Mob: {st.session_state.pat_mobile}")
    c.drawString(50, height - 190, f"Diagnosis: {st.session_state.pat_diag}")
    c.line(50, height - 200, width - 50, height - 200)
    
    # Rx
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 230, "Rx")
    y_position = height - 260
    c.setFont("Helvetica", 12)
    meds_list = st.session_state.pat_meds.split('\n')
    for i, med in enumerate(meds_list):
        if med.strip():
            c.drawString(60, y_position, f"{i+1}. {med.strip()}")
            y_position -= 25
            if y_position < 150: 
                c.showPage()
                y_position = height - 50

    # Signature
    sig_y = 100
    if os.path.exists(SIG_FILE):
        try:
            c.drawImage(SIG_FILE, width - 180, sig_y, width=100, height=45, mask='auto', preserveAspectRatio=True)
        except: pass
    
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - 50, sig_y - 15, s["doc_name"])
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 50, sig_y - 30, s["doc_degree"])
    c.save()
    buffer.seek(0)
    return buffer

# --- 6. SIDEBAR MENU ---
with st.sidebar:
    st.title("🏥 Clinic Menu")

    with st.expander("👤 Doctor Profile & Settings", expanded=False):
        st.info("Update your details here.")
        with st.form("profile_form"):
            s_doc = st.text_input("Doctor Name", st.session_state.settings["doc_name"])
            s_deg = st.text_input("Degrees", st.session_state.settings["doc_degree"])
            s_reg = st.text_input("Reg No", st.session_state.settings["doc_reg"])
            s_cln = st.text_input("Clinic Name", st.session_state.settings["clinic_name"])
            s_add = st.text_input("Address", st.session_state.settings["address"])
            s_con = st.text_input("Contact", st.session_state.settings["contact"])
            
            if st.form_submit_button("💾 Save Profile"):
                new_settings = {
                    "doc_name": s_doc, "doc_degree": s_deg, "doc_reg": s_reg,
                    "clinic_name": s_cln, "address": s_add, "contact": s_con
                }
                save_settings(new_settings)
                st.session_state.settings = new_settings
                st.toast("✅ Profile Saved!")

    with st.expander("✍️ Signature", expanded=False):
        uploaded_sig = st.file_uploader("Upload PNG", type=['png'])
        if uploaded_sig:
            with open(SIG_FILE, "wb") as f:
                f.write(uploaded_sig.getbuffer())
            st.success("Signature Saved!")
            st.image(uploaded_sig, width=150)

    with st.expander("❓ Help / Instructions", expanded=False):
        st.markdown("""
        **1. New Patient:** Click '✨ New'.
        **2. Prescribe:** Type meds (one per line).
        **3. Save:** Click '💾 Save'.
        **4. WhatsApp:** Click '💬 WhatsApp' -> Drag PDF.
        """)

# --- 7. MAIN LAYOUT (Title & Columns) ---
st.title(f"👨‍⚕️ {st.session_state.settings['clinic_name']}") 
st.markdown("---")

col_left, col_right = st.columns([1, 1.2])

# --- RIGHT COLUMN (History + Exit) ---
with col_right:
    col_search, col_undo, col_exit = st.columns([3, 1, 1])
    
    with col_search:
        st.subheader("🔍 Patient History")
    with col_undo:
        st.button("↩️ Undo", on_click=undo_last_action, help="Reverse last change")
    with col_exit:
        if st.button("❌ Exit", type="primary", help="Close App Safely"):
            st.error("🛑 SHUTTING DOWN...")
            st.write("You can safely close this window now.")
            time.sleep(3)
            os.kill(os.getpid(), signal.SIGTERM)

    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        if "Mobile" not in df.columns: df["Mobile"] = ""
        
        search = st.text_input("Search...", "")
        if search:
            mask = df['Name'].str.contains(search, case=False, na=False) | df['Diagnosis'].str.contains(search, case=False, na=False)
            filtered_df = df[mask]
        else:
            filtered_df = df.sort_index(ascending=False)

        sel = st.dataframe(filtered_df, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key=f"table_{st.session_state.table_key}")
        
        if sel.selection.rows:
            idx = filtered_df.index[sel.selection.rows[0]]
            if idx != st.session_state.last_selected_row:
                r = df.loc[idx]
                st.session_state.pat_name = r['Name']
                st.session_state.pat_age = int(r['Age'])
                st.session_state.pat_sex = r['Sex']
                st.session_state.pat_mobile = str(r['Mobile']) if pd.notna(r['Mobile']) else ""
                st.session_state.pat_date = datetime.strptime(str(r['Date']), '%Y-%m-%d').date()
                st.session_state.pat_diag = r['Diagnosis']
                st.session_state.pat_meds = str(r['Medicines']).replace('; ', '\n')
                st.session_state.last_selected_row = idx
                st.rerun()

# --- LEFT COLUMN (Form Inputs) ---
with col_left:
    c_h, c_r = st.columns([3, 1])
    c_h.subheader("📝 Prescription")
    c_r.button("✨ New", on_click=clear_form)

    st.text_input("Name", key="pat_name")
    st.text_input("Mobile (for WhatsApp)", key="pat_mobile")
    c1, c2 = st.columns(2)
    c1.number_input("Age", 0, key="pat_age")
    c2.selectbox("Sex", ["M", "F", "Other"], key="pat_sex")
    st.date_input("Date", key="pat_date")
    st.text_input("Diagnosis", key="pat_diag")
    
    st.markdown("### Medicine")
    st.text_area("Rx (One per line)", height=150, key="pat_meds")

    # ACTIONS
    c_save, c_del = st.columns(2)
    c_save.button("💾 Save", on_click=save_patient_data, use_container_width=True)
    c_del.button("🗑️ Delete", on_click=delete_record, use_container_width=True)

    st.markdown("---")
    
    # PDF BUTTON (Calling the function defined above)
    pdf_bytes = generate_pdf()
    c_pdf, c_wa = st.columns(2)
    c_pdf.download_button("📄 PDF", pdf_bytes, file_name=f"Rx_{st.session_state.pat_name}.pdf", mime="application/pdf", use_container_width=True)
    
    mob = st.session_state.pat_mobile.strip()
    if mob:
        clean_mob = ''.join(filter(str.isdigit, mob))
        if len(clean_mob) == 10: clean_mob = "91" + clean_mob
        txt = urllib.parse.quote(f"Namaste {st.session_state.pat_name}, please find your prescription from {st.session_state.settings['doc_name']} attached.")
        link = f"https://wa.me/{clean_mob}?text={txt}"
        c_wa.link_button("💬 WhatsApp", link, use_container_width=True)
    else:
        c_wa.button("💬 WhatsApp", disabled=True, use_container_width=True)