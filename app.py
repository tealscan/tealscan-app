import streamlit as st
import pandas as pd
import casparser
import numpy as np
from datetime import date
from pyxirr import xirr

# --- CONFIGURATION ---
st.set_page_config(page_title="TealScan Pro", page_icon="📈", layout="wide")

# --- HELPER FUNCTIONS ---

def get_asset_class(fund_name):
    """Guess Asset Class based on keywords in the Fund Name"""
    name = fund_name.upper()
    if any(x in name for x in ["LIQUID", "OVERNIGHT", "BOND", "DEBT", "GILT", "TREASURY"]):
        return "Debt"
    elif any(x in name for x in ["GOLD", "SILVER", "COMMODITIES"]):
        return "Commodity"
    elif any(x in name for x in ["HYBRID", "BALANCED", "DYNAMIC"]):
        return "Hybrid"
    else:
        return "Equity"

def calculate_metrics(scheme):
    """
    Smart calculation that handles 'Partial Data' gracefully.
    Returns: (XIRR, Absolute_Return, Status_Message)
    """
    transactions = scheme.transactions
    current_val = float(scheme.valuation.value or 0)
    total_cost = float(scheme.valuation.cost or 0)
    
    # 1. Calculate Absolute Return (Simple & Robust)
    abs_return = 0.0
    if total_cost > 0:
        abs_return = ((current_val - total_cost) / total_cost) * 100

    # 2. Check for "No Transaction" Case
    if not transactions:
        # If we have no history, we can't calc XIRR. Return Absolute only.
        return None, abs_return, "No History"

    # 3. Try XIRR Calculation
    dates = []
    amounts = []
    
    try:
        # Check if there is a massive Opening Balance mismatch
        # If current value is 10x the sum of transactions found, the data is partial.
        invested_sum = sum([float(t.amount) for t in transactions if t.amount])
        if invested_sum > 0 and (current_val / invested_sum) > 5.0 and total_cost > invested_sum:
             # Likely a partial statement (Huge value, tiny SIPs found)
             return None, abs_return, "Partial Data"

        for txn in transactions:
            dt = txn.date
            amt = float(txn.amount or 0)
            if amt == 0: continue
            
            desc = str(txn.description).upper()
            
            # Sign logic: Money OUT (-), Money IN (+)
            if any(x in desc for x in ["PURCHASE", "SIP", "SWITCH IN", "STP IN", "DIVIDEND"]):
                amounts.append(amt * -1.0)
            elif any(x in desc for x in ["REDEMPTION", "SWITCH OUT", "STP OUT", "SWP"]):
                amounts.append(amt * 1.0)
            else:
                amounts.append(amt * -1.0) # Default to purchase
                
            dates.append(dt)

        # Add Current Value
        dates.append(date.today())
        amounts.append(current_val)

        res = xirr(dates, amounts)
        
        if res is None: 
            return None, abs_return, "Calc Error"
        
        xirr_val = res * 100
        
        # Sanity Check: If XIRR > 100% or < -90%, fallback to Absolute
        if xirr_val > 100.0 or xirr_val < -90.0:
             return None, abs_return, "Data Mismatch"
             
        return xirr_val, abs_return, "OK"

    except Exception:
        return None, abs_return, "Error"

def get_fund_rating(xirr_val, abs_val):
    """Rating Logic with Fallback"""
    # Use XIRR if available, else Absolute Return
    val = xirr_val if xirr_val is not None else abs_val
    
    if val >= 20.0:
        return "🔥 IN-FORM"
    elif 12.0 <= val < 20.0:
        return "✅ ON-TRACK"
    elif 0.0 < val < 12.0:
        return "⚠️ OFF-TRACK"
    else:
        return "❌ OUT-OF-FORM"

# --- MAIN UI ---

st.title("📈 TealScan Pro: Portfolio Health Engine")

# --- INPUT SECTION (Main Page) ---
st.subheader("📂 Step 1: Upload Data")
st.info("💡 For accurate XIRR, please upload a **'Since Inception'** CAS PDF. 'Financial Year' statements may show N/A.")
uploaded_file = st.file_uploader("Upload CAMS/KFintech CAS (PDF)", type="pdf")
password = st.text_input("Enter PDF Password (PAN)", type="password")

if uploaded_file and password:
    if st.button("🚀 Run Full Diagnosis", type="primary"):
        try:
            with st.spinner("Initializing Deep Scan Engine (pdfminer)..."):
                with open("temp.pdf", "wb") as f:
                    f.write(uploaded_file.getbuffer())

                data = casparser.read_cas_pdf("temp.pdf", password, force_pdfminer=True)

                portfolio_data = []
                total_curr = 0.0
                total_invested = 0.0
                
                for folio in data.folios:
                    for scheme in folio.schemes:
                        name = scheme.scheme
                        valuation = float(scheme.valuation.value or 0)
                        cost = float(scheme.valuation.cost or 0)
                        
                        if valuation < 100: continue
                        
                        category = get_asset_class(name)
                        is_regular = "DIRECT" not in name.upper()
                        
                        # Calculate Metrics
                        my_xirr, my_abs, status = calculate_metrics(scheme)
                        
                        # Determine Rating
                        rating = get_fund_rating(my_xirr, my_abs)
                        
                        # Determine Display Values
                        display_xirr = f"{my_xirr:.2f}%" if my_xirr is not None else "N/A"
                        display_abs = f"{my_abs:.2f}%"
                        
                        portfolio_data.append({
                            "Fund Name": name,
                            "Category": category,
                            "Value": valuation,
                            "Invested": cost,
                            "Type": "Regular 🔴" if is_regular else "Direct 🟢",
                            "XIRR": display_xirr,
                            "Abs Return": display_abs,
                            "Rating": rating,
                            "Data Status": status
                        })
                        
                        total_curr += valuation
                        total_invested += cost

                # --- DASHBOARD ---
                df = pd.DataFrame(portfolio_data)
                
                # METRICS
                st.divider()
                st.subheader("📊 Portfolio Summary")
                
                # Calculate Overall Portfolio Gain
                total_gain = total_curr - total_invested
                total_gain_pct = (total_gain / total_invested * 100) if total_invested > 0 else 0
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Value", f"₹{total_curr:,.0f}")
                m2.metric("Total Invested", f"₹{total_invested:,.0f}")
                m3.metric("Overall Gain", f"₹{total_gain:,.0f}", f"{total_gain_pct:.1f}%")

                # HEALTH CARD
                st.subheader("🏥 Fund Health Card")
                st.caption("Note: funds with 'N/A' XIRR are due to partial transaction history in the PDF.")
                
                st.dataframe(
                    df,
                    column_config={
                        "Value": st.column_config.NumberColumn(format="₹%d"),
                        "Invested": st.column_config.NumberColumn(format="₹%d"),
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # DOWNLOAD CSV
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Download Analysis Report",
                    csv,
                    "tealscan_report.csv",
                    "text/csv",
                    key='download-csv'
                )

        except Exception as e:
            st.error(f"❌ Error during analysis. Details: {e}")
