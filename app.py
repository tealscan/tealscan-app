import streamlit as st
import pandas as pd
import casparser
from io import BytesIO

# --- CONFIGURATION ---
st.set_page_config(page_title="TealScan", page_icon="💸")

# --- UI HEADER ---
st.title("💸 TealScan: Mutual Fund X-Ray")
st.markdown("""
**Stop losing money to hidden commissions.**
Upload your **CAMS/KFintech CAS PDF** to detect 'Regular' funds.
""")

# --- INPUT SECTION ---
uploaded_file = st.file_uploader("📂 Step 1: Upload CAS PDF", type="pdf")
password = st.text_input("🔑 Step 2: PDF Password (PAN)", type="password")

# --- LOGIC SECTION ---
if st.button("🚀 Scan Portfolio"):
    if uploaded_file and password:
        try:
            # We use a progress bar because the 'Robust' engine is slower
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            status_text.text("Initializing Deep Scan...")
            progress_bar.progress(10)

            # Save uploaded file to temp path
            with open("temp.pdf", "wb") as f:
                f.write(uploaded_file.getbuffer())

            status_text.text("Parsing PDF layers (This may take 10-15 seconds)...")
            progress_bar.progress(30)

            # --- DEEP RESEARCH FIX ---
            # force_pdfminer=True switches to a slower but more accurate engine
            # capable of reading tables that split across pages.
            data = casparser.read_cas_pdf("temp.pdf", password, force_pdfminer=True)
            
            progress_bar.progress(80)
            status_text.text("Analyzing Funds...")
            
            total_val = 0.0
            total_loss = 0.0
            bad_funds = []
            
            # Iterate through all Folios
            for folio in data.folios:
                for scheme in folio.schemes:
                    name = scheme.scheme
                    
                    # FIX: Handle cases where valuation might be None
                    value = float(scheme.valuation.value or 0)
                    
                    total_val += value
                    
                    # LOGIC: Check for "DIRECT" (Case Insensitive)
                    if "DIRECT" not in name.upper():
                        # Math: Estimate 1% annual commission loss
                        loss = value * 0.01 
                        total_loss += loss
                        
                        # Only flag if it has value
                        if value > 0:
                            bad_funds.append({
                                "Fund Name": name,
                                "Value": f"₹{value:,.0f}",
                                "Yearly Loss": f"₹{loss:,.0f}"
                            })

            progress_bar.progress(100)
            status_text.empty() # Clear status text
            progress_bar.empty() # Clear progress bar

            # --- RESULTS ---
            st.divider()
            
            col1, col2 = st.columns(2)
            col1.metric("Portfolio Value", f"₹{total_val:,.0f}")
            col2.metric("Est. Annual Loss", f"₹{total_loss:,.0f}", delta_color="inverse")
            
            if total_loss > 0:
                st.error(f"⚠️ You are wasting ~₹{total_loss:,.0f} every year!")
                st.write("These funds are charging you hidden commissions:")
                st.table(pd.DataFrame(bad_funds))
                st.info("💡 Solution: Switch these funds to 'Direct Plans' on any modern app.")
            else:
                st.balloons()
                st.success("✅ Excellent! Your portfolio is 100% Direct Plans.")
                st.markdown("You are not paying any hidden distributor commissions.")

        except Exception as e:
            st.error(f"❌ Error reading PDF. Check your password. Details: {e}")
    else:
        st.warning("⚠️ Please upload a file and enter a password.")
