import streamlit as st
import pandas as pd
import io
import os

st.set_page_config(page_title="Volley Scout", layout="wide")

# --- Rerun compatibile con tutte le versioni ---
def safe_rerun():
    rerun = getattr(st, "rerun", None)
    if callable(rerun):
        return rerun()
    exp_rerun = getattr(st, "experimental_rerun", None)
    if callable(exp_rerun):
        return exp_rerun()
    st.warning("La tua versione di Streamlit non supporta il rerun automatico.")

MAX_PLAYERS = 20
SETS = 5

# === Fondamentali abbreviati ===
ACTION_CODES = {
    "BAT":  ["Punto", "Buona", "Regolare", "Errore"],
    "RICE": ["Ottima", "Buona", "Regolare", "Scarsa", "Errore"],
    "ATK":  ["Punto", "Buono", "Regolare", "Murato", "Errore"],
    "DIF":  ["Ottima", "Errore"],
    "MU":   ["Punto", "Errore"]
}

# === Roster upload & template ===
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
if "positions" not in st.session_state:
    st.session_state.positions = {i: None for i in range(1, 7)}
    st.session_state.positions["Libero"] = None
if "team_names" not in st.session_state:
    st.session_state.team_names = {"A":"SMV","B":"Squadra B"}
if "score" not in st.session_state:
    st.session_state.score = {"A":0,"B":0}
if "selected_player" not in st.session_state:
    st.session_state.selected_player = None
if "selected_action" not in st.session_state:
    st.session_state.selected_action = None
if "service_team" not in st.session_state:
    st.session_state.service_team = "A"

# ==============
# Sidebar
# ==============
st.sidebar.header("Impostazioni partita")

# ---- Roster (upload + template) ----
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

template_bytes = df_to_excel_bytes(default_roster_df(), sheet_name="Roster")
st.sidebar.download_button(
    "Scarica template roster.xlsx",
    data=template_bytes,
    file_name="roster_template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# ---- Squadre ----
st.sidebar.subheader("Squadre")
team_a = st.sidebar.text_input("Squadra A", value=st.session_state.team_names["A"])
team_b = st.sidebar.text_input("Squadra B", value=st.session_state.team_names["B"])
st.session_state.team_names["A"] = team_a
st.session_state.team_names["B"] = team_b

# ---- Set attuale ----
st.sidebar.subheader("Set attuale")
st.session_state.current_set = st.sidebar.number_input(
    "Seleziona Set", min_value=1, max_value=SETS, value=st.session_state.current_set, step=1
)

# ---- Chi inizia al servizio ----
st.sidebar.subheader("Servizio iniziale")
service_start = st.sidebar.radio(
    "Chi inizia al servizio?",
    options=["A", "B"],
    format_func=lambda x: st.session_state.team_names[x],
    index=0 if st.session_state.service_team == "A" else 1
)
st.session_state.service_team = service_start

# ---- Formazione ----
st.sidebar.subheader("Formazione (posizioni 1–6 + Libero)")
available_players = st.session_state.players["Nome"].tolist()
used = [p for p in st.session_state.positions.values() if p]

for pos in range(1, 7):
    current_player = st.session_state.positions[pos]
    valid_options = [""] + [p for p in available_players if p not in used or p == current_player]
    if current_player in available_players:
        index_value = valid_options.index(current_player)
    else:
        index_value = 0
        st.session_state.positions[pos] = ""
    st.session_state.positions[pos] = st.sidebar.selectbox(
        f"Posizione {pos}",
        valid_options,
        index=index_value,
        key=f"pos_{pos}"
    )

# Libero
current_libero = st.session_state.positions["Libero"]
valid_libero_options = [""] + [p for p in available_players if p not in used or p == current_libero]
if current_libero in available_players:
    libero_index = valid_libero_options.index(current_libero)
else:
    libero_index = 0
    st.session_state.positions["Libero"] = ""
st.session_state.positions["Libero"] = st.sidebar.selectbox(
    "Libero",
    valid_libero_options,
    index=libero_index,
    key="pos_libero"
)

# Verifica formazione
if any(v in [None, ""] for v in st.session_state.positions.values()):
    st.sidebar.warning("Completa la formazione (posizioni 1–6 + Libero).")
else:
    st.sidebar.success("Formazione completa.")

# ==============
# Funzioni di gioco
# ==============
def rotate_team_positions():
    current = st.session_state.positions
    new_positions = {
        1: current[2],
        6: current[1],
        5: current[6],
        4: current[5],
        3: current[4],
        2: current[3],
        "Libero": current["Libero"]
    }
    st.session_state.positions = new_positions

def update_score():
    score = {"A":0,"B":0}
    for _, row in st.session_state.raw.iterrows():
        team = row["Team"]
        action = row["Azione"]
        code = row["Codice"]

        if action in ["ATK","BAT","MU"]:
            if code == "Punto":
                score[team] += 1
            elif code == "Errore":
                other = "B" if team == "A" else "A"
                score[other] += 1
        elif action == "Errore avversario":
            score["A"] += 1
        elif action == "Punto avversario":
            score["B"] += 1
        elif action == "Errore squadra":
            score["B"] += 1
    st.session_state.score = score

update_score()

# =======================
# Campo e fondamentali
# =======================
st.markdown(f"### 🏐 Servizio: **{st.session_state.team_names[st.session_state.service_team]}**")

if all(v not in [None, ""] for v in st.session_state.positions.values()):
    st.subheader("Disposizione in campo (posizioni 1–6)")
    positions_layout = [[4, 3, 2], [5, 6, 1]]

    for row in positions_layout:
        cols = st.columns(3)
        for i, pos in enumerate(row):
            player = st.session_state.positions[pos]
            if player:
                if cols[i].button(
                    f"{pos}: {player}",
                    key=f"player_{player}",
                    use_container_width=True,
                    type="primary" if st.session_state.selected_player == player else "secondary"
                ):
                    st.session_state.selected_player = player
                    st.session_state.selected_action = None
                    safe_rerun()

    libero = st.session_state.positions["Libero"]
    if libero:
        if st.button(
            f"Libero: {libero}",
            key="player_libero",
            use_container_width=True,
            type="primary" if st.session_state.selected_player == libero else "secondary"
        ):
            st.session_state.selected_player = libero
            st.session_state.selected_action = None
            safe_rerun()
else:
    st.info("Imposta tutti i giocatori nelle posizioni per iniziare.")

# =======================
# Eventi generali
# =======================
extra_cols = st.columns(3)

# --- Bottone Avversari ---
if extra_cols[0].button("Avversari", use_container_width=True, type="secondary"):
    st.session_state.selected_player = "Avversari"
    st.session_state.selected_action = None
    safe_rerun()

# --- Errore squadra ---
if extra_cols[2].button("Errore squadra", use_container_width=True):
    st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([{
        "Set": st.session_state.current_set,
        "PointNo": len(st.session_state.raw) + 1,
        "Team": "B",
        "Giocatore": "Evento Generale",
        "Azione": "Errore squadra",
        "Codice": "",
        "Note": ""
    }])], ignore_index=True)
    update_score()
    st.session_state.service_team = "B"
    safe_rerun()

# --- Fondamentali o Avversari ---
if st.session_state.selected_player and st.session_state.selected_player != "Avversari" and not st.session_state.selected_action:
    st.markdown("---")
    actions = list(ACTION_CODES.keys())
    cols_actions = st.columns(len(actions))
    for i, action in enumerate(actions):
        if cols_actions[i].button(action, key=f"action_{st.session_state.selected_player}_{action}", use_container_width=True):
            st.session_state.selected_action = action
            safe_rerun()

elif st.session_state.selected_player == "Avversari":
    st.markdown("---")
    cols_avv = st.columns(2)
    for i, label in enumerate(["Punto", "Errore"]):
        if cols_avv[i].button(label, key=f"avv_{label}", use_container_width=True, type="secondary"):
            if label == "Punto":
                st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([{
                    "Set": st.session_state.current_set,
                    "PointNo": len(st.session_state.raw) + 1,
                    "Team": "B",
                    "Giocatore": "Evento Generale",
                    "Azione": "Punto avversario",
                    "Codice": "",
                    "Note": ""
                }])], ignore_index=True)
                update_score()
                st.session_state.service_team = "B"
            else:
                st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([{
                    "Set": st.session_state.current_set,
                    "PointNo": len(st.session_state.raw) + 1,
                    "Team": "A",
                    "Giocatore": "Evento Generale",
                    "Azione": "Errore avversario",
                    "Codice": "",
                    "Note": ""
                }])], ignore_index=True)
                update_score()
                if st.session_state.service_team != "A":
                    rotate_team_positions()
                    st.session_state.service_team = "A"

            st.session_state.selected_player = None
            st.session_state.selected_action = None
            safe_rerun()

# --- Scelta esito fondamentale ---
if st.session_state.selected_player and st.session_state.selected_action:
    st.markdown("---")
    action = st.session_state.selected_action
    codes = ACTION_CODES[action]
    cols_codes = st.columns(len(codes))
    for i, code in enumerate(codes):
        if cols_codes[i].button(code, key=f"code_{st.session_state.selected_player}_{action}_{code}", use_container_width=True):
            new_row = {
                "Set": st.session_state.current_set,
                "PointNo": len(st.session_state.raw) + 1,
                "Team": "A",
                "Giocatore": st.session_state.selected_player,
                "Azione": action,
                "Codice": code,
                "Note": ""
            }
            st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([new_row])], ignore_index=True)
            update_score()

            if action in ["ATK","BAT","MU"] and code == "Punto":
                if st.session_state.service_team == "A":
                    pass
                else:
                    rotate_team_positions()
                    st.session_state.service_team = "A"
            elif action in ["ATK","BAT","MU"] and code == "Errore":
                if st.session_state.service_team == "B":
                    pass
                else:
                    st.session_state.service_team = "B"

            st.session_state.selected_action = None
            st.session_state.selected_player = None
            safe_rerun()

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
# Tabellini e export
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

st.subheader("Tabellini giocatori")
tabellino = compute_counts(st.session_state.raw)
st.dataframe(tabellino, use_container_width=True)

# === Export Excel ===
st.header("Esporta")
def to_excel_bytes(tabellino, raw_data):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        tabellino.to_excel(writer, index=False)
        raw_data.to_excel(writer, sheet_name="Eventi", index=False)
    return output.getvalue()

excel_data = to_excel_bytes(tabellino, st.session_state.raw)
st.download_button(
    "Scarica Excel (.xlsx)",
    data=excel_data,
    file_name="Volley_Scout_Report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
