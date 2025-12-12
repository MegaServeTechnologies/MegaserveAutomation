import streamlit as st
import pandas as pd
import numpy as np
import re
import base64
from io import BytesIO
import logging
import openpyxl
from openpyxl.styles import Alignment, Border, Side, Font
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check Streamlit version for compatibility
try:
    import streamlit
    logger.info(f"Streamlit version: {streamlit.__version__}")
except ImportError:
    st.error("Streamlit is not installed. Please install it using `pip install streamlit`.")
    st.stop()


# ===================== MAIN RUN FUNCTION =====================
def run():
    # ===================== CUSTOM CSS & STYLING =====================
    st.markdown("""
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <style>
    body {
        font-family: 'Inter', sans-serif;
        background: linear-gradient(135deg, #f3f4f6, #e5e7eb);
    }
    .stButton>button {
        background: linear-gradient(45deg, #3b82f6, #60a5fa);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 0.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover {
        background: linear-gradient(45deg, #2563eb, #3b82f6);
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
    .stDateInput input {
        border: 2px solid #3b82f6;
        border-radius: 0.5rem;
        padding: 0.5rem;
        background: #ffffff;
        color: #1f2937;
        font-size: 1rem;
        transition: all 0.3s ease;
    }
    .stDateInput input:focus {
        outline: none;
        border-color: #2563eb;
        box-shadow: 0 0 8px rgba(59, 130, 246, 0.5);
        background: #f8fafc;
    }
    .stFileUploader button {
        background: linear-gradient(45deg, #10b981, #34d399);
        color: white;
        border-radius: 0.5rem;
        padding: 0.75rem;
    }
    .stFileUploader button:hover {
        background: linear-gradient(45deg, #059669, #10b981);
    }
    .stCheckbox label {
        font-size: 1rem;
        color: #1f2937;
    }
    .metric-card {
        background: #ffffff;
        padding: 1.5rem;
        border-radius: 0.75rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
        transition: transform 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    .metric-label {
        font-size: 1.1rem;
        color: #6b7280;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 1.1rem;
        font-weight: 600;
        padding: 0.75rem 1.5rem;
        border-radius: 0.5rem;
        transition: all 0.3s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: #e5e7eb;
    }
    .insights-box {
        background: #ffffff;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-top: 1.5rem;
    }
    .chart-container {
        background: #ffffff;
        padding: 1.5rem;
        border-radius: 0.75rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 1.5rem;
    }
    .header-text {
        font-size: 2.25rem;
        font-weight: 800;
        color: #1f2937;
        text-align: center;
        margin-bottom: 1rem;
    }
    .subheader-text {
        font-size: 1.25rem;
        color: #4b5563;
        text-align: center;
        margin-bottom: 2rem;
    }
    footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

    # ===================== ALL FUNCTIONS FIRST (EXACT SAME) =====================

    def process_portfolio_data(gridlog_file, summary_file):
        if gridlog_file.name.endswith('.csv'):
            df_grid = pd.read_csv(gridlog_file)
        elif gridlog_file.name.endswith('.xlsx'):
            df_grid = pd.read_excel(gridlog_file)
        else:
            raise ValueError("Unsupported GridLog file type. Use CSV or Excel.")

        df_grid.columns = df_grid.columns.str.strip()

        mask = df_grid['Message'].str.contains(r'Combined SL:|Combined trail target:', case=False, na=False)
        filtered_grid = df_grid.loc[mask, ['Message', 'Option Portfolio', 'Timestamp']].dropna(subset=['Option Portfolio'])

        filtered_grid['MessageType'] = filtered_grid['Message'].str.extract(r'(Combined SL|Combined trail target)', flags=re.IGNORECASE)
        duplicate_mask = filtered_grid.duplicated(subset=['Option Portfolio', 'MessageType'], keep=False)
        filtered_grid = filtered_grid[duplicate_mask]

        summary_grid = (
            filtered_grid.groupby('Option Portfolio').agg({
                'Message': lambda x: ', '.join(x.unique()),
                'Timestamp': 'max'
            }).reset_index()
            .rename(columns={'Message': 'Reason', 'Timestamp': 'Time'})
        )

        xl = pd.ExcelFile(summary_file)
        summary_list = []

        for sheet_name in xl.sheet_names:
            if "legs" in sheet_name.lower():
                df_leg = xl.parse(sheet_name)
                df_leg.columns = df_leg.columns.str.strip()

                if {'Exit Type', 'Portfolio Name', 'Exit Time'}.issubset(df_leg.columns):
                    onsqoff_df = df_leg[df_leg['Exit Type'].astype(str).str.strip() == 'OnSqOffTime']
                    if not onsqoff_df.empty:
                        grouped = onsqoff_df.groupby('Portfolio Name')['Exit Time'].max().reset_index()
                        for _, row in grouped.iterrows():
                            summary_list.append({
                                'Option Portfolio': row['Portfolio Name'],
                                'Reason': 'OnSqOffTime',
                                'Time': row['Exit Time']
                            })

        summary_summary = pd.DataFrame(summary_list)
        final_df = pd.concat([summary_grid, summary_summary], ignore_index=True)
        final_df = final_df.groupby('Option Portfolio').agg({
            'Reason': lambda x: ', '.join(sorted(set(x))),
            'Time': 'last'
        }).reset_index()

        completed_list = []
        grid_portfolios = df_grid['Option Portfolio'].dropna().unique()

        for sheet_name in xl.sheet_names:
            if "legs" in sheet_name.lower():
                df_leg = xl.parse(sheet_name)
                df_leg.columns = df_leg.columns.str.strip()

                if 'Portfolio Name' in df_leg.columns and 'Status' in df_leg.columns:
                    for portfolio, group in df_leg.groupby('Portfolio Name'):
                        if (portfolio not in final_df['Option Portfolio'].values 
                            and portfolio in grid_portfolios):
                            statuses = group['Status'].astype(str).str.strip().unique()
                            if len(statuses) == 1 and statuses[0].lower() == 'completed':
                                reason_text = 'AllLegsCompleted'
                                exit_time_to_use = None
                                if 'Exit Time' in group.columns:
                                    for exit_time, exit_type in zip(group['Exit Time'], group.get('Exit Type', [])):
                                        if pd.isna(exit_time):
                                            continue
                                        normalized_exit_time = str(exit_time).replace('.', ':').strip()
                                        matching_rows = df_grid[
                                            (df_grid['Option Portfolio'] == portfolio) &
                                            (df_grid['Timestamp'].astype(str).str.contains(normalized_exit_time))
                                        ]
                                        if not matching_rows.empty:
                                            reason_text += f", {exit_type.strip()}"
                                            exit_time_to_use = exit_time
                                            break
                                completed_list.append({
                                    'Option Portfolio': portfolio,
                                    'Reason': reason_text,
                                    'Time': exit_time_to_use
                                })

        if completed_list:
            completed_df = pd.DataFrame(completed_list)
            final_df = pd.concat([final_df, completed_df], ignore_index=True)

        def clean_reason(text):
            if pd.isna(text):
                return text
            text = str(text)
            match = re.search(r'(Combined SL: [^ ]+ hit|Combined Trail Target: [^ ]+ hit)', text, re.IGNORECASE)
            if match:
                return match.group(1)
            if 'AllLegsCompleted' in text:
                text = text.replace('AllLegsCompleted,', '').replace('AllLegsCompleted', '').strip()
            return text.strip()

        final_df['Reason'] = final_df['Reason'].apply(clean_reason)

        filename = gridlog_file.name
        match = re.search(r'(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})', filename)
        if match:
            raw_date = match.group(1)
            parts = raw_date.split()
            formatted_date = f"{parts[0]} {parts[1].lower()}"
        else:
            formatted_date = "unknown_date"
        output_filename = f"completed portfolio of {formatted_date}.csv"

        final_df['Time'] = final_df['Time'].astype(str).str.strip().replace('nan', None)
        return final_df, output_filename

    def process_data(df, nfo_bhav_file, bfo_bhav_file, expiry_nfo, expiry_bfo,
                     include_settlement_nfo, include_settlement_bfo):
        logger.info("Starting PNL data processing")
        try:
            required_columns = ['Exchange', 'Symbol', 'Net Qty', 'Buy Avg Price', 'Sell Avg Price',
                                'Sell Qty', 'Buy Qty', 'Realized Profit', 'Unrealized Profit']
            missing = [c for c in required_columns if c not in df.columns]
            if missing:
                raise ValueError(f"Missing columns: {missing}")

            mask = df["Exchange"].isin(["NFO", "BFO"])
            df.loc[mask, "Symbol"] = df.loc[mask, "Symbol"].astype(str).str[-5:] + df.loc[mask, "Symbol"].astype(str).str[-8:-6]

            df_nfo = df[df["Exchange"] == "NFO"].copy()
            df_bfo = df[df["Exchange"] == "BFO"].copy()

            total_realized_nfo = total_realized_bfo = 0
            total_settlement_nfo = total_settlement_bfo = 0

            cond_nfo = [df_nfo["Net Qty"] == 0, df_nfo["Net Qty"] > 0, df_nfo["Net Qty"] < 0]
            choice_nfo = [
                (df_nfo["Sell Avg Price"] - df_nfo["Buy Avg Price"]) * df_nfo["Sell Qty"],
                (df_nfo["Sell Avg Price"] - df_nfo["Buy Avg Price"]) * df_nfo["Sell Qty"],
                (df_nfo["Sell Avg Price"] - df_nfo["Buy Avg Price"]) * df_nfo["Buy Qty"]
            ]
            df_nfo["Calculated_Realized_PNL"] = np.select(cond_nfo, choice_nfo, default=0)
            total_realized_nfo = df_nfo["Calculated_Realized_PNL"].fillna(0).sum()

            cond_bfo = [df_bfo["Net Qty"] == 0, df_bfo["Net Qty"] > 0, df_bfo["Net Qty"] < 0]
            choice_bfo = [
                (df_bfo["Sell Avg Price"] - df_bfo["Buy Avg Price"]) * df_bfo["Sell Qty"],
                (df_bfo["Sell Avg Price"] - df_bfo["Buy Avg Price"]) * df_bfo["Sell Qty"],
                (df_bfo["Sell Avg Price"] - df_bfo["Buy Avg Price"]) * df_bfo["Buy Qty"]
            ]
            df_bfo["Calculated_Realized_PNL"] = np.select(cond_bfo, choice_bfo, default=0)
            total_realized_bfo = df_bfo["Calculated_Realized_PNL"].fillna(0).sum()

            if include_settlement_nfo and nfo_bhav_file:
                df_bhav_nfo = pd.read_csv(nfo_bhav_file)
                df_bhav_nfo["Date"] = df_bhav_nfo["CONTRACT_D"].str.extract(r'(\d{2}-[A-Z]{3}-\d{4})')
                df_bhav_nfo["Symbol"] = df_bhav_nfo["CONTRACT_D"].str.extract(r'^(.*?)(\d{2}-[A-Z]{3}-\d{4})')[0]
                df_bhav_nfo["Strike_Type"] = df_bhav_nfo["CONTRACT_D"].str.extract(r'(PE\d+|CE\d+)$')
                df_bhav_nfo["Date"] = pd.to_datetime(df_bhav_nfo["Date"], format="%d-%b-%Y")
                df_bhav_nfo["Strike_Type"] = df_bhav_nfo["Strike_Type"].str.replace(r'^(PE|CE)(\d+)$', r'\2\1', regex=True)
                df_bhav_nfo = df_bhav_nfo[(df_bhav_nfo["Date"] == pd.to_datetime(expiry_nfo)) & (df_bhav_nfo["Symbol"] == "OPTIDXNIFTY")]
                df_nfo["Strike_Type"] = df_nfo["Symbol"].str.extract(r'(\d+[A-Z]{2})$')
                df_nfo = df_nfo.merge(df_bhav_nfo[["Strike_Type", "SETTLEMENT"]], on="Strike_Type", how="left")
                df_nfo["Calculated_Settlement_PNL"] = np.select(
                    [df_nfo["Net Qty"] > 0, df_nfo["Net Qty"] < 0],
                    [(df_nfo["SETTLEMENT"] - df_nfo["Buy Avg Price"]) * abs(df_nfo["Net Qty"]),
                     (df_nfo["Sell Avg Price"] - df_nfo["SETTLEMENT"]) * abs(df_nfo["Net Qty"])],
                    default=0)
                total_settlement_nfo = df_nfo["Calculated_Settlement_PNL"].fillna(0).sum()

            if include_settlement_bfo and bfo_bhav_file:
                df_bhav_bfo = pd.read_csv(bfo_bhav_file)
                df_bhav_bfo["Expiry Date"] = pd.to_datetime(df_bhav_bfo["Expiry Date"], format="%d %b %Y", errors="coerce")
                df_bhav_bfo = df_bhav_bfo[df_bhav_bfo["Expiry Date"] == pd.to_datetime(expiry_bfo)]
                df_bhav_bfo["Symbols"] = df_bhav_bfo["Series Code"].astype(str).str[-7:]
                mapping = df_bhav_bfo.drop_duplicates("Symbols").set_index("Symbols")["Close Price"]
                df_bfo["Close Price"] = df_bfo["Symbol"].astype(str).str.strip().map(mapping)
                df_bfo["Calculated_Settlement_PNL"] = 0
                df_bfo.loc[df_bfo["Net Qty"] > 0, "Calculated_Settlement_PNL"] = (df_bfo["Close Price"] - df_bfo["Buy Avg Price"]) * df_bfo["Net Qty"].abs()
                df_bfo.loc[df_bfo["Net Qty"] < 0, "Calculated_Settlement_PNL"] = (df_bfo["Sell Avg Price"] - df_bfo["Close Price"]) * df_bfo["Net Qty"].abs()
                total_settlement_bfo = df_bfo["Calculated_Settlement_PNL"].fillna(0).sum()

            overall_realized = total_realized_nfo + total_realized_bfo
            overall_settlement = total_settlement_nfo + total_settlement_bfo
            grand_total = overall_realized + overall_settlement

            return {
                "total_realized_nfo": total_realized_nfo,
                "total_settlement_nfo": total_settlement_nfo,
                "total_realized_bfo": total_realized_bfo,
                "total_settlement_bfo": total_settlement_bfo,
                "overall_realized": overall_realized,
                "overall_settlement": overall_settlement,
                "grand_total": grand_total
            }
        except Exception as e:
            logger.error(f"Error in process_data: {e}")
            raise

    def get_excel_download_link(df, filename):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='PNL Data')
            ws = writer.sheets['PNL Data']
            for row in ws.rows:
                for cell in row:
                    cell.alignment = Alignment(horizontal='center')
                    cell.border = Border(left=Side(style='thin'), right=Side(style='thin'),
                                         top=Side(style='thin'), bottom=Side(style='thin'))
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = openpyxl.styles.PatternFill(start_color="4F81BD", fill_type="solid")
        b64 = base64.b64encode(output.getvalue()).decode()
        return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}.xlsx">Download {filename}.xlsx</a>'

    def get_csv_download_link(df, filename):
        csv = df.to_csv(index=False).encode()
        b64 = base64.b64encode(csv).decode()
        return f'<a href="data:text/csv;base64,{b64}" download="{filename}">Download {filename}</a>'

    # ===================== TABS =====================
    tab1, tab2 = st.tabs(["Full PNL Calculation", "Portfolio Exit Analysis"])

   # ===================== TAB 1: PNL CALCULATION =====================
    with tab1:
        st.markdown('<h1 class="header-text">A19 Realized & Settlement Calculator</h1>', unsafe_allow_html=True)
        st.markdown('<p class="subheader-text">Calculate the Realized P&L & Settlement Value for every index of A19</p>', unsafe_allow_html=True)
       
        st.markdown('<h2 class="text-lg font-bold text-gray-800 dark:text-gray-200 mb-4">Upload Data</h2>', unsafe_allow_html=True)
        with st.container():
            positions_file = st.file_uploader("Positions CSV", type="csv", help="Upload VS20 22 AUG 2025 POSITIONS(EOD).csv", key=("positions_upload"))
            selected_user = None
            if positions_file:
                if 'positions_df' not in st.session_state or st.session_state.get('positions_file_name') != positions_file.name:
                    st.session_state.positions_df = pd.read_csv(positions_file)
                    st.session_state.positions_file_name = positions_file.name
                df = st.session_state.positions_df
                if 'UserID' in df.columns:
                    users = sorted(df['UserID'].unique().tolist())
                    selected_user = st.selectbox("Select User", users, key="selected_user")
                else:
                    st.error("'UserID' column not found in positions file.")
           
            checkbox_col1, checkbox_col2 = st.columns(2)
            with checkbox_col1:
                include_settlement_nfo = st.checkbox("Include Settlement PNL for NFO", value=True, key="nfo_settlement")
            with checkbox_col2:
                include_settlement_bfo = st.checkbox("Include Settlement PNL for BFO", value=True, key="bfo_settlement")
           
            col1, col2 = st.columns(2)
            with col1:
                nfo_bhav_file = st.file_uploader("NFO Bhavcopy", type="csv", key="nfo_upload") if include_settlement_nfo else None
                if not include_settlement_nfo:
                    st.info("NFO Bhavcopy not required when settlement PNL for NFO is disabled.")
            with col2:
                bfo_bhav_file = st.file_uploader("BFO Bhavcopy", type="csv", key="bfo_upload") if include_settlement_bfo else None
                if not include_settlement_bfo:
                    st.info("BFO Bhavcopy not required when settlement PNL for BFO is disabled.")
           
            st.markdown('<h2 class="text-lg font-bold text-gray-800 dark:text-gray-200 mb-4">Expiry Dates</h2>', unsafe_allow_html=True)
            col3, col4 = st.columns(2)
            with col3:
                expiry_nfo = st.date_input("NFO Expiry Date", value=datetime.now().date(), key="nfo_expiry", disabled=not include_settlement_nfo)
            with col4:
                expiry_bfo = st.date_input("BFO Expiry Date", value=datetime.now().date(), key="bfo_expiry", disabled=not include_settlement_bfo)
           
            process_button = st.button("Process Data", key="process_button")

            if process_button:
                if positions_file and selected_user:
                    if (include_settlement_nfo and not nfo_bhav_file) or (include_settlement_bfo and not bfo_bhav_file):
                        st.error("Please upload all required files.")
                    else:
                        try:
                            with st.spinner("Processing PNL..."):
                                filtered_df = st.session_state.positions_df[st.session_state.positions_df['UserID'] == selected_user]
                                results = process_data(
                                    filtered_df, nfo_bhav_file, bfo_bhav_file,
                                    expiry_nfo, expiry_bfo,
                                    include_settlement_nfo, include_settlement_bfo
                                )

                            st.success("PNL processed successfully!")

                            # ==================== DISPLAY RESULTS WITH METRIC CARDS ====================
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.markdown(f"""
                                <div class="metric-card">
                                    <div class="metric-label">NFO Realized PNL</div>
                                    <div class="metric-value" style="color: {'#10b981' if results['total_realized_nfo'] >= 0 else '#ef4444'}">
                                        ₹{results['total_realized_nfo']:,.2f}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            with col2:
                                st.markdown(f"""
                                <div class="metric-card">
                                    <div class="metric-label">NFO Settlement PNL</div>
                                    <div class="metric-value" style="color: {'#10b981' if results['total_settlement_nfo'] >= 0 else '#ef4444'}">
                                        ₹{results['total_settlement_nfo']:,.2f}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            with col3:
                                st.markdown(f"""
                                <div class="metric-card">
                                    <div class="metric-label">BFO Realized PNL</div>
                                    <div class="metric-value" style="color: {'#10b981' if results['total_realized_bfo'] >= 0 else '#ef4444'}">
                                        ₹{results['total_realized_bfo']:,.2f}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            with col4:
                                st.markdown(f"""
                                <div class="metric-card">
                                    <div class="metric-label">BFO Settlement PNL</div>
                                    <div class="metric-value" style="color: {'#10b981' if results['total_settlement_bfo'] >= 0 else '#ef4444'}">
                                        ₹{results['total_settlement_bfo']:,.2f}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                            # Overall Summary
                            st.markdown("### Overall Summary")
                            colA, colB, colC = st.columns(3)
                            with colA:
                                st.markdown(f"""
                                <div class="metric-card">
                                    <div class="metric-label">Total Realized PNL</div>
                                    <div class="metric-value" style="color: {'#10b981' if results['overall_realized'] >= 0 else '#ef4444'}; font-size: 2rem;">
                                        ₹{results['overall_realized']:,.2f}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            with colB:
                                st.markdown(f"""
                                <div class="metric-card">
                                    <div class="metric-label">Total Settlement PNL</div>
                                    <div class="metric-value" style="color: {'#10b981' if results['overall_settlement'] >= 0 else '#ef4444'}; font-size: 2rem;">
                                        ₹{results['overall_settlement']:,.2f}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            with colC:
                                st.markdown(f"""
                                <div class="metric-card">
                                    <div class="metric-label">Grand Total PNL</div>
                                    <div class="metric-value" style="color: {'#10b981' if results['grand_total'] >= 0 else '#ef4444'}; font-size: 2.5rem;">
                                        ₹{results['grand_total']:,.2f}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                            # ==================== DOWNLOAD FILTERED DATA ====================
                            st.markdown("### Download Processed Positions Data")
                            download_df = filtered_df.copy()
                            csv_link = get_csv_download_link(download_df, f"PNL_{selected_user}_{datetime.now().strftime('%Y%m%d')}.csv")
                            excel_link = get_excel_download_link(download_df, f"PNL_{selected_user}_{datetime.now().strftime('%Y%m%d')}")

                            col_d1, col_d2 = st.columns(2)
                            with col_d1:
                                st.markdown(csv_link, unsafe_allow_html=True)
                            with col_d2:
                                st.markdown(excel_link, unsafe_allow_html=True)

                        except Exception as e:
                            st.error(f"Error during processing: {e}")
                            logger.error(f"Processing error: {e}", exc_info=True)
                else:
                    st.error("Please upload positions file and select a user.")

        # ===================== ALL USERS SUMMARY (B2: file-only, pointer resets) =====================
        # This section runs ONLY after process_button click and only if positions_file exists
        if process_button and positions_file:
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown("## All Users Realized & Settlement Summary")

            df_all = st.session_state.positions_df

            # Make sure UserID exists
            if 'UserID' not in df_all.columns:
                st.error("'UserID' column missing in positions file — cannot build summary.")
            else:
                users = df_all['UserID'].unique()
                summary_rows = []

                # Check bhavcopy requirements BEFORE looping
                if include_settlement_nfo and not nfo_bhav_file:
                    st.error("NFO settlement is enabled but NFO Bhavcopy file was not uploaded.")
                elif include_settlement_bfo and not bfo_bhav_file:
                    st.error("BFO settlement is enabled but BFO Bhavcopy file was not uploaded.")
                else:
                    for user in users:
                        temp_df = df_all[df_all["UserID"] == user].copy()

                        # RESET pointer before EACH read (critical for B2)
                        try:
                            if include_settlement_nfo and nfo_bhav_file:
                                nfo_bhav_file.seek(0)
                        except Exception:
                            pass

                        try:
                            if include_settlement_bfo and bfo_bhav_file:
                                bfo_bhav_file.seek(0)
                        except Exception:
                            pass

                        # Now safely call process_data()
                        try:
                            results = process_data(
                                temp_df,
                                nfo_bhav_file if include_settlement_nfo else None,
                                bfo_bhav_file if include_settlement_bfo else None,
                                expiry_nfo,
                                expiry_bfo,
                                include_settlement_nfo,
                                include_settlement_bfo
                            )
                        except Exception as e:
                            st.error(f"Error while calculating summary for user {user}: {e}")
                            # continue to next user (don't break entire summary)
                            continue

                        summary_rows.append({
                            "UserID": user,
                            "NFO Realized": results.get("total_realized_nfo", 0),
                            "NFO Settlement": results.get("total_settlement_nfo", 0),
                            "BFO Realized": results.get("total_realized_bfo", 0),
                            "BFO Settlement": results.get("total_settlement_bfo", 0),
                            "Total Realized": results.get("overall_realized", 0),
                            "Total Settlement": results.get("overall_settlement", 0),
                            "Grand Total": results.get("grand_total", 0)
                        })

                    # Build DataFrame
                    summary_df = pd.DataFrame(summary_rows)
                    st.dataframe(summary_df)

                    # ====== EXCEL DOWNLOAD ======
                    output = BytesIO()
                    filename = f"A19_Realized&settlement_PNL_{datetime.now().strftime('%Y%m%d')}.xlsx"

                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        summary_df.to_excel(writer, index=False, sheet_name='Summary')

                    b64 = base64.b64encode(output.getvalue()).decode()
                    download_link = (
                        f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" '
                        f'download="{filename}">📥 Download All Users Summary Excel</a>'
                    )

                    st.markdown(download_link, unsafe_allow_html=True)

    # ===================== TAB 2: PORTFOLIO ANALYSIS =====================
    with tab2:
        st.markdown('<hr class="my-8 border-gray-300">', unsafe_allow_html=True)
        st.markdown('<h1 class="header-text">Portfolio Analysis</h1>', unsafe_allow_html=True)
        st.markdown('<p class="subheader-text">Upload GridLog and Summary files to analyze portfolio exit reasons and timestamps.</p>', unsafe_allow_html=True)
        st.info("Upload the required files below and click 'Process Portfolio Data' to view results.")
        st.markdown('<h2 class="text-lg font-bold text-gray-800 dark:text-gray-200 mb-4">Upload Portfolio Data</h2>', unsafe_allow_html=True)
        
        col_grid, col_summary = st.columns(2)
        with col_grid:
            gridlog_file = st.file_uploader("GridLog File", type=["csv", "xlsx"], key="gridlog_upload")
        with col_summary:
            summary_file = st.file_uploader("Summary Excel File", type="xlsx", key="summary_upload")
        
        if st.button("Process Portfolio Data", key="process_portfolio_button"):
            if gridlog_file and summary_file:
                try:
                    with st.spinner("Processing portfolio data..."):
                        final_df, output_filename = process_portfolio_data(gridlog_file, summary_file)
                    st.success("Done!")
                    st.write(final_df)
                    st.markdown(get_csv_download_link(final_df, output_filename), unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("Please upload both files.")

# ===================== AUTO CALL run() =====================
if __name__ == "__main__":
    st.write(f"DEBUG: Starting app at {datetime.now()}")
    run()

