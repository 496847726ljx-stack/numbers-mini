import json, re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

JST=ZoneInfo("Asia/Tokyo")
now=datetime.now(JST)
headers={"User-Agent":"Mozilla/5.0 NumbersMiniResearch/1.0"}

def month_url(dt):
    return f"https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers3/index.html?month={dt.month}&year={dt.year}"

def parse_month(dt):
    html=requests.get(month_url(dt),headers=headers,timeout=30).text
    soup=BeautifulSoup(html,"html.parser")
    out=[]
    for tr in soup.select("table tr"):
        cells=[x.get_text(" ",strip=True) for x in tr.select("th,td")]
        if len(cells)<3: continue
        txt=" | ".join(cells)
        m=re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日",txt)
        nums=re.findall(r"(?<!\d)(\d{3})(?!\d)",txt)
        if not m or not nums: continue
        num=nums[0]
        # Try to recover draw number and sales amount from row text.
        no_match=re.search(r"(?:第)?(\d{3,5})回",txt)
        sales=re.findall(r"[\d,]{5,}",txt)
        sales_val=int(sales[-1].replace(",","")) if sales else 0
        out.append({"no":int(no_match.group(1)) if no_match else 0,
                    "date":f"{m.group(1)}/{int(m.group(2)):02d}/{int(m.group(3)):02d}",
                    "number":num,"sales":sales_val})
    return out

rows=[]
for k in range(8):
    d=(now.replace(day=1)-timedelta(days=35*k)).replace(day=1)
    try: rows.extend(parse_month(d))
    except Exception: pass

# de-duplicate and sort
uniq={ (x["date"],x["number"]):x for x in rows if x["number"] }
rows=sorted(uniq.values(),key=lambda x:(x["date"],x["no"]),reverse=True)
if not rows: raise SystemExit("No official data parsed")
rows=rows[:200]

from collections import Counter
last=rows[0]
pair_hits=Counter(x["number"][-2:] for x in rows[:100])
tens=Counter(x["number"][-2] for x in rows[:50])
units=Counter(x["number"][-1] for x in rows[:50])

sc=[]
for a in range(10):
  for b in range(10):
    p=f"{a}{b}"
    idx=next((i for i,x in enumerate(rows) if x["number"][-2:]==p),None)
    miss=idx if idx is not None else 100
    score=(tens[str(a)]/50*45)+(units[str(b)]/50*45)+(pair_hits[p]/100*20)+(min(miss,30)/30*10)
    sc.append({"pair":p,"score":score,"tens":tens[str(a)],"units":units[str(b)],
               "pair_hits":pair_hits[p],"miss":miss})
sc.sort(key=lambda x:x["score"],reverse=True)

dc=Counter()
for x in rows[:50]:
  dc[x["number"][-2]]+=1; dc[x["number"][-1]]+=1
ds=sorted(dc.items(),key=lambda z:(-z[1],z[0]))
payload={
 "updated_jst":now.strftime("%Y-%m-%d %H:%M"),
 "next_draw":(now+timedelta(days=1)).strftime("%Y-%m-%d") if now.weekday()<4 else "",
 "last":last,"top3":sc[:3],
 "hot":[{"d":d,"c":c} for d,c in ds[:3]],
 "cold":[{"d":d,"c":c} for d,c in ds[-3:]],
 "recent10":rows[:10]
}
Path="data.json"
open(Path,"w",encoding="utf-8").write(json.dumps(payload,ensure_ascii=False,indent=2))
