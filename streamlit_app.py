# -*- coding: utf-8 -*-
"""
CUT Embedded Wall Streamlit v7.4
Professional single-pane Streamlit interface aligned with the desktop GUI.
"""
from __future__ import annotations

import hashlib
import base64
import html
import math
import os
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, ScalarFormatter
import pandas as pd
import streamlit as st

import matplotlib.cm as cm
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from copy import deepcopy

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import CUT_Embedded_Wall_SOLVER_DISPATCHER_v6 as solvers

APP_VERSION = "CUT Embedded Wall v7.4"
HOME_URL = "https://cut-apps.streamlit.app/"
REINFORCEMENT_REQUIRED_SOLVER = "Flexible wall - Fixed base (differential equation)"
REINFORCEMENT_ALLOWED_SOLVERS = {
    "Flexible wall - Fixed base (differential equation)",
    "Flexible wall - Base spring (differential equation)",
}


def about_text() -> str:
    return (
        f"{APP_VERSION}\n\n"
        "Educational / research tool for CUT embedded wall calculations.\n\n"
        "Developer: Associate Professor Lysandros Pantelidis\n"
        "Department of Civil Engineering and Geomatics\n"
        "Cyprus University of Technology\n"
        "Email: lysandros.pantelidis@cut.ac.cy\n\n"
        "Free educational tool. No warranty is provided. Use at your own responsibility."
    )

PAGES = [
    "Model inputs",
    "Stages and reinforcement",
    "Run & solver monitor",
    "Summary results",
    "Results table",
    "Plots",
    "Water level animation",
    "Stages animation",
    "Point query",
    "Advanced diagnostics",
]

SOLVER_CARDS = [
    ("fixed_closed", "Flexible wall - Fixed base (closed-form bending)", "Closed-form bending"),
    ("fixed_diff", "Flexible wall - Fixed base (differential equation)", "Differential equation"),
    ("base_spring", "Flexible wall - Base spring (differential equation)", "Base spring"),
    ("rigid", "Rigid wall (no bending)", "Rigid wall"),
    ("general", "Any wall (general case)", "General case"),
]

REINFORCEMENT_CARDS = [
    ("none", "No reinforcement", "No reinforcement"),
    ("anchor", "Anchored embedded wall", "Anchors"),
    ("prop", "Propped embedded wall", "Props"),
    ("geogrid", "MSE walls, geogrid reinforced", "Geogrid"),
    ("strip", "MSE walls, metal strip reinforced", "Metal strips"),
    ("metalgrid", "MSE walls, metal grid reinforced", "Metal grids"),
]

st.set_page_config(page_title=APP_VERSION, page_icon="🏗️", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
<style>
:root { --cut-blue:#173f6b; --cut-blue2:#1f5f99; --cut-bg:#f4f7fb; --cut-border:#d8e2ee; --cut-text:#283044; }

.block-container {
    padding-top:1.35rem;
    padding-bottom:.8rem;
    max-width:1500px;
}

.cut-hero {
    padding:1.05rem 1.20rem;
    border-radius:16px;
    background:linear-gradient(135deg,#0f2542,#173f6b 55%,#1f5f99);
    color:white;
    box-shadow:0 8px 18px rgba(15,37,66,.15);
    margin-top:.45rem;
    margin-bottom:.85rem;
}

.cut-hero h1 {
    margin:0;
    font-size:1.55rem;
    line-height:1.15;
}

.cut-hero p {
    margin:.45rem 0 0;
    color:#dce9f8;
    font-size:.88rem;
}

.cut-hero h1{
    margin:0;
    font-size:1.25rem;
    line-height:1.05
}

.cut-hero p{
    margin:.15rem 0 0;
    color:#dce9f8;
    font-size:.78rem
}

.cut-section-title{
    font-size:1.15rem;
    font-weight:750;
    margin:.35rem 0 .20rem;
    color:#2b3042
}

.cut-note{
    border-left:4px solid var(--cut-blue2);
    background:#eef6ff;
    color:#17324f;
    padding:.42rem .65rem;
    border-radius:8px;
    margin:.25rem 0 .45rem;
    font-size:.82rem
}

.cut-warning{
    border-left:4px solid #f97316;
    background:#fff7ed;
    color:#7c2d12;
    padding:.42rem .65rem;
    border-radius:8px;
    margin:.25rem 0 .45rem;
    font-size:.82rem
}

.home-link{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    gap:.38rem;
    background:#eaf2fb;
    color:#173f6b!important;
    text-decoration:none!important;
    border:1px solid #9fbedf;
    border-radius:14px;
    padding:.28rem .58rem;
    font-weight:700;
    box-shadow:0 2px 8px rgba(0,0,0,.10);
    white-space:nowrap;
    font-size:.82rem;
    height:42px;
    min-width:118px;
    box-sizing:border-box;
}

.home-link img{
    width:20px;
    height:20px;
    object-fit:contain
}

.home-link:hover{
    background:#eef6ff;
}

.stat-grid{
    display:grid;
    grid-template-columns:repeat(5,minmax(0,1fr));
    gap:.36rem;
    margin:.25rem 0 .42rem
}

.stat{
    background:#fff;
    border:1px solid var(--cut-border);
    border-radius:11px;
    padding:.38rem .52rem;
    min-height:48px
}

.stat-label{
    font-size:.68rem;
    color:#64748b;
    font-weight:650
}

.stat-value{
    font-size:.82rem;
    color:#2b3042;
    font-weight:720;
    line-height:1.18;
    white-space:normal;
    overflow:visible;
    text-overflow:clip;
    word-break:normal;
}

.nav-wrap div[role="radiogroup"]{
    gap:.18rem
}

.nav-wrap label{
    border-radius:999px!important;
    background:#edf2f7!important;
    border:1px solid #dbe4ef!important;
    padding:.32rem .55rem!important;
    font-size:.82rem!important
}

.nav-wrap label[data-baseweb="radio"] > div:first-child{
    display:none!important
}

.nav-wrap p{
    font-size:.82rem!important;
}

/* ------------------------------------------------ */
/* Reinforcement & solver icon buttons              */
/* ------------------------------------------------ */

.img-grid{
    display:grid;
    gap:.38rem;
    margin:.28rem 0 .45rem
}

.img-grid.solver{
    grid-template-columns:repeat(5,minmax(118px,1fr));
}

.img-grid.reinf{
    grid-template-columns:repeat(6,minmax(120px,1fr));
}

.img-card{
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    gap:.30rem;

    border:1px solid #d7dee8;
    border-radius:12px;

    background:#fff;

    min-height:102px;

    padding:.45rem .30rem;

    text-decoration:none!important;
    color:#334155!important;

    box-shadow:0 3px 10px rgba(23,63,107,.05);

    transition:.10s ease-in-out
}

.img-card:hover{
    border-color:#1f5f99;
    transform:translateY(-1px);
    box-shadow:0 6px 14px rgba(23,63,107,.12)
}

.img-card.selected{
    border:2px solid #1f5f99;
    background:#eef6ff
}

.img-card img{
    width:auto;

    max-width:72px;
    max-height:72px;

    object-fit:contain;
    display:block;
    image-rendering:auto
}

.img-card span{
    font-size:.76rem;
    font-weight:760;

    text-align:center;

    line-height:1.08;

    min-height:1.6em;

    display:flex;
    align-items:center;
    justify-content:center
}

.img-grid.reinf .img-card{
    min-height:96px
}

.img-grid.reinf .img-card img{
    max-width:66px;
    max-height:66px
}


.cut-visible-field-label{
    font-size:.82rem;
    font-weight:750;
    color:#334155;
    margin:.45rem 0 .12rem 0;
    line-height:1.15;
}

/* ------------------------------------------------ */
/* Compact number inputs                            */
/* ------------------------------------------------ */

[data-testid="stNumberInput"] button,
[data-testid="stNumberInputStepUp"],
[data-testid="stNumberInputStepDown"] {
    display:none!important;
    visibility:hidden!important;
    width:0!important;
}

[data-testid="stNumberInput"] input {
    padding:.12rem .30rem!important;
    min-height:1.45rem!important;
    font-size:.72rem!important;
}

[data-testid="stNumberInput"] label p,
.stSelectbox label p,
.stTextInput label p {
    font-size:.67rem!important;
    line-height:1.05!important;
}

.stDataFrame{
    border:1px solid #d8e2ee;
    border-radius:8px;
    overflow:hidden;
    font-size:.72rem!important
}

.element-container{
    margin-bottom:.02rem!important
}

h4{
    margin-top:.65rem!important;
    margin-bottom:.25rem!important
}

.stExpander{
    border-radius:12px!important
}

.stPlotlyChart,
.stPyplot{
    margin-top:.1rem!important
}

.input-grid-header{
    font-size:.78rem;
    font-weight:750;
    color:#334155;
    padding:.12rem .20rem;
    border-bottom:1px solid #d8e2ee;
}

.input-grid-label{
    font-size:.82rem;
    font-weight:650;
    color:#334155;
    padding-top:.22rem;
}

.input-grid-value{
    font-size:.82rem;
    color:#334155;
    padding-top:.22rem;
}

div[data-testid="stNumberInput"]{
    margin-top:-.35rem!important;
    margin-bottom:-.45rem!important;
}

div[data-testid="stNumberInput"] input{
    height:1.55rem!important;
    min-height:1.55rem!important;
    padding:.05rem .30rem!important;
    font-size:.74rem!important;
}

/* Compact engineering tables use explicit header rows, so Streamlit widget
   labels must not be repeated inside the cells. */
div[data-testid="stNumberInput"] label,
div[data-testid="stSelectbox"] label{
    display:none!important;
    height:0!important;
    min-height:0!important;
    margin:0!important;
    padding:0!important;
    visibility:hidden!important;
}

@media(max-width:900px){

    .stat-grid{
        grid-template-columns:repeat(2,1fr)
    }

    .img-grid.reinf{
        grid-template-columns:repeat(3,1fr)
    }

    .img-grid.solver{
        grid-template-columns:repeat(6,1fr)
    }
    .img-grid.solver .img-card{grid-column:span 3}
    .img-grid.solver .img-card:nth-child(n+3){grid-column:span 2}
}
}


/* ------------------------------------------------ */
/* v7.4 responsive compact engineering grids         */
/* ------------------------------------------------ */
/* Mobile fix: keep Streamlit column rows as compact grid rows.
   The expander body is the single horizontal scroll container; individual
   widgets are not allowed to create their own horizontal/vertical whitespace. */
@media(max-width:900px){
    div[data-testid="stExpander"] details > div{
        overflow-x:auto!important;
        overflow-y:visible!important;
        -webkit-overflow-scrolling:touch!important;
        padding-left:.55rem!important;
        padding-right:.55rem!important;
    }

    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]{
        display:grid!important;
        grid-auto-flow:column!important;
        grid-auto-columns:max-content!important;
        align-items:start!important;
        flex-wrap:nowrap!important;
        gap:.10rem!important;
        width:max-content!important;
        min-width:max-content!important;
        max-width:none!important;
        overflow:visible!important;
        margin:.015rem 0!important;
        padding:0!important;
    }

    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))){
        grid-template-columns:108px 132px 132px!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(6)):not(:has(> div:nth-child(7))){
        grid-template-columns:104px 76px 76px 104px 96px 96px!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(4)):not(:has(> div:nth-child(5))){
        grid-template-columns:150px 150px 150px 120px!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(5)):not(:has(> div:nth-child(6))){
        grid-template-columns:135px 135px 100px 110px 110px!important;
    }

    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] > div,
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{
        width:auto!important;
        min-width:0!important;
        max-width:none!important;
        flex:none!important;
        padding:0!important;
        margin:0!important;
    }

    .input-grid-header{
        font-size:.72rem!important;
        line-height:1.05!important;
        padding:.03rem .03rem!important;
        white-space:nowrap!important;
        border-bottom:1px solid #cfd8e3!important;
        min-height:1.05rem!important;
        display:flex!important;
        align-items:end!important;
    }
    .input-grid-label{
        font-size:.72rem!important;
        line-height:1.05!important;
        padding:.03rem .03rem!important;
        min-height:1.72rem!important;
        display:flex!important;
        align-items:center!important;
        white-space:nowrap!important;
    }
    .input-grid-value{
        font-size:.72rem!important;
        line-height:1.05!important;
        padding:.03rem .03rem!important;
        min-height:1.72rem!important;
        display:flex!important;
        align-items:center!important;
        white-space:nowrap!important;
    }

    div[data-testid="stNumberInput"],
    div[data-testid="stSelectbox"],
    div[data-testid="stCheckbox"]{
        margin:0!important;
        padding:0!important;
    }
    div[data-testid="stNumberInput"] label,
    div[data-testid="stSelectbox"] label{
        display:none!important;
        height:0!important;
        min-height:0!important;
        margin:0!important;
        padding:0!important;
        visibility:hidden!important;
    }
    div[data-testid="stNumberInput"] input{
        height:1.72rem!important;
        min-height:1.72rem!important;
        padding:.02rem .24rem!important;
        font-size:.72rem!important;
        border-radius:.42rem!important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
        min-height:1.92rem!important;
        height:1.92rem!important;
        font-size:.78rem!important;
        border-radius:.50rem!important;
    }
    div[data-testid="stVerticalBlock"]{
        gap:.08rem!important;
    }
    .stMarkdown:has(.input-grid-header),
    .stMarkdown:has(.input-grid-label),
    .stMarkdown:has(.input-grid-value){
        margin:0!important;
        padding:0!important;
    }
    h4{
        margin-top:.50rem!important;
        margin-bottom:.18rem!important;
        font-size:1.05rem!important;
    }
}

/* Main navigation: align previous/select/next in one row and color them. */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
    background:#eaf2fb!important;
    border:1px solid #b8cce2!important;
    border-radius:11px!important;
}
button[kind="secondary"]{
    background:#e8eef6!important;
    border:1px solid #b8cce2!important;
    color:#223044!important;
    border-radius:11px!important;
}
button[kind="secondary"]:hover{
    background:#dbe8f6!important;
    border-color:#7fa2c7!important;
}

.header-actions{
    display:flex;
    align-items:center;
    gap:.45rem;
    margin:-.35rem 0 .55rem .05rem;
    flex-wrap:nowrap;
}
.header-actions .home-link{margin:0;}
/* Make Home and About visually identical without Streamlit columns. */
.about-details{position:relative;margin:0;padding:0;}
.about-details summary{
    list-style:none;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    height:42px;
    min-width:118px;
    width:118px;
    box-sizing:border-box;
    background:#eaf2fb;
    border:1px solid #9fbedf;
    color:#173f6b;
    border-radius:14px;
    font-weight:700;
    box-shadow:0 2px 8px rgba(0,0,0,.10);
    cursor:pointer;
    white-space:nowrap;
}
.about-details summary::-webkit-details-marker{display:none;}
.about-details[open] summary{background:#dbe8f6;border-color:#7fa2c7;}
.about-details > div{
    position:absolute;
    z-index:1000;
    top:48px;
    left:0;
    width:min(360px, calc(100vw - 2rem));
    background:#fff;
    border:1px solid #cfd8e3;
    border-radius:12px;
    box-shadow:0 8px 24px rgba(0,0,0,.16);
    padding:.75rem;
    color:#223044;
    font-size:.82rem;
    line-height:1.35;
}

@media(max-width:900px){
    .header-actions{gap:.35rem;margin:.35rem 0 .55rem .05rem;}
    .home-link, .about-details summary{
        width:118px!important;
        min-width:118px!important;
        max-width:118px!important;
        height:42px!important;
        margin:0!important;
    }
}

.about-chip{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    min-height:32px;
    padding:.28rem .72rem;
    border-radius:999px;
    background:#ffffff;
    color:#173f6b!important;
    font-weight:750;
    box-shadow:0 2px 8px rgba(0,0,0,.13);
    border:1px solid #d8e2ee;
}

@media(max-width:900px){
    .block-container{padding-left:.75rem;padding-right:.75rem;}
    .cut-hero h1{font-size:1.25rem!important;}
}

</style>
""",
    unsafe_allow_html=True,
)


# v7.4 FIX6: final mobile polishing overrides for compact engineering input grids.
st.markdown(
    """
<style>
@media(max-width:900px){
    .header-actions{
        display:flex!important;
        flex-direction:row!important;
        flex-wrap:nowrap!important;
        align-items:center!important;
        justify-content:flex-start!important;
        gap:.50rem!important;
        width:max-content!important;
        max-width:100%!important;
        margin:.35rem 0 .55rem .05rem!important;
        overflow:visible!important;
    }
    .home-link, .about-details summary{
        width:118px!important;
        min-width:118px!important;
        max-width:118px!important;
        height:42px!important;
        padding:0!important;
        margin:0!important;
        flex:0 0 118px!important;
        box-sizing:border-box!important;
    }

    /* One and only one horizontal scroll region per expander body. */
    div[data-testid="stExpander"] details > div{
        overflow-x:auto!important;
        overflow-y:visible!important;
        -webkit-overflow-scrolling:touch!important;
        padding:.85rem .72rem .62rem .72rem!important;
    }

    /* Streamlit columns are forced to behave as a real table row on phones. */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]{
        display:flex!important;
        flex-direction:row!important;
        flex-wrap:nowrap!important;
        align-items:stretch!important;
        justify-content:flex-start!important;
        gap:.22rem!important;
        width:max-content!important;
        min-width:max-content!important;
        max-width:none!important;
        overflow:visible!important;
        margin:0!important;
        padding:0!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] > div,
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{
        flex:0 0 auto!important;
        width:auto!important;
        min-width:0!important;
        max-width:none!important;
        padding:0!important;
        margin:0!important;
        overflow:visible!important;
    }

    /* Three-column engineering rows: Parameter | Left | Right. */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) > div:nth-child(1){
        flex-basis:126px!important; width:126px!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) > div:nth-child(2),
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) > div:nth-child(3){
        flex-basis:176px!important; width:176px!important;
    }

    /* Six-column global parameter rows. */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(6)):not(:has(> div:nth-child(7))) > div{
        flex-basis:118px!important; width:118px!important;
    }

    /* Four- and five-column numerical/animation rows. */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(4)):not(:has(> div:nth-child(5))) > div{
        flex-basis:156px!important; width:156px!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(5)):not(:has(> div:nth-child(6))) > div{
        flex-basis:144px!important; width:144px!important;
    }

    .stMarkdown:has(.input-grid-header),
    .stMarkdown:has(.input-grid-label),
    .stMarkdown:has(.input-grid-value){
        margin:0!important;
        padding:0!important;
        overflow:visible!important;
    }
    .stMarkdown:has(.input-grid-header) p,
    .stMarkdown:has(.input-grid-label) p,
    .stMarkdown:has(.input-grid-value) p{
        margin:0!important;
        padding:0!important;
    }

    .input-grid-header{
        height:1.40rem!important;
        min-height:1.40rem!important;
        line-height:1.05!important;
        padding:0 .16rem .10rem .16rem!important;
        display:flex!important;
        align-items:flex-end!important;
        white-space:nowrap!important;
        overflow:visible!important;
        font-size:.72rem!important;
        border-bottom:1px solid #cfd8e3!important;
    }
    .input-grid-label,
    .input-grid-value{
        height:2.18rem!important;
        min-height:2.18rem!important;
        line-height:1.05!important;
        padding:.06rem .16rem!important;
        display:flex!important;
        align-items:center!important;
        white-space:nowrap!important;
        overflow:visible!important;
        font-size:.72rem!important;
    }

    div[data-testid="stNumberInput"],
    div[data-testid="stSelectbox"],
    div[data-testid="stCheckbox"]{
        margin:0!important;
        padding:0!important;
        width:100%!important;
        max-width:none!important;
        overflow:visible!important;
    }
    div[data-testid="stNumberInput"] input{
        height:2.06rem!important;
        min-height:2.06rem!important;
        padding:.05rem .28rem!important;
        font-size:.72rem!important;
        border-radius:.46rem!important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
        min-height:2.10rem!important;
        height:2.10rem!important;
        font-size:.76rem!important;
        border-radius:.50rem!important;
    }
    div[data-testid="stVerticalBlock"]{
        gap:.10rem!important;
    }
    h4{
        margin-top:.70rem!important;
        margin-bottom:.28rem!important;
        font-size:1.05rem!important;
        line-height:1.15!important;
    }
}
</style>
""",
    unsafe_allow_html=True,
)



# v7.4 FIX7: final mobile spacing polish.  Keep the table-like Streamlit
# column rows compact, but give header rows enough real height so the first
# data row cannot collide with the headings on narrow screens.
st.markdown(
    """
<style>
@media(max-width:900px){
    /* Header / about buttons: same size and always in one row. */
    .header-actions{
        display:flex!important;
        flex-direction:row!important;
        flex-wrap:nowrap!important;
        align-items:center!important;
        gap:.45rem!important;
        width:100%!important;
        overflow:visible!important;
        margin:.35rem 0 .60rem 0!important;
    }
    .home-link, .about-details summary{
        flex:0 0 122px!important;
        width:122px!important;
        min-width:122px!important;
        max-width:122px!important;
        height:42px!important;
        box-sizing:border-box!important;
    }

    /* Only the expander body scrolls horizontally; cells/widgets never do. */
    div[data-testid="stExpander"] details > div{
        overflow-x:auto!important;
        overflow-y:visible!important;
        -webkit-overflow-scrolling:touch!important;
        padding:.80rem .70rem .64rem .70rem!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]{
        display:flex!important;
        flex-direction:row!important;
        flex-wrap:nowrap!important;
        align-items:stretch!important;
        gap:.18rem!important;
        width:max-content!important;
        min-width:max-content!important;
        max-width:none!important;
        overflow:visible!important;
        margin:0!important;
        padding:0!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] > div,
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{
        flex:0 0 auto!important;
        padding:0!important;
        margin:0!important;
        min-width:0!important;
        max-width:none!important;
        overflow:visible!important;
    }

    /* Input table: narrow enough to be readable on phone, wide enough not to break. */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) > div:nth-child(1){
        flex-basis:122px!important; width:122px!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) > div:nth-child(2),
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) > div:nth-child(3){
        flex-basis:170px!important; width:170px!important;
    }

    /* Global parameters: tighter, but labels remain visible. */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(6)):not(:has(> div:nth-child(7))) > div{
        flex-basis:112px!important; width:112px!important;
    }

    /* Numerical/animation rows. */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(4)):not(:has(> div:nth-child(5))) > div{
        flex-basis:150px!important; width:150px!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(5)):not(:has(> div:nth-child(6))) > div{
        flex-basis:138px!important; width:138px!important;
    }

    .stMarkdown:has(.input-grid-header),
    .stMarkdown:has(.input-grid-label),
    .stMarkdown:has(.input-grid-value){
        margin:0!important;
        padding:0!important;
        overflow:visible!important;
    }
    .stMarkdown:has(.input-grid-header){
        margin-bottom:.18rem!important;
    }
    .stMarkdown:has(.input-grid-header) p,
    .stMarkdown:has(.input-grid-label) p,
    .stMarkdown:has(.input-grid-value) p{
        margin:0!important;
        padding:0!important;
    }

    .input-grid-header{
        height:1.58rem!important;
        min-height:1.58rem!important;
        line-height:1.05!important;
        padding:0 .14rem .16rem .14rem!important;
        display:flex!important;
        align-items:flex-end!important;
        font-size:.72rem!important;
        white-space:nowrap!important;
        overflow:visible!important;
        border-bottom:1px solid #cfd8e3!important;
    }
    .input-grid-label,
    .input-grid-value{
        height:1.98rem!important;
        min-height:1.98rem!important;
        line-height:1.05!important;
        padding:.04rem .14rem!important;
        display:flex!important;
        align-items:center!important;
        font-size:.72rem!important;
        white-space:nowrap!important;
        overflow:visible!important;
    }
    div[data-testid="stNumberInput"],
    div[data-testid="stSelectbox"],
    div[data-testid="stCheckbox"]{
        margin:0!important;
        padding:0!important;
        width:100%!important;
        max-width:none!important;
        overflow:visible!important;
    }
    div[data-testid="stNumberInput"] input{
        height:1.88rem!important;
        min-height:1.88rem!important;
        padding:.04rem .26rem!important;
        font-size:.72rem!important;
        border-radius:.44rem!important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
        min-height:1.98rem!important;
        height:1.98rem!important;
        font-size:.76rem!important;
        border-radius:.50rem!important;
    }
    h4{
        margin-top:.62rem!important;
        margin-bottom:.34rem!important;
        font-size:1.05rem!important;
        line-height:1.15!important;
    }
}
</style>
""",
    unsafe_allow_html=True,
)

def asset_path(*parts: str) -> Path:
    return APP_DIR.joinpath(*parts)



# -----------------------------------------------------------------------------
# In-app help texts (used by Streamlit widgets as the small "?" tooltip).
# This replaces long inline explanatory notes and keeps the interface readable on
# small screens while the written manual is still under development.
# -----------------------------------------------------------------------------
HELP_TEXTS = {
    "Section": "Choose the program page. Previous/Next buttons move sequentially through the workflow.",
    "H (m)": "Wall/ground height measured downward from the retained-side ground surface. Left is excavation side; right is retained side.",
    "z_ex=H_R-H_L (m)": "Final excavation depth below the retained-side ground surface. It is computed from the two ground-surface levels.",
    "β (deg)": "Ground-surface inclination angle on each side, in degrees.",
    "q (kPa)": "Uniform surface surcharge applied on the corresponding side.",
    "z_w (m)": "Water-table elevation/depth below the retained-side ground surface on the corresponding side.",
    "k_h (-)": "Horizontal seismic coefficient. Positive values act in the conventional active direction used by the solver.",
    "k_v (-)": "Vertical seismic coefficient. The sign controls upward/downward inertial effect.",
    "γ_w (kN/m³)": "Unit weight of water used for hydrostatic pressure calculations.",
    "Stiffness type": "Choose whether wall bending stiffness is entered directly as EI or calculated from E with I/thickness.",
    "EI (kPa·m⁴)": "Flexural rigidity per metre width of wall.",
    "E (kPa)": "Young's modulus of the wall material.",
    "I (m⁴) or t (m)": "Second moment of area per metre width, or wall thickness when the program computes I automatically.",
    "Solver": "Select the analysis model. Reinforced systems are automatically restricted to compatible differential-equation solvers.",
    "Integration": "Numerical integration method used for resultant forces and moments.",
    "Rigid movement mode": "Controls how a rigid wall translation/rotation mechanism is selected.",
    "Rigid optimization solver": "Fast equilibrium solves only the balance equations; energy-aware mode also checks work/compatibility criteria.",
    "N iterations": "Maximum number of iterations for the nonlinear search/solver.",
    "Δz / plotting dz (m)": "Vertical discretization used for plotting and numerical profiles. Smaller values give smoother curves but take longer.",
    "n profile points": "Number of depth points used to sample result profiles.",
    "tol": "Numerical convergence tolerance used by the solver.",
    "tol_W work band": "Tolerance for the work/energy acceptance band in relevant solver modes.",
    "tol_F = |ΣF|/scale": "Normalized force-equilibrium tolerance.",
    "tol_M = |ΣM|/scale": "Normalized moment-equilibrium tolerance.",
    "Number of main excavation stages": "Number of principal excavation levels after the initial Stage 0. Stage 0 is the ground-surface/no-excavation state; Stage 1 is the first excavation line; the final stage is locked to z_ex = H_R − H_L.",
    "Intermediate excavation drops between main stages": "Optional lowering steps inserted before each main stage. Example: 4 creates four lowering steps between the previous stage and Stage i, with only supports 1..i−1 active until the main stage is reached.",
    "Diagram": "Select which result quantity is displayed in the animation/plot."
    ,"Run stage animation": "Runs the staged-excavation analysis from Stage 0 to the final stage."
    ,"Apply / regenerate": "Regenerates the stage table using the selected number of main excavation stages. The final row remains locked to z_ex."
    ,"final": "The final excavation stage is locked to the computed final excavation depth.",
    "Water rise mode": "Uniform rise changes both water levels by the same increment; proportional rise moves both toward their final values together.",
    "Number of steps": "Number of water-level or stage positions used in the animation.",
    "z_final_left (m)": "Final water level on the left/excavation side for the water-level animation.",
    "z_final_right (m)": "Final water level on the right/retained side for the water-level animation.",
    "Frame duration (ms)": "Delay between animation frames. Larger values make the animation slower.",
    "x_min": "Manual left plotting limit. Leave the automatic value unless extra horizontal space is needed.",
    "x_max": "Manual right plotting limit. Increase it when long reinforcement elements must be visible.",
    "z query (m)": "Depth/elevation below the retained-side ground surface where local calculated quantities are queried.",
}

def _help_for(label: Any) -> str | None:
    text = str(label) if label is not None else ""
    if text in HELP_TEXTS:
        return HELP_TEXTS[text]
    for k, v in HELP_TEXTS.items():
        if k and (text.startswith(k) or k in text):
            return v
    return None

# Add help tooltips consistently and keep labels visible. A few earlier versions
# used label_visibility="collapsed" for compactness, but this hid titles on the
# Streamlit interface when the window was narrow.
_orig_number_input = st.number_input
_orig_selectbox = st.selectbox
_orig_checkbox = st.checkbox
_orig_text_input = st.text_input
_orig_radio = st.radio
_orig_button = st.button

def _with_help_kwargs(label, kwargs):
    if kwargs.get("help") is None:
        h = _help_for(label)
        if h:
            kwargs["help"] = h
    # Respect intentional collapsed labels in compact table-like rows.
    return kwargs

def _number_input_with_help(label, *args, **kwargs):
    return _orig_number_input(label, *args, **_with_help_kwargs(label, kwargs))

def _selectbox_with_help(label, *args, **kwargs):
    return _orig_selectbox(label, *args, **_with_help_kwargs(label, kwargs))

def _checkbox_with_help(label, *args, **kwargs):
    return _orig_checkbox(label, *args, **_with_help_kwargs(label, kwargs))

def _text_input_with_help(label, *args, **kwargs):
    return _orig_text_input(label, *args, **_with_help_kwargs(label, kwargs))

def _radio_with_help(label, *args, **kwargs):
    return _orig_radio(label, *args, **_with_help_kwargs(label, kwargs))

def _button_with_help(label, *args, **kwargs):
    return _orig_button(label, *args, **_with_help_kwargs(label, kwargs))

st.number_input = _number_input_with_help
st.selectbox = _selectbox_with_help
st.checkbox = _checkbox_with_help
st.text_input = _text_input_with_help
st.radio = _radio_with_help
st.button = _button_with_help

def img_uri(path: Path) -> str:
    try:
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        ext = path.suffix.lower().lstrip(".") or "png"
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        return f"data:image/{mime};base64,{data}"
    except Exception:
        return ""



PERSISTENT_INPUT_KEYS = {
    "beta_L",
    "beta_R",
    "q_L",
    "q_R",
    "z_w_L",
    "z_w_R",
    "gamma_w",
    "k_h",
    "k_v",
    "dx_trans",
    "theta_rot",
    "z_pivot",
    "EI",
    "E",
    "I_or_t",
    "stiffness_type",
    "stiffness_type_select",
    "N",
    "dz",
    "n_points",
    "tol",
    "integration_method",
    "no_bending_mode",
    "rigid_optimization_solver",
    "equilibrium_force_tol",
    "equilibrium_moment_tol",
    "work_band_tol",
    "general_case_bending_schemes",
    "general_case_theta_refine_passes",
    "general_case_theta_points",
    "general_case_zp_points",
    "general_case_pivot_margin_frac",
    "general_case_parallel",
    "general_case_max_workers",
    "query_z",
    "water_anim_plot_type",
    "water_anim_mode",
    "water_anim_steps",
    "water_anim_z_final_left",
    "water_anim_z_final_right",
    "water_anim_speed_ms",
    "water_anim_x_min",
    "water_anim_x_max",
    "ui_water_anim_x_min",
    "ui_water_anim_x_max",
    "water_anim_auto_x_pending",
    "water_anim_results",
    "n_excavation_stages",
    "intermediate_stage_drops",
    "stages_df",
    "stage_anim_plot_type",
    "stage_anim_speed_ms",
    "stage_anim_x_min",
    "stage_anim_x_max",
    "ui_stage_anim_x_min",
    "ui_stage_anim_x_max",
    "stage_anim_auto_x_pending",
    "stage_anim_results",
    "water_anim_summary",
    "water_anim_levels",
    "last_model",
    "last_result",
    "run_message",
}


def preserve_persistent_inputs() -> None:
    """Prevent Streamlit from deleting widget state across pages.

    This must be called only before widgets are rendered.
    """
    for key in list(PERSISTENT_INPUT_KEYS):
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]


def request_active_page(page: str) -> None:
    """Request navigation safely after the page selector widget exists."""
    if page in PAGES:
        st.session_state["_pending_active_page"] = page


def apply_pending_active_page() -> None:
    """Apply deferred navigation before any widget using active_page is created."""
    pending = st.session_state.pop("_pending_active_page", None)
    if pending in PAGES:
        st.session_state.active_page = pending
        # Safe here: this function runs near the top of the script, before
        # the central selectbox with key active_page_selector is instantiated.
        st.session_state.active_page_selector = pending


def init_state() -> None:
    defaults = {
        "active_page": "Model inputs",
        "n_excavation_stages": 1,
        "intermediate_stage_drops": 0,
    "stage_q_L_apply": "Stage N+1 (after final)",
    "stage_q_R_apply": "Stage 0",
        "stages_df": None,
        "stage_anim_plot_type": "Total horizontal pressure",
        "stage_anim_speed_ms": 650,
        "stage_anim_x_min": None,
        "stage_anim_x_max": None,
        "stage_anim_auto_x_pending": False,
        "stage_anim_results": [],
        "solver_display": "Flexible wall - Fixed base (closed-form bending)",
        "reinforcement_type": "No reinforcement",
        "beta_L": 0.0, "beta_R": 0.0, "q_L": 0.0, "q_R": 0.0,
        "z_w_L": 20.0, "z_w_R": 20.0, "gamma_w": 9.81,
        "k_h": 0.0, "k_v": 0.0,
        "stiffness_type": "EI", "EI": 1500000, "E": 1000000, "I_or_t": 1.5,
        "dx_trans": 0.0, "theta_rot": 0.0, "z_pivot": 4.0,
        "dz": 0.05, "n_points": 401, "N": 30, "tol": 1.0e-8,
        "integration_method": "Gauss", "no_bending_mode": "Auto (ΣF=0 & ΣM=0)",
        "rigid_optimization_solver": "Fast equilibrium only",
        "equilibrium_force_tol": 0.05, "equilibrium_moment_tol": 0.05, "work_band_tol": 0.05,
        "general_case_bending_schemes": 10, "general_case_theta_refine_passes": 5,
        "general_case_theta_points": 41, "general_case_zp_points": 17,
        "general_case_pivot_margin_frac": 0.02, "general_case_parallel": False, "general_case_max_workers": 0,
        "query_z": 2.0,
        "water_anim_plot_type": "Total horizontal pressure",
        "water_anim_mode": "Uniform rise",
        "water_anim_steps": 15,
        "water_anim_z_final_left": None,
        "water_anim_z_final_right": None,
        "water_anim_speed_ms": 650,
        "water_anim_x_min": None,
        "water_anim_x_max": None,
        "water_anim_auto_x_pending": False,
        "water_anim_results": [],
        "water_anim_summary": [],
        "water_anim_levels": [],
        "last_model": None, "last_result": None, "run_message": "Ready. Select a solver and run.",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    st.session_state.setdefault("left_layers_df", default_layer_df("SL", 6.0))
    st.session_state.setdefault("right_layers_df", default_layer_df("SR", 10.0))
    st.session_state.setdefault("reinf_dfs", {})



def sanitize_state() -> None:
    # Practical Streamlit defaults: keep plots smooth and avoid microscopic tolerances/steps from previous sessions.
    try:
        if float(st.session_state.get("dz", 0.05)) < 0.005:
            st.session_state.dz = 0.05
    except Exception:
        st.session_state.dz = 0.05
    try:
        if int(st.session_state.get("n_points", 401)) < 101:
            st.session_state.n_points = 401
    except Exception:
        st.session_state.n_points = 401
    try:
        if float(st.session_state.get("tol", 1.0e-8)) < 1.0e-10:
            st.session_state.tol = 1.0e-8
    except Exception:
        st.session_state.tol = 1.0e-8

    # Repair stale invalid zero values from earlier sessions.
    positive_defaults = {
        "gamma_w": 9.81,
        "EI": 1500000.0,
        "E": 1000000.0,
        "I_or_t": 1.5,
        "z_pivot": 4.0,
        "z_w_L": 20.0,
        "z_w_R": 20.0,
    }

    for key, default in positive_defaults.items():
        try:
            if abs(float(st.session_state.get(key, default))) <= 1.0e-15:
                st.session_state[key] = default
        except Exception:
            st.session_state[key] = default

def default_layer_df(prefix: str, h: float = 1.0, n: int = 1) -> pd.DataFrame:
    return pd.DataFrame([
        {"code": f"{prefix}{i+1}", "h (m)": h if i == 0 else 1.0, "c′ (kPa)": 0.001, "φ′ (°)": 30.0, "γ (kN/m³)": 20.0, "γsat (kN/m³)": 20.0, "E (kPa)": 20000.0, "ν (-)": 0.30}
        for i in range(n)
    ])

def handle_selector_query_params() -> None:
    selector_specs = [
        ("reinforcement_type", "Stages and reinforcement", REINFORCEMENT_CARDS),
        ("solver_display", "Run & solver monitor", SOLVER_CARDS),
    ]

    for state_key, target_page, cards in selector_specs:
        query_key = f"select_{state_key}"

        try:
            selected = st.query_params.get(query_key)
        except Exception:
            selected = None

        if isinstance(selected, list):
            selected = selected[0] if selected else None

        valid_values = {value for _, value, _ in cards}

        if selected in valid_values:
            st.session_state[state_key] = selected
            st.session_state.active_page = target_page

            if state_key == "reinforcement_type" and selected != "No reinforcement":
                st.session_state.solver_display = REINFORCEMENT_REQUIRED_SOLVER

            try:
                del st.query_params[query_key]
            except Exception:
                pass
                
def normalize_layer_df(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    cols = ["code", "h (m)", "c′ (kPa)", "φ′ (°)", "γ (kN/m³)", "γsat (kN/m³)", "E (kPa)", "ν (-)"]
    defaults = {"h (m)": 1.0, "c′ (kPa)": 0.001, "φ′ (°)": 30.0, "γ (kN/m³)": 20.0, "γsat (kN/m³)": 20.0, "E (kPa)": 20000.0, "ν (-)": 0.30}
    out = pd.DataFrame(df).copy()
    for c in cols:
        if c not in out:
            out[c] = defaults.get(c, "")
    out = out[cols].dropna(how="all").reset_index(drop=True)
    if out.empty:
        out = default_layer_df(prefix, 1.0)
    for i in range(len(out)):
        if not str(out.loc[i, "code"]).strip() or str(out.loc[i, "code"]).lower() == "nan":
            out.loc[i, "code"] = f"{prefix}{i+1}"
    for c, v in defaults.items():
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(v)
    out["h (m)"] = out["h (m)"].clip(lower=0.0)
    out["c′ (kPa)"] = out["c′ (kPa)"].clip(lower=0.001)
    out["E (kPa)"] = out["E (kPa)"].clip(lower=1.0e-12)
    return out

def enforce_unique_codes(df, prefix):
    df = df.copy()
    for i in range(len(df)):
        df.loc[i, "code"] = f"{prefix}{i+1}"
    return df

def material_id(row):
    return (
        round(float(row["c′ (kPa)"]), 3),
        round(float(row["φ′ (°)"]), 2),
        round(float(row["γ (kN/m³)"]), 2),
        round(float(row["γsat (kN/m³)"]), 2),
    )

def material_color_map(df):
    mats = [material_id(row) for _, row in df.iterrows()]
    unique_mats = list(dict.fromkeys(mats))  # preserve order

    cmap = cm.get_cmap("tab20", len(unique_mats))

    return {
        m: cmap(i)
        for i, m in enumerate(unique_mats)
    }
    
def height_from_df(df: pd.DataFrame) -> float:
    try:
        return float(pd.to_numeric(df["h (m)"], errors="coerce").fillna(0.0).clip(lower=0.0).sum())
    except Exception:
        return 0.0


def layers_from_df(df: pd.DataFrame) -> list[Any]:
    layers = []
    for i, row in normalize_layer_df(df, "S").reset_index(drop=True).iterrows():
        h = float(row.get("h (m)", 0.0) or 0.0)
        if h <= 0:
            continue
        layers.append(solvers.SoilLayer(
            code=str(row.get("code", f"S{i+1}")), thickness=h,
            c_prime=max(0.001, float(row.get("c′ (kPa)", 0.001) or 0.001)),
            phi_prime_deg=float(row.get("φ′ (°)", 30.0) or 30.0),
            gamma=float(row.get("γ (kN/m³)", 18.0) or 18.0),
            gamma_sat=float(row.get("γsat (kN/m³)", 20.0) or 20.0),
            E_s=max(1.0e-12, float(row.get("E (kPa)", 20000.0) or 20000.0)),
            nu=float(row.get("ν (-)", 0.30) or 0.30),
        ))
    return layers


def default_reinf_df(rtype: str) -> pd.DataFrame:
    if rtype == "Anchored embedded wall":
        return pd.DataFrame([{"code":"A1","z (m)":1.0,"θ (°)":-15.0,"Lf (m)":6.0,"Lb (m)":4.0,"EA (kN)":200000.0,"s (m)":2.0,"T0 (kN)":0.0,"Tpo (kN)":500.0,"Ts (kN)":500.0}])
    if rtype == "Propped embedded wall":
        return pd.DataFrame([{"code":"P1","z (m)":1.0,"L (m)":4.0,"EA (kN)":200000.0,"s (m)":2.0,"Rult (kN)":500.0}])
    if rtype == "MSE walls, geogrid reinforced":
        return pd.DataFrame([{"code":"R1","z (m)":1.0,"L (m)":5.0,"J/EA (kN/m)":1000.0,"Tult (kN/m)":50.0}])
    if rtype in ("MSE walls, metal strip reinforced", "MSE walls, metal grid reinforced"):
        return pd.DataFrame([{"code":"R1","z (m)":1.0,"L (m)":5.0,"s_h (m)":1.0,"EA (kN)":1000.0,"Tult (kN)":50.0}])
    return pd.DataFrame()


def normalize_reinf_df(df: pd.DataFrame, rtype: str) -> pd.DataFrame:
    base = default_reinf_df(rtype)
    if rtype == "No reinforcement":
        return pd.DataFrame()
    cols = list(base.columns)
    out = pd.DataFrame(df).copy()
    for c in cols:
        if c not in out:
            out[c] = base.iloc[0][c]
    out = out[cols].dropna(how="all").reset_index(drop=True)
    if out.empty:
        out = base.copy()
    prefix = "A" if rtype == "Anchored embedded wall" else ("P" if rtype == "Propped embedded wall" else "R")
    for i in range(len(out)):
        if not str(out.loc[i, "code"]).strip() or str(out.loc[i, "code"]).lower() == "nan":
            out.loc[i, "code"] = f"{prefix}{i+1}"
    for c in cols:
        if c != "code":
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(float(base.iloc[0][c]))
            if not (rtype == "Anchored embedded wall" and c == "θ (°)"):
                out[c] = out[c].clip(lower=0.0)
    return out


def get_reinf_df(rtype: str) -> pd.DataFrame:
    if rtype not in st.session_state.reinf_dfs:
        st.session_state.reinf_dfs[rtype] = default_reinf_df(rtype)
    return normalize_reinf_df(st.session_state.reinf_dfs[rtype], rtype)


def auto_mse_sv(rows: list[dict[str, Any]]) -> dict[int, float]:
    indexed = []
    for idx, row in enumerate(rows):
        try:
            indexed.append((float(row.get("z (m)", 0.0) or 0.0), idx))
        except Exception:
            indexed.append((0.0, idx))
    if not indexed:
        return {}
    indexed.sort(key=lambda t: t[0])
    if len(indexed) == 1:
        return {indexed[0][1]: 1.0}
    out = {}
    for pos, (z, idx) in enumerate(indexed):
        if pos == 0:
            sv = abs(indexed[1][0] - z)
        elif pos == len(indexed) - 1:
            sv = abs(z - indexed[pos-1][0])
        else:
            sv = 0.5 * abs(indexed[pos+1][0] - indexed[pos-1][0])
        out[idx] = max(float(sv), 1.0e-12)
    return out


def reinforcement_supports() -> list[dict[str, Any]]:
    rtype = st.session_state.reinforcement_type
    if rtype == "No reinforcement":
        return []
    df = get_reinf_df(rtype)
    rows = df.fillna(0).to_dict("records")
    supports = []
    if rtype == "Propped embedded wall":
        for r in rows:
            spacing = max(float(r.get("s (m)", 1.0) or 1.0), 1e-12)
            L = max(float(r.get("L (m)", 0.0) or 0.0), 1e-12)
            EA = float(r.get("EA (kN)", 0.0) or 0.0)
            Rult = float(r.get("Rult (kN)", 0.0) or 0.0)
            supports.append({"type":"prop","code":str(r.get("code","P")),"z":float(r.get("z (m)",0.0) or 0.0),"theta_deg":0.0,"L":L,"EA":EA,"spacing":spacing,"k":EA/(L*spacing),"cap":Rult/spacing})
    elif rtype.startswith("MSE walls"):
        sv_map = auto_mse_sv(rows)
        for i, r in enumerate(rows):
            if rtype == "MSE walls, geogrid reinforced":
                sh = 1.0; EA = float(r.get("J/EA (kN/m)", 0.0) or 0.0); cap = float(r.get("Tult (kN/m)", 0.0) or 0.0)
            else:
                sh = max(float(r.get("s_h (m)", 1.0) or 1.0), 1e-12); EA = float(r.get("EA (kN)", 0.0) or 0.0); cap = float(r.get("Tult (kN)", 0.0) or 0.0) / sh
            supports.append({"type":"mse","code":str(r.get("code","R")),"z":float(r.get("z (m)",0.0) or 0.0),"theta_deg":0.0,"L":float(r.get("L (m)",0.0) or 0.0),"Sv":sv_map.get(i,1.0),"spacing":sh,"k":EA/sh,"cap":cap})
    elif rtype == "Anchored embedded wall":
        for r in rows:
            spacing = max(float(r.get("s (m)", 1.0) or 1.0), 1e-12)
            Lf = max(float(r.get("Lf (m)", 0.0) or 0.0), 1e-12)
            Lb = max(float(r.get("Lb (m)", 0.0) or 0.0), 0.0)
            EA = float(r.get("EA (kN)", 0.0) or 0.0)
            cap = min(
                float(r.get("Tpo (kN)", 0.0) or 0.0),
                float(r.get("Ts (kN)", 0.0) or 0.0)
            ) / spacing

            supports.append({
                "type": "anchor",
                "code": str(r.get("code", "A")),
                "z": float(r.get("z (m)", 0.0) or 0.0),
                "theta_deg": float(r.get("θ (°)", 0.0) or 0.0),
                "Lf": Lf,
                "Lb": Lb,
                "L": Lf + Lb,
                "k": EA / Lf / spacing,
                "cap": cap,
                "prestress": float(r.get("T0 (kN)", 0.0) or 0.0) / spacing,
            })
    return supports


init_state()
sanitize_state()
apply_pending_active_page()
preserve_persistent_inputs()



def enforce_solver_rule():
    if st.session_state.reinforcement_type != "No reinforcement":
        if st.session_state.solver_display not in REINFORCEMENT_ALLOWED_SOLVERS:
            st.session_state.solver_display = REINFORCEMENT_REQUIRED_SOLVER
            st.warning("Solver automatically switched to a differential method due to reinforcement.")


def build_model() -> Any:
    enforce_solver_rule()
    repair_core_numeric_defaults()
    left_layers = layers_from_df(st.session_state.left_layers_df)
    right_layers = layers_from_df(st.session_state.right_layers_df)
    H_L = sum(float(l.thickness) for l in left_layers)
    H_R = sum(float(l.thickness) for l in right_layers)
    z_exc = H_R - H_L
    mode = solvers.SOLVER_DISPLAY_NAMES.get(st.session_state.solver_display, "general_case")
    controls = solvers.SolverControls(
        dz=float(st.session_state.dz), n_points=max(101, int(st.session_state.n_points)), max_iterations=max(1, int(st.session_state.N)), tolerance=float(st.session_state.tol),
        integration_method=str(st.session_state.integration_method), no_bending_mode=str(st.session_state.no_bending_mode), rigid_optimization_solver=str(st.session_state.rigid_optimization_solver),
        equilibrium_force_tol=float(st.session_state.equilibrium_force_tol), equilibrium_moment_tol=float(st.session_state.equilibrium_moment_tol), work_band_tol=float(st.session_state.work_band_tol),
        general_case_bending_schemes=max(2, int(st.session_state.general_case_bending_schemes)), general_case_theta_refine_passes=max(0, int(st.session_state.general_case_theta_refine_passes)),
        general_case_theta_points=max(5, int(st.session_state.general_case_theta_points)), general_case_zp_points=max(5, int(st.session_state.general_case_zp_points)),
        general_case_pivot_margin_frac=max(0.0, min(0.20, float(st.session_state.general_case_pivot_margin_frac))), general_case_parallel=bool(st.session_state.general_case_parallel), general_case_max_workers=max(0, int(st.session_state.general_case_max_workers)),
    )
    if H_L <= 0 or H_R <= 0:
        st.error("Both sides must have positive height")
        st.stop()

    if st.session_state.stiffness_type == "EI" and st.session_state.EI <= 0:
        st.error("EI must be positive")
        st.stop()
    return solvers.ModelInput(
        geometry=solvers.GeometryInput(H_R=H_R, H_L=H_L, z_p=float(st.session_state.z_pivot)),
        left=solvers.SideInput(beta_deg=float(st.session_state.beta_L), q=float(st.session_state.q_L), z_w=max(float(st.session_state.z_w_L), z_exc)),
        right=solvers.SideInput(beta_deg=float(st.session_state.beta_R), q=float(st.session_state.q_R), z_w=float(st.session_state.z_w_R)),
        seismic=solvers.SeismicInput(k_h=max(0.0, float(st.session_state.k_h)), k_v=float(st.session_state.k_v)),
        movement=solvers.MovementInput(dx_trans=float(st.session_state.dx_trans), theta_rot_deg=float(st.session_state.theta_rot), z_pivot=float(st.session_state.z_pivot)),
        wall=solvers.WallStiffnessInput(stiffness_type=str(st.session_state.stiffness_type), EI=float(st.session_state.EI), E=float(st.session_state.E), I_or_t=float(st.session_state.I_or_t)),
        controls=controls, gamma_w=float(st.session_state.gamma_w), left_layers=left_layers, right_layers=right_layers, reinforcement_supports=reinforcement_supports(), solver_mode=mode,
    )


def image_selector(cards: list[tuple[str, str, str]], state_key: str, target_page: str, columns: int) -> None:
    """Clickable icon-card selector using a CSS grid so mobile layouts stay controlled.

    Desktop keeps the intended single-row layout.  On phones the CSS below forces:
    - reinforcement: 3 columns x 2 rows
    - solver: 2 cards on the first row and 3 cards on the second row
    """
    query_key = f"select_{state_key}"
    grid_kind = "solver" if state_key == "solver_display" else "reinf"

    items = []
    for icon, value, label in cards:
        selected = (st.session_state.get(state_key) == value)
        card_class = "img-card selected" if selected else "img-card"
        src = img_uri(asset_path("assets", "icons", f"{icon}.png"))
        href = f"?{query_key}={quote(value)}"
        items.append(
            f'<a class="{card_class}" href="{href}" target="_self" title="{label}">'
            f'<img src="{src}" alt="{label}"><span>{label}</span></a>'
        )

    st.markdown(
        f'<div class="img-grid {grid_kind}">' + "".join(items) + "</div>",
        unsafe_allow_html=True,
    )

def result_dataframe(result: Any) -> pd.DataFrame:
    if result is None:
        return pd.DataFrame()
    z = list(getattr(result, "z", []) or []); n = len(z)
    def arr(name, default=0.0):
        v = list(getattr(result, name, []) or [])
        return (v + [default]*n)[:n]
    return pd.DataFrame({
        "z (m)": z,
        "p_L total (kPa)": arr("p_left"), "p_R total (kPa)": arr("p_right"), "p_net (kPa)": arr("net_pressure"),
        "σ'_h,L (kPa)": arr("sigma_left_eff"), "σ'_h,R (kPa)": arr("sigma_right_eff"), "u_L (kPa)": arr("u_left"), "u_R (kPa)": arr("u_right"),
        "K_L (-)": arr("K_left"), "K_R (-)": arr("K_right"), "m_L (-)": arr("m_left"), "m_R (-)": arr("m_right"),
        "Δxmax,A R (mm)": [1000*x for x in arr("dxmax_right_A")], "Δxmax,P L (mm)": [1000*x for x in arr("dxmax_left_P")],
        "V (kN/m)": arr("shear"), "M (kNm/m)": arr("moment"), "Δx (mm)": [1000*x for x in arr("deflection")], "θ (deg)": arr("rotation"),
    })



def format_results_for_display(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for c in out.columns:
        if c == "z (m)":
            out[c] = pd.to_numeric(out[c], errors="coerce").map(lambda x: f"{x:.3f}" if pd.notna(x) else "")
        elif pd.api.types.is_numeric_dtype(out[c]):
            out[c] = pd.to_numeric(out[c], errors="coerce").map(lambda x: f"{x:.5g}" if pd.notna(x) else "")
    return out

def interp_col(df: pd.DataFrame, col: str, zq: float) -> float:
    if df.empty or col not in df: return float("nan")
    z = df["z (m)"].astype(float).to_list(); y = df[col].astype(float).to_list()
    if not z: return float("nan")
    if zq <= z[0]: return y[0]
    if zq >= z[-1]: return y[-1]
    for i in range(1, len(z)):
        if z[i] >= zq:
            t = (zq-z[i-1])/(z[i]-z[i-1]) if z[i] != z[i-1] else 0.0
            return y[i-1] + t*(y[i]-y[i-1])
    return y[-1]


def _finite_xy(x_values, z_values):
    x_clean = []
    z_clean = []

    for x, z in zip(list(x_values or []), list(z_values or [])):
        try:
            xf = float(x)
            zf = float(z)
        except Exception:
            xf = float("nan")
            zf = float("nan")

        if math.isfinite(xf) and math.isfinite(zf):
            x_clean.append(xf)
            z_clean.append(zf)

    return x_clean, z_clean


def _auto_xlim(series_values, pad_frac: float = 0.12):
    vals = []

    for values in series_values:
        for v in list(values or []):
            try:
                vf = float(v)
            except Exception:
                continue
            if math.isfinite(vf):
                vals.append(vf)

    if not vals:
        return (-1.0, 1.0)

    vmin = min(vals + [0.0])
    vmax = max(vals + [0.0])

    if abs(vmax - vmin) < 1.0e-12:
        base = max(abs(vmin), abs(vmax), 1.0)
        return (-base, base)

    pad = pad_frac * (vmax - vmin)
    return (vmin - pad, vmax + pad)


def _series_style(label: str, index: int):
    """Desktop-like, restrained engineering plot styles."""
    lab = str(label).lower()

    # Calculated curves: strong black.
    if "rotation" in lab or lab in ("θ", "theta"):
        return {"color": "black", "linestyle": "-", "linewidth": 1.75}

    if "calculated" in lab or lab in ("δx", "p_net", "v", "m"):
        return {"color": "black", "linestyle": "-", "linewidth": 1.75}

    # Deflection limits: red dashed, as in the desktop program.
    if "δxmax" in lab or "dxmax" in lab:
        return {"color": "red", "linestyle": "--", "linewidth": 1.10}

    # Earth-pressure limits: restrained desktop palette.
    if "at-rest" in lab or "σoe" in lab or "oe" in lab:
        return {"color": "black", "linestyle": "--", "linewidth": 1.05}
    if "passive" in lab or "σpe" in lab or "pe" in lab:
        return {"color": "red", "linestyle": "--", "linewidth": 1.05}
    if "active" in lab or "σae" in lab or "ae" in lab:
        return {"color": "green", "linestyle": "--", "linewidth": 1.05}

    # Effective/water/K paired curves.
    if "δx/δxmax" in lab or "dx/dxmax" in lab or "Δx/Δxmax".lower() in lab:
        return {"color": "black", "linestyle": "-", "linewidth": 1.55}

    if "left" in lab:
        return {"color": "black", "linestyle": "--", "linewidth": 1.35}
    if "right" in lab:
        return {"color": "black", "linestyle": "-", "linewidth": 1.35}

    return {"color": "black", "linestyle": "-", "linewidth": 1.35}


def plot_profile(
    series: list[tuple[str, list[float]]],
    z: list[float],
    xlabel: str,
    title: str,
    zero_line: bool = True,
    shade: bool = False,
    vlines: list[tuple[float, str, str]] | None = None,
    shade_count: int | None = None,
    x_values_for_limits: list[float] | None = None,
):
    """Professional depth-profile chart used by the Streamlit plots tab.

    Convention:
    - z is positive downward.
    - Left-side quantities are passed as negative values when a mirrored diagram is required.
    - If shade=True and shade_count is given, only the first shade_count curves are shaded.
      This is used so calculated curves are shaded, while limit envelopes are not.
    """

    fig, ax = plt.subplots(figsize=(4.95, 4.75), dpi=145)

    fig.patch.set_facecolor("white")
    ax.set_facecolor("#f8fafc")

    clean_series = []

    for i, (label, values) in enumerate(series):
        x_clean, z_clean = _finite_xy(values, z)

        if not x_clean:
            continue

        clean_series.append((label, x_clean, z_clean))

        should_shade = bool(shade)
        if shade_count is not None:
            should_shade = should_shade and i < int(shade_count)

        if should_shade:
            ax.fill_betweenx(
                z_clean,
                0.0,
                x_clean,
                color="0.55",
                alpha=0.16,
                linewidth=0,
                zorder=2,
            )

        style = _series_style(label, i)

        ax.plot(
            x_clean,
            z_clean,
            label=label,
            zorder=6 if style["linewidth"] < 1.5 else 8,
            solid_capstyle="round",
            **style,
        )

    if zero_line:
        ax.axvline(
            0.0,
            linewidth=0.90,
            linestyle="-",
            color="0.35",
            alpha=0.70,
            zorder=4,
        )

    for item in vlines or []:
        try:
            x0, label, linestyle = item
            ax.axvline(
                float(x0),
                linewidth=1.0,
                linestyle=linestyle,
                color="red",
                alpha=0.70,
                label=label,
                zorder=5,
            )
        except Exception:
            pass

    if x_values_for_limits is None:
        all_x = [x for _, xs, _ in clean_series for x in xs]
    else:
        all_x = list(x_values_for_limits)

    xmin, xmax = _auto_xlim([all_x])
    ax.set_xlim(xmin, xmax)

    ax.set_title(
        title,
        fontsize=10.8,
        fontweight="bold",
        color="#172033",
        pad=7,
    )

    ax.set_xlabel(xlabel, fontsize=9.0, color="#334155")
    ax.set_ylabel("z (m)", fontsize=9.0, color="#334155")

    ax.invert_yaxis()

    ax.grid(True, which="major", linestyle="--", alpha=0.28, linewidth=0.65)
    ax.grid(True, which="minor", linestyle=":", alpha=0.10, linewidth=0.45)
    ax.minorticks_on()

    ax.tick_params(axis="both", labelsize=7.8, colors="#334155")

    ax.xaxis.set_major_locator(MaxNLocator(nbins=5, prune=None))
    ax.xaxis.set_minor_locator(MaxNLocator(nbins=10))

    formatter = ScalarFormatter(useMathText=True)
    formatter.set_powerlimits((-3, 4))
    ax.xaxis.set_major_formatter(formatter)
    ax.ticklabel_format(axis="x", style="sci", scilimits=(-3, 4))

    for tick in ax.get_xticklabels():
        tick.set_rotation(0)
        tick.set_horizontalalignment("center")

    ax.spines["top"].set_visible(True)
    ax.spines["right"].set_visible(True)
    for spine in ax.spines.values():
        spine.set_color("#8a96a3")
        spine.set_linewidth(0.70)

    if len(clean_series) > 1 or vlines:
        leg = ax.legend(
            fontsize=6.8,
            loc="best",
            frameon=True,
            fancybox=False,
            framealpha=0.86,
            borderpad=0.35,
            handlelength=2.2,
        )
        leg.get_frame().set_edgecolor("#cbd5e1")
        leg.get_frame().set_linewidth(0.65)

    fig.tight_layout()
    return fig


def _mask_side_surface_point(values, z_values, surface_z: float):
    """Remove the singular/free-surface value for one side only."""
    out = []

    for value, zz in zip(list(values or []), list(z_values or [])):
        try:
            zf = float(zz)
        except Exception:
            zf = float("nan")

        if math.isfinite(zf) and abs(zf - float(surface_z)) <= 1.0e-9:
            out.append(float("nan"))
        else:
            try:
                out.append(float(value))
            except Exception:
                out.append(float("nan"))

    return out


def _clip_for_plot(values, limit: float):
    """Clip extreme plotting values while preserving sign."""
    out = []

    for value in list(values or []):
        try:
            v = float(value)
        except Exception:
            out.append(float("nan"))
            continue

        if not math.isfinite(v):
            out.append(float("nan"))
        elif v > limit:
            out.append(limit)
        elif v < -limit:
            out.append(-limit)
        else:
            out.append(v)

    return out


def _robust_symmetric_limit(values, hard_limit: float = 10.0, percentile: float = 95.0):
    """Return a readable symmetric axis limit for diagrams with singular surface values."""
    vals = []

    for value in list(values or []):
        try:
            v = float(value)
        except Exception:
            continue

        if math.isfinite(v):
            vals.append(abs(v))

    if not vals:
        return hard_limit

    try:
        q = float(np.nanpercentile(vals, percentile))
    except Exception:
        q = max(vals)

    lim = max(1.0, min(hard_limit, 1.20 * q))

    return lim


def plot_convergence_profile(result: Any, quantity: str):
    """Return convergence chart.

    quantity:
    - "change": max iteration change / candidate work path
    - "abs_dx": maximum absolute deflection / candidate displacement path
    """

    fig, ax = plt.subplots(figsize=(4.65, 4.10), dpi=140)

    fig.patch.set_facecolor("white")
    ax.set_facecolor("#fbfdff")
    ax.grid(True, linestyle="--", alpha=0.24, linewidth=0.75)

    summary = dict(getattr(result, "summary", {}) or {})
    candidates = list(summary.get("general_case_solutions_table", []) or [])
    conv = list(getattr(result, "convergence_history", []) or [])

    plotted = False

    if candidates:
        try:
            rows = sorted(
                candidates,
                key=lambda r: float(r.get("load_factor", r.get("factor", 0.0)) or 0.0),
            )

            x = [
                float(r.get("load_factor", r.get("factor", i + 1)) or (i + 1))
                for i, r in enumerate(rows)
            ]

            if quantity == "change":
                y = [
                    float(
                        r.get(
                            "W_total_signed",
                            r.get("W_total", r.get("energy", 0.0)),
                        )
                        or 0.0
                    )
                    for r in rows
                ]
                title = "Convergence: Δchange"
                xlabel = "load / bending factor γ (-)"
                ylabel = "candidate work / change"
            else:
                y = [
                    1000.0
                    * abs(
                        float(
                            r.get(
                                "max_deflection_abs_m",
                                r.get("max_abs_deflection_m", r.get("dx_trans", 0.0)),
                            )
                            or 0.0
                        )
                    )
                    for r in rows
                ]
                title = "Convergence: abs(Δx)"
                xlabel = "load / bending factor γ (-)"
                ylabel = "max |Δx| (mm)"

            ax.plot(x, y, linewidth=2.0, marker="o", markersize=3.4)
            ax.fill_between(x, y, [0.0] * len(y), alpha=0.12)
            plotted = True
        except Exception:
            plotted = False

    if not plotted and conv:
        try:
            x = [
                int(r.get("iteration", i + 1) or (i + 1))
                for i, r in enumerate(conv)
            ]

            if quantity == "change":
                y = [
                    1000.0
                    * abs(
                        float(
                            r.get(
                                "max_change_m",
                                r.get("max_iteration_change_m", 0.0),
                            )
                            or 0.0
                        )
                    )
                    for r in conv
                ]
                title = "Convergence: Δchange"
                xlabel = "iteration"
                ylabel = "max Δchange (mm)"
            else:
                y = [
                    1000.0
                    * abs(
                        float(
                            r.get(
                                "max_abs_deflection_m",
                                r.get("max_deflection_abs_m", 0.0),
                            )
                            or 0.0
                        )
                    )
                    for r in conv
                ]
                title = "Convergence: abs(Δx)"
                xlabel = "iteration"
                ylabel = "max |Δx| (mm)"

            ax.plot(x, y, linewidth=2.0, marker="o", markersize=3.4)
            ax.fill_between(x, y, [0.0] * len(y), alpha=0.12)
            plotted = True
        except Exception:
            plotted = False

    if not plotted:
        title = "Convergence: Δchange" if quantity == "change" else "Convergence: abs(Δx)"
        xlabel = "iteration"
        ylabel = "value"
        ax.text(
            0.5,
            0.5,
            "No convergence history available",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=9,
            color="#64748b",
        )

    ax.set_title(title, fontsize=11.4, fontweight="bold", color="#172033", pad=8)
    ax.set_xlabel(xlabel, fontsize=9.2, color="#334155")
    ax.set_ylabel(ylabel, fontsize=9.2, color="#334155")
    ax.tick_params(axis="both", labelsize=8.0, colors="#334155")

    ax.xaxis.set_major_locator(MaxNLocator(nbins=6, prune=None))
    ax.xaxis.set_minor_locator(MaxNLocator(nbins=12))

    formatter = ScalarFormatter(useMathText=True)
    formatter.set_powerlimits((-3, 4))
    ax.xaxis.set_major_formatter(formatter)
    ax.ticklabel_format(axis="x", style="sci", scilimits=(-3, 4))

    for tick in ax.get_xticklabels():
        tick.set_rotation(0)
        tick.set_horizontalalignment("center")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")

    fig.tight_layout()
    return fig


def plot_geometry(model: Any):

    H_R = float(model.geometry.H_R)
    H_L = float(model.geometry.H_L)

    z_left = H_R - H_L

    beta_L = math.radians(float(st.session_state.beta_L))
    beta_R = math.radians(float(st.session_state.beta_R))

    qL = float(st.session_state.q_L)
    qR = float(st.session_state.q_R)

    xr = max(2.5, 0.40 * H_R)
    xl = -0.45 * xr

    fig, ax = plt.subplots(figsize=(8.5, 7.0), dpi=130)

    brown_palette = [
        "#d9c2a7",
        "#ccb08f",
        "#e4cfba",
        "#c79f74",
        "#b98d62",
    ]

    material_colors = {}

    def mat_id(row):
        return (
            round(float(row["c′ (kPa)"]), 2),
            round(float(row["φ′ (°)"]), 2),
            round(float(row["γ (kN/m³)"]), 2),
        )

    def get_color(row):
        m = mat_id(row)

        if m not in material_colors:
            material_colors[m] = brown_palette[
                len(material_colors) % len(brown_palette)
            ]

        return material_colors[m]

    # =====================================================
    # SURFACES
    # =====================================================

    def surfR(x):
        return -x * math.tan(beta_R)

    def surfL(x):
        return z_left + x * math.tan(beta_L)

    # =====================================================
    # RIGHT SIDE
    # =====================================================

    right_df = normalize_layer_df(
        st.session_state.right_layers_df,
        "SR"
    )

    z0 = 0.0

    for _, row in right_df.iterrows():

        h = float(row["h (m)"])

        z1 = z0 + h

        color = get_color(row)

        poly_x = [0, xr, xr, 0]
        poly_y = [
            surfR(0),
            surfR(xr),
            z1,
            z1
        ]

        ax.fill(
            poly_x,
            poly_y,
            color=color,
            ec="none",
            zorder=1
        )

        ax.text(
            xr * 0.52,
            0.5 * (z0 + z1),
            row["code"],
            ha="center",
            va="center",
            fontsize=9
        )

        z0 = z1

    # =====================================================
    # LEFT SIDE
    # =====================================================

    left_df = normalize_layer_df(
        st.session_state.left_layers_df,
        "SL"
    )

    z0 = z_left

    for _, row in left_df.iterrows():

        h = float(row["h (m)"])

        z1 = z0 + h

        color = get_color(row)

        poly_x = [xl, 0, 0, xl]
        poly_y = [
            surfL(xl),
            surfL(0),
            z1,
            z1
        ]

        ax.fill(
            poly_x,
            poly_y,
            color=color,
            ec="none",
            zorder=1
        )

        ax.text(
            xl * 0.50,
            0.5 * (z0 + z1),
            row["code"],
            ha="center",
            va="center",
            fontsize=9
        )

        z0 = z1

    # =====================================================
    # WALL
    # =====================================================

    ax.plot(
        [0, 0],
        [0, H_R],
        color="black",
        linewidth=2.4,
        zorder=5
    )

    # Layer interface lines - right side
    z_int = 0.0
    for _, row in right_df.iloc[:-1].iterrows():
        z_int += float(row["h (m)"])
        ax.plot(
            [0, xr],
            [z_int, z_int],
            color="0.45",
            linewidth=0.8,
            zorder=4
        )

    # Layer interface lines - left side
    z_int = z_left
    for _, row in left_df.iloc[:-1].iterrows():
        z_int += float(row["h (m)"])
        ax.plot(
            [xl, 0],
            [z_int, z_int],
            color="0.45",
            linewidth=0.8,
            zorder=4
        )
        
    # =====================================================
    # GROUND LINES
    # =====================================================

    ax.plot(
        [0, xr],
        [surfR(0), surfR(xr)],
        color="saddlebrown",
        linewidth=1.6,
        zorder=6
    )

    ax.plot(
        [xl, 0],
        [surfL(xl), surfL(0)],
        color="saddlebrown",
        linewidth=1.6,
        zorder=6
    )

    # =====================================================
    # WATER
    # =====================================================

    z_w_R = float(st.session_state.z_w_R)
    z_w_L = max(
        float(st.session_state.z_w_L),
        z_left
    )

    ax.plot(
        [0, xr],
        [z_w_R, z_w_R],
        "--",
        color="blue",
        linewidth=1.2
    )

    ax.plot(
        [xl, 0],
        [z_w_L, z_w_L],
        "--",
        color="blue",
        linewidth=1.2
    )

    # =====================================================
    # SURCHARGES
    # =====================================================

    if abs(qR) > 0:

        for x in [xr*0.25, xr*0.50, xr*0.75]:

            y = surfR(x)

            ax.annotate(
                "",
                xy=(x, y),
                xytext=(x, y - 0.7),
                arrowprops=dict(
                    arrowstyle="-|>",
                    lw=1.0,
                    color="#1f5f99"
                )
            )

        ax.text(
            xr * 0.5,
            surfR(xr*0.5) - 1.0,
            f"q_R = {qR:g} kPa",
            ha="center",
            fontsize=10,
            color="#1f5f99"
        )

    if abs(qL) > 0:

        for x in [xl*0.25, xl*0.50, xl*0.75]:

            y = surfL(x)

            ax.annotate(
                "",
                xy=(x, y),
                xytext=(x, y - 0.7),
                arrowprops=dict(
                    arrowstyle="-|>",
                    lw=1.0,
                    color="#b91c1c"
                )
            )

        ax.text(
            xl * 0.5,
            surfL(xl*0.5) - 1.0,
            f"q_L = {qL:g} kPa",
            ha="center",
            fontsize=10,
            color="#b91c1c"
        )

    # =====================================================
    # LABELS
    # =====================================================

    ax.text(
        xr * 0.55,
        0.4,
        "Right / retained",
        fontsize=8
    )

    ax.text(
        xl * 0.55,
        z_left + 0.4,
        "Left / excavation",
        fontsize=8
    )

    # =====================================================
    # AXES
    # =====================================================
    extra_headroom = 1.2 + 0.05 * st.session_state.beta_R
    ymin = min(
        surfR(xr),
        surfL(xl),
        -extra_headroom
    )

    ax.set_xlim(xl * 1.08, xr * 1.08)

    ax.set_ylim(ymin, H_R + 0.8)

    ax.invert_yaxis()

    ax.set_title(
        "Geometry / soil configuration",
        fontsize=16,
        fontweight="bold"
    )

    ax.set_xlabel("x (m, schematic)", fontsize=11)

    ax.set_ylabel("z (m)", fontsize=11)

    ax.grid(True, linestyle="--", alpha=0.18)

    fig.tight_layout()

    return fig


def interp_result_at_z(result: Any, field: str, zq: float) -> float:
    """Interpolate a result array at depth zq."""
    if result is None:
        return float("nan")

    z = list(getattr(result, "z", []) or [])
    y = list(getattr(result, field, []) or [])

    pairs = []
    for zz, yy in zip(z, y):
        try:
            zf = float(zz)
            yf = float(yy)
        except Exception:
            continue

        if math.isfinite(zf) and math.isfinite(yf):
            pairs.append((zf, yf))

    if not pairs:
        return float("nan")

    pairs.sort(key=lambda p: p[0])
    zs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    zq = float(zq)

    if zq <= zs[0]:
        return ys[0]

    if zq >= zs[-1]:
        return ys[-1]

    for i in range(1, len(zs)):
        if zs[i] >= zq:
            dz = zs[i] - zs[i - 1]
            t = 0.0 if abs(dz) <= 1.0e-15 else (zq - zs[i - 1]) / dz
            return ys[i - 1] + t * (ys[i] - ys[i - 1])

    return ys[-1]


def reported_support_force_map(result: Any) -> dict[str, float]:
    """Collect solver-reported support forces, if present."""
    if result is None:
        return {}

    candidates = []

    for attr in [
        "support_results",
        "supports_results",
        "reinforcement_results",
        "reinforcement_support_results",
        "support_forces",
    ]:
        value = getattr(result, attr, None)
        if isinstance(value, list) and value:
            candidates.extend(value)

    summary = dict(getattr(result, "summary", {}) or {})

    for key in [
        "support_results",
        "support_results_table",
        "reinforcement_results",
        "support_forces",
        "support_forces_table",
    ]:
        value = summary.get(key)
        if isinstance(value, list) and value:
            candidates.extend(value)

    out = {}

    for i, item in enumerate(candidates):
        if not isinstance(item, dict):
            continue

        code = str(item.get("code", item.get("id", f"S{i+1}")))

        for fkey in [
            "Fh",
            "force",
            "force_kN_per_m",
            "support_force_kN_per_m",
            "axial",
            "axial_force",
            "T",
            "reaction",
        ]:
            if fkey in item:
                try:
                    val = float(item.get(fkey))
                except Exception:
                    continue

                if math.isfinite(val):
                    out[code] = val
                    break

    return out


def estimate_support_force_from_model_result(support: dict[str, Any], result: Any) -> float:
    """Estimate support force per metre from stiffness and displacement.

    Used only when the solver result does not expose support reactions.
    """
    try:
        z = float(support.get("z", 0.0) or 0.0)
        k = float(support.get("k", 0.0) or 0.0)
        prestress = float(support.get("prestress", 0.0) or 0.0)
        cap = float(support.get("cap", 0.0) or 0.0)
    except Exception:
        return float("nan")

    dx = interp_result_at_z(result, "deflection", z)

    if not math.isfinite(dx):
        dx = 0.0

    force = prestress + k * abs(dx)

    if cap > 0.0:
        force = min(force, cap)

    return max(0.0, force)


def support_force_for_display(support: dict[str, Any], result: Any) -> float:
    code = str(support.get("code", ""))
    reported = reported_support_force_map(result)

    if code in reported:
        return reported[code]

    return estimate_support_force_from_model_result(support, result)


def plot_reinforcement(model: Any, result: Any = None):
    H_R = float(model.geometry.H_R)
    H_L = float(model.geometry.H_L)
    z_left = H_R - H_L

    supports = list(model.reinforcement_supports or [])

    max_L = max(
        [float(s.get("L", 0.0) or 0.0) for s in supports] + [0.40 * H_R, 2.5]
    )

    xr = max(2.5, max_L * 1.20, 0.45 * H_R)
    xl = -0.45 * max(2.5, 0.40 * H_R)

    fig, ax = plt.subplots(figsize=(8.5, 7.0), dpi=130)

    ax.fill_betweenx([0, H_R], 0, xr, color="#dbeafe", alpha=0.22)
    ax.fill_betweenx([z_left, H_R], xl, 0, color="#fecdd3", alpha=0.18)

    ax.plot([0, 0], [0, H_R], color="black", linewidth=2.0, zorder=5)
    ax.plot([0, xr], [0, 0], color="saddlebrown", linewidth=1.45, zorder=5)
    ax.plot([xl, 0], [z_left, z_left], color="saddlebrown", linewidth=1.45, zorder=5)

    if not supports:
        ax.text(
            0.50 * xr,
            0.50 * H_R,
            "No reinforcement",
            ha="center",
            va="center",
            fontsize=8
        )

    for s in supports:
        z = float(s.get("z", 0.0) or 0.0)
        code = str(s.get("code", ""))
        typ = str(s.get("type", ""))

        if typ == "prop":
            L = max(float(s.get("L", 0.0) or 0.0), 0.2 * xr)

            ax.plot([-L, 0], [z, z], color="darkorange", linewidth=1.8, zorder=7)
            ax.plot(0, z, "s", color="darkorange", markersize=4, zorder=8)
            force = support_force_for_display(s, result)
            force_label = f"{code}: {force:.3g} kN/m" if math.isfinite(force) else code
            ax.text(-L, z, force_label, ha="right", va="center", fontsize=7, color="darkorange")

        elif typ == "mse":
            L = max(float(s.get("L", 0.0) or 0.0), 0.1 * xr)

            ax.plot([0, L], [z, z], color="purple", linewidth=1.5, zorder=7)
            force = support_force_for_display(s, result)
            force_label = f"{code}: {force:.3g} kN/m" if math.isfinite(force) else code
            ax.text(0.5 * L, z, force_label, ha="center", va="bottom", fontsize=7, color="purple")

        elif typ == "anchor":
            theta = math.radians(float(s.get("theta_deg", 0.0) or 0.0))

            Lf = float(s.get("Lf", 0.0) or 0.0)
            Lb = float(s.get("Lb", 0.0) or 0.0)
            L = max(float(s.get("L", Lf + Lb) or 0.0), 1e-9)

            x_free = Lf * math.cos(theta)
            y_free = z - Lf * math.sin(theta)

            x_end = L * math.cos(theta)
            y_end = z - L * math.sin(theta)

            ax.plot([0, x_free], [z, y_free], color="#2563eb", linewidth=1.6, zorder=7)
            ax.plot([x_free, x_end], [y_free, y_end], color="#2563eb", linewidth=3.0, alpha=0.75, zorder=7)

            ax.plot(0, z, "o", color="#2563eb", markersize=4.5, zorder=8)
            ax.plot(x_free, y_free, "o", color="#2563eb", markersize=3.5, zorder=8)

            force = support_force_for_display(s, result)
            force_label = f"{code}: {force:.3g} kN/m" if math.isfinite(force) else code

            ax.text(
                x_end + 0.10,
                y_end,
                force_label,
                ha="left",
                va="center",
                fontsize=7,
                color="#2563eb"
            )

    ax.set_xlim(xl * 1.10, xr * 1.25)
    ax.set_ylim(H_R + 0.8, -0.8)

    ax.set_aspect("auto")
    ax.set_title("Reinforcement layout", fontweight="bold", fontsize=12)
    ax.set_xlabel("x (m, schematic)", fontsize=10)
    ax.set_ylabel("z (m)", fontsize=10)
    ax.tick_params(labelsize=8)
    ax.grid(True, linestyle="--", alpha=0.18)

    fig.tight_layout()
    return fig

def show_fig(fig, width: int = 420) -> None:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=135, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    st.image(buf.getvalue(), width=width)

def run_solver_now():
    # Final repair in case Run was clicked immediately after editing a number.
    repair_core_numeric_defaults()

    model = build_model()

    # Clear previous result before the new run, so plots/tables cannot show
    # stale/default results while a new model is being solved.
    st.session_state.last_model = model
    st.session_state.last_result = None

    progress = st.progress(0.0, text="Running solver...")

    def cb(info):
        try:
            progress.progress(
                max(0.0, min(1.0, float(info.get("fraction", 0.0)))),
                text=str(info.get("message", "running"))
            )
        except Exception:
            pass

    result = cached_solve(model)

    progress.progress(1.0, text="Completed")

    st.session_state.last_model = model
    st.session_state.last_result = result
    st.session_state.run_message = f"{result.status}: {result.message}"

    # Navigate after a successful run without touching the selectbox key after
    # it has been instantiated in this run.  The pending page is applied safely
    # at the top of the next rerun, before the widget is created.
    request_active_page("Plots")
    st.rerun()


def cached_solve(model):
    """Run solver with the current model.

    Not cached: engineering inputs must never be silently replaced by a
    previous/default run when Streamlit reruns the script.
    """
    return solvers.solve(model)
    

def _short(text: str, n: int = 42) -> str:
    text = str(text)
    return text if len(text) <= n else text[:n-1] + "…"


def stat_cards() -> None:
    left_h = height_from_df(st.session_state.left_layers_df); right_h = height_from_df(st.session_state.right_layers_df)
    vals = [
        ("H_L excavation side", f"{left_h:.4g} m"),
        ("H_R retained side", f"{right_h:.4g} m"),
        ("Solver", _short(st.session_state.solver_display.replace("Flexible wall - ", ""), 36)),
        ("Reinforcement", _short("None" if st.session_state.reinforcement_type == "No reinforcement" else st.session_state.reinforcement_type.replace("MSE walls, ", "MSE "), 36)),
        ("Status", _short(str(st.session_state.run_message).split(":")[0], 36)),
    ]
    html = ['<div class="stat-grid">']
    for lab, val in vals:
        html.append(f'<div class="stat"><div class="stat-label">{lab}</div><div class="stat-value">{val}</div></div>')
    html.append('</div>')
    st.markdown('\n'.join(html), unsafe_allow_html=True)

def render_header():
    home_img = img_uri(asset_path("home.png"))

    st.markdown(f"""
<div class="cut-hero"><div><h1>{APP_VERSION}</h1></div></div>
""", unsafe_allow_html=True)

    about_html = html.escape(about_text()).replace("\n", "<br>")
    st.markdown(
        f"""<div class="header-actions">
<a class="home-link" href="{HOME_URL}" target="_blank"><img src="{home_img}" alt="home">Home</a>
<details class="about-details"><summary>About⌄</summary><div>{about_html}</div></details>
</div>""",
        unsafe_allow_html=True,
    )

    stat_cards()

    # Compact navigation. Previous/Next are rendered as an HTML flex pair,
    # not as Streamlit columns, so they stay side-by-side on mobile. The
    # section dropdown remains below them.
    import urllib.parse as _cut_urlparse

    try:
        _qp_page = st.query_params.get("cut_page", None)
    except Exception:
        _qp_page = None
    if isinstance(_qp_page, list):
        _qp_page = _qp_page[0] if _qp_page else None

    # Previous/Next use the temporary URL parameter cut_page.
    # Consume it once, then remove it so the central dropdown can control
    # the page on the next rerun instead of being forced back by a stale URL.
    if _qp_page in PAGES:
        st.session_state.active_page = _qp_page
        st.session_state.active_page_selector = _qp_page
        try:
            del st.query_params["cut_page"]
        except Exception:
            pass

    try:
        current_idx = PAGES.index(st.session_state.get("active_page", PAGES[0]))
    except ValueError:
        current_idx = 0
        st.session_state.active_page = PAGES[0]

    # Initialize the selector once only. Do not overwrite it on every rerun,
    # because Streamlit has already stored the user's new dropdown choice
    # before this script reaches render_header().
    if st.session_state.get("active_page_selector") not in PAGES:
        st.session_state.active_page_selector = st.session_state.active_page

    _prev_disabled = current_idx == 0
    _next_disabled = current_idx >= len(PAGES) - 1
    _prev_page = PAGES[max(0, current_idx - 1)]
    _next_page = PAGES[min(len(PAGES) - 1, current_idx + 1)]

    # Previous/Next must be real Streamlit buttons, not HTML links.
    # HTML links reload the browser page and can lose in-memory solver results.
    # These buttons rerun Streamlit in the same session, so last_model/last_result
    # remain available when moving from Plots to Results, Summary, etc.
    st.markdown('<div class="cut-nav-streamlit-pair-start"></div>', unsafe_allow_html=True)
    nav_prev_col, nav_next_col = st.columns(2, gap="small")
    with nav_prev_col:
        if st.button("◀ Previous", key="cut_prev_page_btn", disabled=_prev_disabled, use_container_width=True):
            st.session_state.active_page = _prev_page
            st.session_state.active_page_selector = _prev_page
            st.rerun()
    with nav_next_col:
        if st.button("Next ▶", key="cut_next_page_btn", disabled=_next_disabled, use_container_width=True):
            st.session_state.active_page = _next_page
            st.session_state.active_page_selector = _next_page
            st.rerun()

    selected_page = st.selectbox(
        "Section",
        PAGES,
        index=current_idx,
        key="active_page_selector",
        label_visibility="collapsed",
    )
    if selected_page in PAGES and selected_page != st.session_state.get("active_page"):
        st.session_state.active_page = selected_page
        st.rerun()



    if st.session_state.reinforcement_type != "No reinforcement":
        st.markdown(
            '<div class="cut-warning">Reinforcement is active; the differential fixed-base solver is selected automatically, matching the desktop GUI rule.</div>',
            unsafe_allow_html=True
        )

def input_grid(labels_keys: list[tuple[str, str]], cols: int = 4):
    columns = st.columns(cols, gap="small")
    for i, (label, key) in enumerate(labels_keys):
        with columns[i % cols]:
            st.number_input(label, key=key, label_visibility="visible")



def _cut_editor_text_df(df, exclude_cols=None):
    """Return a copy whose editable TextColumn fields are strings.
    This avoids Streamlit type errors when TextColumn is used for numeric data,
    while write-back normalization still converts values to floats.
    """
    out = df.copy()
    exclude_cols = set(exclude_cols or [])
    for col in out.columns:
        if col not in exclude_cols:
            out[col] = out[col].map(lambda v: "" if pd.isna(v) else str(v))
    return out

def _layer_column_config(prefix: str):
    # Text columns are used intentionally so Streamlit does not right-align
    # numeric-looking values in the editor. Normalization below still converts
    # values back to floats.
    return {
        "code": st.column_config.TextColumn("code", default=f"{prefix}1", width="small"),
        "h (m)": st.column_config.TextColumn("h (m)", default="1.0", width="small"),
        "c′ (kPa)": st.column_config.TextColumn("c′ (kPa)", default="0.001", width="small"),
        "φ′ (°)": st.column_config.TextColumn("φ′ (°)", default="30.0", width="small"),
        "γ (kN/m³)": st.column_config.TextColumn("γ (kN/m³)", default="20.0", width="small"),
        "γsat (kN/m³)": st.column_config.TextColumn("γsat (kN/m³)", default="20.0", width="small"),
        "E (kPa)": st.column_config.TextColumn("E (kPa)", default="20000", width="medium"),
        "ν (-)": st.column_config.TextColumn("ν (-)", default="0.30", width="small"),
    }



CORE_NUMERIC_DEFAULTS = {
    "beta_L": 0.0,
    "beta_R": 0.0,
    "q_L": 0.0,
    "q_R": 0.0,
    "z_w_L": 20.0,
    "z_w_R": 20.0,
    "gamma_w": 9.81,
    "k_h": 0.0,
    "k_v": 0.0,
    "dx_trans": 0.0,
    "theta_rot": 0.0,
    "z_pivot": 4.0,
    "EI": 1500000.0,
    "E": 1000000.0,
    "I_or_t": 1.5,
}

POSITIVE_DEFAULT_KEYS = {
    "z_w_L",
    "z_w_R",
    "gamma_w",
    "z_pivot",
    "EI",
    "E",
    "I_or_t",
}



def repair_core_numeric_defaults() -> None:
    """Repair only invalid positive-only inputs.

    Do not use separate ui_* keys.  The actual Streamlit widget keys are the
    engineering keys, so values persist across tabs and reruns.
    """
    for key in POSITIVE_DEFAULT_KEYS:
        default = float(CORE_NUMERIC_DEFAULTS[key])
        try:
            value = float(st.session_state.get(key, default))
        except Exception:
            value = default

        if not math.isfinite(value) or abs(value) <= 1.0e-15:
            st.session_state[key] = default


def synced_number_input(label: str, key: str, default: float, **kwargs):
    """Direct, persistent number input for engineering variables."""
    if key not in st.session_state:
        st.session_state[key] = default

    if key in POSITIVE_DEFAULT_KEYS:
        try:
            value = float(st.session_state.get(key, default))
        except Exception:
            value = default

        if not math.isfinite(value) or abs(value) <= 1.0e-15:
            st.session_state[key] = default

    return st.number_input(
        label,
        key=key,
        label_visibility=kwargs.pop("label_visibility", "collapsed"),
        **kwargs
    )


repair_core_numeric_defaults()

handle_selector_query_params()



# v7.4 FIX9: replace fragile Streamlit-column pseudo-tables with native compact
# editable tables.  This CSS only tightens data-editor spacing and does not
# affect the solver/backend.
st.markdown(
    """
<style>
/* Compact native data-editor tables used for Model inputs. */
div[data-testid="stDataFrame"]{
    margin-top:.15rem!important;
    margin-bottom:.65rem!important;
}
div[data-testid="stDataFrame"] [role="gridcell"],
div[data-testid="stDataFrame"] [role="columnheader"]{
    font-size:.78rem!important;
}
@media(max-width:900px){
    div[data-testid="stDataFrame"]{
        max-width:100%!important;
        overflow-x:auto!important;
        -webkit-overflow-scrolling:touch!important;
    }
    div[data-testid="stExpander"] details > div{
        padding:.85rem .65rem .55rem .65rem!important;
    }
    h4{
        margin-top:.55rem!important;
        margin-bottom:.25rem!important;
        font-size:1.05rem!important;
    }
}
</style>
""",
    unsafe_allow_html=True,
)



# v7.4 FIX11: enforce left alignment for every Streamlit table/dataframe/editor
# and keep the navigation/action buttons in the same elegant blue palette.
st.markdown(
    """
<style>
/* ---------------- All tables: left aligned cells everywhere ---------------- */
div[data-testid="stDataFrame"],
div[data-testid="stDataFrame"] *{
    text-align:left!important;
}
div[data-testid="stDataFrame"] [role="grid"],
div[data-testid="stDataFrame"] [role="row"],
div[data-testid="stDataFrame"] [role="gridcell"],
div[data-testid="stDataFrame"] [role="columnheader"],
div[data-testid="stDataFrame"] [data-testid="glide-cell"],
div[data-testid="stDataFrame"] [data-testid="stDataFrameCell"]{
    text-align:left!important;
    justify-content:flex-start!important;
    align-items:center!important;
}
div[data-testid="stDataFrame"] [role="gridcell"] > div,
div[data-testid="stDataFrame"] [role="columnheader"] > div{
    text-align:left!important;
    justify-content:flex-start!important;
    margin-left:0!important;
}
[data-testid="stTable"] table,
[data-testid="stTable"] th,
[data-testid="stTable"] td{
    text-align:left!important;
}
/* Keep ordinary input text left aligned too. */
div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea{
    text-align:left!important;
}

/* ---------------- Elegant common button palette ---------------- */
button[kind="secondary"],
button[data-testid="baseButton-secondary"]{
    background:linear-gradient(180deg,#edf6ff 0%,#e3effb 100%)!important;
    border:1px solid #9fbfe2!important;
    color:#1f334d!important;
    border-radius:13px!important;
    box-shadow:0 2px 8px rgba(31,95,153,.08)!important;
    font-weight:650!important;
}
button[kind="secondary"]:hover,
button[data-testid="baseButton-secondary"]:hover{
    background:linear-gradient(180deg,#e2f0ff 0%,#d4e7fb 100%)!important;
    border-color:#6f9ecc!important;
    box-shadow:0 4px 12px rgba(31,95,153,.14)!important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
    background:linear-gradient(180deg,#edf6ff 0%,#e3effb 100%)!important;
    border:1px solid #9fbfe2!important;
    color:#1f334d!important;
    border-radius:13px!important;
}
.header-actions .home-link,
.about-details summary{
    width:132px!important;
    min-width:132px!important;
    max-width:132px!important;
    background:linear-gradient(180deg,#edf6ff 0%,#e3effb 100%)!important;
    border:1px solid #9fbfe2!important;
    color:#12355b!important;
    border-radius:13px!important;
    box-shadow:0 2px 8px rgba(31,95,153,.08)!important;
    font-weight:750!important;
}
.header-actions .home-link:hover,
.about-details summary:hover{
    background:linear-gradient(180deg,#e2f0ff 0%,#d4e7fb 100%)!important;
    border-color:#6f9ecc!important;
}
</style>
""",
    unsafe_allow_html=True,
)


# v7.4 FIX12: surgical spacing for Stages and reinforcement mobile controls.
# The earlier compact-number-input CSS pulls number inputs upward globally; these
# overrides give the visible labels in the excavation-staging panel enough real
# vertical space so labels cannot collide with the input boxes.
st.markdown(
    """
<style>
.cut-stage-heading{
    font-size:1.38rem;
    font-weight:760;
    line-height:1.15;
    color:#2b3042;
    margin:1.25rem 0 .80rem 0;
}
.cut-stage-subheading{
    font-size:1.12rem;
    font-weight:750;
    line-height:1.18;
    color:#2b3042;
    margin:1.35rem 0 .75rem 0;
}
.cut-visible-field-label{
    display:block!important;
    margin:.95rem 0 .62rem 0!important;
    min-height:1.20rem!important;
    line-height:1.25!important;
}
@media(max-width:900px){
    .cut-stage-heading{
        font-size:1.38rem!important;
        margin:1.25rem 0 .85rem 0!important;
    }
    .cut-stage-subheading{
        font-size:1.10rem!important;
        margin:1.35rem 0 .80rem 0!important;
    }
    .cut-visible-field-label{
        margin:1.05rem 0 .70rem 0!important;
        min-height:1.30rem!important;
        line-height:1.25!important;
    }
}
</style>
""",
    unsafe_allow_html=True,
)


def _cut_fmt(value: Any, fmt: str = "{:.2f}") -> str:
    try:
        return fmt.format(float(value))
    except Exception:
        return str(value)

def _cut_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        text = str(value).strip().replace(",", ".")
        if text == "":
            return default
        return float(text)
    except Exception:
        return default

def sync_model_input_editors(force: bool = False) -> None:
    H_L = height_from_df(st.session_state.left_layers_df)
    H_R = height_from_df(st.session_state.right_layers_df)

    input_df = pd.DataFrame({
        "Parameter": ["H (m)", "β (deg)", "q (kPa)", "z_w (m)"],
        "Left / excavation": [
            _cut_fmt(H_L),
            _cut_fmt(st.session_state.get("beta_L", 0.0)),
            _cut_fmt(st.session_state.get("q_L", 0.0)),
            _cut_fmt(st.session_state.get("z_w_L", 20.0)),
        ],
        "Right / retained": [
            _cut_fmt(H_R),
            _cut_fmt(st.session_state.get("beta_R", 0.0)),
            _cut_fmt(st.session_state.get("q_R", 0.0)),
            _cut_fmt(st.session_state.get("z_w_R", 20.0)),
        ],
    })

    global_df = pd.DataFrame({
        "γ_w (kN/m³)": [_cut_fmt(st.session_state.get("gamma_w", 9.81))],
        "k_h (-)": [_cut_fmt(st.session_state.get("k_h", 0.0), "{:.3g}")],
        "k_v (-)": [_cut_fmt(st.session_state.get("k_v", 0.0), "{:.3g}")],
        "Δx_trans (m)": [_cut_fmt(st.session_state.get("dx_trans", 0.0), "{:.3g}")],
        "θ_rot (deg)": [_cut_fmt(st.session_state.get("theta_rot", 0.0), "{:.3g}")],
        "z_pivot (m)": [_cut_fmt(st.session_state.get("z_pivot", 4.0))],
    })

    if force:
        st.session_state.model_input_compact_df = input_df.copy()
    elif "model_input_compact_df" not in st.session_state:
        st.session_state.model_input_compact_df = input_df.copy()

    if force:
        st.session_state.global_parameters_compact_df = global_df.copy()
    elif "global_parameters_compact_df" not in st.session_state:
        st.session_state.global_parameters_compact_df = global_df.copy()

def _apply_data_editor_edits(df: pd.DataFrame, editor_key: str) -> pd.DataFrame:
    out = pd.DataFrame(df).copy()
    state = st.session_state.get(editor_key, {})

    if not isinstance(state, dict):
        return out

    edited_rows = state.get("edited_rows", {}) or {}

    for r, changes in edited_rows.items():
        try:
            ri = int(r)
        except Exception:
            continue

        if ri < 0 or ri >= len(out):
            continue

        for col, val in dict(changes).items():
            if col in out.columns:
                out.at[ri, col] = val

    return out


def _commit_model_input_editor() -> None:
    key = "model_input_compact_editor_v3"

    if "model_input_compact_df" not in st.session_state:
        return

    df = _apply_data_editor_edits(
        st.session_state.model_input_compact_df,
        key,
    )

    st.session_state.model_input_compact_df = df.copy()

    try:
        st.session_state.beta_L = _cut_float(df.loc[1, "Left / excavation"])
        st.session_state.beta_R = _cut_float(df.loc[1, "Right / retained"])
        st.session_state.q_L = _cut_float(df.loc[2, "Left / excavation"])
        st.session_state.q_R = _cut_float(df.loc[2, "Right / retained"])
        st.session_state.z_w_L = _cut_float(df.loc[3, "Left / excavation"], 20.0)
        st.session_state.z_w_R = _cut_float(df.loc[3, "Right / retained"], 20.0)
    except Exception:
        pass


def _commit_global_parameters_editor() -> None:
    key = "global_parameters_compact_editor_v3"

    if "global_parameters_compact_df" not in st.session_state:
        return

    df = _apply_data_editor_edits(
        st.session_state.global_parameters_compact_df,
        key,
    )

    st.session_state.global_parameters_compact_df = df.copy()

    try:
        row = df.iloc[0]
        st.session_state.gamma_w = _cut_float(row["γ_w (kN/m³)"], 9.81)
        st.session_state.k_h = _cut_float(row["k_h (-)"])
        st.session_state.k_v = _cut_float(row["k_v (-)"])
        st.session_state.dx_trans = _cut_float(row["Δx_trans (m)"])
        st.session_state.theta_rot = _cut_float(row["θ_rot (deg)"])
        st.session_state.z_pivot = _cut_float(row["z_pivot (m)"], 4.0)
    except Exception:
        pass

def render_model_inputs(model_preview: Any):
    st.markdown('<div class="cut-section-title">Model inputs</div>', unsafe_allow_html=True)

    # -----------------------------
    # Geometry / loads
    # -----------------------------
    with st.expander("Geometry, loading, water and seismic", expanded=True):

        st.markdown("#### Input data")

        sync_model_input_editors()

        edited_input_df = st.data_editor(
            st.session_state.model_input_compact_df,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            height=178,
            key="model_input_compact_editor_v3",
            on_change=_commit_model_input_editor,
            disabled=["Parameter"],
            column_config={
                "Parameter": st.column_config.TextColumn("Parameter", width="small"),
                "Left / excavation": st.column_config.TextColumn("Left / excavation", width="medium"),
                "Right / retained": st.column_config.TextColumn("Right / retained", width="medium"),
            },
        )

        st.markdown("#### Global parameters")

        edited_global_df = st.data_editor(
            st.session_state.global_parameters_compact_df,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            height=80,
            key="global_parameters_compact_editor_v3",
            on_change=_commit_global_parameters_editor,
            column_config={
                "γ_w (kN/m³)": st.column_config.TextColumn("γ_w (kN/m³)", width="small"),
                "k_h (-)": st.column_config.TextColumn("k_h (-)", width="small"),
                "k_v (-)": st.column_config.TextColumn("k_v (-)", width="small"),
                "Δx_trans (m)": st.column_config.TextColumn("Δx_trans (m)", width="small"),
                "θ_rot (deg)": st.column_config.TextColumn("θ_rot (deg)", width="small"),
                "z_pivot (m)": st.column_config.TextColumn("z_pivot (m)", width="small"),
            },
        )


    # -----------------------------
    # Wall stiffness
    # -----------------------------
    with st.expander("Wall stiffness", expanded=True):

        stiffness_options = ["EI", "E & I", "E & t"]
        stiffness = st.session_state.get("stiffness_type_select", st.session_state.get("stiffness_type", "EI"))
        if stiffness not in stiffness_options:
            stiffness = "EI"

        if stiffness == "EI":
            stiffness_df = pd.DataFrame({
                "Stiffness Type": [stiffness],
                "EI (kPa·m⁴)": [_cut_fmt(st.session_state.get("EI", 1500000.0))],
            })
            edited_stiffness_df = st.data_editor(
                stiffness_df,
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                height=80,
                key="wall_stiffness_compact_editor_ei_v1",
                column_config={
                    "Stiffness Type": st.column_config.SelectboxColumn("Stiffness Type", options=stiffness_options, width="medium"),
                    "EI (kPa·m⁴)": st.column_config.TextColumn("EI (kPa·m⁴)", width="medium"),
                },
            )
            try:
                new_stiffness = str(edited_stiffness_df.loc[0, "Stiffness Type"])
                st.session_state.stiffness_type_select = new_stiffness
                st.session_state.stiffness_type = new_stiffness
                st.session_state.EI = _cut_float(edited_stiffness_df.loc[0, "EI (kPa·m⁴)"], 1500000.0)
                if new_stiffness != stiffness:
                    st.rerun()
            except Exception:
                pass
        else:
            second_label = "I (m⁴)" if stiffness == "E & I" else "t (m)"
            stiffness_df = pd.DataFrame({
                "Stiffness Type": [stiffness],
                "E (kPa)": [_cut_fmt(st.session_state.get("E", 1000000.0))],
                second_label: [_cut_fmt(st.session_state.get("I_or_t", 1.5), "{:.4g}")],
            })
            edited_stiffness_df = st.data_editor(
                stiffness_df,
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                height=80,
                key=f"wall_stiffness_compact_editor_{stiffness.replace(' ', '_').replace('&', 'and')}_v1",
                column_config={
                    "Stiffness Type": st.column_config.SelectboxColumn("Stiffness Type", options=stiffness_options, width="medium"),
                    "E (kPa)": st.column_config.TextColumn("E (kPa)", width="medium"),
                    second_label: st.column_config.TextColumn(second_label, width="medium"),
                },
            )
            try:
                new_stiffness = str(edited_stiffness_df.loc[0, "Stiffness Type"])
                st.session_state.stiffness_type_select = new_stiffness
                st.session_state.stiffness_type = new_stiffness
                st.session_state.E = _cut_float(edited_stiffness_df.loc[0, "E (kPa)"], 1000000.0)
                st.session_state.I_or_t = _cut_float(edited_stiffness_df.loc[0, second_label], 1.5)
                if new_stiffness != stiffness:
                    st.rerun()
            except Exception:
                pass

    # =====================================================
    # ✅ LEFT SIDE
    # =====================================================
    st.markdown("#### Left / excavation side soil layers")

    left_df = normalize_layer_df(st.session_state.left_layers_df, "SL").copy()
    left_df = _cut_editor_text_df(left_df)
    left_df["✓"] = False

    left_key = f"left_layers_editor_{hash(str(left_df))}"

    left_edit = st.data_editor(
        left_df,
        num_rows="fixed",
        hide_index=True,
        use_container_width=True,
        key=left_key,
        height=150,
        column_config={
            "✓": st.column_config.CheckboxColumn(width="small"),
            **_layer_column_config("SL")
        }
    )

    # write-back

    clean_left = left_edit.drop(columns=["✓"])
    new_left = normalize_layer_df(clean_left, "SL")
    new_left = enforce_unique_codes(new_left, "SL")


    if not new_left.equals(st.session_state.left_layers_df):
        st.session_state.left_layers_df = new_left
        st.rerun()

    # buttons LEFT
    lc1, lc2 = st.columns(2)

    if lc1.button("Add layer", key="add_layer_left", use_container_width=True):
        df = st.session_state.left_layers_df
        new_id = f"SL{len(df)+1}"

        new_row = default_layer_df("SL", 1.0)
        new_row.loc[0, "code"] = new_id

        st.session_state.left_layers_df = pd.concat([df, new_row], ignore_index=True)
        st.rerun()

    if lc2.button("Remove selected", key="remove_layer_left", use_container_width=True):

        keep = left_edit[left_edit["✓"] == False].drop(columns=["✓"])

        if len(keep) == 0:
            keep = default_layer_df("SL", 1.0)

        st.session_state.left_layers_df = normalize_layer_df(keep, "SL")
        st.rerun()


    # =====================================================
    # ✅ RIGHT SIDE
    # =====================================================
    st.markdown("#### Right / retained side soil layers")

    right_df = normalize_layer_df(st.session_state.right_layers_df, "SR").copy()
    right_df = _cut_editor_text_df(right_df)
    right_df["✓"] = False

    right_key = f"right_layers_editor_{hash(str(right_df))}"

    right_edit = st.data_editor(
        right_df,
        num_rows="fixed",
        hide_index=True,
        use_container_width=True,
        key=right_key,
        height=150,
        column_config={
            "✓": st.column_config.CheckboxColumn(width="small"),
            **_layer_column_config("SR")
        }
    )

    # write-back
    clean_right = right_edit.drop(columns=["✓"])
    new_right = normalize_layer_df(clean_right, "SR")
    new_right = enforce_unique_codes(new_right, "SR")

    if not new_right.equals(st.session_state.right_layers_df):
        st.session_state.right_layers_df = new_right
        st.rerun()

    # buttons RIGHT
    rc1, rc2 = st.columns(2)

    if rc1.button("Add layer", key="add_layer_right", use_container_width=True):
        df = st.session_state.right_layers_df
        new_id = f"SR{len(df)+1}"

        new_row = default_layer_df("SR", 1.0)
        new_row.loc[0, "code"] = new_id

        st.session_state.right_layers_df = pd.concat([df, new_row], ignore_index=True)
        st.rerun()

    if rc2.button("Remove selected", key="remove_layer_right", use_container_width=True):

        keep = right_edit[right_edit["✓"] == False].drop(columns=["✓"])

        if len(keep) == 0:
            keep = default_layer_df("SR", 1.0)

        st.session_state.right_layers_df = normalize_layer_df(keep, "SR")
        st.rerun()


    # =====================================================
    # ✅ GEOMETRY PREVIEW (always fresh)
    # =====================================================
    st.markdown("#### Geometry preview")

    try:
        model_preview = build_model()
        show_fig(plot_geometry(model_preview), width=750)
    except Exception:
        pass


def _reinf_column_config(rtype: str):
    base = default_reinf_df(rtype)
    cfg = {}
    if base.empty:
        return cfg
    for c in base.columns:
        if c == "code":
            cfg[c] = st.column_config.TextColumn(c, default=str(base.iloc[0][c]), width="small")
        else:
            cfg[c] = st.column_config.TextColumn(c, default=str(base.iloc[0][c]), width="small")
    return cfg

def add_reinf_row(rtype: str) -> None:
    df = get_reinf_df(rtype).copy()
    base = default_reinf_df(rtype)

    if base.empty:
        return

    new_row = base.iloc[[0]].copy()

    prefix = (
        "A" if rtype == "Anchored embedded wall"
        else "P" if rtype == "Propped embedded wall"
        else "R"
    )

    new_row.loc[0, "code"] = f"{prefix}{len(df) + 1}"

    if "z (m)" in df.columns and len(df) > 0:
        last_z = float(pd.to_numeric(df["z (m)"], errors="coerce").fillna(1.0).iloc[-1])
        new_row.loc[0, "z (m)"] = last_z + 0.5
    else:
        new_row.loc[0, "z (m)"] = 1.0

    st.session_state.reinf_dfs[rtype] = normalize_reinf_df(
        pd.concat([df, new_row], ignore_index=True),
        rtype
    )
    
def render_reinforcement(model_preview: Any):
    st.markdown(
        '<div class="cut-section-title">Reinforcement</div>',
        unsafe_allow_html=True
    )

    image_selector(
        REINFORCEMENT_CARDS,
        "reinforcement_type",
        "Stages and reinforcement",
        6
    )

    rtype = st.session_state.reinforcement_type
    st.markdown(f"**Selected:** {rtype}")

    preview_df = None

    if rtype == "No reinforcement":

        st.info("No reinforcement is applied. Solver support list is empty.")

    else:

        df = get_reinf_df(rtype).copy()
        df = _cut_editor_text_df(df)
        df["✓"] = False

        edited = st.data_editor(
            df,
            num_rows="fixed",
            hide_index=True,
            use_container_width=True,
            key=f"reinf_editor_{rtype}",
            height=145,
            column_config={
                "✓": st.column_config.CheckboxColumn(width="small"),
                **_reinf_column_config(rtype)
            }
        )

        clean = edited.drop(columns=["✓"])
        preview_df = normalize_reinf_df(clean, rtype)

        st.session_state.reinf_dfs[rtype] = preview_df

        b1, b2 = st.columns(2)

        if b1.button("Add reinforcement row", key=f"add_reinf_{rtype}", use_container_width=True):
            add_reinf_row(rtype)
            st.rerun()

        if b2.button("Remove selected", key=f"remove_reinf_{rtype}", use_container_width=True):
            keep = edited[edited["✓"] == False].drop(columns=["✓"])

            if len(keep) == 0:
                keep = default_reinf_df(rtype)

            st.session_state.reinf_dfs[rtype] = normalize_reinf_df(keep, rtype)
            st.rerun()

        if rtype.startswith("MSE walls"):
            st.caption(
                "For MSE systems, Sv is computed automatically from the z-levels."
            )

    try:
        if rtype != "No reinforcement" and preview_df is not None:
            st.session_state.reinf_dfs[rtype] = preview_df

        fresh_model = build_model()

        st.markdown("#### Reinforcement preview")

        show_fig(
            plot_reinforcement(fresh_model, st.session_state.last_result),
            width=750
        )

    except Exception:
        pass

def render_run():
    # Keep numerical controls in practical ranges
    if int(st.session_state.get("n_points", 401)) < 101:
        st.session_state.n_points = 401
    if float(st.session_state.get("dz", 0.05)) < 0.005:
        st.session_state.dz = 0.05
    if float(st.session_state.get("tol", 1e-8)) < 1e-10:
        st.session_state.tol = 1e-8

    st.markdown(
        '<div class="cut-section-title">Run & solver monitor</div>',
        unsafe_allow_html=True
    )

    # -------------------------------------------------------
    # ✅ Solver selection
    # -------------------------------------------------------
    st.markdown("#### Solver selection")
    image_selector(SOLVER_CARDS, "solver_display", "Run & solver monitor", 5)

    # -------------------------------------------------------
    # ✅ Numerical controls
    # -------------------------------------------------------
    st.markdown("#### Numerical controls")
    st.caption("These numerical controls are passed to the active solver mode, so all solvers use the same N, tolerances and integration settings unless a method ignores an irrelevant control.")

    # Compact native table layout (mobile-safe): no st.columns(), no duplicated labels.
    numerical_row1 = pd.DataFrame({
        "Integration": [str(st.session_state.get("integration_method", "Gauss"))],
        "Rigid movement mode": [str(st.session_state.get("no_bending_mode", "Auto (ΣF=0 & ΣM=0)"))],
        "Rigid optimization solver": [str(st.session_state.get("rigid_optimization_solver", "Fast equilibrium only"))],
        "N iterations": [str(int(st.session_state.get("N", 30)))],
    })
    edited_num1 = st.data_editor(
        numerical_row1,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        height=80,
        key="numerical_controls_compact_row1_v1",
        column_config={
            "Integration": st.column_config.SelectboxColumn("Integration", options=["Gauss", "Lumped"], width="medium"),
            "Rigid movement mode": st.column_config.SelectboxColumn("Rigid movement mode", options=["Auto (ΣF=0 & ΣM=0)", "Manual"], width="medium"),
            "Rigid optimization solver": st.column_config.SelectboxColumn("Rigid optimization solver", options=["Fast equilibrium only", "Energy-aware variational"], width="medium"),
            "N iterations": st.column_config.TextColumn("N iterations", width="small"),
        },
    )
    try:
        st.session_state.integration_method = str(edited_num1.loc[0, "Integration"])
        st.session_state.no_bending_mode = str(edited_num1.loc[0, "Rigid movement mode"])
        st.session_state.rigid_optimization_solver = str(edited_num1.loc[0, "Rigid optimization solver"])
        st.session_state.N = max(1, int(_cut_float(edited_num1.loc[0, "N iterations"], 30)))
    except Exception:
        pass

    numerical_row2 = pd.DataFrame({
        "Δz / plotting dz (m)": [_cut_fmt(st.session_state.get("dz", 0.05), "{:.4g}")],
        "n profile points": [str(int(st.session_state.get("n_points", 401)))],
        "tol": [_cut_fmt(st.session_state.get("tol", 1e-8), "{:.2e}")],
        "tol_W work band": [_cut_fmt(st.session_state.get("work_band_tol", 0.05), "{:.6g}")],
    })
    edited_num2 = st.data_editor(
        numerical_row2,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        height=80,
        key="numerical_controls_compact_row2_v1",
        column_config={
            "Δz / plotting dz (m)": st.column_config.TextColumn("Δz / plotting dz (m)", width="medium"),
            "n profile points": st.column_config.TextColumn("n profile points", width="medium"),
            "tol": st.column_config.TextColumn("tol", width="medium"),
            "tol_W work band": st.column_config.TextColumn("tol_W work band", width="medium"),
        },
    )
    try:
        st.session_state.dz = max(0.005, _cut_float(edited_num2.loc[0, "Δz / plotting dz (m)"], 0.05))
        st.session_state.n_points = max(101, int(_cut_float(edited_num2.loc[0, "n profile points"], 401)))
        st.session_state.tol = max(1e-8, _cut_float(edited_num2.loc[0, "tol"], 1e-8))
        st.session_state.work_band_tol = max(0.05, _cut_float(edited_num2.loc[0, "tol_W work band"], 0.05))
    except Exception:
        pass

    numerical_row3 = pd.DataFrame({
        "tol_F = |ΣF| / scale": [_cut_fmt(st.session_state.get("equilibrium_force_tol", 0.05), "{:.6g}")],
        "tol_M = |ΣM| / scale": [_cut_fmt(st.session_state.get("equilibrium_moment_tol", 0.05), "{:.6g}")],
        "Parallel execution": ["Yes" if bool(st.session_state.get("general_case_parallel", False)) else "No"],
    })
    edited_num3 = st.data_editor(
        numerical_row3,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        height=80,
        key="numerical_controls_compact_row3_v1",
        column_config={
            "tol_F = |ΣF| / scale": st.column_config.TextColumn("tol_F = |ΣF| / scale", width="medium"),
            "tol_M = |ΣM| / scale": st.column_config.TextColumn("tol_M = |ΣM| / scale", width="medium"),
            "Parallel execution": st.column_config.SelectboxColumn("Parallel execution", options=["No", "Yes"], width="medium", help="For Streamlit Cloud leave No; useful only for local runs."),
        },
    )
    try:
        st.session_state.equilibrium_force_tol = max(0.05, _cut_float(edited_num3.loc[0, "tol_F = |ΣF| / scale"], 0.05))
        st.session_state.equilibrium_moment_tol = max(0.05, _cut_float(edited_num3.loc[0, "tol_M = |ΣM| / scale"], 0.05))
        st.session_state.general_case_parallel = str(edited_num3.loc[0, "Parallel execution"]).strip().lower() == "yes"
    except Exception:
        pass

    # -------------------------------------------------------
    # ✅ Run button (with spinner)
    # -------------------------------------------------------
    if st.button("Run solver", key="run_solver_button", type="primary", use_container_width=True):
        try:

            with st.spinner("Running solver... please wait"):
                run_solver_now()
            st.rerun()
        except Exception as exc:
            st.session_state.run_message = f"Error: {exc}"
            st.error(str(exc))

    # -------------------------------------------------------
    # ✅ Results
    # -------------------------------------------------------
    result = st.session_state.last_result

    if result is not None:

        st.divider()

        design_summary(result)

        s = dict(getattr(result, "summary", {}) or {})

        rows = [
            ["Selected solver", st.session_state.solver_display],
            ["Internal mode", getattr(result, "solver_mode", "")],
            ["Status", getattr(result, "status", "")],
            ["Message", getattr(result, "message", "")]
        ]

        for k in [
            "iterations",
            "converged",
            "max_deflection_abs_m",
            "max_iteration_change_m",
            "max_net_pressure_change_kPa",
            "ΣF kN/m",
            "ΣM kNm/m",
            "|ΣF|/scale",
            "|ΣM|/scale"
        ]:
            if k in s:
                rows.append([k, s[k]])

        st.markdown("#### Solver report")

        st.dataframe(
            pd.DataFrame(rows, columns=["Quantity", "Value"]),
            use_container_width=True,
            hide_index=True,
            height=360
        )


def render_results():
    st.markdown('<div class="cut-section-title">Results table</div>', unsafe_allow_html=True)
    df = result_dataframe(st.session_state.last_result)
    if df.empty:
        st.info("Run a solver first.")
    else:
        st.dataframe(format_results_for_display(df), use_container_width=True, hide_index=True, height=560)
        st.download_button("Download results CSV", df.to_csv(index=False).encode("utf-8"), "cut_embedded_wall_results.csv", "text/csv")



def _finite_pairs(x_values, z_values):
    xs = []
    zs = []
    for x, z in zip(list(x_values or []), list(z_values or [])):
        try:
            xf = float(x)
            zf = float(z)
        except Exception:
            continue
        if math.isfinite(xf) and math.isfinite(zf):
            xs.append(xf)
            zs.append(zf)
    return xs, zs


def _plotly_style(label: str):
    lab = str(label).lower()

    if "δx/δxmax" in lab or "dx/dxmax" in lab or "Δx/Δxmax".lower() in lab:
        return "black", "solid", 2.4

    if "rotation" in lab or lab in ("θ", "theta"):
        return "black", "solid", 2.4

    if "calculated" in lab or lab in ("δx", "p_net", "v", "m"):
        return "black", "solid", 2.4

    if "δxmax" in lab or "dxmax" in lab:
        return "red", "dash", 1.6

    if "at-rest" in lab or "σoe" in lab or "oe" in lab:
        return "black", "dash", 1.5
    if "passive" in lab or "σpe" in lab or "pe" in lab:
        return "red", "dash", 1.5
    if "active" in lab or "σae" in lab or "ae" in lab:
        return "green", "dash", 1.5

    if "δx/δxmax" in lab or "dx/dxmax" in lab or "Δx/Δxmax".lower() in lab:
        return "black", "solid", 2.0

    if "left" in lab:
        return "black", "dash", 1.7
    if "right" in lab:
        return "black", "solid", 1.7

    return "black", "solid", 1.7


def plot_profile_interactive(
    series: list[tuple[str, list[float]]],
    z: list[float],
    xlabel: str,
    title: str,
    zero_line: bool = True,
    shade: bool = False,
    vlines: list[tuple[float, str, str]] | None = None,
    shade_count: int | None = None,
    x_values_for_limits: list[float] | None = None,
    show_legend: bool = False,
    legend_corner: str | None = None,
):
    """Interactive Plotly version of the depth-profile chart."""

    fig = go.Figure()
    clean_x_for_axis = []

    for i, (label, values) in enumerate(series):
        xs, zs = _finite_pairs(values, z)
        if not xs:
            continue

        clean_x_for_axis.extend(xs)

        should_shade = bool(shade)
        if shade_count is not None:
            should_shade = should_shade and i < int(shade_count)

        if should_shade:
            fig.add_trace(
                go.Scatter(
                    x=[0.0] * len(zs) + xs[::-1],
                    y=zs + zs[::-1],
                    fill="toself",
                    fillcolor="rgba(90, 90, 90, 0.16)",
                    line=dict(width=0),
                    hoverinfo="skip",
                    showlegend=False,
                    name=f"{label} shaded area",
                )
            )

        # Special override:
        # Δx/Δxmax curves must be black solid.
        # They contain "dxmax" in their label, so they must be caught
        # before the generic dxmax limit-style rule.
        lab = str(label).lower()
        if (
            "δx/δxmax" in lab
            or "dx/dxmax" in lab
            or "δx/δxmax" in lab
            or "Δx/Δxmax".lower() in lab
        ):
            color, dash, width = "black", "solid", 2.4
        else:
            color, dash, width = _plotly_style(label)

        legend_name = str(label).strip()
        show_this_legend = bool(show_legend)

        if show_legend and legend_name.lower().startswith("calculated"):
            show_this_legend = False

        if show_legend:
            existing_names = {
                tr.name for tr in fig.data
                if getattr(tr, "showlegend", False)
            }
            if legend_name in existing_names:
                show_this_legend = False

        fig.add_trace(
            go.Scatter(
                x=xs,
                y=zs,
                mode="lines",
                name=legend_name,
                showlegend=show_this_legend,
                legendgroup=legend_name,
                line=dict(color=color, dash=dash, width=width),
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    + xlabel
                    + ": %{x:.3f}<br>z: %{y:.3f} m<extra></extra>"
                ),
            )
        )

    if x_values_for_limits is None:
        axis_values = clean_x_for_axis
    else:
        axis_values = list(x_values_for_limits or [])

    xmin, xmax = _auto_xlim([axis_values])
    shapes = []

    if zero_line:
        shapes.append(
            dict(
                type="line",
                x0=0.0,
                x1=0.0,
                y0=min(z) if z else 0.0,
                y1=max(z) if z else 1.0,
                line=dict(color="rgba(70,70,70,0.75)", width=1.0),
            )
        )

    for item in vlines or []:
        try:
            x0, label, linestyle = item

            # All Δx/Δxmax limit lines must be red dashed.
            shapes.append(
                dict(
                    type="line",
                    x0=float(x0),
                    x1=float(x0),
                    y0=min(z) if z else 0.0,
                    y1=max(z) if z else 1.0,
                    line=dict(
                        color="rgba(220,0,0,0.75)",
                        width=1.2,
                        dash="dash",
                    ),
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=[float(x0)],
                    y=[min(z) if z else 0.0],
                    mode="lines",
                    name=label,
                    line=dict(
                        color="red",
                        width=2,
                        dash="dash",
                    ),
                    hoverinfo="skip",
                    showlegend=bool(show_legend),
                )
            )

        except Exception:
            pass

    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            xanchor="center",
            font=dict(size=18, color="#172033"),
        ),
        template="plotly_white",
        height=520,
        margin=dict(l=60, r=20, t=55, b=55),
        hovermode="closest",
        showlegend=bool(show_legend),
        legend=dict(
            bgcolor="rgba(255,255,255,0.86)",
            bordercolor="rgba(203,213,225,0.9)",
            borderwidth=1,
            font=dict(size=11),
            x=0.02 if legend_corner == "upper_left" else None,
            y=0.98 if legend_corner == "upper_left" else None,
            xanchor="left" if legend_corner == "upper_left" else None,
            yanchor="top" if legend_corner == "upper_left" else None,
        ),
        shapes=shapes,
        plot_bgcolor="#f8fafc",
    )

    fig.update_xaxes(
        title=xlabel,
        range=[xmin, xmax],
        showgrid=True,
        gridcolor="rgba(148,163,184,0.25)",
        zeroline=False,
        tickformat=".4g",
    )

    fig.update_yaxes(
        title="z (m)",
        autorange="reversed",
        showgrid=True,
        gridcolor="rgba(148,163,184,0.25)",
        tickformat=".4g",
    )

    return fig


def plot_convergence_profile_interactive(result: Any, quantity: str):
    summary = dict(getattr(result, "summary", {}) or {})
    candidates = list(summary.get("general_case_solutions_table", []) or [])
    conv = list(getattr(result, "convergence_history", []) or [])

    x = []
    y = []

    if candidates:
        rows = sorted(candidates, key=lambda r: float(r.get("load_factor", r.get("factor", 0.0)) or 0.0))
        x = [float(r.get("load_factor", r.get("factor", i + 1)) or (i + 1)) for i, r in enumerate(rows)]

        if quantity == "change":
            y = [float(r.get("W_total_signed", r.get("W_total", r.get("energy", 0.0))) or 0.0) for r in rows]
            title = "Convergence: Δchange"
            xlabel = "load / bending factor γ (-)"
            ylabel = "candidate work / change"
        else:
            y = [
                1000.0 * abs(float(r.get("max_deflection_abs_m", r.get("max_abs_deflection_m", r.get("dx_trans", 0.0))) or 0.0))
                for r in rows
            ]
            title = "Convergence: abs(Δx)"
            xlabel = "load / bending factor γ (-)"
            ylabel = "max |Δx| (mm)"

    elif conv:
        x = [int(r.get("iteration", i + 1) or (i + 1)) for i, r in enumerate(conv)]

        if quantity == "change":
            y = [1000.0 * abs(float(r.get("max_change_m", r.get("max_iteration_change_m", 0.0)) or 0.0)) for r in conv]
            title = "Convergence: Δchange"
            xlabel = "iteration"
            ylabel = "max Δchange (mm)"
        else:
            y = [1000.0 * abs(float(r.get("max_abs_deflection_m", r.get("max_deflection_abs_m", 0.0)) or 0.0)) for r in conv]
            title = "Convergence: abs(Δx)"
            xlabel = "iteration"
            ylabel = "max |Δx| (mm)"
    else:
        title = "Convergence: Δchange" if quantity == "change" else "Convergence: abs(Δx)"
        xlabel = "iteration"
        ylabel = "value"

    fig = go.Figure()

    if x and y:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines+markers",
                name=title,
                line=dict(color="black", width=2.0),
                marker=dict(size=6),
                hovertemplate="<b>%{fullData.name}</b><br>" + xlabel + ": %{x:.6g}<br>" + ylabel + ": %{y:.6g}<extra></extra>",
            )
        )
    else:
        fig.add_annotation(text="No convergence history available", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center", font=dict(size=18, color="#172033")),
        template="plotly_white",
        height=450,
        margin=dict(l=60, r=20, t=55, b=55),
        hovermode="closest",
        plot_bgcolor="#f8fafc",
        showlegend=False,
    )
    fig.update_xaxes(title=xlabel, showgrid=True, gridcolor="rgba(148,163,184,0.25)", tickformat=".4g")
    fig.update_yaxes(title=ylabel, showgrid=True, gridcolor="rgba(148,163,184,0.25)", tickformat=".4g")

    return fig


def _integrate_resultant(z, values):
    pairs = []
    for zz, vv in zip(list(z or []), list(values or [])):
        try:
            zf = float(zz)
            vf = float(vv)
        except Exception:
            continue
        if math.isfinite(zf) and math.isfinite(vf):
            pairs.append((zf, abs(vf)))

    if len(pairs) < 2:
        return float("nan"), float("nan")

    pairs.sort(key=lambda t: t[0])
    zs = np.array([p[0] for p in pairs], dtype=float)
    ps = np.array([p[1] for p in pairs], dtype=float)

    force = float(np.trapezoid(ps, zs))
    moment = float(np.trapezoid(ps * zs, zs))

    z_app = moment / force if abs(force) > 1.0e-12 else float("nan")
    return force, z_app


def _failure_z_from_ratio(z, ratio_values, threshold: float = 1.0):
    failed = []
    for zz, rr in zip(list(z or []), list(ratio_values or [])):
        try:
            zf = float(zz)
            rf = abs(float(rr))
        except Exception:
            continue
        if math.isfinite(zf) and math.isfinite(rf) and rf >= threshold:
            failed.append((zf, rf))

    if not failed:
        return "No", "—", "—"

    z0, r0 = min(failed, key=lambda t: t[0])
    return "Yes", f"{z0:.3g}", f"{r0:.3g}"


def _support_results_dataframe(model: Any, result: Any) -> pd.DataFrame:
    """Support-force table.

    Uses solver-reported forces when available.  If the solver does not expose
    them, estimates force per metre from support stiffness, prestress and wall
    displacement at the support depth.
    """
    supports = list(getattr(model, "reinforcement_supports", []) or [])
    reported = reported_support_force_map(result)

    rows = []

    if supports:
        for i, support in enumerate(supports):
            code = str(support.get("code", f"S{i+1}"))
            z = float(support.get("z", 0.0) or 0.0)

            if code in reported:
                force = float(reported[code])
                source = "solver"
            else:
                force = support_force_for_display(support, result)
                source = "estimated"

            rows.append({
                "Support": code,
                "(z, force)": f"({fmt_num(z)}, {fmt_num(force)} kN/m)",
                "z (m)": z,
                "Force (kN/m)": force,
                "Source": source,
            })

    elif reported:
        for code, force in reported.items():
            rows.append({
                "Support": code,
                "(z, force)": f"(—, {fmt_num(force)} kN/m)",
                "z (m)": "—",
                "Force (kN/m)": force,
                "Source": "solver",
            })

    return pd.DataFrame(rows)


def engineering_summary_tables(model: Any, result: Any):
    z = list(getattr(result, "z", []) or [])

    def arr(name):
        return list(getattr(result, name, []) or [])

    resultant_rows = []
    for label, left_name, right_name in [
        ("Total", "p_left", "p_right"),
        ("Effective", "sigma_left_eff", "sigma_right_eff"),
        ("Water", "u_left", "u_right"),
    ]:
        FL, zL = _integrate_resultant(z, arr(left_name))
        FR, zR = _integrate_resultant(z, arr(right_name))

        resultant_rows.append({
            "Component": label,
            "Left force (kN/m)": FL,
            "Left z_app (m)": zL,
            "Right force (kN/m)": FR,
            "Right z_app (m)": zR,
        })

    z_left_surface = float(model.geometry.H_R) - float(model.geometry.H_L)

    active_ratio = []
    passive_ratio = []
    defl = arr("deflection")
    dxA = arr("dxmax_right_A")
    dxP = arr("dxmax_left_P")

    for zz, w, a, p in zip(z, defl, dxA, dxP):
        try:
            active_ratio.append(abs(float(w)) / abs(float(a)) if abs(float(a)) > 1.0e-12 else float("nan"))
        except Exception:
            active_ratio.append(float("nan"))

        try:
            passive_ratio.append(abs(float(w)) / abs(float(p)) if float(zz) > z_left_surface + 1.0e-9 and abs(float(p)) > 1.0e-12 else float("nan"))
        except Exception:
            passive_ratio.append(float("nan"))

    a_yes, a_z, a_ratio = _failure_z_from_ratio(z, active_ratio)
    p_yes, p_z, p_ratio = _failure_z_from_ratio(z, passive_ratio)

    failure_df = pd.DataFrame([
        {"Failure mode": "Active", "Failure": a_yes, "z (m)": a_z, "max ratio": a_ratio},
        {"Failure mode": "Passive", "Failure": p_yes, "z (m)": p_z, "max ratio": p_ratio},
    ])

    return pd.DataFrame(resultant_rows), _support_results_dataframe(model, result), failure_df


def render_plots():
    st.markdown('<div class="cut-section-title">Plots</div>', unsafe_allow_html=True)

    result = st.session_state.last_result
    model = st.session_state.last_model

    if result is None or model is None:
        st.info("Run a solver first.")
        return

    z = list(result.z)

    st.markdown("#### Engineering plots")

    def arr(name):
        return list(getattr(result, name, []) or [])

    def safe_float(x):
        try:
            xf = float(x)
            return xf if math.isfinite(xf) else float("nan")
        except Exception:
            return float("nan")

    def neg(values, scale=1.0):
        return [-scale * safe_float(x) for x in list(values or [])]

    def pos(values, scale=1.0):
        return [scale * safe_float(x) for x in list(values or [])]

    def has_values(values):
        return any(math.isfinite(safe_float(x)) for x in list(values or []))

    def ratio(num, den, sign=1.0):
        out = []

        for a, b in zip(list(num or []), list(den or [])):
            try:
                af = float(a)
                bf = float(b)
                out.append(sign * af / bf if abs(bf) > 1.0e-12 else float("nan"))
            except Exception:
                out.append(float("nan"))

        return out

    # Free-surface levels of each side.
    z_right_surface = 0.0
    z_left_surface = float(model.geometry.H_R) - float(model.geometry.H_L)

    # -------------------------------------------------------
    # Total horizontal pressure with earth-pressure envelopes
    # -------------------------------------------------------
    calc_left_pressure = neg(arr("p_left"))
    calc_right_pressure = pos(arr("p_right"))

    total_pressure_series = [
        ("Calculated left", calc_left_pressure),
        ("Calculated right", calc_right_pressure),
    ]

    for label, left_attr, right_attr in [
        ("At-rest state", "sigma_left_OE", "sigma_right_OE"),
        ("Passive state", "sigma_left_PE", "sigma_right_PE"),
        ("Active state", "sigma_left_AE", "sigma_right_AE"),
    ]:
        left_values = neg(arr(left_attr))
        right_values = pos(arr(right_attr))

        if has_values(left_values):
            total_pressure_series.append((label, left_values))

        if has_values(right_values):
            total_pressure_series.append((f"{label} ", right_values))

    # -------------------------------------------------------
    # Deflection with limiting displacements Δxmax,A/P
    # -------------------------------------------------------
    deflection_series = [
        ("calculated Δx", neg(arr("deflection"), scale=1000.0)),
    ]

    dxmax_A_mm = [-1000.0 * abs(safe_float(x)) for x in arr("dxmax_right_A")]

    dxmax_P_mm = []
    for zz, x in zip(z, arr("dxmax_left_P")):
        zf = safe_float(zz)
        val = 1000.0 * abs(safe_float(x))
        dxmax_P_mm.append(val if zf > z_left_surface + 1.0e-9 and math.isfinite(val) and val > 0.0 else float("nan"))

    if has_values(dxmax_A_mm):
        deflection_series.append(("Δxmax,A", dxmax_A_mm))

    if has_values(dxmax_P_mm):
        deflection_series.append(("Δxmax,P", dxmax_P_mm))

    # -------------------------------------------------------
    # K diagram: omit side-surface singular/free-surface points
    # and clip only the displayed values.
    # -------------------------------------------------------
    k_left_plot = _mask_side_surface_point(
        neg(arr("K_left")),
        z,
        z_left_surface,
    )
    k_right_plot = _mask_side_surface_point(
        pos(arr("K_right")),
        z,
        z_right_surface,
    )

    k_limit = _robust_symmetric_limit(k_left_plot + k_right_plot, hard_limit=8.0, percentile=92.0)
    k_left_plot = _clip_for_plot(k_left_plot, k_limit)
    k_right_plot = _clip_for_plot(k_right_plot, k_limit)

    # -------------------------------------------------------
    # Mobilization diagram: active negative, passive positive.
    # Omit z=0 on retained side and z=H_R-H_L on excavation side.
    # -------------------------------------------------------
    dx_ratio_A = _mask_side_surface_point(
        ratio(arr("deflection"), arr("dxmax_right_A"), sign=-1.0),
        z,
        z_right_surface,
    )

    dx_ratio_P = _mask_side_surface_point(
        ratio(arr("deflection"), arr("dxmax_left_P"), sign=1.0),
        z,
        z_left_surface,
    )

    dx_ratio_P = [
        v if safe_float(zz) > z_left_surface + 1.0e-9 else float("nan")
        for zz, v in zip(z, dx_ratio_P)
    ]

    plots = [
        plot_profile_interactive(
            total_pressure_series,
            z,
            "total horizontal pressure, p_h (kPa)",
            "Total horizontal pressure",
            shade=True,
            shade_count=2,
            x_values_for_limits=calc_left_pressure + calc_right_pressure,
            show_legend=True,
            legend_corner="upper_left",
        ),
        plot_profile_interactive(
            deflection_series,
            z,
            "Δx (mm, left negative)",
            "Deflection",
            shade=False,
            # Keep axis scaling based only on calculated deflection.
            # Very large Δxmax values collapse the calculated curve visually.
            x_values_for_limits=deflection_series[0][1],
        ),
        plot_profile_interactive(
            [("left σ'_h", neg(arr("sigma_left_eff"))), ("right σ'_h", pos(arr("sigma_right_eff")))],
            z,
            "-σ'_h,L or σ'_h,R (kPa)",
            "Effective horizontal stresses",
            shade=True,
        ),
        plot_profile_interactive(
            [("left u", neg(arr("u_left"))), ("right u", pos(arr("u_right")))],
            z,
            "-u_L or u_R (kPa)",
            "Water stresses",
            shade=True,
        ),
        plot_profile_interactive(
            [("K_L", k_left_plot), ("K_R", k_right_plot)],
            z,
            "-K_L or K_R (-)",
            f"K diagram (display clipped at ±{k_limit:.3g})",
            shade=True,
        ),
        plot_profile_interactive(
            [
                ("Δx/Δxmax,A", dx_ratio_A),
                ("Δx/Δxmax,P", dx_ratio_P),
            ],
            z,
            "Δx / Δxmax (-)",
            "Δx / Δxmax",
            shade=False,
            vlines=[(-1.0, "active limit", "--"), (1.0, "passive limit", "--")],
        ),
        plot_profile_interactive(
            [("p_net", pos(arr("net_pressure")))],
            z,
            "p_net (kPa)",
            "Net pressure",
            shade=True,
        ),
        plot_profile_interactive(
            [("rotation", pos(arr("rotation")))],
            z,
            "θ (deg)",
            "Rotation",
            shade=False,
        ),
        plot_profile_interactive(
            [("V", pos(arr("shear")))],
            z,
            "V (kN/m)",
            "Shear",
            shade=True,
        ),
        plot_profile_interactive(
            [("M", pos(arr("moment")))],
            z,
            "M (kNm/m)",
            "Moment",
            shade=True,
        ),
        plot_convergence_profile_interactive(result, "change"),
        plot_convergence_profile_interactive(result, "abs_dx"),
    ]

    for i in range(0, len(plots), 2):
        c1, c2 = st.columns(2, gap="medium")

        with c1:
            st.plotly_chart(plots[i], use_container_width=True)

        if i + 1 < len(plots):
            with c2:
                st.plotly_chart(plots[i + 1], use_container_width=True)



def fmt_num(value, digits: int = 4, suffix: str = ""):
    try:
        v = float(value)
    except Exception:
        return "—"

    if not math.isfinite(v):
        return "—"

    if abs(v) < 1.0e-12:
        v = 0.0

    return f"{v:.{digits}g}{suffix}"


def _summary_extreme(z, values, factor: float = 1.0, use_abs: bool = True):
    best_z = float("nan")
    best_v = float("nan")
    best_key = -1.0

    for zz, vv in zip(list(z or []), list(values or [])):
        try:
            zf = float(zz)
            vf = factor * float(vv)
        except Exception:
            continue

        if not (math.isfinite(zf) and math.isfinite(vf)):
            continue

        key = abs(vf) if use_abs else vf

        if key > best_key:
            best_key = key
            best_v = vf
            best_z = zf

    return best_v, best_z


def summary_resultants_df(model: Any, result: Any) -> pd.DataFrame:
    z = list(getattr(result, "z", []) or [])

    def arr(name):
        return list(getattr(result, name, []) or [])

    rows = []

    for label, left_name, right_name in [
        ("Total", "p_left", "p_right"),
        ("Effective", "sigma_left_eff", "sigma_right_eff"),
        ("Water", "u_left", "u_right"),
    ]:
        FL, zL = _integrate_resultant(z, arr(left_name))
        FR, zR = _integrate_resultant(z, arr(right_name))

        rows.append({
            "Component": label,
            "Left resultant (kN/m)": fmt_num(FL),
            "Left z_app (m)": fmt_num(zL),
            "Right resultant (kN/m)": fmt_num(FR),
            "Right z_app (m)": fmt_num(zR),
        })

    return pd.DataFrame(rows)


def summary_support_forces_df(model: Any, result: Any) -> pd.DataFrame:
    df = _support_results_dataframe(model, result)

    if df is None or df.empty:
        return pd.DataFrame(columns=["Support", "(z, force)", "z (m)", "Force (kN/m)", "Source"])

    out_rows = []

    for _, row in df.iterrows():
        support = row.get("Support", "—")
        z = row.get("z (m)", "—")
        force = row.get("Force (kN/m)", "—")
        source = row.get("Source", "—")

        try:
            z_fmt = fmt_num(float(z), 4)
        except Exception:
            z_fmt = str(z)

        try:
            f_fmt = fmt_num(float(force), 4)
        except Exception:
            f_fmt = str(force) if str(force).strip() else "—"

        out_rows.append({
            "Support": support,
            "(z, force)": f"({z_fmt}, {f_fmt} kN/m)",
            "z (m)": z_fmt,
            "Force (kN/m)": f_fmt,
            "Source": source,
        })

    return pd.DataFrame(out_rows)


def summary_failure_df(model: Any, result: Any) -> pd.DataFrame:
    z = list(getattr(result, "z", []) or [])

    def arr(name):
        return list(getattr(result, name, []) or [])

    z_left_surface = float(model.geometry.H_R) - float(model.geometry.H_L)

    def ratios(defl, limit, passive=False):
        out = []
        for zz, w, lim in zip(z, defl, limit):
            try:
                zf = float(zz)
                wf = abs(float(w))
                lf = abs(float(lim))
            except Exception:
                out.append(float("nan"))
                continue

            if passive and not (zf > z_left_surface + 1.0e-9):
                out.append(float("nan"))
            elif lf > 1.0e-12:
                out.append(wf / lf)
            else:
                out.append(float("nan"))
        return out

    active = ratios(arr("deflection"), arr("dxmax_right_A"), passive=False)
    passive = ratios(arr("deflection"), arr("dxmax_left_P"), passive=True)

    a_yes, a_z, a_ratio = _failure_z_from_ratio(z, active)
    p_yes, p_z, p_ratio = _failure_z_from_ratio(z, passive)

    return pd.DataFrame([
        {"Failure mode": "Active", "Failure": a_yes, "z_failure (m)": a_z, "ratio": a_ratio},
        {"Failure mode": "Passive", "Failure": p_yes, "z_failure (m)": p_z, "ratio": p_ratio},
    ])


def summary_extremes_df(result: Any) -> pd.DataFrame:
    z = list(getattr(result, "z", []) or [])

    dx, z_dx = _summary_extreme(z, getattr(result, "deflection", []), factor=1000.0, use_abs=True)
    M, z_M = _summary_extreme(z, getattr(result, "moment", []), factor=1.0, use_abs=True)
    V, z_V = _summary_extreme(z, getattr(result, "shear", []), factor=1.0, use_abs=True)

    return pd.DataFrame([
        {"Quantity": "Max |deflection|", "Value": fmt_num(abs(dx), 4, " mm"), "z (m)": fmt_num(z_dx)},
        {"Quantity": "Max |moment|", "Value": fmt_num(abs(M), 4, " kNm/m"), "z (m)": fmt_num(z_M)},
        {"Quantity": "Max |shear|", "Value": fmt_num(abs(V), 4, " kN/m"), "z (m)": fmt_num(z_V)},
    ])


def render_summary_results():
    st.markdown('<div class="cut-section-title">Summary results</div>', unsafe_allow_html=True)

    result = st.session_state.last_result
    model = st.session_state.last_model

    if result is None or model is None:
        st.info("Run a solver first.")
        return

    st.markdown("#### Resultant actions and points of application")
    st.dataframe(
        summary_resultants_df(model, result),
        use_container_width=True,
        hide_index=True,
        height=145,
    )

    st.markdown("#### Reinforcement/support force pairs")
    support_df = summary_support_forces_df(model, result)

    # Remove redundant combined pair column
    support_df = support_df.drop(columns=["(z, force)"], errors="ignore")

    if support_df.empty:
        st.caption("No reinforcement/supports in the current model.")
    else:
        st.dataframe(
            support_df,
            use_container_width=True,
            hide_index=True,
            height=min(260, 42 + 36 * max(1, len(support_df))),
        )

    st.markdown("#### Active/passive failure check")
    st.dataframe(
        summary_failure_df(model, result),
        use_container_width=True,
        hide_index=True,
        height=112,
    )

    st.markdown("#### Extreme structural response")
    st.dataframe(
        summary_extremes_df(result),
        use_container_width=True,
        hide_index=True,
        height=145,
    )


# ============================================================
# WATER LEVEL ANIMATION
# ============================================================

WATER_PLOT_OPTIONS = {
    "Total horizontal pressure": "pressure",
    "Deflection": "deflection",
    "Moment": "moment",
    "Shear": "shear",
    "Rotation": "rotation",
    "Water stresses": "water",
    "Effective stresses": "effective",
    "Net pressure": "net",
}


def build_water_animation_levels(
    H_R: float,
    H_L: float,
    z_final_left: float,
    z_final_right: float,
    n_steps: int,
    mode: str,
) -> list[tuple[float, float]]:
    """Return water levels [(z_w_L, z_w_R), ...]."""
    n_steps = max(2, int(n_steps))
    z_left_surface = float(H_R) - float(H_L)
    z0 = float(H_R)
    z_final_left = max(float(z_final_left), z_left_surface)
    z_final_right = max(float(z_final_right), 0.0)
    rows = []

    if mode == "Simultaneous proportional rise":
        for i in range(n_steps):
            t = i / max(1, n_steps - 1)
            zL = z0 + t * (z_final_left - z0)
            zR = z0 + t * (z_final_right - z0)
            rows.append((zL, zR))
    else:
        total_rise = max(z0 - z_final_left, z0 - z_final_right, 0.0)
        for i in range(n_steps):
            t = i / max(1, n_steps - 1)
            rise = t * total_rise
            zL = max(z_final_left, z0 - rise)
            zR = max(z_final_right, z0 - rise)
            rows.append((zL, zR))

    return rows



def _animation_solver_water_levels(
    z_w_L: float,
    z_w_R: float,
    H_R: float,
    H_L: float,
) -> tuple[float, float]:
    """Return water levels safe for solver execution in animation frames.

    The exact free-surface values can trigger a different numerical branch in
    some solver pressure routines.  For animation sweeps, use an infinitesimal
    value below the ground surface so the last frame remains consistent with
    the preceding frames.
    """
    eps = max(1.0e-6, 1.0e-7 * max(float(H_R), 1.0))
    z_left_surface = float(H_R) - float(H_L)

    zL = float(z_w_L)
    zR = float(z_w_R)

    if zL <= z_left_surface + eps:
        zL = z_left_surface + eps

    if zR <= eps:
        zR = eps

    return zL, zR



def total_pressure_animation_series(result: Any) -> list[tuple[str, list[float]]]:
    """Pressure traces for animation pressure charts, including limiting envelopes.

    Uses the same sign convention and dashed state styling as the main
    Total horizontal pressure engineering plot.
    """
    def arr(name):
        return list(getattr(result, name, []) or [])

    def safe_float(x):
        try:
            xf = float(x)
            return xf if math.isfinite(xf) else float("nan")
        except Exception:
            return float("nan")

    def neg(values):
        return [-safe_float(x) for x in list(values or [])]

    def pos(values):
        return [safe_float(x) for x in list(values or [])]

    def has_values(values):
        return any(math.isfinite(safe_float(x)) for x in list(values or []))

    series = [
        ("Calculated left", neg(arr("p_left"))),
        ("Calculated right", pos(arr("p_right"))),
    ]

    for label, left_attr, right_attr in [
        ("At-rest state", "sigma_left_OE", "sigma_right_OE"),
        ("Passive state", "sigma_left_PE", "sigma_right_PE"),
        ("Active state", "sigma_left_AE", "sigma_right_AE"),
    ]:
        left_values = neg(arr(left_attr))
        right_values = pos(arr(right_attr))
        if has_values(left_values):
            series.append((label, left_values))
        if has_values(right_values):
            series.append((f"{label} ", right_values))

    return series

def plot_water_animation_frame(
    result: Any,
    model: Any,
    quantity: str,
    z_w_L: float,
    z_w_R: float,
    x_min: float | None = None,
    x_max: float | None = None,
) -> go.Figure:
    z = list(result.z)

    def arr(name):
        return list(getattr(result, name, []) or [])

    def neg(values, scale=1.0):
        out = []
        for x in values:
            try:
                out.append(-scale * float(x))
            except Exception:
                out.append(float("nan"))
        return out

    def pos(values, scale=1.0):
        out = []
        for x in values:
            try:
                out.append(scale * float(x))
            except Exception:
                out.append(float("nan"))
        return out

    if quantity == "pressure":
        pressure_series = total_pressure_animation_series(result)
        fig = plot_profile_interactive(
            pressure_series,
            z,
            "Pressure (kPa)",
            "Total horizontal pressure",
            shade=True,
            shade_count=2,
            show_legend=True,
            legend_corner="upper_left",
        )
    elif quantity == "deflection":
        fig = plot_profile_interactive(
            [("Δx", neg(arr("deflection"), 1000.0))],
            z,
            "Δx (mm)",
            "Deflection",
        )
    elif quantity == "moment":
        fig = plot_profile_interactive(
            [("M", pos(arr("moment")))],
            z,
            "Moment (kNm/m)",
            "Moment",
            shade=True,
        )
    elif quantity == "shear":
        fig = plot_profile_interactive(
            [("V", pos(arr("shear")))],
            z,
            "Shear (kN/m)",
            "Shear",
            shade=True,
        )
    elif quantity == "rotation":
        fig = plot_profile_interactive(
            [("rotation", pos(arr("rotation")))],
            z,
            "Rotation (deg)",
            "Rotation",
        )
    elif quantity == "water":
        fig = plot_profile_interactive(
            [("u_L", neg(arr("u_left"))), ("u_R", pos(arr("u_right")))],
            z,
            "u (kPa)",
            "Water stresses",
            shade=True,
        )
    elif quantity == "effective":
        fig = plot_profile_interactive(
            [("σh,L", neg(arr("sigma_left_eff"))), ("σh,R", pos(arr("sigma_right_eff")))],
            z,
            "σ'h (kPa)",
            "Effective stresses",
            shade=True,
        )
    else:
        fig = plot_profile_interactive(
            [("p_net", pos(arr("net_pressure")))],
            z,
            "p_net (kPa)",
            "Net pressure",
            shade=True,
        )

    H_R = float(model.geometry.H_R)
    H_L = float(model.geometry.H_L)
    z_left_surface = H_R - H_L

    # Use the actual x-axis coordinates for the water split.
    # This makes x=0 the exact separator between left and right water levels.
    try:
        auto_range = list(fig.layout.xaxis.range or [])
    except Exception:
        auto_range = []

    if x_min is None:
        x_min = float(auto_range[0]) if len(auto_range) == 2 else -1.0
    if x_max is None:
        x_max = float(auto_range[1]) if len(auto_range) == 2 else 1.0

    x_min = float(x_min)
    x_max = float(x_max)

    if x_min >= 0.0:
        x_min = -max(abs(x_max), 1.0)
    if x_max <= 0.0:
        x_max = max(abs(x_min), 1.0)

    water_fill = "rgba(56, 189, 248, 0.16)"
    water_line = "rgba(37, 99, 235, 0.90)"
    ground_line = "rgba(120, 72, 36, 0.88)"

    shapes = list(fig.layout.shapes) if fig.layout.shapes else []
    shapes.extend([
        # left/excavation water: x_min to wall axis x=0
        dict(type="rect", xref="x", yref="y", x0=x_min, x1=0.0, y0=max(float(z_w_L), z_left_surface), y1=H_R, fillcolor=water_fill, line=dict(width=0), layer="below"),
        # right/retained water: wall axis x=0 to x_max
        dict(type="rect", xref="x", yref="y", x0=0.0, x1=x_max, y0=max(float(z_w_R), 0.0), y1=H_R, fillcolor=water_fill, line=dict(width=0), layer="below"),
        dict(type="line", xref="x", yref="y", x0=x_min, x1=0.0, y0=float(z_w_L), y1=float(z_w_L), line=dict(color=water_line, width=2, dash="dash"), layer="above"),
        dict(type="line", xref="x", yref="y", x0=0.0, x1=x_max, y0=float(z_w_R), y1=float(z_w_R), line=dict(color=water_line, width=2, dash="dash"), layer="above"),
        # elegant ground-level references
        dict(type="line", xref="x", yref="y", x0=x_min, x1=0.0, y0=z_left_surface, y1=z_left_surface, line=dict(color=ground_line, width=1.6), layer="above"),
        dict(type="line", xref="x", yref="y", x0=0.0, x1=x_max, y0=0.0, y1=0.0, line=dict(color=ground_line, width=1.6), layer="above"),
    ])

    title_text = fig.layout.title.text if fig.layout.title and fig.layout.title.text else "Water-level animation"
    fig.update_layout(
        shapes=shapes,
        title=dict(text=f"{title_text}<br><sup>z_w,L={z_w_L:.3f} m, z_w,R={z_w_R:.3f} m</sup>", x=0.5, xanchor="center", font=dict(size=18, color="#172033")),
    )
    fig.update_xaxes(range=[x_min, x_max])
    return fig


def max_response_for_quantity(result: Any, quantity: str) -> tuple[float, str]:
    if quantity == "deflection":
        values = [abs(float(x)) * 1000.0 for x in getattr(result, "deflection", [])]
        return (max(values) if values else float("nan")), "mm"
    if quantity == "moment":
        values = [abs(float(x)) for x in getattr(result, "moment", [])]
        return (max(values) if values else float("nan")), "kNm/m"
    if quantity == "shear":
        values = [abs(float(x)) for x in getattr(result, "shear", [])]
        return (max(values) if values else float("nan")), "kN/m"
    if quantity == "rotation":
        values = [abs(float(x)) for x in getattr(result, "rotation", [])]
        return (max(values) if values else float("nan")), "deg"
    if quantity == "water":
        values = [abs(float(x)) for x in list(getattr(result, "u_left", []) or []) + list(getattr(result, "u_right", []) or [])]
        return (max(values) if values else float("nan")), "kPa"
    if quantity == "effective":
        values = [abs(float(x)) for x in list(getattr(result, "sigma_left_eff", []) or []) + list(getattr(result, "sigma_right_eff", []) or [])]
        return (max(values) if values else float("nan")), "kPa"
    if quantity == "pressure":
        values = [abs(float(x)) for x in list(getattr(result, "p_left", []) or []) + list(getattr(result, "p_right", []) or [])]
        return (max(values) if values else float("nan")), "kPa"
    values = [abs(float(x)) for x in getattr(result, "net_pressure", [])]
    return (max(values) if values else float("nan")), "kPa"



def water_animation_quantity_x_values(result: Any, quantity: str) -> list[float]:
    """Return the x-values used by the selected water-animation diagram.

    This is used only for intelligent x-axis limits; it does not affect solver results.
    """
    if result is None:
        return []

    def arr(name):
        return list(getattr(result, name, []) or [])

    def safe_float(x):
        try:
            xf = float(x)
            return xf if math.isfinite(xf) else float("nan")
        except Exception:
            return float("nan")

    def finite(values):
        out = []
        for x in list(values or []):
            xf = safe_float(x)
            if math.isfinite(xf):
                out.append(xf)
        return out

    if quantity == "pressure":
        return finite([-safe_float(x) for x in arr("p_left")] + [safe_float(x) for x in arr("p_right")])

    if quantity == "deflection":
        return finite([-1000.0 * safe_float(x) for x in arr("deflection")])

    if quantity == "moment":
        return finite([safe_float(x) for x in arr("moment")])

    if quantity == "shear":
        return finite([safe_float(x) for x in arr("shear")])

    if quantity == "rotation":
        return finite([safe_float(x) for x in arr("rotation")])

    if quantity == "water":
        return finite([-safe_float(x) for x in arr("u_left")] + [safe_float(x) for x in arr("u_right")])

    if quantity == "effective":
        return finite([-safe_float(x) for x in arr("sigma_left_eff")] + [safe_float(x) for x in arr("sigma_right_eff")])

    return finite([safe_float(x) for x in arr("net_pressure")])


def smart_water_animation_x_range(stored_items: list[dict[str, Any]], quantity: str, fallback_result: Any = None) -> tuple[float, float]:
    """Return a readable x-range for the selected animation diagram."""
    values = []

    for item in list(stored_items or []):
        values.extend(water_animation_quantity_x_values(item.get("result"), quantity))

    if not values and fallback_result is not None:
        values.extend(water_animation_quantity_x_values(fallback_result, quantity))

    values = [float(v) for v in values if math.isfinite(float(v))]

    if not values:
        return -1.0, 1.0

    xmin, xmax = _auto_xlim([values], pad_frac=0.14)

    # x=0 is the wall and the water-level separator. Keep it visible.
    xmin = min(float(xmin), 0.0)
    xmax = max(float(xmax), 0.0)

    if abs(xmax - xmin) < 1.0e-12:
        base = max(abs(xmin), abs(xmax), 1.0)
        xmin, xmax = -base, base

    return float(xmin), float(xmax)


def mark_water_animation_auto_x() -> None:
    """Request smart x-limits after a diagram change."""
    st.session_state.water_anim_auto_x_pending = True


def water_animation_support_force_table(stored_items: list[dict[str, Any]]) -> pd.DataFrame:
    """Support/reinforcement force per stage for the water animation."""
    rows = []

    for item in list(stored_items or []):
        model_i = item.get("model")
        result_i = item.get("result")

        if model_i is None or result_i is None:
            continue

        df = _support_results_dataframe(model_i, result_i)

        if df is None or df.empty:
            continue

        df = df.drop(columns=["(z, force)"], errors="ignore")

        for _, row in df.iterrows():
            rows.append({
                "Step": item.get("step"),
                "z_w_L (m)": fmt_num(item.get("z_w_L"), 4),
                "z_w_R (m)": fmt_num(item.get("z_w_R"), 4),
                "Support": row.get("Support", "—"),
                "z_support (m)": fmt_num(row.get("z (m)"), 4),
                "Force (kN/m)": fmt_num(row.get("Force (kN/m)"), 4),
                "Source": row.get("Source", "—"),
            })

    return pd.DataFrame(rows)



def water_animation_support_force_wide_df(stored_items):
    """Compact Stage | P1 | P2 ... table."""
    rows = []
    support_codes = []

    for item in list(stored_items or []):
        row = {"Stage": int(item.get("step", len(rows) + 1))}

        model_i = item.get("model")
        result_i = item.get("result")

        supports = list(getattr(model_i, "reinforcement_supports", []) or [])

        for s in supports:
            code = str(s.get("code", "")).strip()
            if not code:
                continue

            if code not in support_codes:
                support_codes.append(code)

            try:
                force = float(support_force_for_display(s, result_i))
            except Exception:
                force = float("nan")

            row[code] = force

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    for code in support_codes:
        if code not in df.columns:
            df[code] = float("nan")

    return df[["Stage"] + support_codes]


def render_water_animation_support_forces(stored_items):
    force_df = water_animation_support_force_wide_df(stored_items)

    if force_df.empty or len(force_df.columns) <= 1:
        return

    st.markdown("#### Reinforcement/support force (kN/m) per stage")

    support_cols = [c for c in force_df.columns if c != "Stage"]

    sel_cols = st.columns([0.9] + [0.45] * len(support_cols), gap="small")

    with sel_cols[0]:
        st.markdown(
            "<div class='input-grid-header'>Select</div>",
            unsafe_allow_html=True
        )

    selected = []

    default_selected = st.session_state.get(
        "water_anim_selected_supports",
        support_cols[: min(2, len(support_cols))]
    )

    for i, code in enumerate(support_cols):
        with sel_cols[i + 1]:
            checked = st.checkbox(
                code,
                value=(code in default_selected),
                key=f"water_anim_support_select_{code}",
            )
            if checked:
                selected.append(code)

    st.session_state.water_anim_selected_supports = selected

    display_df = force_df.copy()

    for col in support_cols:
        display_df[col] = pd.to_numeric(
            display_df[col],
            errors="coerce"
        ).map(lambda v: f"{v:.3f}" if pd.notna(v) else "—")

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=min(520, 42 + 35 * len(display_df)),
    )

    if not selected:
        return

    fig_support = go.Figure()

    for code in selected:
        fig_support.add_trace(
            go.Scatter(
                x=force_df["Stage"],
                y=pd.to_numeric(force_df[code], errors="coerce"),
                mode="lines+markers",
                name=code,
                line=dict(width=2),
                marker=dict(size=7),
                hovertemplate=(
                    f"<b>{code}</b><br>"
                    "Stage: %{x}<br>"
                    "Force: %{y:.3f} kN/m<extra></extra>"
                ),
            )
        )

    fig_support.update_layout(
        title="Stage vs reinforcement/support force",
        template="plotly_white",
        height=420,
        xaxis_title="Stage",
        yaxis_title="Force (kN/m)",
        hovermode="closest",
        plot_bgcolor="#f8fafc",
        margin=dict(l=60, r=20, t=55, b=55),
    )

    fig_support.update_xaxes(
        showgrid=True,
        gridcolor="rgba(148,163,184,0.25)"
    )

    fig_support.update_yaxes(
        showgrid=True,
        gridcolor="rgba(148,163,184,0.25)"
    )

    st.plotly_chart(fig_support, use_container_width=True)



def interpolate_non_ok_water_animation_summary(summary_rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Interpolate max-response values for non-converged animation stages.

    Status remains unchanged. Only the displayed/evolution Max value is replaced
    for non-ok stages. The Comment column records the interpolation and raw value.
    """
    df = pd.DataFrame(summary_rows)

    if df.empty:
        return df

    max_cols = [c for c in df.columns if str(c).startswith("Max value")]
    if not max_cols or "Status" not in df.columns or "Step" not in df.columns:
        return df

    y_col = max_cols[0]
    df[y_col] = pd.to_numeric(df[y_col], errors="coerce")
    df["Comment"] = "—"

    def _is_finite(v) -> bool:
        try:
            return math.isfinite(float(v))
        except Exception:
            return False

    ok_mask = (
        df["Status"].astype(str).str.lower().eq("ok")
        & df[y_col].apply(_is_finite)
    )

    for idx, row in df.iterrows():
        status = str(row.get("Status", "")).lower()

        if status == "ok":
            continue

        raw_value = row.get(y_col, float("nan"))

        try:
            current_step = float(row.get("Step", idx + 1))
        except Exception:
            current_step = float(idx + 1)

        prev_ok = df.loc[(df.index < idx) & ok_mask]
        next_ok = df.loc[(df.index > idx) & ok_mask]

        interpolated = float("nan")
        comment = "not_converged; interpolation unavailable"

        if not prev_ok.empty and not next_ok.empty:
            p = prev_ok.iloc[-1]
            n = next_ok.iloc[0]

            x0 = float(p["Step"])
            y0 = float(p[y_col])
            x1 = float(n["Step"])
            y1 = float(n[y_col])

            if abs(x1 - x0) > 1.0e-12:
                interpolated = y0 + (current_step - x0) * (y1 - y0) / (x1 - x0)
            else:
                interpolated = 0.5 * (y0 + y1)

            comment = (
                f"not_converged; max value interpolated from stages "
                f"{int(x0)} and {int(x1)}; raw={fmt_num(raw_value)}"
            )

        elif not prev_ok.empty:
            p = prev_ok.iloc[-1]
            interpolated = float(p[y_col])
            comment = (
                f"not_converged; max value copied from previous converged "
                f"stage {int(float(p['Step']))}; raw={fmt_num(raw_value)}"
            )

        elif not next_ok.empty:
            n = next_ok.iloc[0]
            interpolated = float(n[y_col])
            comment = (
                f"not_converged; max value copied from next converged "
                f"stage {int(float(n['Step']))}; raw={fmt_num(raw_value)}"
            )

        if math.isfinite(interpolated):
            df.at[idx, y_col] = interpolated

        df.at[idx, "Comment"] = comment

    return df


def render_water_animation():
    st.markdown('<div class="cut-section-title">Water level animation</div>', unsafe_allow_html=True)

    base_model = st.session_state.last_model
    base_result = st.session_state.last_result
    if base_model is None or base_result is None:
        st.info("Run a solver first.")
        return

    H_R = float(base_model.geometry.H_R)
    H_L = float(base_model.geometry.H_L)
    z_left_surface = H_R - H_L

    if st.session_state.get("water_anim_z_final_left") is None:
        st.session_state.water_anim_z_final_left = float(z_left_surface)
    if st.session_state.get("water_anim_z_final_right") is None:
        st.session_state.water_anim_z_final_right = 0.0
    st.session_state.setdefault("water_anim_plot_type", "Total horizontal pressure")
    st.session_state.setdefault("water_anim_mode", "Uniform rise")
    st.session_state.setdefault("water_anim_steps", 15)
    st.session_state.setdefault("water_anim_speed_ms", 650)
    stored_items_for_range = list(st.session_state.get("water_anim_results", []) or [])
    selected_quantity_for_range = WATER_PLOT_OPTIONS.get(
        st.session_state.get("water_anim_plot_type", "Total horizontal pressure"),
        "pressure",
    )

    if (
        st.session_state.get("water_anim_x_min") is None
        or st.session_state.get("water_anim_x_max") is None
        or bool(st.session_state.get("water_anim_auto_x_pending", False))
    ):
        auto_x_min, auto_x_max = smart_water_animation_x_range(
            stored_items_for_range,
            selected_quantity_for_range,
            base_result,
        )
        st.session_state.water_anim_x_min = auto_x_min
        st.session_state.water_anim_x_max = auto_x_max
        st.session_state.ui_water_anim_x_min = auto_x_min
        st.session_state.ui_water_anim_x_max = auto_x_max
        st.session_state.water_anim_auto_x_pending = False

    st.markdown("#### Animation controls")

    h1, h2, h3, h4, h5 = st.columns([1.30, 1.20, 0.75, 0.85, 0.85], gap="small")
    with h1:
        st.markdown("<div class='input-grid-header'>Diagram</div>", unsafe_allow_html=True)
    with h2:
        st.markdown("<div class='input-grid-header'>Water rise mode</div>", unsafe_allow_html=True)
    with h3:
        st.markdown("<div class='input-grid-header'>Number of steps</div>", unsafe_allow_html=True)
    with h4:
        st.markdown("<div class='input-grid-header'>z_final_left (m)</div>", unsafe_allow_html=True)
    with h5:
        st.markdown("<div class='input-grid-header'>z_final_right (m)</div>", unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns([1.30, 1.20, 0.75, 0.85, 0.85], gap="small")
    with c1:
        quantity_name = st.selectbox(
            "Diagram",
            list(WATER_PLOT_OPTIONS.keys()),
            key="water_anim_plot_type",
            label_visibility="collapsed",
            on_change=mark_water_animation_auto_x,
        )
    with c2:
        mode = st.selectbox("Water rise mode", ["Uniform rise", "Simultaneous proportional rise"], key="water_anim_mode", label_visibility="collapsed")
    with c3:
        n_steps = st.number_input("Number of steps", min_value=2, max_value=100, step=1, key="water_anim_steps", label_visibility="collapsed", help="Number of water-level positions used in the animation.")
    with c4:
        z_final_left = st.number_input("z_final_left (m)", min_value=float(z_left_surface), max_value=float(H_R), step=0.5, format="%.4g", key="water_anim_z_final_left", label_visibility="collapsed", help="Default is the left/excavation ground surface.")
    with c5:
        z_final_right = st.number_input("z_final_right (m)", min_value=0.0, max_value=float(H_R), step=0.5, format="%.4g", key="water_anim_z_final_right", label_visibility="collapsed", help="Default is the right/retained ground surface.")

    h1, h2, h3, h4 = st.columns([0.85, 0.85, 0.85, 2.5], gap="small")
    with h1:
        st.markdown("<div class='input-grid-header'>Frame duration (ms)</div>", unsafe_allow_html=True)
    with h2:
        st.markdown("<div class='input-grid-header'>x_min</div>", unsafe_allow_html=True)
    with h3:
        st.markdown("<div class='input-grid-header'>x_max</div>", unsafe_allow_html=True)
    with h4:
        st.markdown("<div class='input-grid-header'>Notes</div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([0.85, 0.85, 0.85, 2.5], gap="small")
    with c1:
        speed_ms = st.number_input("Frame duration (ms)", min_value=100, max_value=5000, step=100, key="water_anim_speed_ms", label_visibility="collapsed", help="Delay between animation frames. Larger values make the animation slower.")
    with c2:
        x_min = st.number_input("x_min", step=1.0, format="%.4g", key="ui_water_anim_x_min", label_visibility="collapsed", help="Manual left plotting limit. Leave the automatic value unless you need extra horizontal space.")
    with c3:
        x_max = st.number_input("x_max", step=1.0, format="%.4g", key="ui_water_anim_x_max", label_visibility="collapsed", help="Manual right plotting limit. Increase it when long reinforcement elements need to be shown.")
    with c4:
        st.caption(
            "x_min/x_max are selected intelligently whenever the diagram changes; they can still be adjusted manually. "
            "Run once for the selected water-level sequence, then use the Diagram dropdown without rerunning."
        )

    # Copy widget values to canonical variables. Do not write to ui_* after this point.
    try:
        st.session_state.water_anim_x_min = float(x_min)
        st.session_state.water_anim_x_max = float(x_max)
    except Exception:
        pass

    if float(x_min) >= 0.0 or float(x_max) <= 0.0 or float(x_min) >= float(x_max):
        st.warning("For water animation, use x_min < 0 < x_max so that x=0 is the wall/water-level separator.")

    quantity = WATER_PLOT_OPTIONS[quantity_name]

    if st.button("Run water level animation", key="run_water_animation", type="primary", use_container_width=True):
        levels = build_water_animation_levels(H_R, H_L, float(z_final_left), float(z_final_right), int(n_steps), str(mode))
        progress = st.progress(0.0, text="Running water-level sequence...")
        stored_items = []
        summary_base = []
        old_zL = st.session_state.z_w_L
        old_zR = st.session_state.z_w_R
        try:
            for i, (zL, zR) in enumerate(levels):
                progress.progress((i + 1) / len(levels), text=f"Step {i + 1}/{len(levels)}")
                zL_solver, zR_solver = _animation_solver_water_levels(
                    float(zL),
                    float(zR),
                    H_R,
                    H_L,
                )

                st.session_state.z_w_L = zL_solver
                st.session_state.z_w_R = zR_solver

                model_i = build_model()
                result_i = cached_solve(model_i)

                stored_items.append({
                    "step": i + 1,
                    "z_w_L": float(zL),
                    "z_w_R": float(zR),
                    "z_w_L_solver": float(zL_solver),
                    "z_w_R_solver": float(zR_solver),
                    "model": model_i,
                    "result": result_i,
                })

                summary_base.append({
                    "Step": i + 1,
                    "z_w_L (m)": float(zL),
                    "z_w_R (m)": float(zR),
                })
        finally:
            st.session_state.z_w_L = old_zL
            st.session_state.z_w_R = old_zR
        progress.empty()
        st.session_state.water_anim_results = stored_items
        st.session_state.water_anim_summary = summary_base
        st.session_state.water_anim_levels = levels

        auto_x_min, auto_x_max = smart_water_animation_x_range(stored_items, quantity, base_result)
        st.session_state.water_anim_x_min = auto_x_min
        st.session_state.water_anim_x_max = auto_x_max

    stored_items = list(st.session_state.get("water_anim_results", []) or [])
    if not stored_items:
        st.info("Press 'Run water level animation' to generate the stored water-level cases.")
        return

    frames = []
    summary_rows = []
    for item in stored_items:
        result_i = item["result"]
        model_i = item["model"]
        zL = float(item["z_w_L"])
        zR = float(item["z_w_R"])
        fig_i = plot_water_animation_frame(result_i, model_i, quantity, zL, zR, float(x_min), float(x_max))
        frames.append(go.Frame(name=str(item["step"]), data=list(fig_i.data), layout=go.Layout(shapes=fig_i.layout.shapes, title=fig_i.layout.title)))
        max_value, unit = max_response_for_quantity(result_i, quantity)
        status = str(getattr(result_i, "status", ""))
        summary_rows.append({"Step": item["step"], "z_w_L (m)": zL, "z_w_R (m)": zR, f"Max value ({unit})": max_value, "Status": status})

    first_fig = plot_water_animation_frame(stored_items[0]["result"], stored_items[0]["model"], quantity, float(stored_items[0]["z_w_L"]), float(stored_items[0]["z_w_R"]), float(x_min), float(x_max))
    first_fig.frames = frames
    first_fig.update_layout(
        updatemenus=[dict(type="buttons", showactive=False, x=0.02, y=-0.12, xanchor="left", yanchor="top", buttons=[
            dict(label="Play", method="animate", args=[None, {"frame": {"duration": int(speed_ms), "redraw": True}, "transition": {"duration": 0}, "fromcurrent": True}]),
            dict(label="Pause", method="animate", args=[[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}]),
        ])],
        sliders=[dict(active=0, x=0.18, y=-0.10, len=0.78, currentvalue=dict(prefix="Step "), steps=[
            dict(label=str(item["step"]), method="animate", args=[[str(item["step"])], {"frame": {"duration": 0, "redraw": True}, "transition": {"duration": 0}, "mode": "immediate"}])
            for item in stored_items
        ])],
        margin=dict(l=60, r=20, t=75, b=95),
    )

    st.markdown("#### Animation")
    st.plotly_chart(first_fig, use_container_width=True)

    summary_df = interpolate_non_ok_water_animation_summary(summary_rows)
    st.markdown("#### Evolution of maximum value")
    y_col = [c for c in summary_df.columns if c.startswith("Max value")][0]
    fig_evol = go.Figure()
    hover_text = []
    for _, row in summary_df.iterrows():
        comment = str(row.get("Comment", "—"))
        status = str(row.get("Status", ""))
        if comment and comment != "—":
            hover_text.append(f"Status: {status}<br>{comment}")
        else:
            hover_text.append(f"Status: {status}")

    fig_evol.add_trace(go.Scatter(
        x=summary_df["Step"],
        y=summary_df[y_col],
        mode="lines+markers",
        line=dict(color="black", width=2),
        marker=dict(size=7),
        text=hover_text,
        hovertemplate="Step: %{x}<br>" + y_col + ": %{y:.3f}<br>%{text}<extra></extra>",
    ))
    fig_evol.update_layout(title="Step vs maximum response", template="plotly_white", height=420, xaxis_title="Step", yaxis_title=y_col, plot_bgcolor="#f8fafc")
    fig_evol.update_xaxes(showgrid=True, gridcolor="rgba(148,163,184,0.25)")
    fig_evol.update_yaxes(showgrid=True, gridcolor="rgba(148,163,184,0.25)")
    st.plotly_chart(fig_evol, use_container_width=True)

    st.markdown("#### Water-level sequence table")
    st.dataframe(summary_df, use_container_width=True, hide_index=True, height=min(520, 42 + 35 * len(summary_df)))

    render_water_animation_support_forces(stored_items)


# -----------------------------------------------------------------------------
# Excavation stages and stage animation
# -----------------------------------------------------------------------------
def _as_float(x, default=0.0):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def default_stage_depths(H_R: float, H_L: float, n: int) -> pd.DataFrame:
    z_ex = max(0.0, float(H_R) - float(H_L))
    n = max(1, int(n))
    return pd.DataFrame({
        "Stage": [f"Stage {i+1}" for i in range(n)],
        "z excavation level (m)": [z_ex * (i + 1) / n for i in range(n)],
    })


def normalize_stage_df(df: pd.DataFrame | None, H_R: float, H_L: float, n: int) -> pd.DataFrame:
    z_ex = max(0.0, float(H_R) - float(H_L))
    n = max(1, int(n))
    if df is None or len(pd.DataFrame(df)) == 0:
        out = default_stage_depths(H_R, H_L, n)
    else:
        raw = pd.DataFrame(df).copy()
        values = []
        if "z excavation level (m)" in raw.columns:
            values = [_as_float(v, float("nan")) for v in raw["z excavation level (m)"].tolist()]
        values = [v for v in values if math.isfinite(v)]
        defaults = default_stage_depths(H_R, H_L, n)["z excavation level (m)"].tolist()
        values = (values + defaults)[:n]
        values = [max(0.0, min(z_ex, float(v))) for v in values]
        # Enforce top-to-bottom order and force the last excavation stage to the final excavation level.
        values = sorted(values)
        if len(values) < n:
            values += defaults[len(values):]
        values[-1] = z_ex
        for i in range(1, n):
            if values[i] < values[i-1]:
                values[i] = values[i-1]
        out = pd.DataFrame({"Stage": [f"Stage {i+1}" for i in range(n)], "z excavation level (m)": values})
    out = out.iloc[:n].copy().reset_index(drop=True)
    out["Stage"] = [f"Stage {i+1}" for i in range(n)]
    out.loc[n-1, "z excavation level (m)"] = z_ex
    return out


def _layers_with_total_height(layers: list[Any], target_height: float) -> list[Any]:
    """Return a copy of layers with total thickness adjusted at the top layer."""
    target_height = max(1.0e-9, float(target_height))
    out = deepcopy(list(layers or []))
    if not out:
        return [solvers.SoilLayer(code="SL1", thickness=target_height, c_prime=0.001, phi_prime_deg=30.0, gamma=20.0, gamma_sat=20.0, E_s=20000.0, nu=0.30)]
    total = sum(max(0.0, float(getattr(l, "thickness", 0.0))) for l in out)
    delta = target_height - total
    if delta >= 0.0:
        out[0].thickness = max(1.0e-9, float(out[0].thickness) + delta)
        return out
    # Trim from the top downward if required.
    remaining_cut = -delta
    trimmed = []
    for layer in out:
        th = max(0.0, float(getattr(layer, "thickness", 0.0)))
        if remaining_cut >= th:
            remaining_cut -= th
            continue
        new_layer = deepcopy(layer)
        new_layer.thickness = max(1.0e-9, th - remaining_cut)
        remaining_cut = 0.0
        trimmed.append(new_layer)
    return trimmed or [deepcopy(out[-1])]


def model_for_excavation_stage(base_model: Any, z_exc_stage: float, active_count: int, qL_active: bool = True, qR_active: bool = True) -> Any:
    H_R = float(base_model.geometry.H_R)
    H_L_stage = max(1.0e-9, H_R - float(z_exc_stage))
    supports_all = sorted(list(getattr(base_model, "reinforcement_supports", []) or []), key=lambda s: float(s.get("z", 0.0) or 0.0))
    supports_active = deepcopy(supports_all[:max(0, int(active_count))])
    return solvers.ModelInput(
        geometry=solvers.GeometryInput(H_R=H_R, H_L=H_L_stage, z_p=float(base_model.geometry.z_p)),
        left=solvers.SideInput(beta_deg=float(base_model.left.beta_deg), q=(float(base_model.left.q) if qL_active else 0.0), z_w=max(float(base_model.left.z_w), float(z_exc_stage))),
        right=solvers.SideInput(beta_deg=float(base_model.right.beta_deg), q=(float(base_model.right.q) if qR_active else 0.0), z_w=float(base_model.right.z_w)),
        seismic=deepcopy(base_model.seismic),
        movement=deepcopy(base_model.movement),
        wall=deepcopy(base_model.wall),
        controls=deepcopy(base_model.controls),
        gamma_w=float(base_model.gamma_w),
        left_layers=_layers_with_total_height(list(base_model.left_layers or []), H_L_stage),
        right_layers=deepcopy(list(base_model.right_layers or [])),
        reinforcement_supports=supports_active,
        solver_mode=str(base_model.solver_mode),
    )


def _stage_load_index_from_text(text: str, n: int, default: int = 0) -> int:
    txt = str(text or "").strip()
    if "N+1" in txt or "after final" in txt:
        return int(n) + 1
    if "N" in txt and "final" in txt:
        return int(n)
    m = re.search(r"(-?\d+)", txt)
    if m:
        return max(0, min(int(n) + 1, int(m.group(1))))
    return int(default)


def build_stage_sequence(stage_depths: list[float], n_intermediate: int, qL_apply_stage: int | None = None, qR_apply_stage: int | None = None) -> list[dict[str, Any]]:
    """Build the staged excavation path, aligned with the desktop version.

    The first frame is always Stage 0: original ground, z=0, no excavation and
    no supports active. Intermediate drops before main Stage i keep only
    supports 1..i-1 active. q_L/q_R become active from their selected
    construction load index; Stage N+1 is added when a surcharge is applied
    after the final excavation.
    """
    depths = [float(z) for z in stage_depths]
    n_intermediate = max(0, int(n_intermediate))
    n = len(depths)
    qL_stage = int(n + 1 if qL_apply_stage is None else qL_apply_stage)
    qR_stage = int(0 if qR_apply_stage is None else qR_apply_stage)
    rows = [{"label": "Stage 0", "z": 0.0, "main_stage": 0, "active_supports": 0, "kind": "stage0", "load_index": 0, "qL_active": 0 >= qL_stage, "qR_active": 0 >= qR_stage}]
    prev_z = 0.0
    for i, z in enumerate(depths, start=1):
        if n_intermediate > 0:
            for j in range(n_intermediate):
                t = (j + 1) / (n_intermediate + 1)
                zi = prev_z + t * (z - prev_z)
                prefix = i - 1
                rows.append({"label": f"Stage {prefix}.{j+1}", "z": zi, "main_stage": i - 1, "active_supports": max(0, i - 1), "kind": "substage", "load_index": i - 1, "qL_active": (i - 1) >= qL_stage, "qR_active": (i - 1) >= qR_stage})
        label = f"Stage {i}" + (" (final)" if i == n else "")
        rows.append({"label": label, "z": z, "main_stage": i, "active_supports": i, "kind": "stage", "load_index": i, "qL_active": i >= qL_stage, "qR_active": i >= qR_stage})
        prev_z = z
    if qL_stage == n + 1 or qR_stage == n + 1:
        rows.append({"label": f"Stage {n+1} (post-excavation loading)", "z": prev_z, "main_stage": n + 1, "active_supports": n, "kind": "post_loading", "load_index": n + 1, "qL_active": (n + 1) >= qL_stage, "qR_active": (n + 1) >= qR_stage})
    return rows


def stage_chart_traces(result: Any, quantity: str):
    z = list(getattr(result, "z", []) or [])
    def arr(name):
        return list(getattr(result, name, []) or [])
    def safe(vals, scale=1.0, sign=1.0):
        out=[]
        for v in vals:
            try: out.append(sign*scale*float(v))
            except Exception: out.append(float("nan"))
        return out
    if quantity == "pressure":
        pressure_series = total_pressure_animation_series(result)
        return [(name, values, "kPa") for name, values in pressure_series], "Total horizontal pressure"
    if quantity == "deflection":
        return [("Δx", safe(arr("deflection"), scale=1000.0, sign=-1.0), "mm")], "Deflection"
    if quantity == "moment":
        return [("M", safe(arr("moment")), "kNm/m")], "Moment"
    if quantity == "shear":
        return [("V", safe(arr("shear")), "kN/m")], "Shear"
    if quantity == "rotation":
        return [("rotation", safe(arr("rotation")), "deg")], "Rotation"
    if quantity == "water":
        return [("u_L", safe(arr("u_left"), sign=-1.0), "kPa"), ("u_R", safe(arr("u_right")), "kPa")], "Water stresses"
    if quantity == "effective":
        return [("σh,L", safe(arr("sigma_left_eff"), sign=-1.0), "kPa"), ("σh,R", safe(arr("sigma_right_eff")), "kPa")], "Effective stresses"
    return [("p_net", safe(arr("net_pressure")), "kPa")], "Net pressure"


def plot_stage_animation_frame(item: dict[str, Any], quantity: str, x_range: tuple[float, float] | None = None) -> go.Figure:
    model = item["model"]
    result = item["result"]
    H_R = float(model.geometry.H_R)
    z_stage = float(item["z"])
    active_supports = list(getattr(model, "reinforcement_supports", []) or [])
    all_supports = list(item.get("all_supports", []) or [])
    traces, chart_title = stage_chart_traces(result, quantity)

    fig = make_subplots(rows=1, cols=2, column_widths=[0.42, 0.58], horizontal_spacing=0.08, subplot_titles=("Geometry / active supports", chart_title))

    # Geometry panel
    x_left = -max(3.0, 0.60 * H_R)
    max_L = max([float(s.get("L", 0.0) or 0.0) for s in all_supports] + [0.6 * H_R])
    x_right = max(3.0, 0.75 * max_L, 0.6 * H_R)
    fig.add_trace(go.Scatter(x=[0, 0], y=[0, H_R], mode="lines", line=dict(color="black", width=4), name="Wall", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=[0, x_right], y=[0, 0], mode="lines", line=dict(color="saddlebrown", width=3), name="Retained ground", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=[x_left, 0], y=[z_stage, z_stage], mode="lines", line=dict(color="saddlebrown", width=3), name="Excavation level", showlegend=False), row=1, col=1)
    # dashed future/main stage references
    for srow in item.get("stage_depths", []):
        zz = float(srow)
        fig.add_trace(go.Scatter(x=[x_left, 0], y=[zz, zz], mode="lines", line=dict(color="rgba(120,72,36,0.45)", width=1.4, dash="dash"), showlegend=False, hoverinfo="skip"), row=1, col=1)

    # inactive supports faint, active supports solid with force labels
    active_codes = {str(s.get("code", "")) for s in active_supports}
    for support in all_supports:
        z = float(support.get("z", 0.0) or 0.0)
        code = str(support.get("code", "S"))
        L = max(1.0, float(support.get("L", support.get("Lf", 3.0)) or 3.0))
        theta = math.radians(float(support.get("theta_deg", 0.0) or 0.0))
        x2 = L * math.cos(theta)
        y2 = z - L * math.sin(theta)
        active = code in active_codes
        color = "#b45309" if active else "rgba(148,163,184,0.45)"
        width = 3 if active else 1.5
        dash = None if active else "dot"
        fig.add_trace(go.Scatter(x=[0, x2], y=[z, y2], mode="lines+markers", line=dict(color=color, width=width, dash=dash), marker=dict(size=6), showlegend=False, hovertemplate=f"{code}<extra></extra>"), row=1, col=1)
        if active:
            try:
                f = support_force_for_display(support, result)
                txt = f"{code}: {f:.1f} kN/m"
            except Exception:
                txt = f"{code}: active"
            fig.add_annotation(x=x2, y=y2, text=txt, showarrow=False, xanchor="left", yanchor="middle", font=dict(size=11, color="#7c2d12"), row=1, col=1)
        else:
            fig.add_annotation(x=x2, y=y2, text=f"{code} inactive", showarrow=False, xanchor="left", yanchor="middle", font=dict(size=10, color="#64748b"), row=1, col=1)

    fig.add_annotation(x=x_left * 0.98, y=z_stage, text=item["label"], showarrow=False, xanchor="left", yanchor="bottom", font=dict(size=12, color="#7c2d12"), row=1, col=1)

    # Chart panel
    zres = list(getattr(result, "z", []) or [])
    allx = []
    for i, (name, values, unit) in enumerate(traces):
        allx.extend([v for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))])
        if quantity == "pressure" and i < 2:
            xs, zs = _finite_pairs(values, zres)
            if xs:
                fig.add_trace(
                    go.Scatter(
                        x=[0.0] * len(zs) + xs[::-1],
                        y=zs + zs[::-1],
                        fill="toself",
                        fillcolor="rgba(90, 90, 90, 0.16)",
                        line=dict(width=0),
                        hoverinfo="skip",
                        showlegend=False,
                        name=f"{name} shaded area",
                    ),
                    row=1,
                    col=2,
                )
        color, dash, width = _plotly_style(name)
        legend_name = str(name).strip()
        show_this_legend = bool(quantity == "pressure" and i >= 2)
        if quantity == "pressure" and i >= 2:
            existing_names = {
                tr.name for tr in fig.data
                if getattr(tr, "showlegend", False)
            }
            if legend_name in existing_names:
                show_this_legend = False
        fig.add_trace(
            go.Scatter(
                x=values,
                y=zres,
                mode="lines",
                name=legend_name,
                showlegend=show_this_legend,
                legendgroup=legend_name,
                line=dict(color=color, dash=dash, width=width),
            ),
            row=1,
            col=2,
        )
    if x_range is None:
        if allx:
            m = max(abs(min(allx)), abs(max(allx)), 1.0)
            x_range = (-1.15*m, 1.15*m)
        else:
            x_range = (-1.0, 1.0)
    unit = traces[0][2] if traces else ""
    fig.update_xaxes(title_text="x (m)", range=[x_left, x_right], row=1, col=1, zeroline=False)
    fig.update_yaxes(title_text="z (m)", range=[H_R, 0], row=1, col=1)
    fig.update_xaxes(title_text=unit, range=list(x_range), row=1, col=2, zeroline=True, zerolinecolor="rgba(0,0,0,0.35)")
    fig.update_yaxes(title_text="z (m)", range=[H_R, 0], row=1, col=2)
    fig.update_layout(template="plotly_white", height=640, margin=dict(l=35, r=20, t=78, b=80), title=dict(text=f"Stages animation — {item['label']} | z={z_stage:.3f} m | active supports={len(active_supports)} | q_L={'on' if item.get('qL_active') else 'off'} | q_R={'on' if item.get('qR_active') else 'off'} | status={getattr(result, 'status', '')}", x=0.5))
    if quantity == "pressure":
        fig.update_layout(
            showlegend=True,
            legend=dict(
                x=0.47,
                y=0.96,
                xanchor="left",
                yanchor="top",
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor="rgba(203,213,225,0.95)",
                borderwidth=1,
                font=dict(size=11),
            ),
        )
    return fig


def stage_animation_x_range(items: list[dict[str, Any]], quantity: str) -> tuple[float, float]:
    vals=[]
    for item in list(items or []):
        traces, _ = stage_chart_traces(item.get("result"), quantity)
        for _, xs, _ in traces:
            vals.extend([float(v) for v in xs if isinstance(v, (int,float)) and math.isfinite(float(v))])
    if not vals:
        return (-1.0, 1.0)
    xmin, xmax = _auto_xlim([vals], pad_frac=0.14)
    xmin = min(float(xmin), 0.0)
    xmax = max(float(xmax), 0.0)
    if abs(xmax - xmin) < 1.0e-12:
        base = max(abs(xmin), abs(xmax), 1.0)
        xmin, xmax = -base, base
    return (float(xmin), float(xmax))


def smart_stage_animation_x_range(stored_items, quantity, last_result=None):
    """
    Smart x-range for stage animation.

    It derives x_min/x_max from the actual plotted MAIN traces only.
    Dashed limit/reference curves such as At-rest, Active and Passive
    are deliberately ignored.
    """

    xs = []

    skip_words = (
        "at-rest",
        "at rest",
        "active",
        "passive",
        "limit",
        "k0",
        "ka",
        "kp",
    )

    def _is_reference_trace(trace):
        name = str(getattr(trace, "name", "") or "").lower()

        if any(w in name for w in skip_words):
            return True

        line = getattr(trace, "line", None)
        dash = getattr(line, "dash", None) if line is not None else None

        if dash not in (None, "", "solid"):
            return True

        return False

    for item in stored_items or []:
        try:
            fig_tmp = plot_stage_animation_frame(
                item,
                quantity,
                (-1.0e12, 1.0e12),
            )
        except Exception:
            continue

        for tr in fig_tmp.data:
            if _is_reference_trace(tr):
                continue

            x = getattr(tr, "x", None)
            if x is None:
                continue

            try:
                arr = np.asarray(x, dtype=float).ravel()
                arr = arr[np.isfinite(arr)]
                if arr.size:
                    xs.extend(arr.tolist())
            except Exception:
                continue

    vals = np.asarray(xs, dtype=float)
    vals = vals[np.isfinite(vals)]

    if vals.size == 0:
        return -1.0, 1.0

    xmin = float(np.nanmin(vals))
    xmax = float(np.nanmax(vals))

    if abs(xmax - xmin) < 1e-12:
        pad = max(1.0, abs(xmax) * 0.25)
        xmin -= pad
        xmax += pad
    else:
        pad = 0.15 * (xmax - xmin)
        xmin -= pad
        xmax += pad

    xmin = min(xmin, 0.0)
    xmax = max(xmax, 0.0)

    return xmin, xmax


def mark_stage_animation_auto_x() -> None:
    """Request smart x-limits after a stage-animation diagram change."""
    st.session_state.stage_anim_auto_x_pending = True


def render_stages_and_reinforcement(model_preview: Any):
    st.markdown(
        '<div class="cut-section-title" style="margin-top:1.05rem; margin-bottom:.85rem;">Stages and reinforcement</div>',
        unsafe_allow_html=True
    )
    base_model = model_preview or build_model()
    H_R = float(base_model.geometry.H_R)
    H_L = float(base_model.geometry.H_L)
    z_ex = max(0.0, H_R - H_L)
    left, right = st.columns([0.42, 0.58], gap="large")
    with left:
        st.markdown(
            '<div class="cut-stage-heading">Excavation stages</div>',
            unsafe_allow_html=True
        )
        st.caption(f"Total excavation depth: z_ex = H_R − H_L = {z_ex:.4g} m")
        st.markdown('<div class="cut-visible-field-label">Number of main excavation stages</div>', unsafe_allow_html=True)
        n = st.number_input("Number of main excavation stages", min_value=1, max_value=30, step=1, key="n_excavation_stages", label_visibility="collapsed", help="Number of principal excavation levels after Stage 0. Stage 0 is no excavation/no supports; the final stage is locked to z_ex = H_R − H_L.")
        st.markdown('<div class="cut-visible-field-label">Intermediate excavation drops between main stages</div>', unsafe_allow_html=True)
        st.number_input("Intermediate excavation drops between main stages", min_value=0, max_value=20, step=1, key="intermediate_stage_drops", label_visibility="collapsed", help="Optional lowering steps inserted before each main stage. Example: 4 creates four drops before Stage i, with only supports 1..i−1 active until Stage i is reached.")
        st.markdown(
            '<div class="cut-stage-subheading">Surcharge staging</div>',
            unsafe_allow_html=True
        )
        qR_options = [f"Stage {i}" for i in range(0, int(n) + 1)] + [f"Stage {int(n)+1} (after final)"]
        if st.session_state.get("stage_q_R_apply", "Stage 0") not in qR_options:
            st.session_state.stage_q_R_apply = "Stage 0"
        qcols = st.columns(2)
        with qcols[0]:
            st.markdown('<div class="cut-visible-field-label">Apply q_L at stage:</div>', unsafe_allow_html=True)
            st.selectbox("Apply q_L at stage:", ["Stage N (final)", "Stage N+1 (after final)"], key="stage_q_L_apply", label_visibility="collapsed", help="Select whether the excavation-side surcharge q_L is present at the final excavation stage or is added afterward as a separate post-excavation loading stage. Default: Stage N+1.")

        with qcols[1]:
            st.markdown('<div class="cut-visible-field-label">Apply q_R at stage:</div>', unsafe_allow_html=True)
            st.selectbox("Apply q_R at stage:", qR_options, key="stage_q_R_apply", label_visibility="collapsed", help="Construction stage from which the retained-side surcharge q_R becomes active. Stage 0 means it exists from the initial ground condition.")
        stage_df = normalize_stage_df(st.session_state.get("stages_df"), H_R, H_L, int(n))
        locked = stage_df.copy()
        locked["Locked final"] = [False] * (len(locked)-1) + [True]
        locked = _cut_editor_text_df(locked, exclude_cols=["Stage", "Locked final"])
        edited = st.data_editor(
            locked,
            hide_index=True,
            num_rows="fixed",
            use_container_width=True,
            key="stages_editor",
            height=min(420, 42 + 36 * len(locked)),
            disabled=["Stage", "Locked final"],
            column_config={
                "z excavation level (m)": st.column_config.TextColumn("z excavation level (m)", width="medium"),
                "Locked final": st.column_config.CheckboxColumn("final", width="small"),
            },
        )
        cleaned = normalize_stage_df(edited.drop(columns=["Locked final"], errors="ignore"), H_R, H_L, int(n))
        st.session_state.stages_df = cleaned
        st.caption("Stage 0 is the initial ground-surface/no-excavation state. Stage 1 is the first excavation line. The final stage is locked to z_ex.")
    with right:
        st.markdown("#### Reinforcement")
        render_reinforcement(base_model)


def render_stages_animation():
    st.markdown('<div class="cut-section-title">Stages animation</div>', unsafe_allow_html=True)

    base_model = build_model()
    H_R = float(base_model.geometry.H_R)
    H_L = float(base_model.geometry.H_L)
    z_ex = max(0.0, H_R - H_L)

    n = max(1, int(st.session_state.get("n_excavation_stages", 1)))
    n_inter = max(0, int(st.session_state.get("intermediate_stage_drops", 0)))

    stage_df = normalize_stage_df(
        st.session_state.get("stages_df"),
        H_R,
        H_L,
        n,
    )
    st.session_state.stages_df = stage_df

    stored_items_for_range = list(
        st.session_state.get("stage_anim_results", []) or []
    )

    selected_quantity_for_range = WATER_PLOT_OPTIONS.get(
        st.session_state.get(
            "stage_anim_plot_type",
            "Total horizontal pressure",
        ),
        "pressure",
    )

    # ==========================================================
    # SMART AUTO XRANGE
    # ==========================================================
    if (
        st.session_state.get("stage_anim_x_min") is None
        or st.session_state.get("stage_anim_x_max") is None
        or bool(st.session_state.get("stage_anim_auto_x_pending", False))
    ):

        auto_x_min, auto_x_max = smart_stage_animation_x_range(
            stored_items_for_range,
            selected_quantity_for_range,
            st.session_state.get("last_result"),
        )

        st.session_state.stage_anim_x_min = auto_x_min
        st.session_state.stage_anim_x_max = auto_x_max

        # IMPORTANT:
        # initialize widget values ONLY BEFORE widget creation
        if "ui_stage_anim_x_min" not in st.session_state:
            st.session_state.ui_stage_anim_x_min = auto_x_min

        if "ui_stage_anim_x_max" not in st.session_state:
            st.session_state.ui_stage_anim_x_max = auto_x_max

        st.session_state.stage_anim_auto_x_pending = False

    # ==========================================================
    # HEADERS
    # ==========================================================
    h1, h2, h3, h4 = st.columns(
        [1.30, 0.85, 0.85, 2.5],
        gap="small",
    )

    with h1:
        st.markdown(
            "<div class='input-grid-header'>Diagram</div>",
            unsafe_allow_html=True,
        )

    with h2:
        st.markdown(
            "<div class='input-grid-header'>Frame duration (ms)</div>",
            unsafe_allow_html=True,
        )

    with h3:
        st.markdown(
            "<div class='input-grid-header'>x_min</div>",
            unsafe_allow_html=True,
        )

    with h4:
        st.markdown(
            "<div class='input-grid-header'>x_max / notes</div>",
            unsafe_allow_html=True,
        )

    # ==========================================================
    # CONTROLS
    # ==========================================================
    c1, c2, c3, c4 = st.columns(
        [1.30, 0.85, 0.85, 2.5],
        gap="small",
    )

    with c1:
        quantity_name = st.selectbox(
            "Diagram",
            list(WATER_PLOT_OPTIONS.keys()),
            key="stage_anim_plot_type",
            label_visibility="collapsed",
            on_change=mark_stage_animation_auto_x,
        )

    with c2:
        speed_ms = st.number_input(
            "Frame duration (ms)",
            min_value=100,
            max_value=5000,
            step=100,
            key="stage_anim_speed_ms",
            label_visibility="collapsed",
            help="Delay between stage-animation frames. Larger values make the animation slower.",
        )

    with c3:
        x_min = st.number_input(
            "x_min",
            step=1.0,
            format="%.4g",
            key="ui_stage_anim_x_min",
            label_visibility="collapsed",
            help="Manual left plotting limit.",
        )

    with c4:
        x_max = st.number_input(
            "x_max",
            step=1.0,
            format="%.4g",
            key="ui_stage_anim_x_max",
            label_visibility="collapsed",
            help="Manual right plotting limit.",
        )

        st.caption(
            "x_min/x_max are selected intelligently whenever the diagram changes; "
            "they can still be adjusted manually. "
            "Run once for the selected excavation-stage sequence, "
            "then use the Diagram dropdown without rerunning."
        )

    # ==========================================================
    # SAVE MANUAL VALUES
    # ==========================================================
    try:
        st.session_state.stage_anim_x_min = float(x_min)
        st.session_state.stage_anim_x_max = float(x_max)
    except Exception:
        pass

    if float(x_min) >= float(x_max):
        st.warning("For stage animation, use x_min < x_max.")

    st.caption(
        "The geometry animation and the selected diagram use the same frames "
        "and the same slider. Intermediate drops keep the support set "
        "of the preceding main stage."
    )

    # ==========================================================
    # RUN BUTTON
    # ==========================================================
    if st.button(
        "Run stages animation",
        key="run_stages_animation",
        type="primary",
        use_container_width=True,
    ):

        qL_apply_stage = _stage_load_index_from_text(
            st.session_state.get(
                "stage_q_L_apply",
                "Stage N+1 (after final)",
            ),
            n,
            default=n + 1,
        )

        qR_apply_stage = _stage_load_index_from_text(
            st.session_state.get(
                "stage_q_R_apply",
                "Stage 0",
            ),
            n,
            default=0,
        )

        seq = build_stage_sequence(
            stage_df["z excavation level (m)"].tolist(),
            n_inter,
            qL_apply_stage=qL_apply_stage,
            qR_apply_stage=qR_apply_stage,
        )

        progress = st.progress(
            0.0,
            text="Running staged excavation sequence...",
        )

        stored = []

        all_supports = sorted(
            list(getattr(base_model, "reinforcement_supports", []) or []),
            key=lambda s: float(s.get("z", 0.0) or 0.0),
        )

        try:
            for i, row in enumerate(seq):

                progress.progress(
                    (i + 1) / max(1, len(seq)),
                    text=f"{row['label']} ({i+1}/{len(seq)})",
                )

                model_i = model_for_excavation_stage(
                    base_model,
                    float(row["z"]),
                    int(row["active_supports"]),
                    bool(row.get("qL_active", True)),
                    bool(row.get("qR_active", True)),
                )

                result_i = cached_solve(model_i)

                stored.append({
                    **row,
                    "step": i + 1,
                    "model": model_i,
                    "result": result_i,
                    "all_supports": all_supports,
                    "stage_depths": stage_df["z excavation level (m)"].tolist(),
                })

        finally:
            progress.empty()

        st.session_state.stage_anim_results = stored

        auto_x_min, auto_x_max = smart_stage_animation_x_range(
            stored,
            WATER_PLOT_OPTIONS.get(quantity_name, "pressure"),
            st.session_state.get("last_result"),
        )

        st.session_state.stage_anim_x_min = auto_x_min
        st.session_state.stage_anim_x_max = auto_x_max

        # IMPORTANT:
        # reset widget state SAFELY
        st.session_state.pop("ui_stage_anim_x_min", None)
        st.session_state.pop("ui_stage_anim_x_max", None)

        st.session_state.ui_stage_anim_x_min = auto_x_min
        st.session_state.ui_stage_anim_x_max = auto_x_max

    # ==========================================================
    # RESULTS
    # ==========================================================
    stored = list(
        st.session_state.get("stage_anim_results", []) or []
    )

    if not stored:
        st.info(
            "Press 'Run stages animation' to solve every main stage "
            "and every intermediate substage."
        )
        return

    quantity = WATER_PLOT_OPTIONS.get(
        quantity_name,
        "pressure",
    )

    x_range = (
        float(st.session_state.get("stage_anim_x_min", -1.0)),
        float(st.session_state.get("stage_anim_x_max", 1.0)),
    )

    frames = []

    for item in stored:

        fig_i = plot_stage_animation_frame(
            item,
            quantity,
            x_range,
        )

        frames.append(
            go.Frame(
                name=str(item["step"]),
                data=list(fig_i.data),
                layout=go.Layout(
                    shapes=fig_i.layout.shapes,
                    annotations=fig_i.layout.annotations,
                    title=fig_i.layout.title,
                ),
            )
        )

    fig = plot_stage_animation_frame(
        stored[0],
        quantity,
        x_range,
    )

    fig.frames = frames

    fig.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                showactive=False,
                x=0.02,
                y=-0.12,
                xanchor="left",
                yanchor="top",
                buttons=[
                    dict(
                        label="Play",
                        method="animate",
                        args=[
                            None,
                            {
                                "frame": {
                                    "duration": int(speed_ms),
                                    "redraw": True,
                                },
                                "transition": {"duration": 0},
                                "fromcurrent": True,
                            },
                        ],
                    ),
                    dict(
                        label="Pause",
                        method="animate",
                        args=[
                            [None],
                            {
                                "frame": {
                                    "duration": 0,
                                    "redraw": False,
                                },
                                "mode": "immediate",
                            },
                        ],
                    ),
                ],
            )
        ],
        sliders=[
            dict(
                active=0,
                x=0.18,
                y=-0.10,
                len=0.78,
                currentvalue=dict(prefix="Frame "),
                steps=[
                    dict(
                        label=str(item["step"]),
                        method="animate",
                        args=[
                            [str(item["step"])],
                            {
                                "frame": {
                                    "duration": 0,
                                    "redraw": True,
                                },
                                "transition": {"duration": 0},
                                "mode": "immediate",
                            },
                        ],
                    )
                    for item in stored
                ],
            )
        ],
    )

    st.plotly_chart(fig, use_container_width=True)

    rows = []

    for item in stored:

        maxv, unit = max_response_for_quantity(
            item["result"],
            quantity,
        )

        rows.append({
            "Frame": item["step"],
            "Stage/substage": item["label"],
            "z excavation (m)": item["z"],
            "Active supports": item["active_supports"],
            "Status": getattr(item["result"], "status", ""),
            f"Max {quantity} ({unit})": maxv,
        })

    st.markdown("#### Stage/substage results")

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        height=min(520, 42 + 35 * len(rows)),
    )

def render_query():
    st.markdown('<div class="cut-section-title">Point query</div>', unsafe_allow_html=True)
    df = result_dataframe(st.session_state.last_result)
    if df.empty:
        st.info("Run a solver first."); return
    zq = st.number_input("z query (m)", key="query_z", help="Depth/elevation below the retained-side ground surface where the local calculated quantities are queried.")
    cols = [c for c in df.columns if c != "z (m)"]
    qdf = pd.DataFrame({"Quantity": cols, "Value": [interp_col(df, c, zq) for c in cols]})
    st.dataframe(qdf, use_container_width=True, hide_index=True, height=560)


def render_advanced():
    st.markdown('<div class="cut-section-title">Advanced diagnostics</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="small")
    c1.number_input("general n bending schemes", key="general_case_bending_schemes", min_value=2, step=1)
    c2.number_input("general θ refine passes", key="general_case_theta_refine_passes", min_value=0, step=1)
    c3.number_input("general θ grid points", key="general_case_theta_points", min_value=5, step=1)
    c4.number_input("general z_pivot grid points", key="general_case_zp_points", min_value=5, step=1)
    c1, c2 = st.columns(2, gap="small")
    c1.number_input("general pivot margin frac", key="general_case_pivot_margin_frac", min_value=0.0, max_value=0.20, format="%.6g")
    c2.number_input("general max workers (0=auto)", key="general_case_max_workers", min_value=0, step=1)
    result = st.session_state.last_result
    if result is not None:
        s = dict(getattr(result, "summary", {}) or {})
        candidates = s.get("general_case_solutions_table", []) or []
        if candidates:
            st.markdown("#### Ranked candidate solutions")
            st.dataframe(pd.DataFrame(candidates), use_container_width=True, hide_index=True, height=500)
        conv = getattr(result, "convergence_history", []) or []
        if conv:
            st.markdown("#### Convergence history")
            st.dataframe(pd.DataFrame(conv), use_container_width=True, hide_index=True, height=420)

def design_summary(result):
    if result is None:
        return

    try:
        z = list(getattr(result, "z", []) or [])
        dx, z_dx = _summary_extreme(z, getattr(result, "deflection", []), factor=1000.0, use_abs=True)
        M, z_M = _summary_extreme(z, getattr(result, "moment", []), factor=1.0, use_abs=True)
        V, z_V = _summary_extreme(z, getattr(result, "shear", []), factor=1.0, use_abs=True)

        st.markdown("#### Key results")

        c1, c2, c3 = st.columns(3)
        c1.metric("Max |M|", f"{abs(M):.4g} kNm/m", help=f"z = {z_M:.4g} m")
        c2.metric("Max |V|", f"{abs(V):.4g} kN/m", help=f"z = {z_V:.4g} m")
        c3.metric("Max |Δx|", f"{abs(dx):.4g} mm", help=f"z = {z_dx:.4g} m")

        st.caption("Detailed resultants, support-force pairs and failure checks are in the Summary results tab.")

    except Exception:
        pass


# v7.4 surgical memory fix: Previous/Next are Streamlit buttons, not HTML links.
# Keep them paired and coloured without affecting solver state.
st.markdown("""
<style>
/* The navigation marker is immediately followed by Streamlit's two-column block. */
.stMarkdown:has(.cut-nav-streamlit-pair-start){
    margin:0!important;
    padding:0!important;
}
.stMarkdown:has(.cut-nav-streamlit-pair-start) + div[data-testid="stHorizontalBlock"]{
    display:flex!important;
    flex-direction:row!important;
    flex-wrap:nowrap!important;
    gap:.65rem!important;
    width:100%!important;
    margin:.55rem 0 .65rem 0!important;
}
.stMarkdown:has(.cut-nav-streamlit-pair-start) + div[data-testid="stHorizontalBlock"] > div{
    flex:1 1 0!important;
    width:50%!important;
    min-width:0!important;
}
.stMarkdown:has(.cut-nav-streamlit-pair-start) + div[data-testid="stHorizontalBlock"] button{
    min-height:54px!important;
    border-radius:13px!important;
    font-weight:800!important;
    font-size:1.02rem!important;
    box-shadow:0 5px 14px rgba(20,65,110,.10)!important;
}
.stMarkdown:has(.cut-nav-streamlit-pair-start) + div[data-testid="stHorizontalBlock"] > div:nth-child(1) button{
    background:linear-gradient(180deg,#fff3f3,#f7dddd)!important;
    border:1px solid #e2a0a0!important;
    color:#7b2323!important;
}
.stMarkdown:has(.cut-nav-streamlit-pair-start) + div[data-testid="stHorizontalBlock"] > div:nth-child(2) button{
    background:linear-gradient(180deg,#f0fbf2,#dff4e5)!important;
    border:1px solid #92c99f!important;
    color:#1f6b34!important;
}
.stMarkdown:has(.cut-nav-streamlit-pair-start) + div[data-testid="stHorizontalBlock"] > div:nth-child(1) button:hover{
    background:linear-gradient(180deg,#ffe8e8,#f1cccc)!important;
    border-color:#d37a7a!important;
}
.stMarkdown:has(.cut-nav-streamlit-pair-start) + div[data-testid="stHorizontalBlock"] > div:nth-child(2) button:hover{
    background:linear-gradient(180deg,#e3f8e8,#ccefd6)!important;
    border-color:#72b983!important;
}
@media(max-width:900px){
    .stMarkdown:has(.cut-nav-streamlit-pair-start) + div[data-testid="stHorizontalBlock"]{
        gap:.45rem!important;
        flex-wrap:nowrap!important;
    }
    .stMarkdown:has(.cut-nav-streamlit-pair-start) + div[data-testid="stHorizontalBlock"] button{
        font-size:.98rem!important;
        min-height:52px!important;
    }
}
</style>
""", unsafe_allow_html=True)


render_header()
try:
    model_preview = build_model()
except Exception as exc:
    model_preview = None
    st.error(str(exc))

page = st.session_state.active_page
if page == "Model inputs":
    render_model_inputs(model_preview)

elif page == "Stages and reinforcement":
    render_stages_and_reinforcement(model_preview)

elif page == "Run & solver monitor":
    render_run()

elif page == "Summary results":
    render_summary_results()

elif page == "Results table":
    render_results()

elif page == "Plots":
    render_plots()

elif page == "Water level animation":
    render_water_animation()

elif page == "Stages animation":
    render_stages_animation()

elif page == "Point query":
    render_query()

elif page == "Advanced diagnostics":
    render_advanced()


# Surgical mobile layout corrections for the accepted Streamlit version.
st.markdown("""
<style>
/* Main Previous/Next navigation: previous = soft red, next = soft green. */
.stMarkdown:has(.cut-main-nav-marker) + div[data-testid="stHorizontalBlock"]{
    align-items:stretch!important;
}
.stMarkdown:has(.cut-main-nav-marker) + div[data-testid="stHorizontalBlock"] > div:nth-child(1) button{
    background:linear-gradient(180deg,#fff1f1,#f8dede)!important;
    border:1px solid #e3a4a4!important;
    color:#7a2323!important;
}
.stMarkdown:has(.cut-main-nav-marker) + div[data-testid="stHorizontalBlock"] > div:nth-child(1) button:hover{
    background:linear-gradient(180deg,#ffe8e8,#f3cdcd)!important;
    border-color:#d47f7f!important;
}
.stMarkdown:has(.cut-main-nav-marker) + div[data-testid="stHorizontalBlock"] > div:nth-child(2) button{
    background:linear-gradient(180deg,#eefaf0,#dff3e4)!important;
    border:1px solid #9ccca8!important;
    color:#1f6b34!important;
}
.stMarkdown:has(.cut-main-nav-marker) + div[data-testid="stHorizontalBlock"] > div:nth-child(2) button:hover{
    background:linear-gradient(180deg,#e4f7e8,#cfead7)!important;
    border-color:#78b888!important;
}

@media(max-width:900px){
    /* Force Previous + Next to stay side-by-side on mobile. */
    .stMarkdown:has(.cut-main-nav-marker) + div[data-testid="stHorizontalBlock"]{
        display:flex!important;
        flex-wrap:wrap!important;
        align-items:stretch!important;
        row-gap:.55rem!important;
        column-gap:.55rem!important;
    }
    .stMarkdown:has(.cut-main-nav-marker) + div[data-testid="stHorizontalBlock"] > div:nth-child(1),
    .stMarkdown:has(.cut-main-nav-marker) + div[data-testid="stHorizontalBlock"] > div:nth-child(2){
        flex:1 1 calc(50% - .35rem)!important;
        min-width:calc(50% - .35rem)!important;
        width:calc(50% - .35rem)!important;
    }
    .stMarkdown:has(.cut-main-nav-marker) + div[data-testid="stHorizontalBlock"] > div:nth-child(3){
        flex:1 1 100%!important;
        min-width:100%!important;
        width:100%!important;
    }
    .stMarkdown:has(.cut-main-nav-marker) + div[data-testid="stHorizontalBlock"] button{
        min-height:54px!important;
        font-weight:700!important;
    }

    /* Icon selectors: controlled mobile grids. */
    .img-grid.reinf{grid-template-columns:repeat(3,minmax(0,1fr))!important;}
    .img-grid.solver{grid-template-columns:repeat(6,minmax(0,1fr))!important;}
    .img-grid.solver .img-card{grid-column:span 3!important;}
    .img-grid.solver .img-card:nth-child(n+3){grid-column:span 2!important;}
    .img-card{min-height:120px!important;padding:.42rem .20rem!important;}
}
</style>
""", unsafe_allow_html=True)

st.caption("Educational / research software — no warranty. Results must be independently checked by a qualified engineer before design use.")

# v7.4 FIX8: definitive mobile table polishing.
# The previous mobile CSS made the row structure stable but still allowed header
# text to collide with the first input row on narrow screens.  This final layer
# deliberately makes the engineering rows wider and gives header rows real
# vertical clearance.  Horizontal scrolling remains only at expander-body level.
st.markdown(
    """
<style>
@media(max-width:900px){
    /* Keep Home/About as two equal buttons in one row. */
    .header-actions{
        display:flex!important;
        flex-direction:row!important;
        flex-wrap:nowrap!important;
        align-items:center!important;
        justify-content:flex-start!important;
        gap:.50rem!important;
        width:100%!important;
        margin:.45rem 0 .70rem 0!important;
    }
    .home-link, .about-details summary{
        flex:0 0 122px!important;
        width:122px!important;
        min-width:122px!important;
        max-width:122px!important;
        height:42px!important;
        box-sizing:border-box!important;
    }

    /* One scroll area only: the expander body. */
    div[data-testid="stExpander"] details > div{
        overflow-x:auto!important;
        overflow-y:visible!important;
        -webkit-overflow-scrolling:touch!important;
        padding:.95rem .90rem .78rem .90rem!important;
    }

    /* Streamlit column rows behave like fixed-width table rows. */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]{
        display:flex!important;
        flex-direction:row!important;
        flex-wrap:nowrap!important;
        align-items:stretch!important;
        justify-content:flex-start!important;
        gap:.34rem!important;
        width:max-content!important;
        min-width:max-content!important;
        max-width:none!important;
        overflow:visible!important;
        margin:0!important;
        padding:0!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] > div,
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{
        flex:0 0 auto!important;
        min-width:0!important;
        max-width:none!important;
        padding:0!important;
        margin:0!important;
        overflow:visible!important;
    }

    /* Rows with exactly 3 columns: Parameter | Left | Right. */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) > div:nth-child(1){
        flex-basis:145px!important; width:145px!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) > div:nth-child(2),
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) > div:nth-child(3){
        flex-basis:225px!important; width:225px!important;
    }

    /* Rows with exactly 2 columns, mainly EI wall stiffness. */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(2)):not(:has(> div:nth-child(3))) > div:nth-child(1){
        flex-basis:150px!important; width:150px!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(2)):not(:has(> div:nth-child(3))) > div:nth-child(2){
        flex-basis:220px!important; width:220px!important;
    }

    /* Rows with exactly 6 columns: Global parameters.  Wider columns prevent
       the labels from being clipped/overprinted. */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(6)):not(:has(> div:nth-child(7))) > div{
        flex-basis:145px!important; width:145px!important;
    }

    /* Numerical/animation rows remain compact but readable. */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(4)):not(:has(> div:nth-child(5))) > div{
        flex-basis:170px!important; width:170px!important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(5)):not(:has(> div:nth-child(6))) > div{
        flex-basis:160px!important; width:160px!important;
    }

    /* Header rows need real clearance before the first data row. */
    div[data-testid="stHorizontalBlock"]:has(.input-grid-header){
        margin-bottom:.42rem!important;
        align-items:flex-end!important;
    }
    .stMarkdown:has(.input-grid-header),
    .stMarkdown:has(.input-grid-label),
    .stMarkdown:has(.input-grid-value){
        margin:0!important;
        padding:0!important;
        overflow:visible!important;
    }
    .stMarkdown:has(.input-grid-header) p,
    .stMarkdown:has(.input-grid-label) p,
    .stMarkdown:has(.input-grid-value) p{
        margin:0!important;
        padding:0!important;
    }

    .input-grid-header{
        min-height:1.95rem!important;
        height:1.95rem!important;
        line-height:1.08!important;
        padding:0 .18rem .22rem .18rem!important;
        display:flex!important;
        align-items:flex-end!important;
        border-bottom:1px solid #cfd8e3!important;
        font-size:.72rem!important;
        font-weight:750!important;
        white-space:normal!important;
        overflow:visible!important;
        word-break:normal!important;
    }
    .input-grid-label,
    .input-grid-value{
        min-height:2.04rem!important;
        height:2.04rem!important;
        line-height:1.08!important;
        padding:.05rem .18rem!important;
        display:flex!important;
        align-items:center!important;
        font-size:.72rem!important;
        font-weight:700!important;
        white-space:nowrap!important;
        overflow:visible!important;
    }
    .input-grid-value{font-weight:500!important;}

    div[data-testid="stNumberInput"],
    div[data-testid="stSelectbox"],
    div[data-testid="stCheckbox"]{
        margin:0!important;
        padding:0!important;
        width:100%!important;
        max-width:none!important;
        overflow:visible!important;
    }
    div[data-testid="stNumberInput"] label,
    div[data-testid="stSelectbox"] label{
        display:none!important;
        height:0!important;
        min-height:0!important;
        margin:0!important;
        padding:0!important;
        visibility:hidden!important;
    }
    div[data-testid="stNumberInput"] input{
        height:1.96rem!important;
        min-height:1.96rem!important;
        padding:.05rem .30rem!important;
        font-size:.72rem!important;
        border-radius:.46rem!important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
        min-height:2.00rem!important;
        height:2.00rem!important;
        font-size:.76rem!important;
        border-radius:.50rem!important;
    }

    h4{
        margin-top:.76rem!important;
        margin-bottom:.42rem!important;
        font-size:1.08rem!important;
        line-height:1.15!important;
    }
}
</style>
""",
    unsafe_allow_html=True,
)


# v7.4 FIX10: colored navigation/buttons and left-aligned native tables.
st.markdown("""
<style>
/* Header action buttons: same size and same colour. */
.header-actions{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;gap:.55rem!important;align-items:center!important;}
.home-link,.about-details summary{
    width:128px!important;min-width:128px!important;max-width:128px!important;height:44px!important;
    background:linear-gradient(180deg,#eaf4ff,#dcecfb)!important;
    border:1px solid #7facd8!important;color:#123d67!important;
    border-radius:15px!important;box-shadow:0 5px 14px rgba(20,65,110,.12)!important;
    font-weight:800!important;justify-content:center!important;
}
.home-link:hover,.about-details summary:hover{background:linear-gradient(180deg,#dcecff,#cfe3f8)!important;border-color:#5d94c8!important;}


/* Surgical Previous/Next navigation: fixed two-button group on every screen. */
.cut-nav-pair{
    display:flex!important;
    flex-direction:row!important;
    flex-wrap:nowrap!important;
    gap:.65rem!important;
    width:100%!important;
    margin:.55rem 0 .65rem 0!important;
}
.cut-nav-pair .cut-nav-btn{
    flex:1 1 0!important;
    width:50%!important;
    min-width:0!important;
    min-height:54px!important;
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
    border-radius:13px!important;
    text-decoration:none!important;
    font-weight:800!important;
    font-size:1.02rem!important;
    box-shadow:0 5px 14px rgba(20,65,110,.10)!important;
}
.cut-nav-pair .cut-nav-prev{
    background:linear-gradient(180deg,#fff3f3,#f7dddd)!important;
    border:1px solid #e2a0a0!important;
    color:#7b2323!important;
}
.cut-nav-pair .cut-nav-next{
    background:linear-gradient(180deg,#f0fbf2,#dff4e5)!important;
    border:1px solid #92c99f!important;
    color:#1f6b34!important;
}
.cut-nav-pair .cut-nav-prev:hover{background:linear-gradient(180deg,#ffe8e8,#f1cccc)!important;border-color:#d37a7a!important;}
.cut-nav-pair .cut-nav-next:hover{background:linear-gradient(180deg,#e3f8e8,#ccefd6)!important;border-color:#72b983!important;}
.cut-nav-pair .cut-nav-disabled{
    opacity:.55!important;
    pointer-events:none!important;
    cursor:not-allowed!important;
}
@media(max-width:900px){
    .cut-nav-pair{gap:.45rem!important;}
    .cut-nav-pair .cut-nav-btn{font-size:.98rem!important;min-height:52px!important;}
}

/* Previous / Next buttons: common colour. */
div[data-testid="stButton"] button[kind="secondary"]{
    background:linear-gradient(180deg,#e7f0fb,#d9e8f7)!important;
    border:1px solid #8eb3d9!important;color:#173f6b!important;
    border-radius:13px!important;font-weight:700!important;
}
div[data-testid="stButton"] button[kind="secondary"]:hover{
    background:linear-gradient(180deg,#dcecff,#cce0f5)!important;border-color:#5e95c9!important;
}

/* Section dropdown: distinct but harmonious colour. */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
    background:linear-gradient(180deg,#f3f7fb,#e6eef7)!important;
    border:1px solid #9eb8d2!important;border-radius:13px!important;color:#223044!important;
}

/* Native editable tables: left-align every header and cell. */
div[data-testid="stDataFrame"] [role="columnheader"],
div[data-testid="stDataFrame"] [role="gridcell"],
div[data-testid="stDataFrame"] [data-testid="stDataFrameCell"]{
    text-align:left!important;justify-content:flex-start!important;align-items:center!important;
}
div[data-testid="stDataFrame"] canvas{image-rendering:auto;}

/* Data-editor toolbar/menu icons are not needed for these engineering input tables. */
div[data-testid="stDataFrame"] [data-testid="stDataFrameColumnHeaderMenu"]{display:none!important;}

@media(max-width:900px){
  .header-actions{gap:.45rem!important;margin:.45rem 0 .65rem 0!important;}
  .home-link,.about-details summary{width:116px!important;min-width:116px!important;max-width:116px!important;height:42px!important;}
}
</style>
""", unsafe_allow_html=True)
