"""Add the FieldRota-AI section to the FieldRota web app (app/index.html)."""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "app/index.html"
s = open(path, encoding="utf-8").read()
if "id=\"rlSec\"" in s:
    print("already patched"); sys.exit()

CSS = r"""
/* FieldRota-AI section */
.rl{display:grid;gap:14px}
.rl .box{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 18px;display:grid;gap:10px}
.rl h3{margin:0;font:700 19px var(--f-display)}
.rl .chips{display:flex;flex-wrap:wrap;gap:6px}
.rl .chip{display:grid;gap:2px;min-width:74px;padding:6px 8px;border-radius:6px;border:1px solid var(--line);background:var(--bg);font-size:14px;font-weight:700}
.rl .chip small{font:500 11px var(--f-mono);color:var(--muted)}
.rl .chip i{display:block;height:5px;border-radius:3px}
.rl .strip{display:flex;height:26px;border-radius:4px;overflow:hidden;border:1px solid var(--line)}
.rl .strip div{flex:1;min-width:0}
.rl .dec{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;font-size:14px}
@media (max-width:600px){.rl .dec{grid-template-columns:1fr}}
.rl .dec div{background:var(--bg);border-radius:6px;padding:8px 10px}
.rl .dec b{display:block;font:600 12px var(--f-mono);color:var(--muted)}
.rl table td.num{font:700 17px var(--f-display)}
.rl tbody th{text-transform:none;letter-spacing:0;font:700 15px/1.3 var(--f-body);color:var(--ink)}
.rl tbody th small{font:500 12px var(--f-body);color:var(--muted)}
.rl tr.me td,.rl tr.me th{background:var(--good-soft)}
.rl .warn{background:var(--wheat-soft);border-left:4px solid var(--wheat);padding:8px 12px;border-radius:0 6px 6px 0;font-size:15px}
.rl svg{width:100%;height:90px}
.rl thead th{text-transform:none;letter-spacing:0}
"""

SECTION = """
<section class="step rl" id="rlSec">
  <h2><span class="n">5</span><span id="rlT"></span></h2>
  <p class="hint" id="rlH"></p>
  <div class="box" id="rlPlan"></div>
  <div class="box" id="rlTest"></div>
  <details><summary id="rlHowS"></summary><div id="rlHow"></div></details>
</section>
"""

JS = r"""
/* ---------------- FieldRota-AI: learned rotation policy (reinforcement learning) ---------------- */
Object.assign(T.en,{
  rlT:"FieldRota-AI: a planner that learned from NASA weather and climate models",
  rlH:"A reinforcement-learning agent practised on this field for millions of virtual seasons under three NASA CMIP6 climate models for 2026–2060 (each future year = the model's warming trend plus the ups and downs of a real 1986–2025 NASA POWER year). Every year it looks at the last two crops in the field and the decade, then picks the next crop for your goal. The 2026–2060 test below uses two climate models it never trained on; the 2015–2025 columns come from a twin agent trained only on 1986–2008 weather (it looks at last year's rainfall instead of the decade).",
  rlPlanT:(a,b)=>`The AI's plan for your field (last crops: ${a} → ${b})`,
  rlStrip:"2027 → 2060, one block per year",
  rlDec:["2027–2035","2036–2045","2046–2060"],
  rlSwitch:(drop,add)=>`As the climate warms, the AI ${drop?`drops <b>${drop}</b>`:""}${drop&&add?" and ":""}${add?`brings in <b>${add}</b>`:""}.`,
  rlSame:"The AI's main crops stay the same through 2060; any short switches are shown in the decades above.",
  rlTestT:"Tested on data it never saw",
  rlCols:["Plan","Real weather 2015–2025: score","well water (m³/da/yr)","2026–2060, 2 unseen climate models: score","well water (m³/da/yr)","bad year (5th pct.)"],
  rlRows:{ai:"FieldRota-AI (learned policy)",v1:"FieldRota v1 (best fixed 3-year rotation)",farm:"Farmers' common rotation",my:"Myopic (best crop for this year only)"},
  rlFoot:(opt,pct)=>`Score = FieldRota's score for the selected goal (water, soil and climate fit, up to 100), averaged per year; it can fall below 0 when a plan needs more well water than the region's thirstiest crop. Exact optimum of the expected score on the unseen climate models (dynamic programming): <b>${opt}</b>. The AI reaches <b>${pct}%</b> of it.`,
  rlWorse:(h,f)=>`<b>Honest note:</b> here the simple v1 search does better than the AI${h?` on the real 2015–2025 weather (by ${h} points)`:""}${h&&f?" and":""}${f?` on the unseen climate models (by ${f} points)`:""}. The AI learns from single noisy weather years and starts from your real field history; v1 assumes you are already in its rotation and scores rotations with average climate.`,
  rlBetter:(d)=>`Here the AI scores up to ${d} points above v1 on data it never saw, by starting from your field's real history and changing crops as the decades warm.`,
  rlTie:"The AI and v1 land on almost the same answer: two very different methods agree, which makes the suggestion more trustworthy.",
  rlCurve:"Learning curve: average yearly score while the agent practised (left = start, right = end)",
  rlHowS:"How the AI works and what it does not know",
  rlHow:`<ul><li><b>Method:</b> tabular Q-learning. State = the two previous crops + the decade (training on CMIP6 futures) or last year's rainfall (training on past weather). Action = next crop, limited to FieldRota's rules (crop list, three different crops in any three years, no two high-water crops in a row in Konya, sowing and harvest must not overlap).</li><li><b>Reward:</b> FieldRota's own yearly score: well water, climate fit and soil health, weighted by your goal.</li><li><b>Simulator:</b> FieldRota's calibrated crop numbers, made year-by-year with real NASA POWER weather (ET₀, rainfall, days ≥ 35 °C in each crop's most sensitive month). Future years follow each CMIP6 model's trend to 2041–2060 plus the ups and downs of a real past year.</li><li><b>Test:</b> trained on 1986–2008 and 3 climate models; the best of 3 training runs is chosen on 2009–2014 and a 4th model (MRI-ESM2-0); tested on 2015–2025 and 2 more models it never saw (GFDL-ESM4, IPSL-CM6A-LR).</li><li><b>Limits:</b> yields are not simulated directly (climate fit stands in for them); one field and one main crop per year; soil-moisture carry-over and pests are not modelled; prices are not in the score.</li></ul>`
});
Object.assign(T.tr,{
  rlT:"FieldRota-AI: NASA hava verisi ve iklim modelleriyle öğrenen planlayıcı",
  rlH:"Pekiştirmeli öğrenme ajanı bu tarlada 2026–2060 için üç NASA CMIP6 iklim modeli altında milyonlarca sanal sezon denedi (her gelecek yıl = modelin ısınma eğilimi + 1986–2025 arasındaki gerçek bir NASA POWER yılının iniş çıkışları). Her yıl tarladaki son iki ürüne ve hangi on yılda olduğuna bakıp hedefinize göre sıradaki ürünü seçiyor. Aşağıdaki 2026–2060 testi, eğitimde hiç kullanılmayan iki iklim modeliyle yapıldı; 2015–2025 sütunları yalnızca 1986–2008 havasıyla eğitilen ikiz ajandan geliyor (on yıl yerine geçen yılın yağışına bakıyor).",
  rlPlanT:(a,b)=>`Yapay zekânın tarlanız için planı (son ürünler: ${a} → ${b})`,
  rlStrip:"2027 → 2060, her blok bir yıl",
  rlDec:["2027–2035","2036–2045","2046–2060"],
  rlSwitch:(drop,add)=>`İklim ısındıkça yapay zekâ ${drop?`<b>${drop}</b> ürününü bırakıyor`:""}${drop&&add?" ve ":""}${add?`<b>${add}</b> ekliyor`:""}.`,
  rlSame:"Yapay zekânın ana ürünleri 2060'a kadar aynı kalıyor; kısa süreli değişiklikler yukarıdaki on yıllarda görünüyor.",
  rlTestT:"Hiç görmediği verilerle test",
  rlCols:["Plan","Gerçek hava 2015–2025: puan","kuyu suyu (m³/da/yıl)","2026–2060, görmediği 2 iklim modeli: puan","kuyu suyu (m³/da/yıl)","kötü yıl (%5'lik dilim)"],
  rlRows:{ai:"FieldRota-AI (öğrenilmiş politika)",v1:"FieldRota v1 (en iyi sabit 3 yıllık nöbet)",farm:"Çiftçilerin yaygın nöbeti",my:"Miyop (yalnızca bu yılın en iyisi)"},
  rlFoot:(opt,pct)=>`Puan = seçtiğiniz hedef için FieldRota'nın puanı (su, toprak ve iklim uyumu, en fazla 100), yıllık ortalama; plan bölgenin en çok su isteyen ürününden fazla kuyu suyu gerektirirse 0'ın altına inebilir. Görmediği iklim modellerinde beklenen puanın tam optimumu (dinamik programlama): <b>${opt}</b>. Yapay zekâ bunun <b>%${pct}</b>'ine ulaşıyor.`,
  rlWorse:(h,f)=>`<b>Dürüst not:</b> burada basit v1 araması yapay zekâdan daha iyi sonuç veriyor${h?`: gerçek 2015–2025 havasında ${h} puan`:""}${h&&f?",":""}${f?`${h?"":":"} görmediği iklim modellerinde ${f} puan`:""}. Yapay zekâ tek tek, gürültülü hava yıllarından öğreniyor ve tarlanızın gerçek geçmişinden başlıyor; v1 ise zaten kendi nöbetinizde olduğunuzu varsayıyor ve nöbetleri ortalama iklimle puanlıyor.`,
  rlBetter:(d)=>`Burada yapay zekâ görmediği verilerde v1'den ${d} puana kadar yukarıda: tarlanızın gerçek geçmişinden başlıyor ve on yıllar ısındıkça ürün değiştiriyor.`,
  rlTie:"Yapay zekâ ve v1 neredeyse aynı cevaba varıyor: birbirinden çok farklı iki yöntemin aynı sonucu bulması öneriyi daha güvenilir kılıyor.",
  rlCurve:"Öğrenme eğrisi: ajan pratik yaparken yıllık ortalama puan (sol = başlangıç, sağ = son)",
  rlHowS:"Yapay zekâ nasıl çalışıyor ve neyi bilmiyor",
  rlHow:`<ul><li><b>Yöntem:</b> tablolu Q-öğrenme. Durum = önceki iki ürün + on yıl (CMIP6 gelecekleriyle eğitimde) ya da geçen yılın yağışı (geçmiş havayla eğitimde). Eylem = sıradaki ürün; FieldRota kurallarıyla sınırlı (ürün listesi, her üç yılda üç farklı ürün, Konya'da çok su isteyen iki ürün arka arkaya gelmez, ekim ve hasat çakışmaz).</li><li><b>Ödül:</b> FieldRota'nın yıllık puanı: kuyu suyu, iklim uyumu ve toprak sağlığı, hedefinize göre ağırlıklı.</li><li><b>Simülatör:</b> FieldRota'nın kalibre edilmiş ürün değerleri, gerçek NASA POWER havasıyla yıl yıl hesaplanıyor (ET₀, yağış, her ürünün en hassas ayında 35 °C üstü günler). Gelecek yıllar her CMIP6 modelinin 2041–2060 eğilimini ve gerçek bir geçmiş yılın iniş çıkışlarını izliyor.</li><li><b>Test:</b> 1986–2008 ve 3 iklim modeliyle eğitildi; 3 eğitim denemesinden en iyisi 2009–2014 yılları ve 4. bir modelle (MRI-ESM2-0) seçildi; hiç görmediği 2015–2025 yılları ve 2 başka modelle (GFDL-ESM4, IPSL-CM6A-LR) test edildi.</li><li><b>Sınırlar:</b> verim doğrudan simüle edilmiyor (iklim uyumu onun yerine geçiyor); tek tarla, yılda tek ana ürün; topraktaki nem birikimi ve zararlılar modelde yok; fiyatlar puana girmiyor.</li></ul>`
});
const RLCACHE={};
async function rlLoad(k){ if(!(k in RLCACHE)){ try{ RLCACHE[k]=await (await fetch(`ai/${k}.json`)).json(); }catch(e){ RLCACHE[k]=null; } } return RLCACHE[k]; }
const rlBucket=y=>y<=2035?0:(y<=2045?1:2);
function rlPath(A,g,a2,a1){ const P=A.goals[g].policy, out=[]; for(let y=2027;y<=2060;y++){ const p=P[`${a2}|${a1}`]; if(!p) break; const a=p[rlBucket(y)]; out.push({y,u:a}); a2=a1; a1=a; } return out; }
const rlCol=u=>isFal(u)?"var(--bare)":`var(${FAMC[D.crops[u].family]})`;
function rlSpark(c){ if(!c||c.length<2) return ""; const mn=Math.min(...c), mx=Math.max(...c), W=600, H=80, sx=i=>i*(W-10)/(c.length-1)+5, sy=v=>H-5-(v-mn)/((mx-mn)||1)*(H-10);
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${t("rlCurve")}"><polyline fill="none" stroke="var(--good)" stroke-width="2.5" points="${c.map((v,i)=>`${sx(i).toFixed(1)},${sy(v).toFixed(1)}`).join(" ")}"/><text x="6" y="14" font-size="12" fill="var(--muted)">${fmt(mx,0)}</text><text x="6" y="${H-6}" font-size="12" fill="var(--muted)">${fmt(mn,0)}</text></svg>`; }
async function rlRender(){
  const sec=document.getElementById("rlSec"); if(!sec) return;
  ["rlT","rlH","rlHowS"].forEach(id=>document.getElementById(id).textContent=t(id)); document.getElementById("rlHow").innerHTML=t("rlHow");
  const reg=REGION, A=await rlLoad(reg); if(reg!==REGION) return;
  if(!A){ document.getElementById("rlPlan").innerHTML=`<p class="hint">ai/${reg}.json not found.</p>`; document.getElementById("rlTest").innerHTML=""; return; }
  const G=A.goals[goal], a2=current[1], a1=current[2], path=rlPath(A,goal,a2,a1);
  const chips=path.slice(0,10).map(p=>`<div class="chip"><small>${p.y}</small>${sh(p.u)||nm(p.u)}<i style="background:${rlCol(p.u)}"></i></div>`).join("");
  const strip=path.map(p=>`<div style="background:${rlCol(p.u)}" title="${p.y}: ${nm(p.u)}"></div>`).join("");
  const sets=[0,1,2].map(b=>[...new Set(path.filter(p=>rlBucket(p.y)===b).map(p=>p.u))]);
  const dec=sets.map((s,b)=>`<div><b>${t("rlDec")[b]}</b>${s.map(nm).join(", ")}</div>`).join("");
  // compare the settled rotation of the first decade (after the switch-over years) with the 2050s
  const early=[...new Set(path.filter(p=>p.y>=2030&&p.y<=2035).map(p=>p.u))], late=[...new Set(path.filter(p=>p.y>=2046).map(p=>p.u))];
  const drop=early.filter(u=>!late.includes(u)).map(nm).join(", "), add=late.filter(u=>!early.includes(u)).map(nm).join(", ");
  document.getElementById("rlPlan").innerHTML=`<h3>${t("rlPlanT")(nm(a2),nm(a1))}</h3><div class="chips">${chips}</div>
    <div class="hint">${t("rlStrip")}</div><div class="strip">${strip}</div><div class="dec">${dec}</div>
    <p style="margin:0">${drop||add?t("rlSwitch")(drop,add):t("rlSame")}</p>`;
  const pick=(arr,f)=>arr.find(f)||{};
  const isFarm=r=>r.policy.startsWith("Farmers");
  const H=G.hist_test, F=G.future_test;
  const rows=[["ai",r=>r.policy.startsWith("FieldRota-AI")],["v1",r=>r.policy.startsWith("FieldRota v1")],["farm",isFarm],["my",r=>r.policy.startsWith("Myopic")]];
  const cell=v=>v==null?"–":fmt(v,0), cell1=v=>v==null?"–":fmt(v,1);
  const body=rows.map(([k,f])=>{ const h=pick(H,f), fu=pick(F,f); const lab=k==="farm"?`${t("rlRows").farm}<br><small>${(G.farmer||[]).map(sh).join(" → ")}</small>`:t("rlRows")[k];
    return `<tr class="${k==="ai"?"me":""}"><th scope="row">${lab}</th><td class="num">${cell1(h.score)}</td><td class="num" style="color:var(--water)">${cell(h.irrigation_m3_da)}</td><td class="num">${cell1(fu.score)}</td><td class="num" style="color:var(--water)">${cell(fu.irrigation_m3_da)}</td><td class="num">${cell1(fu.worst_year)}</td></tr>`; }).join("");
  const ai=pick(F,rows[0][1]), v1=pick(F,rows[1][1]), opt=G.dp_opt["test models"], pct=fmt(Math.min(100,100*ai.score/opt),1);
  const aiH=pick(H,rows[0][1]), v1H=pick(H,rows[1][1]), dh=aiH.score-v1H.score, df=ai.score-v1.score;
  let verdict;
  if(Math.abs(dh)<1&&Math.abs(df)<1) verdict=t("rlTie");
  else if(dh<=-1||df<=-1) verdict=t("rlWorse")(dh<=-1?fmt(-dh,1):null, df<=-1?fmt(-df,1):null);
  else verdict=t("rlBetter")(fmt(Math.max(dh,df),1));
  document.getElementById("rlTest").innerHTML=`<h3>${t("rlTestT")}</h3><div class="tbl"><table style="min-width:640px"><colgroup><col style="width:220px"><col><col><col><col><col></colgroup><thead><tr>${t("rlCols").map(c=>`<th>${c}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div>
    <p class="hint" style="margin:0">${t("rlFoot")(fmt(opt,1),pct)}</p><div class="warn">${verdict}</div>
    <div class="hint">${t("rlCurve")}</div>${rlSpark(G.curve)}`;
}
{ const _r0=render; render=function(){ _r0(); rlRender(); }; }
rlRender();
"""

# 1) CSS
s = s.replace("</style>", CSS + "</style>", 1)
# 2) section after step 4 (before the heat section)
anchor = '<section class="step">\n  <h2 id="heatT"'
assert anchor in s, "anchor not found"
s = s.replace(anchor, SECTION.strip() + "\n\n" + anchor, 1)
# 3) JS before the last </script> that closes the main app script, then make sure render runs again
i = s.rindex("</script>")
s = s[:i] + JS + "\n" + s[i:]
open(path, "w", encoding="utf-8").write(s)
print("patched", path)
