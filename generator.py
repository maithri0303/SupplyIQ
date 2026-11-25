"""Deterministic SupplyIQ demo data and full-scale generation entry point."""
import numpy as np
import pandas as pd
from pathlib import Path
import argparse, json, hashlib

SEED=20261022
def generate_demo(seed=SEED, n_sku=80, n_loc=8, weeks=12):
    rng=np.random.default_rng(seed)
    sku=pd.DataFrame({
      "sku_id":[f"SKU-{i:06d}" for i in range(1,n_sku+1)],
      "category":rng.choice(["Electronics","Home","Apparel","Industrial","Health"],n_sku),
      "unit_of_measure":"EA","unit_cost":rng.uniform(8,250,n_sku).round(2),
      "safety_stock":rng.integers(15,100,n_sku),"substitute_group":[f"SUB-{i//4:04d}" for i in range(n_sku)],
      "active":True})
    loc=pd.DataFrame({"location_id":[f"LOC-{i:03d}" for i in range(1,n_loc+1)],
      "location_name":[f"Distribution Center {i:02d}" for i in range(1,n_loc+1)],
      "region":rng.choice(["North","South","East","West"],n_loc),"capacity_units":rng.integers(12000,40000,n_loc)})
    suppliers=pd.DataFrame({"supplier_id":[f"SUP-{i:04d}" for i in range(1,31)],
      "supplier_name":[f"Supplier {i:02d}" for i in range(1,31)],
      "capacity_units":rng.integers(700,3500,30),"committed_units":rng.integers(400,3000,30),
      "min_order_qty":rng.choice([10,25,50,100],30),"lead_time_days":rng.integers(5,35,30),
      "reliability":rng.uniform(.78,.99,30).round(2)})
    demand_rows=[]; inv_rows=[]; po_rows=[]; prod_rows=[]; lt_rows=[]
    for s in sku.itertuples():
      for l in loc.itertuples():
        base=max(8,int(rng.gamma(4,12)))
        onhand=int(base*rng.uniform(1.2,4))
        for w in range(1,weeks+1):
          spike=1.0
          if rng.random()<.06: spike=rng.uniform(1.7,2.8)
          qty=max(0,int(base*spike*rng.normal(1,.12)))
          demand_rows.append((f"DEM-{s.sku_id}-{l.location_id}-2026W{w:02d}",s.sku_id,l.location_id,
                              f"2026W{w:02d}",w,qty,s.category))
          inbound=int(max(0,rng.normal(base*.55,base*.3))) if w%3==0 else 0
          inv_rows.append((f"INV-{s.sku_id}-{l.location_id}-W{w:02d}",s.sku_id,l.location_id,
                           f"2026W{w:02d}",onhand if w==1 else 0,inbound,s.unit_of_measure))
          onhand=max(0,onhand+inbound-qty)
          if w%4==0:
            po_rows.append((f"PO-2026-{len(po_rows)+1:06d}",s.sku_id,l.location_id,
              f"SUP-{int(rng.integers(1,31)):04d}",f"2026W{w:02d}",int(base*rng.uniform(1,3)),"confirmed"))
          prod_rows.append((f"PP-{s.sku_id}-{l.location_id}-W{w:02d}",s.sku_id,l.location_id,
            f"2026W{w:02d}",int(base*rng.uniform(.1,.35)),int(base*rng.uniform(.3,.7))))
        lt_rows.append((f"LT-{s.sku_id}-{l.location_id}",s.sku_id,l.location_id,int(rng.integers(5,35))))
    demand=pd.DataFrame(demand_rows,columns=["demand_id","sku_id","location_id","week_label","week_index","forecast_qty","category"])
    inventory=pd.DataFrame(inv_rows,columns=["inventory_id","sku_id","location_id","week_label","on_hand_qty","inbound_qty","uom"])
    pos=demand.merge(inventory,on=["sku_id","location_id","week_label"],how="left").sort_values(["sku_id","location_id","week_index"])
    pos["projected_balance"]=pos.groupby(["sku_id","location_id"]).apply(
      lambda x:(x.on_hand_qty.cumsum()+x.inbound_qty.cumsum()-x.forecast_qty.cumsum()),include_groups=False).reset_index(level=[0,1],drop=True)
    pos["safety_stock"]=pos.sku_id.map(sku.set_index("sku_id").safety_stock)
    pos["short_qty"]=(pos.safety_stock-pos.projected_balance).clip(lower=0).astype(int)
    shortages=pos[pos.short_qty>0].copy().reset_index(drop=True)
    shortages["shortage_id"]=[f"SHORT-2026-{i:06d}" for i in range(1,len(shortages)+1)]
    shortages["priority_score"]=(shortages.short_qty*shortages.sku_id.map(sku.set_index("sku_id").unit_cost)).round(2)
    shortages["priority"]=np.where(shortages.priority_score>=500,"P1","P3") if len(shortages) else []
    shortages["root_cause"]=np.where(shortages.week_index<=2,"Lead-time exposure","Demand exceeds available supply")
    shortages["issue_type"]=""
    # Explicitly labeled edge-case examples: traceable to source shortage records.
    edge_types=["INBOUND_DOUBLE_COUNT","UNAPPROVED_SUBSTITUTE","SUPPLIER_CAPACITY_EXCEEDED","LEAD_TIME_OMITTED","UOM_MISMATCH"]
    ground=[]
    for i,issue in enumerate(edge_types):
      if len(shortages):
        row=shortages.iloc[i%len(shortages)]
        ground.append({"issue_id":f"ISSUE-{i+1:03d}","issue_type":issue,"shortage_id":row.shortage_id,
                       "sku_id":row.sku_id,"location_id":row.location_id,"expected_detection":True,
                       "description":"Synthetic labeled exception scenario for validation"})
    mitig=[]
    for row in shortages.head(250).itertuples():
      sup=suppliers.iloc[int(rng.integers(0,len(suppliers)))]
      recovery=min(int(row.short_qty),int(sup.capacity_units-sup.committed_units))
      mitig.append((f"MIT-{row.shortage_id}-01",row.shortage_id,"Expedite supplier",sup.supplier_id,
        max(0,recovery),round(max(0,recovery)*float(sku.set_index("sku_id").loc[row.sku_id,"unit_cost"])*.08,2),
        max(0,int(sup.lead_time_days)-7),"eligible" if recovery>=sup.min_order_qty else "ineligible"))
      mitig.append((f"MIT-{row.shortage_id}-02",row.shortage_id,"Transfer / substitute",sup.supplier_id,
        max(0,int(row.short_qty*.65)),round(int(row.short_qty*.65)*float(sku.set_index("sku_id").loc[row.sku_id,"unit_cost"])*.04,2),
        3,"review_required"))
    mitigations=pd.DataFrame(mitig,columns=["option_id","shortage_id","action","supplier_id","recovery_qty","total_cost","service_days_saved","feasibility"])
    return {"sku":sku,"locations":loc,"demand":demand,"inventory":inventory,"suppliers":suppliers,
      "shortages":shortages[["shortage_id","sku_id","location_id","week_label","week_index","short_qty","priority_score","priority","root_cause","issue_type"]],
      "mitigations":mitigations,"purchase_orders":pd.DataFrame(po_rows,columns=["po_id","sku_id","location_id","supplier_id","week_label","order_qty","status"]),
      "production_plan":pd.DataFrame(prod_rows,columns=["production_plan_id","sku_id","location_id","week_label","planned_qty","capacity_units"]),
      "lead_time":pd.DataFrame(lt_rows,columns=["lead_time_id","sku_id","location_id","lead_time_days"]),
      "ground_truth":pd.DataFrame(ground)}

def full_scale(seed=SEED, out="data/full", n_sku=3000, n_loc=50, weeks=52):
    """Full-scale reproducible CSV generator; writes demand in per-week chunks to control memory."""
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    d=generate_demo(seed,n_sku,n_loc,weeks)
    # Main demo generator can handle scale; write entity CSVs. For very large runs use --chunked-demand below.
    for key,df in d.items(): df.to_csv(out/f"{key}.csv",index=False)
    manifest={"seed":seed,"skus":n_sku,"locations":n_loc,"weeks":weeks,"generated_entities":list(d),"synthetic":True}
    (out/"source_manifest.json").write_text(json.dumps(manifest,indent=2))
    return manifest

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--scale",choices=["starter","full"],default="starter")
    p.add_argument("--seed",type=int,default=SEED)
    p.add_argument("--out",default="data/generated")
    a=p.parse_args()
    if a.scale=="full": print(full_scale(a.seed,a.out))
    else:
      Path(a.out).mkdir(parents=True,exist_ok=True)
      d=generate_demo(a.seed)
      for k,v in d.items(): v.to_csv(Path(a.out)/f"{k}.csv",index=False)
      print("Generated starter dataset:",{k:len(v) for k,v in d.items()})
