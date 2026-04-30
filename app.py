"""
Weiterbildungs-Radar — TH Wildau
"""
import re, json, math, warnings
from collections import defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="Weiterbildungs-Radar · TH Wildau",
    page_icon="https://www.th-wildau.de/favicon.ico",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject light section backgrounds
st.markdown("""
<style>
div[data-testid="stVerticalBlock"] > div.element-container { }
.section-input      { background:#f0f4f8; border-radius:10px; padding:1.2rem 1.4rem; margin-bottom:1rem; }
.section-cost       { background:#f5f0fa; border-radius:10px; padding:1.2rem 1.4rem; margin-bottom:1rem; }
.section-angebot    { background:#f0f7f4; border-radius:10px; padding:1.2rem 1.4rem; margin-bottom:1rem; }
.section-nachfrage  { background:#fff8f0; border-radius:10px; padding:1.2rem 1.4rem; margin-bottom:1rem; }
.section-preis      { background:#f0f4ff; border-radius:10px; padding:1.2rem 1.4rem; margin-bottom:1rem; }
.beruf-tag-sel {
    display:inline-block;background:#0f6e56;color:#fff;
    border-radius:6px;padding:4px 12px;margin:3px;font-size:13px;cursor:pointer;
}
.beruf-tag-unsel {
    display:inline-block;background:#e1f5ee;color:#085041;
    border-radius:6px;padding:4px 12px;margin:3px;font-size:13px;cursor:pointer;
}
</style>
""", unsafe_allow_html=True)

DATA = Path(__file__).parent / "data"

REGIONS_DISPLAY = {
    "TH Wildau Region": ["Dahme-Spreewald","Oder-Spree","Teltow-Fläming"],
    "Berlin":           ["Berlin"],
    "Brandenburg":      ["Brandenburg"],
    "Deutschland":      ["Deutschland"],
}
REGION_ORDER = ["TH Wildau Region","Berlin","Brandenburg","Deutschland"]

CAT_COLS = ["PGT_effektive_Verwaltung","PGT_effektive_Verwaltung_oeffentlich",
            "PGT_zukunftsfaehige_Mobilitaet","PGT_nachhaltige_Wertschoepfung",
            "QST_Diversity","QST_Nachhaltigkeit","QST_Internationalisation"]
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
    "BIS_500_EUR":              "bis 500 EUR",
    "UEBER_500_BIS_1000_EUR":   "500 – 1.000 EUR",
    "UEBER_1000_BIS_5000_EUR":  "1.000 – 5.000 EUR",
    "UEBER_5000_BIS_10000_EUR": "5.000 – 10.000 EUR",
    "UEBER_10000_EUR":          "über 10.000 EUR",
}

# ─── MATCHING CONFIG ─────────────────────────────────────────────────────

SHORT_TECH = {"ki","it","iot","erp","crm","sap","ai","ml","bi","bim","cad",
              "cam","cnc","plm","rpa","api","sql","hr","aws","gcp","kpi","ux","ui"}

CONCEPT_TO_KLDB = {
    r"\bki\b|\bai\b|künstl.*intel|machine.learn|deep.learn|neural|llm|chatbot|sprachmodell": {
        "primary":["41","43"],"secondary":[]},
    r"softwar.*entwickl|programmi|app.*entwickl|web.*entwickl|coding": {
        "primary":["41","43"],"secondary":[]},
    r"data.scien|datenanalys|daten.*analyst|big.data|data.engineer|datengetrieben": {
        "primary":["41","43"],"secondary":[]},
    r"cyber.*sicher|it.sicher|informations.*sicher|security|it.forensik": {
        "primary":["43"],"secondary":["41"]},
    r"cloud|devops|infrastruktur.*it|kubernetes|container": {
        "primary":["43"],"secondary":["41"]},
    r"digitalis|digital.transform|industrie.*4\.?0|smart.factor": {
        "primary":["41","43"],"secondary":["25","26"]},
    r"automobil|automotive|\bkfz\b|kraftfahr": {
        "primary":["25","26"],"secondary":["62"]},
    r"elektromobil|e.mobil|ladeinfra|ladesäule": {
        "primary":["26","25"],"secondary":[]},
    r"autonomes.fahr|selbstfahr|adas": {
        "primary":["25","26","41"],"secondary":[]},
    r"fahrzeugtechn|fahrzeugentwick|fahrzeugbau": {
        "primary":["25","26"],"secondary":[]},
    r"maschinenbau|fertigungs.*techn|produktions.*techn": {
        "primary":["25"],"secondary":["26"]},
    r"robotik|automatisier.*techn|mechatronik": {
        "primary":["25","26"],"secondary":[]},
    r"elektrotechn|elektroingenieur|energietechn": {
        "primary":["26"],"secondary":["25"]},
    r"projekt.*manag|agil|scrum|product.owner|kanban": {
        "primary":["71"],"secondary":["72"]},
    r"supply.chain|logistik.*manag|beschaffungs.*manag": {
        "primary":["51"],"secondary":[]},
    r"marketing|vertrieb.*strateg|sales.*manag": {
        "primary":["61"],"secondary":[]},
    r"personal.*manag|hr.manag|talent.manag|recruiting": {
        "primary":["71"],"secondary":[]},
    r"finanz.*manag|controlling|buchführ|rechnungsw|bilanzier": {
        "primary":["72"],"secondary":[]},
    r"strateg.*manag|unternehmens.*führ|business.develop|change.manag": {
        "primary":["71","72"],"secondary":[]},
    r"datenschutz|dsgvo|privacy|datensicherheit": {
        "primary":["73","71"],"secondary":[]},
    r"verwaltungs.*recht|öffentl.*verwalt|kommunal|beamt": {
        "primary":["73"],"secondary":["71"]},
    r"compliance|audit|revision|risiko.*manag": {
        "primary":["73","72"],"secondary":[]},
    r"gesundheits.*manag|klinik.*manag|krankenhaus.*führ": {
        "primary":["81"],"secondary":["82"]},
    r"pflege.*manag|pflegefach|altenpfleg|demenz": {
        "primary":["82","81"],"secondary":[]},
    r"bildungs.*manag|hochschul.*didakt|lehrkompe|didaktik": {
        "primary":["84"],"secondary":["83"]},
    r"weiterbildungs.*manag|e.learn|lerndesign|instructional": {
        "primary":["84"],"secondary":["83"]},
    r"bau.*manag|bauprojekt|architektur|stadtplan": {
        "primary":["31","29"],"secondary":[]},
    r"nachhaltigkeits.*manag|\besg\b|\bcsrb?|umwelt.*manag": {
        "primary":["32","31"],"secondary":["84"]},
    r"energie.*manag|erneuerbar.*energie|photovoltaik|windenergie": {
        "primary":["26","31"],"secondary":[]},
    r"verkehrs.*plan|mobilitäts.*manag|öpnv|schienenverkehr": {
        "primary":["51"],"secondary":["31"]},
    r"medien.*manag|kommunikation.*manag|pr.manag|journalismus": {
        "primary":["93"],"secondary":[]},
    r"sprach.*kompetenz|fremdsprach|interkulturell|internationali": {
        "primary":["94"],"secondary":[]},
}

def tokenize(text):
    all_words = re.findall(r'\b\w+\b', text.lower())
    return {w for w in all_words if len(w) >= 4 or w in SHORT_TECH}

def match_berufe(berufe_df, user_text, n=15):
    user_words  = tokenize(user_text)
    user_stems  = {w[:5] for w in user_words if len(w) >= 4}
    user_lower  = user_text.lower()

    primary, secondary = set(), set()
    for pattern, groups in CONCEPT_TO_KLDB.items():
        if re.search(pattern, user_lower):
            primary.update(groups["primary"])
            secondary.update(groups["secondary"])
    secondary -= primary

    scores = defaultdict(float)
    for _, row in berufe_df.iterrows():
        prefix2 = row["kldb_prefix2"]
        last    = str(row["kldb_id"])[-1]
        beruf_lower = row["beruf_name"].lower()
        beruf_words = tokenize(beruf_lower)
        beruf_stems = {w[:5] for w in beruf_words if len(w) >= 4}

        s  = len(user_words & beruf_words) * 4.0
        s += len((user_stems & beruf_stems) - user_words) * 1.5

        if primary and prefix2 in primary:
            s += 2.0
            if last in ("3","4"): s += 1.0
        elif secondary and prefix2 in secondary:
            s += 0.8
            if last in ("3","4"): s += 0.5

        if primary and last == "1":
            s -= 1.0

        if s >= 2.0:
            scores[row["beruf_name"]] = s

    ranked = sorted(scores.items(), key=lambda x: -x[1])[:n]
    return [{"beruf_name":b,
             "kldb_id": int(berufe_df[berufe_df["beruf_name"]==b]["kldb_id"].iloc[0]),
             "kldb_prefix2": berufe_df[berufe_df["beruf_name"]==b]["kldb_prefix2"].iloc[0],
             "score":s} for b,s in ranked]

def expand_berufe(berufe_df, selected_names, exclude_names, n=15):
    sel_rows    = berufe_df[berufe_df["beruf_name"].isin(selected_names)]
    sel_prefixes = set(sel_rows["kldb_prefix2"].tolist())
    sel_words   = set()
    for name in selected_names:
        sel_words |= tokenize(name)
    sel_stems = {w[:5] for w in sel_words if len(w) >= 4}

    scores = defaultdict(float)
    for _, row in berufe_df.iterrows():
        if row["beruf_name"] in exclude_names: continue
        bwords = tokenize(row["beruf_name"].lower())
        bstems = {w[:5] for w in bwords if len(w) >= 4}
        last   = str(row["kldb_id"])[-1]
        s = 0.0
        if row["kldb_prefix2"] in sel_prefixes:
            s += 2.5
            if last in ("3","4"): s += 0.8
        s += len(sel_stems & bstems) * 1.5
        if s >= 2.0: scores[row["beruf_name"]] = s

    ranked = sorted(scores.items(), key=lambda x: -x[1])[:n]
    return [{"beruf_name":b,
             "kldb_id": int(berufe_df[berufe_df["beruf_name"]==b]["kldb_id"].iloc[0]),
             "kldb_prefix2": berufe_df[berufe_df["beruf_name"]==b]["kldb_prefix2"].iloc[0],
             "score":s} for b,s in ranked]

# ─── DATA ────────────────────────────────────────────────────────────────

@st.cache_data
def load_offers():
    df = pd.read_csv(DATA/"offers.csv")
    for c in CAT_COLS:
        if c in df.columns: df[c] = df[c].fillna(False).astype(bool)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    return df

@st.cache_data
def load_demand():
    df = pd.read_csv(DATA/"demand_2025.csv")
    df["kldb_id"] = df["kldb_id"].astype(int)
    return df

@st.cache_data
def load_berufe():
    df = pd.read_csv(DATA/"berufe.csv")
    df["kldb_id"] = df["kldb_id"].astype(int)
    df["kldb_prefix2"] = df["kldb_id"].astype(str).str[:2]
    return df

@st.cache_data
def load_kgs():
    with open(DATA/"knowledge_groups.json", encoding="utf-8") as f:
        return json.load(f)

# ─── HELPERS ─────────────────────────────────────────────────────────────

def match_offers(offers, user_text, selected_cats, kg, n=60):
    user_words = tokenize(user_text)
    user_stems = {w[:5] for w in user_words if len(w) >= 4}
    scores = []
    for _, row in offers.iterrows():
        s = 0.0
        rt = (str(row.get("title",""))+" "+str(row.get("description",""))).lower()
        rw = tokenize(rt); rs = {w[:5] for w in rw if len(w) >= 4}
        s += len(user_words & rw) * 2.0
        s += len(user_stems & rs) * 1.0
        for cat in selected_cats:
            if row.get(cat, False): s += 3.0
        if kg and str(row.get("knowledgeGroup","")) == kg: s += 2.0
        scores.append(s)
    o2 = offers.copy(); o2["_score"] = scores
    return o2[o2["_score"]>0].sort_values("_score", ascending=False).head(n)

def score_badge(score, label):
    c = "#0f6e56" if score<=4 else "#854f0b" if score<=7 else "#9b1c1c"
    bg= "#e1f5ee" if score<=4 else "#faeeda" if score<=7 else "#fee2e2"
    st.markdown(
        f'<div style="display:inline-flex;align-items:center;gap:12px;'
        f'background:{bg};border-radius:10px;padding:12px 20px;margin:6px 0">'
        f'<span style="font-size:2rem;font-weight:700;color:{c};line-height:1">{score}/10</span>'
        f'<span style="color:{c};font-size:.9rem;line-height:1.4">{label}</span></div>',
        unsafe_allow_html=True)

def angebots_score(n):
    if n==0:   return 1,"Kaum Angebot vorhanden — Lücke im Markt."
    if n<=3:   return 3,"Sehr geringes Angebot — gute Marktchance."
    if n<=8:   return 5,"Moderates Angebot — Differenzierung empfehlenswert."
    if n<=20:  return 7,"Angebot vorhanden — klares Profil nötig."
    if n<=40:  return 9,"Starkes Angebot — Nische oder USP wichtig."
    return 10,"Sehr gesättigter Markt — Positionierung entscheidend."

def nachfrage_score(demand, kldb_ids, region_names):
    sub = demand[demand["kldb_id"].isin(kldb_ids) & demand["region"].isin(region_names)]
    if sub.empty: return 1,"Keine Nachfragedaten für diese Berufe."
    mg = sub["percentage_diff_previous_year"].median()
    tj = sub["total_jobs"].sum()
    if pd.isna(mg): return 3,"Unzureichende Daten."
    gs = min(10,max(1,int((mg*100+5)*1.2)))
    sb = min(2,math.log10(max(tj,1))/3)
    f  = min(10,max(1,round(gs+sb)))
    trend = "wachsend" if mg>0.05 else "stabil" if mg>-0.05 else "rückläufig"
    return f,f"Trend: {trend}  ·  Wachstum: {mg*100:+.1f}%  ·  Gesamtstellen: {int(tj):,}"

# ─── SECTIONS ────────────────────────────────────────────────────────────

def section_header(color_hex, label):
    st.markdown(
        f'<div style="background:{color_hex};border-radius:8px;'
        f'padding:8px 16px;margin-bottom:1rem">'
        f'<span style="font-size:1.1rem;font-weight:600;color:#1a1a1a">{label}</span>'
        f'</div>', unsafe_allow_html=True)

def phase_0(kgs):
    # ── Kursbeschreibung ──────────────────────────────────────────────
    section_header("#dceefb", "1. Kursbeschreibung")
    with st.container():
        c1, c2 = st.columns([3,2])
        with c1:
            title = st.text_input("Kurstitel",
                placeholder="z.B. KI in der Automobilindustrie — Zertifikatskurs")
            description = st.text_area("Kurzbeschreibung / Lernziele",
                placeholder="Was lernen die Teilnehmer? Welche Kompetenzen werden vermittelt?",
                height=110)
            keywords = st.text_input("Weitere Stichworte (optional)",
                placeholder="z.B. Machine Learning, Fahrzeugdaten, ADAS")
        with c2:
            kg = st.selectbox("Wissensgebiet",["(bitte wählen)"]+kgs)
            selected_cats = st.multiselect(
                "Thematische Schwerpunkte (optional, Mehrfachnennung möglich)",
                options=list(CAT_LABELS.keys()),
                format_func=lambda x: CAT_LABELS[x])
            fmt = st.selectbox("Format",
                ["Online / Digital","Hybrid / Blended","Präsenz","Noch offen"])
            degree = st.selectbox("Abschluss", [
                "Zertifikat / Hochschulzertifikat",
                "Microcredential (digitales Badge / Teilleistung)",
                "Teilnahmebescheinigung",
                "Bachelor",
                "Master",
                "Abschlussprüfung",
                "Sonstiges",
            ])
            c3, c4, c5 = st.columns(3)
            ects  = c3.number_input("ECTS",min_value=0,max_value=120,value=5)
            hours = c4.number_input("Workload (Std.)",min_value=0,value=60,step=10)
            months= c5.number_input("Dauer (Monate)",min_value=1,value=3)

    st.write("")
    # ── Kosteninputs ─────────────────────────────────────────────────
    section_header("#ede0f5", "2. Kosteninputs für Preiskalkulation")
    with st.container():
        cc1, cc2, cc3, cc4, cc5 = st.columns(5)
        dev_h     = cc1.number_input("Entwicklungsstunden",value=40,step=5)
        dev_rate  = cc2.number_input("Satz Entw. (EUR/h)",value=80,step=5)
        impl_h    = cc3.number_input("Impl.-Stunden",value=20,step=5)
        impl_rate = cc4.number_input("Satz Impl. (EUR/h)",value=60,step=5)
        sachkosten= cc5.number_input("Sachkosten/TN (EUR)",value=50,step=10)
        sc1, sc2  = st.columns(2)
        overhead  = sc1.number_input("Overhead (%)",value=10.0,step=1.0)/100
        target_tn = sc2.number_input("Geplante Teilnehmerzahl",min_value=1,value=15,step=5)

    return {"title":title,"description":description,"keywords":keywords,
            "user_text":f"{title} {description} {keywords}".strip(),
            "kg":kg if kg!="(bitte wählen)" else "",
            "selected_cats":selected_cats,"format":fmt,"degree":degree,
            "ects":ects,"hours":hours,"months":months,"target_tn":target_tn,
            "dev_h":dev_h,"dev_rate":dev_rate,"impl_h":impl_h,
            "impl_rate":impl_rate,"sachkosten":sachkosten,"overhead":overhead}

def phase_1(offers, params):
    section_header("#d4edda", "3. Angebot — wie viel gibt es bereits?")
    if not params["user_text"].strip():
        st.info("Bitte Kurstitel und Beschreibung eingeben."); return None

    with st.spinner("Suche ähnliche Angebote..."):
        matched = match_offers(offers, params["user_text"],
                               params["selected_cats"], params["kg"])

    score, score_text = angebots_score(len(matched))
    col_sc, col_info = st.columns([1,3])
    with col_sc:
        score_badge(score, score_text)
    with col_info:
        st.write(f"{len(matched)} ähnliche Angebote von {len(offers):,} gefunden. "
                 f"Score 1 = wenig Wettbewerb, Score 10 = stark gesättigter Markt.")

    tab_local, tab_regional, tab_national = st.tabs([
        "Lokal — TH Wildau Region",
        "Regional — Berlin & Brandenburg",
        "National",
    ])

    # Controls above the tabs
    ctrl1, ctrl2 = st.columns([1, 4])
    n_display = ctrl1.selectbox("Angebote anzeigen", [10, 20], index=0, key="n_display")

    # Per-tab deselect state
    if "deselected" not in st.session_state:
        st.session_state.deselected = set()

    def show_tab(geo_filter, geo_label, tab_key):
        geo_courses = matched[matched["geo_tier"].isin(geo_filter)]
        online      = matched[matched["format"].str.contains(
            "Digital|Online|Combined|Blended|Fern", case=False, na=False)]
        combined    = pd.concat([geo_courses, online]).drop_duplicates(subset=["id"])

        st.caption(f"{len(combined)} Angebote "
                   f"({len(geo_courses)} {geo_label} + {len(online)} online/flexibel)")

        if combined.empty:
            st.info("Keine passenden Angebote für diese Region."); return

        # Build display table
        top_n = combined.head(n_display).copy()

        def fmt_price(row):
            pb = str(row.get("price_band",""))
            if pb in PREIS_LABELS: return PREIS_LABELS[pb]
            if pd.notna(row.get("price")): return f"{row['price']:,.0f} EUR"
            return "k.A."

        def fmt_link(row):
            url = str(row.get("url",""))
            if url.startswith("http"):
                label = "Kurs" if "hochschulweiterbildung" in url else "Anbieter"
                return f'<a href="{url}" target="_blank">{label} &rarr;</a>'
            return "—"

        def fmt_source(row):
            if row.get("source") == "hochundweit":
                return '<span style="background:#dceefb;color:#0c3a6b;padding:2px 8px;border-radius:4px;font-size:12px">Hochschule</span>'
            return '<span style="background:#faeeda;color:#6b3000;padding:2px 8px;border-radius:4px;font-size:12px">Weiterbildung</span>'

        top_n["_Quelle"]  = top_n.apply(fmt_source, axis=1)
        top_n["_Preis"]   = top_n.apply(fmt_price, axis=1)
        top_n["_Link"]    = top_n.apply(fmt_link, axis=1)
        top_n["_Umfang"]  = top_n.get("umfang", pd.Series("", index=top_n.index)).fillna("").apply(
            lambda x: x if x else "k.A.")

        # Show table with deselect checkboxes
        st.markdown("**Vergleichsangebote** — Haken entfernen, um Angebote aus der Statistik auszuschließen:")

        # HTML table with coloured source badges
        rows_html = []
        active_ids = []
        for _, row in top_n.iterrows():
            rid = str(row["id"])
            is_active = rid not in st.session_state.deselected
            if is_active:
                active_ids.append(rid)
            chk_key = f"chk_{tab_key}_{rid}"
            checked = st.checkbox(
                f"{row['title'][:65]}  |  {row['provider'][:30]}  |  {row['_Umfang']}  |  {row['_Preis']}",
                value=is_active,
                key=chk_key,
            )
            if not checked and rid not in st.session_state.deselected:
                st.session_state.deselected.add(rid)
                st.rerun()
            elif checked and rid in st.session_state.deselected:
                st.session_state.deselected.discard(rid)
                st.rerun()

        # Statistics based on active (non-deselected) rows only
        active_df  = combined[~combined["id"].astype(str).isin(st.session_state.deselected)]
        priced_act = active_df.dropna(subset=["price"])
        n_desel    = len(combined) - len(active_df)

        if n_desel > 0:
            st.caption(f"{n_desel} Angebot(e) aus der Statistik ausgeschlossen.")

        if len(priced_act) >= 3:
            st.markdown("**Preisstatistik** (basierend auf ausgewählten Angeboten):")
            m1, m2, m3 = st.columns(3)
            m1.metric("Median",    f"{priced_act['price'].median():,.0f} EUR")
            m2.metric("25. Perz.", f"{priced_act['price'].quantile(.25):,.0f} EUR")
            m3.metric("75. Perz.", f"{priced_act['price'].quantile(.75):,.0f} EUR")
        elif len(active_df) > 0:
            st.caption("Zu wenige Preisangaben für Statistik.")

        # Source legend
        st.markdown(
            '<div style="margin-top:8px;font-size:12px">' +
            '<span style="background:#dceefb;color:#0c3a6b;padding:2px 8px;border-radius:4px">Hochschule</span> ' +
            '= hochundweit.de &nbsp;&nbsp;' +
            '<span style="background:#faeeda;color:#6b3000;padding:2px 8px;border-radius:4px">Weiterbildung</span> ' +
            '= mein-now.de</div>',
            unsafe_allow_html=True)

    with tab_local:
        show_tab(["wildau"], "lokale", "local")
    with tab_regional:
        show_tab(["wildau","berlin_bb"], "Berlin/BB", "regional")
    with tab_national:
        show_tab(["wildau","berlin_bb","national","national_flex"], "alle", "national")

    return matched

def phase_2(berufe_df, demand, params):
    section_header("#fff0d4", "4. Nachfrage — wer braucht diesen Kurs?")
    if not params["user_text"].strip():
        st.info("Bitte Kurstitel und Beschreibung eingeben."); return []

    # ── State init ────────────────────────────────────────────────────
    if "confirmed_berufe" not in st.session_state:
        st.session_state.confirmed_berufe = set()
    if "last_input" not in st.session_state:
        st.session_state.last_input = ""

    # Recompute initial suggestions if input changed
    current_input = params["user_text"]
    if current_input != st.session_state.last_input:
        st.session_state.last_input = current_input
        st.session_state.confirmed_berufe = set()

    # Get initial suggestions
    initial_suggestions = match_berufe(berufe_df, current_input, n=15)
    initial_names = [s["beruf_name"] for s in initial_suggestions]

    # Get expansions based on confirmed selections
    confirmed = st.session_state.confirmed_berufe
    expanded_names = []
    if confirmed:
        expansions = expand_berufe(berufe_df, list(confirmed),
                                   initial_names + list(confirmed), n=15)
        expanded_names = [e["beruf_name"] for e in expansions]

    # All options to show = initial + expanded (no duplicates)
    all_options = initial_names + [n for n in expanded_names if n not in initial_names]

    # ── Instruction ───────────────────────────────────────────────────
    st.write(
        "Klicken Sie auf die Berufsgruppen, die von Ihrem Kurs profitieren könnten. "
        "Bereits ausgewählte Berufe erscheinen grün. "
        "Basierend auf Ihrer Auswahl werden weitere verwandte Berufsgruppen vorgeschlagen."
    )
    if not all_options:
        st.warning("Keine passenden Berufe gefunden. Bitte Beschreibung ergänzen.")
        return []

    # ── Clickable list ────────────────────────────────────────────────
    changed = False
    for beruf in all_options:
        is_sel = beruf in confirmed
        col_btn, col_badge = st.columns([5, 1])
        with col_btn:
            label = ("✓  " if is_sel else "    ") + beruf
            is_expanded = beruf in expanded_names
            border_color = "#0f6e56" if is_sel else "#1a5c9e" if is_expanded else "#ccc"
            bg_color = "#e1f5ee" if is_sel else "#eaf2fb" if is_expanded else "#fafafa"
            txt_color = "#085041" if is_sel else "#0c3a6b" if is_expanded else "#333"
            st.markdown(
                f'<div style="background:{bg_color};border:1.5px solid {border_color};'
                f'border-radius:6px;padding:6px 14px;margin:2px 0;color:{txt_color};'
                f'font-size:14px;line-height:1.4">{label}</div>',
                unsafe_allow_html=True)
        with col_badge:
            if is_expanded and not is_sel:
                st.caption("verwandt")
            btn_label = "Entfernen" if is_sel else "Auswählen"
            if st.button(btn_label, key=f"btn_{beruf}", use_container_width=True):
                if is_sel:
                    st.session_state.confirmed_berufe.discard(beruf)
                else:
                    st.session_state.confirmed_berufe.add(beruf)
                changed = True

    if changed:
        st.rerun()

    if not confirmed:
        st.info("Bitte mindestens einen Beruf auswählen, um die Nachfrageanalyse zu starten.")
        return []

    # ── Demand analysis ───────────────────────────────────────────────
    st.write("---")
    st.markdown(f"**Ausgewählt: {len(confirmed)} Berufsgruppen**")
    tags = " ".join(
        f'<span style="display:inline-block;background:#0f6e56;color:#fff;'
        f'border-radius:5px;padding:3px 10px;margin:2px;font-size:13px">{b}</span>'
        for b in sorted(confirmed))
    st.markdown(tags, unsafe_allow_html=True)
    st.write("")

    all_kldb = berufe_df[berufe_df["beruf_name"].isin(confirmed)]["kldb_id"].astype(int).tolist()
    demand_sub = demand[demand["kldb_id"].isin(all_kldb)]

    if demand_sub.empty:
        st.warning("Keine Nachfragedaten für diese Berufsgruppen in der Jobmonitor-Datenbank.")
        return all_kldb

    local_regions = (REGIONS_DISPLAY["TH Wildau Region"] +
                     REGIONS_DISPLAY["Berlin"] + REGIONS_DISPLAY["Brandenburg"])
    nd_score, nd_text = nachfrage_score(demand_sub, all_kldb, local_regions)

    col_sc2, col_info2 = st.columns([1,3])
    with col_sc2:
        score_badge(nd_score, nd_text)
    with col_info2:
        st.caption("Score 1 = geringe/sinkende Nachfrage  ·  Score 10 = stark wachsend")

    # Regional chart
    rrows = []
    for dname, db_regs in REGIONS_DISPLAY.items():
        sub = demand_sub[demand_sub["region"].isin(db_regs)]
        if sub.empty: continue
        total = sub["total_jobs"].sum()
        diff  = sub["total_diff_previous_year"].sum()
        prior = total - diff
        pct   = diff / prior if prior > 0 else 0
        rrows.append({"Region":dname,"Stellen":int(total),"Wachstum_%":round(pct*100,1)})

    if rrows:
        rdf = pd.DataFrame(rrows)
        rdf = rdf.set_index("Region").reindex(REGION_ORDER).dropna().reset_index()
        colors = rdf["Wachstum_%"].apply(
            lambda x: "#27ae60" if x>5 else "#f39c12" if x>-5 else "#c0392b")
        fig = go.Figure(go.Bar(
            x=rdf["Region"], y=rdf["Wachstum_%"],
            marker_color=colors,
            text=rdf["Wachstum_%"].apply(lambda x: f"{x:+.1f}%"),
            textposition="outside"))
        fig.update_layout(title="Nachfragewachstum 2024 → 2025",
                          yaxis_title="Wachstum (%)", height=300,
                          margin=dict(t=50,b=20), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(rdf[["Region","Stellen","Wachstum_%"]]
                     .rename(columns={"Wachstum_%":"Wachstum (%)"}),
                     use_container_width=True, hide_index=True)

    st.markdown("**Top Berufe nach Wachstum — Berlin & Brandenburg**")
    top = (demand_sub[demand_sub["region"].isin(["Berlin","Brandenburg"])]
           .groupby(["kldb_id","beruf_name"], as_index=False)
           .agg(Stellen=("total_jobs","sum"),
                Wachstum_pct=("percentage_diff_previous_year","mean"))
           .sort_values("Wachstum_pct", ascending=False).head(15))
    top["Wachstum"] = top["Wachstum_pct"].apply(
        lambda x: f"{x*100:+.1f}%" if pd.notna(x) else "n/a")
    top["Stellenausschreibungen"] = top["Stellen"].apply(lambda x: f"{int(x):,}")
    st.dataframe(top[["beruf_name","Stellenausschreibungen","Wachstum"]]
                 .rename(columns={"beruf_name":"Berufsbezeichnung",
                                  "Wachstum":"Wachstum 2024 → 2025"}),
                 use_container_width=True, hide_index=True)

    return all_kldb

def phase_3(offers, params, matched):
    section_header("#dce3ff", "5. Preisgestaltung")
    priced_all = matched.dropna(subset=["price"]) if matched is not None and len(matched) > 0 else None

    has_cost = params["dev_h"] > 0
    if has_cost:
        fix_net   = params["dev_h"]*params["dev_rate"] + params["impl_h"]*params["impl_rate"]
        fix_gross = fix_net * (1 + params["overhead"])
        be_preis  = ((fix_net / params["target_tn"]) + params["sachkosten"]) * (1 + params["overhead"])

        b1,b2,b3 = st.columns(3)
        b1.metric("Gesamte Fixkosten (inkl. Overhead)", f"{fix_gross:,.0f} EUR")
        b2.metric("Break-even-Preis pro TN",            f"{be_preis:,.0f} EUR")
        b3.metric("Bei Zielauslastung",
                  f"{params['target_tn']} TN")

        # Deckungsbeitrag chart
        tn_max = max(params["target_tn"]*3, 40)
        tn_range = list(range(1, tn_max+1))
        price_points = [500, 1000, 2000, 5000, round(be_preis/100)*100]
        price_points = sorted(set(p for p in price_points if p > 0))

        fig_be = go.Figure()
        colors_line = ["#185fa5","#27ae60","#f39c12","#9b1c1c","#7f77dd"]
        for i, preis in enumerate(price_points):
            revenue = [t * (preis/(1+params["overhead"]) - params["sachkosten"]) - fix_net
                       for t in tn_range]
            label = f"{preis:,.0f} EUR/TN"
            if abs(preis - be_preis) < 50: label += " (Break-even)"
            fig_be.add_trace(go.Scatter(
                x=tn_range, y=revenue, mode="lines", name=label,
                line=dict(width=2.5, color=colors_line[i % len(colors_line)],
                          dash="dash" if abs(preis-be_preis)<50 else "solid")))

        fig_be.add_hline(y=0, line_color="#333", line_width=1)
        fig_be.add_hline(y=0, line_dash="dot", line_color="#c0392b", line_width=1.5,
                         annotation_text="Kostendeckung", annotation_position="right")
        fig_be.add_vline(x=params["target_tn"], line_dash="dash",
                         line_color="#888", line_width=1,
                         annotation_text=f"Ziel: {params['target_tn']} TN")
        fig_be.update_layout(
            title="Deckungsbeitrag je Preispunkt und Teilnehmerzahl",
            xaxis_title="Teilnehmerzahl", yaxis_title="Ergebnis (EUR)",
            height=400, margin=dict(t=50,b=80),
            legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig_be, use_container_width=True)
        st.caption("Oberhalb der Nulllinie ist der Kurs profitabel. "
                   "Die gestrichelte Linie zeigt Ihren Break-even-Preis.")

        st.write("")
        be_table = []
        for p in [500,1000,2000,3000,5000,8000,10000,15000]:
            d = p/(1+params["overhead"]) - params["sachkosten"]
            if d > 0:
                be_table.append({"Preis pro TN (EUR)": f"{p:,}",
                                 "Benötigte TN für Break-even": math.ceil(fix_net/d)})
        if be_table:
            st.dataframe(pd.DataFrame(be_table), use_container_width=True, hide_index=True)

        st.write("---")

    st.subheader("Marktpreise ähnlicher Kurse")
    if priced_all is not None and len(priced_all) >= 3:
        p25 = priced_all["price"].quantile(.25)
        med = priced_all["price"].median()
        p75 = priced_all["price"].quantile(.75)

        fig_mkt = px.box(priced_all, y="price", points="outliers",
            title="Preisverteilung ähnlicher Kurse",
            labels={"price":"Preis (EUR)"},
            color_discrete_sequence=["#185fa5"], height=300)
        if has_cost:
            fig_mkt.add_hline(y=be_preis, line_dash="dash", line_color="#c0392b",
                              annotation_text="Ihr Break-even",
                              annotation_position="top right")
        fig_mkt.update_layout(margin=dict(t=50,b=10))
        st.plotly_chart(fig_mkt, use_container_width=True)

        col1,col2,col3,col4 = st.columns(4)
        col1.metric("25. Perz.",        f"{p25:,.0f} EUR")
        col2.metric("Median",           f"{med:,.0f} EUR")
        col3.metric("75. Perz.",        f"{p75:,.0f} EUR")
        col4.metric("Empfohlene Spanne",f"{p25:,.0f} – {p75:,.0f} EUR")

        if has_cost:
            if be_preis < p25:
                st.success(f"Ihr Break-even ({be_preis:,.0f} EUR) liegt unter dem 25. Perzentil — gute Spielräume.")
            elif be_preis < med:
                st.info(f"Ihr Break-even ({be_preis:,.0f} EUR) liegt im unteren Marktbereich.")
            else:
                st.warning(f"Ihr Break-even ({be_preis:,.0f} EUR) liegt über dem Marktmedian — Kostensenkung prüfen.")
    else:
        st.info("Bitte Kurstitel und Beschreibung eingeben, um Marktpreise zu berechnen.")

def feedback_section():
    st.write("---")
    section_header("#f5f5f5", "Feedback")
    st.markdown("Ihr Feedback hilft, das Werkzeug zu verbessern. Das Formular dauert ca. 2 Minuten:")
    FORM_URL = ("https://docs.google.com/forms/d/1m-3oij-Lcb59ilQMUcHaRDS56fNFwi8J194jRNgxq64"
                "/viewform?embedded=true")
    st.markdown(
        f'<iframe src="{FORM_URL}" width="100%" height="560" '
        f'frameborder="0" marginheight="0" marginwidth="0">Wird geladen...</iframe>',
        unsafe_allow_html=True)

# ─── MAIN ────────────────────────────────────────────────────────────────

def main():
    offers = load_offers()
    demand = load_demand()
    berufe = load_berufe()
    kgs    = load_kgs()

    with st.sidebar:
        st.markdown("""
## Weiterbildungs-Radar
### TH Wildau

Dieses Werkzeug unterstützt Lehrende dabei, eine neue Weiterbildungsidee zu analysieren — bevor die eigentliche Kursentwicklung beginnt.

---

### Wie funktioniert die Suche?

**Angebotssuche** — Das Werkzeug vergleicht Ihren Kurstitel und Ihre Beschreibung mit über 13.000 Kursen aus hochundweit.de und mein-now.de. Die Ähnlichkeit wird über Schlagwortabgleich berechnet: übereinstimmende Wörter und Wortstämme erhöhen die Punktzahl. Zusätzlich werden thematische Schwerpunkte (PGT/QST) berücksichtigt, wenn Sie diese auswählen. Je mehr Beschreibungstext Sie eingeben, desto besser die Ergebnisse.

**Kategorisierung (PGT/QST)** — Kurse sind in zwei Systemen kategorisiert. Die *Profilgebenden Themen (PGT)* unterscheiden zwischen Verwaltung, Mobilität und Wertschöpfung. Die *Querschnittsthemen (QST)* erfassen übergreifende Dimensionen wie Nachhaltigkeit, Diversity und Internationalisation. Ein Kurs kann mehrere Kategorien haben. Die Kategorisierung basiert auf einem regelbasierten Schlüsselwortsystem.

**Angebots-Score** — Der Score (1–10) gibt an, wie stark der Markt mit ähnlichen Kursen besetzt ist. Er basiert auf der Anzahl der Treffer: 0 Treffer = Score 1 (Marktlücke), über 40 Treffer = Score 10 (sehr gesättigt). Der Score ist kein absolutes Qualitätsurteil — ein Score von 7 bedeutet, dass Differenzierung wichtig ist, nicht dass der Kurs nicht sinnvoll wäre.

---

### Wie funktioniert die Berufssuche?

Das Werkzeug gleicht Ihren Text mit 1.210 Berufsbezeichnungen aus der KldB-Systematik (Klassifikation der Berufe, Bundesagentur für Arbeit) ab. Dabei werden drei Methoden kombiniert:

1. **Direkte Wortübereinstimmung** — z.B. "Automatisierung" trifft auf Berufe, die dieses Wort im Namen tragen.
2. **Stammabgleich** — die ersten fünf Buchstaben werden verglichen, damit "Maschinenbau" auch "Maschinenbauer" findet.
3. **Konzept-Mapping** — Fachbegriffe wie "KI", "DSGVO" oder "Supply Chain" werden auf die passenden KldB-Berufsgruppen gemappt (z.B. KI → Informatikberufe, DSGVO → Rechts- und Verwaltungsberufe), da diese Begriffe meist nicht direkt in Berufsbezeichnungen vorkommen.

Nur Berufe ab Spezialistenniveau (KldB-Endziffer 3 oder 4) werden angezeigt.

**Nachfrage-Score** — Der Score (1–10) basiert auf dem medianen prozentualen Wachstum der Stellenanzeigen für die gewählten Berufe in der Region (2024→2025) plus einem Größenbonus für absolute Stellenzahlen. Score 1 = sinkende oder keine Nachfrage, Score 10 = stark wachsende Nachfrage.

---

### Wie wird der Preis berechnet?

**Break-even-Preis** = ((Entwicklungskosten + Implementierungskosten) / Teilnehmerzahl + Sachkosten pro TN) × (1 + Overhead-Zuschlag)

Der Deckungsbeitrags-Chart zeigt, ab wie vielen Teilnehmern verschiedene Preispunkte die Fixkosten decken. Die Marktpreisverteilung zeigt Median, 25. und 75. Perzentil ähnlicher Kurse aus der Datenbank.

---

**Datenquellen**

Angebotsdaten: hochundweit.de und mein-now.de (Stand 2025, über 13.000 Kurse).

Nachfragedaten: Jobmonitor der Bertelsmann Stiftung, Stellenanzeigenanalyse 2024–2025, Regionen Berlin, Brandenburg, Dahme-Spreewald, Oder-Spree, Teltow-Fläming.

---

*Dieser Prototyp dient zur Orientierung. Alle Ergebnisse ersetzen keine vollständige Marktanalyse.*

---
        """)
        st.caption("Version 1.0 · TH Wildau 2025")

    st.title("Weiterbildungs-Radar")
    st.markdown(
        "Analysieren Sie Angebot, Nachfrage und Preisgestaltung für Ihre Weiterbildungsidee. "
        "Geben Sie Ihren Kurstitel und eine kurze Beschreibung ein — das Werkzeug führt Sie "
        "durch drei Analyseschritte."
    )

    st.markdown("""
<div style="display:flex;gap:16px;margin:1rem 0 1.5rem 0;flex-wrap:wrap">

<div style="flex:1;min-width:220px;background:#e8f4fd;border-radius:10px;padding:1rem 1.2rem;border-top:4px solid #185fa5">
<div style="font-size:1rem;font-weight:700;color:#0c3a6b;margin-bottom:6px">Schritt 1 &nbsp; Angebot</div>
<div style="font-size:13px;color:#1a3a5c;line-height:1.6">
Wie viele ähnliche Kurse gibt es bereits? Das Werkzeug durchsucht über 13.000 Weiterbildungsangebote
aus ganz Deutschland und filtert nach Ihrer Region — lokal (TH Wildau Umgebung),
regional (Berlin &amp; Brandenburg) und national. Sie erhalten einen <strong>Angebots-Score</strong>
(1–10), der zeigt, wie gesättigt der Markt ist: ein niedriger Score bedeutet eine Marktlücke,
ein hoher Score bedeutet starken Wettbewerb. Die Kurse werden nach inhaltlicher Ähnlichkeit zu
Ihrer Idee sortiert und mit Preisangaben und Links angezeigt.
</div></div>

<div style="flex:1;min-width:220px;background:#fff4e6;border-radius:10px;padding:1rem 1.2rem;border-top:4px solid #c77700">
<div style="font-size:1rem;font-weight:700;color:#6b3800;margin-bottom:6px">Schritt 2 &nbsp; Nachfrage</div>
<div style="font-size:13px;color:#4a2800;line-height:1.6">
Welche Berufsgruppen würden von Ihrem Kurs profitieren, und wächst die Nachfrage nach
diesen Berufen? Das Werkzeug schlägt passende Berufsbilder vor — Sie wählen die relevanten aus.
Je mehr Sie auswählen, desto mehr verwandte Berufe werden vorgeschlagen. Auf Basis der
Jobmonitor-Daten der Bertelsmann Stiftung (Stellenanzeigenanalyse 2024–2025) erhalten Sie
einen <strong>Nachfrage-Score</strong> (1–10) sowie eine Übersicht über das Wachstum in
Berlin, Brandenburg und der TH Wildau Region.
</div></div>

<div style="flex:1;min-width:220px;background:#ede8ff;border-radius:10px;padding:1rem 1.2rem;border-top:4px solid #5b3fd4">
<div style="font-size:1rem;font-weight:700;color:#2d1a7a;margin-bottom:6px">Schritt 3 &nbsp; Preisgestaltung</div>
<div style="font-size:13px;color:#1e1050;line-height:1.6">
Was können Sie für den Kurs verlangen? Wenn Sie Ihre Kostenstruktur eingeben
(Entwicklungsstunden, Stundensätze, Sachkosten), berechnet das Werkzeug Ihren
<strong>Break-even-Preis</strong> und zeigt, wie viele Teilnehmer bei verschiedenen
Preispunkten benötigt werden. Die Marktpreisverteilung ähnlicher Kurse zeigt, ob Ihre
Kalkulation realistisch ist.
</div></div>

</div>
""", unsafe_allow_html=True)

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
