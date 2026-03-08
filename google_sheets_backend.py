from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


ACQ_SHEET = "acquisition_trips"
COMP_SHEET = "completion_sessions"

# Scopes consistent with service-account write access for Sheets/Drive.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_gspread_client() -> gspread.Client:
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_spreadsheet() -> gspread.Spreadsheet:
    client = _get_gspread_client()
    sheet_id = st.secrets["google_sheet_id"]
    return client.open_by_key(sheet_id)


def _get_worksheet(title: str) -> gspread.Worksheet:
    ss = _get_spreadsheet()
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=title, rows=1000, cols=30)
        return ws


def _ensure_headers(ws: gspread.Worksheet, headers: list[str]) -> None:
    current = ws.row_values(1)
    if not current:
        ws.append_row(headers, value_input_option="USER_ENTERED")
    elif current != headers:
        raise ValueError(
            f"Worksheet '{ws.title}' headers do not match expected headers.\n"
            f"Current:  {current}\nExpected: {headers}"
        )


def _clean_value(v: Any) -> Any:
    if pd.isna(v):
        return ""
    return v


def read_sheet_df(sheet_name: str, headers: list[str]) -> pd.DataFrame:
    ws = _get_worksheet(sheet_name)
    _ensure_headers(ws, headers)

    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=headers)

    df = pd.DataFrame(records)

    for col in headers:
        if col not in df.columns:
            df[col] = ""

    return df[headers].copy()


def append_row(sheet_name: str, headers: list[str], row_dict: dict[str, Any]) -> None:
    ws = _get_worksheet(sheet_name)
    _ensure_headers(ws, headers)

    row = [_clean_value(row_dict.get(col, "")) for col in headers]
    ws.append_row(row, value_input_option="USER_ENTERED")


def replace_sheet(sheet_name: str, headers: list[str], df: pd.DataFrame) -> None:
    ws = _get_worksheet(sheet_name)
    _ensure_headers(ws, headers)

    data = [headers]
    for _, r in df.iterrows():
        data.append([_clean_value(r.get(col, "")) for col in headers])

    ws.clear()
    ws.update(data)