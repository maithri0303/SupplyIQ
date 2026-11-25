import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from generator import generate_demo

st.set_page_config(page_title="SupplyIQ | Planning Control Tower", page_icon="📦", layout="wide")
st.markdown("""
<style>
.stApp {background:#f5f7fb}
[data-testid="stSidebar"] {background:#101c34}
[data-testid="stSidebar"] * {color:#eaf0ff}
.hero {padding:22px 26px;border-radius:18px;background:linear-gradient(120deg,#101c34,#244b76);color:white;margin-bottom:16px}
.hero h1 {margin:0;font-size:32px;letter-spacing:-.6px}
.hero p {margin:8px 0 0;color:#d7e5fa;font-size:14px}
.kpi {background:white;border:1px solid #e6eaf2;border-radius:14px;padding:17px 18px}
.kpi .label {color:#6b7280;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.6px}
.kpi .value {font-size:28px;font-weight:750;color:#14213d;margin-top:5px}
.kpi .note {font-size:12px;color:#7b8798;margin-top:4px}
.section {font-size:20px;font-weight:700;color:#14213d;margin:14px 0 8px}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def data():
    return generate_demo(seed=20261022)

d=data()
demand=d["demand"]; inventory=d["inventory"]; suppliers=d["suppliers"]
shortages=d["shortages"]; mitigations=d["mitigations"]; orders=d["purchase_orders"]

st.sidebar.markdown("## 📦 SupplyIQ")
st.sidebar.caption("Planning intelligence · Demo workspace")
page=st.sidebar.radio("WORKSPACE",["Executive Overview","Demand & Inventory","Shortage Control","Mitigation Planner","Data & Governance"])
st.sidebar.divider()
st.sidebar.markdown("**Scenario**")
scenario=st.sidebar.selectbox("Planning horizon",["Next 12 weeks","Next 26 weeks","Full 52 weeks"])
horizon={"Next 12 weeks":12,"Next 26 weeks":26,"Full 52 weeks":52}[scenario]
st.sidebar.caption("Demo data · fixed seed 20261022")
st.sidebar.success("Data integrity checks: demo pass")

st.markdown('<div class="hero"><h1>SupplyIQ</h1><p>Demand, inventory & supply planning — see risk early, understand why, act with confidence.</p></div>',unsafe_allow_html=True)
if page=="Executive Overview":
    st.markdown("### Planning pulse")
    cols=st.columns(4)
    metrics=[
        ("SKUs monitored",f"{d['sku'].sku_id.nunique():,}","Across active planning locations"),
        ("Forecast demand",f"{int(demand[demand.week_index<=horizon].forecast_qty.sum()):,}","Units in selected horizon"),
        ("At-risk SKU-location-weeks",f"{len(shortages):,}","Projected balance below safety stock"),
        ("Supplier capacity alerts",f"{int((suppliers.capacity_units<suppliers.committed_units).sum()):,}","Capacity utilization exceptions")
    ]
    for c,(label,val,note) in zip(cols,metrics):
        c.markdown(f'<div class="kpi"><div class="label">{label}</div><div class="value">{val}</div><div class="note">{note}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="section">Demand vs available supply</div>',unsafe_allow_html=True)
    weekly=demand[demand.week_index<=horizon].groupby("week_label",as_index=False).forecast_qty.sum()
    supply=inventory.groupby("week_label",as_index=False).inbound_qty.sum()
    chart=weekly.merge(supply,on="week_label",how="left").fillna(0)
    fig=px.line(chart,x="week_label",y=["forecast_qty","inbound_qty"],markers=True,
                 labels={"week_label":"Planning week","value":"Units","variable":"Measure"},
                 color_discrete_sequence=["#3268d4","#12a89d"])
    fig.update_layout(plot_bgcolor="white",paper_bgcolor="white",legend_title_text="",margin=dict(l=10,r=10,t=20,b=10))
    st.plotly_chart(fig,use_container_width=True)
    left,right=st.columns([1.2,1])
    with left:
        st.markdown('<div class="section">Shortage priority queue</div>',unsafe_allow_html=True)
        st.dataframe(shortages.sort_values("priority_score",ascending=False).head(10)[["shortage_id","sku_id","location_id","week_label","short_qty","priority","root_cause"]],use_container_width=True,hide_index=True)
    with right:
        st.markdown('<div class="section">Risk by root cause</div>',unsafe_allow_html=True)
        cause=shortages.groupby("root_cause",as_index=False).short_qty.sum()
        st.plotly_chart(px.bar(cause,x="root_cause",y="short_qty",color="root_cause",text_auto=True),use_container_width=True)
    st.info("Decision support demo: recommendations are rule-based and traceable to planning inputs. No ground-truth labels are used as model features.")
elif page=="Demand & Inventory":
    st.markdown("### Demand & inventory")
    a,b=st.columns(2)
    with a:
        st.markdown("**Forecast demand by category**")
        cat=demand.groupby("category",as_index=False).forecast_qty.sum().sort_values("forecast_qty",ascending=False)
        st.plotly_chart(px.bar(cat,x="category",y="forecast_qty",color="category"),use_container_width=True)
    with b:
        st.markdown("**Inventory position**")
        inv=inventory.groupby("location_id",as_index=False)[["on_hand_qty","inbound_qty"]].sum()
        st.plotly_chart(px.bar(inv,x="location_id",y=["on_hand_qty","inbound_qty"],barmode="group"),use_container_width=True)
    st.markdown("**Weekly demand records**")
    st.dataframe(demand[demand.week_index<=horizon].head(500),use_container_width=True,hide_index=True)
elif page=="Shortage Control":
    st.markdown("### Shortage control tower")
    c1,c2,c3=st.columns(3)
    priority=c1.multiselect("Priority",sorted(shortages.priority.unique()),default=sorted(shortages.priority.unique()))
    causes=c2.multiselect("Root cause",sorted(shortages.root_cause.unique()),default=sorted(shortages.root_cause.unique()))
    minqty=c3.slider("Minimum shortage units",0,int(max(1,shortages.short_qty.max())),0)
    view=shortages[shortages.priority.isin(priority)&shortages.root_cause.isin(causes)&(shortages.short_qty>=minqty)]
    st.metric("Filtered shortage records",len(view))
    st.dataframe(view.sort_values("priority_score",ascending=False),use_container_width=True,hide_index=True)
    st.download_button("Export shortage queue CSV",view.to_csv(index=False),"supplyiq_shortage_queue.csv","text/csv")
elif page=="Mitigation Planner":
    st.markdown("### Mitigation planner")
    st.caption("Compare policy-compliant options by cost, recovery and service impact.")
    selected=st.selectbox("Select shortage",shortages.shortage_id.tolist())
    options=mitigations[mitigations.shortage_id==selected].sort_values("total_cost")
    st.dataframe(options,use_container_width=True,hide_index=True)
    if len(options):
        best=options.iloc[0]
        st.success(f"Lowest-cost eligible option: {best.option_id} · {best.action} · estimated cost {best.total_cost:,.0f} · recover {best.recovery_qty} units")
        st.caption(f"Trade-off: {best.service_days_saved} days saved; feasibility status: {best.feasibility}")
elif page=="Data & Governance":
    st.markdown("### Data & governance")
    st.write("Deterministic synthetic data · fixed seed 20261022 · generated source records · derived planning outcomes.")
    st.markdown("**Core entities**")
    st.write("SKU, Location, ForecastDemand, Inventory, Supplier, SupplierCapacity, LeadTime, PurchaseOrder, ProductionPlan, Shortage, MitigationOption")
    st.markdown("**Traceability & edge cases**")
    st.write("Each injected scenario is stored with issue_type and a separate ground-truth file. Ground truth is not joined into planning features.")
    st.markdown("**Validation coverage**")
    st.write("Primary key uniqueness · foreign-key integrity · allowed enums · date ordering · balance reconciliation · lifecycle checks · duplicate detection")
    st.markdown("**Data dictionary**")
    st.dataframe(pd.read_csv(Path(__file__).parent/"data_dictionary.csv"),use_container_width=True,hide_index=True)
    st.markdown("**Source manifest**")
    st.json({"source":"Synthetic data generated by SupplyIQ","seed":20261022,"external_data":"None","license":"Original synthetic data"})
st.caption("SupplyIQ · Planning intelligence prototype · All data shown is synthetic.")
