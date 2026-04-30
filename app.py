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

def match_offers(offers, user_text, selected_cats, kg, n_per_source=30):
    """
    Score courses by relevance to user_text.
    Title matches are weighted 5× more than description matches.
    Description matches are length-normalised to prevent MN's long
    keyword-stuffed titles from dominating over concise HW titles.
    Returns up to n_per_source from each source, sorted by score.
    """
    user_words = tokenize(user_text)
    user_stems = {w[:5] for w in user_words if len(w) >= 4}
    scores = []
    for _, row in offers.iterrows():
        s = 0.0
        title = str(row.get("title","")).lower()
        desc  = str(row.get("description","")).lower()
        tw = tokenize(title); dw = tokenize(desc)
        ts = {w[:5] for w in tw if len(w)>=4}
        ds = {w[:5] for w in dw if len(w)>=4}
        desc_len = max(len(dw), 1)

        # Title match: high fixed weight per match
        t_exact = user_words & tw
        t_stem  = (user_stems & ts) - user_words
        s += len(t_exact) * 5.0
        s += len(t_stem)  * 2.0

        # Description: log-normalised to prevent length advantage
        d_exact = user_words & dw
        d_stem  = (user_stems & ds) - user_words - t_exact
        if d_exact:
            s += math.log(1 + len(d_exact)) / math.log(1 + desc_len) * 8
        if d_stem:
            s += math.log(1 + len(d_stem))  / math.log(1 + desc_len) * 3

        for cat in selected_cats:
            if row.get(cat, False): s += 2.0
        if kg and str(row.get("knowledgeGroup","")) == kg: s += 1.5
        scores.append(s)

    o2 = offers.copy(); o2["_score"] = scores
    o2 = o2[o2["_score"] > 0].sort_values("_score", ascending=False)
    hw = o2[o2["source"] == "hochundweit"].head(n_per_source)
    mn = o2[o2["source"] == "meinnow"].head(n_per_source)
    return pd.concat([hw, mn]).sort_values("_score", ascending=False).reset_index(drop=True)

def score_badge(score, label):
    # 10 = green (good), 1 = red (bad)
    c = "#9b1c1c" if score<=3 else "#854f0b" if score<=6 else "#0f6e56"
    bg= "#fee2e2" if score<=3 else "#faeeda" if score<=6 else "#e1f5ee"
    st.markdown(
        f'<div style="display:inline-flex;align-items:center;gap:12px;'
        f'background:{bg};border-radius:10px;padding:12px 20px;margin:6px 0">'
        f'<span style="font-size:2rem;font-weight:700;color:{c};line-height:1">{score}/10</span>'
        f'<span style="color:{c};font-size:.9rem;line-height:1.4">{label}</span></div>',
        unsafe_allow_html=True)

def angebots_score(n):
    # 10 = best (little competition), 1 = worst (very saturated)
    if n==0:   return 10,"Kaum Angebot vorhanden — Lücke im Markt."
    if n<=3:   return 9,"Sehr geringes Angebot — gute Marktchance."
    if n<=8:   return 7,"Moderates Angebot — Differenzierung empfehlenswert."
    if n<=20:  return 5,"Angebot vorhanden — klares Profil nötig."
    if n<=40:  return 3,"Starkes Angebot — Nische oder USP wichtig."
    return 1,"Sehr gesättigter Markt — Positionierung entscheidend."

def nachfrage_score(demand, kldb_ids, region_names):
    """
    Weighted score: local (TH Wildau) = 3×, Berlin/BB = 2×, national = 1×.
    """
    LOCAL  = ["Dahme-Spreewald","Oder-Spree","Teltow-Fläming"]
    BB     = ["Berlin","Brandenburg"]
    weights = {r: 3 for r in LOCAL}
    weights.update({r: 2 for r in BB})

    sub = demand[demand["kldb_id"].isin(kldb_ids) & demand["region"].isin(region_names)]
    if sub.empty: return 1,"Keine Nachfragedaten für diese Berufe."

    sub = sub.copy()
    sub["_w"] = sub["region"].map(lambda r: weights.get(r, 1))

    # Weighted median growth
    rows_w = []
    for _, row in sub.iterrows():
        rows_w.extend([row["percentage_diff_previous_year"]] * int(row["_w"]))
    rows_w = [x for x in rows_w if pd.notna(x)]
    if not rows_w: return 3,"Unzureichende Daten."

    rows_w.sort()
    mg = rows_w[len(rows_w)//2]
    tj = (sub["total_jobs"] * sub["_w"]).sum() / sub["_w"].sum()  # weighted avg

    gs = min(10, max(1, int((mg*100+5)*1.2)))
    sb = min(2, math.log10(max(tj,1))/3)
    f  = min(10, max(1, round(gs+sb)))
    trend = "wachsend" if mg>0.05 else "stabil" if mg>-0.05 else "rückläufig"
    return f, f"Trend: {trend}  ·  Wachstum (gewichtet): {mg*100:+.1f}%  ·  Stellen: {int(sub['total_jobs'].sum()):,}"

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

    # Split by purpose:
    # Wettbewerb: same-format courses (Präsenz/Hybrid/Berufsbegleitend) = real competition
    # Preisreferenz: all formats including online = broader price benchmark
    PHYSICAL_FORMATS = ["Berufsbegleitender","Präsenz","Blockkurs","Hybrid","Wochenend",
                        "Seminar","Praxistraining","Teilzeit","Vollzeit","Studium"]

    def is_physical(fmt):
        return any(f in str(fmt) for f in PHYSICAL_FORMATS)

    matched_competition = matched[matched["format"].apply(is_physical)].reset_index(drop=True)
    matched_price       = matched.reset_index(drop=True)  # all formats

    n_comp  = len(matched_competition)
    n_total = len(matched)
    score, score_text = angebots_score(n_comp)

    col_sc, col_info = st.columns([1,3])
    with col_sc:
        score_badge(score, score_text)
    with col_info:
        st.write(
            f"**{n_comp}** inhaltlich ähnliche Präsenz/Hybrid-Kurse gefunden "
            f"(von {n_total} Treffern gesamt inkl. Online). "
            f"Score 10 = wenig Wettbewerb, Score 1 = stark gesättigter Markt."
        )

    if "deselected" not in st.session_state:
        st.session_state.deselected = set()

    st.markdown("""<div style="height:8px"></div>""", unsafe_allow_html=True)

    subtab_wett, subtab_preis = st.tabs([
        f"Wettbewerbs-Angebote ({n_comp} Präsenz/Hybrid)",
        f"Preisreferenz ({n_total} inkl. Online)",
    ])

    ctrl1, _ = st.columns([1,4])
    n_display = ctrl1.selectbox("Angebote pro Seite", [10, 20], index=0, key="n_display")

    def show_offers(df_src, tab_key, show_price_stats=True):
        if df_src.empty:
            st.info("Keine passenden Angebote für diese Kombination."); return

        # Filter out deselected
        active = df_src[~df_src["id"].astype(str).isin(st.session_state.deselected)].reset_index(drop=True)
        n_excl = len(df_src) - len(active)
        if n_excl:
            st.caption(f"{n_excl} Angebot(e) ausgeblendet.")

        # Pagination
        n_pages  = max(1, math.ceil(len(df_src) / n_display))
        pk       = f"page_{tab_key}"
        if pk not in st.session_state: st.session_state[pk] = 0
        page     = max(0, min(st.session_state[pk], n_pages-1))
        page_rows = df_src.iloc[page*n_display:(page+1)*n_display].copy()

        # Table header
        st.markdown(
            '<div style="display:grid;grid-template-columns:90px 1fr 140px 80px 90px 80px 70px;'
            'gap:0;background:#f0f4f8;padding:5px 0;font-size:12px;font-weight:600;'
            'border-bottom:2px solid #ccc;margin-bottom:2px">'
            '<span style="padding:0 6px">Quelle</span>'
            '<span style="padding:0 6px">Titel</span>'
            '<span style="padding:0 6px">Anbieter</span>'
            '<span style="padding:0 6px">Umfang</span>'
            '<span style="padding:0 6px">Preis</span>'
            '<span style="padding:0 6px">Link</span>'
            '<span style="padding:0 6px"></span>'
            '</div>',
            unsafe_allow_html=True)

        changed = False
        for _, row in page_rows.iterrows():
            rid      = str(row["id"])
            is_active = rid not in st.session_state.deselected

            pb = str(row.get("price_band",""))
            price_str = (PREIS_LABELS.get(pb) if pb in PREIS_LABELS
                         else (f"{row['price']:,.0f} EUR" if pd.notna(row.get("price")) and row["price"]>0 else "k.A."))
            url   = str(row.get("url",""))
            link  = (f'<a href="{url}" target="_blank">Link&nbsp;&rarr;</a>' if url.startswith("http") else "—")
            umf   = str(row.get("umfang","") or "k.A.")
            title = str(row.get("title",""))[:52]
            prov  = str(row.get("provider",""))[:22]
            src_l = row.get("source","")
            badge = ('<span style="background:#dceefb;color:#0c3a6b;padding:1px 6px;border-radius:4px;font-size:11px">HW</span>'
                     if src_l=="hochundweit" else
                     '<span style="background:#faeeda;color:#6b3000;padding:1px 6px;border-radius:4px;font-size:11px">MN</span>')
            row_bg = "#fafafa" if is_active else "#fff0f0"

            st.markdown(
                f'<div style="display:grid;grid-template-columns:90px 1fr 140px 80px 90px 80px 70px;' +
                f'gap:0;background:{row_bg};padding:4px 0;font-size:13px;' +
                f'border-bottom:1px solid #e8e8e8;align-items:center">' +
                f'<span style="padding:0 6px">{badge}</span>' +
                f'<span style="padding:0 6px" title="{str(row.get("title",""))}">{title}</span>' +
                f'<span style="padding:0 6px;color:#555;font-size:12px">{prov}</span>' +
                f'<span style="padding:0 6px;color:#555;font-size:12px">{umf}</span>' +
                f'<span style="padding:0 6px;font-weight:500">{price_str}</span>' +
                f'<span style="padding:0 6px">{link}</span>' +
                f'<span style="padding:0 6px"></span>' +
                '</div>',
                unsafe_allow_html=True)

            btn_label = "Ausblenden" if is_active else "Wieder anzeigen"
            if st.button(btn_label, key=f"btn_{tab_key}_{rid}", use_container_width=False):
                if is_active:
                    st.session_state.deselected.add(rid)
                else:
                    st.session_state.deselected.discard(rid)
                changed = True

        if changed:
            st.rerun()

        # Pagination controls
        if n_pages > 1:
            pc1, pc2, pc3 = st.columns([1,2,1])
            if pc1.button("← Zurück", key=f"prev_{tab_key}", disabled=page==0):
                st.session_state[pk] = page-1; st.rerun()
            pc2.markdown(f'<div style="text-align:center;padding:6px;font-size:13px">'
                         f'Seite {page+1} von {n_pages}</div>', unsafe_allow_html=True)
            if pc3.button("Weiter →", key=f"next_{tab_key}", disabled=page==n_pages-1):
                st.session_state[pk] = page+1; st.rerun()

        if not show_price_stats: return

        # Price stats from active HW courses (real granular prices)
        hw_act = active[(active["source"]=="hochundweit") &
                        active["price"].notna() & (active["price"]>0)]
        mn_act = active[active["source"]=="meinnow"]

        st.markdown("")
        if len(hw_act) >= 3:
            st.markdown("**Preisstatistik — Hochschulangebote (reale Preise):**")
            m1,m2,m3 = st.columns(3)
            m1.metric("Median",    f"{hw_act['price'].median():,.0f} EUR")
            m2.metric("25. Perz.", f"{hw_act['price'].quantile(.25):,.0f} EUR")
            m3.metric("75. Perz.", f"{hw_act['price'].quantile(.75):,.0f} EUR")
        if len(mn_act) >= 2:
            bands = mn_act["price_band"].value_counts()
            band_str = "  ·  ".join(
                f"{PREIS_LABELS.get(b,b)}: {c}" for b,c in bands.items())
            st.caption(f"Weiterbildungsangebote (Preisbänder): {band_str}")
        elif len(hw_act) < 3:
            st.caption("Zu wenige Preisangaben für Statistik.")

        # Legend
        st.markdown(
            '<div style="margin-top:4px;font-size:12px;color:#666">' +
            '<span style="background:#dceefb;color:#0c3a6b;padding:1px 6px;border-radius:4px">HW</span> ' +
            'hochundweit.de &nbsp;·&nbsp;' +
            '<span style="background:#faeeda;color:#6b3000;padding:1px 6px;border-radius:4px">MN</span> ' +
            'mein-now.de</div>', unsafe_allow_html=True)

    with subtab_wett:
        tab_local, tab_regional, tab_national = st.tabs([
            "Lokal — TH Wildau",
            "Regional — Berlin/BB",
            "National",
        ])
        def geo_filter(df, tiers):
            geo   = df[df["geo_tier"].isin(tiers)]
            return geo.drop_duplicates(subset=["id"]).reset_index(drop=True)

        with tab_local:
            show_offers(geo_filter(matched_competition, ["wildau"]), "wett_local")
        with tab_regional:
            show_offers(geo_filter(matched_competition, ["wildau","berlin_bb"]), "wett_regional")
        with tab_national:
            show_offers(matched_competition, "wett_national")

    with subtab_preis:
        st.caption("Alle Formate (inkl. Online) — für Preisvergleich und Marktsättigung.")
        tab_local2, tab_regional2, tab_national2 = st.tabs([
            "Lokal — TH Wildau",
            "Regional — Berlin/BB",
            "National",
        ])
        with tab_local2:
            show_offers(geo_filter(matched_price, ["wildau"]), "preis_local")
        with tab_regional2:
            show_offers(geo_filter(matched_price, ["wildau","berlin_bb"]), "preis_regional")
        with tab_national2:
            show_offers(matched_price, "preis_national")

    return matched_price


def phase_2(berufe_df, demand, params):
    section_header("#fff0d4", "4. Nachfrage — wer braucht diesen Kurs?")
    if not params["user_text"].strip():
        st.info("Bitte Kurstitel und Beschreibung eingeben."); return []

    current_input = params["user_text"]

    # ── Session state ────────────────────────────────────────────────
    if "confirmed_berufe"  not in st.session_state: st.session_state.confirmed_berufe  = set()
    if "last_nd_input"     not in st.session_state: st.session_state.last_nd_input     = ""
    if "nd_base"           not in st.session_state: st.session_state.nd_base           = []
    if "nd_shown_count"    not in st.session_state: st.session_state.nd_shown_count    = 5
    if "nd_pool"           not in st.session_state: st.session_state.nd_pool           = []

    # Recompute only when text changes
    if current_input != st.session_state.last_nd_input:
        st.session_state.last_nd_input   = current_input
        st.session_state.confirmed_berufe = set()
        st.session_state.nd_shown_count  = 5
        base = match_berufe(berufe_df, current_input, n=30)
        st.session_state.nd_base  = [b["beruf_name"] for b in base]
        st.session_state.nd_pool  = st.session_state.nd_base.copy()

    confirmed = st.session_state.confirmed_berufe

    # Expand pool when user has made selections
    if confirmed:
        all_known = set(st.session_state.nd_pool) | confirmed
        expansions = expand_berufe(berufe_df, list(confirmed), list(all_known), n=30)
        new_exp = [e["beruf_name"] for e in expansions if e["beruf_name"] not in all_known]
        # Add new expansions to pool if not already there
        for b in new_exp:
            if b not in st.session_state.nd_pool:
                st.session_state.nd_pool.append(b)

    # Candidates = pool minus already confirmed, up to shown_count
    candidates = [b for b in st.session_state.nd_pool if b not in confirmed]
    shown      = candidates[:st.session_state.nd_shown_count]
    has_more   = len(candidates) > st.session_state.nd_shown_count

    # ── Instructions ─────────────────────────────────────────────────
    st.write(
        "Klicken Sie auf die Kacheln, um Berufsgruppen als Zielgruppe auszuwählen. "
        "Ausgewählte Kacheln erscheinen grün. Klicken Sie **Weitere Vorschläge**, "
        "um mehr verwandte Berufsgruppen zu sehen."
    )

    # ── Tile grid: unconfirmed suggestions ───────────────────────────
    if shown:
        cols = st.columns(min(len(shown), 3))
        changed = False
        for i, beruf in enumerate(shown):
            is_exp = beruf not in st.session_state.nd_base
            tag    = " ↗" if is_exp else ""
            with cols[i % 3]:
                # Grey tile — clickable to select
                if st.button(
                    beruf + tag,
                    key=f"tile_add_{beruf}",
                    use_container_width=True,
                    help="Klicken zum Auswählen" + (" (verwandter Vorschlag)" if is_exp else ""),
                ):
                    st.session_state.confirmed_berufe.add(beruf)
                    changed = True
                # Style via CSS injection (Streamlit buttons cannot be styled directly)
        if changed:
            st.rerun()

    # "Weitere Vorschläge" button
    col_more, _ = st.columns([1,3])
    if has_more:
        if col_more.button("Weitere Vorschläge anzeigen"):
            st.session_state.nd_shown_count += 5
            st.rerun()

    # ── Selected tiles (green) ────────────────────────────────────────
    if confirmed:
        st.markdown("**Ausgewählt:**")
        cols2 = st.columns(min(len(confirmed), 3))
        changed2 = False
        for i, beruf in enumerate(sorted(confirmed)):
            with cols2[i % 3]:
                st.markdown(
                    f'<div style="background:#0f6e56;color:#fff;border-radius:8px;' +
                    f'padding:9px 12px;margin:2px 0;font-size:13px;line-height:1.4;text-align:center">' +
                    f'{beruf}</div>',
                    unsafe_allow_html=True)
                if st.button("× Entfernen", key=f"del2_{beruf}", use_container_width=True):
                    st.session_state.confirmed_berufe.discard(beruf)
                    changed2 = True
        if changed2:
            st.rerun()
    else:
        st.info("Bitte mindestens eine Berufsgruppe auswählen, um die Nachfrageanalyse zu starten.")
        return []

    # ── Demand analysis ───────────────────────────────────────────────
    st.write("---")
    all_kldb = berufe_df[berufe_df["beruf_name"].isin(confirmed)]["kldb_id"].astype(int).tolist()
    demand_sub = demand[demand["kldb_id"].isin(all_kldb)]

    if demand_sub.empty:
        st.warning("Keine Nachfragedaten für diese Berufsgruppen in der Jobmonitor-Datenbank.")
        return all_kldb

    all_regions = (REGIONS_DISPLAY["TH Wildau Region"] + REGIONS_DISPLAY["Berlin"] +
                   REGIONS_DISPLAY["Brandenburg"] + REGIONS_DISPLAY["Deutschland"])
    nd_score, nd_text = nachfrage_score(demand_sub, all_kldb, all_regions)

    col_sc2, col_info2 = st.columns([1,3])
    with col_sc2:
        score_badge(nd_score, nd_text)
    with col_info2:
        st.caption("Score 10 = stark wachsende lokale Nachfrage  ·  Score 1 = sinkend oder gering")
        st.caption("Lokale Nachfrage (TH Wildau Region) wird dreifach, Berlin/BB zweifach gewichtet.")

    # Regional chart
    rrows = []
    for dname, db_regs in REGIONS_DISPLAY.items():
        sub = demand_sub[demand_sub["region"].isin(db_regs)]
        if sub.empty: continue
        total = sub["total_jobs"].sum()
        diff  = sub["total_diff_previous_year"].sum()
        prior = total - diff
        pct   = diff / prior if prior > 0 else 0
        rrows.append({"Region":dname,"Stellenausschreibungen":int(total),"Wachstum_%":round(pct*100,1)})

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
        st.dataframe(rdf[["Region","Stellenausschreibungen","Wachstum_%"]]
                     .rename(columns={"Wachstum_%":"Wachstum (%)"}),
                     use_container_width=True, hide_index=True)

    st.markdown("**Top Berufe nach Wachstum — Berlin & Brandenburg**")
    top = (demand_sub[demand_sub["region"].isin(["Berlin","Brandenburg"])]
           .groupby(["kldb_id","beruf_name"], as_index=False)
           .agg(Stellen=("total_jobs","sum"),
                Wachstum_pct=("percentage_diff_previous_year","mean"))
           .sort_values("Wachstum_pct", ascending=False).head(15))
    top["Wachstum 2024→2025"] = top["Wachstum_pct"].apply(
        lambda x: f"{x*100:+.1f}%" if pd.notna(x) else "n/a")
    top["Stellenausschreibungen"] = top["Stellen"].apply(lambda x: f"{int(x):,}")
    st.dataframe(top[["beruf_name","Stellenausschreibungen","Wachstum 2024→2025"]]
                 .rename(columns={"beruf_name":"Berufsbezeichnung"}),
                 use_container_width=True, hide_index=True)

    return all_kldb


def phase_3(offers, params, matched):
    section_header("#dce3ff", "5. Preisgestaltung")
    priced_all = matched[
    (matched["source"] == "hochundweit") &
    matched["price"].notna() &
    (matched["price"] > 0)
] if matched is not None and len(matched) > 0 else None

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
