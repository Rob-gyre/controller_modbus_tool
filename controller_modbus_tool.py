#!/usr/bin/env python3
"""Controller Serial Mapping Tool v4.0 - Modbus RTU and CAREL PJEZ."""
import json
import sys
import time
from pathlib import Path

try:
    import serial
    import serial.tools.list_ports
    import minimalmodbus
except ImportError as exc:
    print(f"Missing dependency: {exc}. Run: pip install -r requirements.txt")
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent
PROFILES = ROOT / "profiles"
STX, ETX, ENQ, ACK, NUL = 0x02, 0x03, 0x05, 0x06, 0x00

# Addresses supplied in Universal_R_Map.xlsx for XR77U / 2C310000, firmware 5.9.
XR77U = {
    "PbC": (769,1,False,"Kind of probe",""), "Hy": (770,10,False,"Differential","C"),
    "LS": (771,10,True,"Minimum set point","C"), "US": (772,10,True,"Maximum set point","C"),
    "ot": (773,10,True,"Thermostat probe calibration","C"), "AC": (774,1,False,"Anti-short cycle delay","min"),
    "ALC": (776,1,False,"Temperature alarm configuration",""), "ALU": (777,10,True,"High temperature alarm","C"),
    "ALL": (778,10,True,"Low temperature alarm","C"), "ALd": (780,1,False,"Temperature alarm delay","min"),
    "dAo": (781,1,False,"Alarm delay at start-up","min"), "odS": (782,1,False,"Output delay at start-up","min"),
    "CCt": (783,1,False,"Continuous cycle duration","min"), "CCS": (784,10,True,"Continuous cycle set point","C"),
    "dAF": (785,1,False,"Defrost delay after fast freezing","min"), "idF": (786,1,False,"Defrost interval","hour"),
    "dSd": (787,1,False,"Start defrost delay","min"), "MdF": (789,1,False,"Maximum first defrost length","min"),
    "dtE": (790,10,True,"First evaporator defrost end temperature","C"), "MdS": (792,1,False,"Maximum second defrost length","min"),
    "FSt": (800,10,True,"Fan stop temperature","C"), "oE": (809,10,True,"Evaporator probe calibration","C"),
    "CF": (813,1,False,"Temperature unit",""), "SEt": (853,10,True,"Set point","C"),
}

CAREL = {
    "Pb1":("S11",10,True,"Probe 1 / room temperature","C"), "Pb2":("S21",10,True,"Probe 2 / evaporator","C"),
    "Pb3":("S31",10,True,"Probe 3 / auxiliary","C"), "St":("S81",10,True,"Setpoint","C"),
    "rd":("S91",10,True,"Differential","C"), "LSE":("S:1",10,True,"Minimum setpoint","C"),
    "HSE":("S;1",10,True,"Maximum setpoint","C"), "/C1":("S51",10,True,"Probe 1 calibration","C"),
    "/C2":("S61",10,True,"Probe 2 calibration","C"), "F1":("SC1",10,True,"Fan stop temperature","C"),
    "AL":("S?1",10,True,"Low alarm","C"), "AH":("S@1",10,True,"High alarm","C"),
    "dt":("S=1",10,True,"Defrost end temperature","C"), "c1":("U<1",1,False,"Minimum between starts","min"),
    "c2":("U=1",1,False,"Minimum OFF time","min"), "c3":("U>1",1,False,"Minimum ON time","min"),
    "d0":("UB1",1,False,"Defrost type",""), "d1":("UC1",1,False,"Defrost interval","hour"),
    "dP":("UD1",1,False,"Maximum defrost time","min"), "d5":("UE1",1,False,"Defrost delay","min"),
    "dd":("UF1",1,False,"Drain time","min"), "d8":("UG1",1,False,"Defrost priority",""),
    "Fd":("UL1",1,False,"Fan delay after dripping","min"), "d4":("BL1",1,False,"Defrost at power-on","bool"),
    "d6":("BM1",1,False,"Display during defrost","bool"), "d9":("BN1",1,False,"Defrost priority over protection","bool"),
    "dC":("BO1",1,False,"Defrost time base","bool"), "F0":("BQ1",1,False,"Evaporator fan control","bool"),
    "F2":("BR1",1,False,"Fans cycle with compressor","bool"), "F3":("BS1",1,False,"Fans in defrost","bool"),
}
CAREL_STATUS = {"B21":"Compressor ON","B31":"Defrost active","B41":"Fan ON","B71":"Alarm active","B:1":"Probe fault"}

def ask(text, default=None):
    value = input(f"{text}" + (f" [{default}]" if default is not None else "") + ": ").strip()
    return value or (str(default) if default is not None else "")

def yesno(text, default=False):
    value = input(f"{text} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    return default if not value else value in ("y","yes")

def s16(value): return value - 65536 if value >= 32768 else value

def safe_name(name): return "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")

def save_profile(profile):
    PROFILES.mkdir(exist_ok=True)
    path = PROFILES / f"{safe_name(profile['name'])}.json"
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    print(f"Saved {path}")

def seed_profiles():
    PROFILES.mkdir(exist_ok=True)
    xr = PROFILES / "xr77u.json"
    if not xr.exists():
        params = {n:{"register_type":"holding","address":a,"scale":sc,"signed":sg,"description":d,"units":u,
                     "access":"unknown","verification":"mapped_unverified"} for n,(a,sc,sg,d,u) in XR77U.items()}
        save_profile({"name":"XR77U","protocol":"modbus_rtu","model":"XR77U / 2C310000","firmware":"5.9",
          "connection":{"port":"/dev/ttyUSB0","slave":1,"baudrate":9600,"parity":"N","stopbits":1,"timeout":0.6},"parameters":params})
    cp = PROFILES / "carel_pjezc0p000.json"
    if not cp.exists():
        params = {n:{"token":t,"scale":sc,"signed":sg,"description":d,"units":u,"access":"read_write",
                     "verification":"live_confirmed"} for n,(t,sc,sg,d,u) in CAREL.items()}
        save_profile({"name":"CAREL PJEZC0P000","protocol":"carel_pjez",
          "connection":{"port":"/dev/ttyACM0","unit":1,"baudrate":19200,"parity":"N","stopbits":2},"parameters":params})

def profiles(protocol=None):
    seed_profiles(); result=[]
    for path in sorted(PROFILES.glob("*.json")):
        try:
            item=json.loads(path.read_text(encoding="utf-8"))
            if protocol is None or item.get("protocol")==protocol: result.append(item)
        except Exception as exc: print(f"Could not load {path.name}: {exc}")
    return result

def select_profile(protocol=None):
    items=profiles(protocol)
    for i,p in enumerate(items,1): print(f" {i}) {p['name']} ({p['protocol']})")
    try: return items[int(ask("Select profile",1))-1]
    except (ValueError,IndexError): print("Invalid selection."); return None

def modbus_settings(profile):
    d=profile.get("connection",{})
    return {"port":ask("Serial port",d.get("port","/dev/ttyUSB0")),"slave":int(ask("Slave address",d.get("slave",1))),
      "baudrate":int(ask("Baud rate",d.get("baudrate",9600))),"parity":ask("Parity N/E/O",d.get("parity","N")).upper(),
      "stopbits":int(ask("Stop bits",d.get("stopbits",1))),"timeout":float(ask("Timeout seconds",d.get("timeout",0.6)))}

def instrument(settings):
    dev=minimalmodbus.Instrument(settings["port"],settings["slave"],mode=minimalmodbus.MODE_RTU)
    dev.serial.baudrate=settings["baudrate"]; dev.serial.bytesize=8
    dev.serial.parity={"N":serial.PARITY_NONE,"E":serial.PARITY_EVEN,"O":serial.PARITY_ODD}[settings["parity"]]
    dev.serial.stopbits=settings["stopbits"]; dev.serial.timeout=settings["timeout"]
    dev.clear_buffers_before_each_transaction=True
    return dev

def read_reg(dev,address,fc=3):
    try: return dev.read_register(address,0,functioncode=fc,signed=False)
    except Exception: return None

def test_modbus(profile):
    st=modbus_settings(profile)
    try: dev=instrument(st)
    except Exception as exc: print(f"Could not open port: {exc}"); return
    print("Testing known profile addresses with read-only FC03 requests...")
    for item in profile.get("parameters",{}).values():
        if "address" in item:
            value=read_reg(dev,item["address"],3)
            if value is not None:
                print(f"SUCCESS: holding register {item['address']} replied with raw value {value}.")
                profile["connection"]=st; save_profile(profile); return
    print("No valid reply. Check Adr, serial settings, A/B polarity and port ownership.")

def read_modbus(profile):
    st=modbus_settings(profile); dev=instrument(st)
    print(f"\n{profile['name']} MAPPED VALUES\n"+"-"*76)
    for name,item in profile.get("parameters",{}).items():
        raw=read_reg(dev,item["address"],3); loc=f"H:{item['address']}"
        if raw is None: print(f"{name:<10} {'N/A':>12} {item.get('units',''):<6} {loc:<10} no response"); continue
        val=(s16(raw) if item.get("signed") else raw)/float(item.get("scale",1))
        print(f"{name:<10} {val:>12g} {item.get('units',''):<6} {loc:<10} {item.get('verification','')}")

def scan_modbus(profile, quiet=False):
    st=modbus_settings(profile); start=int(ask("Starting address",0)); end=int(ask("Ending address",999)); dev=instrument(st)
    print("Read-only FC03 scan. No controller values will be written.")
    found={}
    for address in range(start,end+1):
        value=read_reg(dev,address,3)
        if value is not None:
            found[address]=value
            if not quiet: print(f" FOUND holding {address} raw={value}")
        if address and address%100==0: print(f" Scanned through {address}; readable={len(found)}")
    out=ROOT/"last_modbus_discovery.json"
    out.write_text(json.dumps({"settings":st,"holding":found},indent=2),encoding="utf-8")
    print(f"Found {len(found)} readable holding registers. Saved {out}")
    return st,found

def inference(before,after,old,new):
    options=[]
    for signed in (False,True):
        b=s16(before) if signed else before; a=s16(after) if signed else after
        if new!=old and (a-b)/(new-old)>0:
            exact=(a-b)/(new-old); scale=min((1,10,100,1000),key=lambda x:abs(x-exact))
            score=abs(exact-scale)+abs(b/scale-old)+abs(a/scale-new)
            options.append((score,scale,signed,b,a))
    return min(options,default=(1e9,1,False,before,after))

def map_modbus(profile):
    print("This compares two read-only snapshots. Change only one controller parameter.")
    if not yesno("Continue"): return
    st,before=scan_modbus(profile,True); name=ask("Parameter name"); desc=ask("Description",name); units=ask("Units","")
    try: old=float(ask("Current displayed value"))
    except ValueError: print("A numeric display value is required."); return
    input("Change only that parameter, exit the keypad menu, then press ENTER...")
    try: new=float(ask("New displayed value"))
    except ValueError: print("A numeric display value is required."); return
    dev=instrument(st); candidates=[]
    for address,oldraw in before.items():
        newraw=read_reg(dev,address,3)
        if newraw is not None and newraw!=oldraw:
            score,scale,signed,b,a=inference(oldraw,newraw,old,new)
            candidates.append((score,address,oldraw,newraw,scale,signed,b,a))
    candidates.sort()
    if not candidates: print("No changed registers found. Repeat with a larger safe change."); return
    for i,c in enumerate(candidates[:20],1):
        _,addr,br,ar,scale,signed,b,a=c
        print(f" {i}) H:{addr} raw {br}->{ar}; {'signed' if signed else 'unsigned'}; scale {scale}; decoded {b/scale:g}->{a/scale:g}")
    try:
        c=candidates[int(ask("Select candidate",1))-1]; _,addr,br,ar,suggested,signed,_,_=c
        scale=float(ask("Confirm/edit scale",suggested))
    except (ValueError,IndexError): print("Invalid selection or scale."); return
    signed=yesno("Interpret as signed 16-bit",signed)
    item={"register_type":"holding","address":addr,"scale":scale,"signed":signed,"description":desc,"units":units,
      "access":"read","verification":"read_mapped","evidence":{"display_before":old,"display_after":new,"raw_before":br,"raw_after":ar}}
    if yesno(f"Save {name} as H:{addr}, scale {scale:g}",True):
        profile.setdefault("parameters",{})[name]=item; profile["connection"]=st; save_profile(profile)

def write_modbus(profile):
    name=ask("Mapped parameter name"); item=profile.get("parameters",{}).get(name)
    if not item: print("Unknown mapped parameter."); return
    try: value=float(ask("Value to write"))
    except ValueError: print("Invalid value."); return
    raw=int(round(value*float(item.get("scale",1))))
    print("WARNING: This writes a real value and leaves the controller changed.")
    print(f"Proposed: {name}={value:g}, H:{item['address']}, raw={raw} (0x{raw&65535:04X})")
    if ask("Type WRITE to confirm")!="WRITE": print("Cancelled."); return
    st=modbus_settings(profile); dev=instrument(st)
    try:
        dev.write_register(item["address"],raw,0,functioncode=6,signed=item.get("signed",False)); time.sleep(.3)
        check=read_reg(dev,item["address"],3); print(f"Write accepted; raw read-back={check}")
        if yesno(f"Does the controller display show {value:g}"):
            item["access"]="read_write"; item["verification"]="write_verified"; save_profile(profile)
    except Exception as exc: print(f"Write failed: {exc}")

def carel_hex(text):
    result=0
    for c in text:
        if "0"<=c<="9": v=ord(c)-48
        elif "A"<=c<="F": v=ord(c)-55
        elif "a"<=c<="f": v=ord(c)-87
        elif ":"<=c<="?": v=ord(c)-48
        else: return 0
        result=(result<<4)|(v&15)
    return result

def carel_packet(body):
    core=bytes([STX])+body.encode("ascii")+bytes([ETX]); check=sum(core)&255
    return core+bytes([48+((check>>4)&15),48+(check&15)])

class PJEZ:
    def __init__(self,port,unit=1):
        self.unit=unit; self.slot=chr(48+unit)
        self.ser=serial.Serial(port,19200,bytesize=8,parity="N",stopbits=2,timeout=.5)
    def close(self): self.ser.close()
    def send(self,body,timeout=.8):
        self.ser.reset_input_buffer(); self.ser.write(carel_packet(body)); end=time.monotonic()+timeout
        while time.monotonic()<end:
            b=self.ser.read(1)
            if b and b[0]==ACK: return True
        return False
    def identity(self):
        self.ser.reset_input_buffer(); self.ser.write(carel_packet(f"{self.slot}?")); end=time.monotonic()+1; data=bytearray()
        while time.monotonic()<end:
            b=self.ser.read(1)
            if b: data+=b
            if ETX in data: data+=self.ser.read(2); break
        return bytes(data)
    def event(self,timeout=.8):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            b=self.ser.read(1)
            if not b: continue
            if b[0]==NUL: return bytes([NUL])
            if b[0]!=STX: continue
            data=bytearray([STX])
            while time.monotonic()<end:
                c=self.ser.read(1)
                if c: data+=c
                if c and c[0]==ETX: data+=self.ser.read(2); return bytes(data)
        return None
    def dump(self,cycles=180,max_nul=50):
        values={}; nulls=0
        if not self.send(f"{self.slot}F1"): return values
        for _ in range(cycles):
            self.ser.write(bytes([ENQ,48+self.unit])); frame=self.event()
            if frame==bytes([NUL]):
                nulls+=1
                if nulls>=max_nul: break
                continue
            if not frame: continue
            nulls=0; self.ser.write(bytes([ACK]))
            try:
                body=frame[1:frame.index(ETX)].decode("ascii","ignore")
                if len(body)>=5 and body[1] in "SUB": values[body[1:4]]=carel_hex(body[4:])&65535
            except (ValueError,IndexError): pass
        return values
    def write(self,token,raw,password=0x16):
        if not self.send(f"{self.slot}U71{password:04X}") or not self.send(f"{self.slot}A00001"): return False
        body=f"{self.slot}D{token[1]}{'1' if raw else '0'}" if token[0]=="B" else f"{self.slot}A{token[1]}{raw&65535:04X}"
        return self.send(body)

def carel_settings(profile):
    d=profile.get("connection",{}); return ask("Serial port",d.get("port","/dev/ttyACM0")),int(ask("Unit",d.get("unit",1)))

def test_carel(profile):
    try:
        port,unit=carel_settings(profile); dev=PJEZ(port,unit); reply=dev.identity(); dev.close()
        print(f"SUCCESS: {reply.hex(' ')}" if reply.startswith(bytes([STX])) else "No CAREL identity response.")
    except Exception as exc: print(f"Connection failed: {exc}")

def read_carel(profile):
    port,unit=carel_settings(profile); dev=PJEZ(port,unit); values=dev.dump(); dev.close()
    print(f"Captured {len(values)} CAREL tokens.")
    for name,item in profile.get("parameters",{}).items():
        raw=values.get(item["token"])
        val="N/A" if raw is None else f"{(s16(raw) if item.get('signed') else raw)/float(item.get('scale',1)):g}"
        print(f"{name:<8} {val:>10} {item.get('units',''):<6} token {item['token']}")
    for token,desc in CAREL_STATUS.items():
        print(f"{desc:<28} " + ("N/A" if token not in values else ("ON" if values[token]&1 else "OFF")))

def map_carel(profile):
    print("Two read-only F1 table dumps will be compared. Change one parameter only.")
    port,unit=carel_settings(profile); dev=PJEZ(port,unit); before=dev.dump()
    name=ask("Parameter name"); desc=ask("Description",name); units=ask("Units","")
    try: old=float(ask("Current displayed value"))
    except ValueError: dev.close(); print("Numeric value required."); return
    input("Change that parameter, exit its menu, then press ENTER...")
    try: new=float(ask("New displayed value"))
    except ValueError: dev.close(); print("Numeric value required."); return
    after=dev.dump(); dev.close(); candidates=[]
    for token in before.keys()&after.keys():
        if before[token]!=after[token]:
            result=inference(before[token],after[token],old,new); candidates.append((result[0],token,before[token],after[token],*result[1:]))
    candidates.sort()
    if not candidates: print("No changed token found."); return
    for i,c in enumerate(candidates[:20],1):
        _,token,br,ar,scale,signed,b,a=c; print(f" {i}) {token} raw {br}->{ar}; scale {scale}; decoded {b/scale:g}->{a/scale:g}")
    try:
        c=candidates[int(ask("Select candidate",1))-1]; _,token,br,ar,suggested,signed,_,_=c
        scale=float(ask("Confirm/edit scale",suggested))
    except (ValueError,IndexError): print("Invalid selection or scale."); return
    signed=yesno("Interpret as signed 16-bit",signed)
    profile.setdefault("parameters",{})[name]={"token":token,"scale":scale,"signed":signed,"description":desc,"units":units,
      "access":"read","verification":"read_mapped","evidence":{"display_before":old,"display_after":new,"raw_before":br,"raw_after":ar}}
    if yesno(f"Save {name} as {token}, scale {scale:g}",True): save_profile(profile)

def choose_protocol_profile():
    print(" 1) Modbus RTU\n 2) CAREL PJEZ TTL")
    protocol="modbus_rtu" if ask("Protocol",1)=="1" else "carel_pjez"
    return select_profile(protocol)

def list_ports():
    for p in serial.tools.list_ports.comports(): print(f"{p.device}: {p.description} [{p.hwid}]")

def main():
    seed_profiles()
    while True:
        print("\n"+"="*58+"\n             CONTROLLER SERIAL MAPPING TOOL v4.0\n"+"="*58)
        print("1) Test controller connection\n2) Read mapped values\n3) Discover Modbus holding registers")
        print("4) Map parameter by before/after comparison\n5) Controlled Modbus write verification")
        print("6) View saved profile\n7) List serial devices\n8) Exit")
        choice=ask("Select",1)
        if choice=="1":
            p=choose_protocol_profile()
            if p: test_modbus(p) if p["protocol"]=="modbus_rtu" else test_carel(p)
        elif choice=="2":
            p=select_profile()
            if p: read_modbus(p) if p["protocol"]=="modbus_rtu" else read_carel(p)
        elif choice=="3":
            p=select_profile("modbus_rtu")
            if p: scan_modbus(p)
        elif choice=="4":
            p=choose_protocol_profile()
            if p: map_modbus(p) if p["protocol"]=="modbus_rtu" else map_carel(p)
        elif choice=="5":
            p=select_profile("modbus_rtu")
            if p: write_modbus(p)
        elif choice=="6":
            p=select_profile()
            if p: print(json.dumps(p,indent=2))
        elif choice=="7": list_ports()
        elif choice=="8": return 0
        else: print("Invalid selection.")

if __name__=="__main__":
    try: raise SystemExit(main())
    except KeyboardInterrupt: print("\nStopped safely."); raise SystemExit(130)
