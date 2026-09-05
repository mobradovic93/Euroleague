import streamlit as st
import pandas as pd
import plotly.express as px

# --- PODEŠAVANJE STRANICE ---
st.set_page_config(page_title="Euroleague Player Stats", layout="wide")

# --- FUNKCIJA ZA RESETOVANJE ---
def reset_filters():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
   # st.rerun()

# --- POMOĆNE FUNKCIJE ---
def get_hit_rate_color(percentage):
    if percentage < 50:
        r, g, b = 255, int(255 * (percentage / 50)), 0
    else:
        r, g, b = int(255 * (1 - (percentage - 50) / 50)), 255, 0
    return f"rgb({r}, {g}, {b})"

@st.cache_data
def load_data():
    try:
        df = pd.read_csv('boxscores_final.csv')
        # Konverzija datuma
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
        # Čišćenje imena igrača i timova
        df['Player'] = df['Player'].str.strip() if 'Player' in df.columns else "Unknown"
        df['TeamName'] = df['TeamName'].str.strip() if 'TeamName' in df.columns else "Unknown"
        
        # Parsiranje minuta (iz stringa u float)
        def parse_minutes(x):
            try:
                s = str(x).strip()
                if ':' in s:
                    parts = s.split(':')
                    return int(parts[0]) + int(parts[1])/60
                return float(s) if s and s.upper() not in ['DNP', 'DSR', 'NAN', ''] else 0.0
            except:
                return 0.0
        
        df['Minutes_Numeric'] = df['Minutes'].apply(parse_minutes)
        
        # Derivacija Venue-a iz Matchup-a
        # Ako Matchup počinje sa TeamName, to je "Home" (vs format)
        # Ako nema TeamName na početku, to je "Away" (@ format)
        df['Venue'] = df.apply(
            lambda row: 'Home' if pd.notna(row['TeamName']) and pd.notna(row['Matchup']) and str(row['Matchup']).startswith(str(row['TeamName'])) else 'Away',
            axis=1
        )
        
        return df
    except Exception as e:
        st.error(f"Greška pri učitavanju fajla: {e}")
        return None

def get_team_options_with_images(df):
    """Kreira options za timove sa njihovim logotipima"""
    team_data = df[['TeamName', 'TeamImageUrl']].drop_duplicates().set_index('TeamName')['TeamImageUrl'].to_dict()
    return team_data

def get_opponent_from_matchup(matchup_str, player_team):
    """Ekstraktuje naziv protivničkog tima iz Matchup stringa"""
    if pd.isna(matchup_str) or pd.isna(player_team):
        return None
    
    matchup = str(matchup_str).strip()
    player_team = str(player_team).strip()
    
    # Očekivani formati: "TEAM1 vs TEAM2" ili "TEAM1 @ TEAM2"
    for separator in [' vs ', ' vs. ', ' @ ']:
        if separator in matchup:
            parts = [p.strip() for p in matchup.split(separator)]
            if len(parts) == 2:
                team1, team2 = parts
                # Vrati protivnika
                if team1 == player_team:
                    return team2
                elif team2 == player_team:
                    return team1
    
    return None

def main():
    df = load_data()
    if df is None: return

    # --- SIDEBAR: RESET I SELEKCIJA ---
    st.sidebar.button("🔄 Resetuj sve filtere", on_click=reset_filters, use_container_width=True)
    st.sidebar.markdown("---")
    
    st.sidebar.header("🏀 Selekcija")
    
    player_options = (
        df.sort_values('Date', ascending=False)
        .dropna(subset=['Player', 'TeamName'])
        .drop_duplicates(subset=['Player'], keep='first')
        [['Player', 'TeamName']]
    )
    player_options = {
        f"{row['Player']} - {row['TeamName']}": (row['Player'], row['TeamName'])
        for _, row in player_options.sort_values(['Player', 'TeamName']).iterrows()
    }
    selected_player_option = st.sidebar.selectbox(
        "Izaberi Igrača:",
        list(player_options),
        key="sb_player"
    )
    selected_player, player_team = player_options[selected_player_option]
    
    # Podaci za selektovanog igrača i njegov tim
    pdf = df[
        (df['Player'] == selected_player) &
        (df['TeamName'] == player_team)
    ].copy()
    pdf = pdf.sort_values('Date', ascending=False)

    st.sidebar.markdown("---")
    st.sidebar.header("🛠️ Kumulativni Filteri")

    # 1. On/Off Saigrač (Multiselect)
    teammates = sorted(df[(df['TeamName'] == player_team) & (df['Player'] != selected_player)]['Player'].unique())
    exclude_teammates = st.sidebar.multiselect("Isključi saigrače:", teammates, key="sb_teammates")

    # 2. Lokacija
    venue_choice = st.sidebar.radio("Lokacija:", ['Sve', 'Home', 'Away'], key="sb_venue")
    if venue_choice != 'Sve':
        pdf = pdf[pdf['Venue'] == venue_choice]

    # 3. Minutaža
    if not pdf.empty:
        minutes_min = int(pdf['Minutes_Numeric'].min())
        minutes_max = int(pdf['Minutes_Numeric'].max())
        if minutes_min < minutes_max:
            selected_minutes = st.sidebar.slider(
                "Minuta odigranih:",
                minutes_min,
                minutes_max,
                (minutes_min, minutes_max),
                key="sb_minutes"
            )
            pdf = pdf[pdf['Minutes_Numeric'].between(*selected_minutes)]

    # 4. Protivnik
    # Ekstraktuj imena protivničkih timova iz matchupa
    pdf_temp = pdf.copy()
    pdf_temp['Opponent'] = pdf_temp.apply(
        lambda row: get_opponent_from_matchup(row['Matchup'], row['TeamName']),
        axis=1
    )
    
    all_opponents = sorted([opp for opp in pdf_temp['Opponent'].dropna().unique() if opp])
    
    def on_opponents_change():
        if "sb_opponents" in st.session_state:
            selection = st.session_state["sb_opponents"]
            if len(selection) > 1:
                if selection[-1] == "Svi":
                    st.session_state["sb_opponents"] = ["Svi"]
                elif "Svi" in selection:
                    st.session_state["sb_opponents"] = [x for x in selection if x != "Svi"]

    selected_opponents = st.sidebar.multiselect(
        "Protivnik:", 
        ["Svi"] + all_opponents, 
        default=["Svi"], 
        key="sb_opponents",
        on_change=on_opponents_change
    )
    
    if "Svi" not in selected_opponents and len(selected_opponents) > 0:
        pdf = pdf[pdf.apply(
            lambda row: get_opponent_from_matchup(row['Matchup'], row['TeamName']) in selected_opponents,
            axis=1
        )]

    # 5. Broj poslednjih utakmica
    total_found = len(pdf)
    if total_found > 1:
        num_games = st.sidebar.slider("Poslednjih utakmica:", 1, total_found, min(10, total_found), key="sb_num_games")
        pdf = pdf.head(num_games)
    elif total_found == 1:
        st.sidebar.info("Pronađena samo jedna utakmica.")
    
    # --- KONTROLE U GLAVNOM DELU ---
    chart_stats = {
        'Poeni': 'Points', 'Asistencije': 'Assists', 'Skokovi': 'Rebounds'
    }
    
    col_s, col_l = st.columns(2)
    with col_s:
        selected_label = st.selectbox("Statistika za Line:", list(chart_stats.keys()), key="sb_stat_label")
        selected_col = chart_stats[selected_label]
    
    with col_l:
        if not pdf.empty:
            curr_max = float(pdf[selected_col].max())
            s_max = max(curr_max + 0.5, 1.5)
            default_threshold = min(10.5, s_max)
            st.slider("Granica:", 0.5, s_max, default_threshold, 1.0, key="sb_threshold")
            threshold = st.session_state.get("sb_threshold", default_threshold)
        else:
            threshold = 10.5

    # Zasebne granice za bojenje statistika u tabeli
    category_thresholds = {}
    threshold_labels = {
        'Points': 'Granica poena:',
        'Rebounds': 'Granica skokova:',
        'Assists': 'Granica asistencija:'
    }
    threshold_columns = st.columns(3)
    for column, (stat_column, label) in zip(threshold_columns, threshold_labels.items()):
        with column:
            if not pdf.empty:
                stat_max = max(float(pdf[stat_column].max()) + 0.5, 1.5)
                category_thresholds[stat_column] = st.slider(
                    label,
                    0.5,
                    stat_max,
                    min(10.5, stat_max),
                    1.0,
                    key=f"sb_threshold_{stat_column.lower()}"
                )
            else:
                category_thresholds[stat_column] = 10.5

    # --- PRIKAZ PODATAKA ---
    if not pdf.empty:
        # Kalkulacija Hit Rate-a
        hits = len(pdf[pdf[selected_col] > threshold])
        total = len(pdf)
        hit_rate = (hits / total) * 100
        
        # --- CUSTOM HEADER ---
        st.markdown(f"""
        <div style="background-color: #0e1117; padding: 20px; border-radius: 10px; display: flex; justify-content: space-around; align-items: center; color: white; border: 1px solid #333;">
            <div style="text-align: center;">
                <div style="font-size: 12px; color: #888;">HIT RATE</div>
                <div style="font-size: 24px; font-weight: bold; color: {get_hit_rate_color(hit_rate)};">{hit_rate:.1f}%</div>
                <div style="font-size: 14px;">({hits}/{total})</div>
            </div>
            <div style="border-left: 1px solid #333; height: 40px;"></div>
            <div style="text-align: center;"><div style="font-size: 12px; color: #888;">PTS</div><div style="font-size: 20px; font-weight: bold;">{pdf['Points'].mean():.1f}</div></div>
            <div style="text-align: center;"><div style="font-size: 12px; color: #888;">AST</div><div style="font-size: 20px; font-weight: bold;">{pdf['Assists'].mean():.1f}</div></div>
            <div style="text-align: center;"><div style="font-size: 12px; color: #888;">REB</div><div style="font-size: 20px; font-weight: bold;">{pdf['Rebounds'].mean():.1f}</div></div>
        </div>
        """, unsafe_allow_html=True)

        # --- INTERAKTIVNI GRAFIKON ---
        st.write("")
        chart_df = pdf.sort_values('Date').copy()
        chart_df['date_fmt'] = chart_df['Date'].dt.strftime('%d-%b-%Y')
        chart_df['x_axis'] = chart_df['date_fmt'] + "<br>" + chart_df['MatchupAxis']
        chart_df['Diff'] = chart_df[selected_col] - threshold
        chart_df['Result'] = chart_df['Diff'].apply(
            lambda difference: 'Preko granice' if difference > 0 else 'Ispod granice'
        )

        fig = px.bar(
            chart_df, x='x_axis', y=selected_col, color='Result',
            color_discrete_map={
                'Preko granice': '#22c55e',
                'Ispod granice': '#ef4444'
            },
            text=selected_col, title=f"Analiza: {selected_player} | Granica: {threshold}"
        )
        fig.add_hline(y=threshold, line_dash="dash", line_color="white")
        
        # Povećanje fonta labela na stubićima
        fig.update_traces(
            texttemplate='%{text}',
            textfont_size=20, 
            textposition="outside", 
            cliponaxis=False
        )
        fig.add_hline(y=threshold, line_dash="dash", line_color="white")
        
        # Povećanje fonta labela na stubićima
        fig.update_traces(
            textfont_size=18, 
            textposition="outside", 
            cliponaxis=False
        )
        
        # Povećanje fonta osa i naslova
        fig.update_layout(
            xaxis_title="", 
            yaxis_title=selected_label, 
            xaxis_type='category', 
            showlegend=False,
            font=dict(size=16), 
            title_font_size=22,
            xaxis=dict(tickfont=dict(size=14)),
            yaxis=dict(tickfont=dict(size=14))
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # --- TABELA ---
        st.subheader("Match Log")
        display_df = pdf[['Date', 'Matchup', 'Venue', 'Minutes_Numeric', 'Points', 'Rebounds', 'Assists']].copy()
        stat_columns = ['Points', 'Rebounds', 'Assists']

        def color_stats(row):
            return [
                (
                    "color: #22c55e;"
                    if row[stat_column] > category_thresholds[stat_column]
                    else "color: #ef4444;"
                )
                for stat_column in stat_columns
            ]

        styled_display_df = display_df.style.apply(
            color_stats,
            axis=1,
            subset=stat_columns
        )
        
        st.dataframe(
            styled_display_df, 
            use_container_width=True,
            column_config={
                "Date": st.column_config.DateColumn(
                    "Datum",
                    format="DD-MMM-YYYY",
                ),
                "Matchup": st.column_config.TextColumn("Utakmica"),
                "Venue": st.column_config.TextColumn("Lokacija"),
                "Minutes_Numeric": st.column_config.NumberColumn("Minuti", format="%.1f"),
                "Points": st.column_config.NumberColumn("Poeni"),
                "Rebounds": st.column_config.NumberColumn("Skokovi"),
                "Assists": st.column_config.NumberColumn("Asistencije")
            }
        )
    else:
        st.error("Nema utakmica koje zadovoljavaju kombinaciju svih filtera. Klikni 'Resetuj sve filtere'.")

if __name__ == "__main__":
    main()