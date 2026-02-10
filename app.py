import streamlit as st
from CoolProp.CoolProp import PropsSI
import pandas as pd
import math
import graphviz

# --- [1. 확장된 PIPE DB (NPS & DN 매핑)] ---
PIPE_DATA = [
    {"NPS": "1/2\"", "DN": 15, "OD": 21.3, "Sch40": 2.77, "Sch80": 3.73, "Sch160": 4.78},
    {"NPS": "3/4\"", "DN": 20, "OD": 26.7, "Sch40": 2.87, "Sch80": 3.91, "Sch160": 5.56},
    {"NPS": "1\"", "DN": 25, "OD": 33.4, "Sch40": 3.38, "Sch80": 4.55, "Sch160": 6.35},
    {"NPS": "1-1/2\"", "DN": 40, "OD": 48.3, "Sch40": 3.68, "Sch80": 5.08, "Sch160": 7.14},
    {"NPS": "2\"", "DN": 50, "OD": 60.3, "Sch40": 3.91, "Sch80": 5.54, "Sch160": 8.74},
    {"NPS": "3\"", "DN": 80, "OD": 88.9, "Sch40": 5.49, "Sch80": 7.62, "Sch160": 11.13},
    {"NPS": "4\"", "DN": 100, "OD": 114.3, "Sch40": 6.02, "Sch80": 8.56, "Sch160": 13.49},
    {"NPS": "6\"", "DN": 150, "OD": 168.3, "Sch40": 7.11, "Sch80": 10.97, "Sch160": 18.26},
    {"NPS": "8\"", "DN": 200, "OD": 219.1, "Sch40": 8.18, "Sch80": 12.70, "Sch160": 23.01},
    {"NPS": "10\"", "DN": 250, "OD": 273.1, "Sch40": 9.27, "Sch80": 15.09, "Sch160": 28.58},
    {"NPS": "12\"", "DN": 300, "OD": 323.8, "Sch40": 10.31, "Sch80": 17.48, "Sch160": 33.32},
    {"NPS": "14\"", "DN": 350, "OD": 355.6, "Sch40": 11.13, "Sch80": 19.05, "Sch160": 35.71},
    {"NPS": "16\"", "DN": 400, "OD": 406.4, "Sch40": 12.70, "Sch80": 21.44, "Sch160": 40.49},
    {"NPS": "18\"", "DN": 450, "OD": 457.0, "Sch40": 14.27, "Sch80": 23.83, "Sch160": 45.24},
    {"NPS": "20\"", "DN": 500, "OD": 508.0, "Sch40": 15.09, "Sch80": 26.19, "Sch160": 50.01},
    {"NPS": "24\"", "DN": 600, "OD": 610.0, "Sch40": 17.48, "Sch80": 30.96, "Sch160": 59.54},
]

MATERIAL_DB = {
    "CS (A106-B)": {"roughness": 0.045, "stress": 17100, "y": 0.4},
    "Alloy (P91)": {"roughness": 0.045, "stress": 14300, "y": 0.4},
    "SS (304SS)": {"roughness": 0.015, "stress": 18800, "y": 0.4}
}

K_FACTORS = {
    "90 deg Elbow": 0.75, "45 deg Elbow": 0.35, "Tee (Branch)": 1.50,
    "Gate Valve": 0.15, "Globe Valve": 10.0, "Check Valve": 2.0
}

# --- [2. 유틸리티 함수] ---
def convert_to_pa(val, unit, rho=1000):
    if unit == "bar g": return (val + 1.01325) * 1e5
    if unit == "bar a": return val * 1e5
    if unit == "MPa g": return (val + 0.101325) * 1e6
    if unit == "MPa a": return val * 1e6
    if unit == "m (Head)": return (val * rho * 9.81) + 101325 # 절대압 환산
    return val

def convert_from_pa(pa, unit, rho=1000):
    if unit == "bar g": return (pa / 1e5) - 1.01325
    if unit == "bar a": return pa / 1e5
    if unit == "MPa g": return (pa / 1e6) - 0.101325
    if unit == "MPa a": return pa / 1e6
    if unit == "m (Head)": return (pa - 101325) / (rho * 9.81)
    return pa

# --- [3. 메인 앱] ---
if 'network' not in st.session_state:
    st.session_state.network = []

st.set_page_config(page_title="Piping Network Master", layout="wide")
st.title("🏭 Piping Network Master")

with st.sidebar:
    st.header("📍 Segment Definition")
    with st.form("input_form"):
        name = st.text_input("Segment ID", value=f"SEG-{len(st.session_state.network)+1}")
        parent = st.selectbox("Upstream Segment", ["None (Root)"] + [s['name'] for s in st.session_state.network])
        
        col1, col2 = st.columns(2)
        p_unit = col1.selectbox("Press Unit", ["bar g", "bar a", "MPa g", "MPa a", "m (Head)"])
        p_val = col2.number_input("Input Pressure", value=15.0 if "m" not in p_unit else 150.0)
        
        size_unit = st.radio("Pipe Size Unit", ["NPS (inch)", "DN (mm)"], horizontal=True)
        f_type = st.radio("Flow Unit", ["Mass (kg/h)", "Vol (m³/h)"], horizontal=True)
        f_val = st.number_input("Flow Value", value=10000.0)
        
        temp = st.number_input("Temp (°C)", value=250.0)
        mat = st.selectbox("Material", list(MATERIAL_DB.keys()))
        length = st.number_input("Length (m)", value=30.0)
        sch_pref = st.selectbox("Schedule", ["40", "80", "160"])
        v_limit = st.number_input("V-Limit (m/s)", value=35.0)
        
        f_counts = {fn: st.number_input(fn, min_value=0, value=0) for fn in K_FACTORS}
        
        if st.form_submit_button("Add Segment"):
            st.session_state.network.append({
                "name": name, "parent": parent, "p_unit": p_unit, "p_val": p_val,
                "f_type": f_type, "f_val": f_val, "temp": temp, "mat": mat, "size_unit": size_unit,
                "length": length, "sch": sch_pref, "v_limit": v_limit, "f_counts": f_counts
            })
            st.rerun()

# --- [4. 계산 및 결과] ---
def run_system_calc():
    results = []
    exit_p_map = {}
    
    for seg in st.session_state.network:
        # 1. 입구 압력 설정
        if seg['parent'] == "None (Root)":
            in_p_pa = convert_to_pa(seg['p_val'], seg['p_unit'])
        else:
            in_p_pa = exit_p_map.get(seg['parent'], 101325)
            
        T_k = seg['temp'] + 273.15
        rho = PropsSI('D', 'T', T_k, 'P', in_p_pa, "Water")
        mu = PropsSI('V', 'T', T_k, 'P', in_p_pa, "Water")
        
        vol_flow_s = (seg['f_val']/rho/3600) if "Mass" in seg['f_type'] else (seg['f_val']/3600)
        
        best_size = "N/A"; act_v = 0.0; dp_pa = 0.0
        
        for p in PIPE_DATA:
            thk = p[f"Sch{seg['sch']}"]
            id_m = (p["OD"] - 2*thk)/1000
            v = vol_flow_s / (math.pi * id_m**2 / 4)
            
            # B31.1 두께 검토
            S_pa = MATERIAL_DB[seg['mat']]['stress'] * 6894.76
            min_t = (in_p_pa * p["OD"]) / (2 * (S_pa + in_p_pa * 0.4)) + 1.5
            
            if v <= seg['v_limit'] and thk >= min_t:
                re = (rho * v * id_m) / mu
                rr = MATERIAL_DB[seg['mat']]['roughness'] / (id_m * 1000)
                f = (1/(-1.8*math.log10((rr/3.7)**1.11 + 6.9/re)))**2 if re > 2300 else 64/max(re,1)
                total_k = sum([seg['f_counts'][fn] * K_FACTORS[fn] for fn in K_FACTORS])
                dp_pa = (f * (seg['length']/id_m) + total_k) * (rho * v**2 / 2)
                
                best_size = p["NPS"] if "NPS" in seg['size_unit'] else f"DN {p['DN']}"
                act_v = v
                break
        
        exit_p_pa = in_p_pa - dp_pa
        exit_p_map[seg['name']] = exit_p_pa
        
        # 선택한 단위로 변환하여 저장
        in_p_disp = convert_from_pa(in_p_pa, seg['p_unit'], rho)
        out_p_disp = convert_from_pa(exit_p_pa, seg['p_unit'], rho)
        # 손실압력은 차이값이므로 별도 계산 (수두일 경우 m 단위로 바로 변환)
        dp_disp = (in_p_disp - out_p_disp) if "m" in seg['p_unit'] else (dp_pa / (1e5 if "bar" in seg['p_unit'] else 1e6))
        dp_unit_label = seg['p_unit'].split(' ')[0] if "m" not in seg['p_unit'] else "m"

        results.append({
            "Segment": seg['name'],
            f"Size ({seg['size_unit'].split(' ')[0]})": best_size,
            f"In-P ({seg['p_unit']})": round(in_p_disp, 3),
            f"Flow ({seg['f_type'].split(' ')[0]})": round(seg['f_val'], 1),
            "Vel (m/s)": round(act_v, 2),
            f"Loss ({dp_unit_label})": round(dp_disp, 4),
            f"Out-P ({seg['p_unit']})": round(out_p_disp, 3)
        })
    return results

# --- [5. 출력] ---
if st.session_state.network:
    final_res = run_system_calc()
    st.subheader("🖼️ System Diagram")
    dot = graphviz.Digraph(graph_attr={'rankdir': 'LR'})
    for r in final_res:
        # 동적 키 대응
        size_key = [k for k in r.keys() if "Size" in k][0]
        dot.node(r['Segment'], f"{r['Segment']}\n{r[size_key]}", shape='box', style='filled', fillcolor='lightblue')
        if r['Parent' if 'Parent' in r else 'Segment'] != r['Segment']: pass # 연결로직
    
    # 엣지 연결 (Parent 정보 기반)
    for s in st.session_state.network:
        if s['parent'] != "None (Root)":
            dot.edge(s['parent'], s['name'])
    st.graphviz_chart(dot)
    
    st.subheader("📊 Unit-Matched Analysis Report")
    st.dataframe(pd.DataFrame(final_res), use_container_width=True)
    
    if st.button("Reset All"):
        st.session_state.network = []
        st.rerun()
