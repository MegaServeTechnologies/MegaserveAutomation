import streamlit as st
import pandas as pd
import uuid

# Streamlit page configuration
st.set_page_config(page_title="Algo UI Orderbook Analysis", layout="wide")

# Title and description
st.title("Algo UI Orderbook Analysis")
st.markdown("Upload an Algo UI Orderbook Excel file to analyze trades for specified user IDs.")

# User IDs
user_ids = ["7RA1RM61", "7RA1IL10", "7RA110119", "7RA110084","7RIK2014"]

# File uploader
uploaded_file = st.file_uploader("Upload Orderbook Excel File", type=["xlsx"])

def parse_col(s):
    return pd.to_datetime(s, errors="coerce", dayfirst=True)

def make_pairs(filtered: pd.DataFrame):
    pairs = []
    for sym, g in filtered.groupby("symbol", sort=False):
        buys, sells = [], []
        for row in g.sort_values("ts").itertuples(index=False):
            side, qty, price, ts = row.order_side, float(row.order_quantity), float(row.order_avg_price), row.ts
            if side == "BUY":
                while sells and qty > 0:
                    s = sells[0]
                    pair_qty = min(qty, s["qty"])
                    pairs.append({
                        "symbol": sym, "direction": "SELL→BUY",
                        "buy_time": ts, "buy_qty": pair_qty, "buy_avg_price": price,
                        "buy_value": price * pair_qty,
                        "sell_time": s["ts"], "sell_qty": pair_qty, "sell_avg_price": s["price"],
                        "sell_value": s["price"] * pair_qty,
                        "realised_value": (s["price"] * pair_qty) - (price * pair_qty),
                    })
                    qty -= pair_qty
                    s["qty"] -= pair_qty
                    if s["qty"] == 0: sells.pop(0)
                if qty > 0: buys.append({"qty": qty, "price": price, "ts": ts})
            else:  # SELL
                while buys and qty > 0:
                    b = buys[0]
                    pair_qty = min(qty, b["qty"])
                    pairs.append({
                        "symbol": sym, "direction": "BUY→SELL",
                        "buy_time": b["ts"], "buy_qty": pair_qty, "buy_avg_price": b["price"],
                        "buy_value": b["price"] * pair_qty,
                        "sell_time": ts, "sell_qty": pair_qty, "sell_avg_price": price,
                        "sell_value": price * pair_qty,
                        "realised_value": (price * pair_qty) - (b["price"] * pair_qty),
                    })
                    qty -= pair_qty
                    b["qty"] -= pair_qty
                    if b["qty"] == 0: buys.pop(0)
                if qty > 0: sells.append({"qty": qty, "price": price, "ts": ts})
    return pd.DataFrame(pairs)

if uploaded_file is not None:
    # Load and process the Excel file
    df = pd.read_excel(uploaded_file, dtype=str)

    # Build unified timestamp
    ts = pd.Series(pd.NaT, index=df.index)
    for col in ["order_generated_time", "exchange_transact_time", "_date"]:
        if col in df.columns:
            ts = ts.combine_first(parse_col(df[col]))
    df["ts"] = ts

    # Clean numerics and sides
    df["order_quantity"] = pd.to_numeric(df["order_quantity"], errors="coerce")
    df["order_avg_price"] = pd.to_numeric(df["order_avg_price"], errors="coerce")
    df["order_side"] = df["order_side"].str.upper().str.strip()

    # Rename trading symbol column
    sym_col = "traiding_symbol" if "traiding_symbol" in df.columns else "trading_symbol"
    df = df.rename(columns={sym_col: "symbol"})

    # Process each user ID
    for uid in user_ids:
        st.subheader(f"Pivot Summary for User ID: {uid}")
        
        user_df = df[
            (df["user_id"] == uid) &
            (df["order_status"] == "COMPLETE") &
            (df["order_side"].isin(["BUY", "SELL"])) &
            (~df["ts"].isna())
        ].copy()

        if user_df.empty:
            st.warning(f"No trades found for {uid}")
            continue

        pairs_df = make_pairs(user_df)

        if pairs_df.empty:
            st.warning(f"No complete transitions for {uid}")
            continue

        # Create pivot table
        pivot = pairs_df.groupby("symbol", as_index=False).agg(
            completed_transitions=("symbol", "count"),
            total_buy_value=("buy_value", "sum"),
            total_sell_value=("sell_value", "sum"),
            total_realised_value=("realised_value", "sum")
        )

        # Add grand total
        grand_total = pd.DataFrame([{
            "symbol": "Grand Total",
            "completed_transitions": pivot["completed_transitions"].sum(),
            "total_buy_value": pivot["total_buy_value"].sum(),
            "total_sell_value": pivot["total_sell_value"].sum(),
            "total_realised_value": pivot["total_realised_value"].sum()
        }])
        pivot = pd.concat([pivot, grand_total], ignore_index=True)

        # Display pivot table
        st.dataframe(
            pivot.style.format({
                "total_buy_value": "₹{:,.2f}",
                "total_sell_value": "₹{:,.2f}",
                "total_realised_value": "₹{:,.2f}"
            }),
            use_container_width=True
        )
else:

    st.info("Please upload an Excel file to begin analysis.")
