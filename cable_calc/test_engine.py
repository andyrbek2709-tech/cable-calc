import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))
from engine import select_section, check_section, calc_max_load, CableInput, SourceParams

TP = SourceParams(z_t_mohm=54.0, r_t_mohm=16.8, x_t_mohm=51.32, u_nom_v=380.0)
results = []

def chk(name, got, expected, tol=0.05):
    ok = abs(got - expected) <= abs(expected) * tol + 0.5
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}]  {name}: {got:.3f}  (ожид. ~{expected})")
    results.append(ok)

# 1. Iр 3ф
print("\n[1] Iр 3ф: P=100кВт cosφ=0.85 -> 178.5А")
r = select_section(CableInput(phases=3, power_kw=100, cos_phi=0.85, length_m=50,
    material="Cu", insulation="PVC", method="C", cables_nearby=1, ambient_temp_c=30, source=TP))
chk("Iр, А", r.i_calc_a, 1000*100/(math.sqrt(3)*380*0.85))

# 2. Iр 1ф
print("\n[2] Iр 1ф: P=10кВт cosφ=0.9 -> 67.2А")
r1 = select_section(CableInput(phases=1, power_kw=10, cos_phi=0.90, length_m=30,
    material="Cu", insulation="PVC", method="C", cables_nearby=1, ambient_temp_c=30, source=TP))
chk("Iр, А", r1.i_calc_a, 1000*10/((380/math.sqrt(3))*0.90))

# 3. Сечение: метод C, Cu PVC, 30°C -> 70мм²
print("\n[3] Сечение: P=100кВт, C, Cu, ПВХ, 30°C -> 70мм²")
r3 = select_section(CableInput(phases=3, power_kw=100, cos_phi=0.85, length_m=50,
    material="Cu", insulation="PVC", method="C", cables_nearby=1, ambient_temp_c=30, source=TP))
chk("Сечение, мм²", r3.section_mm2, 70, tol=0.0)
chk("Iдоп, А", r3.i_allowable_a, 184, tol=0.05)

# 4. k_temp воздух 40°C -> 0.87
print("\n[4] k_temp воздух 40°C -> 0.87")
r4 = check_section(CableInput(phases=3, power_kw=50, cos_phi=0.85, length_m=30,
    material="Cu", insulation="PVC", method="C", cables_nearby=1, ambient_temp_c=40, source=TP, section_mm2=35))
chk("k_temp", r4.k_temp, 0.87, tol=0.02)

print("\n[4b] k_temp воздух 20°C -> 1.12")
r4b = check_section(CableInput(phases=3, power_kw=50, cos_phi=0.85, length_m=30,
    material="Cu", insulation="PVC", method="C", cables_nearby=1, ambient_temp_c=20, source=TP, section_mm2=35))
chk("k_temp", r4b.k_temp, 1.12, tol=0.02)

# 5. k_temp грунт 30°C -> 0.89
print("\n[5] k_temp грунт 30°C -> 0.89")
r5 = check_section(CableInput(phases=3, power_kw=50, cos_phi=0.85, length_m=30,
    material="Cu", insulation="PVC", method="D2", cables_nearby=1, ambient_temp_c=30, source=TP, section_mm2=35))
chk("k_temp (грунт)", r5.k_temp, 0.89, tol=0.02)

# 6. k_group метод C, 4 кабеля -> 0.75
print("\n[6] k_group метод C, 4 кабеля -> 0.75")
r6 = check_section(CableInput(phases=3, power_kw=30, cos_phi=0.85, length_m=30,
    material="Cu", insulation="PVC", method="C", cables_nearby=4, ambient_temp_c=30, source=TP, section_mm2=16))
chk("k_group", r6.k_group, 0.75, tol=0.05)

# 7. ΔU: P=100кВт, L=100м, 70мм²
print("\n[7] Падение напряжения: P=100кВт, L=100м, Cu 70мм², метод C")
r7 = check_section(CableInput(phases=3, power_kw=100, cos_phi=0.85, length_m=100,
    material="Cu", insulation="PVC", method="C", cables_nearby=1, ambient_temp_c=30, source=TP, section_mm2=70))
chk("ΔU, %", r7.delta_u_pct, 2.4, tol=0.30)

# 8. P_max: 95мм², метод C
print("\n[8] P_max: 95мм², метод C -> 223А, ~124.7кВт")
r8 = calc_max_load(CableInput(phases=3, cos_phi=0.85, material="Cu", insulation="PVC",
    method="C", ambient_temp_c=30, source=TP, section_mm2=95))
expected_p = 223 * 380 * math.sqrt(3) * 0.85 / 1000
chk("Iдоп, А", r8.i_allowable_a, 223, tol=0.02)
chk("P_max, кВт", r8.methodology.get("p_max_kw", 0), expected_p, tol=0.05)

# 9. Проверка: 35мм², P=30кВт, метод C -> OK
print("\n[9] Проверка: 35мм², P=30кВт, метод C -> OK")
r9 = check_section(CableInput(phases=3, power_kw=30, cos_phi=0.85, length_m=50,
    material="Cu", insulation="PVC", method="C", cables_nearby=1, ambient_temp_c=30, source=TP, section_mm2=35))
chk("Iр, А", r9.i_calc_a, 53.5, tol=0.05)
chk("Iдоп, А", r9.i_allowable_a, 119.0, tol=0.02)
ok_s = r9.status == "OK"
print(f"  [{'PASS' if ok_s else 'FAIL'}]  Статус: {r9.status}  (ожид. OK)")
results.append(ok_s)

# 10. АВ: Iр~178.5А -> 200А
print("\n[10] АВ: Iр~178.5А -> Iн=200А")
r10 = select_section(CableInput(phases=3, power_kw=100, cos_phi=0.85, length_m=50,
    material="Cu", insulation="PVC", method="C", cables_nearby=1, ambient_temp_c=30, source=TP))
chk("Iн_АВ, А", r10.cb_rating_a, 200, tol=0.0)

# 11. XLPE > PVC: 35мм², метод C
print("\n[11] XLPE vs PVC: 35мм² -> 147А > 119А")
r11 = check_section(CableInput(phases=3, power_kw=30, cos_phi=0.85, length_m=50,
    material="Cu", insulation="XLPE", method="C", cables_nearby=1, ambient_temp_c=30, source=TP, section_mm2=35))
chk("Iдоп XLPE, А", r11.i_allowable_a, 147.0, tol=0.02)
ok_xlpe = r11.i_allowable_a > r9.i_allowable_a
print(f"  [{'PASS' if ok_xlpe else 'FAIL'}]  XLPE>PVC: {r11.i_allowable_a:.1f} > {r9.i_allowable_a:.1f}")
results.append(ok_xlpe)

passed = sum(results)
total = len(results)
print(f"\n{'='*35}")
print(f"Итого: {passed}/{total}")
if passed == total:
    print("Все тесты прошли!")
else:
    print(f"{total - passed} упало")
