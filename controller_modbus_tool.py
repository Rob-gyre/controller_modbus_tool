#!/usr/bin/env python3
"""Controller Serial Mapping Tool v4.1 - Modbus RTU and CAREL PJEZ."""
import json, sys, time
from pathlib import Path
try:
    import serial, serial.tools.list_ports, minimalmodbus
except ImportError as exc:
    print(f"Missing dependency: {exc}. Run: pip install -r requirements.txt")
    raise SystemExit(1)

ROOT=Path(__file__).resolve().parent; PROFILE_DIR=ROOT/"profiles"
STX,ETX,ENQ,ACK,NUL=2,3,5,6,0
KINDS={"holding":3,"input":4,"coil":1,"discrete":2}

# name: address, scale, signed, description, units, group, current, minimum, maximum
XR_MAPPED={
"Pb1":(256,10,True,"Probe 1 / room temperature","C","Live probes",None,-55,150),
"Pb2":(257,10,True,"Probe 2 / first evaporator temperature","C","Live probes",None,-55,150),
"Pb3":(258,10,True,"Probe 3 / second evaporator temperature","C","Live probes",None,-55,150),
"PbC":(769,1,False,"Kind of probe","","Probes","ntC",None,None),"Hy":(770,10,False,"Differential","C","Regulation",2.0,.1,25.5),
"LS":(771,10,True,"Minimum set point value","C","Regulation",-50,-55,2),"US":(772,10,True,"Maximum set point value","C","Regulation",50,2,150),
"ot":(773,10,True,"Thermostat probe calibration","C","Probes",0,-12,12),"AC":(774,1,False,"Anti-short cycle delay","min","Regulation",1,0,50),
"ALC":(776,1,False,"Temperature alarm configuration","","Alarm","Ab",None,None),"ALU":(777,10,True,"High temperature alarm","C","Alarm",50,-50,150),
"ALL":(778,10,True,"Low temperature alarm","C","Alarm",-50,-55,50),"ALd":(780,1,False,"Temperature alarm delay","min","Alarm",15,0,255),
"dAo":(781,1,False,"Alarm delay at start-up","min","Alarm",90,0,720),"odS":(782,1,False,"Output delay at start-up","min","Regulation",0,0,255),
"CCt":(783,1,False,"Continuous cycle duration","min","Regulation",0,0,990),"CCS":(784,10,True,"Continuous cycle set point","C","Regulation",2,-55,150),
"dAF":(785,1,False,"Defrost delay after fast freezing","min","Defrost",2,0,255),"idF":(786,1,False,"Interval between defrost cycles","hour","Defrost",4,0,250),
"dSd":(787,1,False,"Start defrost delay","min","Defrost",0,0,255),"MdF":(789,1,False,"Maximum first defrost length","min","Defrost",30,0,255),
"dtE":(790,10,True,"First evaporator defrost end temperature","C","Defrost",8,-55,50),"MdS":(792,1,False,"Maximum second defrost length","min","Defrost",30,0,255),
"FSt":(800,10,True,"Fan stop temperature","C","Fan",17,-55,50),"oE":(809,10,True,"Evaporator probe calibration","C","Probes",.6,-12,12),
"CF":(813,1,False,"Temperature measurement unit","","Regulation","C",None,None),"SEt":(853,10,True,"Set point","C","Regulation",2,-50,50)}

# Metadata imported from the same XR77U workbook; address deliberately unknown.
XR_UNMAPPED={
"tC":("Parameter map selection","","Other",6,1,7),"dtS":("Second evaporator defrost end temperature","C","Defrost",8,-55,50),
"dFd":("Display during defrost","","Defrost","dEF",None,None),"dAd":("Maximum display delay after defrost","min","Defrost",10,0,255),
"tdF":("Defrost type","","Defrost","EL",None,None),"Fdt":("Drain down time","min","Defrost",2,0,255),
"dPo":("First defrost after start-up","","Defrost","no",None,None),"FnC":("Fan operating mode","","Fan","O_n",None,None),
"Fnd":("Fan delay after defrost","min","Fan",7,0,255),"Fon":("Fan on time with compressor off","min","Fan",0,0,15),
"FoF":("Fan off time with compressor off","min","Fan",0,0,15),"P2P":("Evaporator probe presence","","Probes","yes",None,None),
"P3P":("Third probe presence","","Probes","yes",None,None),"o3":("Third probe calibration","C","Probes",0,-12,12),
"rES":("Display resolution","","Regulation","dE",None,None),"Lod":("Display visualisation","","Regulation","P1",None,None),
"dLy":("Display temperature update delay","min","Regulation",0,None,None),"Con":("Compressor ON time with faulty probe","min","Regulation",15,0,255),
"CoF":("Compressor OFF time with faulty probe","min","Regulation",30,0,255),"tbA":("Alarm output silencing by button","","Alarm","yes",None,None),
"diC":("Digital input 1 configuration","","Digital inputs","EAL",None,None),"diP":("Digital input 1 polarity","","Digital inputs","CL",None,None),
"did":("Digital input 1 alarm delay","min","Digital inputs",0,0,255),"di2":("Digital input 2 alarm delay","min","Digital inputs",0,0,255),
"odC":("Compressor and fan state with door open","","Digital inputs","no",None,None),"dot":("Alarm exclusion with door open","min","Alarm",20,0,255),
"rrd":("Regulation restart with door alarm","","Alarm","no",None,None),"HES":("Energy-saving differential","C","Probes",0,-30,30),
"onF":("On/off key configuration","","Configuration","nu",None,None),"bEn":("Buzzer enabled","","Configuration","yes",None,None),
"Ptb":("Map code","","Other",3,0,65535),"rEL":("Software release","","Other",None,None,None),
"Prd":("Room probe display","C","Other",None,None,None),"dP2":("Evaporator probe display","C","Other",None,None,None),
"dP3":("Third probe display","C","Other",None,None,None)}

CAREL={"Pb1":("S11",10,True,"Probe 1","C"),"Pb2":("S21",10,True,"Probe 2","C"),"Pb3":("S31",10,True,"Probe 3","C"),
"St":("S81",10,True,"Setpoint","C"),"rd":("S91",10,True,"Differential","C"),"LSE":("S:1",10,True,"Minimum setpoint","C"),
"HSE":("S;1",10,True,"Maximum setpoint","C"),"/C1":("S51",10,True,"Probe 1 calibration","C"),"/C2":("S61",10,True,"Probe 2 calibration","C"),
"F1":("SC1",10,True,"Fan stop temperature","C"),"AL":("S?1",10,True,"Low alarm","C"),"AH":("S@1",10,True,"High alarm","C"),
"dt":("S=1",10,True,"Defrost end temperature","C"),"c1":("U<1",1,False,"Minimum between starts","min"),"c2":("U=1",1,False,"Minimum OFF time","min"),
"c3":("U>1",1,False,"Minimum ON time","min"),"d0":("UB1",1,False,"Defrost type",""),"d1":("UC1",1,False,"Defrost interval","hour"),
"dP":("UD1",1,False,"Maximum defrost time","min"),"d5":("UE1",1,False,"Defrost delay","min"),"dd":("UF1",1,False,"Drain time","min"),
"d8":("UG1",1,False,"Defrost priority",""),"Fd":("UL1",1,False,"Fan delay","min"),"d4":("BL1",1,False,"Defrost at power-on","bool"),
"d6":("BM1",1,False,"Display during defrost","bool"),"d9":("BN1",1,False,"Defrost priority","bool"),"dC":("BO1",1,False,"Defrost time base","bool"),
"F0":("BQ1",1,False,"Fan control","bool"),"F2":("BR1",1,False,"Fans cycle with compressor","bool"),"F3":("BS1",1,False,"Fans in defrost","bool")}

def ask(text,default=None):
    v=input(text+(f" [{default}]" if default is not None else "")+": ").strip(); return v or (str(default) if default is not None else "")
def yesno(text,default=False):
    v=input(f"{text} [{'Y/n' if default else 'y/N'}]: ").strip().lower(); return default if not v else v in ("y","yes")
def s16(v): return v-65536 if v>=32768 else v
def pname(n): return "".join(c.lower() if c.isalnum() else "_" for c in n).strip("_")
def save(p):
    PROFILE_DIR.mkdir(exist_ok=True); path=PROFILE_DIR/f"{pname(p['name'])}.json"; path.write_text(json.dumps(p,indent=2),encoding="utf-8"); print(f"Saved {path}")

def seed():
    PROFILE_DIR.mkdir(exist_ok=True)
    if not (PROFILE_DIR/"xr77u.json").exists():
        ps={}
        for n,(a,sc,sg,d,u,g,cur,lo,hi) in XR_MAPPED.items(): ps[n]={"address":a,"register_type":"holding","scale":sc,"signed":sg,"description":d,"units":u,"group":g,"current":cur,"minimum":lo,"maximum":hi,"access":"unknown","verification":"mapped_unverified"}
        for n,(d,u,g,cur,lo,hi) in XR_UNMAPPED.items(): ps[n]={"description":d,"units":u,"group":g,"current":cur,"minimum":lo,"maximum":hi,"verification":"unmapped"}
        save({"name":"XR77U","protocol":"modbus_rtu","model":"XR77U / 2C310000","firmware":"5.9","connection":{"port":"/dev/ttyUSB0","slave":1,"baudrate":9600,"parity":"N","stopbits":1,"timeout":.6},"parameters":ps})
    if not (PROFILE_DIR/"carel_pjezc0p000.json").exists():
        ps={n:{"token":t,"scale":sc,"signed":sg,"description":d,"units":u,"verification":"live_confirmed","access":"read_write"} for n,(t,sc,sg,d,u) in CAREL.items()}
        save({"name":"CAREL PJEZC0P000","protocol":"carel_pjez","connection":{"port":"/dev/ttyACM0","unit":1,"baudrate":19200,"parity":"N","stopbits":2},"parameters":ps})

def get_profiles(protocol=None):
    seed(); out=[]
    for f in sorted(PROFILE_DIR.glob("*.json")):
        try:
            p=json.loads(f.read_text(encoding="utf-8"))
            if p.get("name")=="XR77U":
                changed=False; items=p.setdefault("parameters",{})
                for n,(a,sc,sg,d,u,g,cur,lo,hi) in XR_MAPPED.items():
                    if n not in items:items[n]={"address":a,"register_type":"holding","scale":sc,"signed":sg,"description":d,"units":u,"group":g,"current":cur,"minimum":lo,"maximum":hi,"access":"read","verification":"mapped_unverified"};changed=True
                for n,(d,u,g,cur,lo,hi) in XR_UNMAPPED.items():
                    if n not in items:items[n]={"description":d,"units":u,"group":g,"current":cur,"minimum":lo,"maximum":hi,"verification":"unmapped"};changed=True
                if changed:save(p)
            if protocol is None or p.get("protocol")==protocol: out.append(p)
        except Exception as e: print(f"Could not load {f.name}: {e}")
    return out
def choose_profile(protocol=None):
    ps=get_profiles(protocol)
    for i,p in enumerate(ps,1): print(f" {i}) {p['name']} ({p['protocol']})")
    try:return ps[int(ask("Select profile",1))-1]
    except (ValueError,IndexError):return None

def configure(previous=None):
    print("\nCONNECTION SETUP (used until you choose Change connection)")
    if previous and yesno("Reuse current connection",True): return previous
    print(" 1) Modbus RTU\n 2) CAREL PJEZ TTL"); proto="modbus_rtu" if ask("Protocol",1)=="1" else "carel_pjez"; profile=choose_profile(proto)
    if not profile:return None
    d=profile.get("connection",{})
    if proto=="modbus_rtu": conn={"port":ask("Serial port",d.get("port","/dev/ttyUSB0")),"slave":int(ask("Slave address",d.get("slave",1))),"baudrate":int(ask("Baud",d.get("baudrate",9600))),"parity":ask("Parity N/E/O",d.get("parity","N")).upper(),"stopbits":int(ask("Stop bits",d.get("stopbits",1))),"timeout":float(ask("Timeout",d.get("timeout",.6)))}
    else: conn={"port":ask("Serial port",d.get("port","/dev/ttyACM0")),"unit":int(ask("Unit",d.get("unit",1))),"baudrate":19200,"parity":"N","stopbits":2}
    profile["connection"]=conn; save(profile); return {"protocol":proto,"profile":profile,"connection":conn,"discovery":None}

def inst(c):
    d=minimalmodbus.Instrument(c["port"],c["slave"],mode=minimalmodbus.MODE_RTU); d.serial.baudrate=c["baudrate"]; d.serial.bytesize=8
    d.serial.parity={"N":serial.PARITY_NONE,"E":serial.PARITY_EVEN,"O":serial.PARITY_ODD}[c["parity"]]; d.serial.stopbits=c["stopbits"]; d.serial.timeout=c["timeout"]; d.clear_buffers_before_each_transaction=True; return d
def readloc(d,kind,address):
    try:return d.read_bit(address,functioncode=KINDS[kind]) if kind in ("coil","discrete") else d.read_register(address,0,functioncode=KINDS[kind],signed=False)
    except Exception:return None
def scan(session,kinds=None,ask_range=True,quiet=False):
    if session["protocol"]!="modbus_rtu":print("Modbus discovery requires a Modbus connection.");return None
    if kinds is None:
        print(" 1) All read areas\n 2) Holding FC03\n 3) Input FC04\n 4) Coils FC01\n 5) Discrete inputs FC02")
        ch=ask("Scan selection",1); kinds={"1":list(KINDS),"2":["holding"],"3":["input"],"4":["coil"],"5":["discrete"]}.get(ch,list(KINDS))
    start=int(ask("Starting address",0)) if ask_range else 0; end=int(ask("Ending address",999)) if ask_range else 999; d=inst(session["connection"]); result={k:{} for k in kinds}
    print("Read-only discovery. No values will be written.")
    for kind in kinds:
        for address in range(start,end+1):
            value=readloc(d,kind,address)
            if value is not None:
                result[kind][address]=value
                if not quiet:print(f" FOUND {kind} {address} raw={value}")
            if address and address%100==0:print(f" {kind}: through {address}, readable={len(result[kind])}")
        print(f"{kind}: {len(result[kind])} readable")
    session["discovery"]={"start":start,"end":end,"values":result}; (ROOT/"last_discovery.json").write_text(json.dumps(session["discovery"],indent=2),encoding="utf-8"); return result

def test(session):
    if session["protocol"]=="carel_pjez":
        try:d=PJEZ(session["connection"]["port"],session["connection"]["unit"]); r=d.identity();d.close();print(f"SUCCESS: CAREL identity {r.hex(' ')}" if r.startswith(bytes([STX])) else "No CAREL response.")
        except Exception as e:print(f"Connection failed: {e}")
        return
    d=inst(session["connection"]); candidates=[(i.get("register_type","holding"),i["address"]) for i in session["profile"]["parameters"].values() if "address" in i]
    for kind,address in candidates:
        v=readloc(d,kind,address)
        if v is not None:print(f"SUCCESS: {kind} {address} raw={v}");return
    print("No valid response. Check port, address, settings, A/B polarity and port ownership.")

def read_profile(session):
    p=session["profile"]
    if session["protocol"]=="carel_pjez":
        d=PJEZ(session["connection"]["port"],session["connection"]["unit"]); values=d.dump();d.close()
        for n,i in p["parameters"].items():
            raw=values.get(i.get("token")); val="N/A" if raw is None else f"{(s16(raw) if i.get('signed') else raw)/float(i.get('scale',1)):g}";print(f"{n:<8}{val:>10} {i.get('units',''):<5} {i.get('token','')}")
        return
    d=inst(session["connection"])
    for n,i in p["parameters"].items():
        if "address" not in i:continue
        raw=readloc(d,i.get("register_type","holding"),i["address"]); val="N/A" if raw is None else f"{(s16(raw) if i.get('signed') else raw)/float(i.get('scale',1)):g}"
        print(f"{n:<8}{val:>10} {i.get('units',''):<5} {i.get('register_type','holding')[0].upper()}:{i['address']} {i.get('verification','')}")

def possible(values,target,item):
    out=[]; preferred_signed=(item.get("minimum") is not None and isinstance(item.get("minimum"),(int,float)) and item["minimum"]<0)
    for kind,locations in values.items():
        for address,raw in locations.items():
            for signed in (preferred_signed,not preferred_signed):
                number=s16(raw) if signed else raw
                for scale in (1,10,100,1000):
                    if abs(number/scale-target)<1e-7:out.append((0 if signed==preferred_signed else 1,kind,address,raw,scale,signed))
    unique={ (x[1],x[2],x[4],x[5]):x for x in out};return sorted(unique.values())
def delta_candidates(before,after,old,new,item):
    out=[]
    for kind,locs in before.items():
        for address,br in locs.items():
            if address not in after.get(kind,{}) or after[kind][address]==br:continue
            ar=after[kind][address]
            for signed in (False,True):
                b=s16(br) if signed else br;a=s16(ar) if signed else ar
                if new!=old and (a-b)/(new-old)>0:
                    exact=(a-b)/(new-old);scale=min((1,10,100,1000),key=lambda q:abs(q-exact));score=abs(exact-scale)+abs(b/scale-old)+abs(a/scale-new);out.append((score,kind,address,br,ar,scale,signed))
    return sorted(out)

def refresh(session,template):
    d=inst(session["connection"]);out={}
    for kind,locations in template.items():
        out[kind]={}
        for address in locations:
            value=readloc(d,kind,int(address))
            if value is not None:out[kind][int(address)]=value
    return out
def choose_unmapped(p):
    items=[(n,i) for n,i in p["parameters"].items() if "address" not in i and "token" not in i]
    for x,(n,i) in enumerate(items,1):print(f" {x}) {n:<5} {i.get('description','')}")
    try:return items[int(ask("Select parameter",1))-1]
    except (ValueError,IndexError):return None,None

def mapping_session(session):
    if session["protocol"]=="carel_pjez":
        map_carel_session(session);return
    if not session.get("discovery"):
        print("A discovery snapshot is needed once for this mapping session.");values=scan(session)
    else:values=session["discovery"]["values"]
    if not values:return
    mapped=[]
    while True:
        name,item=choose_unmapped(session["profile"])
        if not name:break
        current=item.get("current"); raw=ask("Controller current value",current)
        try:current=float(raw)
        except ValueError:print("Text/enumerated values require before/after mapping for now.");continue
        current_values=refresh(session,values); matches=possible(current_values,current,item)
        if len(matches)==1:
            _,kind,address,raw,scale,signed=matches[0];print(f"One exact match: {kind} {address}, raw {raw}, scale {scale}, signed={signed}")
            if yesno("Save as probable mapping",True):
                item.update({"register_type":kind,"address":address,"scale":scale,"signed":signed,"access":"read","verification":"value_matched"});save(session["profile"]);mapped.append(name)
        else:
            print(f"{len(matches)} exact interpretations found. A change is needed to distinguish them.")
            if not yesno("Change this parameter now",True):continue
            input("Change only this parameter, exit the keypad menu, then press ENTER...")
            try:new=float(ask("New displayed value"))
            except ValueError:continue
            after=refresh(session,current_values); cs=delta_candidates(current_values,after,current,new,item)
            for x,c in enumerate(cs[:20],1):print(f" {x}) {c[1]} {c[2]} raw {c[3]}->{c[4]}, scale {c[5]}, signed={c[6]}")
            if not cs:print("No matching change found.");continue
            try:c=cs[int(ask("Select candidate",1))-1];scale=float(ask("Confirm/edit scale",c[5]))
            except (ValueError,IndexError):continue
            if yesno(f"Save {name} as {c[1]} {c[2]}",True):item.update({"register_type":c[1],"address":c[2],"scale":scale,"signed":c[6],"access":"read","verification":"change_verified"});save(session["profile"]);mapped.append(name)
        print(f"Mapped this session: {', '.join(mapped) or 'none'}")
        if not yesno("Map another parameter",True):break

def verify(session):
    p=session["profile"]; mapped=[(n,i) for n,i in p["parameters"].items() if "address" in i or "token" in i]
    print(" 1) Verify one from current value\n 2) Verify all against saved current values\n 3) Review statuses");ch=ask("Select",1)
    if ch=="3":
        for n,i in mapped:print(f"{n:<8}{i.get('verification','unknown')}")
        return
    if session["protocol"]!="modbus_rtu":print("CAREL verification will use its next live dump implementation.");return
    d=inst(session["connection"]); targets=mapped
    if ch=="1":
        for x,(n,i) in enumerate(mapped,1):print(f" {x}) {n}")
        try:targets=[mapped[int(ask("Select",1))-1]]
        except (ValueError,IndexError):return
    for n,i in targets:
        raw=readloc(d,i.get("register_type","holding"),i["address"])
        if raw is None:print(f"{n}: no response");continue
        decoded=(s16(raw) if i.get("signed") else raw)/float(i.get("scale",1)); expected=i.get("current")
        print(f"{n}: decoded={decoded:g}, saved current={expected}")
        if expected is not None and isinstance(expected,(int,float)) and abs(decoded-float(expected))<1e-7:i["verification"]="value_verified"
        elif ch=="1":
            try:shown=float(ask("Value shown on controller"))
            except ValueError:continue
            if abs(decoded-shown)<1e-7:i["verification"]="value_verified";i["current"]=shown
    save(p)

def write_modbus(session):
    p=session["profile"]; mapped=[(n,i) for n,i in p["parameters"].items() if "address" in i and i.get("register_type")=="holding"]
    for x,(n,i) in enumerate(mapped,1):print(f" {x}) {n} H:{i['address']}")
    try:n,i=mapped[int(ask("Select",1))-1];value=float(ask("Value to write"))
    except (ValueError,IndexError):return
    raw=int(round(value*float(i.get("scale",1))));print(f"WARNING: leaves controller changed. {n}={value:g}, H:{i['address']}, raw={raw}")
    if ask("Type WRITE to confirm")!="WRITE":return
    d=inst(session["connection"])
    try:d.write_register(i["address"],raw,0,functioncode=6,signed=i.get("signed",False));time.sleep(.3);print(f"Read-back raw: {readloc(d,'holding',i['address'])}")
    except Exception as e:print(f"Write failed: {e}");return
    if yesno(f"Does controller show {value:g}"):i["verification"]="write_verified";i["access"]="read_write";i["current"]=value;save(p)

def chex(text):
    r=0
    for c in text:
        v=ord(c)-48 if "0"<=c<="9" or ":"<=c<="?" else ord(c)-55 if "A"<=c<="F" else ord(c)-87 if "a"<=c<="f" else 0;r=(r<<4)|(v&15)
    return r
def packet(body):
    core=bytes([STX])+body.encode("ascii")+bytes([ETX]);v=sum(core)&255;return core+bytes([48+(v>>4),48+(v&15)])
class PJEZ:
    def __init__(self,port,unit):self.unit=unit;self.slot=chr(48+unit);self.ser=serial.Serial(port,19200,bytesize=8,parity="N",stopbits=2,timeout=.5)
    def close(self):self.ser.close()
    def send(self,body):
        self.ser.reset_input_buffer();self.ser.write(packet(body));end=time.monotonic()+.8
        while time.monotonic()<end:
            b=self.ser.read(1)
            if b and b[0]==ACK:return True
        return False
    def identity(self):
        self.ser.reset_input_buffer();self.ser.write(packet(f"{self.slot}?"));end=time.monotonic()+1;d=bytearray()
        while time.monotonic()<end:
            b=self.ser.read(1);d+=b
            if ETX in d:d+=self.ser.read(2);break
        return bytes(d)
    def event(self):
        end=time.monotonic()+.8
        while time.monotonic()<end:
            b=self.ser.read(1)
            if not b:continue
            if b[0]==NUL:return b
            if b[0]!=STX:continue
            d=bytearray(b)
            while time.monotonic()<end:
                c=self.ser.read(1);d+=c
                if c and c[0]==ETX:d+=self.ser.read(2);return bytes(d)
        return None
    def dump(self):
        vals={};nulls=0
        if not self.send(f"{self.slot}F1"):return vals
        for _ in range(180):
            self.ser.write(bytes([ENQ,48+self.unit]));f=self.event()
            if f==bytes([NUL]):nulls+=1
            elif f:
                nulls=0;self.ser.write(bytes([ACK]))
                try:b=f[1:f.index(ETX)].decode("ascii","ignore");vals[b[1:4]]=chex(b[4:])&65535
                except Exception:pass
            if nulls>=50:break
        return vals
    def write_token(self,token,raw,password=0x16):
        if not self.send(f"{self.slot}U71{password:04X}"):return False
        if not self.send(f"{self.slot}A00001"):return False
        body=f"{self.slot}D{token[1]}{'1' if raw else '0'}" if token.startswith("B") else f"{self.slot}A{token[1]}{raw&65535:04X}"
        return self.send(body)

def map_carel_session(session):
    p=session["profile"];mapped=[]
    while True:
        print("Capturing CAREL F1 table dump...");d=PJEZ(session["connection"]["port"],session["connection"]["unit"]);before=d.dump()
        name=ask("Parameter name");item=p.get("parameters",{}).get(name,{"description":name,"units":""})
        try:old=float(ask("Controller current value",item.get("current")))
        except (ValueError,TypeError):d.close();print("Numeric value required.");return
        matches=possible({"token":before},old,item)
        if len(matches)==1:
            _,_,token,raw,scale,signed=matches[0];print(f"One exact match: token {token}, raw {raw}, scale {scale}, signed={signed}")
            if yesno("Save as probable mapping",True):item.update({"token":str(token),"scale":scale,"signed":signed,"access":"read","verification":"value_matched"});p.setdefault("parameters",{})[name]=item;save(p);mapped.append(name)
        else:
            print(f"{len(matches)} exact interpretations found. Change is needed to distinguish them.")
            if yesno("Change this parameter now",True):
                input("Change only this parameter, exit its menu, then press ENTER...")
                try:new=float(ask("New displayed value"))
                except ValueError:d.close();return
                after=d.dump();cs=delta_candidates({"token":before},{"token":after},old,new,item)
                for x,c in enumerate(cs[:20],1):print(f" {x}) token {c[2]} raw {c[3]}->{c[4]}, scale {c[5]}, signed={c[6]}")
                if cs:
                    try:c=cs[int(ask("Select candidate",1))-1];scale=float(ask("Confirm/edit scale",c[5]))
                    except (ValueError,IndexError):d.close();return
                    if yesno(f"Save {name} as token {c[2]}",True):item.update({"token":str(c[2]),"scale":scale,"signed":c[6],"access":"read","verification":"change_verified"});p.setdefault("parameters",{})[name]=item;save(p);mapped.append(name)
        d.close();print(f"Mapped this session: {', '.join(mapped) or 'none'}")
        if not yesno("Map another parameter",True):return

def write_carel(session):
    p=session["profile"];items=[(n,i) for n,i in p["parameters"].items() if "token" in i]
    for x,(n,i) in enumerate(items,1):print(f" {x}) {n} token {i['token']}")
    try:n,i=items[int(ask("Select",1))-1];value=float(ask("Value to write"));password=int(ask("Password","0x16"),0)
    except (ValueError,IndexError):return
    raw=int(round(value*float(i.get("scale",1))))&65535;print(f"WARNING: leaves controller changed. {n}={value:g}, token {i['token']}, raw=0x{raw:04X}")
    if ask("Type WRITE to confirm")!="WRITE":return
    d=PJEZ(session["connection"]["port"],session["connection"]["unit"]);ok=d.write_token(i["token"],raw,password);d.close();print("Write ACK received." if ok else "Write failed or no ACK.")

def ports():
    for p in serial.tools.list_ports.comports():print(f"{p.device}: {p.description} [{p.hwid}]")
def active(s):
    c=s["connection"];return f"{c['port']} | {s['protocol']} | "+(f"address {c['slave']} | {c['baudrate']} 8{c['parity']}{c['stopbits']}" if s["protocol"]=="modbus_rtu" else f"unit {c['unit']} | 19200 8N2")
def main():
    seed();session=configure()
    if not session:return 1
    while True:
        print("\n"+"="*64+f"\nACTIVE: {active(session)}\nPROFILE: {session['profile']['name']}\n"+"="*64)
        print("1) Test connection\n2) Read mapped values\n3) Discover readable locations\n4) Map parameters")
        print("5) Verify mapped parameters\n6) Controlled write verification\n7) View profile\n8) Change connection\n9) List serial devices\n0) Exit")
        ch=ask("Select",1)
        if ch=="1":test(session)
        elif ch=="2":read_profile(session)
        elif ch=="3":scan(session)
        elif ch=="4":mapping_session(session)
        elif ch=="5":verify(session)
        elif ch=="6":write_modbus(session) if session["protocol"]=="modbus_rtu" else write_carel(session)
        elif ch=="7":print(json.dumps(session["profile"],indent=2))
        elif ch=="8":session=configure(session) or session
        elif ch=="9":ports()
        elif ch=="0":return 0
if __name__=="__main__":
    try:raise SystemExit(main())
    except KeyboardInterrupt:print("\nStopped safely.");raise SystemExit(130)
