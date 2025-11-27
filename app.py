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
            with st.spinner("Analyzing portfolio..."):
                # Save uploaded file to temp path
                with open("temp.pdf", "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # Parse PDF
                data = casparser.read_cas_pdf("temp.pdf", password)
                
                total_val = 0.0
                total_loss = 0.0
                bad_funds = []
                
                # Iterate through portfolios
                for folio in data.folios:
                    for scheme in folio.schemes:
                        name = scheme.scheme
                        value = scheme.valuation.value
                        total_val += value
                        
                        # LOGIC: If "Direct" is missing, it's likely Regular
                        if "Direct" not in name:
                            # Math: Estimate 1% annual commission loss
                            loss = value * 0.01 
                            total_loss += loss
                            
                            bad_funds.append({
                                "Fund Name": name,
                                "Value": f"₹{value:,.0f}",
                                "Yearly Loss": f"₹{loss:,.0f}"
                            })

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

        except Exception as e:
            st.error(f"❌ Error reading PDF. Check your password. Details: {e}")
    else:
        st.warning("⚠️ Please upload a file and enter a password.")
