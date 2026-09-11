import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Euroleague Props", page_icon="🏀", layout="wide")

# ---------------------------------------------------------------------------
# THEME / CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, .stApp, .stApp *:not([data-testid="stIconMaterial"]):not([data-testid="stIconMaterial"] *) {
        font-family: 'Inter', 'Source Sans', sans-serif !important;
        font-variant-numeric: tabular-nums;
    }

    .stApp { background-color: #0b0e14; }
    div[data-testid="stSidebar"] { background-color: #10141d; }
    .block-container { padding-top: 4rem; }

    .player-card {
        display: flex; align-items: center; gap: 18px;
        background: linear-gradient(135deg, #151a24 0%, #0f131b 100%);
        border: 1px solid #232a38; border-radius: 16px;
        padding: 18px 24px; margin-bottom: 14px;
    }
    .player-photo-wrap { position: relative; width: 64px; height: 64px; flex-shrink: 0; }
    .player-photo-wrap .headshot {
        width: 64px; height: 64px; border-radius: 50%; object-fit: cover;
        object-position: 50% 12%;
        background: #1b2131; border: 2px solid #2a3245;
    }
    .player-photo-wrap .team-badge {
        position: absolute; right: -4px; bottom: -4px; width: 26px; height: 26px;
        object-fit: contain; background: #0b0e14; border-radius: 50%;
        border: 2px solid #0f131b; padding: 2px;
    }
    .player-name { font-size: 26px; font-weight: 800; color: #fff; line-height: 1.1; }
    .player-sub { font-size: 14px; color: #8b93a7; margin-top: 2px; }

    .market-pill {
        display: inline-block; padding: 4px 14px; border-radius: 999px;
        background: #1b2131; color: #9aa4bc; font-size: 13px; font-weight: 600;
        border: 1px solid #2a3245; margin-right: 6px;
    }

    .sidebar-header {
        font-size: 12px; font-weight: 800; letter-spacing: .09em; text-transform: uppercase;
        color: #8b93a7; margin: 2px 0 12px 0; padding-left: 10px;
        border-left: 3px solid #ff4b4b;
    }

    .matchup-row-logo {
        width: 28px; height: 28px; object-fit: contain;
        background: #1b2131; border-radius: 6px; padding: 3px;
        display: block; margin: 4px auto;
        pointer-events: none; /* a raw <img>, not st.image -- no native click-to-zoom */
    }

    /* Inter renders noticeably wider than Source Sans at the same size, which was
       wrapping the narrow 3-letter team-code buttons onto two lines ("DU"/"B").
       Tighter padding/size in the sidebar (where those live) keeps them on one line. */
    section[data-testid="stSidebar"] .stButton button {
        font-size: 13px; padding: 4px 6px; white-space: nowrap;
    }

    .splits-grid {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(88px, 1fr));
        gap: 10px; margin-top: 6px;
    }
    .split-card {
        background: #131826; border: 1px solid #232a38; border-radius: 14px;
        padding: 14px 8px; text-align: center;
    }
    .split-label { font-size: 12px; color: #8b93a7; letter-spacing: .04em; font-weight: 700; }
    .split-pct { font-size: 30px; font-weight: 800; margin: 4px 0 2px 0; }
    .split-frac { font-size: 13px; color: #6b7386; }

    .stat-row { display:flex; flex-wrap: wrap; justify-content: space-around; margin-top: 10px; }
    .stat-box { text-align: center; min-width: 80px; padding: 6px 4px; }
    .stat-box .v { font-size: 20px; font-weight: 800; color: #fff; }
    .stat-box .l { font-size: 11px; color: #8b93a7; }

    section[data-testid="stSidebar"] label, .stSlider label, .stRadio label { color: #cdd3e0 !important; }

    /* --- Mobile --- */
    @media (max-width: 640px) {
        .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
        .player-card { padding: 14px 16px; gap: 12px; }
        .player-photo-wrap, .player-photo-wrap .headshot { width: 48px; height: 48px; }
        .player-photo-wrap .team-badge { width: 20px; height: 20px; }
        .player-name { font-size: 20px; }
        .player-sub { font-size: 12px; }
        .splits-grid { grid-template-columns: repeat(3, 1fr); gap: 8px; }
        .split-pct { font-size: 22px; }
        .split-label { font-size: 10px; }
        .split-frac { font-size: 11px; }
        .stat-box .v { font-size: 17px; }
        .market-pill { font-size: 12px; padding: 3px 10px; }
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# DATA
# ---------------------------------------------------------------------------
def parse_minutes(x):
    try:
        s = str(x).strip()
        if ':' in s:
            parts = s.split(':')
            return int(parts[0]) + int(parts[1]) / 60
        return float(s) if s and s.upper() not in ['DNP', 'DSQ', 'NAN', ''] else 0.0
    except Exception:
        return 0.0


@st.cache_data
def load_data():
    stats = pd.read_csv('boxscores.csv')
    meta = pd.read_csv('boxscores_final.csv')
    try:
        headshots = pd.read_csv('players.csv')
        headshots['_key_player'] = headshots['Player'].str.strip().str.upper()
        headshots = headshots.drop_duplicates(subset='_key_player')[['_key_player', 'PlayerImageUrl']]
    except FileNotFoundError:
        headshots = pd.DataFrame(columns=['_key_player', 'PlayerImageUrl'])

    # dtype=str matters: player codes are zero-padded ("008855"), and pandas would
    # otherwise read them as ints and break the join against Player_ID.
    try:
        rosters = pd.read_csv('rosters.csv', dtype=str)
        rosters['PlayerCode'] = rosters['PlayerCode'].astype(str).str.strip()
        rosters = (
            rosters.dropna(subset=['PlayerCode'])
            .drop_duplicates(subset='PlayerCode')
            .set_index('PlayerCode')[['TeamCode', 'TeamName', 'TeamImageUrl']]
            .rename(columns={'TeamCode': 'RosterTeamCode', 'TeamName': 'RosterTeamName',
                             'TeamImageUrl': 'RosterTeamImageUrl'})
        )
    except FileNotFoundError:
        rosters = pd.DataFrame(columns=['RosterTeamCode', 'RosterTeamName', 'RosterTeamImageUrl'])

    stats = stats[~stats['Player'].str.strip().str.upper().isin(['TOTAL', 'TEAM'])].copy()

    # Build a common merge key: date + player name + team code (case/whitespace-insensitive)
    stats['_key_date'] = stats['date']
    stats['_key_player'] = stats['Player'].str.strip().str.upper()
    stats['_key_team'] = stats['Team'].str.strip().str.upper()

    meta['_key_date'] = meta['Date']
    meta['_key_player'] = meta['Player'].str.strip().str.upper()
    meta['_key_team'] = meta['TeamCode'].str.strip().str.upper()

    meta_cols = ['_key_date', '_key_player', '_key_team', 'Player', 'TeamCode', 'TeamName',
                 'TeamImageUrl', 'OpponentTeamName', 'OpponentTeamImageUrl',
                 'Matchup', 'MatchupAxis', 'TeamScore', 'OpponentScore']

    df = stats.merge(meta[meta_cols], on=['_key_date', '_key_player', '_key_team'],
                      how='inner', suffixes=('', '_meta'))
    df = df.merge(headshots, on='_key_player', how='left')

    # Player_ID is the roster feed's player code with a "P" prefix -- stripping it
    # gives the stable identity used to join rosters/headshots, which beats matching
    # on name (two different Davids, Kraemer vs Kramer, already collide in this data).
    df['PlayerCode'] = df['Player_ID'].astype(str).str.strip().str.lstrip('P')
    df['Player'] = df['Player_meta'].fillna(df['Player'])
    df['Date'] = pd.to_datetime(df['_key_date'], errors='coerce')
    df['Minutes_Numeric'] = df['Minutes'].apply(parse_minutes)
    df['Played'] = df['IsPlaying'].fillna(0).astype(int).eq(1) | (df['Minutes_Numeric'] > 0)

    df = df.rename(columns={
        'TotalRebounds': 'Rebounds',
        'Assistances': 'Assists',
        'FieldGoalsMade3': 'ThreePM',
        'FieldGoalsAttempted3': 'ThreePA',
        'FieldGoalsMade2': 'TwoPM',
        'FieldGoalsAttempted2': 'TwoPA',
        'FreeThrowsMade': 'FTM',
        'FreeThrowsAttempted': 'FTA',
        'BlocksFavour': 'Blocks',
        'OffensiveRebounds': 'OffRebounds',
        'DefensiveRebounds': 'DefRebounds',
    })

    for c in ['Points', 'Rebounds', 'Assists', 'ThreePM', 'Steals', 'Blocks', 'Turnovers']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    # the feed's "Valuation" is the EuroLeague's Performance Index Rating -- verified
    # against the official formula (PTS+REB+AST+STL+BLK+FoulsDrawn, minus missed FG/FT,
    # turnovers, shots rejected and fouls committed) on every row in the dataset
    df['PIR'] = pd.to_numeric(df['Valuation'], errors='coerce')

    df['PRA'] = df['Points'] + df['Rebounds'] + df['Assists']
    df['PR'] = df['Points'] + df['Rebounds']
    df['PA'] = df['Points'] + df['Assists']
    df['RA'] = df['Rebounds'] + df['Assists']
    df['Stocks'] = df['Steals'] + df['Blocks']

    df['Venue'] = df.apply(
        lambda row: 'Home' if pd.notna(row['TeamName']) and pd.notna(row['Matchup'])
        and str(row['Matchup']).startswith(str(row['TeamName'])) else 'Away',
        axis=1
    )

    df['TeamScore'] = pd.to_numeric(df['TeamScore'], errors='coerce')
    df['OpponentScore'] = pd.to_numeric(df['OpponentScore'], errors='coerce')
    df['GameScore'] = df['TeamScore'].astype('Int64').astype(str) + '-' + df['OpponentScore'].astype('Int64').astype(str)
    df.loc[df['TeamScore'].isna() | df['OpponentScore'].isna(), 'GameScore'] = None
    df['ScoreMargin'] = df['TeamScore'] - df['OpponentScore']  # positive = player's team won, negative = lost

    # --- CURRENT TEAM -------------------------------------------------------
    # A player belongs to whichever club has him on the upcoming season's roster;
    # if he isn't listed yet (preseason rosters fill in gradually, and some players
    # simply aren't re-signed), fall back to the team he last played a game for, so
    # nobody drops out of the app. Roster wins where both exist.
    last_played = (
        df.sort_values('Date')
        .groupby('PlayerCode')
        .agg(FallbackTeamCode=('TeamCode', 'last'),
             FallbackTeamName=('TeamName', 'last'),
             FallbackTeamImageUrl=('TeamImageUrl', 'last'))
    )
    current = last_played.join(rosters, how='left')
    current['CurrentTeamCode'] = current['RosterTeamCode'].fillna(current['FallbackTeamCode'])
    current['CurrentTeamName'] = current['RosterTeamName'].fillna(current['FallbackTeamName'])
    current['CurrentTeamImageUrl'] = current['RosterTeamImageUrl'].fillna(current['FallbackTeamImageUrl'])
    current['IsRostered'] = current['RosterTeamCode'].notna()

    df = df.merge(
        current[['CurrentTeamCode', 'CurrentTeamName', 'CurrentTeamImageUrl', 'IsRostered']],
        left_on='PlayerCode', right_index=True, how='left',
    )
    # a game played for anyone other than his current club -- surfaced in the match log
    df['FormerTeamGame'] = (
        df['TeamCode'].str.upper() != df['CurrentTeamCode'].astype(str).str.upper()
    )

    keep = ['Date', 'Player', 'PlayerCode', 'TeamCode', 'TeamName', 'TeamImageUrl',
            'CurrentTeamCode', 'CurrentTeamName', 'CurrentTeamImageUrl',
            'IsRostered', 'FormerTeamGame',
            'PlayerImageUrl', 'OpponentTeamName',
            'OpponentTeamImageUrl', 'Matchup', 'MatchupAxis', 'Venue',
            'GameScore', 'ScoreMargin',
            'Minutes_Numeric', 'Played',
            'Points', 'Rebounds', 'Assists', 'ThreePM', 'ThreePA',
            'TwoPM', 'TwoPA', 'FTM', 'FTA', 'OffRebounds', 'DefRebounds',
            'Steals', 'Blocks', 'BlocksAgainst', 'Turnovers', 'FoulsCommited',
            'PIR', 'Plusminus', 'PRA', 'PR', 'PA', 'RA', 'Stocks']
    return df[keep].sort_values('Date', ascending=False).reset_index(drop=True)


@st.cache_data
def load_upcoming_schedule():
    try:
        schedule = pd.read_csv('schedule_upcoming.csv')
    except FileNotFoundError:
        return None
    schedule['Date'] = pd.to_datetime(schedule['Date'], errors='coerce')
    schedule['HomeCode'] = schedule['HomeCode'].str.strip().str.upper()
    schedule['AwayCode'] = schedule['AwayCode'].str.strip().str.upper()
    if 'StartTime' in schedule.columns:
        schedule['StartTime'] = schedule['StartTime'].astype(str).str.strip()
    else:
        schedule['StartTime'] = ''
    return schedule


def get_next_game_day(schedule):
    """The nearest date (today or later) with at least one scheduled game, plus its matchups."""
    if schedule is None or schedule.empty:
        return None, None
    today = pd.Timestamp.now().normalize()
    upcoming = schedule[schedule['Date'] >= today]
    if upcoming.empty:
        return None, None
    next_date = upcoming['Date'].min()
    games = upcoming[upcoming['Date'] == next_date].sort_values('StartTime')
    return next_date, games


def snap_line_to_half():
    """Keep the line on a .5 grid (8.5, not 8.0 or 9.0) even after direct typing.
    Must run as an on_change callback: Streamlit forbids mutating a widget's own
    session_state key from the main script body once that widget is instantiated.
    """
    val = st.session_state.get("sb_line_val")
    if val is not None and val == int(val):
        st.session_state["sb_line_val"] = val + 0.5


def get_opponent(matchup_str, player_team):
    if pd.isna(matchup_str) or pd.isna(player_team):
        return None
    matchup, player_team = str(matchup_str).strip(), str(player_team).strip()
    for sep in [' vs ', ' vs. ', ' @ ']:
        if sep in matchup:
            parts = [p.strip() for p in matchup.split(sep)]
            if len(parts) == 2:
                t1, t2 = parts
                if t1 == player_team:
                    return t2
                if t2 == player_team:
                    return t1
    return None


def hit_rate_color(pct):
    if pct < 50:
        r, g = 255, int(255 * (pct / 50))
    else:
        r, g = int(255 * (1 - (pct - 50) / 50)), 255
    return f"rgb({r}, {g}, 0)"


def reset_filters():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def set_session_value(key, value):
    st.session_state[key] = value


def select_matchup(gid):
    """Pick a whole matchup (both teams) -- clears any single-team narrowing."""
    st.session_state["sb_next_matchup"] = gid
    st.session_state.pop("sb_next_team_only", None)
    st.session_state.pop("sb_next_team_only_for", None)


def select_matchup_team(gid, team_code):
    """Narrow to just one team within a matchup."""
    st.session_state["sb_next_matchup"] = gid
    st.session_state["sb_next_team_only"] = team_code
    st.session_state["sb_next_team_only_for"] = gid


def clear_team_only_filter():
    st.session_state.pop("sb_next_team_only", None)
    st.session_state.pop("sb_next_team_only_for", None)


def sidebar_header(text):
    st.sidebar.markdown(f'<div class="sidebar-header">{text}</div>', unsafe_allow_html=True)


def split_card_html(label, hits, total):
    if total == 0:
        pct, color = 0, "#555"
    else:
        pct = hits / total * 100
        color = hit_rate_color(pct)
    # No leading whitespace/newlines: st.markdown's CommonMark parser treats a
    # blank-line-then-4-space-indent as a literal code block, which breaks
    # unsafe_allow_html for every card after the first once these get joined.
    return (
        f'<div class="split-card"><div class="split-label">{label}</div>'
        f'<div class="split-pct" style="color:{color};">{pct:.0f}%</div>'
        f'<div class="split-frac">{hits}/{total}</div></div>'
    )


MARKETS = {
    'Points': 'Points',
    'Rebounds': 'Rebounds',
    'Assists': 'Assists',
    '3-Pointers Made': 'ThreePM',
    'Steals': 'Steals',
    'Blocks': 'Blocks',
    'Turnovers': 'Turnovers',
    'Pts + Reb + Ast (PRA)': 'PRA',
    'Pts + Reb (PR)': 'PR',
    'Pts + Ast (PA)': 'PA',
    'Reb + Ast (RA)': 'RA',
    'Stocks (Stl + Blk)': 'Stocks',
    'PIR (Valuation)': 'PIR',
}


# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------
def main():
    df = load_data()
    if df is None or df.empty:
        st.error("No data available.")
        return

    st.sidebar.button("Reset all filters", on_click=reset_filters, use_container_width=True)

    # --- PLAYER POOL (all players, or only those playing on the next game day) ---
    schedule_upcoming = load_upcoming_schedule()
    next_game_date, next_day_games = get_next_game_day(schedule_upcoming)
    active_team_codes = set()
    pool_choice = "all"

    # historical crests, then roster crests layered on top -- clubs new to the
    # competition (Besiktas in 2026-27) have no game history to source a logo from
    team_logo_by_code = (
        df.dropna(subset=['TeamCode', 'TeamImageUrl'])
        .drop_duplicates(subset='TeamCode')
        .set_index('TeamCode')['TeamImageUrl'].to_dict()
    )
    team_logo_by_code.update(
        df.dropna(subset=['CurrentTeamCode', 'CurrentTeamImageUrl'])
        .drop_duplicates(subset='CurrentTeamCode')
        .set_index('CurrentTeamCode')['CurrentTeamImageUrl'].to_dict()
    )

    if next_game_date is not None:
        active_team_codes = set(next_day_games['HomeCode']) | set(next_day_games['AwayCode'])
        st.sidebar.markdown("---")
        sidebar_header("Player pool")
        # stable option values ("all"/"next") with a display-only label -- the label
        # text embeds a date that shifts day to day, but the stored choice must not,
        # or a stale session_state value would no longer match the options list.
        # "next" listed first so it's the default (radio defaults to its first option).
        pool_choice = st.sidebar.radio(
            "Show players from:", ["next", "all"],
            format_func=lambda v: "All players" if v == "all" else f"Next game day ({next_game_date:%d-%b-%Y})",
            key="sb_pool_choice",
        )
        if pool_choice == "next":
            # stable id per game ("HOME_AWAY" codes) -- next_day_games is already
            # sorted by StartTime (earliest tip-off first).
            game_by_id = {
                f"{r['HomeCode']}_{r['AwayCode']}": r for _, r in next_day_games.iterrows()
            }
            matchup_label_by_id = {
                gid: f"{row['StartTime']} · {row['HomeCode']} vs {row['AwayCode']}"
                for gid, row in game_by_id.items()
            }
            matchup_choices = ["all"] + list(game_by_id)

            st.sidebar.markdown("---")
            sidebar_header("Upcoming matchups")

            # dropdown and clickable rows below both drive this same session_state key,
            # so picking a game either way stays in sync everywhere else on the page.
            if st.session_state.get("sb_next_matchup") not in matchup_choices:
                st.session_state["sb_next_matchup"] = "all"
            selected_matchup_id = st.sidebar.selectbox(
                "Matchup:", matchup_choices,
                format_func=lambda gid: "All matchups" if gid == "all" else matchup_label_by_id[gid],
                key="sb_next_matchup",
                on_change=clear_team_only_filter,
            )

            # a team-only narrowing only applies while it's still for the currently
            # selected matchup -- switching matchups (dropdown or button) clears it,
            # so a stale pick from a previous game can't silently carry over.
            team_only_code = st.session_state.get("sb_next_team_only")
            team_only_for = st.session_state.get("sb_next_team_only_for")

            if selected_matchup_id != "all":
                game_row = game_by_id[selected_matchup_id]
                home_code, away_code = game_row['HomeCode'], game_row['AwayCode']
                if team_only_for == selected_matchup_id and team_only_code in (home_code, away_code):
                    active_team_codes = {team_only_code}
                else:
                    active_team_codes = {home_code, away_code}

            for gid, row in game_by_id.items():
                is_matchup_selected = gid == selected_matchup_id
                is_home_only = is_matchup_selected and team_only_for == gid and team_only_code == row['HomeCode']
                is_away_only = is_matchup_selected and team_only_for == gid and team_only_code == row['AwayCode']

                # logos in their own row, buttons in a second row directly below --
                # keeps all three buttons on one aligned line instead of the side
                # buttons sitting lower than the middle one because of the stacked logo.
                logo_cols = st.sidebar.columns([1, 4, 1])
                with logo_cols[0]:
                    st.markdown(
                        f'<img src="{team_logo_by_code.get(row["HomeCode"], "")}" class="matchup-row-logo" />',
                        unsafe_allow_html=True,
                    )
                with logo_cols[2]:
                    st.markdown(
                        f'<img src="{team_logo_by_code.get(row["AwayCode"], "")}" class="matchup-row-logo" />',
                        unsafe_allow_html=True,
                    )

                button_cols = st.sidebar.columns([1, 4, 1])
                with button_cols[0]:
                    st.button(
                        row['HomeCode'], key=f"exp_team_home_{gid}", use_container_width=True,
                        type="primary" if is_home_only else "secondary",
                        on_click=select_matchup_team, args=(gid, row['HomeCode']),
                    )
                with button_cols[1]:
                    st.button(
                        f"{row['HomeCode']} vs {row['AwayCode']} · {row['StartTime']}",
                        key=f"exp_matchup_{gid}", use_container_width=True,
                        type="primary" if (is_matchup_selected and not is_home_only and not is_away_only) else "secondary",
                        on_click=select_matchup, args=(gid,),
                    )
                with button_cols[2]:
                    st.button(
                        row['AwayCode'], key=f"exp_team_away_{gid}", use_container_width=True,
                        type="primary" if is_away_only else "secondary",
                        on_click=select_matchup_team, args=(gid, row['AwayCode']),
                    )

    st.sidebar.markdown("---")
    sidebar_header("Player")

    # keyed on the player code, not the name: a player is one entry under his current
    # club even if his games were played for a different one (traded in the offseason).
    player_options = (
        df.dropna(subset=['Player', 'PlayerCode', 'CurrentTeamCode', 'CurrentTeamName'])
        .drop_duplicates(subset=['PlayerCode'], keep='first')
        [['PlayerCode', 'Player', 'CurrentTeamCode', 'CurrentTeamName', 'CurrentTeamImageUrl']]
    )
    if pool_choice == "next":
        player_options = player_options[
            player_options['CurrentTeamCode'].str.upper().isin(active_team_codes)
        ]

    player_map = {
        f"{row['Player']} ({row['CurrentTeamName']})": row['PlayerCode']
        for _, row in player_options.sort_values('Player').iterrows()
    }

    if not player_map:
        st.sidebar.warning("No players found for this pool.")
        return

    # if the stored pick isn't valid for the current pool (e.g. switching from "All
    # players" to "Next game day"), reset it before the widget is instantiated --
    # Streamlit forbids doing this after the widget already exists this run.
    # NOTE: explicitly assign a valid option here rather than popping the key --
    # popping leaves Streamlit to default to index 0 internally, but the selectbox's
    # displayed label can then desync from that (shows the stale pick while the rest
    # of the page already reflects the new default) until some later, unrelated
    # rerun catches it up. Setting a real value keeps the widget's own state in sync.
    if st.session_state.get("sb_player") not in player_map:
        st.session_state["sb_player"] = next(iter(player_map))

    selected_option = st.sidebar.selectbox("Select player:", list(player_map), key="sb_player")
    selected_code = player_map[selected_option]
    selected_row = player_options[player_options['PlayerCode'] == selected_code].iloc[0]
    selected_player = selected_row['Player']
    player_team = selected_row['CurrentTeamName']
    player_team_code = selected_row['CurrentTeamCode']

    # Scrollable, clickable player list as an alternative to the dropdown above.
    # Clicking a row writes into the *same* sb_player session_state the dropdown
    # uses (via on_click), so it's the identical, already-tested selection logic.
    with st.sidebar.container(height=320):
        for _, row in player_options.sort_values('Player').iterrows():
            option_key = f"{row['Player']} ({row['CurrentTeamName']})"
            is_selected = option_key == selected_option
            cols = st.columns([1, 4])
            with cols[0]:
                st.markdown(
                    f'<img src="{row["CurrentTeamImageUrl"] or ""}" class="matchup-row-logo" />',
                    unsafe_allow_html=True,
                )
            with cols[1]:
                st.button(
                    row['Player'], key=f"exp_player_{option_key}", use_container_width=True,
                    type="primary" if is_selected else "secondary",
                    on_click=set_session_value, args=("sb_player", option_key),
                )

    # all of his games, whichever club they were played for -- a traded player's
    # old-team form is the only history there is to project the new season from
    pdf = df[df['PlayerCode'] == selected_code].copy()
    pdf = pdf.sort_values('Date', ascending=False)

    st.sidebar.markdown("---")
    sidebar_header("Filters")

    only_played = st.sidebar.checkbox("Exclude DNP / did-not-play games", value=True, key="sb_played")
    if only_played:
        pdf = pdf[pdf['Played']]

    # Teammates are whoever actually appeared in the same games he did, matched on
    # (date, team) pairs from his own rows rather than on his current club -- for a
    # traded player those games belong to his former team, so filtering by the
    # current club would match nothing.
    player_game_keys = set(zip(pdf['Date'], pdf['TeamCode']))
    squad_rows = df[[k in player_game_keys for k in zip(df['Date'], df['TeamCode'])]]
    teammates = sorted(squad_rows[squad_rows['PlayerCode'] != selected_code]['Player'].unique())

    def games_teammate_played(names):
        played = squad_rows[squad_rows['Player'].isin(names) & squad_rows['Played']]
        return set(zip(played['Date'], played['TeamCode']))

    include_teammates = st.sidebar.multiselect("Include games teammate played:", teammates, key="sb_teammates_include")
    for teammate in include_teammates:
        keys = games_teammate_played([teammate])
        pdf = pdf[[k in keys for k in zip(pdf['Date'], pdf['TeamCode'])]]

    exclude_teammates = st.sidebar.multiselect("Exclude games teammate played:", teammates, key="sb_teammates")
    if exclude_teammates:
        keys = games_teammate_played(exclude_teammates)
        pdf = pdf[[k not in keys for k in zip(pdf['Date'], pdf['TeamCode'])]]

    venue_choice = st.sidebar.radio("Venue:", ['All', 'Home', 'Away'], key="sb_venue", horizontal=True)
    if venue_choice != 'All':
        pdf = pdf[pdf['Venue'] == venue_choice]

    sel_min = None
    if not pdf.empty:
        mn, mx = int(pdf['Minutes_Numeric'].min()), int(pdf['Minutes_Numeric'].max())
        if mn < mx:
            sel_min = st.sidebar.slider("Minutes played:", mn, mx, (mn, mx), key="sb_minutes")
            pdf = pdf[pdf['Minutes_Numeric'].between(*sel_min)]

    sel_margin = None
    margins = pdf['ScoreMargin'].dropna()
    if not margins.empty:
        margin_min, margin_max = int(margins.min()), int(margins.max())
        if margin_min < margin_max:
            sel_margin = st.sidebar.slider(
                "Final score margin (pts):", margin_min, margin_max, (margin_min, margin_max),
                key="sb_margin",
                help="Positive = player's team won by this many points, negative = lost by this many. "
                     "Narrow to blowout wins/losses or close games."
            )
            pdf = pdf[pdf['ScoreMargin'].isna() | pdf['ScoreMargin'].between(*sel_margin)]

            # Paint the slider track red -> grey -> green, anchored at the true zero
            # point (loss vs. win) rather than the middle of the range, which is
            # off-center whenever the min/max margins aren't symmetric. Scoped by
            # aria-label (mirrors the widget's own label) and DOM structure rather
            # than Streamlit's internal hashed class names, so it survives version
            # bumps that would otherwise silently break a class-name-based selector.
            span = margin_max - margin_min
            zero_pct = 50.0 if span <= 0 else max(0.0, min(100.0, (0 - margin_min) / span * 100))
            band = 8.0
            lo = max(zero_pct - band, 0.0)
            hi = min(zero_pct + band, 100.0)
            st.sidebar.markdown(f"""
            <style>
                /* the outer track div is a tall (~40px) hit-area, not the visible rail --
                   painting it directly turned the whole hit-area into a thick color bar.
                   The actual thin rail is its first child; that's the one to color. */
                div[role="group"][aria-label="Final score margin (pts):"] > div > div:first-child {{
                    background: linear-gradient(to right,
                        #ef4444 0%, #ef4444 {lo}%,
                        #6b7386 {zero_pct}%,
                        #22c55e {hi}%, #22c55e 100%) !important;
                }}
            </style>
            """, unsafe_allow_html=True)

    pdf_opp = pdf.copy()
    pdf_opp['Opponent'] = pdf_opp.apply(lambda r: get_opponent(r['Matchup'], r['TeamName']), axis=1)
    all_opponents = sorted([o for o in pdf_opp['Opponent'].dropna().unique() if o])
    selected_opponents = st.sidebar.multiselect("Opponent:", all_opponents, key="sb_opponents")
    if selected_opponents:
        pdf = pdf[pdf.apply(lambda r: get_opponent(r['Matchup'], r['TeamName']) in selected_opponents, axis=1)]

    # Reset the "sample size" widget to its sensible default whenever the active
    # filter combination changes, so e.g. clearing an opponent filter that narrowed
    # the sample to 2 games doesn't leave the slider stuck at 2.
    filter_signature = (
        selected_player, player_team, only_played,
        tuple(sorted(include_teammates)), tuple(sorted(exclude_teammates)),
        venue_choice, sel_min, sel_margin, tuple(sorted(selected_opponents)),
    )
    if st.session_state.get("_filter_signature") != filter_signature:
        st.session_state["_filter_signature"] = filter_signature
        st.session_state.pop("sb_num_games", None)

    # --- HEADER CARD ---
    # badge shows his current club, not whoever he last played a game for
    logo = selected_row['CurrentTeamImageUrl'] or team_logo_by_code.get(player_team_code, "")
    headshot = pdf['PlayerImageUrl'].dropna().iloc[0] if not pdf['PlayerImageUrl'].dropna().empty else logo
    games_count = len(pdf)
    former_count = int(pdf['FormerTeamGame'].sum()) if not pdf.empty else 0
    former_note = (
        f" &nbsp;•&nbsp; {former_count} with a former team" if former_count else ""
    )
    st.markdown(f"""
    <div class="player-card">
        <div class="player-photo-wrap">
            <img class="headshot" src="{headshot}" />
            <img class="team-badge" src="{logo}" />
        </div>
        <div>
            <div class="player-name">{selected_player}</div>
            <div class="player-sub">{player_team} &nbsp;•&nbsp; {games_count} games matching filters{former_note}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if pdf.empty:
        st.error("No games match the current combination of filters. Click 'Reset all filters'.")
        return

    # --- MARKET + LINE CONTROLS ---
    col_m, col_line, col_n = st.columns([2, 1, 1])
    with col_m:
        market_label = st.selectbox("Market:", list(MARKETS.keys()), key="sb_market")
        stat_col = MARKETS[market_label]
    with col_line:
        cur_max = float(pdf[stat_col].max()) if not pdf.empty else 10.0
        line_max = max(cur_max + 5, 5.5)
        default_line = min(10.5, max(cur_max / 2, 0.5))
        default_line = int(default_line) + 0.5  # lines always sit on a .5, e.g. 8.5 not 8.0 or 9.0

        # line_max shrinks/grows with the selected player+market's own stat ceiling, but
        # the line value persists in session_state across player/market switches -- if a
        # previous player's line no longer fits this one's bounds, reset it before the
        # widget is instantiated (mutating session_state after is not allowed).
        stored_line = st.session_state.get("sb_line_val")
        if stored_line is not None and not (0.5 <= stored_line <= line_max):
            st.session_state["sb_line_val"] = default_line

        line = st.number_input("Line:", min_value=0.5, max_value=line_max,
                                value=float(st.session_state.get("sb_line_val", default_line)),
                                step=0.5, key="sb_line_val", on_change=snap_line_to_half)
    with col_n:
        total_found = len(pdf)
        num_games = st.number_input("Sample size (last N games):", min_value=1,
                                     max_value=max(total_found, 1),
                                     value=min(10, total_found), step=1, key="sb_num_games")

    sample = pdf.head(int(num_games)).copy()

    # --- HIT RATE SPLITS ---
    st.write("")
    split_defs = [
        ("FILTERED", sample),
        ("L5", pdf.head(5)),
        ("L10", pdf.head(10)),
        ("SEASON", pdf),
        ("HOME", pdf[pdf['Venue'] == 'Home']),
        ("AWAY", pdf[pdf['Venue'] == 'Away']),
    ]
    cards_html = "".join(
        split_card_html(label, int((subset[stat_col] > line).sum()), len(subset))
        for label, subset in split_defs
    )
    st.markdown(f'<div class="splits-grid">{cards_html}</div>', unsafe_allow_html=True)

    # --- SAMPLE SUMMARY ---
    hits_n = int((sample[stat_col] > line).sum())
    total_n = len(sample)
    hit_rate = hits_n / total_n * 100 if total_n else 0
    fga = sample['TwoPA'] + sample['ThreePA']
    fgm = sample['TwoPM'] + sample['ThreePM']
    avg_fga = fga.mean() if total_n else 0.0
    fg_pct = (fgm.sum() / fga.sum() * 100) if fga.sum() else 0.0
    st.markdown(f"""
    <div style="background-color:#131826;border:1px solid #232a38;border-radius:14px;padding:16px 24px;margin-top:14px;">
        <span class="market-pill">{market_label}</span>
        <span class="market-pill">Line {line}</span>
        <span style="color:#8b93a7;font-size:13px;">over last {total_n} games</span>
        <div class="stat-row">
            <div class="stat-box"><div class="v" style="color:{hit_rate_color(hit_rate)}">{hit_rate:.1f}%</div><div class="l">HIT RATE ({hits_n}/{total_n})</div></div>
            <div class="stat-box"><div class="v">{sample[stat_col].mean():.1f}</div><div class="l">AVG {market_label.upper()}</div></div>
            <div class="stat-box"><div class="v">{sample[stat_col].median():.1f}</div><div class="l">MEDIAN</div></div>
            <div class="stat-box"><div class="v">{sample['Minutes_Numeric'].mean():.1f}</div><div class="l">AVG MIN</div></div>
            <div class="stat-box"><div class="v">{avg_fga:.1f}</div><div class="l">AVG FGA</div></div>
            <div class="stat-box"><div class="v">{fg_pct:.1f}%</div><div class="l">FG%</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- CHART ---
    st.write("")
    chart_df = sample.sort_values('Date').copy()
    chart_df['date_fmt'] = chart_df['Date'].dt.strftime('%d-%b-%Y')
    chart_df['x_axis'] = chart_df['date_fmt'] + "<br>" + chart_df['MatchupAxis']
    chart_df['Result'] = chart_df[stat_col].apply(lambda v: 'Over' if v > line else 'Under')

    fig = px.bar(
        chart_df, x='x_axis', y=stat_col, color='Result',
        color_discrete_map={'Over': '#22c55e', 'Under': '#ef4444'},
        text=stat_col, title=f"{selected_player} — {market_label} (line {line})",
        category_orders={'x_axis': chart_df['x_axis'].tolist()}
    )
    fig.add_hline(y=line, line_dash="dash", line_color="white")
    fig.update_traces(texttemplate='%{text}', textfont_size=16, textposition="outside", cliponaxis=False)
    fig.update_layout(
        xaxis_title="", yaxis_title=market_label, xaxis_type='category', showlegend=False,
        plot_bgcolor='#0b0e14', paper_bgcolor='#0b0e14',
        font=dict(family='Inter, sans-serif', size=14, color='#cdd3e0'),
        title_font_size=20, xaxis=dict(tickfont=dict(size=12)), yaxis=dict(tickfont=dict(size=12)),
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- MATCH LOG TABLE ---
    st.subheader("Match Log")
    # which club he played the game for -- starred and dimmed when it isn't his
    # current one, so old-team form is never mistaken for form with the new club
    sample = sample.copy()
    sample['TeamPlayed'] = sample['TeamCode'].astype(str) + sample['FormerTeamGame'].map({True: ' *', False: ''})
    former_mask = sample['FormerTeamGame']

    display_cols = ['Date', 'TeamPlayed', 'MatchupAxis', 'GameScore', 'Minutes_Numeric', 'Points',
                     'Rebounds', 'Assists', 'ThreePM', 'Steals', 'Blocks', 'Turnovers', 'PRA', 'PIR']
    display_df = sample[display_cols].copy()

    def color_market(row):
        is_former = bool(former_mask.loc[row.name])
        styles = []
        for col in display_cols:
            if col == stat_col:
                styles.append("color: #22c55e; font-weight:700;" if row[col] > line
                              else "color: #ef4444; font-weight:700;")
            else:
                styles.append("color: #6b7386;" if is_former else "")
        return styles

    styled = display_df.style.apply(color_market, axis=1, subset=display_cols)

    st.dataframe(
        styled, use_container_width=True, hide_index=True,
        column_config={
            "Date": st.column_config.DateColumn("Date", format="DD-MMM-YYYY"),
            "TeamPlayed": st.column_config.TextColumn("Team"),
            "MatchupAxis": st.column_config.TextColumn("Matchup"),
            "GameScore": st.column_config.TextColumn("Score"),
            "Minutes_Numeric": st.column_config.NumberColumn("MIN", format="%.1f"),
            "Points": st.column_config.NumberColumn("PTS"),
            "Rebounds": st.column_config.NumberColumn("REB"),
            "Assists": st.column_config.NumberColumn("AST"),
            "ThreePM": st.column_config.NumberColumn("3PM"),
            "Steals": st.column_config.NumberColumn("STL"),
            "Blocks": st.column_config.NumberColumn("BLK"),
            "Turnovers": st.column_config.NumberColumn("TOV"),
            "PRA": st.column_config.NumberColumn("PRA"),
            "PIR": st.column_config.NumberColumn("PIR"),
        }
    )
    if bool(former_mask.any()):
        st.caption(f"* played for a former team — {player_team} is his current club.")


if __name__ == "__main__":
    main()
