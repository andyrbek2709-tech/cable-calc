"""FastAPI маршруты."""
import io, os, sys, tempfile
from dataclasses import asdict as _asdict
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine import select_section, check_section, calc_max_load, CableInput, SourceParams
from parsers import parse_file
from .schemas import CableInputIn, CableResultOut, BatchRequestIn, ParsedRowOut

router = APIRouter()


def _asdict_result(r, inp: CableInputIn) -> dict:
    d = _asdict(r)
    d["cable_mark"]     = inp.material + "-" + inp.insulation
    d["length_m"]       = inp.length_m
    d["method"]         = inp.method
    d["phases"]         = inp.phases
    d["ambient_temp_c"] = inp.ambient_temp_c
    return d


def _to_engine_input(inp: CableInputIn) -> CableInput:
    src = SourceParams(
        source_type=inp.source.source_type,
        z_t_mohm=inp.source.z_t_mohm,
        r_t_mohm=inp.source.r_t_mohm,
        x_t_mohm=inp.source.x_t_mohm,
        u_nom_v=inp.source.u_nom_v,
        s_nom_kva=inp.source.s_nom_kva,
    )
    return CableInput(
        line_id=inp.line_id, line_name=inp.line_name,
        phases=inp.phases, power_kw=inp.power_kw,
        cos_phi=inp.cos_phi, start_current_ratio=inp.start_current_ratio,
        length_m=inp.length_m, delta_u_pct_max=inp.delta_u_pct_max,
        material=inp.material, insulation=inp.insulation,
        method=inp.method, cables_nearby=inp.cables_nearby,
        cable_count=inp.cable_count, section_mm2=inp.section_mm2,
        ambient_temp_c=inp.ambient_temp_c,
        soil_resistivity=inp.soil_resistivity,
        source=src,
    )


def _result_to_out(r) -> CableResultOut:
    return CableResultOut(
        line_id=r.line_id, line_name=r.line_name,
        i_calc_a=round(r.i_calc_a, 2),
        i_allowable_a=round(r.i_allowable_a, 2),
        i_kz_1ph_a=round(r.i_kz_1ph_a, 1),
        i_kz_3ph_a=round(r.i_kz_3ph_a, 1),
        section_mm2=r.section_mm2,
        section_zero_mm2=r.section_zero_mm2,
        delta_u_pct=round(r.delta_u_pct, 3),
        cb_rating_a=r.cb_rating_a,
        k_temp=round(r.k_temp, 3),
        k_group=round(r.k_group, 3),
        k_soil=round(r.k_soil, 3),
        check_current=r.check_current,
        check_voltage=r.check_voltage,
        check_kz=r.check_kz,
        status=r.status,
        hints=r.hints,
        methodology=r.methodology,
    )


@router.post("/calculate/single", response_model=CableResultOut)
def calculate_single(inp: CableInputIn):
    try:
        if inp.power_kw is None or inp.power_kw <= 0:
            raise ValueError("power_kw (мощность) обязателен и должен быть > 0 для режима select")
        return _result_to_out(select_section(_to_engine_input(inp)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/calculate/check", response_model=CableResultOut)
def calculate_check(inp: CableInputIn):
    if inp.section_mm2 is None:
        raise HTTPException(status_code=400, detail="section_mm2 обязателен")
    try:
        return _result_to_out(check_section(_to_engine_input(inp)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/calculate/max_load", response_model=CableResultOut)
def calculate_max_load_route(inp: CableInputIn):
    if inp.section_mm2 is None:
        raise HTTPException(status_code=400, detail="section_mm2 обязателен")
    try:
        return _result_to_out(calc_max_load(_to_engine_input(inp)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/calculate/batch", response_model=List[CableResultOut])
def calculate_batch(req: BatchRequestIn):
    fn_map = {"select": select_section, "check": check_section, "max_load": calc_max_load}
    calc_fn = fn_map.get(req.mode, select_section)
    results = []
    for inp in req.cables:
        try:
            if req.mode == "select" and (inp.power_kw is None or inp.power_kw <= 0):
                raise ValueError(f"Режим 'select': power_kw обязателен и > 0, получено {inp.power_kw}")
            if req.mode in ("check", "max_load") and (inp.section_mm2 is None or inp.section_mm2 <= 0):
                raise ValueError(f"Режим '{req.mode}': section_mm2 обязателен и > 0, получено {inp.section_mm2}")
            results.append(_result_to_out(calc_fn(_to_engine_input(inp))))
        except Exception as e:
            error_hint = str(e)
            if "power_kw" in error_hint or "mощность" in error_hint.lower():
                error_hint = f"❌ Не найдена мощность кабеля. {error_hint}"
            elif "section_mm2" in error_hint or "сечение" in error_hint.lower():
                error_hint = f"❌ Не найдено сечение кабеля. {error_hint}"
            results.append(CableResultOut(
                line_id=inp.line_id, line_name=inp.line_name,
                i_calc_a=0, i_allowable_a=0, i_kz_1ph_a=0, i_kz_3ph_a=0,
                section_mm2=0, section_zero_mm2=0, delta_u_pct=0,
                cb_rating_a=0, k_temp=1, k_group=1, k_soil=1,
                check_current=False, check_voltage=False, check_kz=False,
                status="ERROR", hints=[error_hint], methodology={},
            ))
    return results


@router.post("/parse/journal", response_model=List[ParsedRowOut])
async def parse_journal(file: UploadFile = File(...)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ("pdf", "xlsx", "xls", "xlsm", "docx", "doc"):
        raise HTTPException(status_code=415, detail=f"Формат .{ext} не поддерживается")
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = parse_file(tmp_path)
    finally:
        os.unlink(tmp_path)
    return [
        ParsedRowOut(
            row_num=r.row_num, cable_id=r.cable_id,
            cable_mark=r.cable_mark, section_str=r.section_str,
            phases=r.phases, section_mm2=r.section_mm2,
            length_m=r.length_m, voltage_kv=r.voltage_kv,
            from_point=r.from_point, to_point=r.to_point,
        )
        for r in result.rows
    ]


@router.post("/report/excel")
def report_excel(req: BatchRequestIn):
    from reports import build_excel_report
    fn_map = {"select": select_section, "check": check_section, "max_load": calc_max_load}
    calc_fn = fn_map.get(req.mode, select_section)
    results = []
    for inp in req.cables:
        try:
            results.append(_asdict_result(calc_fn(_to_engine_input(inp)), inp))
        except Exception as e:
            results.append({"line_id": inp.line_id, "line_name": inp.line_name,
                            "status": "ERROR", "hints": [str(e)], "methodology": {},
                            "section_mm2": 0, "i_calc_a": 0, "i_allowable_a": 0,
                            "delta_u_pct": 0, "cb_rating_a": 0, "i_kz_1ph_a": 0,
                            "i_kz_3ph_a": 0, "k_temp": 1, "k_group": 1,
                            "cable_mark": "", "length_m": 0, "method": "", "phases": 3,
                            "ambient_temp_c": 30})
    xlsx = build_excel_report(results)
    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=cable_calc.xlsx"},
    )


@router.post("/report/word")
def report_word(req: BatchRequestIn):
    from reports import build_word_report
    fn_map = {"select": select_section, "check": check_section, "max_load": calc_max_load}
    calc_fn = fn_map.get(req.mode, select_section)
    results = []
    for inp in req.cables:
        try:
            results.append(_asdict_result(calc_fn(_to_engine_input(inp)), inp))
        except Exception as e:
            results.append({"line_id": inp.line_id, "line_name": inp.line_name,
                            "status": "ERROR", "hints": [str(e)], "methodology": {},
                            "section_mm2": 0, "i_calc_a": 0, "i_allowable_a": 0,
                            "delta_u_pct": 0, "cb_rating_a": 0, "i_kz_1ph_a": 0,
                            "i_kz_3ph_a": 0, "k_temp": 1, "k_group": 1,
                            "cable_mark": "", "length_m": 0, "method": "", "phases": 3,
                            "ambient_temp_c": 30})
    docx_bytes = build_word_report(results)
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=cable_calc.docx"},
    )


@router.get("/methods")
def get_methods():
    from engine.tables import INSTALLATION_METHODS
    return INSTALLATION_METHODS


@router.get("/health")
def health():
    return {"status": "ok"}
