import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Euroleague Props", page_icon="🏀", layout="wide")

# ---------------------------------------------------------------------------
# THEME / CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
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

    stats = stats[~stats['Player'].str.strip().str.upper().isin(['TOTAL', 'TEAM'])].copy()

    # Build a common merge key: date + player name + team code (case/whitespace-insensitive)
    stats['_key_date'] = stats['date']
    stats['_key_player'] = stats['Player'].str.strip().str.upper()
    stats['_key_team'] = stats['Team'].str.strip().str.upper()

    meta['_key_date'] = meta['Date']
    meta['_key_player'] = meta['Player'].str.strip().str.upper()
    meta['_key_team'] = meta['TeamCode'].str.strip().str.upper()

    meta_cols = ['_key_date', '_key_player', '_key_team', 'Player', 'TeamName',
                 'TeamImageUrl', 'OpponentTeamName', 'OpponentTeamImageUrl',
                 'Matchup', 'MatchupAxis']

    df = stats.merge(meta[meta_cols], on=['_key_date', '_key_player', '_key_team'],
                      how='inner', suffixes=('', '_meta'))
    df = df.merge(headshots, on='_key_player', how='left')

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

    keep = ['Date', 'Player', 'TeamName', 'TeamImageUrl', 'PlayerImageUrl', 'OpponentTeamName',
            'OpponentTeamImageUrl', 'Matchup', 'MatchupAxis', 'Venue',
            'Minutes_Numeric', 'Played',
            'Points', 'Rebounds', 'Assists', 'ThreePM', 'ThreePA',
            'TwoPM', 'TwoPA', 'FTM', 'FTA', 'OffRebounds', 'DefRebounds',
            'Steals', 'Blocks', 'BlocksAgainst', 'Turnovers', 'FoulsCommited',
            'Valuation', 'Plusminus', 'PRA', 'PR', 'PA', 'RA', 'Stocks']
    return df[keep].sort_values('Date', ascending=False).reset_index(drop=True)


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
}


# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------
def main():
    df = load_data()
    if df is None or df.empty:
        st.error("No data available.")
        return

    st.sidebar.button("🔄 Reset all filters", on_click=reset_filters, use_container_width=True)
    st.sidebar.markdown("---")
    st.sidebar.header("🏀 Player")

    player_options = (
        df.dropna(subset=['Player', 'TeamName'])
        .drop_duplicates(subset=['Player'], keep='first')[['Player', 'TeamName']]
    )
    player_map = {
        f"{row['Player']} ({row['TeamName']})": (row['Player'], row['TeamName'])
        for _, row in player_options.sort_values('Player').iterrows()
    }
    selected_option = st.sidebar.selectbox("Select player:", list(player_map), key="sb_player")
    selected_player, player_team = player_map[selected_option]

    pdf = df[(df['Player'] == selected_player) & (df['TeamName'] == player_team)].copy()
    pdf = pdf.sort_values('Date', ascending=False)

    st.sidebar.markdown("---")
    st.sidebar.header("🛠️ Filters")

    only_played = st.sidebar.checkbox("Exclude DNP / did-not-play games", value=True, key="sb_played")
    if only_played:
        pdf = pdf[pdf['Played']]

    teammates = sorted(df[(df['TeamName'] == player_team) & (df['Player'] != selected_player)]['Player'].unique())

    include_teammates = st.sidebar.multiselect("Include games teammate played:", teammates, key="sb_teammates_include")
    if include_teammates:
        for teammate in include_teammates:
            teammate_dates = df[(df['TeamName'] == player_team) & (df['Player'] == teammate) & (df['Played'])]['Date'].unique()
            pdf = pdf[pdf['Date'].isin(teammate_dates)]

    exclude_teammates = st.sidebar.multiselect("Exclude games teammate played:", teammates, key="sb_teammates")
    if exclude_teammates:
        played_with = df[(df['TeamName'] == player_team) & (df['Player'].isin(exclude_teammates)) & (df['Played'])]['Date'].unique()
        pdf = pdf[~pdf['Date'].isin(played_with)]

    venue_choice = st.sidebar.radio("Venue:", ['All', 'Home', 'Away'], key="sb_venue", horizontal=True)
    if venue_choice != 'All':
        pdf = pdf[pdf['Venue'] == venue_choice]

    sel_min = None
    if not pdf.empty:
        mn, mx = int(pdf['Minutes_Numeric'].min()), int(pdf['Minutes_Numeric'].max())
        if mn < mx:
            sel_min = st.sidebar.slider("Minutes played:", mn, mx, (mn, mx), key="sb_minutes")
            pdf = pdf[pdf['Minutes_Numeric'].between(*sel_min)]

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
        venue_choice, sel_min, tuple(sorted(selected_opponents)),
    )
    if st.session_state.get("_filter_signature") != filter_signature:
        st.session_state["_filter_signature"] = filter_signature
        st.session_state.pop("sb_num_games", None)

    # --- HEADER CARD ---
    logo = pdf['TeamImageUrl'].dropna().iloc[0] if not pdf['TeamImageUrl'].dropna().empty else ""
    headshot = pdf['PlayerImageUrl'].dropna().iloc[0] if not pdf['PlayerImageUrl'].dropna().empty else logo
    games_count = len(pdf)
    st.markdown(f"""
    <div class="player-card">
        <div class="player-photo-wrap">
            <img class="headshot" src="{headshot}" />
            <img class="team-badge" src="{logo}" />
        </div>
        <div>
            <div class="player-name">{selected_player}</div>
            <div class="player-sub">{player_team} &nbsp;•&nbsp; {games_count} games matching filters</div>
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
        default_line = min(10.5, max(cur_max / 2, 0.5))
        default_line = int(default_line) + 0.5  # lines always sit on a .5, e.g. 8.5 not 8.0 or 9.0
        line = st.number_input("Line:", min_value=0.5, max_value=max(cur_max + 5, 5.5),
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
        plot_bgcolor='#0b0e14', paper_bgcolor='#0b0e14', font=dict(size=14, color='#cdd3e0'),
        title_font_size=20, xaxis=dict(tickfont=dict(size=12)), yaxis=dict(tickfont=dict(size=12)),
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- MATCH LOG TABLE ---
    st.subheader("Match Log")
    display_cols = ['Date', 'Matchup', 'Venue', 'Minutes_Numeric', 'Points', 'Rebounds',
                     'Assists', 'ThreePM', 'Steals', 'Blocks', 'Turnovers', 'PRA']
    display_df = sample[display_cols].copy()

    def color_market(row):
        return ["color: #22c55e; font-weight:700;" if col == stat_col and row[col] > line
                else ("color: #ef4444; font-weight:700;" if col == stat_col else "")
                for col in display_cols]

    styled = display_df.style.apply(color_market, axis=1, subset=display_cols)

    st.dataframe(
        styled, use_container_width=True, hide_index=True,
        column_config={
            "Date": st.column_config.DateColumn("Date", format="DD-MMM-YYYY"),
            "Matchup": st.column_config.TextColumn("Matchup"),
            "Venue": st.column_config.TextColumn("Venue"),
            "Minutes_Numeric": st.column_config.NumberColumn("MIN", format="%.1f"),
            "Points": st.column_config.NumberColumn("PTS"),
            "Rebounds": st.column_config.NumberColumn("REB"),
            "Assists": st.column_config.NumberColumn("AST"),
            "ThreePM": st.column_config.NumberColumn("3PM"),
            "Steals": st.column_config.NumberColumn("STL"),
            "Blocks": st.column_config.NumberColumn("BLK"),
            "Turnovers": st.column_config.NumberColumn("TOV"),
            "PRA": st.column_config.NumberColumn("PRA"),
        }
    )


if __name__ == "__main__":
    main()
