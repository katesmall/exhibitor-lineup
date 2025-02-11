import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# Google Sheets setup
SERVICE_ACCOUNT_FILE = "C:/Users/USER/Documents/2. Python/Console/jsonkeybookings.json"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/14-snTxdOwetRBpARaD0tTZk-i53DdYWOeKmcgpaaL6I"

# Authenticate
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

# Load Google Sheets
spreadsheet = client.open_by_url(SPREADSHEET_URL)
bookings_ws = spreadsheet.worksheet("Bookings Raw Data")
lineup_ws = spreadsheet.worksheet("4DPLEX Lineup Clean")

# Convert to DataFrame
bookings_df = pd.DataFrame(bookings_ws.get_all_records())
lineup_df = pd.DataFrame(lineup_ws.get_all_records())

# ✅ Standardize column names
bookings_df.columns = bookings_df.columns.str.strip().str.replace(" ", "_").str.replace("\n", "_")
lineup_df.columns = lineup_df.columns.str.strip().str.replace(" ", "_").str.replace("\n", "_")

# ✅ Convert First_Release to datetime & Filter only relevant 2025 titles
lineup_df["First_Release"] = pd.to_datetime(lineup_df["First_Release"], errors='coerce')

# ---- Date Range for "What about these titles?" ----
today = datetime.today()
one_month_ago = today - timedelta(days=30)
three_months_ahead = today + timedelta(days=90)

# ✅ Filter only 2025 titles from "4DPLEX Lineup Clean"
lineup_df = lineup_df[lineup_df["First_Release"] >= "2025-01-01"]

# ---- Streamlit Web App ----
st.set_page_config(page_title="Exhibitor 2025 Lineup", layout="wide")

# ---- Maintain Login State Using `st.session_state` ----
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.exhibitor_name = None
    st.session_state.selected_country = None

# ---- UI ----
st.markdown(
    """
    <style>
    body { background-color: white; color: black; text-align: center; font-size:11px }
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

st.markdown('<p class="login-message">LOGIN TO SEE YOUR 2025 LINEUP</p>', unsafe_allow_html=True)

# ---- Login Section ----
if not st.session_state.logged_in:
    exhibitor_name = st.text_input("Enter Exhibitor Name")
    password = st.text_input("Enter Password", type="password")

    if st.button("Login"):
        if password == "2025" and exhibitor_name in bookings_df["Exhibitor"].unique():
            st.session_state.logged_in = True
            st.session_state.exhibitor_name = exhibitor_name
        else:
            st.error("Invalid Exhibitor Name or Password. Try again.")

# ---- Display Content Only if Logged In ----
if st.session_state.logged_in:
    st.success(f"Welcome, {st.session_state.exhibitor_name}!")

    # ✅ Get unique countries for this exhibitor
    exhibitor_countries = bookings_df[bookings_df["Exhibitor"] == st.session_state.exhibitor_name]["Country"].unique()

    # ✅ Dropdown for country selection (store in session state to persist)
    if st.session_state.selected_country is None:
        st.session_state.selected_country = exhibitor_countries[0]

    selected_country = st.selectbox("Filter by Country:", exhibitor_countries, index=0, key="country_selector")

    # ---- Function to get an exhibitor's lineup ----
    def get_exhibitor_lineup(exhibitor_name, selected_country):
        exhibitor_data = bookings_df[
            (bookings_df["Exhibitor"] == exhibitor_name) & (bookings_df["Country"] == selected_country)
        ]

        merged = lineup_df.merge(exhibitor_data, on="Title", how="left")

        merged["Release_Date"] = merged["Start_Date"].apply(lambda x: x if pd.notna(x) else "-")

        def format_bookings(row):
            formats = []
            if "M244DX" in str(row["BU"]):
                formats.append("4DX")
            if "M24SCX" in str(row["BU"]):
                formats.append("ScreenX")
            return ", ".join(formats) if formats else "Not Booked"

        merged["Format_s_Booked"] = merged.apply(format_bookings, axis=1)

        booked_titles = (
            merged[merged["Release_Date"] != "-"]
            .groupby("Title", as_index=False)
            .agg({
                "Country_of_Origin": "first",
                "Release_Date": "first",
                "Format_s_Booked": lambda x: ", ".join(filter(lambda v: v != "—", x.unique()))
            })
        )

        upcoming_titles = lineup_df[
            (~lineup_df["Title"].isin(booked_titles["Title"])) &
            (lineup_df["First_Release"].between(one_month_ago, three_months_ahead)) &
            (~lineup_df["Country_of_Origin"].isin(["China", "Vietnam"]))
        ][["Title", "Country_of_Origin", "4DX", "SX"]].drop_duplicates()

        booked_titles.columns = booked_titles.columns.str.replace("_", " ")
        upcoming_titles.columns = upcoming_titles.columns.str.replace("_", " ")

        return booked_titles, upcoming_titles

    # Fetch exhibitor's lineup (filtered by country)
    booked_titles, upcoming_titles = get_exhibitor_lineup(st.session_state.exhibitor_name, selected_country)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-title">Your 2025 Lineup:</div>', unsafe_allow_html=True)
        st.markdown('<div class="small-title">The below titles are all officially booked and ready for your release:</div>', unsafe_allow_html=True)
        st.dataframe(booked_titles.style.hide(axis="index"))

    with col2:
        st.markdown('<div class="section-title">What about these titles?</div>', unsafe_allow_html=True)
        st.markdown('<div class="small-title">The below titles are upcoming releases you are yet to book:</div>', unsafe_allow_html=True)
        st.dataframe(upcoming_titles.style.hide(axis="index"))
