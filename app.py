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
    """Broad Asset Class (Equity vs Debt)"""
    name = fund_name.upper()
    if any(x in name for x in ["LIQUID", "OVERNIGHT", "BOND", "DEBT", "GILT", "TREASURY"]):
        return "Debt"
    elif any(x in name for x in ["GOLD", "SILVER", "COMMODITIES"]):
        return "Commodity"
    elif any(x in name for x in ["HYBRID", "BALANCED", "DYNAMIC"]):
        return "Hybrid"
    else:
        return "Equity"

def get_detailed_category(fund_name):
    """Specific Category for Overlap Checks"""
    name = fund_name.upper()
    if "SMALL CAP" in name: return "Small Cap"
    if "MID CAP" in name: return "Mid Cap"
    if "LARGE" in name and "MID" in name: return "Large & Mid Cap"
    if "LARGE CAP" in name: return "Large Cap"
    if "FLEXI" in name: return "Flexi Cap"
    if "ELSS" in name or "TAX SAVER" in name: return "ELSS (Tax Saver)"
    if "INDEX" in name: return "Index Fund"
    if "MULTI" in name: return "Multi Cap"
    if "VALUE" in name: return "Value Fund"
    return "Other Equity"

def calculate_metrics(scheme):
    """
    Smart calculation that handles 'Partial Data' gracefully.
    Returns: (XIRR, Absolute_Return, Status_Message)
    """
    transactions = scheme.transactions
    current_val = float(scheme.valuation.value or 0)
    total_cost = float(scheme.valuation.cost or 0)
    
    # 1. Calculate Absolute Return
    abs_return = 0.0
    if total_cost > 0:
        abs_return = ((current_val - total_cost) / total_cost) * 100

    # 2. Check for "No Transaction" Case
    if not transactions:
        return None, abs_return, "No History"

    # 3. Try XIRR Calculation
    dates = []
    amounts = []
    
    try:
        # Check for Partial Data (Opening Balance Mismatch)
        invested_sum = sum([float(t.amount) for t in transactions if t.amount])
        if invested_sum > 0 and (current_val / invested_sum) > 5.0 and total_cost > invested_sum:
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
        
        # Sanity Check
        if xirr_val > 100.0 or xirr_val < -90.0:
             return None, abs_return, "Data Mismatch"
             
        return xirr_val, abs_return, "OK"

    except Exception:
        return None, abs_return, "Error"

def get_fund_rating(xirr_val, abs_val):
    """Rating Logic with Fallback"""
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

# --- INPUT SECTION ---
st.subheader("📂 Step 1: Upload Data")
st.info("💡 For accurate XIRR, please upload a **'Since Inception'** CAS PDF.")
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
                total_commission_loss = 0.0
                
                for folio in data.folios:
                    for scheme in folio.schemes:
                        name = scheme.scheme
                        valuation = float(scheme.valuation.value or 0)
                        cost = float(scheme.valuation.cost or 0)
                        
                        if valuation < 100: continue
                        
                        # Classifications
                        asset_class = get_asset_class(name)
                        detailed_cat = get_detailed_category(name)
                        is_regular = "DIRECT" not in name.upper()
                        
                        # Metrics
                        my_xirr, my_abs, status = calculate_metrics(scheme)
                        rating = get_fund_rating(my_xirr, my_abs)
                        
                        # Commission Loss
                        loss = valuation * 0.01 if is_regular else 0.0
                        total_commission_loss += loss

                        portfolio_data.append({
                            "Fund Name": name,
                            "Category": asset_class,
                            "Sub-Category": detailed_cat,
                            "Value": valuation,
                            "Invested": cost,
                            "Type": "Regular 🔴" if is_regular else "Direct 🟢",
                            "XIRR": f"{my_xirr:.2f}%" if my_xirr is not None else "N/A",
                            "Abs Return": f"{my_abs:.2f}%",
                            "Rating": rating,
                            "Status": status
                        })
                        
                        total_curr += valuation
                        total_invested += cost

                # --- DASHBOARD ---
                df = pd.DataFrame(portfolio_data)
                
                # 1. SUMMARY METRICS
                st.divider()
                st.subheader("📊 Portfolio Summary")
                
                total_gain = total_curr - total_invested
                total_gain_pct = (total_gain / total_invested * 100) if total_invested > 0 else 0
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Value", f"₹{total_curr:,.0f}")
                m2.metric("Total Invested", f"₹{total_invested:,.0f}")
                m3.metric("Overall Gain", f"₹{total_gain:,.0f}", f"{total_gain_pct:.1f}%")
                m4.metric("Commission Loss", f"₹{total_commission_loss:,.0f}", 
                          delta="Perfect" if total_commission_loss == 0 else "Switch & Save",
                          delta_color="inverse")

                # 2. CONCENTRATION & ALLOCATION (Restored)
                st.divider()
                c1, c2 = st.columns(2)
                
                with c1:
                    st.subheader("🍰 Asset Allocation")
                    if not df.empty:
                        alloc = df.groupby("Category")["Value"].sum().reset_index()
                        st.bar_chart(alloc, x="Category", y="Value", color="#2E86C1")
                
                with c2:
                    st.subheader("🔍 Concentration Analysis")
                    if not df.empty:
                        # Breakdown by Specific Category (Small vs Mid vs Large)
                        conc = df.groupby("Sub-Category")["Value"].sum().reset_index()
                        st.bar_chart(conc, x="Sub-Category", y="Value", color="#E67E22")

                # 3. HEALTH CARD
                st.divider()
                st.subheader("🏥 Fund Health Card")
                st.caption("Note: 'N/A' XIRR indicates partial history in PDF. Rating uses Absolute Return in that case.")
                
                st.dataframe(
                    df,
                    column_config={
                        "Value": st.column_config.NumberColumn(format="₹%d"),
                        "Invested": st.column_config.NumberColumn(format="₹%d"),
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # 4. ACTION PLAN (Restored)
                st.divider()
                st.subheader("⚡ Action Plan")
                
                # Check 1: Commissions
                if total_commission_loss > 0:
                    regular_count = len(df[df['Type'].str.contains("Regular")])
                    st.error(f"🛑 **Commissions:** Switch {regular_count} 'Regular' funds to Direct Plans to save ₹{total_commission_loss:,.0f}/year.")
                else:
                    st.success("✅ **Commissions:** Zero! You are in 100% Direct Plans.")
                
                # Check 2: Overlap / Concentration
                # Count funds per sub-category
                cat_counts = df['Sub-Category'].value_counts()
                risky_cats = cat_counts[cat_counts > 2]
                
                if not risky_cats.empty:
                    for cat, count in risky_cats.items():
                        st.warning(f"⚠️ **Concentration Risk:** You have {count} funds in '{cat}'. This causes high overlap. Consider reducing to 1-2 funds.")
                else:
                    st.info("✅ **Diversification:** Good balance. No category is overcrowded.")

        except Exception as e:
            st.error(f"❌ Error during analysis. Details: {e}")
