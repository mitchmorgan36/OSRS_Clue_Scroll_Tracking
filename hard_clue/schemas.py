ACQ_SHEET = "acquisition_trips"
COMP_SHEET = "completion_sessions"
GOAL_PROGRESS_STATE_SHEET = "goal_progress_state"
GOAL_SETTINGS_SHEET = "goal_settings"
ACQ_LOGGER_STATE_SHEET = "acquisition_logger_state"
COMP_LOGGER_STATE_SHEET = "completion_logger_state"


GOAL_PROGRESS_STATE_COLS = (
    "start_acq_total",
    "start_comp_total",
    "start_set_at",
)

GOAL_SETTINGS_COLS = ("goal_caskets",)

ACQ_LOGGER_STATE_COLS = (
    "log_date",
    "start_playtime",
    "end_playtime",
    "start_bloods",
    "end_bloods",
    "clues",
    "notes",
    "start_system",
    "end_system",
    "updated_at",
)

COMP_LOGGER_STATE_COLS = (
    "log_date",
    "start_playtime",
    "end_playtime",
    "clues_completed",
    "notes",
    "start_system",
    "end_system",
    "updated_at",
)

ACQ_COLS = (
    "trip_id",
    "log_date",
    "start_playtime",
    "end_playtime",
    "duration_seconds_playtime",
    "start_system",
    "end_system",
    "duration_seconds_system",
    "duration_seconds",
    "start_bloods",
    "end_bloods",
    "bloods_used",
    "deaths_used",
    "gp_cost",
    "clues",
    "gp_per_clue",
    "clues_per_hour",
    "gp_per_hour",
    "notes",
)

COMP_COLS = (
    "session_id",
    "log_date",
    "start_playtime",
    "end_playtime",
    "duration_seconds_playtime",
    "start_system",
    "end_system",
    "duration_seconds_system",
    "duration_seconds",
    "clues_completed",
    "clues_per_hour",
    "notes",
)
