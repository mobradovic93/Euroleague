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
        df = pd.read_csv('boxscores_2024_merged.csv')
        # Konverzija datuma
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        # Izračunavanje FGA (sabiramo pokušaje za 2 i za 3)
        if 'FieldGoalsAttempted2' in df.columns and 'FieldGoalsAttempted3' in df.columns:
            df['FGA'] = df['FieldGoalsAttempted2'] + df['FieldGoalsAttempted3']
        else:
            df['FGA'] = 0
            
        # Sređivanje minuta
        def parse_min(x):
            try:
                s = str(x).strip()
                if ':' in s:
                    p = s.split(':')
                    return int(p[0]) + int(p[1])/60
                return 0.0 if s.upper() in ['DNP', 'DSR', 'NAN'] else float(s)
            except: return 0.0
        
        if 'Minutes' in df.columns:
            df['MIN_NUMERIC'] = df['Minutes'].apply(parse_min)
        else:
            df['MIN_NUMERIC'] = 0.0
        
        # Protivnik i lokacija
        if 'hometeam' in df.columns and 'awayteam' in df.columns:
            df['Opponent'] = df.apply(lambda row: row['awayteam'] if row['Home'] == 1 else row['hometeam'], axis=1)
            df['Venue'] = df['Home'].apply(lambda x: 'Home' if x == 1 else 'Away')
        
        df['Player'] = df['Player'].str.strip() if 'Player' in df.columns else "Unknown"
        df['Team'] = df['Team'].str.strip() if 'Team' in df.columns else "Unknown"
        return df
    except Exception as e:
        st.error(f"Greška pri učitavanju fajla: {e}")
        return None

def main():
    df = load_data()
    if df is None: return

    # --- SIDEBAR: RESET I SELEKCIJA ---
    st.sidebar.button("🔄 Resetuj sve filtere", on_click=reset_filters, use_container_width=True)
    st.sidebar.markdown("---")
    
    st.sidebar.header("🏀 Selekcija")
    
    all_teams = sorted(df['Team'].dropna().unique())
    selected_team = st.sidebar.selectbox("1. Izaberi Tim:", ["Svi timovi"] + all_teams, key="sb_team")
    
    t_df = df[df['Team'] == selected_team] if selected_team != "Svi timovi" else df
    available_players = sorted(t_df['Player'].dropna().unique())
    selected_player = st.sidebar.selectbox("2. Izaberi Igrača:", available_players, key="sb_player")
    
    # Podaci za selektovanog igrača
    pdf = df[df['Player'] == selected_player].copy()
    pdf = pdf.sort_values('date', ascending=False)

    st.sidebar.markdown("---")
    st.sidebar.header("🛠️ Kumulativni Filteri")

    # 1. On/Off Saigrač
    player_team = pdf['Team'].iloc[0] if not pdf.empty else ""
    teammates = sorted(df[(df['Team'] == player_team) & (df['Player'] != selected_player)]['Player'].unique())
    exclude_teammate = st.sidebar.selectbox("Isključi saigrača (ako je DNP):", ["Niko"] + teammates, key="sb_teammate")
    
    if exclude_teammate != "Niko":
        absent_games = df[(df['Player'] == exclude_teammate) & (df['MIN_NUMERIC'] == 0)]['Gamecode'].unique()
        pdf = pdf[pdf['Gamecode'].isin(absent_games)]

    # 2. Lokacija
    venue_choice = st.sidebar.radio("Lokacija:", ['Sve', 'Home', 'Away'], key="sb_venue")
    if venue_choice != 'Sve':
        pdf = pdf[pdf['Venue'] == venue_choice]

    # 3. Protivnik
    all_opps = sorted(pdf['Opponent'].dropna().unique())
    selected_opps = st.sidebar.multiselect("Vs Team (Protivnik):", ["Svi"] + all_opps, default=["Svi"], key="sb_opps")
    if "Svi" not in selected_opps and len(selected_opps) > 0:
        pdf = pdf[pdf['Opponent'].isin(selected_opps)]

    # 4. Minute (Sigurnosna provera)
    if not pdf.empty:
        m_min = float(pdf['MIN_NUMERIC'].min())
        m_max = float(pdf['MIN_NUMERIC'].max())
        if m_min < m_max:
            st.sidebar.slider("Minutaža:", m_min, m_max, (m_min, m_max), key="sb_mins")
            s_min, s_max = st.session_state.get("sb_mins", (m_min, m_max))
            pdf = pdf[(pdf['MIN_NUMERIC'] >= s_min) & (pdf['MIN_NUMERIC'] <= s_max)]
        else:
            st.sidebar.info(f"Fiksna minutaža: {m_min:.1f}")

    # 5. Broj poslednjih utakmica (Fix za Slider grešku)
    total_found = len(pdf)
    if total_found > 1:
        num_games = st.sidebar.slider("Poslednjih utakmica:", 1, total_found, min(10, total_found), key="sb_num_games")
        pdf = pdf.head(num_games)
    elif total_found == 1:
        st.sidebar.info("Pronađena samo jedna utakmica.")
    
    # --- KONTROLE U GLAVNOM DELU ---
    chart_stats = {
        'Poeni': 'Points', 'Asistencije': 'Assistances', 'Skokovi': 'TotalRebounds', 
        '3PM': 'FieldGoalsMade3', 'Minuti': 'MIN_NUMERIC', 'FGA': 'FGA'
    }
    
    col_s, col_l = st.columns(2)
    with col_s:
        selected_label = st.selectbox("Statistika za Line:", list(chart_stats.keys()), key="sb_stat_label")
        selected_col = chart_stats[selected_label]
    
    with col_l:
        if not pdf.empty:
            curr_max = float(pdf[selected_col].max())
            s_max = max(curr_max + 0.5, 1.5)
            st.slider(f"Granica:", 0.5, s_max, 10.5, 1.0, key="sb_threshold")
            threshold = st.session_state.get("sb_threshold", 10.5)
        else:
            threshold = 10.5

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
            <div style="text-align: center;"><div style="font-size: 12px; color: #888;">AST</div><div style="font-size: 20px; font-weight: bold;">{pdf['Assistances'].mean():.1f}</div></div>
            <div style="text-align: center;"><div style="font-size: 12px; color: #888;">REB</div><div style="font-size: 20px; font-weight: bold;">{pdf['TotalRebounds'].mean():.1f}</div></div>
            <div style="text-align: center;"><div style="font-size: 12px; color: #888;">3PM</div><div style="font-size: 20px; font-weight: bold;">{pdf['FieldGoalsMade3'].mean():.1f}</div></div>
            <div style="text-align: center;"><div style="font-size: 12px; color: #888;">MINS</div><div style="font-size: 20px; font-weight: bold;">{pdf['MIN_NUMERIC'].mean():.1f}</div></div>
            <div style="text-align: center;"><div style="font-size: 12px; color: #888;">FGA</div><div style="font-size: 20px; font-weight: bold;">{pdf['FGA'].mean():.1f}</div></div>
        </div>
        """, unsafe_allow_html=True)

        # --- INTERAKTIVNI GRAFIKON ---
        st.write("")
        chart_df = pdf.sort_values('date').copy()
        chart_df['date_fmt'] = chart_df['date'].dt.strftime('%d-%b-%Y')
        chart_df['x_axis'] = chart_df['date_fmt'] + "<br>vs " + chart_df['Opponent'].str[:10]
        chart_df['Diff'] = chart_df[selected_col] - threshold

        fig = px.bar(
            chart_df, x='x_axis', y=selected_col, color='Diff', 
            color_continuous_scale='RdYlGn', color_continuous_midpoint=0, 
            text_auto=True, title=f"Analiza: {selected_player} | Granica: {threshold}"
        )
        fig.add_hline(y=threshold, line_dash="dash", line_color="white")
        fig.update_layout(xaxis_title="", yaxis_title=selected_label, xaxis_type='category', coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # --- TABELA ---
        st.subheader("Match Log")
        display_df = pdf[['date', 'Opponent', 'Venue', 'Minutes', 'Points', 'TotalRebounds', 'Assistances', 'FGA', 'Valuation']].copy()
        display_df['date'] = display_df['date'].dt.strftime('%d-%b-%Y')
        st.dataframe(display_df, use_container_width=True)
    else:
        st.error("Nema utakmica koje zadovoljavaju kombinaciju svih filtera. Klikni 'Resetuj sve filtere'.")

if __name__ == "__main__":
    main()