import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# ✅ Load Google Sheets credentials with correct OAuth scopes
if "GOOGLE_SHEETS_CREDENTIALS" in st.secrets:
    creds = Credentials.from_service_account_info(
        st.secrets["GOOGLE_SHEETS_CREDENTIALS"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    client = gspread.authorize(creds)
else:
    st.error("Missing GOOGLE_SHEETS_CREDENTIALS secret. Please check Streamlit settings.")

# ✅ Google Sheets setup
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/14-snTxdOwetRBpARaD0tTZk-i53DdYWOeKmcgpaaL6I"
spreadsheet = client.open_by_url(SPREADSHEET_URL)
bookings_ws = spreadsheet.worksheet("Bookings Raw Data")
lineup_ws = spreadsheet.worksheet("4DPLEX Lineup Clean")

# ✅ Convert to DataFrame
bookings_df = pd.DataFrame(bookings_ws.get_all_records())
lineup_df = pd.DataFrame(lineup_ws.get_all_records())

# ✅ Standardize column names
bookings_df.columns = bookings_df.columns.str.strip().str.replace(" ", "_").str.replace("\n", "_")
lineup_df.columns = lineup_df.columns.str.strip().str.replace(" ", "_").str.replace("\n", "_")

# ✅ Convert First_Release to datetime & Filter only relevant 2025 titles
lineup_df["First_Release"] = pd.to_datetime(lineup_df["First_Release"], errors='coerce')

# ---- Streamlit Web App ----
st.set_page_config(page_title="Exhibitor 2025 Lineup", layout="wide")

# ---- UI Styling ----
st.markdown(
    """
    <style>
    body { background-color: white; color: black; text-align: center; font-size:11px }
    .dataframe-container { display: flex; justify-content: center; align-items: start; gap: 8px; }
    .dataframe-container div { flex: 1; min-width: 100%; max-width: 100%; }
    .logo-container { display: flex; justify-content: center; align-items: center; margin-bottom: 5px; }
    .logo-container img { height: 80px; margin: 0 10px; }
    .small-logo { height: 25px !important; }
    .section-title { font-size: 24px; margin-top: 30px; font-weight: bold; color: #C04000; }
    .small-title { font-size: 14px; margin-top: 5px; margin-bottom: 10px; color: black; }
    .login-message { font-size:12px; font-weight: bold; color: black; text-transform: uppercase; margin-bottom: 10px; }
    </style>
    """,
    unsafe_allow_html=True
)

# ---- Logo Header ----
st.markdown(
    """
    <div class="logo-container">
        <img src="https://i.namu.wiki/i/8psG2mipUQg9PIedyoa4039el6UHQbl9t3_DsCHHu-5vBFswdbchE_zNQ5XtB7i4KjiJMnNvN8hTU47L1yL1DA_3Mmu9Qd7lu5mCoZ5gubhH8n2RbGZTBfq1d0MCvwhR-066Z06iVn3D0b7XZcbbYg.webp">
        <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/4DX_2019_logo.svg/1200px-4DX_2019_logo.svg.png" class="small-logo">
    </div>
    """,
    unsafe_allow_html=True
)

# ---- Login Message ----
st.markdown('<p class="login-message">LOGIN TO SEE YOUR 2025 LINEUP</p>', unsafe_allow_html=True)

# ---- Login Section ----
exhibitor_name = st.text_input("Enter Exhibitor Name")
password = st.text_input("Enter Password", type="password")

# Default password is "2025" for all exhibitors
if st.button("Login"):
    if password == "2025" and exhibitor_name in bookings_df["Exhibitor"].unique():
        st.success(f"Welcome, {exhibitor_name}!")

        # ✅ Filter data for the exhibitor
        exhibitor_data = bookings_df[bookings_df["Exhibitor"] == exhibitor_name]

        # ✅ Merge lineup with exhibitor bookings (only 2025 titles)
        merged = lineup_df.merge(exhibitor_data, on="Title", how="left")

        # ✅ Define release date
        merged["Release_Date"] = merged["Start_Date"].apply(
            lambda x: x if pd.notna(x) else "-"
        )

        # ✅ Format booking types correctly
        def format_bookings(row):
            formats = []
            if "M244DX" in str(row["BU"]):
                formats.append("4DX")
            if "M24SCX" in str(row["BU"]):
                formats.append("ScreenX")
            return ", ".join(formats) if formats else "Not Booked"

        merged["Format_s_Booked"] = merged.apply(format_bookings, axis=1)

        # ✅ Create "Your 2025 Lineup" (only movies that were booked)
        booked_titles = (
            merged[merged["Release_Date"] != "-"]
            .groupby("Title", as_index=False)
            .agg({
                "Country_of_Origin": "first",
                "Release_Date": "first",
                "Format_s_Booked": lambda x: ", ".join(filter(lambda v: v != "—", x.unique()))
            })
        )

        # ✅ Create "What about these titles?" (Titles releasing soon that exhibitor did not book)
        today = datetime.today()
        one_month_ago = today - timedelta(days=30)
        three_months_ahead = today + timedelta(days=90)

        upcoming_titles = lineup_df[
            (~lineup_df["Title"].isin(booked_titles["Title"])) &  # Exclude booked titles
            (lineup_df["First_Release"].between(one_month_ago, three_months_ahead)) &  # Within date range
            (~lineup_df["Country_of_Origin"].isin(["China", "Vietnam"]))  # Exclude China & Vietnam titles
        ][["Title", "Country_of_Origin", "4DX", "SX"]].drop_duplicates()

        # ✅ Format column names properly (replace underscores with spaces)
        booked_titles.columns = booked_titles.columns.str.replace("_", " ")
        upcoming_titles.columns = upcoming_titles.columns.str.replace("_", " ")

        # ✅ Display tables side by side
        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<div class="section-title">Your 2025 Lineup:</div>', unsafe_allow_html=True)
            st.markdown('<div class="small-title">The below titles are all officially booked and ready for release:</div>', unsafe_allow_html=True)
            st.dataframe(booked_titles.style.hide(axis="index"))

        with col2:
            st.markdown('<div class="section-title">What about these titles?</div>', unsafe_allow_html=True)
            st.markdown('<div class="small-title">The below titles are upcoming releases you are yet to book:</div>', unsafe_allow_html=True)
            st.dataframe(upcoming_titles.style.hide(axis="index"))

    else:
        st.error("Invalid Exhibitor Name or Password. Try again.")
