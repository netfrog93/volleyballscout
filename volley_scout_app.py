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
if "selected_player" not in st.session_state:
    st.session_state.selected_player = None
if "setup_done" not in st.session_state:
    st.session_state.setup_done = False

# --- Funzioni ---
def rotate_team():
    court_players = st.session_state.field_players[:6]
    st.session_state.field_players[:6] = [court_players[-1]] + court_players[:-1]

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
                score["B" if team=="A" else "A"]+=1
        elif action=="Errore avversario":
            score["A"]+=1
        elif action in ["Punto avversario","Errore squadra"]:
            score["B"]+=1
    st.session_state.score = score

# --- Setup iniziale ---
if not st.session_state.setup_done:
    st.subheader("Setup Partita")

    # Nomi squadre
    team_a = st.text_input("Nome squadra A", value=st.session_state.team_names["A"])
    team_b = st.text_input("Nome squadra B", value=st.session_state.team_names["B"])
    st.session_state.team_names["A"] = team_a
    st.session_state.team_names["B"] = team_b

    # Set attuale
    st.session_state.current_set = st.number_input(
        "Seleziona Set", min_value=1, max_value=SETS, value=st.session_state.current_set, step=1
    )

    # Selezione giocatori
    st.subheader("Seleziona 7 giocatori in campo")
    options = st.multiselect(
        "Giocatori Team A", st.session_state.players["Nome"].tolist(), default=st.session_state.field_players
    )
    if len(options) == 7:
        st.session_state.field_players = options
        st.session_state.setup_done = True
    elif len(options) > 0:
        st.warning("Seleziona esattamente 7 giocatori")

# --- Punteggio ---
st.markdown("## Punteggio attuale 🏐")
st.metric(st.session_state.team_names["A"], st.session_state.score["A"])
st.metric(st.session_state.team_names["B"], st.session_state.score["B"])

# --- Giocatori con pulsante fondamentale + menu codice ---
st.subheader("Giocatori e Score")

for gp in st.session_state.field_players:
    cols = st.columns([2, 2, 4])  # Nome | Pulsante fondamentale | Menu codice
    
    # Colonna 1: nome giocatore
    cols[0].write(f"**{gp}**")
    
    # Colonna 2: pulsante fondamentale
    if cols[1].button("Scegli fondamentale", key=f"fund_{gp}"):
        st.session_state.selected_player = gp
        st.session_state.selected_action = None
        st.session_state.selected_code = None

    # Colonna 3: menu codice (solo se questo giocatore è selezionato)
    if st.session_state.selected_player == gp:
        action = st.selectbox(
            "Seleziona fondamentale",
            list(ACTION_CODES.keys()),
            key=f"action_{gp}"
        )
        st.session_state.selected_action = action

        if action:
            code = cols[2].selectbox(
                "Seleziona risultato",
                ACTION_CODES[action],
                key=f"code_{gp}"
            )
            st.session_state.selected_code = code

            if code:
                # Registra evento
                new_row = {
                    "Set": st.session_state.current_set,
                    "PointNo": len(st.session_state.raw)+1,
                    "Team": "A",
                    "Giocatore": gp,
                    "Azione": action,
                    "Codice": code,
                    "Note": ""
                }
                st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([new_row])], ignore_index=True)
                
                # Aggiorna punteggio
                update_score()
                
                # Rotazione se necessario
                if action in ["Attacco","Battuta","Muro"] and code=="Punto":
                    rotate_team()
                
                # Reset menu
                st.session_state.selected_player = None
                st.session_state.selected_action = None
                st.session_state.selected_code = None

# --- Eventi generali ---
st.subheader("Eventi generali")
for label, team, action in [("Errore avversario","A","Errore avversario"),
                             ("Punto avversario","B","Punto avversario"),
                             ("Errore squadra","B","Errore squadra")]:
    if st.button(label):
        st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([{
            "Set": st.session_state.current_set,
            "PointNo":0,
            "Team": team,
            "Giocatore":"Evento Generale",
            "Azione": action,
            "Codice":"",
            "Note":""
        }])], ignore_index=True)
        update_score()

# --- Eventi registrati ---
st.subheader("Eventi registrati")
if not st.session_state.raw.empty:
    for idx, row in st.session_state.raw.iterrows():
        st.write(f"{row['Set']} | {row['PointNo']} | {st.session_state.team_names[row['Team']]} | {row['Giocatore']} | {row['Azione']} | {row['Codice']} | {row['Note']}")
        if st.button(f"Elimina {idx}", key=f"del_{idx}"):
            st.session_state.raw.drop(idx, inplace=True)
            st.session_state.raw.reset_index(drop=True, inplace=True)
            update_score()

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
