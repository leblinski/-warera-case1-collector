import sys, json, os
AUDIT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,AUDIT)
import ev_ref as E
SNAP='/home/user/-warera-case1-collector/data/warera_case1_market.json'
PUBLIC=os.path.join(os.path.dirname(AUDIT),'public')
def load(): return json.load(open(SNAP))
def tier_of(code):
    if code in E.WEAPON_CODES: return E.WEAPON_CODES.index(code)+1
    return int(code[-1])
def slot_of(code): return 'weapon' if code in E.WEAPON_CODES else code[:-1]
