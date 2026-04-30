"""
Weiterbildungs-Radar — TH Wildau
=================================
Tool für Lehrende: Angebot, Nachfrage und Preisgestaltung für Weiterbildungsideen.

Aufbau:
  Phase 0 — Eckpunkte eingeben
  Phase 1 — Angebot analysieren
  Phase 2 — Nachfrage + Zielgruppe
  Phase 3 — Preisgestaltung
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

# ─── CONFIG ──────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Weiterbildungs-Radar · TH Wildau",
    page_icon="🎓",
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
    "PGT_effektive_Verwaltung":              "Effektive Verwaltung",
    "PGT_effektive_Verwaltung_oeffentlich":  "Effektive Verwaltung (öffentlich)",
    "PGT_zukunftsfaehige_Mobilitaet":        "Zukunftsfähige Mobilität",
    "PGT_nachhaltige_Wertschoepfung":        "Nachhaltige Wertschöpfung",
    "QST_Diversity":                         "QST: Diversity",
    "QST_Nachhaltigkeit":                    "QST: Nachhaltigkeit",
    "QST_Internationalisation":              "QST: Internationalisation",
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

# HuggingFace optional — set env var HF_TOKEN or leave empty
HF_TOKEN = ""  # os.getenv("HF_TOKEN", "")

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
    return pd.read_csv(DATA / "demand_2025.csv")

@st.cache_data
def load_berufe():
    df = pd.read_csv(DATA / "berufe.csv")
    df["kldb_id"] = df["kldb_id"].astype(str)
    df["kldb_prefix2"] = df["kldb_id"].str[:2]
    return df

@st.cache_data
def load_knowledge_groups():
    with open(DATA / "knowledge_groups.json", encoding="utf-8") as f:
        return json.load(f)

# ─── MATCHING LOGIC ──────────────────────────────────────────────────────

def match_offers(offers: pd.DataFrame, user_text: str,
                 selected_cats: list, kg: str, n: int = 50) -> pd.DataFrame:
    """Score offers by similarity to user input."""
    user_words  = set(re.findall(r'\b\w{4,}\b', user_text.lower()))
    user_stems  = {w[:5] for w in user_words}

    scores = []
    for _, row in offers.iterrows():
        s = 0.0
        row_text = (str(row.get("title","")) + " " +
                    str(row.get("description",""))).lower()
        row_words = set(re.findall(r'\b\w{4,}\b', row_text))
        row_stems = {w[:5] for w in row_words}

        # Text overlap
        s += len(user_words & row_words) * 2.0
        s += len(user_stems & row_stems) * 1.0

        # Category overlap
        for cat in selected_cats:
            if row.get(cat, False):
                s += 3.0

        # KnowledgeGroup match
        if kg and str(row.get("knowledgeGroup","")) == kg:
            s += 2.0

        scores.append(s)

    offers = offers.copy()
    offers["_score"] = scores
    result = offers[offers["_score"] > 0].sort_values("_score", ascending=False)
    return result.head(n)

def match_berufe_to_text(berufe: pd.DataFrame, user_text: str,
                          n: int = 15) -> list[dict]:
    """Keyword + stem + KldB-topic matching."""
    user_words = set(re.findall(r'\b\w{4,}\b', user_text.lower()))
    user_stems = {w[:5] for w in user_words}

    scores = defaultdict(float)
    for _, row in berufe.iterrows():
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
        row = berufe[berufe["beruf_name"] == beruf].iloc[0]
        result.append({
            "beruf_name":   beruf,
            "kldb_id":      row["kldb_id"],
            "kldb_prefix2": row["kldb_prefix2"],
            "score":        sc,
        })
    return result

def expand_berufe(berufe: pd.DataFrame, selected_names: list,
                  n: int = 20) -> list[dict]:
    """Find related professions from selected ones via family + word similarity."""
    sel_rows = berufe[berufe["beruf_name"].isin(selected_names)]
    sel_prefixes = set(sel_rows["kldb_prefix2"].tolist())
    sel_words = set()
    for name in selected_names:
        sel_words |= set(re.findall(r'\b\w{4,}\b', name.lower()))
    sel_stems = {w[:5] for w in sel_words}

    scores = defaultdict(float)
    for _, row in berufe.iterrows():
        if row["beruf_name"] in selected_names:
            continue
        bwords = set(re.findall(r'\b\w{4,}\b', row["beruf_name"].lower()))
        bstems = {w[:5] for w in bwords}

        if row["kldb_prefix2"] in sel_prefixes:
            scores[row["beruf_name"]] += 3.0
        scores[row["beruf_name"]] += len(sel_stems & bstems) * 1.5

    ranked = sorted(
        [(b, s) for b, s in scores.items() if s > 0],
        key=lambda x: -x[1]
    )[:n]
    result = []
    for beruf, sc in ranked:
        row = berufe[berufe["beruf_name"] == beruf].iloc[0]
        result.append({
            "beruf_name":   beruf,
            "kldb_id":      row["kldb_id"],
            "kldb_prefix2": row["kldb_prefix2"],
            "score":        sc,
        })
    return result

# ─── SCORING FUNCTIONS ───────────────────────────────────────────────────

def angebots_score(matched_offers: pd.DataFrame) -> tuple[int, str]:
    """
    Score 1–10: how saturated is the market with similar offers?
    High score = many similar courses = more competition.
    """
    n = len(matched_offers)
    if n == 0:   return 1,  "Kaum Angebot vorhanden — Lücke im Markt."
    if n <= 3:   return 3,  "Sehr geringes Angebot — gute Chance."
    if n <= 8:   return 5,  "Moderates Angebot — Differenzierung empfehlenswert."
    if n <= 20:  return 7,  "Angebot vorhanden — klares Profil nötig."
    if n <= 40:  return 9,  "Starkes Angebot — Nische oder USP wichtig."
    return 10, "Sehr gesättigter Markt — Positionierung entscheidend."

def nachfrage_score(demand: pd.DataFrame, kldb_ids: list,
                    region_names: list) -> tuple[int, str]:
    """
    Score 1–10: how strong is demand growth for matched professions?
    """
    sub = demand[
        demand["kldb_id"].isin(kldb_ids) &
        demand["region"].isin(region_names)
    ]
    if sub.empty:
        return 1, "Keine Nachfragedaten für diese Berufe."

    median_growth = sub["percentage_diff_previous_year"].median()
    total_jobs    = sub["total_jobs"].sum()

    if pd.isna(median_growth):
        return 3, "Unzureichende Daten für Bewertung."

    # Combine growth rate + absolute size
    growth_score = min(10, max(1, int((median_growth * 100 + 5) * 1.2)))
    size_bonus   = min(2, math.log10(max(total_jobs, 1)) / 3)
    final        = min(10, max(1, round(growth_score + size_bonus)))

    trend_text = "wachsend" if median_growth > 0.05 else \
                 "stabil" if median_growth > -0.05 else "rückläufig"
    return final, (
        f"Trend: {trend_text} · "
        f"Ø Wachstum: {median_growth*100:+.1f}% · "
        f"Gesamt Stellen: {int(total_jobs):,}"
    )

# ─── UI HELPERS ──────────────────────────────────────────────────────────

def score_badge(score: int, label: str):
    color = "#1a7a4a" if score <= 4 else "#b45309" if score <= 7 else "#9b1c1c"
    bg    = "#d1fae5" if score <= 4 else "#fef3c7" if score <= 7 else "#fee2e2"
    st.markdown(
        f'<div style="display:inline-flex;align-items:center;gap:10px;'
        f'background:{bg};border-radius:10px;padding:10px 18px;margin:4px 0">'
        f'<span style="font-size:2rem;font-weight:700;color:{color}">{score}/10</span>'
        f'<span style="color:{color};font-size:0.95rem">{label}</span></div>',
        unsafe_allow_html=True,
    )

# ─── PHASE 0: ECKPUNKTE ──────────────────────────────────────────────────

def phase_0(kgs):
    st.header("Schritt 1: Ihre Kursidee beschreiben")

    c1, c2 = st.columns([3, 2])
    with c1:
        title = st.text_input(
            "Kurstitel (Idee oder Arbeitstitel)",
            placeholder="z.B. Zertifikatskurs Digitale Verwaltung für Kommunen",
        )
        description = st.text_area(
            "Kurzbeschreibung / Lernziele",
            placeholder="Was sollen Teilnehmer lernen? Welche Kompetenzen vermitteln Sie?",
            height=100,
        )
        keywords = st.text_input(
            "Weitere Stichwörter (optional)",
            placeholder="z.B. DSGVO, Datenschutz, E-Government, Projektmanagement",
        )

    with c2:
        kg = st.selectbox("Wissensgebiet", ["(bitte wählen)"] + kgs)
        selected_cats = st.multiselect(
            "Thematische Schwerpunkte (PGT/QST)",
            options=list(CAT_LABELS.keys()),
            format_func=lambda x: CAT_LABELS[x],
        )
        fmt = st.selectbox(
            "Format",
            ["Online / Digital", "Hybrid / Blended", "Präsenz", "Noch offen"],
        )
        degree = st.selectbox(
            "Angestrebter Abschluss",
            ["Zertifikat","Microcredential","Hochschulzertifikat",
             "Weiterbildungsmaster","Sonstiges"],
        )

    st.write("---")
    c3, c4, c5, c6 = st.columns(4)
    ects    = c3.number_input("ECTS", min_value=0, max_value=120, value=5, step=1)
    hours   = c4.number_input("Workload (Stunden)", min_value=0, value=60, step=10)
    months  = c5.number_input("Dauer (Monate)", min_value=1, value=3, step=1)
    target_tn = c6.number_input("Geplante TN-Zahl", min_value=1, value=15, step=5)

    # Optional cost inputs (collapsed by default)
    with st.expander("💶 Kosteninputs für Preiskalkulation (optional)"):
        cc1, cc2, cc3, cc4 = st.columns(4)
        dev_h      = cc1.number_input("Entwicklungsstunden", value=40, step=5)
        dev_rate   = cc2.number_input("Stundensatz Entwicklung (€)", value=80, step=5)
        impl_h     = cc3.number_input("Implementierungsstunden", value=20, step=5)
        impl_rate  = cc4.number_input("Stundensatz Impl. (€)", value=60, step=5)
        sc1, sc2   = st.columns(2)
        sachkosten = sc1.number_input("Sachkosten pro TN (€)", value=50, step=10)
        overhead   = sc2.number_input("Overhead (%)", value=10.0, step=1.0) / 100

    user_text = f"{title} {description} {keywords}".strip()
    kg_clean  = kg if kg != "(bitte wählen)" else ""

    return {
        "title":        title,
        "description":  description,
        "keywords":     keywords,
        "user_text":    user_text,
        "kg":           kg_clean,
        "selected_cats":selected_cats,
        "format":       fmt,
        "degree":       degree,
        "ects":         ects,
        "hours":        hours,
        "months":       months,
        "target_tn":    target_tn,
        "dev_h":        dev_h or 0,
        "dev_rate":     dev_rate or 0,
        "impl_h":       impl_h or 0,
        "impl_rate":    impl_rate or 0,
        "sachkosten":   sachkosten or 0,
        "overhead":     overhead,
    }


# ─── PHASE 1: ANGEBOT ────────────────────────────────────────────────────

def phase_1(offers: pd.DataFrame, params: dict):
    st.header("Schritt 2: Angebot analysieren")

    if not params["user_text"].strip():
        st.info("Bitte erst Kurstitel und Beschreibung eingeben.")
        return None

    with st.spinner("Ähnliche Angebote werden gesucht…"):
        matched = match_offers(
            offers, params["user_text"],
            params["selected_cats"], params["kg"]
        )

    # ── Score ──────────────────────────────────────────────────────────
    score, score_text = angebots_score(matched)

    col_sc, col_info = st.columns([1, 3])
    with col_sc:
        st.markdown("**Angebots-Score**")
        score_badge(score, "Wettbewerb im Markt")
    with col_info:
        st.markdown(f"**{score_text}**")
        st.caption(
            f"{len(matched)} ähnliche Angebote gefunden von {len(offers):,} gesamt. "
            "Score 1 = wenig Wettbewerb, 10 = starker Wettbewerb."
        )

    st.write("---")

    # ── Tabs: Lokal / Regional / National ──────────────────────────────
    tab_local, tab_regional, tab_national = st.tabs([
        "📍 Lokal (TH Wildau Region)",
        "🗺️ Regional (Berlin-Brandenburg)",
        "🇩🇪 National",
    ])

    def show_offers_tab(df_tab, geo_label):
        # Include online/flexible courses as available everywhere
        online = matched[matched["format"].str.contains(
            "Digital|Online|Combined|Blended|Fern", case=False, na=False
        )]
        combined = pd.concat([df_tab, online]).drop_duplicates(subset=["id"])

        st.caption(f"{len(combined)} Angebote ({len(df_tab)} {geo_label} + {len(online)} online)")

        if combined.empty:
            st.info("Keine passenden Angebote für diese Region.")
            return

        # Preisverteilung
        priced = combined.dropna(subset=["price"])
        if len(priced) >= 3:
            fig = px.box(
                priced, y="price",
                points="outliers",
                title="Preisverteilung ähnlicher Kurse",
                labels={"price": "Preis (€)"},
                color_discrete_sequence=["#1a5c9e"],
                height=300,
            )
            fig.update_layout(margin=dict(t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

            m1, m2, m3 = st.columns(3)
            m1.metric("Median", f"{priced['price'].median():,.0f} €")
            m2.metric("25. Perzentil", f"{priced['price'].quantile(0.25):,.0f} €")
            m3.metric("75. Perzentil", f"{priced['price'].quantile(0.75):,.0f} €")

        # Top 10 table
        st.subheader("Top 10 ähnliche Angebote")
        top10 = combined.head(10)[["title","provider","format","price","url"]].copy()
        top10["price"] = top10["price"].apply(
            lambda x: f"{x:,.0f} €" if pd.notna(x) else "k.A."
        )
        top10["Link"] = top10["url"].apply(
            lambda u: f'<a href="{u}" target="_blank">↗ öffnen</a>' if pd.notna(u) and str(u).startswith("http") else "—"
        )
        top10 = top10.rename(columns={
            "title":"Titel","provider":"Anbieter",
            "format":"Format","price":"Preis"
        })
        st.write(
            top10[["Titel","Anbieter","Format","Preis","Link"]].to_html(
                escape=False, index=False
            ),
            unsafe_allow_html=True,
        )

    with tab_local:
        local = matched[matched["geo_tier"] == "wildau"]
        show_offers_tab(local, "lokale")

    with tab_regional:
        regional = matched[matched["geo_tier"].isin(["berlin_bb", "wildau"])]
        show_offers_tab(regional, "BB/Berlin")

    with tab_national:
        show_offers_tab(matched, "nationale")

    return matched


# ─── PHASE 2: NACHFRAGE ──────────────────────────────────────────────────

def phase_2(berufe_df: pd.DataFrame, demand: pd.DataFrame, params: dict):
    st.header("Schritt 3: Nachfrage und Zielgruppe")

    if not params["user_text"].strip():
        st.info("Bitte erst Kurstitel und Beschreibung eingeben.")
        return

    # ── Step A: Initial suggestions ───────────────────────────────────
    st.subheader("3a. Welche Berufsgruppen könnten profitieren?")
    st.caption(
        "Basierend auf Ihrem Kurstitel und Ihrer Beschreibung wurden diese "
        "Berufsbilder als potenzielle Zielgruppen identifiziert. "
        "**Bitte wählen Sie die relevantesten aus.**"
    )

    suggestions = match_berufe_to_text(berufe_df, params["user_text"], n=18)

    if not suggestions:
        st.warning("Keine passenden Berufe gefunden. Bitte Beschreibung ergänzen.")
        return

    # Render as clickable pills with st.multiselect
    suggested_names = [s["beruf_name"] for s in suggestions]

    selected_initial = st.multiselect(
        "Relevante Berufe auswählen (Mehrfachauswahl möglich)",
        options=suggested_names,
        default=suggested_names[:5],
        key="initial_berufe",
    )

    if not selected_initial:
        return

    # ── Step B: Expand from selected ──────────────────────────────────
    st.write("---")
    st.subheader("3b. Weitere verwandte Berufsgruppen")
    st.caption(
        "Basierend auf Ihrer Auswahl wurden weitere verwandte Berufsbilder "
        "identifiziert. Ergänzen Sie Ihre Zielgruppe nach Bedarf."
    )

    expanded = expand_berufe(berufe_df, selected_initial, n=20)
    expanded_names = [e["beruf_name"] for e in expanded
                      if e["beruf_name"] not in selected_initial]

    selected_expanded = st.multiselect(
        "Weitere Berufe hinzufügen",
        options=expanded_names,
        default=[],
        key="expanded_berufe",
    )

    all_selected = selected_initial + selected_expanded
    all_kldb = (
        berufe_df[berufe_df["beruf_name"].isin(all_selected)]["kldb_id"]
        .tolist()
    )

    # ── Step C: Demand analysis ────────────────────────────────────────
    st.write("---")
    st.subheader("3c. Nachfrageentwicklung für Ihre Zielgruppe")

    # Build demand summary per region
    demand_sub = demand[demand["kldb_id"].isin(all_kldb)]

    if demand_sub.empty:
        st.warning("Keine Nachfragedaten für die gewählten Berufe.")
        return

    # Aggregate by region group
    region_rows = []
    for display_name, db_regions in REGIONS_DISPLAY.items():
        sub = demand_sub[demand_sub["region"].isin(db_regions)]
        if sub.empty:
            continue
        total_jobs = sub["total_jobs"].sum()
        diff       = sub["total_diff_previous_year"].sum()
        pct_growth = diff / (total_jobs - diff) if (total_jobs - diff) > 0 else 0
        region_rows.append({
            "Region":    display_name,
            "Stellen":   int(total_jobs),
            "Wachstum":  pct_growth,
            "Diff":      int(diff),
        })

    region_df = pd.DataFrame(region_rows)

    # Score (use Berlin + TH Wildau combined)
    local_regions = REGIONS_DISPLAY["TH Wildau Region"] + REGIONS_DISPLAY["Berlin"] + REGIONS_DISPLAY["Brandenburg"]
    nd_score, nd_text = nachfrage_score(demand_sub, all_kldb, local_regions)

    col_sc2, col_info2 = st.columns([1, 3])
    with col_sc2:
        st.markdown("**Nachfrage-Score**")
        score_badge(nd_score, "Nachfragestärke")
    with col_info2:
        st.markdown(f"**{nd_text}**")
        st.caption(f"Score 1 = geringe/sinkende Nachfrage, 10 = stark wachsende Nachfrage.")

    st.write("")

    # Growth chart
    if not region_df.empty:
        region_df["Wachstum_%"] = region_df["Wachstum"] * 100
        region_df_sorted = region_df.reindex(
            region_df.set_index("Region").reindex(REGION_ORDER).dropna(how="all").index
        ).reset_index(drop=True)

        fig_bar = px.bar(
            region_df_sorted,
            x="Region",
            y="Wachstum_%",
            color="Wachstum_%",
            color_continuous_scale=["#c0392b","#f39c12","#27ae60"],
            title="Nachfragewachstum 2024→2025 nach Region",
            labels={"Wachstum_%": "Wachstum (%)"},
            height=320,
            text="Wachstum_%",
        )
        fig_bar.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_bar.update_layout(coloraxis_showscale=False, margin=dict(t=50,b=20))
        st.plotly_chart(fig_bar, use_container_width=True)

    # Top growing professions table
    st.subheader("Top Berufe nach Wachstum (Region Berlin-Brandenburg)")
    top_berufe = (
        demand_sub[demand_sub["region"].isin(["Berlin","Brandenburg"])]
        .groupby("beruf_name", as_index=False)
        .agg(
            Stellen=("total_jobs","sum"),
            Wachstum=("percentage_diff_previous_year","mean"),
        )
        .sort_values("Wachstum", ascending=False)
        .head(15)
    )
    top_berufe["Wachstum"] = top_berufe["Wachstum"].apply(
        lambda x: f"{x*100:+.1f}%" if pd.notna(x) else "n/a"
    )
    top_berufe["Stellen"] = top_berufe["Stellen"].apply(lambda x: f"{int(x):,}")
    st.dataframe(top_berufe.reset_index(drop=True), use_container_width=True)

    return all_kldb


# ─── PHASE 3: PREISGESTALTUNG ────────────────────────────────────────────

def phase_3(offers: pd.DataFrame, params: dict, matched_offers):
    st.header("Schritt 4: Preisgestaltung")

    # ── Break-even ────────────────────────────────────────────────────
    if params["dev_h"] > 0:
        fixkosten_netto = (params["dev_h"] * params["dev_rate"] +
                           params["impl_h"] * params["impl_rate"])
        fixkosten_brutto = fixkosten_netto * (1 + params["overhead"])
        be_preis = ((fixkosten_netto / params["target_tn"]) +
                    params["sachkosten"]) * (1 + params["overhead"])

        b1, b2, b3 = st.columns(3)
        b1.metric("Gesamte Fixkosten", f"{fixkosten_brutto:,.0f} €")
        b2.metric("Break-even-Preis", f"{be_preis:,.0f} €",
                  help="Mindestpreis pro TN bei geplanter Auslastung")
        # Break-even TN at different price points
        prices = [500, 1000, 2000, 5000, 10000]
        be_tns = []
        for p in prices:
            if p > params["sachkosten"] * (1 + params["overhead"]):
                tn_needed = fixkosten_netto / (p / (1 + params["overhead"]) - params["sachkosten"])
                be_tns.append(max(1, round(tn_needed)))
            else:
                be_tns.append(None)

        with b3:
            st.markdown("**Min. TN für Break-even**")
            for p, tn in zip(prices, be_tns):
                if tn:
                    st.caption(f"Bei {p:,} €/TN → {tn} TN")

        st.write("---")

    # ── Market pricing ────────────────────────────────────────────────
    st.subheader("Marktpreise ähnlicher Kurse")

    if matched_offers is not None and len(matched_offers) > 0:
        priced = matched_offers.dropna(subset=["price"])
        if len(priced) >= 3:
            fig = px.box(
                priced, y="price",
                points="all",
                title="Preisverteilung ähnlicher Kurse (alle Regionen)",
                labels={"price": "Preis (€)"},
                color_discrete_sequence=["#1a5c9e"],
                height=350,
            )
            if params["dev_h"] > 0:
                be_preis_local = ((params["dev_h"] * params["dev_rate"] +
                                   params["impl_h"] * params["impl_rate"])
                                  / params["target_tn"] + params["sachkosten"]
                                  ) * (1 + params["overhead"])
                fig.add_hline(
                    y=be_preis_local, line_dash="dash", line_color="#c0392b",
                    annotation_text="Break-even",
                    annotation_position="top right",
                )
            st.plotly_chart(fig, use_container_width=True)

            p25  = priced["price"].quantile(0.25)
            med  = priced["price"].median()
            p75  = priced["price"].quantile(0.75)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("25. Perzentil", f"{p25:,.0f} €")
            col2.metric("Median", f"{med:,.0f} €")
            col3.metric("75. Perzentil", f"{p75:,.0f} €")
            col4.metric("Empfohlene Spanne",
                        f"{p25:,.0f} – {p75:,.0f} €",
                        help="Mittlere 50% der Marktpreise")

            # Positioning hint
            if params["dev_h"] > 0 and be_preis:
                if be_preis < p25:
                    st.success(f"✓ Ihr Break-even ({be_preis:,.0f} €) liegt unter dem "
                               f"25. Perzentil — gute Spielräume für Positionierung.")
                elif be_preis < med:
                    st.info(f"ℹ Ihr Break-even ({be_preis:,.0f} €) liegt im unteren "
                            f"Marktbereich — realistische Kalkulation.")
                else:
                    st.warning(f"⚠ Ihr Break-even ({be_preis:,.0f} €) liegt über dem "
                               f"Marktmedian — prüfen Sie Kostensenkungsmöglichkeiten.")
        else:
            st.info("Zu wenige Preisdaten für eine Verteilungsanalyse.")
    else:
        st.info("Bitte erst Schritt 2 ausführen, um Marktpreise anzuzeigen.")


# ─── FEEDBACK ────────────────────────────────────────────────────────────

def feedback_section():
    st.write("---")
    st.subheader("💬 Feedback")
    st.markdown(
        "Hilft Ihnen dieses Tool? Ihr Feedback verbessert zukünftige Versionen. "
        "Das Formular dauert ca. 2 Minuten:"
    )
    # Embed a Google Form — replace with your form ID
    FORM_URL = "https://docs.google.com/forms/d/e/PLACEHOLDER/viewform?embedded=true"
    st.markdown(
        f'<iframe src="{FORM_URL}" width="100%" height="520" '
        f'frameborder="0" marginheight="0" marginwidth="0">'
        f'Wird geladen…</iframe>',
        unsafe_allow_html=True,
    )


# ─── MAIN ────────────────────────────────────────────────────────────────

def main():
    # Load data
    offers  = load_offers()
    demand  = load_demand()
    berufe  = load_berufe()
    kgs     = load_knowledge_groups()

    # Sidebar
    with st.sidebar:
        st.image("https://www.th-wildau.de/typo3conf/ext/thwildau/Resources/Public/Images/TH-Wildau-Logo.svg",
                 width=160)
        st.markdown("## Weiterbildungs-Radar")
        st.caption(
            "Analysieren Sie Angebot, Nachfrage und Preisgestaltung "
            "für Ihre Weiterbildungsidee."
        )
        st.write("---")
        st.markdown("**Fortschritt**")
        st.caption("① Eckpunkte → ② Angebot → ③ Nachfrage → ④ Preis")
        st.write("---")
        st.caption(
            "Datenquellen: hochundweit.de · mein-now.de · "
            "jobmonitor.de (Bertelsmann Stiftung)"
        )
        st.caption("Stand: 2025 · TH Wildau")

    # Title
    st.title("🎓 Weiterbildungs-Radar")
    st.markdown(
        "Geben Sie Ihre Kursidee ein und erhalten Sie eine Marktanalyse "
        "zu Angebot, Nachfrage und Preisgestaltung."
    )

    # Run phases
    params = phase_0(kgs)

    if params["user_text"].strip():
        st.write("---")
        matched = phase_1(offers, params)

        st.write("---")
        all_kldb = phase_2(berufe, demand, params)

        st.write("---")
        phase_3(offers, params, matched)

        feedback_section()
    else:
        st.info("👆 Geben Sie einen Kurstitel und eine Beschreibung ein, um zu starten.")


if __name__ == "__main__":
    main()
