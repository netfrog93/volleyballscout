import streamlit as st
import pandas as pd
import io
import os

st.set_page_config(page_title="Volley Scout", layout="wide")

MAX_PLAYERS = 14
SETS = 5

ACTION_CODES = {
    "Battuta": ["Punto", "Buona", "Regolare", "Errore"],
    "Ricezione": ["Ottima", "Buona", "Regolare", "Scarsa", "Errore"],
    "Attacco": ["Punto", "Buono", "Regolare", "Murato", "Errore"],
    "Difesa": ["Ottima", "Errore"],
    "Muro": ["Punto", "Errore"]
}

# Percorso sicuro per Streamlit Cloud
ROSTER_FILE = os.path.join(os.path.dirname(__file__), "roster.xlsx")

# --- Caricamento roster ---
if "players" not in st.session_state:
    if os.path.exists(ROSTER_FILE):
        st.session_state.players = pd.read_excel(ROSTER_FILE)
    else:
        st.session_state.players = pd.DataFrame({
            "Numero": list(range(1, MAX_PLAYERS+1)),
            "Nome": [f"Player{i}" for i in range(1, MAX_PLAYERS+1)],
            "Ruolo": [""]*MAX_PLAYERS
        })

# --- Session state ---
if "raw" not in st.session_state:
    st.session_state.raw = pd.DataFrame(columns=["Set","PointNo","Team","Giocatore","Azione","Codice","Note"])
if "current_set" not in st.session_state:
    st.session_state.current_set = 1
if "field_players" not in st.session_state:
    st.session_state.field_players = []
if "team_names" not in st.session_state:
    st.session_state.team_names = {"A":"Team A","B":"Team B"}
if "score" not in st.session_state:
    st.session_state.score = {"A":0,"B":0}

# --- Sidebar ---
st.sidebar.header("Impostazioni partita")
st.sidebar.subheader("Squadre")
team_a = st.sidebar.text_input("Nome squadra A", value=st.session_state.team_names["A"])
team_b = st.sidebar.text_input("Nome squadra B", value=st.session_state.team_names["B"])
st.session_state.team_names["A"] = team_a
st.session_state.team_names["B"] = team_b

st.sidebar.subheader("Set attuale")
st.session_state.current_set = st.sidebar.number_input(
    "Seleziona Set", min_value=1, max_value=SETS, value=st.session_state.current_set, step=1
)

st.sidebar.subheader("Formazione in campo")
options = st.sidebar.multiselect(
    "Seleziona 7 giocatori",
    st.session_state.players["Nome"].tolist(),
    default=st.session_state.field_players
)
if len(options) == 7:
    st.session_state.field_players = options
elif len(options) > 0:
    st.sidebar.warning("Seleziona esattamente 7 giocatori")

st.sidebar.subheader("Sostituzioni")
if st.session_state.field_players:
    out_player = st.sidebar.selectbox("Chi esce?", st.session_state.field_players)
    in_player = st.sidebar.selectbox(
        "Chi entra?",
        [p for p in st.session_state.players["Nome"] if p not in st.session_state.field_players]
    )
    if st.sidebar.button("Esegui sostituzione"):
        idx_out = st.session_state.field_players.index(out_player)
        st.session_state.field_players[idx_out] = in_player
        st.success(f"Sostituito {out_player} con {in_player}")

# --- Rotazione ---
def rotate_team():
    court_players = st.session_state.field_players[:6]
    rotated = [court_players[-1]] + court_players[:-1]
    st.session_state.field_players[:6] = rotated

# --- Calcolo punteggio ---
def update_score():
    score = {"A":0,"B":0}
    for _, row in st.session_state.raw.iterrows():
        team = row["Team"]
        action = row["Azione"]
        code = row["Codice"]

        if action in ["Attacco","Battuta","Muro"]:
            if code=="Punto":
                score[team]+=1
            elif code=="Errore":
                other = "B" if team=="A" else "A"
                score[other]+=1
        elif action=="Errore avversario":
            score["A"]+=1
        elif action in ["Punto avversario","Errore squadra"]:
            score["B"]+=1
    st.session_state.score = score

update_score()

# --- Punteggio ---
st.markdown("## Punteggio attuale 🏐")
cols_score = st.columns(2)
cols_score[0].metric(st.session_state.team_names["A"], st.session_state.score["A"])
cols_score[1].metric(st.session_state.team_names["B"], st.session_state.score["B"])

# --- Inserimento eventi ---
st.header("Inserisci evento")

if st.session_state.field_players:
    player_cols = st.columns([2,3], gap="small")
    
    with player_cols[0]:
        st.subheader("Giocatori")
        for gp in st.session_state.field_players:
            if st.button(gp, key=f"player_{gp}"):
                st.session_state.selected_player = gp
                if "selected_score" in st.session_state:
                    del st.session_state.selected_score
    
    with player_cols[1]:
        st.subheader("Score")
        if "selected_player" in st.session_state:
            for action, codes in ACTION_CODES.items():
                st.markdown(f"**{action}**")
                code_cols = st.columns(len(codes), gap="small")
                for j, code in enumerate(codes):
                    if code_cols[j].button(code, key=f"{st.session_state.selected_player}_{action}_{code}"):
                        team = "A"  # I giocatori sono sempre Team A
                        new_row = {
                            "Set": st.session_state.current_set,
                            "PointNo": len(st.session_state.raw)+1,
                            "Team": team,
                            "Giocatore": st.session_state.selected_player,
                            "Azione": action,
                            "Codice": code,
                            "Note": ""
                        }
                        st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([new_row])], ignore_index=True)
                        update_score()
                        if action in ["Attacco","Battuta","Muro"] and code=="Punto" and team=="A":
                            rotate_team()
                        del st.session_state.selected_player
                        st.experimental_rerun()

# --- Eventi generali ---
st.subheader("Eventi generali")
extra_cols = st.columns(3, gap="small")
if extra_cols[0].button("Errore avversario"):
    st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([{
        "Set": st.session_state.current_set,
        "PointNo":0,
        "Team":"A",
        "Giocatore":"Evento Generale",
        "Azione":"Errore avversario",
        "Codice":"",
        "Note":""
    }])], ignore_index=True)
    update_score()
if extra_cols[1].button("Punto avversario"):
    st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([{
        "Set": st.session_state.current_set,
        "PointNo":0,
        "Team":"B",
        "Giocatore":"Evento Generale",
        "Azione":"Punto avversario",
        "Codice":"",
        "Note":""
    }])], ignore_index=True)
    update_score()
if extra_cols[2].button("Errore squadra"):
    st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([{
        "Set": st.session_state.current_set,
        "PointNo":0,
        "Team":"B",
        "Giocatore":"Evento Generale",
        "Azione":"Errore squadra",
        "Codice":"",
        "Note":""
    }])], ignore_index=True)
    update_score()

# --- Eventi registrati ---
st.subheader("Eventi registrati")
if not st.session_state.raw.empty:
    for idx, row in st.session_state.raw.iterrows():
        cols = st.columns([4,1])
        cols[0].write(f"{row['Set']} | {row['PointNo']} | {st.session_state.team_names[row['Team']]} | {row['Giocatore']} | {row['Azione']} | {row['Codice']} | {row['Note']}")
        if cols[1].button("Elimina", key=f"del_{idx}"):
            st.session_state.raw.drop(idx, inplace=True)
            st.session_state.raw.reset_index(drop=True, inplace=True)
            update_score()
            st.experimental_rerun()

# --- Tabellini ---
def compute_counts(df_raw):
    players = st.session_state.players["Nome"].tolist()
    columns = []
    for act, codes in ACTION_CODES.items():
        for c in codes:
            columns.append(f"{act}_{c}")
        columns.append(f"{act}_Tot")
    data = pd.DataFrame(0, index=players, columns=columns)
    for _, row in df_raw.iterrows():
        g = row["Giocatore"]
        act = row["Azione"]
        code = row["Codice"]
        col = f"{act}_{code}"
        if g in data.index and col in data.columns:
            data.at[g, col] += 1
    for act, codes in ACTION_CODES.items():
        code_cols = [f"{act}_{c}" for c in codes]
        data[f"{act}_Tot"] = data[code_cols].sum(axis=1)
    return data

st.subheader("Tabellini giocatrici")
tabellino = compute_counts(st.session_state.raw)
st.dataframe(tabellino)

# --- Export Excel ---
st.header("Esporta")
def to_excel_bytes(tabellino, raw_data):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        tabellino.to_excel(writer, sheet_name="Tabellino", index=False)
        raw_data.to_excel(writer, sheet_name="Raw", index=False)
    return output.getvalue()

excel_data = to_excel_bytes(tabellino, st.session_state.raw)
st.download_button(
    "Scarica Excel (.xlsx)", 
    data=excel_data, 
    file_name="Volley_Scout_Report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
