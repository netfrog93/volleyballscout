import streamlit as st
import pandas as pd
import io
import os

st.set_page_config(page_title="Volley Scout", layout="wide")

# --- Rerun compatibile con tutte le versioni ---
def safe_rerun():
    """Chiama st.rerun() se disponibile, altrimenti st.experimental_rerun() se presente."""
    rerun = getattr(st, "rerun", None)
    if callable(rerun):
        return rerun()
    exp_rerun = getattr(st, "experimental_rerun", None)
    if callable(exp_rerun):
        return exp_rerun()
    st.warning("La tua versione di Streamlit non supporta il rerun automatico.")

MAX_PLAYERS = 14
SETS = 5

ACTION_CODES = {
    "BAT": ["Punto", "Buona", "Regolare", "Errore"],
    "RICE": ["Ottima", "Buona", "Regolare", "Scarsa", "Errore"],
    "ATK": ["Punto", "Buono", "Regolare", "Murato", "Errore"],
    "DIF": ["Ottima", "Errore"],
    "MU": ["Punto", "Errore"]
}

# =========================
#  ROSTER: upload & template
# =========================
REQUIRED_ROSTER_COLUMNS = ["Numero", "Nome", "Ruolo"]

def default_roster_df():
    return pd.DataFrame({
        "Numero": list(range(1, MAX_PLAYERS + 1)),
        "Nome": [f"Player{i}" for i in range(1, MAX_PLAYERS + 1)],
        "Ruolo": [""] * MAX_PLAYERS
    })

def load_roster_from_upload(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file, engine="openpyxl")
    except Exception as e:
        st.sidebar.error(f"Errore nel leggere l'Excel: {e}")
        return None

    # Normalizza nomi colonne (case/whitespace-insensitive)
    rename_map = {}
    for col in df.columns:
        key = col.strip().lower()
        for req in REQUIRED_ROSTER_COLUMNS:
            if key == req.lower():
                rename_map[col] = req
    df = df.rename(columns=rename_map)

    missing = [c for c in REQUIRED_ROSTER_COLUMNS if c not in df.columns]
    if missing:
        st.sidebar.error(
            "Il file roster deve contenere queste colonne: "
            + ", ".join(REQUIRED_ROSTER_COLUMNS)
            + f". Mancanti: {', '.join(missing)}"
        )
        return None

    df = df[REQUIRED_ROSTER_COLUMNS].copy()
    df["Numero"] = pd.to_numeric(df["Numero"], errors="coerce").astype("Int64")
    df["Nome"] = df["Nome"].astype(str).str.strip()
    df["Ruolo"] = df["Ruolo"].astype(str).str.strip()
    df = df[df["Nome"].fillna("").str.len() > 0].reset_index(drop=True)
    return df

def df_to_excel_bytes(df, sheet_name="Roster"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

# --- Session state iniziali ---
if "players" not in st.session_state:
    st.session_state.players = default_roster_df()
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
if "selected_action" not in st.session_state:
    st.session_state.selected_action = None

# ==============
# Sidebar
# ==============
st.sidebar.header("Impostazioni partita")

# ---- Roster upload ----
st.sidebar.subheader("Roster")
uploaded_roster = st.sidebar.file_uploader(
    "Carica roster.xlsx (colonne richieste: Numero, Nome, Ruolo)",
    type=["xlsx"],
    accept_multiple_files=False
)
if uploaded_roster is not None:
    df_loaded = load_roster_from_upload(uploaded_roster)
    if df_loaded is not None:
        st.session_state.players = df_loaded
        st.sidebar.success(f"Roster caricato: {len(df_loaded)} giocatori")
        valid_names = set(st.session_state.players["Nome"].tolist())
        st.session_state.field_players = [p for p in st.session_state.field_players if p in valid_names]

# Template scaricabile
template_bytes = df_to_excel_bytes(default_roster_df(), sheet_name="Roster")
st.sidebar.download_button(
    "Scarica template roster.xlsx",
    data=template_bytes,
    file_name="roster_template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# ---- Squadre ----
st.sidebar.subheader("Squadre")
team_a = st.sidebar.text_input("Nome squadra A", value=st.session_state.team_names["A"])
team_b = st.sidebar.text_input("Nome squadra B", value=st.session_state.team_names["B"])
st.session_state.team_names["A"] = team_a
st.session_state.team_names["B"] = team_b

# ---- Set attuale ----
st.sidebar.subheader("Set attuale")
st.session_state.current_set = st.sidebar.number_input(
    "Seleziona Set", min_value=1, max_value=SETS, value=st.session_state.current_set, step=1
)

# ---- Formazione in campo ----
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

# ---- Sostituzioni ----
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

# ==============
# Funzioni di gioco
# ==============
def rotate_team():
    court_players = st.session_state.field_players[:6]
    if len(court_players) == 6:
        rotated = [court_players[-1]] + court_players[:-1]
        st.session_state.field_players[:6] = rotated

def update_score():
    score = {"A":0,"B":0}
    for _, row in st.session_state.raw.iterrows():
        team = row["Team"]
        action = row["Azione"]
        code = row["Codice"]
        # Punti dai fondamentali
        if action in ["ATK","BAT","MU"]:
            if code == "Punto":
                score[team] += 1
            elif code == "Errore":
                other = "B" if team == "A" else "A"
                score[other] += 1
        # Eventi generali
        elif action == "Errore avversario":
            score["A"] += 1
        elif action in ["Punto avversario","Errore squadra"]:
            score["B"] += 1
    st.session_state.score = score

update_score()

# =======================
# Punteggio totale
# =======================
st.markdown("## Punteggio attuale 🏐")
cols_score = st.columns(2)
cols_score[0].metric(st.session_state.team_names["A"], st.session_state.score["A"])
cols_score[1].metric(st.session_state.team_names["B"], st.session_state.score["B"])

# =======================
# Inserisci evento — flusso in 3 step con righe singole
# =======================
st.header("Inserisci evento")

def register_event(player, action, code):
    team = "A" if player in st.session_state.field_players[:6] else "B"
    new_row = {
        "Set": st.session_state.current_set,
        "PointNo": len(st.session_state.raw) + 1,
        "Team": team,
        "Giocatore": player,
        "Azione": action,
        "Codice": code,
        "Note": ""
    }
    st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([new_row])], ignore_index=True)
    update_score()
    if action in ["ATK", "BAT", "MU"] and code == "Punto" and team == "A":
        rotate_team()
    # torna alla riga dei giocatori
    st.session_state.selected_action = None
    st.session_state.selected_player = None
    safe_rerun()

# --- STEP 1: 7 giocatori su UNA sola riga ---
if st.session_state.field_players:
    st.subheader("Giocatori in campo (7)")
    cols_players = st.columns(7, gap="small")
    for i in range(7):
        name = st.session_state.field_players[i] if i < len(st.session_state.field_players) else None
        if name:
            if cols_players[i].button(name, key=f"player_{name}", use_container_width=True):
                st.session_state.selected_player = name
                st.session_state.selected_action = None
                safe_rerun()
else:
    st.info("Seleziona i 7 giocatori nella sidebar per iniziare.")

# --- STEP 2: scelta fondamentale (una riga) ---
if st.session_state.selected_player and not st.session_state.selected_action:
    st.markdown("---")
    st.subheader(f"{st.session_state.selected_player} → scegli il fondamentale")
    actions = list(ACTION_CODES.keys())  # ["BAT","RICE","ATK","DIF","MU"]
    cols_actions = st.columns(len(actions), gap="small")
    for i, action in enumerate(actions):
        if cols_actions[i].button(action, key=f"action_{st.session_state.selected_player}_{action}", use_container_width=True):
            st.session_state.selected_action = action
            safe_rerun()
    # opzionale: cambia giocatore
    if st.button("⬅️ Cambia giocatore", key="back_players", type="secondary"):
        st.session_state.selected_player = None
        st.session_state.selected_action = None
        safe_rerun()

# --- STEP 3: scelta score per il fondamentale selezionato (una riga) ---
if st.session_state.selected_player and st.session_state.selected_action:
    st.markdown("---")
    action = st.session_state.selected_action
    st.subheader(f"{st.session_state.selected_player} · {action} → scegli lo Score")
    codes = ACTION_CODES[action]
    cols_codes = st.columns(len(codes), gap="small")
    for i, code in enumerate(codes):
        if cols_codes[i].button(code, key=f"code_{st.session_state.selected_player}_{action}_{code}", use_container_width=True):
            register_event(st.session_state.selected_player, action, code)

    nav_cols = st.columns([1,1,4])
    if nav_cols[0].button("⬅️ Fondamentale", key="back_to_action", type="secondary"):
        st.session_state.selected_action = None
        safe_rerun()
    if nav_cols[1].button("⬅️ Giocatori", key="back_to_players2", type="secondary"):
        st.session_state.selected_action = None
        st.session_state.selected_player = None
        safe_rerun()

# =======================
# Eventi generali
# =======================
st.subheader("Eventi generali")
extra_cols = st.columns(3, gap="small")
if extra_cols[0].button("Errore avversario", use_container_width=True):
    st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([{
        "Set": st.session_state.current_set,
        "PointNo": 0,
        "Team": "A",
        "Giocatore": "Evento Generale",
        "Azione": "Errore avversario",
        "Codice": "",
        "Note": ""
    }])], ignore_index=True)
    update_score()
if extra_cols[1].button("Punto avversario", use_container_width=True):
    st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([{
        "Set": st.session_state.current_set,
        "PointNo": 0,
        "Team": "B",
        "Giocatore": "Evento Generale",
        "Azione": "Punto avversario",
        "Codice": "",
        "Note": ""
    }])], ignore_index=True)
    update_score()
if extra_cols[2].button("Errore squadra", use_container_width=True):
    st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([{
        "Set": st.session_state.current_set,
        "PointNo": 0,
        "Team": "B",
        "Giocatore": "Evento Generale",
        "Azione": "Errore squadra",
        "Codice": "",
        "Note": ""
    }])], ignore_index=True)
    update_score()

# =======================
# Eventi registrati
# =======================
st.subheader("Eventi registrati")
if not st.session_state.raw.empty:
    for idx, row in st.session_state.raw.iterrows():
        cols = st.columns([4,1])
        cols[0].write(
            f"{row['Set']}  {row['PointNo']}  {st.session_state.team_names[row['Team']]}  "
            f"{row['Giocatore']}  {row['Azione']}  {row['Codice']}  {row['Note']}"
        )
        if cols[1].button("Elimina", key=f"del_{idx}", use_container_width=True):
            st.session_state.raw.drop(idx, inplace=True)
            st.session_state.raw.reset_index(drop=True, inplace=True)
            update_score()
            safe_rerun()

# =======================
# Tabellini e riepilogo
# =======================
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
st.dataframe(tabellino, use_container_width=True)

# =======================
# Export Excel
# =======================
st.header("Esporta")
def to_excel_bytes(tabellino, raw_data):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        tabellino.to_excel(writer, index=False)
        # raw_data.to_excel(writer, sheet_name="Raw", index=False)  # se vuoi anche il raw
    return output.getvalue()

excel_data = to_excel_bytes(tabellino, st.session_state.raw)
st.download_button(
    "Scarica Excel (.xlsx)",
    data=excel_data,
    file_name="Volley_Scout_Report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
