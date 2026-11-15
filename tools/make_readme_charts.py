"""Make the charts in README.md (docs/img/chart_*.png) from results/, ai/ and data/weather/.
The 2015-2025 year-by-year values are copied from the output of FieldRota_AI.ipynb (section 4)."""
import pandas as pd, numpy as np, json, glob, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
R=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..")+"/"; O=R+"docs/img/"
SURF="#fcfcfb"; INK="#0b0b0b"; INK2="#52514e"; GRID="#e4e3df"
AI="#2a78d6"; BASE="#eb6834"; V1="#1baf7a"; MY="#a3a29b"
plt.rcParams.update({"figure.facecolor":SURF,"axes.facecolor":SURF,"savefig.facecolor":SURF,"axes.edgecolor":GRID,
 "axes.labelcolor":INK2,"xtick.color":INK2,"ytick.color":INK2,"text.color":INK,"font.size":11,"axes.spines.top":False,
 "axes.spines.right":False,"axes.grid":True,"grid.color":GRID,"grid.linewidth":0.8,"axes.axisbelow":True,"axes.titleweight":"bold",
 "axes.titlesize":13,"axes.titlelocation":"left","legend.frameon":False})
S=pd.concat([pd.read_csv(p) for p in sorted(glob.glob(R+"results/summary_*.csv"))])
def who(p):
    if p.startswith("FieldRota-AI"): return "ai"
    if p.startswith("FieldRota v1, today") or p=="FieldRota v1 suggestion": return "v1"
    if p.startswith("Myopic"): return "my"
    if p.startswith("Best"): return "opt"
    if p.startswith("Farmers"): return "farm"
S["who"]=S.policy.map(who)
first=S[S.who=="farm"].groupby(["region","goal","eval"]).head(1)
S2=pd.concat([S[S.who.isin(["ai","v1","my","opt"])],first])
def save(fig,name): fig.savefig(O+name,dpi=170,bbox_inches="tight"); plt.close(fig); print(name)

# 1 Konya well water, two tests
k=S2[(S2.region=="konya")&(S2.goal=="water")]
plans=[("farm","Today's rotation\n(maize → wheat → sugar beet)",BASE),("my","Myopic\n(best crop this year)",MY),("v1","FieldRota v1\n(best fixed rotation)",V1),("ai","FieldRota-AI\n(ours)",AI)]
fig,ax=plt.subplots(figsize=(9,4.6))
x=np.arange(2); w=0.19
for i,(k_,lab,c) in enumerate(plans):
    vals=[k[(k.who==k_)&(k["eval"]==e)].irrigation_m3_da.iloc[0] for e in ["hist_test","future_test"]]
    bars=ax.bar(x+(i-1.5)*w,vals,w*0.92,color=c,label=lab.replace("\n"," "))
    for b,v in zip(bars,vals): ax.text(b.get_x()+b.get_width()/2,v+8,f"{v:.0f}",ha="center",fontsize=10,color=INK2)
ax.set_xticks(x,["Real weather 2015–2025\n(real-weather agent)","2026–2060, 2 unseen climate models\n(climate-model agent)"])
ax.set_ylabel("Well water, m³ per decare per year"); ax.set_ylim(0,600); ax.grid(axis="x",visible=False)
ax.set_title("Konya, save-water goal: FieldRota-AI pumps 45–48 % less than today's rotation")
ax.legend(ncol=2,loc="upper center",bbox_to_anchor=(0.5,-0.2),fontsize=10)
save(fig,"chart_water_konya.png")

# 2 year by year 2015-2025 (from executed notebook output)
yrs=list(range(2015,2026))
ai_c=["Barley","Vetch","Canola","Barley","Vetch","Canola","Barley","Vetch","Canola","Barley","Vetch"]
ai_s=[79.5,64.1,77.4,76.0,68.1,80.0,67.6,63.2,75.9,67.6,53.9]; ai_w=[138.2,350.1,211.1,225.3,303.7,185.4,309.1,352.4,225.8,308.6,354.1]
b_c=["Grain maize","Wheat","Sugar beet"]*4; b_s=[43.0,55.4,25.4,39.3,72.7,22.3,35.5,67.9,18.2,28.4,56.0]
b_w=[499.4,372.6,653.0,536.3,204.0,695.1,574.6,251.6,638.6,577.2,370.2]
fig,(a1,a2)=plt.subplots(2,1,figsize=(9,6.2),sharex=True,gridspec_kw={"hspace":0.25})
for a,(va,vb,yl) in zip([a1,a2],[(ai_s,b_s,"Yearly score (higher is better)"),(ai_w,b_w,"Well water, m³/da")]):
    a.plot(yrs,vb,color=BASE,lw=2,marker="o",ms=7,mec=SURF,mew=2,label="Today's rotation")
    a.plot(yrs,va,color=AI,lw=2,marker="o",ms=7,mec=SURF,mew=2,label="FieldRota-AI")
    a.axvspan(2024.5,2025.5,color="#e34948",alpha=0.08,lw=0); a.set_ylabel(yl)
a1.annotate("2025: record heat,\nvetch loses climate fit",xy=(2025,53.9),xytext=(2022.3,30),fontsize=9.5,color=INK2,arrowprops=dict(arrowstyle="-",color=INK2,lw=0.8))
for y,c,v in zip(yrs,ai_c,ai_s): a1.text(y,v+3,c,ha="center",fontsize=8,color=AI)
a1.set_ylim(10,95); a2.set_ylim(0,760); a1.legend(loc="lower left",ncol=2,fontsize=10)
a1.set_title("2015–2025, years the agent never trained on: one Çumra field, year by year")
a2.set_xticks(yrs)
save(fig,"chart_years_2015_2025.png")

# 3 hot days per year with splits
w=pd.read_csv(R+"data/weather/konya.csv.gz",index_col=0,parse_dates=True)
hot=(w.tmax>=35).groupby(w.index.year).sum()
fig,ax=plt.subplots(figsize=(9,3.8))
cols=[("#c3c2b7" if y<1986 else "#8fb5e8" if y<=2008 else "#b9b8f0" if y<=2014 else "#9a99a0") for y in hot.index]
cols=["#d6d5d0" if y<1986 else "#8db4ea" if y<=2008 else "#c9a8f0" if y<=2014 else "#6d6c69" for y in hot.index]
ax.bar(hot.index,hot.values,0.8,color=cols)
ax.bar([2025],[hot.loc[2025]],0.8,color="#e34948")
for x0,x1,lab in [(1986,2008,"train (1986–2008)"),(2009,2014,"validation"),(2015,2025,"test (2015–2025)")]:
    ax.annotate("",xy=(x0-0.4,hot.max()+5),xytext=(x1+0.4,hot.max()+5),arrowprops=dict(arrowstyle="<->",color=INK2,lw=0.8))
    ax.text((x0+x1)/2,hot.max()+7,lab,ha="center",fontsize=9.5,color=INK2)
ax.text(2025,hot.loc[2025]+1,f"{hot.loc[2025]}",ha="center",fontsize=10,color="#e34948",fontweight="bold")
ax.set_ylim(0,hot.max()+13); ax.set_ylabel("Days ≥ 35 °C"); ax.grid(axis="x",visible=False)
ax.set_title("Hot days at Çumra, 1985–2025 (NASA POWER), and how we split the years")
save(fig,"chart_hot_days.png")

# 4 learning curve
cur=json.load(open(R+"ai/konya.json"))["goals"]["water"]["curve"]
fig,ax=plt.subplots(figsize=(9,3.4))
xs=np.linspace(0,100000,len(cur)); ax.plot(xs,cur,color=AI,lw=2)
ax.axhline(70.7,color=INK2,lw=1,ls=(0,(4,3))); ax.text(99000,69.2,"exact optimum on the training models: 70.7",fontsize=9.5,color=INK2,ha="right")
ax.set_xlabel("Training episodes (each = a 2026–2060 future)"); ax.set_ylabel("Average yearly score")
ax.set_title("Learning curve: the Konya save-water agent improves by trial and error")
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,_: f"{int(v/1000)}k"))
save(fig,"chart_learning_curve.png")

# 5 regions well water dumbbell
names={"konya":"Konya, Türkiye","kansas":"Kansas, USA","punjab":"Punjab, India","california":"California, USA","lamancha":"La Mancha, Spain"}
f=S2[(S2.goal=="water")&(S2["eval"]=="future_test")]
fig,ax=plt.subplots(figsize=(9,3.8))
for i,r in enumerate(["konya","kansas","punjab","california","lamancha"]):
    fa=f[(f.region==r)&(f.who=="farm")].irrigation_m3_da.iloc[0]; ai=f[(f.region==r)&(f.who=="ai")].irrigation_m3_da.iloc[0]
    ax.plot([ai,fa],[i,i],color=GRID,lw=4,solid_capstyle="round",zorder=1)
    ax.scatter([fa],[i],s=90,color=BASE,zorder=2,edgecolor=SURF,lw=2,label="Region's common rotation" if i==0 else None)
    ax.scatter([ai],[i],s=90,color=AI,zorder=3,edgecolor=SURF,lw=2,label="FieldRota-AI" if i==0 else None)
    ax.text(fa+25,i,f"{fa:.0f}",va="center",fontsize=9.5,color=INK2); ax.text(ai-25,i,f"{ai:.0f}",va="center",ha="right",fontsize=9.5,color=INK2)
    ax.text(1330,i,f"−{100*(1-ai/fa):.0f} %",va="center",ha="right",fontsize=11,fontweight="bold",color=INK)
ax.set_yticks(range(5),[names[r] for r in ["konya","kansas","punjab","california","lamancha"]]); ax.invert_yaxis()
ax.set_xlim(0,1340); ax.set_xlabel("Well water, m³ per decare per year (2026–2060, unseen climate models)"); ax.grid(axis="y",visible=False)
ax.set_title("Same method, five groundwater hotspots (save-water goal)"); ax.legend(loc="lower right",bbox_to_anchor=(0.93,0),fontsize=10)
save(fig,"chart_regions_water.png")

# 6 percent of optimum
fu=S2[S2["eval"]=="future_test"].pivot_table(index=["region","goal"],columns="who",values="score")
fu["pct"]=100*fu["ai"]/fu["opt"]; fu["v1pct"]=100*fu["v1"]/fu["opt"]
gname={"water":"save water","soil":"healthy soil","bal":"balanced"}
order=[(r,g) for r in ["konya","kansas","punjab","california","lamancha"] for g in ["water","soil","bal"]]
fig,ax=plt.subplots(figsize=(9,5.2))
for i,(r,g) in enumerate(order):
    ax.scatter(fu.loc[(r,g),"pct"],i,s=80,color=AI,edgecolor=SURF,lw=1.5,zorder=3,label="FieldRota-AI" if i==0 else None)
ax.axvline(100,color=INK2,lw=1,ls=(0,(4,3)))
ax.set_yticks(range(15),[f"{names[r].split(',')[0]} · {gname[g]}" for r,g in order],fontsize=9.5); ax.invert_yaxis()
ax.set_xlabel("FieldRota-AI score as % of the exact optimum (dynamic programming), 2026–2060, unseen climate models")
ax.set_xlim(97.8,100.3); ax.grid(axis="y",visible=False)
ax.set_title(f"Close to the exact optimum: {fu.pct.mean():.1f} % on average, {fu.pct.min():.1f} % at worst")
save(fig,"chart_optimum.png")

# 7 trade-off water vs income (Konya hist test, save water)
kk=S[(S.region=="konya")&(S.goal=="water")&(S["eval"]=="hist_test")]
lab={"FieldRota-AI (RL)":"FieldRota-AI (same plan as v1)","Myopic (best this year)":"Myopic","FieldRota v1 suggestion":"FieldRota v1",
 "Farmers: dane_misir > bugday > seker_pancari":"Maize → wheat → sugar beet\n(today)","Farmers: bugday > aycicegi > dane_misir":"Wheat → sunflower → maize",
 "Farmers: bugday > seker_pancari > patates":"Wheat → sugar beet → potato","Farmers: bugday > nadas > bugday":"Wheat → fallow → wheat"}
fig,ax=plt.subplots(figsize=(9,4.6))
for _,r in kk.iterrows():
    legal=r.rule_breaks==0
    if r.who=="v1": continue
    c=AI if r.who=="ai" else MY if r.who=="my" else BASE
    ax.scatter(r.irrigation_m3_da,r.income_tl_da/1000,s=110,color=c if legal else SURF,edgecolor=c,lw=2,zorder=3)
    ax.annotate(lab[r.policy],(r.irrigation_m3_da,r.income_tl_da/1000),xytext=(8,-4 if r.who!="my" else 6),textcoords="offset points",fontsize=9.5,color=INK2)
ax.set_xlabel("Well water, m³ per decare per year (2015–2025)"); ax.set_ylabel("Modelled income, thousand TL per decare")
ax.set_xlim(150,600); ax.set_ylim(4,23)
ax.set_title("The trade-off: less water, less income (Konya, 2015–2025)")
ax.text(152,22.2,"Filled = follows the 2027 rules every year · hollow = breaks them",fontsize=9.5,color=INK2)
save(fig,"chart_tradeoff.png")
