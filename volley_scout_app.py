import streamlit as st
import pandas as pd
import io
import os

st.set_page_config(page_title="Volley Scout", layout="wide")

# =============================
# RERUN COMPATIBILE
# =============================
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

ACTION_CODES = {
    "BAT":  ["Punto", "Buona", "Regolare", "Errore"],
    "RICE": ["Ottima", "Buona", "Regolare", "Scarsa", "Errore"],
    "ATK":  ["Punto", "Buono", "Regolare", "Murato", "Errore"],
    "DIF":  ["Ottima", "Errore"],
    "MU":   ["Punto", "Errore"]
}

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

# =============================
# SESSION STATE INIZIALI
# =============================
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

# =============================
# NUOVA SEZIONE: ROTAZIONI E LIBERO
# =============================
if "lineups" not in st.session_state:
    st.session_state.lineups = {
        "A": {
            "positions": {"1": "P", "2": "S1", "3": "C2", "4": "O", "5": "S2", "6": "L"},
            "libero": "L",
            "centrali": ["C1", "C2"]
        },
        "B": {
            "positions": {"1": "P", "2": "S1", "3": "C2", "4": "O", "5": "S2", "6": "L"},
            "libero": "L",
            "centrali": ["C1", "C2"]
        }
    }

if "serving_team" not in st.session_state:
    st.session_state.serving_team = "A"

def rotate_team(team):
    pos = st.session_state.lineups[team]["positions"]
    new_pos = {
        "1": pos["2"], "2": pos["3"], "3": pos["4"],
        "4": pos["5"], "5": pos["6"], "6": pos["1"]
    }
    st.session_state.lineups[team]["positions"] = new_pos
    update_libero_positions()

def change_service():
    st.session_state.serving_team = "A" if st.session_state.serving_team == "B" else "B"
    update_libero_positions()

def update_libero_positions():
    for team in ["A", "B"]:
        lineup = st.session_state.lineups[team]
        libero = lineup["libero"]
        centrali = lineup["centrali"]
        pos = lineup["positions"]

        centrale_seconda_linea = None
        for p in ["5", "6"]:
            if pos[p] in centrali:
                centrale_seconda_linea = p
                break

        # Ricezione
        if team != st.session_state.serving_team:
            if centrale_seconda_linea:
                pos[centrale_seconda_linea] = libero

        # Battuta
        else:
            if pos["1"] == libero:
                centrale_fuori = [c for c in centrali if c not in pos.values()]
                if centrale_fuori:
                    pos["1"] = centrale_fuori[0]

# =============================
# SIDEBAR: IMPOSTAZIONI
# =============================
st.sidebar.header("Impostazioni partita")
st.sidebar.subheader("Roster")

uploaded_roster = st.sidebar.file_uploader(
    "Carica roster.xlsx (Numero, Nome, Ruolo)",
    type=["xlsx"], accept_multiple_files=False
)
if uploaded_roster is not None:
    df_loaded = load_roster_from_upload(uploaded_roster)
    if df_loaded is not None:
        st.session_state.players = df_loaded
        st.sidebar.success(f"Roster caricato: {len(df_loaded)} giocatori")
        valid_names = set(st.session_state.players["Nome"].tolist())
        st.session_state.field_players = [p for p in st.session_state.field_players if p in valid_names]

template_bytes = df_to_excel_bytes(default_roster_df(), sheet_name="Roster")
st.sidebar.download_button("Scarica template roster.xlsx", data=template_bytes,
    file_name="roster_template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# =============================
# VISUALIZZAZIONE ROTAZIONI
# =============================
st.markdown("## 🏐 Rotazioni e Libero")

colA, colB = st.columns(2)
with colA:
    st.write(f"**Squadra A** ({st.session_state.team_names['A']})")
    for p in ["1","2","3","4","5","6"]:
        st.write(f"Posto {p}: {st.session_state.lineups['A']['positions'][p]}")
    if st.button("Ruota A"):
        rotate_team("A")

with colB:
    st.write(f"**Squadra B** ({st.session_state.team_names['B']})")
    for p in ["1","2","3","4","5","6"]:
        st.write(f"Posto {p}: {st.session_state.lineups['B']['positions'][p]}")
    if st.button("Ruota B"):
        rotate_team("B")

st.markdown("---")
st.write(f"**Squadra al servizio:** {st.session_state.serving_team}")
if st.button("Cambia servizio"):
    change_service()

st.caption("Il libero entra automaticamente per il centrale in seconda linea e rientra il centrale al servizio.")

# =======================
# Flusso: 7 giocatori → fondamentale → score
# =======================

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
    # Rotazione se punto per Team A su ATK/BAT/MU
    if action in ["ATK", "BAT", "MU"] and code == "Punto" and team == "A":
        rotate_team()
    # Torna alla riga dei giocatori
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
        # Se vuoi, puoi esportare anche il raw:
        # raw_data.to_excel(writer, sheet_name="Raw", index=False)
    return output.getvalue()

excel_data = to_excel_bytes(tabellino, st.session_state.raw)
st.download_button(
    "Scarica Excel (.xlsx)",
    data=excel_data,
    file_name="Volley_Scout_Report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
