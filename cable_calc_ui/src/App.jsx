import React, { useState, useCallback } from 'react';
import './App.css';

const { useState: useStateReact } = React;

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// ── Константы ────────────────────────────────────────────────────────────────
const METHODS  = ['A1','A2','B1','B2','C','D1','D2','E','F','G'];
const SECTIONS = [1.5,2.5,4,6,10,16,25,35,50,70,95,120,150,185,240,300,400,500,630];
const METHOD_DESC = {
  'A1':'В трубе в теплоизол. стене','A2':'В трубе в стене','B1':'В трубе открыто',
  'B2':'В трубе в стене','C':'Открыто на стене/лотке','D1':'В земле в трубе',
  'D2':'В земле напрямую','E':'В воздухе многожильный','F':'В воздухе одножильные',
  'G':'В воздухе параллельные'
};

// ── Компонент: поле формы ────────────────────────────────────────────────────
function Field({label, children, tip}) {
  return (
    <div className="flex flex-col gap-0.5">
      <label className="text-xs font-medium text-gray-600">{label}</label>
      {children}
      {tip && <span className="text-xs text-gray-400">{tip}</span>}
    </div>
  );
}

function Input({...p}) {
  return <input className="border rounded px-2 py-1 text-sm bg-white w-full" {...p}/>;
}

function Select({options, ...p}) {
  return (
    <select className="border rounded px-2 py-1 text-sm bg-white w-full" {...p}>
      {options.map(([v,l])=><option key={v} value={v}>{l}</option>)}
    </select>
  );
}

// ── Компонент: карточка результата ───────────────────────────────────────────
function ResultCard({r}) {
  const [showMethod, setShowMethod] = useState(false);
  const cls = r.status==='OK' ? 'status-ok' : r.status==='ERROR' ? 'status-error' : 'status-warn';
  return (
    <div className="rounded-lg border shadow-sm overflow-hidden">
      <div className={`flex items-center gap-4 px-4 py-2 ${cls} font-semibold text-sm`}>
        <span className="text-base">{r.status==='OK'?'✓':'✗'} {r.status}</span>
        <span>{r.line_id || 'Кабель'}</span>
        <span className="ml-auto">{r.section_mm2} мм²</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 px-4 py-3 bg-white text-sm">
        {[
          ['Iр', r.i_calc_a?.toFixed(1)+' А'],
          ['Iдоп', r.i_allowable_a?.toFixed(1)+' А'],
          ['ΔU', r.delta_u_pct?.toFixed(2)+'%'],
          ['АВ', r.cb_rating_a+' А'],
          ['IКЗ1ф', r.i_kz_1ph_a?.toFixed(0)+' А'],
          ['IКЗ3ф', r.i_kz_3ph_a?.toFixed(0)+' А'],
          ['k_t', r.k_temp?.toFixed(3)],
          ['k_гр', r.k_group?.toFixed(3)],
        ].map(([lbl,val])=>(
          <div key={lbl} className="flex justify-between border-b pb-1">
            <span className="text-gray-500">{lbl}</span>
            <span className="font-mono font-medium">{val}</span>
          </div>
        ))}
      </div>
      <div className="flex gap-3 px-4 py-2 bg-gray-50 text-xs">
        {[['Ток',r.check_current],['Напряжение',r.check_voltage],['КЗ',r.check_kz]].map(([n,ok])=>(
          <span key={n} className={`px-2 py-0.5 rounded-full font-medium ${ok?'bg-green-100 text-green-700':'bg-red-100 text-red-700'}`}>
            {ok?'✓':'✗'} {n}
          </span>
        ))}
      </div>
      {r.hints?.length>0 && (
        <div className="px-4 py-2 bg-white border-t">
          <div className="text-xs font-semibold text-red-600 mb-1">Рекомендации:</div>
          {r.hints.map((h,i)=><div key={i} className="hint-item text-xs">{h}</div>)}
        </div>
      )}
      {r.methodology && Object.keys(r.methodology).length > 0 && (
        <details className="border-t bg-gray-50">
          <summary className="px-4 py-2 text-xs font-medium text-blue-600 hover:bg-blue-50">📐 Методология расчёта</summary>
          <div className="px-4 pb-3">
            <table className="w-full text-xs border-collapse">
              <tbody>
                {Object.entries(r.methodology).map(([k,v])=>(
                  <tr key={k} className="method-row border-b">
                    <td className="py-1 pr-3 text-gray-500 whitespace-nowrap w-1/3 font-medium">{k}</td>
                    <td className="py-1 font-mono text-gray-800 break-all">{String(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  );
}

// ── Вкладка: Калькулятор ─────────────────────────────────────────────────────
function CalcTab() {
  const [mode, setMode] = useState('select');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    line_id:'', phases:3, power_kw:100, cos_phi:0.85,
    length_m:50, delta_u_pct_max:5, material:'Cu', insulation:'PVC',
    method:'C', cables_nearby:1, ambient_temp_c:30,
    section_mm2:70, soil_resistivity:2.5,
    start_current_ratio:1,
    z_t_mohm:54, r_t_mohm:16.8, x_t_mohm:51.32, u_nom_v:380,
  });

  const set = (k,v) => setForm(f=>({...f,[k]:v}));

  const buildPayload = () => ({
    line_id: form.line_id,
    phases: +form.phases,
    power_kw: form.power_kw ? +form.power_kw : null,
    cos_phi: +form.cos_phi,
    length_m: +form.length_m,
    delta_u_pct_max: +form.delta_u_pct_max,
    material: form.material,
    insulation: form.insulation,
    method: form.method,
    cables_nearby: +form.cables_nearby,
    ambient_temp_c: +form.ambient_temp_c,
    section_mm2: (mode !== 'select') ? +form.section_mm2 : null,
    soil_resistivity: +form.soil_resistivity,
    start_current_ratio: +form.start_current_ratio,
    source: {
      z_t_mohm: +form.z_t_mohm, r_t_mohm: +form.r_t_mohm,
      x_t_mohm: +form.x_t_mohm, u_nom_v: +form.u_nom_v,
    },
  });

  const endpoints = {select:'calculate/single', check:'calculate/check', max_load:'calculate/max_load'};

  const calculate = async () => {
    setLoading(true); setError(''); setResult(null);
    try {
      const res = await fetch(`${"${API}"}/${"${endpoints[mode]}"}`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(buildPayload()),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Ошибка сервера');
      setResult(data);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const modeLabels = {select:'Подбор сечения', check:'Проверка сечения', max_load:'Макс. нагрузка'};

  return (
    <div className="space-y-4">
      <div className="flex gap-2 flex-wrap">
        {Object.entries(modeLabels).map(([k,l])=>(
          <button key={k} onClick={()=>setMode(k)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${mode===k?'bg-blue-600 text-white shadow':'bg-white text-gray-700 border hover:bg-blue-50'}`}>
            {l}
          </button>
        ))}
      </div>
      <div className="bg-white rounded-xl border shadow-sm p-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          <Field label="ID"><Input value={form.line_id} onChange={e=>set('line_id',e.target.value)}/></Field>
          <Field label="Фазы"><Select value={form.phases} onChange={e=>set('phases',e.target.value)} options={[[1,'1ф'],[3,'3ф']]}/></Field>
          {mode !== 'max_load' && <Field label="Мощность, кВт"><Input type="number" value={form.power_kw} onChange={e=>set('power_kw',e.target.value)}/></Field>}
          <Field label="cos φ"><Input type="number" step="0.01" min="0.5" max="1" value={form.cos_phi} onChange={e=>set('cos_phi',e.target.value)}/></Field>
          {mode !== 'max_load' && <Field label="Длина, м"><Input type="number" value={form.length_m} onChange={e=>set('length_m',e.target.value)}/></Field>}
          {mode !== 'select' && <Field label="Сечение, мм²"><Select value={form.section_mm2} onChange={e=>set('section_mm2',e.target.value)} options={SECTIONS.map(s=>[s,s+' мм²'])}/></Field>}
          <Field label="Материал"><Select value={form.material} onChange={e=>set('material',e.target.value)} options={[['Cu','Cu (медь)'],['Al','Al (алюминий)']]}/></Field>
          <Field label="Изоляция"><Select value={form.insulation} onChange={e=>set('insulation',e.target.value)} options={[['PVC','ПВХ (PVC)'],['XLPE','XLPE (ПЭ)']]}/></Field>
          <Field label="Метод прокладки"><Select value={form.method} onChange={e=>set('method',e.target.value)} options={METHODS.map(m=>[m,m])}/></Field>
        </div>
        <button onClick={calculate} disabled={loading} className="mt-4 w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold py-2 rounded-lg text-sm">
          {loading ? '⏳ Расчёт...' : '▶ Рассчитать'}
        </button>
      </div>
      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">{error}</div>}
      {result && <ResultCard r={result}/>}
    </div>
  );
}

function JournalTab() {
  const [parsed, setParsed] = useState([]);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [mode, setMode] = useState('select');

  const uploadFile = async (file) => {
    setLoading(true); setError(''); setParsed([]); setResults([]);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await fetch(`${"${API}"}/parse/journal`, {method:'POST', body:fd});
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || 'Ошибка парсинга');
      setParsed(data);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const calcBatch = async () => {
    const cables = parsed.map(r=>({line_id: r.cable_id, phases: r.phases||3, power_kw: null, cos_phi: 0.85, length_m: r.length_m||50, material: 'Cu', insulation: 'PVC', method: 'C', cables_nearby: 1, ambient_temp_c: 30, section_mm2: mode!=='select' ? (r.section_mm2||null) : null}));
    try {
      const r = await fetch(`${"${API}"}/calculate/batch`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({mode, cables})});
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || 'Ошибка расчёта');
      setResults(data);
    } catch(e) { setError(e.message); }
  };

  return (
    <div className="space-y-4">
      <div onDragOver={e=>{e.preventDefault();setDragOver(true)}} onDragLeave={()=>setDragOver(false)} onDrop={e=>{e.preventDefault();setDragOver(false);uploadFile(e.dataTransfer.files[0])}} className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer ${dragOver?'border-blue-400 bg-blue-50':'border-gray-300 bg-white'}`}>
        <input id="jfile" type="file" accept=".pdf,.xlsx,.docx" className="hidden" onChange={e=>e.target.files[0]&&uploadFile(e.target.files[0])}/>
        <p className="text-3xl mb-2" onClick={()=>document.getElementById('jfile').click()}>📂</p>
      </div>
      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">{error}</div>}
      {parsed.length > 0 && <button onClick={calcBatch} className="bg-blue-600 text-white px-4 py-2 rounded">▶ Рассчитать</button>}
      {results.length > 0 && <div>Результаты: {results.length} ({results.filter(r=>r.status==='OK').length} OK)</div>}
    </div>
  );
}

function MethodTab() {
  return <div className="bg-blue-50 p-4 rounded">Методология МЭК 60364-5-52</div>;
}

function App() {
  const [tab, setTab] = useState('calc');
  return (
    <div className="min-h-screen">
      <header className="bg-gradient-to-r from-blue-900 to-blue-700 text-white px-4 py-3">
        <h1 className="font-bold text-lg">⚡ Расчёт кабелей до 1кВ</h1>
      </header>
      <div className="bg-white border-b">
        <div className="max-w-6xl mx-auto flex">
          <button onClick={()=>setTab('calc')} className={tab==='calc'?'tab-active px-5 py-3':'px-5 py-3'}>🔧 Калькулятор</button>
          <button onClick={()=>setTab('journal')} className={tab==='journal'?'tab-active px-5 py-3':'px-5 py-3'}>📋 Журнал</button>
          <button onClick={()=>setTab('method')} className={tab==='method'?'tab-active px-5 py-3':'px-5 py-3'}>📐 Методология</button>
        </div>
      </div>
      <main className="max-w-6xl mx-auto px-4 py-6">
        {tab==='calc' && <CalcTab/>}
        {tab==='journal' && <JournalTab/>}
        {tab==='method' && <MethodTab/>}
      </main>
    </div>
  );
}

export default App;
