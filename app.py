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
        # Default to Equity for most common funds (Small Cap, Mid Cap, Index, etc.)
        return "Equity"

def calculate_fund_xirr(transactions, current_valuation):
    """
    Calculate XIRR using pyxirr.
    Logic: Cashflows = [ -Investments, +Redemptions, +CurrentValue (as of today) ]
    """
    dates = []
    amounts = []

    try:
        # 1. Process Past Transactions
        for txn in transactions:
            dt = txn.date
            amt = float(txn.amount or 0)
            
            # If amt is 0, skip
            if amt == 0: continue
            
            # Logic: Purchase is Cash OUT (-), Redemption is Cash IN (+)
            # casparser usually gives negative for Reversal/Redemption? 
            # We need to ensure Purchase is Negative for XIRR calculation.
            
            description = str(txn.description).upper()
            
            # Check transaction type based on description or amount sign
            # In casparser, amount is absolute. We must assign sign.
            if any(x in description for x in ["PURCHASE", "SIP", "SWITCH IN", "STP IN", "DIVIDEND REINVEST"]):
                amounts.append(amt * -1.0) # Money leaving pocket
            elif any(x in description for x in ["REDEMPTION", "SWITCH OUT", "STP OUT", "SWP"]):
                amounts.append(amt * 1.0)  # Money coming back
            else:
                # Fallback: assume Purchase if we aren't sure, or skip
                amounts.append(amt * -1.0)
                
            dates.append(dt)

        # 2. Append Current Valuation as "Value Today"
        dates.append(date.today())
        amounts.append(float(current_valuation))

        # 3. Calculate XIRR
        # pyxirr is very fast and robust
        result = xirr(dates, amounts)
        
        if result is None: return 0.0
        return result * 100 # Convert to percentage

    except Exception:
        return 0.0

def get_fund_rating(xirr_value):
    """Mock Rating Logic based on Returns"""
    if xirr_value >= 20.0:
        return "🔥 IN-FORM"
    elif 12.0 <= xirr_value < 20.0:
        return "✅ ON-TRACK"
    elif 0.0 < xirr_value < 12.0:
        return "⚠️ OFF-TRACK"
    else:
        return "❌ OUT-OF-FORM"

# --- MAIN UI ---

st.title("📈 TealScan Pro: Portfolio Health Engine")
st.markdown("""
**Comprehensive Analysis:** Commission Check • Asset Allocation • XIRR Performance • Fund Ratings
""")

# Sidebar for Input
with st.sidebar:
    st.header("📂 Data Input")
    uploaded_file = st.file_uploader("Upload CAMS/KFintech CAS (PDF)", type="pdf")
    password = st.text_input("PDF Password", type="password")
    
    st.info("ℹ️ Privacy Note: Analysis happens in your browser session. No data is stored.")

if uploaded_file and password:
    if st.button("🚀 Run Full Diagnosis"):
        try:
            with st.spinner("Initializing Deep Scan Engine (pdfminer)..."):
                # Save temp file
                with open("temp.pdf", "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # PARSE PDF
                # force_pdfminer=True is required for accurate split-table reading
                data = casparser.read_cas_pdf("temp.pdf", password, force_pdfminer=True)

                # --- AGGREGATION VARIABLES ---
                portfolio_data = []
                total_current_value = 0.0
                total_invested_approx = 0.0 # Hard to get exact without full history, but we try
                total_commission_loss = 0.0
                
                # --- PROCESSING LOOP ---
                progress_text = st.empty()
                
                for folio in data.folios:
                    for scheme in folio.schemes:
                        name = scheme.scheme
                        valuation = float(scheme.valuation.value or 0)
                        
                        # Skip zero balance funds for main view
                        if valuation < 100: continue
                        
                        # 1. Asset Class
                        category = get_asset_class(name)
                        
                        # 2. Commission Check
                        is_regular = "DIRECT" not in name.upper()
                        yearly_loss = valuation * 0.01 if is_regular else 0.0
                        total_commission_loss += yearly_loss
                        
                        # 3. XIRR Calculation
                        # We pass the transaction history list to the helper function
                        fund_xirr = calculate_fund_xirr(scheme.transactions, valuation)
                        
                        # 4. Rating
                        rating = get_fund_rating(fund_xirr)
                        
                        # Store Data
                        portfolio_data.append({
                            "Fund Name": name,
                            "Category": category,
                            "Value (₹)": valuation,
                            "Type": "Regular 🔴" if is_regular else "Direct 🟢",
                            "XIRR (%)": round(fund_xirr, 2),
                            "Rating": rating,
                            "Loss/Yr (₹)": round(yearly_loss, 0)
                        })
                        
                        total_current_value += valuation

                # --- DASHBOARD UI ---
                
                # Create DataFrame
                df = pd.DataFrame(portfolio_data)
                
                # SECTION 1: KEY METRICS
                st.divider()
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Portfolio Value", f"₹{total_current_value:,.0f}")
                
                # Calculate Weighted Avg XIRR (Approx) or just sum of loss
                m2.metric("Hidden Commissions / Year", f"₹{total_commission_loss:,.0f}", 
                          delta="- Savings Opportunity" if total_commission_loss > 0 else "Perfect",
                          delta_color="inverse")
                
                # Count "Out of Form" funds
                bad_funds_count = len(df[df['Rating'] == "❌ OUT-OF-FORM"])
                m3.metric("Funds 'Out-of-Form'", f"{bad_funds_count}", 
                          delta="Needs Review" if bad_funds_count > 0 else "All Good",
                          delta_color="inverse")

                # SECTION 2: ASSET ALLOCATION
                st.subheader("📊 Asset Allocation")
                if not df.empty:
                    # Group by Category
                    allocation = df.groupby("Category")["Value (₹)"].sum().reset_index()
                    
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.bar_chart(allocation, x="Category", y="Value (₹)", color="#2E86C1")
                    with c2:
                        st.dataframe(allocation, hide_index=True)

                # SECTION 3: FUND HEALTH REPORT
                st.subheader("🏥 Fund Health Card")
                
                # Styling the dataframe
                st.dataframe(
                    df,
                    column_config={
                        "Value (₹)": st.column_config.NumberColumn(format="₹%d"),
                        "XIRR (%)": st.column_config.NumberColumn(format="%.2f%%"),
                        "Loss/Yr (₹)": st.column_config.NumberColumn(format="₹%d"),
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # SECTION 4: ACTION PLAN
                st.subheader("⚡ Action Plan")
                if total_commission_loss > 0:
                    st.error(f"🛑 CRITICAL: Switch {len(df[df['Type'] == 'Regular 🔴'])} Regular funds to Direct Plans immediately.")
                
                if bad_funds_count > 0:
                    st.warning(f"⚠️ REVIEW: {bad_funds_count} funds are performing below 0% or low returns. Consider rebalancing.")
                    
                if total_commission_loss == 0 and bad_funds_count == 0:
                    st.success("✅ Your Portfolio is in excellent shape!")

        except Exception as e:
            st.error(f"❌ Error during analysis. Details: {e}")
