"""Pydantic-схемы запросов/ответов."""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator


class SourceParamsIn(BaseModel):
    source_type: str = "transformer"
    z_t_mohm: float = 54.0
    r_t_mohm: float = 16.8
    x_t_mohm: float = 51.32
    u_nom_v: float = 380.0
    s_nom_kva: float = 3000.0


class CableInputIn(BaseModel):
    line_id: str = ""
    line_name: str = ""
    phases: int = 3
    power_kw: Optional[float] = None
    cos_phi: float = 0.85
    start_current_ratio: float = 1.0
    length_m: float = 50.0
    delta_u_pct_max: float = 5.0
    material: str = "Cu"
    insulation: str = "PVC"
    method: str = "C"
    cables_nearby: int = 1
    cable_count: int = 1
    section_mm2: Optional[float] = None
    ambient_temp_c: float = 30.0
    soil_resistivity: float = 2.5
    source: SourceParamsIn = Field(default_factory=SourceParamsIn)

    @model_validator(mode='after')
    def validate_critical_fields(self):
        errors = []
        if self.power_kw is None or self.power_kw <= 0:
            errors.append("power_kw обязателен и должен быть > 0 (мощность, кВт)")
        if self.length_m is None or self.length_m <= 0:
            errors.append("length_m обязателен и должен быть > 0 (длина, м)")
        if self.material not in ("Cu", "Al"):
            errors.append(f"material должен быть 'Cu' или 'Al', получено '{self.material}'")
        if self.insulation not in ("PVC", "XLPE"):
            errors.append(f"insulation должен быть 'PVC' или 'XLPE', получено '{self.insulation}'")
        if self.method not in ("A1", "A2", "B1", "B2", "C", "D1", "D2", "E", "F", "G"):
            errors.append(f"method '{self.method}' не поддерживается")
        if errors:
            raise ValueError("Ошибка входных данных: " + "; ".join(errors))
        return self


class CableResultOut(BaseModel):
    line_id: str
    line_name: str
    i_calc_a: float
    i_allowable_a: float
    i_kz_1ph_a: float
    i_kz_3ph_a: float
    section_mm2: float
    section_zero_mm2: float
    delta_u_pct: float
    cb_rating_a: float
    k_temp: float
    k_group: float
    k_soil: float
    check_current: bool
    check_voltage: bool
    check_kz: bool
    status: str
    hints: List[str]
    methodology: Dict[str, Any]


class BatchRequestIn(BaseModel):
    cables: List[CableInputIn]
    mode: str = "select"   # "select" | "check" | "max_load"


class ParsedRowOut(BaseModel):
    row_num: int
    cable_id: str
    cable_mark: str
    section_str: str
    phases: int
    section_mm2: float
    length_m: float
    voltage_kv: float
    from_point: str
    to_point: str
