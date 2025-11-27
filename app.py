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
                # Save uploaded file to temp path (Required for casparser)
                with open("temp.pdf", "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # Parse PDF
                # This reads the CAMS/KFintech file structure
                data = casparser.read_cas_pdf("temp.pdf", password)
                
                total_val = 0.0
                total_loss = 0.0
                bad_funds = []
                
                # Iterate through all Folios (Accounts) found in the PDF
                for folio in data.folios:
                    for scheme in folio.schemes:
                        name = scheme.scheme
                        
                        # FIX 1: Convert Decimal to float immediately
                        # Use (value or 0) to handle rare cases where valuation is missing
                        value = float(scheme.valuation.value or 0)
                        
                        # Add to total portfolio value
                        total_val += value
                        
                        # FIX 2: Case-Insensitive Check
                        # We convert the fund name to UPPERCASE (.upper()) 
                        # so that "DIRECT", "Direct", and "direct" are all detected.
                        if "DIRECT" not in name.upper():
                            
                            # It is likely a Regular plan. Calculate Loss.
                            # Assumption: 1% commission difference.
                            loss = value * 0.01 
                            total_loss += loss
                            
                            # Only list it if it has a non-zero value
                            if value > 0:
                                bad_funds.append({
                                    "Fund Name": name,
                                    "Value": f"₹{value:,.0f}",
                                    "Yearly Loss": f"₹{loss:,.0f}"
                                })

                # --- RESULTS DISPLAY ---
                st.divider()
                
                # Display Metrics
                col1, col2 = st.columns(2)
                col1.metric("Portfolio Value", f"₹{total_val:,.0f}")
                col2.metric("Est. Annual Loss", f"₹{total_loss:,.0f}", delta_color="inverse")
                
                # Logic for Output Message
                if total_loss > 0:
                    st.error(f"⚠️ You are wasting ~₹{total_loss:,.0f} every year!")
                    st.write("These funds are charging you hidden commissions:")
                    
                    # Create a clean table for Bad Funds
                    df = pd.DataFrame(bad_funds)
                    st.table(df)
                    
                    st.info("💡 Solution: Switch these funds to 'Direct Plans' on apps like Zerodha, Groww, or MFCentral.")
                
                else:
                    # Success State
                    st.balloons()
                    st.success("✅ Excellent! Your portfolio is 100% Direct Plans.")
                    st.markdown("You are not paying any hidden distributor commissions.")

        except Exception as e:
            st.error(f"❌ Error reading PDF. Check your password. Details: {e}")
    else:
        st.warning("⚠️ Please upload a file and enter a password.")
