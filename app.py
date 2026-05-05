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


# ─── GEOCODING & FORMAT CLASSIFICATION ──────────────────────────────

UNI_CITY = {
    "Akkon Hochschule":"Berlin","Constructor University":"Bremen",
    "Deutsche Hochschule für Angewandte Wissenschaften":"Hamburg",
    "Duale Hochschule Baden-Württemberg":"Stuttgart",
    "Duale Hochschule Schleswig-Holstein":"Kiel","EBS Universität":"Wiesbaden",
    "EHIP – Europäische Hochschule für Innovation und Perspektive":"Frankfurt",
    "ESMT European School of Management and Technology":"Berlin",
    "Evangelische Hochschule Ludwigsburg":"Ludwigsburg",
    "FOM Hochschule für Oekonomie & Management":"Essen",
    "Fachhochschule Südwestfalen":"Iserlohn","Fachhochschule der Diakonie":"Bielefeld",
    "Fachhochschule des Mittelstands":"Bielefeld","Filmuniversität Babelsberg":"Potsdam",
    "Fliedner Fachhochschule":"Düsseldorf",
    "HAWK Hochschule für angewandte Wissenschaft und Kunst":"Hildesheim",
    "HSD Hochschule Döpfer":"Köln",
    "Helmut-Schmidt-Universität/ Universität der Bundeswehr":"Hamburg",
    "Hessische Hochschule für öffentliches Management und Sicherheit":"Kassel",
    "Hochschule Albstadt-Sigmaringen":"Albstadt","Hochschule Anhalt":"Köthen",
    "Hochschule Ansbach":"Ansbach","Hochschule Biberach":"Biberach an der Riß",
    "Hochschule Bremerhaven":"Bremerhaven","Hochschule Coburg":"Coburg",
    "Hochschule Emden/ Leer":"Emden","Hochschule Fresenius":"Düsseldorf",
    "Hochschule Fulda":"Fulda","Hochschule Geisenheim":"Geisenheim",
    "Hochschule Harz":"Wernigerode","Hochschule Hof":"Hof",
    "Hochschule Kaiserslautern":"Kaiserslautern","Hochschule Kempten":"Kempten",
    "Hochschule Koblenz":"Koblenz","Hochschule Meißen (FH) und Fortbildungszentrum":"Meißen",
    "Hochschule Merseburg":"Merseburg","Hochschule Niederrhein":"Krefeld",
    "Hochschule Nordhausen":"Nordhausen","Hochschule Ruhr West":"Mülheim an der Ruhr",
    "Hochschule Schmalkalden":"Schmalkalden",
    "Hochschule Weihenstephan-Triesdorf":"Weihenstephan",
    "Hochschule Weserbergland":"Hameln","Hochschule Worms":"Worms",
    "Hochschule der Bayerischen Wirtschaft für angewandte Wissenschaften":"München",
    "Hochschule für Katholische Theologie":"München","Hochschule für Philosophie":"München",
    "Hochschule für Technik und Wirtschaft des Saarlandes":"Saarbrücken",
    "Hochschule für Wirtschaft und Gesellschaft Ludwigshafen":"Ludwigshafen",
    "Hochschule für Wirtschaft und Umwelt Nürtingen-Geislingen":"Nürtingen",
    "Hochschule für nachhaltige Entwicklung":"Eberswalde",
    "Hochschule für öffentliche Verwaltung und Finanzen Ludwigsburg":"Ludwigsburg",
    "IB Hochschule für Gesundheit und Soziales":"Berlin",
    "INU - Innovative University of Applied Sciences":"Erfurt",
    "IST-Hochschule für Management":"Düsseldorf",
    "International Psychoanalytic University":"Berlin",
    "International School of Management":"Dortmund","Jade Hochschule":"Wilhelmshaven",
    "Katholische Hochschule Nordrhein-Westfalen":"Köln","Kühne Logistics University":"Hamburg",
    "Leuphana Universität":"Lüneburg","MU Media University of Applied Sciences":"Stuttgart",
    "Mediadesign Hochschule":"München",
    "Ostbayerische Technische Hochschule Amberg-Weiden":"Amberg",
    "Ostfalia Hochschule":"Wolfenbüttel","Pädagogische Hochschule Ludwigsburg":"Ludwigsburg",
    "Pädagogische Hochschule Weingarten":"Weingarten",
    "RPTU Kaiserslautern-Landau":"Kaiserslautern",
    "SRH Fernhochschule - The Mobile University":"Riedlingen",
    "Technische Hochschule Aschaffenburg":"Aschaffenburg",
    "Technische Hochschule Bingen":"Bingen am Rhein",
    "Technische Hochschule Deggendorf":"Deggendorf",
    "Technische Hochschule Rosenheim":"Rosenheim",
    "Tomorrow University of Applied Sciences":"Berlin","University of Labour":"Frankfurt",
    "Universität Hohenheim":"Stuttgart","Universität Koblenz":"Koblenz",
    "Universität Marburg":"Marburg","Universität Tübingen":"Tübingen",
    "Universität Witten/Herdecke":"Witten","Universität des Saarlandes":"Saarbrücken",
    "Vinzenz Pallotti University":"Vallendar","WHU Vallendar":"Vallendar",
    "Westfälische Hochschule":"Gelsenkirchen","Westsächsische Hochschule":"Zwickau",
    "Wilhelm Büchner Hochschule":"Darmstadt",
    "XU Exponential University of Applied Sciences":"Potsdam",
    "Zeppelin Universität":"Friedrichshafen","accadis Hochschule":"Bad Homburg",
    "Hochschule für Kirchenmusik der Evangelischen Kirche von Westfalen":"Herford",
    "TH Wildau":"Wildau","Technische Hochschule Wildau":"Wildau",
}

CITY_COORDS = {
    "Berlin":(52.520,13.405),"Hamburg":(53.551,9.994),"München":(48.137,11.576),
    "Köln":(50.938,6.960),"Frankfurt":(50.110,8.682),"Stuttgart":(48.775,9.182),
    "Düsseldorf":(51.225,6.783),"Leipzig":(51.340,12.375),"Dortmund":(51.514,7.468),
    "Essen":(51.457,7.012),"Bremen":(53.079,8.802),"Dresden":(51.050,13.738),
    "Hannover":(52.374,9.738),"Nürnberg":(49.452,11.077),"Bielefeld":(52.021,8.532),
    "Bonn":(50.733,7.101),"Münster":(51.961,7.628),"Karlsruhe":(49.014,8.404),
    "Mannheim":(49.488,8.468),"Augsburg":(48.370,10.898),"Wiesbaden":(50.082,8.244),
    "Bochum":(51.481,7.226),"Wuppertal":(51.257,7.151),"Kassel":(51.312,9.481),
    "Mainz":(49.998,8.274),"Darmstadt":(49.872,8.652),"Trier":(49.749,6.637),
    "Aachen":(50.776,6.084),"Freiburg":(47.995,7.842),"Regensburg":(49.018,12.098),
    "Heilbronn":(49.140,9.220),"Ulm":(48.399,9.990),"Würzburg":(49.795,9.929),
    "Siegen":(50.876,8.024),"Konstanz":(47.659,9.175),"Heidelberg":(49.399,8.673),
    "Bamberg":(49.900,10.901),"Bayreuth":(49.946,11.578),"Erlangen":(49.598,11.004),
    "Passau":(48.575,13.455),"Offenburg":(48.473,7.944),"Pforzheim":(48.891,8.704),
    "Reutlingen":(48.493,9.212),"Jena":(50.928,11.586),"Weimar":(50.979,11.323),
    "Ilmenau":(50.683,10.916),"Zwickau":(50.720,12.496),"Cottbus":(51.756,14.333),
    "Eberswalde":(52.833,13.822),"Brandenburg":(52.408,12.534),"Potsdam":(52.390,13.064),
    "Greifswald":(54.096,13.387),"Wismar":(53.892,11.456),"Oldenburg":(53.143,8.214),
    "Osnabrück":(52.279,8.047),"Göttingen":(51.534,9.933),"Hildesheim":(52.150,9.957),
    "Lüneburg":(53.248,10.408),"Wolfenbüttel":(52.163,10.534),"Iserlohn":(51.378,7.704),
    "Hagen":(51.361,7.474),"Paderborn":(51.719,8.754),"Aalen":(48.836,10.094),
    "Esslingen":(48.741,9.305),"Ludwigsburg":(48.896,9.192),"Kiel":(54.323,10.133),
    "Erfurt":(50.978,11.030),"Magdeburg":(52.131,11.640),"Halle":(51.482,11.970),
    "Chemnitz":(50.832,12.924),"Rostock":(54.092,12.100),"Saarbrücken":(49.234,6.997),
    "Lübeck":(53.869,10.686),"Marburg":(50.803,8.771),"Tübingen":(48.521,9.057),
    "Flensburg":(54.793,9.436),"Wernigerode":(51.833,10.783),"Hof":(50.316,11.916),
    "Kaiserslautern":(49.444,7.769),"Kempten":(47.726,10.316),"Koblenz":(50.360,7.598),
    "Meißen":(51.163,13.473),"Merseburg":(51.353,11.990),"Krefeld":(51.337,6.557),
    "Nordhausen":(51.505,10.790),"Schmalkalden":(50.724,10.453),"Hameln":(52.104,9.362),
    "Worms":(49.632,8.358),"Nürtingen":(48.628,9.336),"Ludwigshafen":(49.479,8.445),
    "Emden":(53.367,7.206),"Fulda":(50.554,9.676),"Wilhelmshaven":(53.530,8.101),
    "Albstadt":(48.214,9.023),"Köthen":(51.751,11.971),"Ansbach":(49.301,10.571),
    "Bremerhaven":(53.539,8.579),"Coburg":(50.259,10.965),"Amberg":(49.444,11.861),
    "Aschaffenburg":(49.977,9.149),"Deggendorf":(48.840,12.960),"Rosenheim":(47.857,12.125),
    "Witten":(51.436,7.353),"Gelsenkirchen":(51.517,7.106),"Bad Homburg":(50.228,8.618),
    "Friedrichshafen":(47.651,9.479),"Vallendar":(50.407,7.601),"Weingarten":(47.803,9.639),
    "Mülheim an der Ruhr":(51.426,6.884),"Herford":(52.113,8.676),"Wildau":(52.314,13.638),
    "Weihenstephan":(48.398,11.728),"Riedlingen":(48.154,9.477),"Geisenheim":(49.984,7.965),
    "Biberach an der Riß":(48.097,9.793),"Bingen am Rhein":(49.966,7.896),
    "Landshut":(48.537,12.152),"Furtwangen":(48.047,8.208),"Ravensburg":(47.782,9.612),
}

GERMAN_CITIES = list(CITY_COORDS.keys())

def get_uni_city(uni_name):
    if not isinstance(uni_name, str): return None
    # Direct lookup
    if uni_name in UNI_CITY: return UNI_CITY[uni_name]
    # Extract city from name
    for city in GERMAN_CITIES:
        if city.lower() in uni_name.lower():
            return city
    return None

def get_delivery_mode(fmt, spatial_flex=0):
    """
    Classify into 4 delivery modes:
      fully_online     - 100% digital, no fixed location
      hybrid_flexible  - hybrid with no fixed location (e.g. Blended/Combined Learning)
      hybrid_location  - hybrid tied to a specific campus
      in_person        - primarily face-to-face at a fixed location
    """
    fmt_lower = str(fmt).lower()
    flex = float(spatial_flex) if spatial_flex else 0

    if flex == 100 or any(x in fmt_lower for x in ["fernstudium","fernunterricht","digitaler kurs"]):
        return "fully_online"
    if any(x in fmt_lower for x in ["combined learning","blended learning","hybrid learning",
                                      "virtuelles klassenzimmer","online-seminar"]):
        return "hybrid_flexible"
    if any(x in fmt_lower for x in ["berufsbegleitend","blockkurs","wochenendkurs",
                                      "teilzeitstudium","vollzeitstudium","studium"]):
        return "hybrid_location"
    if any(x in fmt_lower for x in ["präsenz","seminar","praxistraining"]):
        return "in_person"
    return "hybrid_location"  # default for academic courses

DELIVERY_LABELS = {
    "fully_online":    "Vollständig online",
    "hybrid_flexible": "Hybrid (ortsunabhängig)",
    "hybrid_location": "Hybrid (standortgebunden)",
    "in_person":       "Präsenz",
}
DELIVERY_COLORS = {
    "fully_online":    "#e8eaf6",
    "hybrid_flexible": "#e8f5e9",
    "hybrid_location": "#fff8e1",
    "in_person":       "#fce4ec",
}

DATA = Path(__file__).parent / "data"


# ─── SEARCH INFRASTRUCTURE ───────────────────────────────────────────────────
import os as _os
HF_TOKEN = _os.getenv("HF_TOKEN", "")
HF_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
HF_API   = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{HF_MODEL}"

STOP_EDUCATIONAL = [
    "lernen","lernst","lehren","lehre","studieren","studium","kurs","kurse",
    "modul","module","thema","themen","bereich","bereichen","grundlagen",
    "einführung","vertiefung","vertiefende","überblick","übersicht",
    "werden","durch","sowie","auch","können","haben","sein","eine","einen",
    "einer","über","nach","beim","liegt","wird","sind","mehr","noch","dazu",
    "weitere","weiteren","dabei","daher","anhand","unter","ohne",
    "diesem","dieser","dieses","ihrer","ihren","ihrem",
    "ziel","ziele","inhalte","inhalt","methoden","methode",
    "praxis","theorie","kompetenz","kompetenzen","kenntnisse","fähigkeiten",
]

@st.cache_resource(show_spinner=False)
def build_tfidf_index(path: str):
    from sklearn.feature_extraction.text import TfidfVectorizer
    import pandas as _pd
    df = _pd.read_csv(path)
    df["_text"] = (df["title"].fillna("") + " " +
                   df["description"].fillna("").str[:400])
    ids = df["id"].astype(str).tolist()
    vec = TfidfVectorizer(
        max_features=25000, min_df=2, max_df=0.65,
        sublinear_tf=True, ngram_range=(1, 2),
        stop_words=STOP_EDUCATIONAL,
    )
    mat = vec.fit_transform(df["_text"])
    return vec, mat, ids


_COMP_SYNONYMS = {
    "gebäudetechnik":"Gebäudesystemtechnik Versorgungstechnik Haustechnik",
    "wärmewende":"Wärmepumpenanlagen Heizungstechnik Energieeffizienz",
    "automobilindustrie":"Fahrzeugtechnik Fahrzeugelektronik Infotainment",
    "automotive":"Fahrzeugtechnik Fahrzeugelektronik",
    "embedded":"Embedded Systems SPS-Programmierung Automatisierungstechnik",
    "sps":"SPS-Programmierung SPS-Technik",
    "cloud":"Cloud Computing Cloud-Sicherheit",
    "devops":"DevOps-Tools DevOps Agile Softwareentwicklung",
    "cybersecurity":"Cybersecurity IT-Sicherheit Datensicherheit",
    "nis2":"Cybersecurity IT-Sicherheit",
    "ki":"KI-Systeme KI-Tools Maschinelles Lernen",
    "iot":"IoT-Plattformen Internet of Things Embedded Systems",
    "nachhaltigkeit":"Nachhaltigkeitsmanagement Umweltmanagement",
    "lean":"Lean Management Prozessoptimierung",
    "dsgvo":"Datenschutz Compliance",
    "digitalisierung":"Digitale Transformation Prozessautomatisierung",
}
_COMP_STOP = {"in","der","die","das","und","für","mit","von","zu","dem","den","des",
              "ein","eine","einer","eines","einem","an","am","im","ist","sind",
              "auf","bei","nach","aus","als","oder","auch","sich","über","durch"}
_SHORT_TECH = {"ki","it","iot","sap","crm","bi","ai","ml","api","sps","nis2","dsgvo","bim"}

def _expand_comp_query(text):
    import re as _re
    extras = [_COMP_SYNONYMS[w] for w in _re.findall(r'\b\w+\b', text.lower())
              if w in _COMP_SYNONYMS]
    return (text + " " + " ".join(extras)) if extras else text

def _comp_qtokens(text):
    import re as _re
    toks = set(_re.findall(r'\b\w+\b', text.lower()))
    return {t for t in toks if (len(t)>=4 or t in _SHORT_TECH) and t not in _COMP_STOP}

def _token_overlap(qtoks, comp_name):
    import re as _re
    ctoks  = set(_re.findall(r'\b\w+\b', comp_name.lower()))
    cstems = {t[:5] for t in ctoks  if len(t)>=4}
    qstems = {t[:5] for t in qtoks  if len(t)>=4}
    return (len(qtoks & ctoks)*2 + len(qstems & cstems)) / max(len(qtoks)*2, 1)

@st.cache_resource(show_spinner=False)
def build_comp_index(comp_demand_path: str):
    from sklearn.feature_extraction.text import TfidfVectorizer
    names = pd.read_csv(comp_demand_path)["competency_name"].dropna().unique()
    vec   = TfidfVectorizer(min_df=1, ngram_range=(1,2), sublinear_tf=True,
                            stop_words=list(_COMP_STOP))
    mat   = vec.fit_transform(names)
    return vec, mat, names

def suggest_comps_for_query(query, comp_demand, top_n=15):
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as _np
    if not query.strip(): return pd.DataFrame()
    expanded = _expand_comp_query(query)
    qtoks    = _comp_qtokens(expanded)
    if not qtoks: return pd.DataFrame()
    vec, mat, names = build_comp_index(str(DATA/"competency_demand.csv"))
    sims = cosine_similarity(vec.transform([expanded]), mat)[0]
    rows = []
    for i in _np.argsort(sims)[::-1][:top_n*8]:
        if sims[i] < 0.06: break
        name = names[i]
        if _token_overlap(qtoks, name) < 0.12: continue
        local = comp_demand[
            comp_demand["competency_name"].eq(name) &
            comp_demand["region"].isin(["Dahme-Spreewald","Oder-Spree","Teltow-Fläming","Berlin"])
        ]
        rows.append({"competency_name":name, "sim":round(float(sims[i]),3),
                     "avg_growth": local["avg_growth"].mean() if not local.empty else None,
                     "weighted_jobs": local["weighted_jobs"].sum() if not local.empty else 0})
        if len(rows) >= top_n: break
    return pd.DataFrame(rows)

def comps_to_professions(selected_names: list, comp_map: pd.DataFrame,
                          top_n: int = 15) -> pd.DataFrame:
    if not selected_names or comp_map.empty: return pd.DataFrame()
    rel = comp_map[comp_map["competency_name"].isin(selected_names)]
    if rel.empty: return pd.DataFrame()
    return (rel.groupby(["profession_name","kldb_id"], as_index=False)
               .agg(n_comps=("competency_name","nunique"), weight=("weight","sum"))
               .sort_values("n_comps", ascending=False).head(top_n))

def tfidf_search(user_text, vectorizer, matrix, ids, offers_df, params=None, top_n=60):
    from sklearn.metrics.pairwise import cosine_similarity as _cos
    import numpy as _np
    if not user_text.strip():
        return offers_df.head(0)
    q_vec = vectorizer.transform([user_text])
    sims  = _cos(q_vec, matrix)[0]
    user_delivery = get_delivery_mode(params.get("format","") if params else "")
    user_degree   = str(params.get("degree","")).lower() if params else ""
    selected_cats = params.get("selected_cats",[]) if params else []
    kg            = params.get("kg","") if params else ""
    boosts = _np.zeros(len(sims))
    for i, r in enumerate(offers_df.itertuples(index=False)):
        b = 0.0
        if r.source == "hochundweit":  b += 0.04
        geo = str(getattr(r,"geo_tier","") or "")
        if geo == "wildau":            b += 0.08
        elif geo == "berlin_bb":       b += 0.04
        mode = str(getattr(r,"delivery_mode","") or "")
        if mode == user_delivery:      b += 0.05
        elif user_delivery in ("hybrid_location","in_person") and mode in ("hybrid_location","in_person"):
            b += 0.02
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

@st.cache_data(show_spinner=False, ttl=1800)
def hf_rerank(query: str, candidate_texts: tuple) -> list:
    if not HF_TOKEN or not candidate_texts:
        return []
    try:
        import requests as _req
        all_texts = [query] + list(candidate_texts)
        resp = _req.post(HF_API,
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={"inputs": all_texts, "options": {"wait_for_model": True}},
            timeout=15)
        if resp.status_code != 200:
            return []
        vecs = resp.json()
        def mp(v): return [sum(c)/len(c) for c in zip(*v)] if isinstance(v[0],list) else v
        qv = mp(vecs[0])
        out = []
        for v in vecs[1:]:
            cv = mp(v)
            dot = sum(a*b for a,b in zip(qv,cv))
            nq  = sum(x*x for x in qv)**0.5
            nc  = sum(x*x for x in cv)**0.5
            out.append(dot/(nq*nc) if nq and nc else 0.0)
        return out
    except Exception:
        return []

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
    "PGT_nachhaltige_Wertschoepfung":       "Nachhaltige Wert(e)schöpfung",
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
    # delivery_mode, lat, lon, city_name are pre-computed in offers.csv
    if "delivery_mode" not in df.columns:
        df["delivery_mode"] = "hybrid_location"
    if "lat" not in df.columns:
        df["lat"] = None
    if "lon" not in df.columns:
        df["lon"] = None
    if "city_name" not in df.columns:
        df["city_name"] = df["city"]
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
def load_competency_demand():
    path = DATA / "competency_demand.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["kldb_id"] = df.get("kldb_id", pd.Series(dtype=str))
    return df

@st.cache_data
def load_competency_summary():
    path = DATA / "competency_summary.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)

@st.cache_data
def load_profession_competency_map():
    path = DATA / "profession_competency_map.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)

@st.cache_data
def load_kgs():
    with open(DATA/"knowledge_groups.json", encoding="utf-8") as f:
        return json.load(f)

# ─── HELPERS ─────────────────────────────────────────────────────────────

def match_offers(offers, user_text, selected_cats, kg, n_per_source=30, params=None):
    """TF-IDF primary search + optional HF re-ranking of top 20."""
    try:
        vec, mat, ids = build_tfidf_index(str(DATA / "offers.csv"))
        results = tfidf_search(user_text, vec, mat, ids, offers, params=params)
    except Exception as e:
        st.warning(f"Suchindex-Fehler: {e}")
        return offers.head(0)
    if results.empty:
        return results
    if HF_TOKEN and len(results) >= 5:
        top20 = results.head(20)
        texts = tuple(
            (str(r.title or "")+" "+str(r.description or ""))[:250]
            for r in top20.itertuples(index=False)
        )
        hf_sc = hf_rerank(user_text, texts)
        if hf_sc:
            top20 = top20.copy()
            top20["_score"] = top20["_score"]*0.5 + pd.Series(hf_sc, index=top20.index)*0.5
            rest  = results.iloc[20:].copy()
            results = pd.concat([
                top20.sort_values("_score", ascending=False), rest
            ]).reset_index(drop=True)
    return results


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
    section_header("#dceefb", "1. Eckdaten zum Angebot")
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
    section_header("#ede0f5", "2. Kosteninputs für Preisgestaltung")
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


def show_offer_map(matched_df):
    """Show HW offers as dots on a map of Germany."""
    try:
        import pydeck as pdk
        hw_map = matched_df[
            (matched_df["source"] == "hochundweit") &
            matched_df["lat"].notna() & matched_df["lon"].notna()
        ].copy()
        if hw_map.empty:
            st.caption("Keine Kartenposition für die gefundenen Hochschulangebote verfügbar.")
            return
        # Aggregate: count courses per city
        city_agg = hw_map.groupby(["city_name","lat","lon"], as_index=False).agg(
            anzahl=("title","count"),
            titel_sample=("title", lambda x: "<br>".join(x.head(3).tolist()))
        )
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=city_agg,
            get_position=["lon","lat"],
            get_radius="anzahl * 15000",
            get_fill_color=[24, 95, 165, 180],
            pickable=True,
        )
        view = pdk.ViewState(latitude=51.2, longitude=10.4, zoom=5, pitch=0)
        tooltip = {"html": "<b>{city_name}</b><br>{anzahl} Kurs(e)<br>{titel_sample}",
                   "style": {"backgroundColor":"#185fa5","color":"white","fontSize":"12px"}}
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view,
                                  tooltip=tooltip, map_style="light"))
        st.caption(f"{len(hw_map)} Hochschulangebote kartiert ({city_agg['anzahl'].sum()} Kurse an {len(city_agg)} Standorten). Kreisgröße = Anzahl Kurse.")
    except ImportError:
        # Fallback: simple table of locations
        hw_map = matched_df[
            (matched_df["source"] == "hochundweit") &
            matched_df["city_name"].notna()
        ].copy()
        if hw_map.empty:
            st.caption("pydeck nicht installiert und keine Standortdaten verfügbar.")
            return
        city_counts = hw_map.groupby("city_name").size().reset_index(name="Kurse").sort_values("Kurse",ascending=False)
        st.dataframe(city_counts.head(15), use_container_width=True, hide_index=True)
        st.caption("Karte nicht verfügbar — pip install pydeck für interaktive Karte.")

def phase_1(offers, params):
    section_header("#dceefb", "3. Was gibt es bereits?")
    if not params["user_text"].strip():
        st.info("Bitte Kurstitel und Beschreibung eingeben."); return None

    with st.spinner("Suche ähnliche Angebote..."):
        matched = match_offers(offers, params["user_text"],
                               params["selected_cats"], params["kg"],
                               params=params)

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

    with st.expander("Karte der Hochschulangebote anzeigen"):
        show_offer_map(matched)

    def show_offers(df_src, tab_key, show_price_stats=True):
        if df_src.empty:
            st.info("Keine passenden Angebote für diese Kombination."); return

        # Build editor key unique to this tab
        editor_key = f"editor_{tab_key}"

        # Prepare display dataframe
        def fmt_price(row):
            pb = str(row.get("price_band",""))
            if pb in PREIS_LABELS: return PREIS_LABELS[pb]
            if pd.notna(row.get("price")) and row["price"] > 0:
                return f"{row['price']:,.0f} EUR"
            return "k.A."

        def fmt_source(src):
            return "Hochschule" if src == "hochundweit" else "Weiterbildung"

        def fmt_mode(mode):
            return DELIVERY_LABELS.get(str(mode), mode)

        display = pd.DataFrame({
            "Einbeziehen":  [str(r["id"]) not in st.session_state.deselected
                             for _, r in df_src.iterrows()],
            "Quelle":       df_src["source"].apply(fmt_source),
            "Titel":        df_src["title"].fillna("").str[:60],
            "Anbieter":     df_src["provider"].fillna("").str[:30],
            "Format":       df_src["format"].apply(fmt_mode).str[:25],
            "Umfang":       df_src.get("umfang", pd.Series("", index=df_src.index)).fillna("").apply(lambda x: x or "k.A."),
            "Preis":        df_src.apply(fmt_price, axis=1),
            "Link":         df_src["url"].fillna("").apply(
                                lambda u: u if u.startswith("http") else ""),
            "_id":          df_src["id"].astype(str),
            "_delivery":    df_src["delivery_mode"].fillna(""),
        })

        # Colour mapping for rows: use delivery mode background
        # st.data_editor doesn't support per-row background natively,
        # but we prefix the Quelle column with a colour indicator
        def quelle_icon(row):
            src_icon = "🔵" if row["Quelle"] == "Hochschule" else "🟡"
            mode_icons = {
                "fully_online":    "💻",
                "hybrid_flexible": "🔄",
                "hybrid_location": "🏫",
                "in_person":       "👥",
            }
            mode_icon = mode_icons.get(row["_delivery"], "")
            return f"{src_icon}{mode_icon} {row['Quelle']}"

        display["Quelle"] = display.apply(quelle_icon, axis=1)

        st.caption(
            "Häkchen in **Einbeziehen** entfernen, um ein Angebot aus der Preisstatistik auszuschließen. "
            "🔵 = Hochschule (hochundweit)  🟡 = Weiterbildung (mein-now)  "
            "💻 Online  🔄 Hybrid (flex)  🏫 Hybrid (Standort)  👥 Präsenz"
        )

        # Render editable table — only "Einbeziehen" is editable
        edited = st.data_editor(
            display.drop(columns=["_id","_delivery"]),
            key=editor_key,
            use_container_width=True,
            hide_index=True,
            height=min(36 * len(display) + 38, 600),
            column_config={
                "Einbeziehen": st.column_config.CheckboxColumn(
                    "Einbeziehen",
                    help="Häkchen entfernen = aus Statistik ausschließen",
                    width="small",
                ),
                "Link": st.column_config.LinkColumn(
                    "Link",
                    display_text="Öffnen →",
                    width="small",
                ),
                "Titel":    st.column_config.TextColumn("Titel",    width="large"),
                "Anbieter": st.column_config.TextColumn("Anbieter", width="medium"),
                "Format":   st.column_config.TextColumn("Format",   width="medium"),
                "Umfang":   st.column_config.TextColumn("Umfang",   width="small"),
                "Preis":    st.column_config.TextColumn("Preis",    width="small"),
                "Quelle":   st.column_config.TextColumn("Quelle",   width="medium"),
            },
            disabled=["Quelle","Titel","Anbieter","Format","Umfang","Preis","Link"],
        )

        # Sync checkbox changes back to session state
        if edited is not None:
            for i, row_checked in enumerate(edited["Einbeziehen"]):
                rid = display["_id"].iloc[i]
                if row_checked:
                    st.session_state.deselected.discard(rid)
                else:
                    st.session_state.deselected.add(rid)

        # Compute active set for statistics
        active_ids = set(display["_id"]) - st.session_state.deselected
        active = df_src[df_src["id"].astype(str).isin(active_ids)]
        n_excl = len(df_src) - len(active)
        if n_excl:
            st.caption(f"{n_excl} Angebot(e) aus der Statistik ausgeschlossen.")

        if not show_price_stats: return

        # Price stats from active HW courses
        hw_act = active[(active["source"]=="hochundweit") &
                        active["price"].notna() & (active["price"]>0)]
        mn_act = active[active["source"]=="meinnow"]

        if len(hw_act) >= 3:
            st.markdown("**Preisstatistik — Hochschulangebote:**")
            m1,m2,m3 = st.columns(3)
            m1.metric("Median",    f"{hw_act['price'].median():,.0f} EUR")
            m2.metric("25. Perz.", f"{hw_act['price'].quantile(.25):,.0f} EUR")
            m3.metric("75. Perz.", f"{hw_act['price'].quantile(.75):,.0f} EUR")
        if len(mn_act) >= 2:
            bands = mn_act["price_band"].value_counts()
            band_str = "  ·  ".join(f"{PREIS_LABELS.get(b,b)}: {c}" for b,c in bands.items())
            st.caption(f"Weiterbildungsangebote (Preisbänder): {band_str}")
        elif len(hw_act) < 3:
            st.caption("Zu wenige Preisangaben für Statistik.")

    _hf_st = "✓ Semantische Re-Ranking aktiv" if HF_TOKEN else "Schlüsselwort-Suche (TF-IDF)"
    st.caption(
        f"Relevanz-Suche: TF-IDF + strukturelle Gewichtung · {_hf_st}. "
        "Häkchen entfernen = aus Statistik ausschließen."
    )
    show_offers(matched, "all", show_price_stats=True)
    return matched


def phase_2(berufe_df, demand, params, comp_demand=None, comp_map=None):
    section_header("#fff0d4", "3. Nachfrage — Kompetenzen und Berufsgruppen")

    user_text = params.get("user_text","").strip()
    if not user_text:
        st.info("Bitte Kurstitel und Beschreibung in Schritt 1 eingeben.")
        return []

    # ── STEP A: Competency suggestions ───────────────────────────────────
    st.markdown("#### Welche Kompetenzen vermittelt Ihr Kurs?")
    st.caption(
        "Basierend auf Ihrem Kurstitel und Ihrer Beschreibung wurden folgende Kompetenzen "
        "vorgeschlagen. Wählen Sie alle aus, die Ihr Kurs abdecken soll. "
        "Die Auswahl bestimmt sowohl den Kompetenz-Score als auch die vorgeschlagenen Zielgruppen."
    )

    if comp_demand is None or comp_demand.empty:
        st.warning("Kompetenz-Daten nicht verfügbar.")
        suggested_df = pd.DataFrame()
    else:
        suggested_df = suggest_comps_for_query(user_text, comp_demand, top_n=15)

    if "selected_comps" not in st.session_state:
        st.session_state.selected_comps = set()

    # Reset if query changed
    if st.session_state.get("_last_query") != user_text:
        st.session_state.selected_comps = set()
        st.session_state._last_query = user_text

    if not suggested_df.empty:
        cols = st.columns(3)
        for i, row in suggested_df.iterrows():
            g   = row.get("avg_growth")
            wj  = row.get("weighted_jobs", 0)
            sel = row["competency_name"] in st.session_state.selected_comps
            g_str  = f"{g*100:+.1f}%" if pd.notna(g) else ""
            wj_str = f"{int(wj):,} Stellen" if wj > 0 else ""
            meta   = "  ·  ".join(filter(None,[g_str,wj_str]))
            prefix = "✓ " if sel else ""
            label  = f"{prefix}{row['competency_name'][:44]}\n{meta}" if meta else f"{prefix}{row['competency_name'][:44]}"
            with cols[i % 3]:
                if st.button(label, key=f"comp_btn_{i}",
                             use_container_width=True,
                             type="primary" if sel else "secondary"):
                    if sel:
                        st.session_state.selected_comps.discard(row["competency_name"])
                    else:
                        st.session_state.selected_comps.add(row["competency_name"])
                    st.rerun()

    selected = st.session_state.selected_comps

    # ── Kompetenz-Score ───────────────────────────────────────────────────
    if selected and comp_demand is not None and not comp_demand.empty:
        st.write("")
        local = comp_demand[
            comp_demand["competency_name"].isin(selected) &
            comp_demand["region"].isin(["Dahme-Spreewald","Oder-Spree","Teltow-Fläming","Berlin"])
        ]
        if not local.empty:
            avg_g  = local["avg_growth"].mean()
            tot_wj = local["weighted_jobs"].sum()
            # Score 1–10: based on average growth of selected competencies
            raw    = min(10, max(1, round(5 + avg_g * 30)))
            trend  = "wachsend" if avg_g > 0.05 else "stabil" if avg_g > -0.05 else "rückläufig"
            csc1, csc2 = st.columns([1,3])
            with csc1:
                score_badge(raw, f"Kompetenz-Trend: {trend}")
            with csc2:
                st.caption(
                    f"**{len(selected)} Kompetenzen ausgewählt** — "
                    f"Ø-Wachstum: {avg_g*100:+.1f}% · "
                    f"Gewichtete Stellennachfrage: {int(tot_wj):,}"
                )
                st.caption(
                    "Grüne Chips = wachsende Kompetenz in der Region. "
                    "Ausgewählte Kompetenzen erscheinen als Lernziel-Vorschläge in der Angebotsbeschreibung."
                )

    st.write("---")

    # ── STEP B: Profession suggestions from competencies ─────────────────
    st.markdown("#### Welche Berufsgruppen profitieren von diesem Kurs?")
    st.caption(
        "Diese Berufsgruppen wurden aus Ihren gewählten Kompetenzen und dem Kurstext abgeleitet. "
        "Bestätigen Sie die relevanten Gruppen — sie bilden die Grundlage für die Nachfrageanalyse."
    )

    # Derive candidate professions: from competencies first, then text fallback
    if selected and comp_map is not None and not comp_map.empty:
        comp_profs = comps_to_professions(list(selected), comp_map, top_n=20)
        comp_prof_names = comp_profs["profession_name"].tolist() if not comp_profs.empty else []
    else:
        comp_prof_names = []

    # Also match by text (existing logic) — merge both sources
    text_matches = match_berufe(berufe_df, user_text, n=15)
    text_prof_names = [b["beruf_name"] for b in text_matches]

    # Combined pool: comp-derived first, then text-derived, deduplicated
    all_candidates = list(dict.fromkeys(comp_prof_names + text_prof_names))[:20]

    if "confirmed_berufe" not in st.session_state: st.session_state.confirmed_berufe = set()
    if "nd_pool"          not in st.session_state: st.session_state.nd_pool          = []

    # Refresh pool when query changes
    if st.session_state.get("_last_query_nd") != user_text or not st.session_state.nd_pool:
        st.session_state.nd_pool = all_candidates
        st.session_state._last_query_nd = user_text
        # Auto-confirm top 3 comp-derived professions
        if comp_prof_names and not st.session_state.confirmed_berufe:
            st.session_state.confirmed_berufe = set(comp_prof_names[:3])

    confirmed = st.session_state.confirmed_berufe

    # Show more button
    shown_count = st.session_state.get("nd_shown", 8)

    # Tile grid
    candidates = [b for b in st.session_state.nd_pool if b not in confirmed][:shown_count]
    if candidates:
        tile_cols = st.columns(3)
        for j, beruf in enumerate(candidates):
            with tile_cols[j % 3]:
                b_row = berufe_df[berufe_df["beruf_name"]==beruf]
                kldb  = int(b_row["kldb_id"].iloc[0]) if not b_row.empty else None
                growth_str = ""
                if kldb:
                    ds = demand[(demand["kldb_id"]==kldb) &
                                demand["region"].isin(["Berlin","Brandenburg"])]
                    if not ds.empty:
                        g = ds["percentage_diff_previous_year"].mean()
                        growth_str = f"{g*100:+.1f}%"
                label_p = f"{beruf[:44]}\n{growth_str}" if growth_str else beruf[:44]
                if st.button(label_p, key=f"nd_conf_{j}", use_container_width=True):
                    st.session_state.confirmed_berufe.add(beruf)
                    st.rerun()

        c_more, c_clear = st.columns([1,1])
        with c_more:
            if len(st.session_state.nd_pool) > shown_count:
                if st.button("Weitere Vorschläge"):
                    st.session_state.nd_shown = shown_count + 5
                    st.rerun()
        with c_clear:
            if st.button("Alle zurücksetzen"):
                st.session_state.confirmed_berufe = set()
                st.session_state.nd_shown = 8
                st.rerun()

    # Confirmed berufe
    if confirmed:
        st.markdown("**Bestätigte Berufsgruppen:**")
        cols2 = st.columns(min(len(confirmed), 3))
        changed2 = False
        for i, beruf in enumerate(sorted(confirmed)):
            with cols2[i % 3]:
                if st.button(f"✓ {beruf[:38]}  ×", key=f"nd_rem_{beruf[:20]}",
                             use_container_width=True, type="primary"):
                    st.session_state.confirmed_berufe.discard(beruf)
                    changed2 = True
        if changed2: st.rerun()
    else:
        st.info("Bitte mindestens eine Berufsgruppe bestätigen, um die Nachfrageanalyse zu starten.")
        return []

    # ── STEP C: Demand analysis ───────────────────────────────────────────
    st.write("---")
    all_kldb   = berufe_df[berufe_df["beruf_name"].isin(confirmed)]["kldb_id"].astype(int).tolist()
    demand_sub = demand[demand["kldb_id"].isin(all_kldb)]

    if demand_sub.empty:
        st.warning("Keine Nachfragedaten für diese Berufsgruppen.")
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
        colors = rdf["Wachstum_%"].apply(lambda x: "#27ae60" if x>5 else "#f39c12" if x>-5 else "#c0392b")
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
    top["Wachstum 2024→2025"] = top["Wachstum_pct"].apply(lambda x: f"{x*100:+.1f}%" if pd.notna(x) else "n/a")
    top["Stellenausschreibungen"] = top["Stellen"].apply(lambda x: f"{int(x):,}")
    st.dataframe(top[["beruf_name","Stellenausschreibungen","Wachstum 2024→2025"]]
                 .rename(columns={"beruf_name":"Berufsbezeichnung"}),
                 use_container_width=True, hide_index=True)

    # ── Competency chips (confirmed professions layer) ────────────────────
    if comp_demand is not None and not comp_demand.empty and all_kldb:
        st.write("---")
        st.markdown("**Nachgefragte Kompetenzen für diese Berufsgruppen**")
        st.caption(
            "Offizielle Kompetenzprofile aus BERUFENET (Bundesagentur für Arbeit), "
            "gewichtet nach regionaler Stellennachfrage. "
            "Grün = wachsend · Gelb = stabil · Rot = rückläufig."
        )
        if comp_map is not None and not comp_map.empty:
            kldb_str = [str(k) for k in all_kldb]
            relevant = comp_map[comp_map["kldb_id"].astype(str).isin(kldb_str)]
            if not relevant.empty:
                top_comps = (relevant
                    .groupby(["competency_name","competency_code","competency_type"], as_index=False)
                    .agg(agg_score=("weight","sum"), n_professions=("kldb_id","nunique"))
                    .sort_values("agg_score", ascending=False).head(40))
                comp_with_demand = top_comps.merge(
                    comp_demand[comp_demand["region"].isin(
                        ["Dahme-Spreewald","Oder-Spree","Teltow-Fläming","Berlin"]
                    )].groupby("competency_name", as_index=False).agg(
                        total_jobs=("total_jobs","sum"),
                        avg_growth=("avg_growth","mean"),
                        demand_score=("demand_score","mean"),
                    ),
                    on="competency_name", how="left"
                ).sort_values("agg_score", ascending=False).head(15)

                if not comp_with_demand.empty:
                    comp_with_demand["Wachstum"] = comp_with_demand["avg_growth"].apply(
                        lambda x: f"{x*100:+.1f}%" if pd.notna(x) else "n/a")
                    cols_c = st.columns(3)
                    for i, (_, row) in enumerate(comp_with_demand.iterrows()):
                        gv = row["avg_growth"] if pd.notna(row.get("avg_growth")) else 0
                        bg  = "#e1f5ee" if gv>0.05 else "#faeeda" if gv>-0.05 else "#fee2e2"
                        txt = "#085041" if gv>0.05 else "#6b3800" if gv>-0.05 else "#7f1d1d"
                        with cols_c[i % 3]:
                            st.markdown(
                                f'<div style="background:{bg};color:{txt};border-radius:7px;'
                                f'padding:7px 12px;margin:3px 0;font-size:13px;line-height:1.4">'
                                f'<strong>{row["competency_name"][:40]}</strong><br>'
                                f'<span style="font-size:11px">Wachstum: {row["Wachstum"]}</span>'
                                f'</div>', unsafe_allow_html=True)
                    with st.expander("Alle Kompetenzen anzeigen"):
                        display_comps = comp_with_demand[[
                            "competency_name","competency_type","Wachstum","n_professions"
                        ]].rename(columns={"competency_name":"Kompetenz",
                                           "competency_type":"Typ","n_professions":"Berufe"})
                        st.dataframe(display_comps, use_container_width=True, hide_index=True)

    # Store selected comps in radar_params for Lernziel pre-fill
    if "radar_params" not in st.session_state:
        st.session_state.radar_params = {}
    st.session_state.radar_params["selected_competencies"] = list(
        st.session_state.get("selected_comps", set()))

    return all_kldb


def phase_3(offers, params, matched):
    section_header("#ede0f5", "5. Preisgestaltung")
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

        # Deckungsbeitrag chart — centred on target_tn
        target  = params["target_tn"]
        tn_min  = max(1, int(target * 0.2))
        tn_max  = max(int(target * 2.8), target + 15)
        tn_range = list(range(tn_min, tn_max + 1))

        # Price lines: break-even + p25/median/p75 from comparable courses
        be_r = round(be_preis / 100) * 100

        # Market percentiles from matched courses
        mkt_p25 = mkt_med = mkt_p75 = None
        if priced_all is not None and len(priced_all) >= 3:
            mkt_p25 = priced_all["price"].quantile(.25)
            mkt_med = priced_all["price"].median()
            mkt_p75 = priced_all["price"].quantile(.75)

        # Build price set: break-even + market anchors (if available) + bracket
        mkt_prices = [p for p in [mkt_p25, mkt_med, mkt_p75] if p is not None]
        price_candidates = sorted(set(filter(lambda p: p > 0, [
            be_r,
            round(be_preis * 0.65 / 100) * 100,
            round(be_preis * 1.4  / 100) * 100,
        ] + [round(p / 100) * 100 for p in mkt_prices])))

        fig_be = go.Figure()
        palette = ["#c0392b","#e67e22","#185fa5","#27ae60","#7f77dd","#9b59b6"]
        mkt_rounded = {round(p/100)*100 for p in mkt_prices} if mkt_prices else set()
        for i, preis in enumerate(price_candidates):
            revenue = [t * (preis/(1+params["overhead"]) - params["sachkosten"]) - fix_net
                       for t in tn_range]
            is_be  = (preis == be_r)
            is_mkt = (preis in mkt_rounded)
            if is_mkt:
                which = ("25. Perz." if mkt_p25 and abs(preis - round(mkt_p25/100)*100) < 50
                         else "Median" if mkt_med and abs(preis - round(mkt_med/100)*100) < 50
                         else "75. Perz.")
                label = f"{preis:,.0f} EUR/TN  ← Markt {which}"
            else:
                label = f"{preis:,.0f} EUR/TN" + (" ← Break-even" if is_be else "")
            fig_be.add_trace(go.Scatter(
                x=tn_range, y=revenue, mode="lines",
                name=label,
                line=dict(width=3 if is_be else 2 if is_mkt else 1.5,
                          color=palette[i % len(palette)],
                          dash="solid" if is_be else "dashdot" if is_mkt else "dot")))

        fig_be.add_hline(y=0, line_color="#333", line_width=1.5)
        fig_be.add_vline(x=target, line_dash="dash", line_color="#555", line_width=1.5,
                         annotation_text=f"{target} TN (Ziel)",
                         annotation_position="top right")
        fig_be.update_layout(
            title="Deckungsbeitrag — zentriert auf Ziel-Teilnehmerzahl",
            xaxis_title="Teilnehmerzahl", yaxis_title="Ergebnis (EUR)",
            xaxis=dict(range=[tn_min, tn_max]),
            height=380, margin=dict(t=50, b=90),
            legend=dict(orientation="h", y=-0.32))

        # Break-even table
        be_rows = []
        for p in sorted(set(price_candidates + [round(be_preis*2/100)*100])):
            d = p/(1+params["overhead"]) - params["sachkosten"]
            if d > 0:
                tn_needed = math.ceil(fix_net/d)
                be_rows.append({
                    "Preis/TN": f"{p:,} EUR",
                    "TN für Break-even": tn_needed,
                    "": "← Ihr Ziel" if tn_needed == target else (
                        "✓ rentabel" if tn_needed < target else "")
                })

        col_chart, col_tbl = st.columns([3, 1])
        with col_chart:
            st.plotly_chart(fig_be, use_container_width=True)
            st.caption("Durchgezogene Linie = Break-even-Preis. "
                       "Oberhalb der Nulllinie ist der Kurs profitabel.")
        with col_tbl:
            st.markdown("**Break-even**")
            if be_rows:
                st.dataframe(pd.DataFrame(be_rows), hide_index=True,
                             use_container_width=True,
                             height=min(36*len(be_rows)+38, 380))

        st.write("---")

    st.subheader("Marktpreise ähnlicher Kurse")
    if priced_all is not None and len(priced_all) >= 3:
        p25 = priced_all["price"].quantile(.25)
        med = priced_all["price"].median()
        p75 = priced_all["price"].quantile(.75)

        # Clip y-axis to avoid outlier distortion: show ±2.5×IQR around median
        iqr = p75 - p25
        y_lo = max(0, p25 - iqr * 1.5)
        y_hi = min(priced_all["price"].max(), p75 + iqr * 2.5)

        fig_mkt = px.box(priced_all, y="price", points="outliers",
            title="Preisverteilung ähnlicher Kurse",
            labels={"price":"Preis (EUR)"},
            color_discrete_sequence=["#185fa5"], height=300)
        fig_mkt.update_yaxes(range=[y_lo, y_hi])
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
    offers        = load_offers()
    demand        = load_demand()
    berufe        = load_berufe()
    kgs           = load_kgs()
    comp_demand   = load_competency_demand()
    comp_summary  = load_competency_summary()
    comp_map      = load_profession_competency_map()

    with st.sidebar:
        st.markdown("""
## Weiterbildungs-Radar
### TH Wildau

Dieses Werkzeug unterstützt Lehrende dabei, eine neue Weiterbildungsidee zu analysieren — bevor die eigentliche Kursentwicklung beginnt.

---

### Schritt 1 — Eckdaten zum Angebot

Geben Sie Kurstitel, Kurzbeschreibung und Kostenparameter ein. Je mehr Text Sie eingeben, desto präziser werden alle nachfolgenden Analysen.

---

### Schritt 2 — Vergleichsangebote

**Was wird verglichen?** Ihr Text wird mit über 13.000 Kursen aus hochundweit.de (wissenschaftliche Weiterbildung) und mein-now.de (berufliche Weiterbildung) verglichen — per Schlagwort- und Stammabgleich.

**Angebots-Score (1–10)** — Wie dicht ist der Markt besetzt? 0 Treffer bei vergleichbaren Hochschulkursen = Score 1 (Marktlücke). Über 40 Treffer = Score 10 (starker Wettbewerb). Ein hoher Score bedeutet nicht, dass der Kurs nicht sinnvoll ist — aber er zeigt, dass Differenzierung wichtig wird.

**PGT/QST-Filter** — Kurse sind in thematischen Kategorien hinterlegt (Profilgebende Themen: Verwaltung, Mobilität, Wertschöpfung; Querschnittsthemen: Nachhaltigkeit, Diversity, Internationalisation). Wählen Sie passende Kategorien, um die Suche zu verfeinern.

---

### Schritt 3 — Nachfrage: Kompetenzen und Berufsgruppen

**Wie funktionieren die Kompetenzvorschläge?**
Aus Ihrem Kurstitel und Ihrer Beschreibung werden passende Kompetenzen aus dem offiziellen BERUFENET-System der Bundesagentur für Arbeit vorgeschlagen (5.303 Kompetenzen, abgeglichen über Wort- und Zeichenketten-Ähnlichkeit). Wählen Sie alle Kompetenzen aus, die Ihr Kurs vermitteln soll.

**Kompetenz-Score (1–10)** — Basiert auf dem durchschnittlichen Nachfragewachstum der gewählten Kompetenzen in der TH-Wildau-Region und Berlin/Brandenburg (Quelle: Jobmonitor + BERUFENET, 2024→2025). Grüne Chips = wachsende Kompetenz. Ausgewählte Kompetenzen werden automatisch als Lernziel-Vorschläge in die Angebotsbeschreibung übertragen.

**Wie werden Berufsgruppen vorgeschlagen?**
Zuerst werden Berufe gesucht, die die gewählten Kompetenzen als Kernkompetenzen einfordern (BERUFENET-Mapping). Ergänzend werden Berufsbezeichnungen direkt mit Ihrem Text abgeglichen (KldB-Systematik, 1.210 Berufsgruppen). Bestätigen Sie die relevanten Berufe — sie bilden die Grundlage für die Nachfrageanalyse.

**Nachfrage-Score (1–10)** — Medianes Wachstum der Stellenanzeigen für die gewählten Berufe, gewichtet nach Region: TH Wildau Region (Dahme-Spreewald, Oder-Spree, Teltow-Fläming) zählt dreifach, Berlin/Brandenburg zweifach.

---

### Schritt 4 — Preisgestaltung

**Break-even-Preis** = ((Entwicklungskosten + Implementierungskosten) / Teilnehmerzahl + Sachkosten/TN) × (1 + Overhead)

Der Deckungsbeitrags-Chart zeigt Ihren Break-even sowie die Marktpreise ähnlicher Kurse: die gestrichelten Linien markieren das 25. Perzentil, den Median und das 75. Perzentil der gefundenen Vergleichskurse.

---

**Datenquellen**

- Kurse: hochundweit.de + mein-now.de, Stand 2025, > 13.000 Kurse
- Stellennachfrage: Jobmonitor der Bertelsmann Stiftung, Berlin/Brandenburg 2024–2025
- Kompetenzprofile: BERUFENET, Bundesagentur für Arbeit, 5.303 Kompetenzen

---

*Dieser Prototyp dient zur Orientierung und ersetzt keine vollständige Marktanalyse.*

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
        phase_2(berufe, demand, params, comp_demand, comp_map)
        st.write("---")
        phase_3(offers, params, matched)
        feedback_section()

        # ── Zur Angebotsbeschreibung ──────────────────────────────
        st.write("---")
        st.subheader("Nächster Schritt")
        st.markdown(
            "Haben Sie genug Informationen gesammelt? Dann können Sie jetzt "
            "direkt zur **offiziellen Angebotsbeschreibung** wechseln — "
            "alle Angaben aus dem Radar werden automatisch übertragen."
        )
        if st.button(
            "Zur Angebotsbeschreibung (Teil 1) →",
            type="primary",
            use_container_width=False,
        ):
            st.session_state.radar_params = params
            st.switch_page("pages/1_Angebotsbeschreibung.py")
    else:
        st.info("Geben Sie einen Kurstitel und eine Beschreibung ein, um zu starten.")

if __name__ == "__main__":
    main()
