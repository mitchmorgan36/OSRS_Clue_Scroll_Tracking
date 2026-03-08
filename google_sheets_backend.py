from __future__ import annotations

import random
import time
from typing import Any

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials


ACQ_SHEET = "acquisition_trips"
COMP_SHEET = "completion_sessions"

# Scopes consistent with service-account write access for Sheets/Drive.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 5
BASE_DELAY_SECONDS = 1.0
MAX_DELAY_SECONDS = 16.0


def _extract_status_code(ex: Exception) -> int | None:
    response = getattr(ex, "response", None)
    if response is not None:
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int):
            return status_code
    for attr_name in ("code", "status"):
        value = getattr(ex, attr_name, None)
        if isinstance(value, int):
            return value
    message = str(ex)
    for code in RETRYABLE_STATUS_CODES:
        if f"[{code}]" in message or f"{code}:" in message:
            return code
    return None


def _call_with_backoff(func, *args, **kwargs):
    last_ex: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except gspread.exceptions.APIError as ex:
            last_ex = ex
            status_code = _extract_status_code(ex)
            if status_code not in RETRYABLE_STATUS_CODES or attempt == MAX_RETRIES - 1:
                raise
            delay = min(MAX_DELAY_SECONDS, BASE_DELAY_SECONDS * (2**attempt))
            delay += random.uniform(0, 0.5)
            time.sleep(delay)
        except Exception as ex:
            last_ex = ex
            raise
    if last_ex is not None:
        raise last_ex
    raise RuntimeError("Unexpected Sheets API retry failure.")


@st.cache_resource(show_spinner=False)
def _get_gspread_client() -> gspread.Client:
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def _get_spreadsheet() -> gspread.Spreadsheet:
    client = _get_gspread_client()
    if "google_sheet_id" in st.secrets:
        sheet_id = st.secrets["google_sheet_id"]
    else:
        sheet_id = st.secrets["gcp_service_account"]["google_sheet_id"]
    return _call_with_backoff(client.open_by_key, sheet_id)


@st.cache_resource(show_spinner=False)
def _get_worksheet(title: str) -> gspread.Worksheet:
    ss = _get_spreadsheet()
    try:
        return _call_with_backoff(ss.worksheet, title)
    except gspread.WorksheetNotFound:
        return _call_with_backoff(ss.add_worksheet, title=title, rows=1000, cols=30)



def _clean_value(v: Any) -> Any:
    if pd.isna(v):
        return ""
    return v



def read_sheet_df(sheet_name: str, headers: list[str]) -> pd.DataFrame:
    ws = _get_worksheet(sheet_name)
    values = _call_with_backoff(ws.get_all_values)

    if not values:
        _call_with_backoff(ws.append_row, headers, value_input_option="USER_ENTERED")
        return pd.DataFrame(columns=headers)

    current_headers = values[0]
    if current_headers != headers:
        raise ValueError(
            f"Worksheet '{ws.title}' headers do not match expected headers.\n"
            f"Current:  {current_headers}\nExpected: {headers}"
        )

    rows = values[1:]
    if not rows:
        return pd.DataFrame(columns=headers)

    normalized_rows: list[list[Any]] = []
    for row in rows:
        if len(row) < len(headers):
            row = row + [""] * (len(headers) - len(row))
        elif len(row) > len(headers):
            row = row[: len(headers)]
        normalized_rows.append(row)

    return pd.DataFrame(normalized_rows, columns=headers)



def append_row(sheet_name: str, headers: list[str], row_dict: dict[str, Any]) -> None:
    ws = _get_worksheet(sheet_name)
    existing_headers = _call_with_backoff(ws.row_values, 1)
    if not existing_headers:
        _call_with_backoff(ws.append_row, headers, value_input_option="USER_ENTERED")
        existing_headers = headers
    elif existing_headers != headers:
        raise ValueError(
            f"Worksheet '{ws.title}' headers do not match expected headers.\n"
            f"Current:  {existing_headers}\nExpected: {headers}"
        )

    row = [_clean_value(row_dict.get(col, "")) for col in headers]
    _call_with_backoff(ws.append_row, row, value_input_option="USER_ENTERED")



def replace_sheet(sheet_name: str, headers: list[str], df: pd.DataFrame) -> None:
    ws = _get_worksheet(sheet_name)
    data = [headers]
    for _, r in df.iterrows():
        data.append([_clean_value(r.get(col, "")) for col in headers])
    _call_with_backoff(ws.clear)
    _call_with_backoff(ws.update, data)
