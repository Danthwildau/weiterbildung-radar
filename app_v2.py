"""
Weiterbildungs-Radar v2 — TH Wildau
Two-mode entry: "Ich habe eine Idee" (directed) or "Ich suche Inspiration" (exploratory).
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
    initial_sidebar_state="collapsed",
)

# ─── GLOBAL CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Clean white background, single column feel */
.main .block-container { max-width: 860px; padding-top: 2rem; }

/* Mode cards */
.mode-card {
    border: 2px solid #e0e0e0; border-radius: 12px;
    padding: 28px 24px; cursor: pointer; transition: border-color .15s;
    background: #fff; text-align: center;
}
.mode-card:hover { border-color: #185fa5; }
.mode-card.active { border-color: #185fa5; background: #f0f6ff; }

/* Competency chips */
.chip {
    display: inline-block; border-radius: 20px;
    padding: 5px 14px; margin: 3px; font-size: 13px;
    cursor: pointer; transition: all .1s;
}
.chip-green  { background:#e1f5ee; color:#085041; border:1.5px solid #0f6e56; }
.chip-active { background:#0f6e56; color:#fff;    border:1.5px solid #0f6e56; }
.chip-blue   { background:#dceefb; color:#0c3a6b; border:1.5px solid #185fa5; }
.chip-grey   { background:#f5f5f5; color:#555;    border:1.5px solid #ccc; }

/* Inline result cards */
.result-card {
    border: 1px solid #e8e8e8; border-radius: 10px;
    padding: 16px 20px; margin: 8px 0; background: #fafafa;
}

/* Step indicators */
.step-dot {
    display:inline-block; width:10px; height:10px;
    border-radius:50%; background:#ccc; margin:0 3px;
}
.step-dot.done { background:#0f6e56; }
.step-dot.active { background:#185fa5; }

/* Demand bar */
.demand-bar-wrap { background:#f0f0f0; border-radius:4px; height:8px; margin:4px 0; }
.demand-bar { background:#185fa5; border-radius:4px; height:8px; }
.demand-bar.grow { background:#0f6e56; }
.demand-bar.fall { background:#c0392b; }

/* Suppress Streamlit chrome */
header[data-testid="stHeader"] { display:none; }
footer { display:none; }
</style>
""", unsafe_allow_html=True)

# ─── PATHS & CONSTANTS ───────────────────────────────────────────────────────
DATA = Path(__file__).parent / "data"

CAT_COLS = [
    "PGT_effektive_Verwaltung","PGT_effektive_Verwaltung_oeffentlich",
    "PGT_zukunftsfaehige_Mobilitaet","PGT_nachhaltige_Wertschoepfung",
    "QST_Diversity","QST_Nachhaltigkeit","QST_Internationalisation",
]

PREIS_LABELS = {
    "BIS_500_EUR":"bis 500 EUR","UEBER_500_BIS_1000_EUR":"500–1.000 EUR",
    "UEBER_1000_BIS_5000_EUR":"1.000–5.000 EUR",
    "UEBER_5000_BIS_10000_EUR":"5.000–10.000 EUR","UEBER_10000_EUR":"über 10.000 EUR",
}

DELIVERY_LABELS = {
    "fully_online":"Vollständig online","hybrid_flexible":"Hybrid (ortsunabhängig)",
    "hybrid_location":"Hybrid (Standort)","in_person":"Präsenz",
}
DELIVERY_COLORS = {
    "fully_online":"#e8eaf6","hybrid_flexible":"#e8f5e9",
    "hybrid_location":"#fff8e1","in_person":"#fce4ec",
}

REGIONS_DISPLAY = {
    "TH Wildau Region": ["Dahme-Spreewald","Oder-Spree","Teltow-Fläming"],
    "Berlin": ["Berlin"],
    "Brandenburg": ["Brandenburg"],
    "Deutschland": ["Deutschland"],
}
REGION_ORDER = ["TH Wildau Region","Berlin","Brandenburg","Deutschland"]

REGION_WEIGHTS = {
    "Dahme-Spreewald":3,"Oder-Spree":3,"Teltow-Fläming":3,
    "Berlin":2,"Brandenburg":2,"Deutschland":1,
}

SHORT_TECH = {"ki","it","iot","erp","crm","sap","ai","ml","bi","bim","cad",
              "cam","cnc","plm","rpa","api","sql","hr","aws","gcp","kpi","ux","ui"}

# ─── SEARCH INFRASTRUCTURE ───────────────────────────────────────────────────
import os as _os
HF_TOKEN = _os.getenv("HF_TOKEN","")
HF_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
HF_API   = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{HF_MODEL}"

STOP_EDUCATIONAL = [
    "lernen","lernst","lehren","lehre","studieren","studium","kurs","kurse",
    "modul","module","thema","themen","bereich","bereichen","grundlagen",
    "einführung","vertiefung","überblick","werden","durch","sowie","auch",
    "können","haben","sein","eine","einen","einer","über","nach","beim",
    "liegt","wird","sind","mehr","noch","dazu","weitere","weiteren","dabei",
    "ziel","ziele","inhalte","inhalt","methoden","praxis","theorie",
    "kompetenz","kompetenzen","kenntnisse","fähigkeiten",
]

@st.cache_resource(show_spinner=False)
def build_tfidf_index(path: str):
    from sklearn.feature_extraction.text import TfidfVectorizer
    df = pd.read_csv(path)
    df["_text"] = df["title"].fillna("") + " " + df["description"].fillna("").str[:400]
    vec = TfidfVectorizer(max_features=25000, min_df=2, max_df=0.65,
                          sublinear_tf=True, ngram_range=(1,2),
                          stop_words=STOP_EDUCATIONAL)
    mat = vec.fit_transform(df["_text"])
    return vec, mat, df["id"].astype(str).tolist()

@st.cache_data(show_spinner=False, ttl=1800)
def hf_rerank(query: str, candidate_texts: tuple) -> list:
    if not HF_TOKEN or not candidate_texts: return []
    try:
        import requests as _req
        all_texts = [query] + list(candidate_texts)
        resp = _req.post(HF_API,
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={"inputs": all_texts, "options": {"wait_for_model": True}},
            timeout=15)
        if resp.status_code != 200: return []
        vecs = resp.json()
        def mp(v): return [sum(c)/len(c) for c in zip(*v)] if isinstance(v[0],list) else v
        qv = mp(vecs[0])
        out = []
        for v in vecs[1:]:
            cv = mp(v)
            dot = sum(a*b for a,b in zip(qv,cv))
            nq = sum(x*x for x in qv)**.5; nc = sum(x*x for x in cv)**.5
            out.append(dot/(nq*nc) if nq and nc else 0.0)
        return out
    except: return []

def tfidf_search(user_text, vectorizer, matrix, ids, offers_df, params=None, top_n=60):
    from sklearn.metrics.pairwise import cosine_similarity as _cos
    import numpy as _np
    if not user_text.strip(): return offers_df.head(0)
    q_vec  = vectorizer.transform([user_text])
    sims   = _cos(q_vec, matrix)[0]
    boosts = _np.zeros(len(sims))
    user_delivery = get_delivery_mode(params.get("format","") if params else "")
    user_degree   = str(params.get("degree","")).lower() if params else ""
    selected_cats = params.get("selected_cats",[]) if params else []
    kg            = params.get("kg","") if params else ""
    for i, r in enumerate(offers_df.itertuples(index=False)):
        b = 0.0
        if r.source == "hochundweit": b += 0.04
        geo = str(getattr(r,"geo_tier","") or "")
        if geo == "wildau": b += 0.08
        elif geo == "berlin_bb": b += 0.04
        mode = str(getattr(r,"delivery_mode","") or "")
        if mode == user_delivery: b += 0.05
        deg = str(r.degree or "").lower()
        if user_degree and deg and user_degree[:4] in deg[:4]: b += 0.03
        for cat in selected_cats:
            if getattr(r, cat, False): b += 0.03
        if kg and str(r.knowledgeGroup or "") == kg: b += 0.04
        boosts[i] = b
    final   = sims + boosts
    top_idx = _np.argsort(final)[::-1][:top_n]
    result  = offers_df.iloc[top_idx].copy()
    result["_score"] = final[top_idx]
    return result[result["_score"] > 0.04].reset_index(drop=True)

# ─── GEOCODING ───────────────────────────────────────────────────────────────
UNI_CITY = {
    "Akkon Hochschule":"Berlin","Constructor University":"Bremen",
    "FOM Hochschule für Oekonomie & Management":"Essen",
    "Filmuniversität Babelsberg":"Potsdam","Leuphana Universität":"Lüneburg",
    "TH Wildau":"Wildau","Technische Hochschule Wildau":"Wildau",
    "Hochschule für nachhaltige Entwicklung":"Eberswalde",
}
CITY_COORDS = {
    "Berlin":(52.520,13.405),"Hamburg":(53.551,9.994),"München":(48.137,11.576),
    "Köln":(50.938,6.960),"Frankfurt":(50.110,8.682),"Stuttgart":(48.775,9.182),
    "Düsseldorf":(51.225,6.783),"Leipzig":(51.340,12.375),"Dortmund":(51.514,7.468),
    "Essen":(51.457,7.012),"Bremen":(53.079,8.802),"Dresden":(51.050,13.738),
    "Potsdam":(52.390,13.064),"Wildau":(52.314,13.638),"Eberswalde":(52.833,13.822),
    "Lüneburg":(53.248,10.408),
}
GERMAN_CITIES = list(CITY_COORDS.keys())

def get_uni_city(name):
    if not isinstance(name, str): return None
    if name in UNI_CITY: return UNI_CITY[name]
    for city in GERMAN_CITIES:
        if city.lower() in name.lower(): return city
    return None

def get_delivery_mode(fmt, spatial_flex=0):
    f = str(fmt).lower(); flex = float(spatial_flex) if spatial_flex else 0
    if flex == 100 or any(x in f for x in ["fernstudium","digitaler kurs"]): return "fully_online"
    if any(x in f for x in ["combined learning","blended learning","hybrid learning",
                              "online-seminar"]): return "hybrid_flexible"
    if any(x in f for x in ["berufsbegleitend","blockkurs","studium"]): return "hybrid_location"
    if any(x in f for x in ["präsenz","seminar"]): return "in_person"
    return "hybrid_location"

# ─── DATA LOADERS ────────────────────────────────────────────────────────────
@st.cache_data
def load_offers():
    df = pd.read_csv(DATA/"offers.csv")
    for c in CAT_COLS:
        if c in df.columns: df[c] = df[c].fillna(False).astype(bool)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    if "delivery_mode" not in df.columns: df["delivery_mode"] = "hybrid_location"
    if "lat" not in df.columns: df["lat"] = None
    if "lon" not in df.columns: df["lon"] = None
    if "city_name" not in df.columns: df["city_name"] = df.get("city","")
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
def load_comp_demand():
    p = DATA/"competency_demand.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()

@st.cache_data
def load_comp_map():
    p = DATA/"profession_competency_map.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()

@st.cache_data
def load_comp_summary():
    p = DATA/"competency_summary.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()

@st.cache_data
def load_kgs():
    with open(DATA/"knowledge_groups.json", encoding="utf-8") as f:
        return json.load(f)

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def tokenize(text):
    return {w for w in re.findall(r'\b\w+\b', text.lower())
            if len(w) >= 4 or w in SHORT_TECH}

@st.cache_resource(show_spinner=False)
def build_topic_index(comp_demand_path: str, comp_map_path: str):
    from sklearn.feature_extraction.text import TfidfVectorizer
    comp_d = pd.read_csv(comp_demand_path)
    comp_m = pd.read_csv(comp_map_path)
    all_comps = comp_d["competency_name"].dropna().unique().tolist()
    all_profs = comp_m["profession_name"].dropna().unique().tolist()
    texts     = all_comps + all_profs
    n_comps   = len(all_comps)
    vec_w = TfidfVectorizer(min_df=1, ngram_range=(1,2), sublinear_tf=True)
    mat_w = vec_w.fit_transform(texts)
    vec_c = TfidfVectorizer(min_df=1, analyzer="char_wb", ngram_range=(4,6), sublinear_tf=True)
    mat_c = vec_c.fit_transform(texts)
    return vec_w, mat_w, vec_c, mat_c, all_comps, all_profs, n_comps

def topic_search(query, comp_demand, comp_map, berufe_df,
                 top_n_comps=12, top_n_profs=12):
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as _np
    if not query.strip(): return [], []
    vec_w, mat_w, vec_c, mat_c, all_comps, all_profs, n_comps = build_topic_index(
        str(DATA/"competency_demand.csv"), str(DATA/"profession_competency_map.csv"))
    q_w  = vec_w.transform([query])
    q_c  = vec_c.transform([query])
    sims = cosine_similarity(q_w, mat_w)[0]*0.6 + cosine_similarity(q_c, mat_c)[0]*0.4
    top_idx = _np.argsort(sims)[::-1][:top_n_comps*6]
    matched_comps, matched_prof_names = [], []
    for i in top_idx:
        if sims[i] < 0.04: break
        if i < n_comps:
            if len(matched_comps) < top_n_comps: matched_comps.append(all_comps[i])
        else:
            if len(matched_prof_names) < top_n_profs: matched_prof_names.append(all_profs[i-n_comps])
    # KldB IDs via comp_map
    prof_rows = []
    seen_names = set()
    for name in matched_prof_names:
        if name in seen_names: continue
        rows = comp_map[comp_map["profession_name"]==name][["profession_name","kldb_id"]].drop_duplicates()
        if not rows.empty:
            prof_rows.append({"beruf_name": name, "kldb_id": int(rows.iloc[0]["kldb_id"])})
            seen_names.add(name)
    # Also via competency→profession mapping
    if matched_comps:
        comp_profs = comp_map[comp_map["competency_name"].isin(matched_comps)]
        by_comp = (comp_profs.groupby(["profession_name","kldb_id"], as_index=False)
                   .agg(n=("competency_name","nunique"))
                   .sort_values("n", ascending=False).head(top_n_profs))
        for _, r in by_comp.iterrows():
            if r["profession_name"] not in seen_names:
                prof_rows.append({"beruf_name": r["profession_name"], "kldb_id": int(r["kldb_id"])})
                seen_names.add(r["profession_name"])
    return matched_comps[:top_n_comps], prof_rows[:top_n_profs]

def get_comp_for_professions(kldb_ids, comp_map, comp_demand, top_n=15):
    """Top competencies for a set of KldB IDs, demand-weighted."""
    if comp_map.empty or comp_demand.empty or not kldb_ids: return pd.DataFrame()
    kldb_str = [str(k) for k in kldb_ids]
    relevant = comp_map[comp_map["kldb_id"].astype(str).isin(kldb_str)]
    if relevant.empty: return pd.DataFrame()
    local_demand = comp_demand[
        comp_demand["region"].isin(["Dahme-Spreewald","Oder-Spree","Teltow-Fläming","Berlin"])
    ].groupby("competency_name", as_index=False).agg(
        demand_score=("demand_score","mean"),
        avg_growth=("avg_growth","mean"),
    )
    top = (relevant.groupby(["competency_name","competency_type"], as_index=False)
           .agg(rel_score=("weight","sum"), n_profs=("kldb_id","nunique"))
           .sort_values("rel_score", ascending=False).head(40))
    top = top.merge(local_demand, on="competency_name", how="left")
    top["combined"] = top["rel_score"] * top["demand_score"].fillna(1)
    return top.sort_values("combined", ascending=False).head(top_n)

def demand_chart(demand_df, kldb_ids):
    """Regional demand bar chart for given KldB IDs."""
    sub = demand_df[demand_df["kldb_id"].isin(kldb_ids)]
    if sub.empty: return None
    rows = []
    for dname, regs in REGIONS_DISPLAY.items():
        s = sub[sub["region"].isin(regs)]
        if s.empty: continue
        total = s["total_jobs"].sum()
        diff  = s["total_diff_previous_year"].sum()
        prior = total - diff
        pct   = diff / prior if prior > 0 else 0
        rows.append({"Region":dname,"Jobs":int(total),"Wachstum":round(pct*100,1)})
    if not rows: return None
    rdf = pd.DataFrame(rows)
    rdf = rdf.set_index("Region").reindex(REGION_ORDER).dropna().reset_index()
    colors = rdf["Wachstum"].apply(lambda x: "#27ae60" if x>5 else "#f39c12" if x>-5 else "#c0392b")
    fig = go.Figure(go.Bar(
        x=rdf["Region"], y=rdf["Wachstum"],
        marker_color=colors,
        text=rdf["Wachstum"].apply(lambda x: f"{x:+.1f}%"),
        textposition="outside",
        customdata=rdf["Jobs"],
        hovertemplate="%{x}<br>Wachstum: %{y:+.1f}%<br>Stellen: %{customdata:,}<extra></extra>",
    ))
    fig.update_layout(
        yaxis_title="Wachstum (%)", height=240,
        margin=dict(t=10,b=10,l=0,r=0), showlegend=False,
        plot_bgcolor="white", paper_bgcolor="white",
    )
    return fig

def match_offers(offers, user_text, params=None, top_n=40):
    try:
        vec, mat, ids = build_tfidf_index(str(DATA/"offers.csv"))
        results = tfidf_search(user_text, vec, mat, ids, offers, params=params, top_n=top_n)
    except Exception: return offers.head(0)
    if results.empty: return results
    if HF_TOKEN and len(results) >= 5:
        top20 = results.head(20)
        texts = tuple((str(r.title or "")+" "+str(r.description or ""))[:250]
                      for r in top20.itertuples(index=False))
        hf_sc = hf_rerank(user_text, texts)
        if hf_sc:
            top20 = top20.copy()
            top20["_score"] = top20["_score"]*0.5 + pd.Series(hf_sc, index=top20.index)*0.5
            results = pd.concat([top20.sort_values("_score",ascending=False),
                                  results.iloc[20:]]).reset_index(drop=True)
    return results

# ─── UI COMPONENTS ────────────────────────────────────────────────────────────

def comp_chips(comps_df, key_prefix):
    """Render competency chips colour-coded by growth."""
    if comps_df.empty: return
    cols = st.columns(3)
    for i, (_, row) in enumerate(comps_df.iterrows()):
        g = row.get("avg_growth", 0) or 0
        bg = "#e1f5ee" if g > 0.05 else "#faeeda" if g > -0.05 else "#fee2e2"
        tc = "#085041" if g > 0.05 else "#6b3800" if g > -0.05 else "#7f1d1d"
        gr = f"{g*100:+.1f}%" if pd.notna(g) else "n/a"
        with cols[i % 3]:
            st.markdown(
                f'<div style="background:{bg};color:{tc};border-radius:8px;'
                f'padding:7px 12px;margin:2px 0;font-size:13px">'
                f'<strong>{row["competency_name"][:40]}</strong>'
                f'<span style="float:right;font-size:11px">{gr}</span></div>',
                unsafe_allow_html=True)

def offer_mini_table(matched, n=8):
    """Compact offer table — no checkboxes, just show top results."""
    if matched.empty:
        st.caption("Keine vergleichbaren Angebote gefunden.")
        return
    hw = matched[matched["source"]=="hochundweit"].head(n//2)
    mn = matched[matched["source"]=="meinnow"].head(n//2)
    df = pd.concat([hw, mn]).reset_index(drop=True)

    def fmt_price(r):
        pb = str(r.get("price_band",""))
        if pb in PREIS_LABELS: return PREIS_LABELS[pb]
        if pd.notna(r.get("price")) and r["price"] > 0: return f"{r['price']:,.0f} EUR"
        return "k.A."

    rows = []
    for _, r in df.iterrows():
        src = "🔵" if r["source"]=="hochundweit" else "🟡"
        rows.append({
            "": src,
            "Titel": str(r["title"])[:50],
            "Preis": fmt_price(r),
            "Link":  str(r.get("url","")) if str(r.get("url","")).startswith("http") else "",
        })
    st.dataframe(
        pd.DataFrame(rows),
        column_config={"Link": st.column_config.LinkColumn("Link", display_text="→")},
        hide_index=True, use_container_width=True, height=36*len(rows)+40,
    )
    hw_priced = matched[(matched["source"]=="hochundweit") &
                        matched["price"].notna() & (matched["price"]>0)]
    if len(hw_priced) >= 3:
        p25,med,p75 = hw_priced["price"].quantile(.25), hw_priced["price"].median(), hw_priced["price"].quantile(.75)
        c1,c2,c3 = st.columns(3)
        c1.metric("25. Perz.", f"{p25:,.0f} EUR")
        c2.metric("Median",    f"{med:,.0f} EUR")
        c3.metric("75. Perz.", f"{p75:,.0f} EUR")

# ─── MODE A: IDEE ────────────────────────────────────────────────────────────

def mode_idee(offers, demand, berufe, comp_demand, comp_map, kgs):
    """Directed flow: topic search → demand → market → design."""

    # ── Step 1: Search ────────────────────────────────────────────────
    EXAMPLE_TOPICS = [
        "KI & Machine Learning", "Projektmanagement", "Nachhaltigkeit & ESG",
        "Datenschutz & DSGVO",   "Elektromobilität",  "Logistik & Supply Chain",
        "Führung & Leadership",  "Digitale Transformation",
    ]

    # If an example chip was clicked last run, pre-fill via _pending key
    # (can't write to a widget key while the widget is rendered)
    pending = st.session_state.pop("_idee_pending", None)
    default_val = pending if pending is not None else st.session_state.get("idee_query", "")

    query = st.text_input(
        "",
        value=default_val,
        placeholder="Thema eingeben — z.B. KI, Datenschutz, Elektromobilität …",
        label_visibility="collapsed",
        key="idee_query",
    )
    if not query.strip():
        st.markdown("<p style='color:#888;font-size:13px;margin:6px 0 4px 0'>Oder Beispiel auswählen:</p>",
                    unsafe_allow_html=True)
        chip_cols = st.columns(4)
        for i, topic in enumerate(EXAMPLE_TOPICS):
            with chip_cols[i % 4]:
                if st.button(topic, key=f"ex_{i}", use_container_width=True):
                    st.session_state["_idee_pending"] = topic
                    st.rerun()
        return

    # ── Step 2: Demand snapshot ───────────────────────────────────────
    with st.spinner("Analysiere Nachfrage …"):
        matched_comps, prof_rows = topic_search(query, comp_demand, comp_map, berufe)

    if not prof_rows and not matched_comps:
        st.info("Keine Treffer. Versuchen Sie: Digitalisierung, KI, Projektmanagement …")
        return

    berufe_matches = prof_rows
    kldb_ids = [b["kldb_id"] for b in prof_rows[:12]]

    # Competencies from topic_search or profession lookup
    comps_df = pd.DataFrame()
    if matched_comps and not comp_demand.empty:
        sub = comp_demand[comp_demand["competency_name"].isin(matched_comps)]
        local = sub[sub["region"].isin(["Dahme-Spreewald","Oder-Spree","Teltow-Fläming","Berlin"])]
        if not local.empty:
            comps_df = (local.groupby("competency_name", as_index=False)
                        .agg(avg_growth=("avg_growth","mean"), demand_score=("demand_score","mean"))
                        .sort_values("demand_score", ascending=False).head(12))
    if comps_df.empty:
        comps_df = get_comp_for_professions(kldb_ids, comp_map, comp_demand, top_n=12)
    comps = comps_df

    # Demand chart
    fig = demand_chart(demand, kldb_ids)

    # Layout: chart left, competencies right
    col_chart, col_comps = st.columns([3, 2])

    with col_chart:
        st.markdown("#### Nachfrage nach Region")
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
        # Top professions
        st.markdown("**Relevante Berufsgruppen**")
        for b in berufe_matches[:6]:
            sub = demand[demand["kldb_id"]==b["kldb_id"]]
            local = sub[sub["region"].isin(["Dahme-Spreewald","Oder-Spree","Teltow-Fläming"])]
            jobs = int(local["total_jobs"].sum()) if not local.empty else 0
            growth = local["percentage_diff_previous_year"].mean() if not local.empty else 0
            growth_str = f"{growth*100:+.1f}%" if jobs > 0 else "—"
            color = "#0f6e56" if growth > 0.05 else "#854f0b" if growth > -0.05 else "#9b1c1c"
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:5px 0;border-bottom:1px solid #f0f0f0;font-size:13px">'
                f'<span>{b["beruf_name"][:45]}</span>'
                f'<span style="color:{color};font-weight:600">{growth_str}</span>'
                f'</div>', unsafe_allow_html=True)

    with col_comps:
        st.markdown("#### Gefragte Kompetenzen")
        if not comps_df.empty:
            comp_chips(comps_df, "idee")
            st.caption("🟢 wachsend  🟡 stabil  🔴 rückläufig (TH Wildau Region + Berlin)")
        else:
            st.caption("Keine Kompetenz-Daten verfügbar.")

    st.markdown("---")

    # ── Step 3: Marktlage (collapsible) ──────────────────────────────
    with st.expander("Vergleichsangebote ansehen"):
        with st.spinner("Suche ähnliche Kurse …"):
            matched = match_offers(offers, query, top_n=30)
        n_comp = len(matched[matched["source"]=="hochundweit"])
        score  = 10 if n_comp==0 else 9 if n_comp<=3 else 7 if n_comp<=8 else 5 if n_comp<=20 else 3
        label  = {10:"Kaum Angebot — gute Marktchance",9:"Wenig Angebot",
                  7:"Moderates Angebot",5:"Angebot vorhanden",3:"Starkes Angebot"}.get(score,"")
        c = "#0f6e56" if score>=8 else "#854f0b" if score>=5 else "#9b1c1c"
        bg = "#e1f5ee" if score>=8 else "#faeeda" if score>=5 else "#fee2e2"
        st.markdown(
            f'<div style="background:{bg};border-radius:8px;padding:10px 16px;'
            f'margin-bottom:12px;display:inline-flex;gap:16px;align-items:center">'
            f'<span style="font-size:1.5rem;font-weight:700;color:{c}">{score}/10</span>'
            f'<span style="color:{c}">{label}</span></div>', unsafe_allow_html=True)
        offer_mini_table(matched)

    # ── Step 4: Kurs entwickeln ───────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Kurs entwickeln")
    st.markdown("Genug gesehen? Hier können Sie Ihren Kurs formal beschreiben und kalkulieren.")

    with st.expander("Kursdetails eingeben"):
        c1, c2 = st.columns(2)
        with c1:
            title = st.text_input("Kurstitel", value=query[:80] if len(query)<80 else "")
            degree = st.selectbox("Abschluss", [
                "Zertifikat / Hochschulzertifikat","Microcredential (digitales Badge / Teilleistung)",
                "Teilnahmebescheinigung","Bachelor","Master","Sonstiges"])
            fmt = st.selectbox("Format", [
                "Hybrid / Blended","Online / Digital","Präsenz","Berufsbegleitend","Noch offen"])
        with c2:
            ects = st.number_input("ECTS", min_value=0, max_value=60, value=0)
            months = st.number_input("Dauer (Monate)", min_value=0, max_value=36, value=0)
            target_tn = st.number_input("Ziel-Teilnehmerzahl", min_value=1, max_value=200, value=15)

        st.markdown("**Kostenplanung** (optional)")
        k1, k2 = st.columns(2)
        with k1:
            dev_h    = st.number_input("Entwicklungsstunden", min_value=0, value=0)
            dev_rate = st.number_input("Entwicklungskosten/h (EUR)", min_value=0, value=80)
        with k2:
            impl_h    = st.number_input("Durchführungsstunden", min_value=0, value=0)
            impl_rate = st.number_input("Durchführungskosten/h (EUR)", min_value=0, value=60)
        sachkosten = st.number_input("Sachkosten pro TN (EUR)", min_value=0, value=0)
        overhead   = st.slider("Overhead (%)", 0, 50, 20) / 100

        # Price calculation
        if dev_h > 0:
            fix_net  = dev_h*dev_rate + impl_h*impl_rate
            be_preis = ((fix_net/target_tn) + sachkosten) * (1+overhead)
            st.success(f"Break-even-Preis: **{be_preis:,.0f} EUR/TN** bei {target_tn} Teilnehmenden")

        go_btn = st.button("Zur Angebotsbeschreibung →", type="primary")
        if go_btn:
            st.session_state.radar_params = {
                "title": title, "description": query,
                "degree": degree, "format": fmt,
                "ects": ects, "months": months,
                "keywords": "",
                "user_text": query,
                "selected_cats": [],
                "kg": "",
                "target_tn": target_tn,
                "dev_h": dev_h, "dev_rate": dev_rate,
                "impl_h": impl_h, "impl_rate": impl_rate,
                "sachkosten": sachkosten, "overhead": overhead,
            }
            st.session_state.confirmed_berufe = set(b["beruf_name"] for b in berufe_matches[:5])
            st.switch_page("pages/1_Angebotsbeschreibung.py")


# ─── MODE B: INSPIRATION ─────────────────────────────────────────────────────

def mode_inspiration(offers, demand, berufe, comp_demand, comp_map, comp_summary, kgs):
    """Exploratory flow: browse top competencies → drill into demand & offers."""

    if comp_summary.empty:
        st.info("Kompetenz-Daten nicht verfügbar."); return

    # ── Filters ───────────────────────────────────────────────────────
    col_r, col_g, col_sort = st.columns([2, 2, 2])
    with col_r:
        region_filter = st.selectbox("Region", list(REGIONS_DISPLAY.keys()), index=0, key="insp_region")
    with col_g:
        growth_filter = st.selectbox("Wachstum", ["Alle","Nur wachsend (>5%)","Stabil","Rückläufig"], key="insp_growth")
    with col_sort:
        sort_by = st.selectbox("Sortierung", ["Nachfrage (lokal)","Wachstum","Alphabetisch"], key="insp_sort")

    # Build regional demand column
    region_map = {
        "TH Wildau Region": ["Dahme-Spreewald","Oder-Spree","Teltow-Fläming"],
        "Berlin": ["Berlin"],
        "Brandenburg": ["Brandenburg"],
        "Deutschland": ["Deutschland"],
    }
    regs = region_map.get(region_filter, ["Dahme-Spreewald","Oder-Spree","Teltow-Fläming"])

    # Compute a fresh demand score for the chosen region
    if not comp_demand.empty:
        reg_agg = (comp_demand[comp_demand["region"].isin(regs)]
                   .groupby("competency_name", as_index=False)
                   .agg(demand_score=("demand_score","mean"),
                        avg_growth=("avg_growth","mean"),
                        total_jobs=("total_jobs","sum")))
    else:
        reg_agg = pd.DataFrame(columns=["competency_name","demand_score","avg_growth","total_jobs"])

    # Merge with summary for type info
    display = reg_agg.copy()

    # Growth filter
    if growth_filter == "Nur wachsend (>5%)":
        display = display[display["avg_growth"] > 0.05]
    elif growth_filter == "Stabil":
        display = display[(display["avg_growth"] >= -0.05) & (display["avg_growth"] <= 0.05)]
    elif growth_filter == "Rückläufig":
        display = display[display["avg_growth"] < -0.05]

    # Sort
    if sort_by == "Wachstum":
        display = display.sort_values("avg_growth", ascending=False)
    elif sort_by == "Alphabetisch":
        display = display.sort_values("competency_name")
    else:
        display = display.sort_values("demand_score", ascending=False)

    display = display.head(60).reset_index(drop=True)

    if display.empty:
        st.info("Keine Kompetenzen für diese Filterauswahl."); return

    st.markdown(f"**{len(display)} Kompetenzen** — klicken Sie auf eine, um Details zu sehen.")

    # Normalise for bar width
    max_score = display["demand_score"].max() or 1

    # ── Competency list ───────────────────────────────────────────────
    if "insp_selected" not in st.session_state:
        st.session_state.insp_selected = None

    for i, row in display.iterrows():
        g     = row.get("avg_growth", 0) or 0
        score = row.get("demand_score", 0) or 0
        bar_w = int(score / max_score * 100)
        bar_color = "grow" if g > 0.05 else "fall" if g < -0.05 else ""
        gr_str = f"{g*100:+.1f}%" if pd.notna(g) else "n/a"
        gr_color = "#0f6e56" if g > 0.05 else "#c0392b" if g < -0.05 else "#854f0b"
        is_sel = st.session_state.insp_selected == row["competency_name"]

        bg = "#f0f6ff" if is_sel else "#fff"
        border = "#185fa5" if is_sel else "#e8e8e8"

        if st.button(
                f"{row['competency_name'][:50]}  ·  {gr_str}",
                key=f"insp_sel_{i}", use_container_width=True,
                type="primary" if is_sel else "secondary"):
            st.session_state.insp_selected = row["competency_name"]
            st.rerun()

    # ── Detail panel ─────────────────────────────────────────────────
    if st.session_state.insp_selected:
        sel = st.session_state.insp_selected
        st.markdown("---")
        st.markdown(f"### {sel}")

        # Which professions need this competency?
        if not comp_map.empty:
            prof_for_comp = comp_map[comp_map["competency_name"]==sel]
            prof_kldb = prof_for_comp["kldb_id"].astype(str).unique().tolist()
            prof_names = prof_for_comp["profession_name"].unique().tolist()

            col_d, col_c = st.columns([3, 2])
            with col_d:
                st.markdown(f"**Nachfrage für diese Kompetenz** ({region_filter})")
                kldb_ints = []
                for k in prof_kldb:
                    try: kldb_ints.append(int(k))
                    except: pass
                fig = demand_chart(demand, kldb_ints)
                if fig:
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
                st.markdown(f"**Berufe die diese Kompetenz benötigen** ({len(prof_names)})")
                for p in prof_names[:8]:
                    st.markdown(f"<span style='font-size:13px'>• {p}</span>", unsafe_allow_html=True)
                if len(prof_names) > 8:
                    st.caption(f"… und {len(prof_names)-8} weitere")

            with col_c:
                st.markdown("**Verwandte Kompetenzen**")
                related = comp_map[comp_map["kldb_id"].astype(str).isin(prof_kldb)]
                related = (related[related["competency_name"] != sel]
                           .groupby("competency_name", as_index=False)
                           .agg(n=("kldb_id","nunique"))
                           .sort_values("n", ascending=False).head(10))
                for _, r in related.iterrows():
                    st.markdown(
                        f'<div style="background:#f5f5f5;border-radius:6px;'
                        f'padding:4px 10px;margin:2px 0;font-size:13px">{r["competency_name"][:40]}</div>',
                        unsafe_allow_html=True)

        # Existing offers on this topic
        st.markdown("**Bestehende Kursangebote**")
        with st.spinner("Suche Angebote …"):
            matched = match_offers(offers, sel, top_n=20)
        offer_mini_table(matched, n=6)

        # CTA: develop this into a course
        st.markdown("")
        if st.button(f"💡 Kurs zu »{sel[:35]}« entwickeln", type="primary", use_container_width=True):
            st.session_state.idee_query = sel
            st.session_state.mode = "idee"
            st.rerun()


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    # Load data
    offers      = load_offers()
    demand      = load_demand()
    berufe      = load_berufe()
    comp_demand = load_comp_demand()
    comp_map    = load_comp_map()
    comp_summary = load_comp_summary()
    kgs         = load_kgs()

    # ── Header ────────────────────────────────────────────────────────
    st.markdown(
        '<h1 style="font-size:1.6rem;font-weight:700;margin-bottom:0">Weiterbildungs-Radar</h1>'
        '<p style="color:#666;margin-top:2px;font-size:14px">TH Wildau · Marktanalyse für neue Weiterbildungsangebote</p>',
        unsafe_allow_html=True)

    # ── Mode selector ─────────────────────────────────────────────────
    if "mode" not in st.session_state:
        st.session_state.mode = None

    col1, col2, col3 = st.columns([5, 5, 2])

    with col1:
        if st.button("💡  Ich habe eine Idee\n\nIch weiß ungefähr, was ich anbieten möchte",
                     use_container_width=True, key="btn_idee",
                     type="primary" if st.session_state.mode=="idee" else "secondary"):
            st.session_state.mode = "idee"
            st.rerun()

    with col2:
        if st.button("🔍  Ich suche Inspiration\n\nZeig mir, was der Markt gerade braucht",
                     use_container_width=True, key="btn_insp",
                     type="primary" if st.session_state.mode=="inspiration" else "secondary"):
            st.session_state.mode = "inspiration"
            st.rerun()

    if st.session_state.mode is None:
        st.markdown(
            '<p style="color:#aaa;font-size:13px;margin-top:16px;text-align:center">'
            'Wählen Sie oben, womit Sie beginnen möchten.</p>',
            unsafe_allow_html=True)
        return

    st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── Route to mode ─────────────────────────────────────────────────
    if st.session_state.mode == "idee":
        mode_idee(offers, demand, berufe, comp_demand, comp_map, kgs)
    else:
        mode_inspiration(offers, demand, berufe, comp_demand, comp_map, comp_summary, kgs)

    # ── Feedback (always at bottom) ───────────────────────────────────
    st.markdown("---")
    with st.expander("Feedback geben"):
        FORM_URL = ("https://docs.google.com/forms/d/1m-3oij-Lcb59ilQMUcHaRDS56fNFwi8J194jRNgxq64"
                    "/viewform?embedded=true")
        st.components.v1.iframe(FORM_URL, height=500, scrolling=True)

if __name__ == "__main__":
    main()
