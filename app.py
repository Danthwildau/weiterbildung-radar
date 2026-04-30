"""
Weiterbildungs-Radar — TH Wildau
Analysewerkzeug für Lehrende: Angebot, Nachfrage und Preisgestaltung.
"""

import re
import json
import math
import warnings
from collections import defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="Weiterbildungs-Radar · TH Wildau",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA = Path(__file__).parent / "data"

REGIONS_DISPLAY = {
    "TH Wildau Region": ["Dahme-Spreewald", "Oder-Spree", "Teltow-Fläming"],
    "Berlin":           ["Berlin"],
    "Brandenburg":      ["Brandenburg"],
    "Deutschland":      ["Deutschland"],
}
REGION_ORDER = ["TH Wildau Region", "Berlin", "Brandenburg", "Deutschland"]

CAT_COLS = [
    "PGT_effektive_Verwaltung",
    "PGT_effektive_Verwaltung_oeffentlich",
    "PGT_zukunftsfaehige_Mobilitaet",
    "PGT_nachhaltige_Wertschoepfung",
    "QST_Diversity",
    "QST_Nachhaltigkeit",
    "QST_Internationalisation",
]
CAT_LABELS = {
    "PGT_effektive_Verwaltung":             "Effektive Verwaltung",
    "PGT_effektive_Verwaltung_oeffentlich": "Effektive Verwaltung (öffentlich)",
    "PGT_zukunftsfaehige_Mobilitaet":       "Zukunftsfähige Mobilität",
    "PGT_nachhaltige_Wertschoepfung":       "Nachhaltige Wertschöpfung",
    "QST_Diversity":                        "QST: Diversity",
    "QST_Nachhaltigkeit":                   "QST: Nachhaltigkeit",
    "QST_Internationalisation":             "QST: Internationalisation",
}

PREIS_LABELS = {
    "BIS_500_EUR":              "bis 500 €",
    "UEBER_500_BIS_1000_EUR":   "500 – 1.000 €",
    "UEBER_1000_BIS_5000_EUR":  "1.000 – 5.000 €",
    "UEBER_5000_BIS_10000_EUR": "5.000 – 10.000 €",
    "UEBER_10000_EUR":          "über 10.000 €",
}

KLDB_TOPICS = {
    "11":["landwirt","forst","agrar","garten","tier"],
    "21":["bergbau","mineral","glas","keramik"],
    "22":["holz","papier","druck","möbel"],
    "23":["kunststoff","kautschuk","chemie"],
    "24":["metall","stahl","schweiss","giesser"],
    "25":["maschinen","mechatronik","industrie","automatisierung","fertigungs"],
    "26":["elektro","elektronik","energie"],
    "27":["textil","bekleidung","leder"],
    "28":["lebensmittel","küche","gastronomie","hotel"],
    "29":["bau","hochbau","tiefbau","architektur"],
    "31":["ingenieur","konstruktion","planung","bau","architektur"],
    "32":["naturwissenschaft","physik","chemie","biologie","labor"],
    "41":["informatik","software","programmier","data","ki","digital"],
    "43":["it","cyber","cloud","netzwerk","devops","entwickler"],
    "51":["lager","logistik","transport","spedition"],
    "52":["schutz","sicherheit","feuerwehr"],
    "53":["reinigung","hauswirtschaft"],
    "61":["verkauf","marketing","vertrieb","handel"],
    "62":["einzelhandel","kaufmann","kauffrau"],
    "71":["büro","verwaltung","management","projekt"],
    "72":["finanz","steuer","versicherung","bank","controlling"],
    "73":["recht","jurist","notar","anwalt"],
    "81":["gesundheit","pflege","medizin","klinik","kranken"],
    "82":["alten","sozial","pflege"],
    "83":["pädagog","erzieh","sozialarbeit","kind"],
    "84":["lehrer","bildung","ausbildung","weiterbildung"],
    "91":["sport","fitness","gesundheitsförder"],
    "92":["dienstleist","service","beratung"],
    "93":["medien","gestaltung","design","kunst","kultur"],
    "94":["sprach","dolmetsch","übersetz"],
}

# ─── DATA LOADING ─────────────────────────────────────────────────────────

@st.cache_data
def load_offers():
    df = pd.read_csv(DATA / "offers.csv")
    for c in CAT_COLS:
        if c in df.columns:
            df[c] = df[c].fillna(False).astype(bool)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    return df

@st.cache_data
def load_demand():
    df = pd.read_csv(DATA / "demand_2025.csv")
    df["kldb_id"] = df["kldb_id"].astype(int)
    return df

@st.cache_data
def load_berufe():
    df = pd.read_csv(DATA / "berufe.csv")
    df["kldb_id"] = df["kldb_id"].astype(int)
    df["kldb_prefix2"] = df["kldb_id"].astype(str).str[:2]
    return df

@st.cache_data
def load_knowledge_groups():
    with open(DATA / "knowledge_groups.json", encoding="utf-8") as f:
        return json.load(f)

# ─── MATCHING LOGIC ──────────────────────────────────────────────────────

def match_offers(offers, user_text, selected_cats, kg, n=50):
    user_words = set(re.findall(r'\b\w{4,}\b', user_text.lower()))
    user_stems = {w[:5] for w in user_words}
    scores = []
    for _, row in offers.iterrows():
        s = 0.0
        row_text = (str(row.get("title","")) + " " + str(row.get("description",""))).lower()
        row_words = set(re.findall(r'\b\w{4,}\b', row_text))
        row_stems = {w[:5] for w in row_words}
        s += len(user_words & row_words) * 2.0
        s += len(user_stems & row_stems) * 1.0
        for cat in selected_cats:
            if row.get(cat, False):
                s += 3.0
        if kg and str(row.get("knowledgeGroup","")) == kg:
            s += 2.0
        scores.append(s)
    offers = offers.copy()
    offers["_score"] = scores
    return offers[offers["_score"] > 0].sort_values("_score", ascending=False).head(n)

def match_berufe_to_text(berufe_df, user_text, n=15):
    user_words = set(re.findall(r'\b\w{4,}\b', user_text.lower()))
    user_stems = {w[:5] for w in user_words}
    scores = defaultdict(float)
    for _, row in berufe_df.iterrows():
        beruf_lower = row["beruf_name"].lower()
        beruf_words = set(re.findall(r'\b\w{4,}\b', beruf_lower))
        beruf_stems = {w[:5] for w in beruf_words}
        s  = len(user_words & beruf_words) * 2.0
        s += len(user_stems & beruf_stems) * 1.5
        topic_words = KLDB_TOPICS.get(row["kldb_prefix2"], [])
        for tw in topic_words:
            for uw in user_words:
                if tw in uw or uw in tw:
                    s += 0.5
                    break
        if s > 0:
            scores[row["beruf_name"]] = s
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:n]
    result = []
    for beruf, sc in ranked:
        row = berufe_df[berufe_df["beruf_name"] == beruf].iloc[0]
        result.append({"beruf_name": beruf, "kldb_id": int(row["kldb_id"]),
                        "kldb_prefix2": row["kldb_prefix2"], "score": sc})
    return result

def expand_berufe(berufe_df, selected_names, all_selected_names, n=20):
    """Find related professions. all_selected_names = everything already shown."""
    sel_rows = berufe_df[berufe_df["beruf_name"].isin(selected_names)]
    sel_prefixes = set(sel_rows["kldb_prefix2"].tolist())
    sel_words = set()
    for name in selected_names:
        sel_words |= set(re.findall(r'\b\w{4,}\b', name.lower()))
    sel_stems = {w[:5] for w in sel_words}
    scores = defaultdict(float)
    for _, row in berufe_df.iterrows():
        if row["beruf_name"] in all_selected_names:
            continue
        bwords = set(re.findall(r'\b\w{4,}\b', row["beruf_name"].lower()))
        bstems = {w[:5] for w in bwords}
        if row["kldb_prefix2"] in sel_prefixes:
            scores[row["beruf_name"]] += 3.0
        scores[row["beruf_name"]] += len(sel_stems & bstems) * 1.5
    ranked = sorted([(b, s) for b, s in scores.items() if s > 0], key=lambda x: -x[1])[:n]
    result = []
    for beruf, sc in ranked:
        row = berufe_df[berufe_df["beruf_name"] == beruf].iloc[0]
        result.append({"beruf_name": beruf, "kldb_id": int(row["kldb_id"]),
                        "kldb_prefix2": row["kldb_prefix2"], "score": sc})
    return result

# ─── SCORING ─────────────────────────────────────────────────────────────

def angebots_score(n):
    if n == 0:  return 1,  "Kaum Angebot vorhanden — Lücke im Markt."
    if n <= 3:  return 3,  "Sehr geringes Angebot — gute Marktchance."
    if n <= 8:  return 5,  "Moderates Angebot — Differenzierung empfehlenswert."
    if n <= 20: return 7,  "Angebot vorhanden — klares Profil nötig."
    if n <= 40: return 9,  "Starkes Angebot — Nische oder USP wichtig."
    return 10, "Sehr gesättigter Markt — Positionierung entscheidend."

def nachfrage_score(demand, kldb_ids, region_names):
    sub = demand[demand["kldb_id"].isin(kldb_ids) & demand["region"].isin(region_names)]
    if sub.empty:
        return 1, "Keine Nachfragedaten für diese Berufe."
    median_growth = sub["percentage_diff_previous_year"].median()
    total_jobs    = sub["total_jobs"].sum()
    if pd.isna(median_growth):
        return 3, "Unzureichende Daten."
    growth_score = min(10, max(1, int((median_growth * 100 + 5) * 1.2)))
    size_bonus   = min(2, math.log10(max(total_jobs, 1)) / 3)
    final        = min(10, max(1, round(growth_score + size_bonus)))
    trend = "wachsend" if median_growth > 0.05 else "stabil" if median_growth > -0.05 else "rückläufig"
    return final, (f"Trend: {trend}  ·  Wachstum: {median_growth*100:+.1f}%  ·  "
                   f"Gesamtstellen: {int(total_jobs):,}")

# ─── UI HELPERS ──────────────────────────────────────────────────────────

def score_badge(score, label):
    color = "#0f6e56" if score <= 4 else "#854f0b" if score <= 7 else "#9b1c1c"
    bg    = "#e1f5ee" if score <= 4 else "#faeeda" if score <= 7 else "#fee2e2"
    st.markdown(
        f'<div style="display:inline-flex;align-items:center;gap:12px;'
        f'background:{bg};border-radius:10px;padding:12px 20px;margin:6px 0">'
        f'<span style="font-size:2.2rem;font-weight:700;color:{color};line-height:1">{score}/10</span>'
        f'<span style="color:{color};font-size:0.9rem;max-width:300px;line-height:1.4">{label}</span></div>',
        unsafe_allow_html=True,
    )

def beruf_selector(label, options, default_selected, key):
    """
    Full-width portrait selector for Berufsgruppen.
    Returns list of selected names.
    """
    st.markdown(f"**{label}**")
    st.caption("Bitte auswählen, welche Berufsgruppen für Ihren Kurs relevant sind.")

    if key not in st.session_state:
        st.session_state[key] = set(default_selected)

    selected = st.session_state[key]

    # Render as full-width toggle buttons in a single column
    cols_per_row = 1 if len(options) <= 10 else 2
    rows = [options[i:i+cols_per_row] for i in range(0, len(options), cols_per_row)]

    for row_items in rows:
        cols = st.columns(cols_per_row)
        for col, beruf in zip(cols, row_items):
            is_sel = beruf in selected
            bg = "#e1f5ee" if is_sel else "transparent"
            border = "#0f6e56" if is_sel else "#ccc"
            check = "Ausgewählt" if is_sel else "Hinzufügen"
            if col.button(
                f"{'[x] ' if is_sel else '[ ] '}{beruf}",
                key=f"{key}_{beruf}",
                use_container_width=True,
            ):
                if beruf in selected:
                    selected.discard(beruf)
                else:
                    selected.add(beruf)
                st.session_state[key] = selected
                st.rerun()

    return list(st.session_state[key])

# ─── PHASE 0: ECKPUNKTE ──────────────────────────────────────────────────

def phase_0(kgs):
    st.header("Schritt 1: Kursidee beschreiben")

    c1, c2 = st.columns([3, 2])
    with c1:
        title = st.text_input(
            "Kurstitel (Idee oder Arbeitstitel)",
            placeholder="z.B. Zertifikatskurs Digitale Verwaltung für Kommunen",
        )
        description = st.text_area(
            "Kurzbeschreibung / Lernziele",
            placeholder="Was sollen Teilnehmer lernen? Welche Kompetenzen werden vermittelt?",
            height=110,
        )
        keywords = st.text_input(
            "Weitere Stichworte (optional)",
            placeholder="z.B. DSGVO, Datenschutz, E-Government",
        )
    with c2:
        kg = st.selectbox("Wissensgebiet", ["(bitte wählen)"] + kgs)
        selected_cats = st.multiselect(
            "Thematische Schwerpunkte",
            options=list(CAT_LABELS.keys()),
            format_func=lambda x: CAT_LABELS[x],
        )
        fmt = st.selectbox("Format",
            ["Online / Digital", "Hybrid / Blended", "Präsenz", "Noch offen"])
        degree = st.selectbox("Abschluss",
            ["Zertifikat","Microcredential","Hochschulzertifikat",
             "Weiterbildungsmaster","Sonstiges"])

    st.write("---")
    c3, c4, c5, c6 = st.columns(4)
    ects       = c3.number_input("ECTS", min_value=0, max_value=120, value=5)
    hours      = c4.number_input("Workload (Stunden)", min_value=0, value=60, step=10)
    months     = c5.number_input("Dauer (Monate)", min_value=1, value=3)
    target_tn  = c6.number_input("Geplante TN-Zahl", min_value=1, value=15, step=5)

    with st.expander("Kosteninputs für Preiskalkulation (optional)"):
        cc1, cc2, cc3, cc4 = st.columns(4)
        dev_h      = cc1.number_input("Entwicklungsstunden", value=40, step=5)
        dev_rate   = cc2.number_input("Stundensatz Entwicklung (EUR)", value=80, step=5)
        impl_h     = cc3.number_input("Implementierungsstunden", value=20, step=5)
        impl_rate  = cc4.number_input("Stundensatz Impl. (EUR)", value=60, step=5)
        sc1, sc2   = st.columns(2)
        sachkosten = sc1.number_input("Sachkosten pro TN (EUR)", value=50, step=10)
        overhead   = sc2.number_input("Overhead (%)", value=10.0, step=1.0) / 100

    return {
        "title": title, "description": description, "keywords": keywords,
        "user_text": f"{title} {description} {keywords}".strip(),
        "kg": kg if kg != "(bitte wählen)" else "",
        "selected_cats": selected_cats, "format": fmt, "degree": degree,
        "ects": ects, "hours": hours, "months": months, "target_tn": target_tn,
        "dev_h": dev_h, "dev_rate": dev_rate, "impl_h": impl_h,
        "impl_rate": impl_rate, "sachkosten": sachkosten, "overhead": overhead,
    }

# ─── PHASE 1: ANGEBOT ────────────────────────────────────────────────────

def phase_1(offers, params):
    st.header("Schritt 2: Angebot analysieren")
    if not params["user_text"].strip():
        st.info("Bitte erst Kurstitel und Beschreibung eingeben.")
        return None

    with st.spinner("Ähnliche Angebote werden gesucht..."):
        matched = match_offers(offers, params["user_text"],
                               params["selected_cats"], params["kg"])

    score, score_text = angebots_score(len(matched))
    col_sc, col_info = st.columns([1, 3])
    with col_sc:
        st.markdown("**Angebots-Score**")
        score_badge(score, score_text)
    with col_info:
        st.markdown(f"{len(matched)} ähnliche Angebote von {len(offers):,} gefunden. "
                    f"Score 1 = wenig Wettbewerb, 10 = stark gesättigter Markt.")

    st.write("---")

    tab_local, tab_regional, tab_national = st.tabs([
        "Lokal (TH Wildau Region)",
        "Regional (Berlin-Brandenburg)",
        "National",
    ])

    def show_tab(df_geo, geo_label):
        online = matched[matched["format"].str.contains(
            "Digital|Online|Combined|Blended|Fern", case=False, na=False)]
        combined = pd.concat([df_geo, online]).drop_duplicates(subset=["id"])
        st.caption(f"{len(combined)} Angebote ({len(df_geo)} {geo_label} + {len(online)} online/flexibel)")
        if combined.empty:
            st.info("Keine passenden Angebote für diese Region.")
            return

        priced = combined.dropna(subset=["price"])
        if len(priced) >= 3:
            fig = px.box(priced, y="price", points="outliers",
                title="Preisverteilung ähnlicher Kurse",
                labels={"price": "Preis (EUR)"},
                color_discrete_sequence=["#185fa5"], height=280)
            fig.update_layout(margin=dict(t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
            m1, m2, m3 = st.columns(3)
            m1.metric("Median", f"{priced['price'].median():,.0f} EUR")
            m2.metric("25. Perz.", f"{priced['price'].quantile(0.25):,.0f} EUR")
            m3.metric("75. Perz.", f"{priced['price'].quantile(0.75):,.0f} EUR")

        st.subheader("Top 10 ähnliche Angebote")
        top10 = combined.head(10).copy()

        def format_price(row):
            if row.get("price_band") and str(row.get("price_band","")) in PREIS_LABELS:
                return PREIS_LABELS[str(row["price_band"])]
            if pd.notna(row.get("price")):
                return f"{row['price']:,.0f} EUR"
            return "k.A."

        def format_link(row):
            url = str(row.get("url",""))
            if url.startswith("http"):
                label = "Kurs aufrufen" if "hochschulweiterbildung" in url else "Anbieter"
                return f'<a href="{url}" target="_blank">{label}</a>'
            return "—"

        top10["Preis_fmt"]  = top10.apply(format_price, axis=1)
        top10["Link_fmt"]   = top10.apply(format_link, axis=1)

        st.write(
            top10[["title","provider","format","Preis_fmt","Link_fmt"]]
            .rename(columns={"title":"Titel","provider":"Anbieter",
                              "format":"Format","Preis_fmt":"Preis","Link_fmt":"Link"})
            .to_html(escape=False, index=False),
            unsafe_allow_html=True,
        )

    with tab_local:
        show_tab(matched[matched["geo_tier"] == "wildau"], "lokale")
    with tab_regional:
        show_tab(matched[matched["geo_tier"].isin(["berlin_bb","wildau"])], "BB/Berlin")
    with tab_national:
        show_tab(matched, "nationale")

    return matched

# ─── PHASE 2: NACHFRAGE ──────────────────────────────────────────────────

def phase_2(berufe_df, demand, params):
    st.header("Schritt 3: Nachfrage und Zielgruppe")
    if not params["user_text"].strip():
        st.info("Bitte erst Kurstitel und Beschreibung eingeben.")
        return []

    # ── 3a: Initial suggestions ──────────────────────────────────────
    st.subheader("3a. Mögliche Zielgruppen-Berufe")
    st.write(
        "Das Werkzeug hat anhand Ihres Kurstitels und Ihrer Beschreibung die folgenden "
        "Berufsbilder als potenzielle Zielgruppen identifiziert. "
        "Bitte wählen Sie die zutreffenden aus — und entfernen Sie alle, die nicht passen."
    )

    suggestions = match_berufe_to_text(berufe_df, params["user_text"], n=15)
    if not suggestions:
        st.warning("Keine passenden Berufe gefunden. Bitte Beschreibung ergänzen.")
        return []

    suggested_names = [s["beruf_name"] for s in suggestions]

    # Full-width multiselect — shows complete names
    selected_initial = st.multiselect(
        "Relevante Berufsgruppen (alle passenden anklicken):",
        options=suggested_names,
        default=suggested_names[:5],
        key="ms_initial",
    )

    if not selected_initial:
        st.info("Bitte mindestens eine Berufsgruppe auswählen, um fortzufahren.")
        return []

    # Show selected as readable tags
    st.markdown("**Ausgewählt:**")
    tags_html = " ".join(
        f'<span style="display:inline-block;background:#e1f5ee;color:#085041;'
        f'border-radius:6px;padding:3px 10px;margin:2px;font-size:13px">{b}</span>'
        for b in selected_initial
    )
    st.markdown(tags_html, unsafe_allow_html=True)

    # ── 3b: Expand ───────────────────────────────────────────────────
    st.write("---")
    st.subheader("3b. Weitere verwandte Berufsgruppen")
    st.write(
        "Basierend auf Ihrer Auswahl wurden weitere verwandte Berufsbilder identifiziert. "
        "Fügen Sie weitere hinzu, die für Ihren Kurs relevant sein könnten."
    )

    expanded = expand_berufe(berufe_df, selected_initial, suggested_names, n=20)
    expanded_names = [e["beruf_name"] for e in expanded]

    selected_expanded = st.multiselect(
        "Weitere Berufsgruppen hinzufügen (optional):",
        options=expanded_names,
        default=[],
        key="ms_expanded",
    )

    all_selected = selected_initial + selected_expanded

    # Summary of full target group
    st.markdown(f"**Gesamte Zielgruppe: {len(all_selected)} Berufsbilder**")
    all_tags = " ".join(
        f'<span style="display:inline-block;background:#e6f1fb;color:#0c447c;'
        f'border-radius:6px;padding:3px 10px;margin:2px;font-size:13px">{b}</span>'
        for b in all_selected
    )
    st.markdown(all_tags, unsafe_allow_html=True)

    # ── 3c: Demand analysis ──────────────────────────────────────────
    st.write("---")
    st.subheader("3c. Nachfrageentwicklung für Ihre Zielgruppe")

    all_kldb = (
        berufe_df[berufe_df["beruf_name"].isin(all_selected)]["kldb_id"]
        .astype(int).tolist()
    )

    demand_sub = demand[demand["kldb_id"].isin(all_kldb)]

    if demand_sub.empty:
        st.warning(
            "Keine Nachfragedaten für die gewählten Berufe gefunden. "
            "Möglicherweise sind diese Berufsbilder in der Jobmonitor-Datenbank "
            "unter einem anderen Namen erfasst."
        )
        return all_kldb

    # Score
    local_regions = (REGIONS_DISPLAY["TH Wildau Region"] +
                     REGIONS_DISPLAY["Berlin"] + REGIONS_DISPLAY["Brandenburg"])
    nd_score, nd_text = nachfrage_score(demand_sub, all_kldb, local_regions)

    col_sc2, col_info2 = st.columns([1, 3])
    with col_sc2:
        st.markdown("**Nachfrage-Score**")
        score_badge(nd_score, nd_text)
    with col_info2:
        st.caption("Score 1 = geringe/sinkende Nachfrage  ·  Score 10 = stark wachsend")

    # Regional bar chart
    region_rows = []
    for display_name, db_regions in REGIONS_DISPLAY.items():
        sub = demand_sub[demand_sub["region"].isin(db_regions)]
        if sub.empty:
            continue
        total    = sub["total_jobs"].sum()
        diff     = sub["total_diff_previous_year"].sum()
        prior    = total - diff
        pct      = diff / prior if prior > 0 else 0
        region_rows.append({"Region": display_name, "Stellen": int(total),
                             "Wachstum_%": round(pct * 100, 1)})

    if region_rows:
        rdf = pd.DataFrame(region_rows)
        rdf = rdf.set_index("Region").reindex(REGION_ORDER).dropna().reset_index()
        rdf["Farbe"] = rdf["Wachstum_%"].apply(
            lambda x: "#27ae60" if x > 5 else "#f39c12" if x > -5 else "#c0392b")
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=rdf["Region"], y=rdf["Wachstum_%"],
            marker_color=rdf["Farbe"],
            text=rdf["Wachstum_%"].apply(lambda x: f"{x:+.1f}%"),
            textposition="outside",
        ))
        fig_bar.update_layout(
            title="Nachfragewachstum 2024 → 2025 nach Region",
            yaxis_title="Wachstum (%)",
            xaxis_title="",
            height=320,
            margin=dict(t=50, b=20),
            showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # Absolute jobs table
        st.dataframe(
            rdf[["Region","Stellen","Wachstum_%"]]
            .rename(columns={"Wachstum_%": "Wachstum (%)"}),
            use_container_width=True, hide_index=True,
        )

    # Top growing professions
    st.markdown("**Top Berufe nach Wachstum — Berlin & Brandenburg**")
    top_berufe = (
        demand_sub[demand_sub["region"].isin(["Berlin","Brandenburg"])]
        .groupby(["kldb_id","beruf_name"], as_index=False)
        .agg(Stellen=("total_jobs","sum"),
             Wachstum_pct=("percentage_diff_previous_year","mean"))
        .sort_values("Wachstum_pct", ascending=False)
        .head(15)
    )
    top_berufe["Wachstum"] = top_berufe["Wachstum_pct"].apply(
        lambda x: f"{x*100:+.1f}%" if pd.notna(x) else "n/a")
    top_berufe["Stellen"] = top_berufe["Stellen"].apply(lambda x: f"{int(x):,}")
    st.dataframe(
        top_berufe[["beruf_name","Stellen","Wachstum"]]
        .rename(columns={"beruf_name": "Berufsbezeichnung"}),
        use_container_width=True, hide_index=True,
    )

    return all_kldb

# ─── PHASE 3: PREISGESTALTUNG ────────────────────────────────────────────

def phase_3(offers, params, matched_offers):
    st.header("Schritt 4: Preisgestaltung")

    priced_all = None
    if matched_offers is not None and len(matched_offers) > 0:
        priced_all = matched_offers.dropna(subset=["price"])

    # ── Break-even ────────────────────────────────────────────────────
    has_cost_data = params["dev_h"] > 0

    if has_cost_data:
        fixkosten_netto  = params["dev_h"] * params["dev_rate"] + params["impl_h"] * params["impl_rate"]
        fixkosten_brutto = fixkosten_netto * (1 + params["overhead"])
        be_preis = ((fixkosten_netto / params["target_tn"]) + params["sachkosten"]) * (1 + params["overhead"])

        b1, b2, b3 = st.columns(3)
        b1.metric("Gesamte Fixkosten (inkl. Overhead)", f"{fixkosten_brutto:,.0f} EUR")
        b2.metric("Break-even-Preis pro TN", f"{be_preis:,.0f} EUR")

        # Break-even at different price points
        price_points = [500, 1000, 2000, 3000, 5000, 8000, 10000, 15000]
        be_data = []
        for p in price_points:
            denom = p / (1 + params["overhead"]) - params["sachkosten"]
            if denom > 0:
                tn = math.ceil(fixkosten_netto / denom)
                be_data.append({"Preis pro TN (EUR)": p, "Benötigte TN": tn})

        with b3:
            st.markdown("**Min. TN für Break-even**")
            for row in be_data[:5]:
                st.caption(f"Bei {row['Preis pro TN (EUR)']:,} EUR → {row['Benötigte TN']} TN")

        st.write("")

        # Break-even chart (like the attached reference)
        if be_data:
            be_df = pd.DataFrame(be_data)
            fig_be = go.Figure()

            # Revenue lines at different TN counts
            tn_range = list(range(1, max(params["target_tn"] * 2, 30) + 1))
            for preis in [1000, 2000, 5000, be_preis]:
                revenue = [t * preis / (1 + params["overhead"]) - params["sachkosten"] * t
                           for t in tn_range]
                label = f"{preis:,.0f} EUR/TN" + (" (Break-even)" if preis == be_preis else "")
                fig_be.add_trace(go.Scatter(
                    x=tn_range, y=revenue,
                    mode="lines", name=label,
                    line=dict(width=2, dash="dash" if preis == be_preis else "solid"),
                ))

            # Fixed cost line
            fig_be.add_hline(y=fixkosten_netto, line_dash="dot",
                             line_color="#c0392b", line_width=1.5,
                             annotation_text="Fixkosten",
                             annotation_position="right")

            # Mark target TN
            fig_be.add_vline(x=params["target_tn"], line_dash="dash",
                             line_color="#888", line_width=1,
                             annotation_text=f"Ziel: {params['target_tn']} TN",
                             annotation_position="top right")

            fig_be.update_layout(
                title="Deckungsbeitrag je Teilnehmerzahl und Preispunkt",
                xaxis_title="Teilnehmerzahl",
                yaxis_title="Deckungsbeitrag (EUR)",
                height=380,
                legend=dict(orientation="h", y=-0.2),
                margin=dict(t=50, b=80),
            )
            fig_be.add_hline(y=0, line_color="#333", line_width=0.5)
            st.plotly_chart(fig_be, use_container_width=True)
            st.caption(
                "Die Linien zeigen den Deckungsbeitrag je Preispunkt in Abhängigkeit "
                "der Teilnehmerzahl. Oberhalb der Fixkosten-Linie (gepunktet) ist der Kurs profitabel."
            )

        st.write("---")

    # ── Market pricing ────────────────────────────────────────────────
    st.subheader("Marktpreise ähnlicher Kurse")

    if priced_all is not None and len(priced_all) >= 3:
        p25 = priced_all["price"].quantile(0.25)
        med = priced_all["price"].median()
        p75 = priced_all["price"].quantile(0.75)

        fig_mkt = px.box(
            priced_all, y="price", points="outliers",
            title="Preisverteilung ähnlicher Kurse — alle Regionen",
            labels={"price": "Preis (EUR)"},
            color_discrete_sequence=["#185fa5"], height=320,
        )
        if has_cost_data:
            fig_mkt.add_hline(y=be_preis, line_dash="dash", line_color="#c0392b",
                              annotation_text="Ihr Break-even",
                              annotation_position="top right")
        fig_mkt.update_layout(margin=dict(t=50, b=10))
        st.plotly_chart(fig_mkt, use_container_width=True)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("25. Perzentil", f"{p25:,.0f} EUR")
        col2.metric("Median", f"{med:,.0f} EUR")
        col3.metric("75. Perzentil", f"{p75:,.0f} EUR")
        col4.metric("Empfohlene Spanne", f"{p25:,.0f} – {p75:,.0f} EUR")

        if has_cost_data:
            if be_preis < p25:
                st.success(f"Ihr Break-even ({be_preis:,.0f} EUR) liegt unter dem 25. Perzentil — gute Spielräume.")
            elif be_preis < med:
                st.info(f"Ihr Break-even ({be_preis:,.0f} EUR) liegt im unteren Marktbereich — realistische Kalkulation.")
            else:
                st.warning(f"Ihr Break-even ({be_preis:,.0f} EUR) liegt über dem Marktmedian — Kostensenkung prüfen.")
    else:
        st.info("Bitte erst Schritt 2 ausführen oder mehr Stichwörter eingeben, um Marktpreise zu berechnen.")

# ─── FEEDBACK ────────────────────────────────────────────────────────────

def feedback_section():
    st.write("---")
    st.subheader("Feedback")
    st.markdown(
        "Hilft Ihnen dieses Werkzeug? Ihr Feedback verbessert zukünftige Versionen. "
        "Das Formular dauert etwa 2 Minuten:"
    )
    FORM_URL = "https://docs.google.com/forms/d/e/PLACEHOLDER/viewform?embedded=true"
    st.markdown(
        f'<iframe src="{FORM_URL}" width="100%" height="520" '
        f'frameborder="0" marginheight="0" marginwidth="0">Wird geladen...</iframe>',
        unsafe_allow_html=True,
    )

# ─── MAIN ────────────────────────────────────────────────────────────────

def main():
    offers = load_offers()
    demand = load_demand()
    berufe = load_berufe()
    kgs    = load_knowledge_groups()

    with st.sidebar:
        st.markdown("""
        ## Weiterbildungs-Radar
        ### TH Wildau

        Dieses Werkzeug unterstützt Lehrende der TH Wildau dabei,
        eine neue Weiterbildungsidee zu analysieren — bevor die
        eigentliche Kursentwicklung beginnt.

        **Was das Werkzeug leistet:**

        - Wie viele ähnliche Kurse gibt es bereits — lokal, regional, national?
        - Welche Berufsgruppen könnten von Ihrem Kurs profitieren, und wie stark wächst die Nachfrage nach diesen Berufen?
        - Wie sind vergleichbare Kurse am Markt bepreist, und ab welcher Teilnehmerzahl rechnet sich Ihr Angebot?

        **Datengrundlage:**
        Die Angebotsdaten stammen aus hochundweit.de und mein-now.de (Stand 2025, über 13.000 Kurse).
        Die Nachfragedaten basieren auf dem Jobmonitor der Bertelsmann Stiftung
        (Stellenanzeigenanalyse 2024–2025, Regionen Berlin, Brandenburg,
        Dahme-Spreewald, Oder-Spree, Teltow-Fläming).

        **Hinweis:** Dieses Werkzeug ist ein Prototyp. Alle Ergebnisse sind
        Orientierungswerte und ersetzen keine vollständige Marktanalyse.

        ---
        """)
        st.caption("Version 1.0 · TH Wildau 2025")

    st.title("Weiterbildungs-Radar")
    st.markdown(
        "Analysieren Sie Angebot, Nachfrage und Preisgestaltung für Ihre Weiterbildungsidee."
    )

    params = phase_0(kgs)

    if params["user_text"].strip():
        st.write("---")
        matched = phase_1(offers, params)
        st.write("---")
        phase_2(berufe, demand, params)
        st.write("---")
        phase_3(offers, params, matched)
        feedback_section()
    else:
        st.info("Geben Sie einen Kurstitel und eine Beschreibung ein, um zu starten.")


if __name__ == "__main__":
    main()
