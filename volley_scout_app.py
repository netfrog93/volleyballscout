import streamlit as st
import pandas as pd
import io
import os

# =========================================================
# CONFIGURAZIONE BASE
# =========================================================
st.set_page_config(page_title="Volley Scout", layout="wide")

def safe_rerun():
    """Compatibilità rerun tra versioni di Streamlit"""
    rerun = getattr(st, "rerun", None)
    if callable(rerun):
        return rerun()
    exp_rerun = getattr(st, "experimental_rerun", None)
    if callable(exp_rerun):
        return exp_rerun()
    st.warning("La tua versione di Streamlit non supporta il rerun automatico.")


# =========================================================
# COSTANTI E VARIABILI GLOBALI
# =========================================================
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

# =========================================================
# INIZIALIZZAZIONE SESSION STATE
# =========================================================
def init_session_state():
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
        st.session_state.team_names = {"A": "SMV", "B": "Squadra B"}
    if "score" not in st.session_state:
        st.session_state.score = {"A": 0, "B": 0}
    if "selected_player" not in st.session_state:
        st.session_state.selected_player = None
    if "selected_action" not in st.session_state:
        st.session_state.selected_action = None
    if "service_team" not in st.session_state:
        st.session_state.service_team = "A"


# =========================================================
# FUNZIONI DI SUPPORTO
# =========================================================
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
        st.sidebar.error("Colonne mancanti: " + ", ".join(missing))
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

def rotate_team_positions():
    current = st.session_state.positions
    st.session_state.positions = {
        1: current[2],
        6: current[1],
        5: current[6],
        4: current[5],
        3: current[4],
        2: current[3],
        "Libero": current["Libero"]
    }

def get_palleggiatrice_posizione():
    palleggiatrici = st.session_state.players.query("Ruolo == 'PALLEGGIATRICE'")["Nome"].tolist()
    if not palleggiatrici:
        return ""
    palleggiatrice = palleggiatrici[0]
    for pos, nome in st.session_state.positions.items():
        if nome == palleggiatrice and isinstance(pos, int):
            return f"P{pos}"
    return ""

def update_score():
    score = {"A": 0, "B": 0}
    for _, row in st.session_state.raw.iterrows():
        team, action, code = row["Team"], row["Azione"], row["Codice"]
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


# =========================================================
# BLOCCO 1 – SIDEBAR
# =========================================================
def sidebar_block():
    st.sidebar.header("Impostazioni partita")

    uploaded_roster = st.sidebar.file_uploader(
        "Carica roster.xlsx (Numero, Nome, Ruolo)",
        type=["xlsx"], accept_multiple_files=False
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

    st.sidebar.subheader("Squadre")
    st.session_state.team_names["A"] = st.sidebar.text_input("Squadra A", value=st.session_state.team_names["A"])
    st.session_state.team_names["B"] = st.sidebar.text_input("Squadra B", value=st.session_state.team_names["B"])

    st.sidebar.subheader("Set attuale")
    st.session_state.current_set = st.sidebar.number_input(
        "Seleziona Set", min_value=1, max_value=SETS, value=st.session_state.current_set, step=1
    )

    st.sidebar.subheader("Servizio iniziale")
    st.session_state.service_team = st.sidebar.radio(
        "Chi serve per primo?",
        ["A", "B"],
        format_func=lambda x: st.session_state.team_names[x],
        index=0 if st.session_state.service_team == "A" else 1
    )

    st.sidebar.subheader("Formazione (posizioni 1–6 + Libero)")
    available_players = st.session_state.players["Nome"].tolist()
    used = [p for p in st.session_state.positions.values() if p]

    for pos in range(1, 7):
        valid_options = [""] + [p for p in available_players if p not in used or p == st.session_state.positions[pos]]
        st.session_state.positions[pos] = st.sidebar.selectbox(f"Posizione {pos}", valid_options, key=f"pos_{pos}")

    valid_libero_options = [""] + [p for p in available_players if p not in used or p == st.session_state.positions["Libero"]]
    st.session_state.positions["Libero"] = st.sidebar.selectbox("Libero", valid_libero_options, key="pos_libero")

    if any(v in [None, ""] for v in st.session_state.positions.values()):
        st.sidebar.warning("Completa la formazione (posizioni 1–6 + Libero)")
    else:
        st.sidebar.success("Formazione completa.")


# =========================================================
# BLOCCO 2 – CAMPO E FONDAMENTALI
# =========================================================
def field_block():
    rotazione_p = get_palleggiatrice_posizione()
    st.markdown(f"### 🏐 Servizio: **{st.session_state.team_names[st.session_state.service_team]}** · Rotazione: **{rotazione_p or '-'}**")

    if all(v not in [None, ""] for v in st.session_state.positions.values()):
        st.subheader("Disposizione in campo (posizioni 1–6)")
        positions_layout = [[4, 3, 2], [5, 6, 1]]
        for row in positions_layout:
            cols = st.columns(3)
            for i, pos in enumerate(row):
                player = st.session_state.positions[pos]
                if player and cols[i].button(
                    f"{pos}: {player}",
                    key=f"player_{player}",
                    use_container_width=True,
                    type="primary" if st.session_state.selected_player == player else "secondary"
                ):
                    st.session_state.selected_player = player
                    st.session_state.selected_action = None
                    safe_rerun()

        libero = st.session_state.positions["Libero"]
        if libero and st.button(
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


# =========================================================
# BLOCCO 3 – EVENTI E PUNTEGGI
# =========================================================
def events_block():
    update_score()

    # Mostra i pulsanti solo se la formazione è completa
    if any(v in [None, ""] for v in st.session_state.positions.values()):
        return

    extra_cols = st.columns(3)

    if extra_cols[0].button("Avversari", use_container_width=True):
        st.session_state.selected_player = "Avversari"
        st.session_state.selected_action = None
        safe_rerun()

    if extra_cols[2].button("Errore squadra", use_container_width=True):
        rot = get_palleggiatrice_posizione()
        new_row = {
            "Set": st.session_state.current_set,
            "PointNo": len(st.session_state.raw) + 1,
            "Team": "B",
            "Giocatore": "Evento Generale",
            "Azione": "Errore squadra",
            "Codice": "",
            "Note": "",
            "Rotazione": rot
        }
        st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([new_row])], ignore_index=True)
        update_score()
        st.session_state.service_team = "B"
        safe_rerun()

    # Azioni fondamentali
    if st.session_state.selected_player and st.session_state.selected_player != "Avversari" and not st.session_state.selected_action:
        st.markdown("---")
        cols = st.columns(len(ACTION_CODES))
        for i, action in enumerate(ACTION_CODES.keys()):
            if cols[i].button(action, key=f"action_{action}", use_container_width=True):
                st.session_state.selected_action = action
                safe_rerun()

    # Azioni avversari
    elif st.session_state.selected_player == "Avversari":
        st.markdown("---")
        cols = st.columns(2)
        for i, label in enumerate(["Punto", "Errore"]):
            if cols[i].button(label, key=f"avv_{label}", use_container_width=True):
                rot = get_palleggiatrice_posizione()
                team, azione = ("B", "Punto avversario") if label == "Punto" else ("A", "Errore avversario")
                new_row = {
                    "Set": st.session_state.current_set,
                    "PointNo": len(st.session_state.raw) + 1,
                    "Team": team,
                    "Giocatore": "Evento Generale",
                    "Azione": azione,
                    "Codice": "",
                    "Note": "",
                    "Rotazione": rot if team == "A" else ""
                }
                st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([new_row])], ignore_index=True)
                update_score()
                if label == "Punto":
                    st.session_state.service_team = "B"
                else:
                    rotate_team_positions()
                    st.session_state.service_team = "A"
                st.session_state.selected_action = None
                st.session_state.selected_player = None
                safe_rerun()

    # Esito fondamentali
    if st.session_state.selected_player and st.session_state.selected_action:
        st.markdown("---")
        action = st.session_state.selected_action
        cols = st.columns(len(ACTION_CODES[action]))
        for i, code in enumerate(ACTION_CODES[action]):
            if cols[i].button(code, key=f"code_{code}", use_container_width=True):
                rot = get_palleggiatrice_posizione()
                new_row = {
                    "Set": st.session_state.current_set,
                    "PointNo": len(st.session_state.raw) + 1,
                    "Team": "A",
                    "Giocatore": st.session_state.selected_player,
                    "Azione": action,
                    "Codice": code,
                    "Note": "",
                    "Rotazione": rot
                }
                st.session_state.raw = pd.concat([st.session_state.raw, pd.DataFrame([new_row])], ignore_index=True)
                update_score()

                if action in ["ATK","BAT","MU"] and code == "Punto":
                    if st.session_state.service_team != "A":
                        rotate_team_positions()
                        st.session_state.service_team = "A"
                elif action in ["ATK","BAT","MU"] and code == "Errore":
                    st.session_state.service_team = "B"

                st.session_state.selected_action = None
                st.session_state.selected_player = None
                safe_rerun()


# =========================================================
# BLOCCO 4 – EVENTI REGISTRATI
# =========================================================
def recorded_block():
    st.subheader("Eventi registrati")
    if not st.session_state.raw.empty:
        for idx, row in st.session_state.raw.iterrows():
            cols = st.columns([4,1])
            cols[0].write(
                f"{row['Set']} | {row['PointNo']} | {st.session_state.team_names[row['Team']]} | "
                f"{row['Giocatore']} | {row['Azione']} | {row['Codice']} | {row['Rotazione']}"
            )
            if cols[1].button("Elimina", key=f"del_{idx}", use_container_width=True):
                st.session_state.raw.drop(idx, inplace=True)
                st.session_state.raw.reset_index(drop=True, inplace=True)
                update_score()
                safe_rerun()


# =========================================================
# BLOCCO 5 – TABELLINI E EXPORT
# =========================================================
def stats_block():
    st.subheader("Tabellini giocatori")

    players = st.session_state.players["Nome"].tolist()
    columns = []
    for act, codes in ACTION_CODES.items():
        for c in codes:
            columns.append(f"{act}_{c}")
        columns.append(f"{act}_Tot")

    data = pd.DataFrame(0, index=players, columns=columns)
    for _, row in st.session_state.raw.iterrows():
        g, act, code = row["Giocatore"], row["Azione"], row["Codice"]
        col = f"{act}_{code}"
        if g in data.index and col in data.columns:
            data.at[g, col] += 1

    for act, codes in ACTION_CODES.items():
        code_cols = [f"{act}_{c}" for c in codes]
        data[f"{act}_Tot"] = data[code_cols].sum(axis=1)

    st.dataframe(data, use_container_width=True)

    st.header("Esporta")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        data.to_excel(writer, index=True, sheet_name="Tabellini")
        st.session_state.raw.to_excel(writer, index=False, sheet_name="Eventi")

    st.download_button(
        "Scarica Excel (.xlsx)",
        data=output.getvalue(),
        file_name="Volley_Scout_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# =========================================================
# MAIN
# =========================================================
def main():
    init_session_state()
    sidebar_block()
    field_block()
    events_block()
    recorded_block()
    stats_block()

if __name__ == "__main__":
    main()
