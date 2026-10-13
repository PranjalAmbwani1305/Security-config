"""Post-deploy smoke test. Creates two throwaway organizations in the target API and walks the
whole workflow (register, every technology checklist, engagement, assessment, finding, risk,
evidence, tenant isolation, error codes).

    API_URL=https://your-api.vercel.app WEB_ORIGIN=https://your-web.vercel.app python scripts/smoke_e2e.py
Needs: pip install httpx.  Exits non-zero if anything fails.
"""
import os, sys, time, httpx, urllib.parse
B=os.environ.get("API_URL","http://localhost:8000").rstrip("/"); O={"Origin":os.environ.get("WEB_ORIGIN","http://localhost:5173")}
RUN=str(int(time.time()))
c=httpx.Client(base_url=B,headers=O,timeout=60)
bad=[]
def call(label,method,path,tok=None,expect=(200,201),**kw):
    h={"Authorization":f"Bearer {tok}"} if tok else {}
    r=c.request(method,path,headers=h,**kw)
    ok=r.status_code in expect
    if not ok: bad.append(label)
    msg=""
    if r.status_code>=400:
        try: msg=r.json().get("detail","")
        except Exception: msg=r.text[:80]
    print(("OK  " if ok else "FAIL"),r.status_code,label,msg)
    return r
def reg(email,org=None):
    r=call(f"register {email}","post","/auth/register",json={"email":email,"password":"Str0ng!Passw0rd#1","full_name":"U "+email,"organization_name":org})
    return r.json()
A=reg(f"smoke-a-{RUN}@example.com",f"Smoke A {RUN}"); B2=reg(f"smoke-b-{RUN}@example.com",f"Smoke B {RUN}")
ta=A["access_token"]; tb=B2["access_token"]
me=call("me","get","/auth/me",ta).json(); print("   perms:",len(me.get("permissions",[])))
techs=[t["name"] for t in call("technologies","get","/technologies",ta).json()["technologies"]]
for n in techs:                       # every technology: checklist + engagement
    q=urllib.parse.quote(n,safe="")
    r=call(f"checklist {n}","get",f"/checklists/{q}",ta)
code="ENG-1"; tech="Windows Server / Active Directory"
call("create engagement","post","/engagements",ta,json={"engagement_id":code,"client_name":"Acme","technology":tech,"reviewer":"Rev"})
call("dup engagement -> 409","post","/engagements",ta,expect=(409,),json={"engagement_id":code,"client_name":"Acme","technology":tech,"reviewer":"Rev"})
cl=call("checklist","get","/checklists/"+urllib.parse.quote(tech,safe=""),ta).json()["checklist"]; ids=[x["item_id"] for x in cl]
res=[{"item_id":i,"status":"Non-Compliant" if k==0 else "Compliant","notes":""} for k,i in enumerate(ids)]
call("save assessment","post","/assessments",ta,json={"engagement_id":code,"results":res})
r=call("load assessment","get",f"/assessments/{code}",ta); assert len(r.json()["assessments"][0]["results"])==len(ids)
call("finding","post","/findings",ta,json={"finding_id":"F-1","engagement_id":code,"item_id":ids[0],"title":"t","description":"d","severity":"High","recommendation":"r","status":"Open"})
call("risk","post","/risks",ta,json={"risk_id":"R-1","engagement_id":code,"finding_id":"F-1","title":"t","likelihood":4,"impact":5,"treatment":"Mitigate","owner":"o","status":"Open"})
call("evidence","post","/evidence",ta,json={"engagement_id":code,"item_id":ids[0],"evidence":"config excerpt"})
ev=call("evidence list","get",f"/evidence/{code}",ta).json()["evidence"]; print("   evidence row:",{k:ev[0][k] for k in("item_id","kind","review_status","uploaded_by")})
call("bad finding severity -> 422","post","/findings",ta,expect=(422,),json={"finding_id":"F-2","engagement_id":code,"item_id":ids[0],"title":"t","severity":"Nope","status":"Open"})
call("bad evidence item -> 422","post","/evidence",ta,expect=(422,),json={"engagement_id":code,"item_id":"ZZZ","evidence":"x"})
call("ai ask","post","/ai/ask",ta,json={"question":"explain risk","context":{}})
call("audit logs","get","/audit-logs?limit=15",ta)
call("unknown route -> 404","get","/nope",ta,expect=(404,))
call("no token -> 401","get","/engagements",None,expect=(401,))
# tenant isolation
r=call("org B sees no engagements","get","/engagements",tb); assert r.json()["engagements"]==[],r.json()
call("org B cannot read A's evidence -> 404","get",f"/evidence/{code}",tb,expect=(404,))
call("org B cannot read A's findings -> 404","get",f"/findings/{code}",tb,expect=(404,))
# token refresh
call("refresh","post","/auth/refresh",expect=(200,),json={"refresh_token":A["refresh_token"]})
print("\nFAILED:",bad or "none")
sys.exit(1 if bad else 0)
