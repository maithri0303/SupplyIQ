"""SupplyIQ integrity checks for generated tables."""
from pathlib import Path
import pandas as pd, json
def validate(folder="data/generated"):
    p=Path(folder); report={"checks":[],"passed":True}
    def check(name,ok,detail=""):
        report["checks"].append({"name":name,"passed":bool(ok),"detail":detail})
        report["passed"] &= bool(ok)
    def read(name):
        f=p/f"{name}.csv"
        return pd.read_csv(f) if f.exists() else pd.DataFrame()
    sku=read("sku"); loc=read("locations"); dem=read("demand"); inv=read("inventory")
    check("SKU primary key",sku.sku_id.is_unique if len(sku) else False)
    check("Location primary key",loc.location_id.is_unique if len(loc) else False)
    check("Demand IDs unique",dem.demand_id.is_unique if len(dem) else False)
    check("Demand SKU foreign keys",dem.sku_id.isin(sku.sku_id).all() if len(dem) else False)
    check("Demand location foreign keys",dem.location_id.isin(loc.location_id).all() if len(dem) else False)
    check("Nonnegative forecast",bool((dem.forecast_qty>=0).all()) if len(dem) else False)
    check("Inventory IDs unique",inv.inventory_id.is_unique if len(inv) else False)
    (p/"validation_summary.json").write_text(json.dumps(report,indent=2))
    return report
if __name__=="__main__":
    r=validate()
    print(json.dumps(r,indent=2))
    raise SystemExit(0 if r["passed"] else 1)
