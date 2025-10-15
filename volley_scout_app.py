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
    st.session_state.raw = pd.DataFrame(columns=["Set","PointNo","Team","Giocatore","Azione","Codice","Note","Rotazione"])
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

# ---- Roster ----
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
        # reset posizioni e chiavi widget
        for pos in range(1,7):
            st.session_state.pop(f"pos_select_{pos}", None)
        st.session_state.pop("pos_select_libero", None)
        st.session_state.positions = {i: None for i in range(1,7)}
        st.session_state.positions["Libero"] = None
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

# ---- Servizio iniziale ----
st.sidebar.subheader("Servizio iniziale")
service_start = st.sidebar.radio(
    "Chi inizia al servizio?",
    options=["A", "B"],
    format_func=lambda x: st.session_state.team_names[x],
    index=0 if st.session_state.service_team == "A" else 1
)
st.session_state.service_team = service_start

# ---- Formazione (nuova versione stabile) ----
st.sidebar.subheader("Formazione (posizioni 1–6 + Libero)")
available_players = st.session_state.players["Nome"].tolist()

widget_keys = {pos: f"pos_select_{pos}" for pos in range(1,7)}
libero_key = "pos_select_libero"

# inizializza chiavi widget
for pos in range(1,7):
    wk = widget_keys[pos]
    if wk not in st.session_state:
        st.session_state[wk] = st.session_state.positions.get(pos, "") or ""
if libero_key not in st.session_state:
    st.session_state[libero_key] = st.session_state.positions.get("Libero", "") or ""

# selectbox posizioni
for pos in range(1,7):
    current_selections = {p: st.session_state[widget_keys[p]] for p in range(1,7)}
    used_by_others = [v for p,v in current_selections.items() if p != pos and v]
    current_player = st.session_state[widget_keys[pos]]
    valid_options = [""] + [p for p in available_players if (p not in used_by_others) or (p == current_player)]
    index_value = valid_options.index(current_player) if current_player in valid_options else 0
    st.session_state[widget_keys[pos]] = st.sidebar.selectbox(
        f"Posizione {pos}",
        valid_options,
        index=index_value,
        key=widget_keys[pos]
    )

# libero
current_libero = st.session_state[libero_key]
used_by_positions = [st.session_state[widget_keys[p]] for p in range(1,7) if st.session_state[widget_keys[p]]]
valid_libero_options = [""] + [p for p in available_players if (p not in used_by_positions) or p == current_libero]
libero_index = valid_libero_options.index(current_libero) if current_libero in valid_libero_options else 0
st.session_state[libero_key] = st.sidebar.selectbox(
    "Libero",
    valid_libero_options,
    index=libero_index,
    key=libero_key
)

# aggiorna dict positions
for pos in range(1,7):
    st.session_state.positions[pos] = st.session_state.get(widget_keys[pos], "") or ""
st.session_state.positions["Libero"] = st.session_state.get(libero_key, "") or ""

# verifica formazione
if any(v in [None, ""] for v in st.session_state.positions.values()):
    st.sidebar.warning("Completa la formazione (posizioni 1–6 + Libero).")
else:
    st.sidebar.success("Formazione completa.")

# (il resto del file — gestione campo, azioni, eventi, tabellini, export — resta invariato)
