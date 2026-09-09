#!/usr/bin/env python3
"""Controller Serial Mapping Tool v4.1 - Modbus RTU and CAREL PJEZ."""
import csv, json, shutil, sys, time
from pathlib import Path
try:
    import serial, serial.tools.list_ports, minimalmodbus
except ImportError as exc:
    print(f"Missing dependency: {exc}. Run: pip install -r requirements.txt")
    raise SystemExit(1)

ROOT=Path(__file__).resolve().parent; PROFILE_DIR=ROOT/"profiles"; EXPORT_DIR=ROOT/"exports"; DISCOVERY_DIR=ROOT/"discoveries"
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

# Enumerated values documented in the Universal-R manual.  These are controller
# setting codes, not discovered Modbus addresses.  The mapper still uses a
# before/after scan to prove which register belongs to each parameter.
XR_ENUMS={
"tC":{"1":"On/off thermostat - cooling","2":"Off-cycle timed defrost","3":"Time/time forced defrost","4":"Time/temperature defrost","5":"Time/temperature defrost with fan delay","6":"Double evaporator defrost","7":"On/off thermostat - heating"},
"PbC":{"0":"PTC probe","1":"NTC probe"},
"ALC":{"0":"Alarms relative to setpoint","1":"Absolute alarms"},
"dFd":{"0":"Real temperature","1":"Temperature at defrost start","2":"Setpoint","3":"dEF label","4":"dEG label"},
"tdF":{"0":"Electrical defrost","1":"Hot-gas defrost"},
"dPo":{"0":"After normal interval","1":"Immediate defrost after power-up"},
"FnC":{"0":"Cycles with compressor; off in defrost","1":"Always on; off in defrost","2":"Cycles with compressor; on in defrost","3":"Always on; on in defrost"},
"P2P":{"0":"Evaporator probe absent","1":"Evaporator probe present"},
"P3P":{"0":"Third probe absent","1":"Third probe present"},
"rES":{"0":"Decimal point shown","1":"No decimal point"},
"CF":{"0":"Celsius","1":"Fahrenheit"},
"Lod":{"0":"Thermostat probe","1":"Evaporator probe","2":"Third probe","3":"Setpoint"},
"tbA":{"0":"Mute buzzer only","1":"Mute buzzer and alarm relay"},
"diC":{"0":"Start defrost","1":"Door switch","2":"Auxiliary relay","3":"Energy saving","4":"Remote on/off","5":"Generic alarm","6":"Serious alarm"},
"diP":{"0":"Closed-circuit activation","1":"Open-circuit activation"},
"odC":{"0":"No output change","1":"Fan off","2":"Compressor off","3":"Compressor and fan off"},
"oAC":{"0":"Alarm relay","1":"Heater/dead-band relay","2":"Auxiliary relay","3":"Second compressor","4":"Light output","5":"Second defrost output"},
"rrd":{"0":"Do not restart regulation","1":"Restart regulation"},
"onF":{"0":"Key disabled","1":"On/off enabled","2":"Energy-saving enabled"},
"bEn":{"0":"Buzzer disabled","1":"Buzzer enabled"}}

# Numeric formats stated by the Universal-R manual.
# name: (scale operation, scale factor, signed)
XR_FORMATS={
"dtS":("divide",10,True),"dAd":("divide",1,False),"Fdt":("divide",1,False),
"Fnd":("divide",1,False),"Fon":("divide",1,False),"FoF":("divide",1,False),
"o3":("divide",10,True),"dLy":("divide",1,False),"Con":("divide",1,False),
"CoF":("divide",1,False),"did":("divide",1,False),"di2":("divide",1,False),
"dot":("divide",1,False),"HES":("divide",10,True),"Ptb":("divide",1,False),"rEL":("divide",10,False),
"Prd":("divide",10,True),"dP2":("divide",10,True),"dP3":("divide",10,True)}

XR_READ_ONLY={"Ptb","rEL","Prd","dP2","dP3"}
XR_MAP_WITHOUT_CHANGE={"tC"}

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

class BackToMenu(Exception):pass

def ask(text,default=None):
    v=input(text+(f" [{default}]" if default is not None else "")+" (B=Back): ").strip()
    if v.lower()=="b":raise BackToMenu
    return v or (str(default) if default is not None else "")
def yesno(text,default=False):
    v=input(f"{text} [{'Y/n' if default else 'y/N'}] (B=Back): ").strip().lower()
    if v=="b":raise BackToMenu
    return default if not v else v in ("y","yes")
def pause(text):
    v=input(text+" (B=Back): ").strip()
    if v.lower()=="b":raise BackToMenu
def s16(v): return v-65536 if v>=32768 else v
def decode_value(raw,item):
    if raw is None:return None
    if item.get("enum") and str(raw) in item["enum"]:return item["enum"][str(raw)]
    if item.get("documented_choices") and str(raw) in item["documented_choices"]:return item["documented_choices"][str(raw)]
    number=s16(raw) if item.get("signed") else raw; factor=float(item.get("scale",1))
    return number*factor if item.get("scale_operation")=="multiply" else number/factor

def display_value(raw,item):
    if raw is None:return "N/A"
    choices=dict(item.get("documented_choices") or {});choices.update(item.get("enum") or {})
    meaning=choices.get(str(raw))
    if meaning is not None:return f"{raw} ({meaning})"
    decoded=decode_value(raw,item)
    return f"{decoded:g}" if isinstance(decoded,(int,float)) else str(decoded)
def encode_value(value,item):
    factor=float(item.get("scale",1))
    return int(round(value/factor if item.get("scale_operation")=="multiply" else value*factor))
def pname(n): return "".join(c.lower() if c.isalnum() else "_" for c in n).strip("_")
def save(p):
    PROFILE_DIR.mkdir(exist_ok=True); path=PROFILE_DIR/f"{pname(p['name'])}.json"; path.write_text(json.dumps(p,indent=2),encoding="utf-8"); print(f"Saved {path}")

def create_profile(protocol):
    print("\nCREATE A BLANK CONTROLLER PROFILE")
    name=ask("Profile name")
    if not name.strip(): print("A profile name is required.");return None
    path=PROFILE_DIR/f"{pname(name)}.json"
    if path.exists() and not yesno(f"Profile {name} already exists. Replace it",False):return None
    profile={"name":name.strip(),"protocol":protocol,"model":ask("Controller model (optional)",""),
             "firmware":ask("Firmware/version (optional)",""),"parameters":{},
             "created":time.strftime("%Y-%m-%d %H:%M:%S")}
    if protocol=="modbus_rtu":profile["connection"]={"port":"/dev/ttyUSB0","slave":1,"baudrate":9600,"parity":"N","stopbits":1,"timeout":.6}
    else:profile["connection"]={"port":"/dev/ttyACM0","unit":1,"baudrate":19200,"parity":"N","stopbits":2}
    save(profile);return profile

def seed():
    PROFILE_DIR.mkdir(exist_ok=True)
    if not (PROFILE_DIR/"xr77u.json").exists():
        ps={}
        for n,(a,sc,sg,d,u,g,cur,lo,hi) in XR_MAPPED.items(): ps[n]={"address":a,"register_type":"holding","scale":sc,"scale_operation":"divide","signed":sg,"description":d,"units":u,"group":g,"default_reference":cur,"minimum":lo,"maximum":hi,"access":"unknown","verification":"mapped_unverified"}
        for n,(d,u,g,cur,lo,hi) in XR_UNMAPPED.items(): ps[n]={"description":d,"units":u,"group":g,"default_reference":cur,"minimum":lo,"maximum":hi,"verification":"unmapped","high_risk":n=="tC"}
        for n,choices in XR_ENUMS.items():
            if n in ps: ps[n]["documented_choices"]=choices
        for n,(operation,factor,signed) in XR_FORMATS.items():
            if n in ps:ps[n].update({"documented_scale_operation":operation,"documented_scale":factor,"documented_signed":signed})
        for n in XR_READ_ONLY:
            if n in ps:ps[n]["read_only"]=True
        for n in XR_MAP_WITHOUT_CHANGE:
            if n in ps:ps[n]["map_without_change"]=True
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
                    source={"address":a,"register_type":"holding","scale":sc,"scale_operation":"divide","signed":sg,"description":d,"units":u,"group":g,"default_reference":cur,"minimum":lo,"maximum":hi}
                    if n not in items:items[n]={**source,"access":"read","verification":"mapped_unverified"};changed=True
                    else:
                        for key,value in source.items():
                            if key not in items[n] or items[n][key] is None:items[n][key]=value;changed=True
                for n,(d,u,g,cur,lo,hi) in XR_UNMAPPED.items():
                    source={"description":d,"units":u,"group":g,"default_reference":cur,"minimum":lo,"maximum":hi,"high_risk":n=="tC"}
                    if n not in items:items[n]={**source,"verification":"unmapped"};changed=True
                    else:
                        for key,value in source.items():
                            if key not in items[n] or items[n][key] is None:items[n][key]=value;changed=True
                for n,choices in XR_ENUMS.items():
                    if n in items and items[n].get("documented_choices")!=choices:
                        items[n]["documented_choices"]=choices;changed=True
                for n,(operation,factor,signed) in XR_FORMATS.items():
                    if n in items:
                        documented={"documented_scale_operation":operation,"documented_scale":factor,"documented_signed":signed}
                        for key,value in documented.items():
                            if items[n].get(key)!=value:items[n][key]=value;changed=True
                for n in XR_READ_ONLY:
                    if n in items and not items[n].get("read_only"):items[n]["read_only"]=True;changed=True
                for n in XR_MAP_WITHOUT_CHANGE:
                    if n in items and not items[n].get("map_without_change"):items[n]["map_without_change"]=True;changed=True
                for item in items.values():
                    if "current" in item and item.get("verification") not in ("user_verified","write_verified"):
                        item.pop("current",None);changed=True
                if changed:save(p)
            if protocol is None or p.get("protocol")==protocol: out.append(p)
        except Exception as e: print(f"Could not load {f.name}: {e}")
    return out
def choose_profile(protocol=None):
    ps=get_profiles(protocol)
    for i,p in enumerate(ps,1): print(f" {i}) {p['name']} ({p['protocol']})")
    print(" N) Create a new blank profile")
    print(" B) Back")
    choice=ask("Select profile",1)
    if choice.lower()=="n":return create_profile(protocol)
    try:return ps[int(choice)-1]
    except (ValueError,IndexError):return None

def configure(previous=None):
    print("\nCONNECTION SETUP (used until you choose Change connection)")
    if previous and yesno("Reuse current connection",True): return previous
    print(" 1) Modbus RTU\n 2) CAREL PJEZ TTL"); proto="modbus_rtu" if ask("Protocol",1)=="1" else "carel_pjez"; profile=choose_profile(proto)
    if not profile:return None
    d=profile.get("connection",{})
    if proto=="modbus_rtu": conn={"port":ask("Serial port",d.get("port","/dev/ttyUSB0")),"slave":int(ask("Slave address",d.get("slave",1))),"baudrate":int(ask("Baud",d.get("baudrate",9600))),"parity":ask("Parity N/E/O",d.get("parity","N")).upper(),"stopbits":int(ask("Stop bits",d.get("stopbits",1))),"timeout":float(ask("Timeout",d.get("timeout",.6)))}
    else: conn={"port":ask("Serial port",d.get("port","/dev/ttyACM0")),"unit":int(ask("Unit",d.get("unit",1))),"baudrate":19200,"parity":"N","stopbits":2}
    profile["connection"]=conn; save(profile);discovery=None
    latest=profile.get("working_snapshot_file") or profile.get("latest_discovery_file")
    if latest:
        try:
            candidate=(ROOT/latest).resolve()
            if ROOT.resolve() in candidate.parents:discovery=json.loads(candidate.read_text(encoding="utf-8"))
        except Exception as exc:print(f"Could not load previous discovery: {exc}")
    if discovery:print(f"Loaded saved discovery: {latest}")
    return {"protocol":proto,"profile":profile,"connection":conn,"discovery":discovery}

def inst(c):
    d=minimalmodbus.Instrument(c["port"],c["slave"],mode=minimalmodbus.MODE_RTU); d.serial.baudrate=c["baudrate"]; d.serial.bytesize=8
    d.serial.parity={"N":serial.PARITY_NONE,"E":serial.PARITY_EVEN,"O":serial.PARITY_ODD}[c["parity"]]; d.serial.stopbits=c["stopbits"]; d.serial.timeout=c["timeout"]; d.clear_buffers_before_each_transaction=True; return d
def readloc(d,kind,address):
    try:return d.read_bit(address,functioncode=KINDS[kind]) if kind in ("coil","discrete") else d.read_register(address,0,functioncode=KINDS[kind],signed=False)
    except Exception:return None
def scan_block(d,kind,start,count,found):
    try:
        values=d.read_bits(start,count,functioncode=KINDS[kind]) if kind in ("coil","discrete") else d.read_registers(start,count,functioncode=KINDS[kind])
        for offset,value in enumerate(values):found[start+offset]=int(value)
        return
    except Exception:pass
    if count==1:return
    left=count//2;scan_block(d,kind,start,left,found);scan_block(d,kind,start+left,count-left,found)
def scan(session,kinds=None,ask_range=True,quiet=False):
    if session["protocol"]!="modbus_rtu":print("Modbus discovery requires a Modbus connection.");return None
    if kinds is None:
        print(" 1) All read areas\n 2) Holding FC03\n 3) Input FC04\n 4) Coils FC01\n 5) Discrete inputs FC02")
        ch=ask("Scan selection",1); kinds={"1":list(KINDS),"2":["holding"],"3":["input"],"4":["coil"],"5":["discrete"]}.get(ch,list(KINDS))
    start=int(ask("Starting address",0)) if ask_range else 0; end=int(ask("Ending address",999)) if ask_range else 999; d=inst(session["connection"]); result={k:{} for k in kinds}
    print("Read-only discovery. No values will be written.")
    for kind in kinds:
        address=start;next_report=start+127
        while address<=end:
            count=min(32,end-address+1);before=len(result[kind]);scan_block(d,kind,address,count,result[kind])
            if not quiet:
                for found_address in sorted(a for a in result[kind] if address<=a<address+count):print(f" FOUND {kind} {found_address} raw={result[kind][found_address]}")
            address+=count
            if address>next_report:print(f" {kind}: through {min(address-1,end)}, readable={len(result[kind])}");next_report+=128
        print(f"{kind}: {len(result[kind])} readable")
    session["discovery"]={"profile":session["profile"]["name"],"captured":time.strftime("%Y-%m-%d %H:%M:%S"),"start":start,"end":end,"values":result}
    DISCOVERY_DIR.mkdir(exist_ok=True);stamp=time.strftime("%Y%m%d_%H%M%S");discovery_path=DISCOVERY_DIR/f"{pname(session['profile']['name'])}_{stamp}.json"
    discovery_path.write_text(json.dumps(session["discovery"],indent=2),encoding="utf-8")
    session["profile"]["latest_discovery_file"]=str(discovery_path.relative_to(ROOT));session["profile"].pop("working_snapshot_file",None);save(session["profile"])
    print(f"Discovery saved to {discovery_path}");return result

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
            raw=values.get(i.get("token"));val=display_value(raw,i);print(f"{n:<8}{val:>32} {i.get('units',''):<5} {i.get('token','')}")
        return
    d=inst(session["connection"])
    for n,i in p["parameters"].items():
        if "address" not in i:continue
        raw=readloc(d,i.get("register_type","holding"),i["address"]);val=display_value(raw,i)
        print(f"{n:<8}{val:>32} {i.get('units',''):<5} {i.get('register_type','holding')[0].upper()}:{i['address']} {i.get('verification','')}")

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
            pause("Change only this parameter, exit the keypad menu, then press ENTER")
            try:new=float(ask("New displayed value"))
            except ValueError:continue
            after=refresh(session,current_values); cs=[c for c in delta_candidates(current_values,after,current,new,item) if c[0]<1e-6]
            for x,c in enumerate(cs[:20],1):print(f" {x}) {c[1]} {c[2]} raw {c[3]}->{c[4]}, scale {c[5]}, signed={c[6]}")
            if not cs:print("No exact matching change found. Nothing was saved.");continue
            try:
                selected=ask("Select candidate, or R to reject","R")
                if selected.lower()=="r":print("Candidates rejected. Nothing was saved.");continue
                c=cs[int(selected)-1];scale=float(ask("Confirm/edit scale",c[5]))
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
    p=session["profile"]; mapped=[(n,i) for n,i in p["parameters"].items() if "address" in i and i.get("register_type")=="holding" and not i.get("read_only") and not i.get("map_without_change") and i.get("access")!="read_only"]
    if not mapped:print("No mapped writable holding-register candidates are available.");return
    print("CONTROLLED WRITE VERIFICATION")
    print("Only mapped holding registers are listed. Fixed/read-only values are excluded.")
    for x,(n,i) in enumerate(mapped,1):
        choices=dict(i.get("documented_choices") or {});choices.update(i.get("enum") or {})
        suffix=" | "+", ".join(f"{code}={meaning}" for code,meaning in choices.items()) if choices else ""
        print(f" {x}) {n} H:{i['address']}{suffix}")
    try:n,i=mapped[int(ask("Select parameter to write",1))-1]
    except (ValueError,IndexError):return
    choices=dict(i.get("documented_choices") or {});choices.update(i.get("enum") or {})
    if choices:
        print("Enter the numeric code shown beside the required meaning.")
        try:value=float(ask("New setting code"))
        except ValueError:print("A numeric setting code is required.");return
        if str(int(value)) not in choices and not yesno(f"Code {value:g} is not documented. Continue anyway",False):return
    else:
        try:value=float(ask(f"New displayed value in {i.get('units','controller units')}"))
        except ValueError:print("A numeric value is required.");return
    raw=encode_value(value,i);meaning=choices.get(str(int(value))) if choices else None
    description=f" ({meaning})" if meaning else ""
    print(f"Proposed write: {n}={value:g}{description}, holding {i['address']}, encoded raw={raw}.")
    print("The controller will be left at this value after a successful test.")
    if not yesno("Send this value to the controller now",True):
        print("Write cancelled; nothing was sent.");return
    d=inst(session["connection"])
    try:
        d.write_register(i["address"],raw,0,functioncode=6,signed=i.get("signed",False));time.sleep(.3);readback=readloc(d,"holding",i["address"]);print(f"Read-back: raw {readback}, displayed interpretation {display_value(readback,i)}")
    except Exception as e:print(f"Write failed: {e}");return
    expected=meaning or f"{value:g} {i.get('units','')}".strip()
    if yesno(f"Does the physical controller now show {expected}"):i["verification"]="write_verified";i["access"]="read_write";i["current"]=value;save(p)

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
                pause("Change only this parameter, exit its menu, then press ENTER")
                try:new=float(ask("New displayed value"))
                except ValueError:d.close();return
                after=d.dump();cs=[c for c in delta_candidates({"token":before},{"token":after},old,new,item) if c[0]<1e-6]
                for x,c in enumerate(cs[:20],1):print(f" {x}) token {c[2]} raw {c[3]}->{c[4]}, scale {c[5]}, signed={c[6]}")
                if cs:
                    try:
                        selected=ask("Select candidate, or R to reject","R")
                        if selected.lower()=="r":d.close();continue
                        c=cs[int(selected)-1];scale=float(ask("Confirm/edit scale",c[5]))
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
    if not yesno("Send this value to the controller now",True):
        print("Write cancelled; nothing was sent.");return
    d=PJEZ(session["connection"]["port"],session["connection"]["unit"]);ok=d.write_token(i["token"],raw,password);d.close();print("Write ACK received." if ok else "Write failed or no ACK.")

def ensure_discovery(session):
    if session.get("discovery"):return session["discovery"]["values"]
    print("No discovery is loaded. Run a read-only scan now.")
    return scan(session)

def current_snapshot(session,template):
    return refresh(session,template)

def persist_working_snapshot(session,working):
    DISCOVERY_DIR.mkdir(exist_ok=True);path=DISCOVERY_DIR/f"{pname(session['profile']['name'])}_working.json"
    payload={"profile":session["profile"]["name"],"captured":time.strftime("%Y-%m-%d %H:%M:%S"),"working":True,"values":working}
    path.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    session["discovery"]=payload;session["profile"]["working_snapshot_file"]=str(path.relative_to(ROOT));save(session["profile"])

def unassigned_snapshot(session):
    values=ensure_discovery(session)
    if not values:return None
    assigned={(item.get("register_type","holding"),int(item["address"])) for item in session["profile"].get("parameters",{}).values() if "address" in item}
    working={kind:{int(address):raw for address,raw in locations.items() if (kind,int(address)) not in assigned} for kind,locations in values.items()}
    print(f"Snapshot: {sum(len(x) for x in values.values())} readable, {len(assigned)} assigned, {sum(len(x) for x in working.values())} available.")
    return working

def changed_locations(before,after,boolean_only=False):
    changes=[]
    for kind,locations in before.items():
        for address,old_raw in locations.items():
            new_raw=after.get(kind,{}).get(address)
            if new_raw is None or new_raw==old_raw:continue
            if boolean_only and (old_raw not in (0,1) or new_raw not in (0,1)):continue
            changes.append((kind,address,old_raw,new_raw))
    return changes

def choose_changed_location(changes,name):
    if not changes:return None
    if len(changes)==1:
        c=changes[0]
        print(f"Only one unassigned location changed: {c[0]} {c[1]}, raw {c[2]} -> {c[3]}")
        print(f"This is strong evidence that {c[0]} {c[1]} is the location for {name}.")
        return c if yesno(f"Assign {c[0]} {c[1]} to {name} and continue",True) else None
    print(f"{len(changes)} unassigned locations changed while {name} was changed.")
    print("Select the location most likely to belong to this parameter. Choose R if the test was not clean.")
    for index,c in enumerate(changes,1):print(f" {index}) {c[0]} {c[1]} raw {c[2]} -> {c[3]}")
    choice=ask(f"Location for {name}; enter its number or R to reject","R")
    if choice.lower()=="r":return None
    try:return changes[int(choice)-1]
    except (ValueError,IndexError):print("Invalid selection.");return None

def map_fixed_parameter(session,name,item,working):
    print(f"\nSelected: {name} - {item.get('description','')}")
    if item.get("read_only"):print("This is a fixed/read-only value, so the tool will not ask you to change it.")
    else:print("Changing this parameter could reconfigure the controller, so it will be mapped without changing it.")
    try:shown=float(ask("Enter the exact value currently shown on the controller"))
    except ValueError:print("A numeric displayed value is required. Nothing saved.");return False
    operation=item.get("documented_scale_operation","divide");factor=float(item.get("documented_scale",1));signed=item.get("documented_signed",False)
    matches=[]
    for kind,locations in working.items():
        for address,raw in locations.items():
            number=s16(raw) if signed else raw;decoded=number*factor if operation=="multiply" else number/factor
            if abs(decoded-shown)<1e-7:matches.append((kind,address,raw,decoded))
    if not matches:
        print(f"No unassigned location decodes to {shown:g} using the documented format ({operation} by {factor}, signed={signed}).")
        print("Nothing was saved. Run a fresh discovery if the snapshot may be out of date.");return False
    if len(matches)==1:
        kind,address,raw,_=matches[0]
        print(f"One matching unassigned location: {kind} {address}, raw {raw} -> {shown:g} {item.get('units','')}")
        if not yesno(f"Assign {kind} {address} to {name}",True):return False
    else:
        print(f"{len(matches)} unassigned locations currently decode to {shown:g}. A fixed value cannot distinguish them automatically.")
        for index,(k,a,r,d) in enumerate(matches,1):print(f" {index}) {k} {a}, raw {r} -> {d:g} {item.get('units','')}")
        choice=ask(f"Location for {name}; enter its number or R to reject","R")
        if choice.lower()=="r":return False
        try:kind,address,raw,_=matches[int(choice)-1]
        except (ValueError,IndexError):print("Invalid selection.");return False
    access="read_only" if item.get("read_only") else "read"
    verification="value_matched_read_only" if item.get("read_only") else "value_matched_no_change"
    item.update({"register_type":kind,"address":address,"scale":factor,"scale_operation":operation,"signed":signed,"access":access,"verification":verification,"last_user_verified":shown})
    session["profile"].setdefault("parameters",{})[name]=item;working.get(kind,{}).pop(address,None);persist_working_snapshot(session,working)
    print(f"Saved no-change mapping: {name} -> {kind} {address}.")
    print(f"That location has been removed from the working snapshot. Unassigned locations remaining: {sum(len(x) for x in working.values())}")
    return True

def map_snapshot_parameter(session,name,item,working,mode=None):
    if item.get("high_risk"):
        print("WARNING: This setting changes the controller application map.")
        if not yesno("Include this high-risk parameter",False):return False
    documented=item.get("documented_choices",{})
    print(f"\nSelected: {name} - {item.get('description','')}")
    if documented:
        print("Documented settings:")
        for code,meaning in documented.items():print(f" {code}) {meaning}")
    print(f"The saved baseline contains {sum(len(x) for x in working.values())} unassigned readable locations.")
    print("Nothing is being written by this tool. It will compare the baseline with the controller after your keypad change.")
    pause(f"On the controller, change only {name} to another safe setting, save/exit its menu, then press ENTER here")
    after=refresh(session,working);changes=changed_locations(working,after,mode=="status")
    selected=choose_changed_location(changes,name)
    if not selected:
        print("No mapping was saved. The unassigned snapshot has not been reduced.");return False
    kind,address,old_raw,new_raw=selected
    if documented or mode=="enum":
        if documented:
            enum=dict(documented);new_label=enum.get(str(new_raw),f"raw {new_raw}")
            print(f"The manual/profile identifies raw {new_raw} as: {new_label}")
            print("No scale or displayed-value entry is needed for this documented choice.")
        else:
            print(f"The changed register now contains raw {new_raw}, but this undocumented profile does not yet know its meaning.")
            new_label=ask(f"Enter the exact text now shown on the controller for raw {new_raw}");enum={str(new_raw):new_label}
        item.update({"register_type":kind,"address":address,"scale":1,"scale_operation":"divide","signed":False,"enum":enum,"access":"read","verification":"change_verified"})
    elif mode=="status":
        print("Tell the profile whether the physical condition is now ON or OFF so both raw states can be labelled correctly.")
        state=ask("Physical state now: ON or OFF","ON").upper();is_on=state=="ON"
        item.update({"register_type":kind,"address":address,"scale":1,"scale_operation":"divide","signed":False,"units":"bool","access":"read","verification":"change_verified","on_value":new_raw if is_on else old_raw,"off_value":old_raw if is_on else new_raw})
    else:
        if "documented_scale" in item:
            operation=item.get("documented_scale_operation","divide");factor=item["documented_scale"];signed=item.get("documented_signed",False)
            preview=s16(new_raw) if signed else new_raw;preview=preview*factor if operation=="multiply" else preview/factor
            print(f"The manual/profile already defines the format: {operation} by {factor}, signed={signed}.")
            print(f"Raw {new_raw} therefore decodes to {preview:g} {item.get('units','')}; no value entry is required.")
        else:
            print("This parameter has no documented scale. The displayed value is needed once to determine how the raw register is encoded.")
            try:new_display=float(ask("Enter the exact new numeric value shown on the controller"))
            except ValueError:print("A numeric displayed value is required. Nothing saved.");return False
            interpretations=quick_candidates({kind:{address:new_raw}},new_display,item)
            if len(interpretations)==1:
                _,_,_,_,factor,signed,operation=interpretations[0]
                print(f"Interpretation: {operation} by {factor}, signed={signed}")
            else:
                if interpretations:
                    for index,c in enumerate(interpretations,1):print(f" {index}) {c[6]} by {c[4]}, signed={c[5]}")
                    choice=ask("Select interpretation, or R to reject","R")
                    if choice.lower()=="r":return False
                    try:_,_,_,_,factor,signed,operation=interpretations[int(choice)-1]
                    except (ValueError,IndexError):return False
                else:
                    operation=ask("Scale operation divide/multiply","divide").lower();factor=float(ask("Scale factor",1));signed=yesno("Signed 16-bit",item.get("minimum",0)<0 if isinstance(item.get("minimum"),(int,float)) else False)
        item.update({"register_type":kind,"address":address,"scale":factor,"scale_operation":operation,"signed":signed,"access":"read","verification":"change_verified"})
    session["profile"].setdefault("parameters",{})[name]=item
    working.clear();working.update(after);working.get(kind,{}).pop(address,None)
    persist_working_snapshot(session,working)
    print(f"Saved mapping: {name} -> {kind} {address}.")
    print(f"That location has been removed from the working snapshot. Unassigned locations remaining: {sum(len(x) for x in working.values())}")
    return True

def quick_candidates(values,target,item):
    candidates=[]
    prefer_signed=isinstance(item.get("minimum"),(int,float)) and item["minimum"]<0
    for kind,locations in values.items():
        for address,raw in locations.items():
            signed_options=(False,) if raw<0x8000 else (prefer_signed,not prefer_signed)
            for signed in signed_options:
                number=s16(raw) if signed else raw
                for factor in (1,10,100,1000):
                    operations=("divide",) if factor==1 else ("divide","multiply")
                    for operation in operations:
                        decoded=number*factor if operation=="multiply" else number/factor
                        if abs(decoded-target)<1e-7:
                            penalty=(0 if signed==prefer_signed else 2)+(0 if operation=="divide" else 1)
                            candidates.append((penalty,kind,address,raw,factor,signed,operation))
    unique={(c[1],c[2],c[4],c[5],c[6]):c for c in candidates}
    return sorted(unique.values())

def exact_changes(before,after,old,new,item):
    candidates=[]
    for kind,locations in before.items():
        for address,braw in locations.items():
            if address not in after.get(kind,{}) or after[kind][address]==braw:continue
            araw=after[kind][address]
            signed_options=(False,) if braw<0x8000 and araw<0x8000 else (False,True)
            for signed in signed_options:
                b=s16(braw) if signed else braw;a=s16(araw) if signed else araw
                for factor in (1,10,100,1000):
                    operations=("divide",) if factor==1 else ("divide","multiply")
                    for operation in operations:
                        bd=b*factor if operation=="multiply" else b/factor
                        ad=a*factor if operation=="multiply" else a/factor
                        if abs(bd-old)<1e-7 and abs(ad-new)<1e-7:
                            candidates.append((kind,address,braw,araw,factor,signed,operation))
    return candidates

def save_numeric_candidate(session,name,item,candidate,status):
    kind,address,braw,araw,factor,signed,operation=candidate
    print(f"{kind} {address}: raw {braw}" + (f" -> {araw}" if araw is not None else ""))
    print(f"Interpretation: {operation} by {factor}; signed={signed}")
    operation=ask("Scale operation divide/multiply",operation).lower()
    factor=float(ask("Confirm/edit scale",factor))
    item.update({"register_type":kind,"address":address,"scale":factor,"scale_operation":operation,
                 "signed":signed,"access":"read","verification":status})
    session["profile"].setdefault("parameters",{})[name]=item;save(session["profile"])

def map_enum_point(session,name,item,values):
    if item.get("high_risk"):
        print("WARNING: This setting changes the controller application map.")
        if not yesno("Include this high-risk parameter",False):return False
    print(f"\n{name} is the controller parameter label: {item.get('description','')}")
    choices=item.get("documented_choices",{})
    if choices:
        print("Documented settings:")
        for code,meaning in choices.items(): print(f"  {code}) {meaning}")
        print("The controller may show a short label (for example dEF) instead of the number.")
    original=ask("Current setting code or displayed text",item.get("default_reference",""))
    original_label=choices.get(str(original),str(original))
    if choices and str(original) in choices:print(f"Current setting: {original} = {original_label}")
    print("One safe setting change lets the tool identify the register.")
    before=current_snapshot(session,values)
    pause(f"Change {name} to a different safe option, exit the controller menu, then press ENTER")
    changed_text=ask("New setting code or displayed text")
    changed_label=choices.get(str(changed_text),str(changed_text))
    if choices and str(changed_text) in choices:print(f"New setting: {changed_text} = {changed_label}")
    after=current_snapshot(session,before);changes=[]
    for kind,locations in before.items():
        for address,braw in locations.items():
            araw=after.get(kind,{}).get(address)
            if araw is not None and araw!=braw:changes.append((kind,address,braw,araw))
    if not changes:print("No changed locations found. Nothing was saved.");return False
    if len(changes)==1:
        kind,address,old_raw,new_raw=changes[0]
        print(f"One changed location found: {kind} {address}, raw {old_raw} -> {new_raw}")
        if not yesno("Save this mapping",True):return False
    else:
        print("\nChanged locations:")
        for x,c in enumerate(changes,1):print(f" {x}) {c[0]} {c[1]} raw {c[2]} -> {c[3]}")
        selected=ask("Select candidate, or R to reject","R")
        if selected.lower()=="r":return False
        try:kind,address,old_raw,new_raw=changes[int(selected)-1]
        except (ValueError,IndexError):print("Invalid selection.");return False
    item.update({"register_type":kind,"address":address,"scale":1,"scale_operation":"divide","signed":False,
                 "enum":{str(old_raw):original_label,str(new_raw):changed_label},"access":"read",
                 "verification":"change_verified"})
    session["profile"].setdefault("parameters",{})[name]=item;save(session["profile"])
    print(f"Saved {name}: {kind} {address}; raw {old_raw}={original_label}, raw {new_raw}={changed_label}")
    print(f"Controller was left at {changed_label}; restore it manually only if required.")
    return True

def map_numeric_point(session,name,item,values):
    if item.get("high_risk"):
        print("WARNING: This setting changes the controller application map.")
        if not yesno("Include this high-risk parameter",False):return False
    reference=item.get("default_reference")
    if isinstance(reference,str) and reference:
        try:float(reference)
        except ValueError:
            print("Detected a text/enumerated parameter. Switching to enum mapping.")
            return map_enum_point(session,name,item,values)
    try:old=float(ask("Controller current value",reference))
    except (ValueError,TypeError):
        print("Detected a text/enumerated parameter. Switching to enum mapping.")
        return map_enum_point(session,name,item,values)
    before=current_snapshot(session,values);matches=quick_candidates(before,old,item)
    if len(matches)==1:
        _,kind,address,raw,factor,signed,operation=matches[0]
        print(f"One exact match: {kind} {address}, raw {raw}, {operation} {factor}, signed={signed}")
        if yesno("Save as probable mapping",True):
            save_numeric_candidate(session,name,item,(kind,address,raw,None,factor,signed,operation),"value_matched");return True
        return False
    print(f"{len(matches)} exact interpretations found. A change is needed to distinguish them.")
    if not yesno("Change this value now",True):return False
    pause("Change only this value, exit the controller menu, then press ENTER")
    try:new=float(ask("New displayed value"))
    except ValueError:return False
    after=current_snapshot(session,before);matches=exact_changes(before,after,old,new,item)
    if not matches:print("No exact matching change found. Nothing was saved.");return False
    for x,c in enumerate(matches,1):print(f" {x}) {c[0]} {c[1]} raw {c[2]}->{c[3]}, {c[6]} {c[4]}, signed={c[5]}")
    selected=ask("Select candidate, or R to reject","R")
    if selected.lower()=="r":return False
    try:candidate=matches[int(selected)-1]
    except (ValueError,IndexError):print("Invalid selection.");return False
    if yesno(f"Save {name}",True):save_numeric_candidate(session,name,item,candidate,"change_verified");return True
    return False

def map_status(session,values):
    name=ask("Status name");description=ask("Description",name)
    print("Use a condition you can safely turn ON and OFF. Unknown bits will only be read.")
    initial=ask("Current physical state OFF/ON","OFF").upper()
    before=current_snapshot(session,values)
    pause(f"Change {name} from {initial} to {'ON' if initial=='OFF' else 'OFF'}, then press ENTER")
    after=current_snapshot(session,before);changes=[]
    for kind in ("coil","discrete","holding","input"):
        for address,b in before.get(kind,{}).items():
            a=after.get(kind,{}).get(address)
            if a is not None and a!=b and b in (0,1) and a in (0,1):changes.append((kind,address,b,a))
    if not changes:print("No Boolean changes found.");return False
    if len(changes)==1:
        kind,address,b,a=changes[0];print(f"One changed location found: {kind} {address}, {b} -> {a}")
        if not yesno("Save this mapping",True):return False
    else:
        for x,c in enumerate(changes,1):print(f" {x}) {c[0]} {c[1]}: {c[2]} -> {c[3]}")
        selected=ask("Select candidate, or R to reject","R")
        if selected.lower()=="r":return False
        try:kind,address,b,a=changes[int(selected)-1]
        except (ValueError,IndexError):return False
    item={"register_type":kind,"address":address,"scale":1,"scale_operation":"divide","signed":False,
          "description":description,"units":"bool","access":"read","verification":"change_verified",
          "on_value":a if initial=="OFF" else b,"off_value":b if initial=="OFF" else a}
    session["profile"].setdefault("parameters",{})[name]=item;save(session["profile"]);return True

def map_new_enum(session,values):
    name=ask("Parameter name");description=ask("Description",name)
    item={"description":description,"units":"","verification":"unmapped"}
    return map_enum_point(session,name,item,values)

def manual_mapping(session):
    name=ask("Name");description=ask("Description",name)
    if session["protocol"]=="carel_pjez":
        token=ask("CAREL token");item={"token":token,"description":description,"units":ask("Units",""),"scale":float(ask("Scale",1)),
          "scale_operation":ask("Scale operation divide/multiply","divide"),"signed":yesno("Signed 16-bit",False),"access":"read","verification":"mapped_unverified"}
    else:
        print("Types: holding, input, coil, discrete");kind=ask("Location type","holding").lower();address=int(ask("Address"))
        item={"register_type":kind,"address":address,"description":description,"units":ask("Units",""),
          "scale":float(ask("Scale",1)),"scale_operation":ask("Scale operation divide/multiply","divide"),
          "signed":yesno("Signed 16-bit",False),"access":"read","verification":"mapped_unverified"}
    session["profile"].setdefault("parameters",{})[name]=item;save(session["profile"])

def mapping_menu(session):
    if session["protocol"]=="carel_pjez":
        print("CAREL mappings use two F1 table dumps and can be repeated in one session.")
        map_carel_session(session);return
    mapped=[];working=unassigned_snapshot(session)
    if not working:return
    while True:
        print("\nMAP PARAMETERS AND STATUS")
        print("1) Map existing profile parameter\n2) Add and map a new numeric value\n3) Add and map a Boolean/status")
        print("4) Add and map a text/enumerated value\n5) Add and map a fixed/read-only value")
        print("6) Enter a known location manually\n7) Review mappings from this session\nB) Back")
        choice=ask("Select",1)
        if choice=="7":print("\n".join(mapped) if mapped else "Nothing mapped in this session.");continue
        if choice=="6":manual_mapping(session);continue
        if choice=="1":
            available=[(n,i) for n,i in session["profile"]["parameters"].items() if "address" not in i and "token" not in i]
            for x,(n,i) in enumerate(available,1):
                risk=" [HIGH RISK]" if i.get("high_risk") else ""
                fixed=" [FIXED/READ-ONLY]" if i.get("read_only") else " [MAP WITHOUT CHANGE]" if i.get("map_without_change") else ""
                print(f" {x}) {n:<5} {i.get('description','')}{risk}{fixed}")
            try:name,item=available[int(ask("Select parameter",1))-1]
            except (ValueError,IndexError):continue
            if item.get("read_only") or item.get("map_without_change"):
                if map_fixed_parameter(session,name,item,working):mapped.append(name)
            else:
                mode="enum" if item.get("documented_choices") or isinstance(item.get("default_reference"),str) else "numeric"
                if map_snapshot_parameter(session,name,item,working,mode):mapped.append(name)
        elif choice=="2":
            name=ask("Name");item={"description":ask("Description",name),"units":ask("Units",""),
                "minimum":None,"maximum":None,"verification":"unmapped"}
            if map_snapshot_parameter(session,name,item,working,"numeric"):mapped.append(name)
        elif choice=="3":
            name=ask("Status name");item={"description":ask("Description",name),"verification":"unmapped"}
            if map_snapshot_parameter(session,name,item,working,"status"):mapped.append(name)
        elif choice=="4":
            name=ask("Parameter name");item={"description":ask("Description",name),"verification":"unmapped"}
            if map_snapshot_parameter(session,name,item,working,"enum"):mapped.append(name)
        elif choice=="5":
            name=ask("Fixed/read-only value name");item={"description":ask("Description",name),"units":ask("Units",""),"verification":"unmapped","read_only":True}
            operation=ask("Known scale operation divide/multiply","divide").lower();factor=float(ask("Known scale factor",1));signed=yesno("Signed 16-bit",False)
            item.update({"documented_scale_operation":operation,"documented_scale":factor,"documented_signed":signed})
            if map_fixed_parameter(session,name,item,working):mapped.append(name)
        else:print("Invalid selection.")

def read_current(session,item,carel_values=None):
    if session["protocol"]=="carel_pjez":
        return carel_values.get(item.get("token")) if carel_values else None
    return readloc(inst(session["connection"]),item.get("register_type","holding"),item["address"])

def verify_menu(session):
    mapped=[(n,i) for n,i in session["profile"]["parameters"].items() if "address" in i or "token" in i]
    print("1) Verify one mapped value with user\n2) Verify all mapped values with user\n3) Review statuses\nB) Back")
    choice=ask("Select",1)
    if choice=="3":
        for n,i in mapped:print(f"{n:<10}{i.get('verification','unknown')}")
        return
    if choice=="1":
        for x,(n,i) in enumerate(mapped,1):print(f" {x}) {n}")
        try:mapped=[mapped[int(ask("Select",1))-1]]
        except (ValueError,IndexError):return
    carel_values=None
    if session["protocol"]=="carel_pjez":
        d=PJEZ(session["connection"]["port"],session["connection"]["unit"]);carel_values=d.dump();d.close()
    counts={"verified":0,"not matched":0,"skipped":0,"no response":0}
    for index,(name,item) in enumerate(mapped,1):
        raw=read_current(session,item,carel_values)
        if raw is None:print(f"{name}: NO RESPONSE");counts["no response"]+=1;continue
        decoded=decode_value(raw,item);loc=item.get("token") or f"{item.get('register_type','holding')}:{item.get('address')}"
        print(f"\nParameter {index} of {len(mapped)}: {name}\nLocation: {loc}\nRaw: {raw}\nDecoded: {decoded} {item.get('units','')}")
        if isinstance(decoded,str) and item.get("enum"):
            answer=ask("Does the controller show this text? Y/N/S","S").lower()
        else:
            answer=ask("Does the controller show this value? Y/N/E/S","S").lower()
        if answer=="y":item["verification"]="user_verified";item["last_user_verified"]=decoded;counts["verified"]+=1
        elif answer=="e":
            shown=ask("Enter exact text/value shown")
            try:
                numeric=float(shown)
                if isinstance(decoded,(int,float)) and abs(decoded-numeric)<1e-7:item["verification"]="user_verified";item["last_user_verified"]=numeric;counts["verified"]+=1
                else:
                    print(f"Values differ: decoded {decoded}, controller {numeric}.")
                    if yesno("Edit scaling now",True):
                        signed=yesno("Interpret raw value as signed 16-bit",item.get("signed",False));base=s16(raw) if signed else raw
                        suggested_operation="multiply" if numeric and abs(numeric)>abs(base) else "divide"
                        suggested_factor=abs(numeric/base) if suggested_operation=="multiply" and base else abs(base/numeric) if numeric else 1
                        operation=ask("Scale operation divide/multiply",suggested_operation).lower();factor=float(ask("Scale factor",f"{suggested_factor:g}"))
                        item.update({"signed":signed,"scale_operation":operation,"scale":factor});revised=decode_value(raw,item)
                        print(f"Revised decoded value: {revised}")
                        if isinstance(revised,(int,float)) and abs(revised-numeric)<1e-7:item["verification"]="user_verified";item["last_user_verified"]=numeric;counts["verified"]+=1
                        else:counts["not matched"]+=1
                    else:counts["not matched"]+=1
            except ValueError:
                item.setdefault("enum",{})[str(raw)]=shown;item["verification"]="user_verified";item["last_user_verified"]=shown;counts["verified"]+=1
        elif answer=="n":counts["not matched"]+=1
        else:counts["skipped"]+=1
        save(session["profile"])
    print("\nVERIFICATION SUMMARY")
    for key,value in counts.items():print(f"{key.title():<14}{value}")

def export_profile(session):
    profile=session["profile"];save(profile);stamp=time.strftime("%Y%m%d_%H%M%S")
    folder=EXPORT_DIR/f"{pname(profile['name'])}_{stamp}";folder.mkdir(parents=True,exist_ok=True)
    json_path=folder/"profile.json";json_path.write_text(json.dumps(profile,indent=2),encoding="utf-8")
    columns=["name","description","register_type","address","token","units","scale_operation","scale","signed","access","verification","minimum","maximum","enum","documented_choices"]
    csv_path=folder/"map.csv"
    with csv_path.open("w",newline="",encoding="utf-8-sig") as handle:
        writer=csv.DictWriter(handle,fieldnames=columns);writer.writeheader()
        for name,item in profile.get("parameters",{}).items():
            row={key:item.get(key,"") for key in columns};row["name"]=name
            row["enum"]=json.dumps(item.get("enum",{}),ensure_ascii=False);row["documented_choices"]=json.dumps(item.get("documented_choices",{}),ensure_ascii=False)
            writer.writerow(row)
    report=[f"# {profile['name']} controller map","",f"Protocol: {profile.get('protocol','')}",f"Model: {profile.get('model','')}",f"Firmware: {profile.get('firmware','')}",f"Exported: {time.strftime('%Y-%m-%d %H:%M:%S')}","","| Name | Description | Location | Decoding | Verification |","|---|---|---|---|---|"]
    for name,item in profile.get("parameters",{}).items():
        location=item.get("token") or (f"{item.get('register_type','')} {item['address']}" if "address" in item else "unmapped")
        decoding="enum" if item.get("enum") or item.get("documented_choices") else f"{item.get('scale_operation','divide')} {item.get('scale',1)}, signed={item.get('signed',False)}"
        clean=lambda value:str(value).replace("|","/").replace("\n"," ")
        report.append(f"| {clean(name)} | {clean(item.get('description',''))} | {clean(location)} | {clean(decoding)} | {clean(item.get('verification',''))} |")
    md_path=folder/"map.md";md_path.write_text("\n".join(report)+"\n",encoding="utf-8")
    latest=profile.get("latest_discovery_file")
    if latest:
        source=ROOT/latest
        if source.exists():shutil.copy2(source,folder/"latest_discovery.json")
    working_file=profile.get("working_snapshot_file")
    if working_file:
        source=ROOT/working_file
        if source.exists():shutil.copy2(source,folder/"unassigned_working_snapshot.json")
    print("\nEXPORT COMPLETE")
    print(f"JSON profile: {json_path}\nCSV map:      {csv_path}\nReadable map: {md_path}")

def raw_monitor(session):
    c=session["connection"];print("Read-only byte monitor. Another Modbus master must create traffic. Ctrl+C stops.")
    try:
        d=serial.Serial(c["port"],c["baudrate"],bytesize=8,parity=c["parity"],stopbits=c["stopbits"],timeout=.5)
        while True:
            data=d.read(d.in_waiting or 1)
            if data:print(f"[{time.strftime('%H:%M:%S')}] {data.hex(' ')}")
    except KeyboardInterrupt:print("Monitor stopped.")
    finally:
        if "d" in locals() and d.is_open:d.close()

def ports():
    for p in serial.tools.list_ports.comports():print(f"{p.device}: {p.description} [{p.hwid}]")
def active(s):
    c=s["connection"];return f"{c['port']} | {s['protocol']} | "+(f"address {c['slave']} | {c['baudrate']} 8{c['parity']}{c['stopbits']}" if s["protocol"]=="modbus_rtu" else f"unit {c['unit']} | 19200 8N2")
def main():
    seed()
    try:session=configure()
    except BackToMenu:return 0
    if not session:return 1
    while True:
        print("\n"+"="*64+f"\nACTIVE: {active(session)}\nPROFILE: {session['profile']['name']}\n"+"="*64)
        print("1) Test connection\n2) Read mapped values\n3) Discover readable locations\n4) Map parameters")
        print("5) Verify mapped parameters\n6) Controlled write verification\n7) View profile\n8) Change connection\n9) Diagnostics\n10) Export profile/map\n0) Exit")
        try:
            ch=ask("Select",1)
            if ch=="1":test(session)
            elif ch=="2":read_profile(session)
            elif ch=="3":scan(session)
            elif ch=="4":mapping_menu(session)
            elif ch=="5":verify_menu(session)
            elif ch=="6":write_modbus(session) if session["protocol"]=="modbus_rtu" else write_carel(session)
            elif ch=="7":print(json.dumps(session["profile"],indent=2))
            elif ch=="8":session=configure(session) or session
            elif ch=="9":
                print("1) List serial devices\n2) Raw byte monitor\nB) Back");diag=ask("Select",1)
                if diag=="1":ports()
                elif diag=="2":raw_monitor(session)
            elif ch=="10":export_profile(session)
            elif ch=="0":return 0
        except BackToMenu:
            print("Returning to main menu.")
if __name__=="__main__":
    try:raise SystemExit(main())
    except KeyboardInterrupt:print("\nStopped safely.");raise SystemExit(130)
