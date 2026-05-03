"""
Расчётный движок кабельных линий до 1 кВ.
Методика: МЭК 60364-5-52, Беляев (ТКЗ), ПУЭ.
"""

import math
from dataclasses import dataclass, field
from typing import Optional
from .tables import (
    STANDARD_SECTIONS, METHOD_IDX,
    IZ_PVC_3_CU, IZ_PVC_3_AL, IZ_XLPE_3_CU, IZ_XLPE_3_AL,
    IZ_PVC_3_CU_EF, IZ_XLPE_3_CU_EF, IZ_PVC_3_AL_EF, IZ_XLPE_3_AL_EF,
    K_TEMP_AIR, K_TEMP_GROUND, K_GROUP_AIR, K_GROUP_GROUND_D2,
    K_SOIL_RESISTIVITY, R0_CU_20, R0_AL_20, X0_CABLE,
    ALPHA_CU, ALPHA_AL, CB_RATINGS, FUSE_RATINGS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Входные данные
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SourceParams:
    """Параметры источника питания (трансформатор или ДГУ)."""
    source_type: str = "transformer"  # "transformer" | "generator"
    # Трансформатор
    z_t_mohm: float = 54.0     # Полное сопротивление тр-ра (1ф КЗ), мОм
    r_t_mohm: float = 16.8     # Активное сопротивление тр-ра, мОм
    x_t_mohm: float = 51.32    # Реактивное сопротивление тр-ра, мОм
    u_nom_v: float = 380.0     # Номинальное напряжение, В
    # ДГУ (дополнительно)
    xd2_pu: float = 0.166      # Xd'' о.е.
    s_nom_kva: float = 3000.0  # Номинальная мощность ДГУ, кВА
    gen_count: int = 1         # Кол-во генераторов


@dataclass
class CableInput:
    """Исходные данные одной кабельной линии."""
    line_id: str = ""
    line_name: str = ""
    phases: int = 3               # 1 или 3
    power_kw: Optional[float] = None   # Расчётная мощность, кВт
    cos_phi: float = 0.85
    start_current_ratio: float = 1.0   # Кратность пускового тока (Iп/Iн)
    length_m: float = 50.0        # Длина линии, м
    delta_u_pct_max: float = 5.0  # Допустимое падение напряжения, %
    material: str = "Cu"          # "Cu" | "Al"
    insulation: str = "PVC"       # "PVC" | "XLPE"
    method: str = "C"             # Способ прокладки МЭК
    cables_nearby: int = 1        # Кол-во кабелей в группе
    spacing: str = "touch"        # Расстояние между: "touch"|"0.125"|"0.25"|"0.5"
    cable_count: int = 1          # Кол-во параллельных кабелей
    section_mm2: Optional[float] = None   # Сечение (если задано)
    ambient_temp_c: float = 30.0  # Температура среды, °C
    soil_resistivity: float = 2.5 # Тепловое сопр. грунта, K·м/Вт
    k_safety: float = 1.0         # Коэффициент запаса по току
    source: SourceParams = field(default_factory=SourceParams)


# ─────────────────────────────────────────────────────────────────────────────
# Результат
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CableResult:
    line_id: str = ""
    line_name: str = ""
    # Токи
    i_calc_a: float = 0.0        # Расчётный ток, А
    i_allowable_a: float = 0.0   # Допустимый ток кабеля с поправками, А
    i_kz_1ph_a: float = 0.0      # Ток 1ф КЗ, А
    i_kz_3ph_a: float = 0.0      # Ток 3ф КЗ, А
    # Сечение
    section_mm2: float = 0.0
    section_zero_mm2: float = 0.0  # Сечение нулевого проводника
    # Падение напряжения
    delta_u_pct: float = 0.0
    # Защита
    cb_rating_a: float = 0.0     # Номинал АВ, А
    cb_thermal_a: float = 0.0    # Уставка теплового расцепителя, А
    cb_mag_a: float = 0.0        # Уставка ЭМ расцепителя, А
    fuse_rating_a: float = 0.0   # Номинал предохранителя, А
    # Поправочные коэффициенты
    k_temp: float = 1.0
    k_group: float = 1.0
    k_soil: float = 1.0
    # Проверки
    check_current: bool = True
    check_voltage: bool = True
    check_kz: bool = True
    # Методика (формулы + значения)
    methodology: dict = field(default_factory=dict)
    # Подсказки при несоответствии
    hints: list = field(default_factory=list)
    # Итоговый статус
    status: str = "OK"  # "OK" | "WARNING" | "ERROR"


# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────────────────────

def _interp_table(table: dict, key: float) -> Optional[float]:
    """Линейная интерполяция по словарю {ключ: значение}."""
    keys = sorted(table.keys())
    if key <= keys[0]:
        return table[keys[0]]
    if key >= keys[-1]:
        return table[keys[-1]]
    for i in range(len(keys) - 1):
        k1, k2 = keys[i], keys[i + 1]
        if k1 <= key <= k2:
            v1, v2 = table[k1], table[k2]
            if v1 is None or v2 is None:
                return v1 if v2 is None else v2
            return v1 + (v2 - v1) * (key - k1) / (k2 - k1)
    return None


def _nearest_group(table: dict, n: int) -> float:
    """Ближайший ключ (снизу) в таблице группирования."""
    keys = sorted(k for k in table.keys() if k <= n)
    return table[keys[-1]] if keys else list(table.values())[0]


def _next_section(s: float) -> Optional[float]:
    """Следующее стандартное сечение."""
    for sec in STANDARD_SECTIONS:
        if sec > s:
            return sec
    return None


def _round_up_section(s: float) -> float:
    """Подобрать стандартное сечение ≥ s."""
    for sec in STANDARD_SECTIONS:
        if sec >= s - 0.001:
            return sec
    return STANDARD_SECTIONS[-1]


def _calc_current(inp: CableInput) -> float:
    """
    Расчётный ток линии (А).
    3ф: Iр = P / (√3 · U · cosφ)
    1ф: Iр = P / (U_ф · cosφ)
    """
    if inp.power_kw is None:
        return 0.0
    if inp.phases == 3:
        return 1000 * inp.power_kw / (math.sqrt(3) * inp.source.u_nom_v * inp.cos_phi)
    else:
        return 1000 * inp.power_kw / (inp.source.u_nom_v / math.sqrt(3) * inp.cos_phi)


def _get_iz0(inp: CableInput, section: float) -> Optional[float]:
    """
    Базовый допустимый ток кабеля (А) для заданного сечения и метода прокладки.
    При методах E/F используются таблицы EF.
    """
    m = inp.method
    is_ef = m in ("E", "F", "G")

    if is_ef:
        if inp.material == "Cu":
            t = IZ_PVC_3_CU_EF if inp.insulation == "PVC" else IZ_XLPE_3_CU_EF
        else:
            t = IZ_PVC_3_AL_EF if inp.insulation == "PVC" else IZ_XLPE_3_AL_EF
        return t.get(section)
    else:
        idx = METHOD_IDX.get(m)
        if idx is None:
            return None
        if inp.material == "Cu":
            t = IZ_PVC_3_CU if inp.insulation == "PVC" else IZ_XLPE_3_CU
        else:
            t = IZ_PVC_3_AL if inp.insulation == "PVC" else IZ_XLPE_3_AL
        row = t.get(section)
        if row is None:
            return None
        val = row[idx]
        return val if val else None


def _get_k_temp(inp: CableInput) -> float:
    """
    Поправочный коэффициент на температуру среды.
    Таблица B.52.14 (воздух) или B.52.15 (грунт).
    """
    is_ground = inp.method in ("D1", "D2")
    t = inp.ambient_temp_c
    col = 0 if inp.insulation == "PVC" else 1

    if is_ground:
        k = _interp_table({k: v[col] for k, v in K_TEMP_GROUND.items()}, t)
    else:
        k = _interp_table({k: v[col] for k, v in K_TEMP_AIR.items()}, t)
    return k if k else 1.0


def _get_k_group(inp: CableInput) -> float:
    """
    Поправочный коэффициент на групповую прокладку.
    Таблица B.52.17 (воздух) / B.52.18 (земля D2).
    """
    n = inp.cables_nearby
    if n <= 1:
        return 1.0
    m = inp.method
    if m == "D2":
        row = K_GROUP_GROUND_D2.get(n) or K_GROUP_GROUND_D2[
            max(k for k in K_GROUP_GROUND_D2 if k <= n)]
        return row.get(inp.spacing, row["touch"])
    elif m in ("A1", "A2", "B1", "B2"):
        return _nearest_group(K_GROUP_AIR["bundles"], n)
    elif m == "C":
        return _nearest_group(K_GROUP_AIR["wall"], n)
    elif m in ("E", "F"):
        return _nearest_group(K_GROUP_AIR["tray"], n)
    elif m == "G":
        return _nearest_group(K_GROUP_AIR["ladder"], n)
    return 1.0


def _get_k_soil(inp: CableInput) -> float:
    """
    Поправочный коэффициент на тепловое сопротивление грунта.
    Таблица B.52.16. Применяется только для D1/D2.
    """
    if inp.method not in ("D1", "D2"):
        return 1.0
    rho = inp.soil_resistivity
    col = 0 if inp.method == "D1" else 1
    k = _interp_table({k: v[col] for k, v in K_SOIL_RESISTIVITY.items()}, rho)
    return k if k else 1.0


def _r_at_temp(r0: float, material: str, t_c: float) -> float:
    """Активное сопротивление при рабочей температуре (мОм/м)."""
    alpha = ALPHA_CU if material == "Cu" else ALPHA_AL
    return r0 * (1 + alpha * (t_c - 20))


def _get_r0(material: str, section: float) -> float:
    """Удельное активное сопротивление жилы при 20°C (мОм/м)."""
    tbl = R0_CU_20 if material == "Cu" else R0_AL_20
    if section in tbl:
        return tbl[section]
    # Интерполяция
    return _interp_table(tbl, section) or 0.1


def _calc_delta_u(inp: CableInput, section: float) -> float:
    """
    Падение напряжения (%).
    ΔU = √3 · Iр · L · (R·cosφ + X·sinφ) / U_ном · 100%  [3ф]
    ΔU = 2 · Iр · L · (R·cosφ + X·sinφ) / U_ном · 100%   [1ф]
    R, X — в Ом на всю длину.
    """
    if inp.power_kw is None:
        return 0.0
    t_work = 90.0 if inp.insulation == "XLPE" else 70.0
    r0 = _get_r0(inp.material, section)
    r_work = _r_at_temp(r0, inp.material, t_work)  # мОм/м
    x0 = X0_CABLE  # мОм/м

    i_r = _calc_current(inp)
    # Перевод: мОм/м → Ом/км → Ом для длины L (м)
    R = r_work * inp.length_m / 1000  # Ом (по одному проводнику)
    X = x0 * inp.length_m / 1000

    sin_phi = math.sin(math.acos(inp.cos_phi))

    if inp.phases == 3:
        du = math.sqrt(3) * i_r * (R * inp.cos_phi + X * sin_phi) / inp.source.u_nom_v * 100
    else:
        du = 2 * i_r * (R * inp.cos_phi + X * sin_phi) / inp.source.u_nom_v * 100

    return round(du / inp.cable_count, 3)


def _calc_kz_1ph(inp: CableInput, section: float) -> float:
    """
    Ток однофазного КЗ (А) — метод Беляева.
    Iкз1ф = U_ф / (Z_т/3 + Z_л)
    где Z_л — сопротивление петли фаза-ноль (2 · R_фазн + R_нулев).
    """
    u_f = inp.source.u_nom_v / math.sqrt(3)  # Фазное напряжение

    # Сопротивление трансформатора на 1ф КЗ
    z_t = inp.source.z_t_mohm / 1000  # Ом

    t_work = 90.0 if inp.insulation == "XLPE" else 70.0
    r0 = _get_r0(inp.material, section)
    r_work = _r_at_temp(r0, inp.material, t_work)  # мОм/м → × L → мОм → /1000 → Ом
    R_phase = r_work * inp.length_m / 1e6  # Ом
    R_neutral = R_phase  # Нулевой такого же сечения (упрощение)

    z_loop = R_phase + R_neutral  # Ом — петля фаза-ноль
    z_total = z_t + z_loop

    return round(u_f / z_total, 1) if z_total > 0 else 0.0


def _calc_kz_3ph(inp: CableInput, section: float) -> float:
    """
    Ток трёхфазного КЗ (А) в начале линии.
    Iкз3ф = U_ном / (√3 · Z_т)
    """
    z_t = inp.source.z_t_mohm / 1000
    if z_t <= 0:
        return 0.0
    return round(inp.source.u_nom_v / (math.sqrt(3) * z_t), 1)


def _select_cb(i_calc: float, k_start: float, i_allowable: float,
               k_safety_t: float = 1.05, k_safety_m: float = 1.25) -> dict:
    """
    Подбор автоматического выключателя.
    Условия:
      Iн_АВ ≥ Iр (защита от перегрузки)
      Iн_АВ ≤ Iдоп / k_safety (защита кабеля)
      Iэм = Iн_АВ · уставка ≥ k_start · Iр  (отстройка от пуска)
    """
    i_min = i_calc
    i_max = i_allowable / k_safety_t

    cb = next((r for r in CB_RATINGS if r >= i_min), CB_RATINGS[-1])
    i_thermal = cb * k_safety_t
    i_mag = cb * k_safety_m * k_start if k_start > 1 else cb * k_safety_m

    return {
        "cb_rating_a": cb,
        "cb_thermal_a": round(i_thermal, 1),
        "cb_mag_a": round(i_mag, 1),
    }


def _select_fuse(i_calc: float) -> float:
    """Подбор предохранителя ППН."""
    return next((r for r in FUSE_RATINGS if r >= i_calc * 1.25), FUSE_RATINGS[-1])


def _build_hints(res: CableResult, inp: CableInput) -> list:
    """Генерация подсказок при несоответствии нормам."""
    hints = []
    if not res.check_current:
        next_sec = _next_section(res.section_mm2)
        if next_sec:
            hints.append(
                f"Увеличьте сечение с {res.section_mm2} до {next_sec} мм² "
                f"(Iдоп вырастет на ~{round((1 - res.i_calc_a / res.i_allowable_a) * 100 * -1)}%)"
            )
        hints.append(
            f"Или проложите {inp.cable_count + 1} параллельных кабеля "
            f"(ток на кабель снизится до {round(res.i_calc_a / (inp.cable_count + 1), 1)} А)"
        )
        if inp.method in ("D1", "D2"):
            hints.append("Смените способ прокладки на открытый (C, E, F) — допустимый ток выше.")
    if not res.check_voltage:
        max_l = round(
            inp.delta_u_pct_max / max(res.delta_u_pct, 0.001) * inp.length_m, 1)
        hints.append(
            f"ΔU={res.delta_u_pct}% > {inp.delta_u_pct_max}%. "
            f"Уменьшите длину до {max_l} м или увеличьте сечение."
        )
        next_sec = _next_section(res.section_mm2)
        if next_sec:
            hints.append(f"Увеличьте сечение до {next_sec} мм² для снижения ΔU.")
    if not res.check_kz:
        hints.append(
            f"Ток 1ф КЗ ({res.i_kz_1ph_a} А) недостаточен для срабатывания АВ "
            f"(уставка ЭМ {res.cb_mag_a} А). "
            f"Проверьте сечение нулевого проводника или выберите АВ с меньшей уставкой ЭМ."
        )
    return hints


# ─────────────────────────────────────────────────────────────────────────────
# Основные функции расчёта
# ─────────────────────────────────────────────────────────────────────────────

def select_section(inp: CableInput) -> CableResult:
    """
    Режим 1: Подбор сечения кабеля по расчётному току.
    Алгоритм:
      1. Вычислить Iр
      2. Для каждого стандартного сечения (по возрастанию):
         - Iдоп = Iз0 · kт · kгр · kгрунт
         - Если Iдоп ≥ Iр · k_safety → сечение подходит
      3. Проверить ΔU, при превышении — следующее сечение
    """
    res = CableResult(line_id=inp.line_id, line_name=inp.line_name)
    i_r = _calc_current(inp)
    res.i_calc_a = round(i_r, 2)

    k_temp = _get_k_temp(inp)
    k_group = _get_k_group(inp)
    k_soil = _get_k_soil(inp)
    res.k_temp = round(k_temp, 3)
    res.k_group = round(k_group, 3)
    res.k_soil = round(k_soil, 3)

    chosen_section = None
    for sec in STANDARD_SECTIONS:
        iz0 = _get_iz0(inp, sec)
        if iz0 is None:
            continue
        iz = iz0 * k_temp * k_group * k_soil * inp.cable_count
        if iz >= i_r * inp.k_safety:
            # Проверить ΔU
            du = _calc_delta_u(inp, sec)
            if inp.delta_u_pct_max > 0 and du > inp.delta_u_pct_max:
                continue  # Пробуем следующее сечение
            chosen_section = sec
            res.i_allowable_a = round(iz, 1)
            res.delta_u_pct = round(du, 3)
            break

    if chosen_section is None:
        chosen_section = STANDARD_SECTIONS[-1]
        iz0 = _get_iz0(inp, chosen_section) or 0
        res.i_allowable_a = round(iz0 * k_temp * k_group * k_soil * inp.cable_count, 1)
        res.delta_u_pct = round(_calc_delta_u(inp, chosen_section), 3)
        res.hints.append("Максимальное стандартное сечение не обеспечивает ток. Рассмотрите параллельную прокладку кабелей.")

    res.section_mm2 = chosen_section
    res.section_zero_mm2 = chosen_section if chosen_section <= 16 else chosen_section / 2

    # КЗ
    res.i_kz_1ph_a = _calc_kz_1ph(inp, chosen_section)
    res.i_kz_3ph_a = _calc_kz_3ph(inp, chosen_section)

    # Защита
    cb = _select_cb(i_r, inp.start_current_ratio, res.i_allowable_a)
    res.cb_rating_a = cb["cb_rating_a"]
    res.cb_thermal_a = cb["cb_thermal_a"]
    res.cb_mag_a = cb["cb_mag_a"]
    res.fuse_rating_a = _select_fuse(i_r)

    # Проверки
    res.check_current = res.i_allowable_a >= i_r * inp.k_safety
    res.check_voltage = inp.delta_u_pct_max <= 0 or res.delta_u_pct <= inp.delta_u_pct_max
    res.check_kz = res.i_kz_1ph_a >= res.cb_mag_a if res.i_kz_1ph_a > 0 else True

    res.hints += _build_hints(res, inp)
    res.status = "OK" if (res.check_current and res.check_voltage and res.check_kz) else (
        "ERROR" if not res.check_current else "WARNING"
    )
    res.methodology = _build_methodology(inp, res, chosen_section, k_temp, k_group, k_soil,
                                         _get_iz0(inp, chosen_section))
    return res


def check_section(inp: CableInput) -> CableResult:
    """
    Режим 2: Проверка заданного сечения кабеля.
    """
    res = CableResult(line_id=inp.line_id, line_name=inp.line_name)
    section = inp.section_mm2
    if section is None:
        res.status = "ERROR"
        res.hints = ["Сечение не задано."]
        return res

    i_r = _calc_current(inp)
    res.i_calc_a = round(i_r, 2)

    k_temp = _get_k_temp(inp)
    k_group = _get_k_group(inp)
    k_soil = _get_k_soil(inp)
    res.k_temp = round(k_temp, 3)
    res.k_group = round(k_group, 3)
    res.k_soil = round(k_soil, 3)

    iz0 = _get_iz0(inp, section)
    iz = (iz0 or 0) * k_temp * k_group * k_soil * inp.cable_count
    res.i_allowable_a = round(iz, 1)
    res.section_mm2 = section
    res.section_zero_mm2 = section if section <= 16 else section / 2

    du = _calc_delta_u(inp, section)
    res.delta_u_pct = round(du, 3)

    res.i_kz_1ph_a = _calc_kz_1ph(inp, section)
    res.i_kz_3ph_a = _calc_kz_3ph(inp, section)

    cb = _select_cb(i_r, inp.start_current_ratio, res.i_allowable_a)
    res.cb_rating_a = cb["cb_rating_a"]
    res.cb_thermal_a = cb["cb_thermal_a"]
    res.cb_mag_a = cb["cb_mag_a"]
    res.fuse_rating_a = _select_fuse(i_r)

    res.check_current = iz >= i_r * inp.k_safety
    res.check_voltage = inp.delta_u_pct_max <= 0 or du <= inp.delta_u_pct_max
    res.check_kz = res.i_kz_1ph_a >= res.cb_mag_a if res.i_kz_1ph_a > 0 else True

    res.hints = _build_hints(res, inp)
    res.status = "OK" if (res.check_current and res.check_voltage and res.check_kz) else (
        "ERROR" if not res.check_current else "WARNING"
    )
    res.methodology = _build_methodology(inp, res, section, k_temp, k_group, k_soil, iz0)
    return res


def calc_max_load(inp: CableInput) -> CableResult:
    """
    Режим 3: Расчёт максимальной нагрузки по заданному сечению.
    Iмакс = Iдоп (с поправками)
    P_мах = Iмакс · U · cosφ · √3 (для 3ф)
    """
    section = inp.section_mm2
    res = CableResult(line_id=inp.line_id, line_name=inp.line_name)
    if section is None:
        res.status = "ERROR"
        res.hints = ["Сечение не задано."]
        return res

    k_temp = _get_k_temp(inp)
    k_group = _get_k_group(inp)
    k_soil = _get_k_soil(inp)
    res.k_temp = round(k_temp, 3)
    res.k_group = round(k_group, 3)
    res.k_soil = round(k_soil, 3)

    iz0 = _get_iz0(inp, section)
    iz = (iz0 or 0) * k_temp * k_group * k_soil * inp.cable_count
    res.i_allowable_a = round(iz, 1)
    res.section_mm2 = section

    if inp.phases == 3:
        p_max = iz * inp.source.u_nom_v * math.sqrt(3) * inp.cos_phi / 1000
    else:
        p_max = iz * inp.source.u_nom_v / math.sqrt(3) * inp.cos_phi / 1000

    res.i_calc_a = round(iz, 2)
    res.delta_u_pct = round(_calc_delta_u(inp, section), 3)
    res.i_kz_1ph_a = _calc_kz_1ph(inp, section)
    res.i_kz_3ph_a = _calc_kz_3ph(inp, section)
    res.cb_rating_a = next((r for r in [400, 630, 800, 1000, 1250] if r >= iz), 1600)
    res.status = "OK"
    res.methodology = {
        "mode": "max_load",
        "iz0_a": iz0,
        "k_temp": k_temp,
        "k_group": k_group,
        "k_soil": k_soil,
        "i_allowable_a": iz,
        "p_max_kw": round(p_max, 2),
        "formula_i": "Iдоп = Iз0 · kт · kгр · kгрунт · N",
        "formula_p": "P_max = Iдоп · U · cosφ · √3  [кВт]" if inp.phases == 3
                     else "P_max = Iдоп · U_ф · cosφ  [кВт]",
    }
    return res


# ─────────────────────────────────────────────────────────────────────────────
# Формирование методики (для отчёта)
# ─────────────────────────────────────────────────────────────────────────────

def _build_methodology(inp, res, section, k_temp, k_group, k_soil, iz0) -> dict:
    t_work = 90.0 if inp.insulation == "XLPE" else 70.0
    r0 = _get_r0(inp.material, section)
    r_work = _r_at_temp(r0, inp.material, t_work)
    sin_phi = math.sin(math.acos(inp.cos_phi))
    u_f = inp.source.u_nom_v / math.sqrt(3)

    return {
        "mode": "select" if inp.section_mm2 is None else "check",
        # 1. Расчётный ток
        "i_calc": {
            "formula": "Iр = P·1000 / (√3·U·cosφ)" if inp.phases == 3 else "Iр = P·1000 / (Uф·cosφ)",
            "values": {
                "P, кВт": inp.power_kw, "U, В": inp.source.u_nom_v, "cosφ": inp.cos_phi
            },
            "result_a": res.i_calc_a,
            "norm": "МЭК 60364-5-52",
        },
        # 2. Допустимый ток
        "i_allowable": {
            "formula": "Iдоп = Iз0 · kт · kгр · kγ · N",
            "values": {
                "Iз0, А": iz0,
                "kт (темп.)": k_temp,
                "kгр (группа)": k_group,
                "kγ (грунт)": k_soil,
                "N (параллельно)": inp.cable_count,
                "Способ прокладки": inp.method,
                "Изоляция": inp.insulation,
                "Материал": inp.material,
                "Сечение, мм²": section,
            },
            "result_a": res.i_allowable_a,
            "table_ref": "МЭК 60364-5-52, Табл. B.52.4/B.52.5",
        },
        # 3. Падение напряжения
        "delta_u": {
            "formula": "ΔU = √3·Iр·L·(r0·cosφ + x0·sinφ) / U · 100%" if inp.phases == 3
                       else "ΔU = 2·Iр·L·(r0·cosφ + x0·sinφ) / U · 100%",
            "values": {
                "r0, мОм/м": round(r_work, 4), "x0, мОм/м": X0_CABLE,
                "L, м": inp.length_m, "cosφ": inp.cos_phi, "sinφ": round(sin_phi, 4),
                "U, В": inp.source.u_nom_v,
            },
            "result_pct": res.delta_u_pct,
            "limit_pct": inp.delta_u_pct_max,
        },
        # 4. Ток КЗ
        "kz": {
            "formula_1ph": "Iкз1ф = Uф / (Zт + 2·R_ф)",
            "formula_3ph": "Iкз3ф = Uн / (√3·Zт)",
            "values": {
                "Uф, В": round(u_f, 1),
                "Zт, Ом": round(inp.source.z_t_mohm / 1000, 4),
                "R_ф, Ом": round(r_work * inp.length_m / 1e6, 6),
            },
            "result_1ph_a": res.i_kz_1ph_a,
            "result_3ph_a": res.i_kz_3ph_a,
            "norm": "Беляев Е.Н. «Выбор аппаратов защиты»",
        },
        # 5. Защита
        "protection": {
            "formula": "Iн_АВ ≥ Iр; Iн_АВ ≤ Iдоп/1.05; Iэм ≥ k_пуск·Iр",
            "values": {
                "Iн_АВ, А": res.cb_rating_a,
                "Iт (уставка), А": res.cb_thermal_a,
                "Iэм (уставка), А": res.cb_mag_a,
                "Предохранитель, А": res.fuse_rating_a,
            },
            "norm": "ГОСТ Р 50571.4.43-2012, ПУЭ п.3.1.8",
        },
    }
