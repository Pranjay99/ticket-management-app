import { useEffect, useRef, useState } from 'react'
import { Upload as UploadIcon, FileText, CheckCircle, AlertTriangle, X, Download } from 'lucide-react'
import * as api from '../api/client.js'
import Spinner from '../components/Spinner.jsx'

function downloadSample() {
  const a = Object.assign(document.createElement('a'), {
    href: api.getSampleCSVUrl(),
    download: 'sample_1000_tickets.csv',
  })
  a.click()
}

export default function Upload() {
  const [summary, setSummary]       = useState(null)
  const [file, setFile]             = useState(null)
  const [uploading, setUploading]   = useState(false)
  const [result, setResult]         = useState(null)
  const [pollStatus, setPollStatus] = useState(null)
  const [error, setError]           = useState(null)
  const [dragging, setDragging]     = useState(false)
  const inputRef = useRef(null)
  const pollRef  = useRef(null)

  useEffect(() => {
    api.getSummary().then(setSummary).catch(() => {})
    return () => clearInterval(pollRef.current)
  }, [])

  const handleFile = (f) => {
    if (!f || !f.name.endsWith('.csv')) { setError('Please select a CSV file'); return }
    setFile(f); setResult(null); setPollStatus(null); setError(null)
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true); setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const r = await api.uploadCSV(fd)
      setResult(r)
      let count = 0
      pollRef.current = setInterval(async () => {
        count++
        try {
          const sd = await api.getTaskStatus(r.task_id)
          setPollStatus(sd)
          if (sd.status === 'SUCCESS' || sd.status === 'FAILURE' || count >= 60) clearInterval(pollRef.current)
        } catch { clearInterval(pollRef.current) }
      }, 3000)
    } catch (e) { setError(String(e))
    } finally { setUploading(false) }
  }

  const progressVal = !pollStatus ? 0
    : pollStatus.status === 'SUCCESS' ? 100
    : Math.min(90, 5 + Math.floor(((pollStatus._poll ?? 1) / 60) * 85))

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900">Upload Tickets</h1>
        <p className="text-sm text-slate-500">Ingest a CSV of support tickets into the AI processing pipeline</p>
      </div>

      {/* DB stats */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            ['Total Tickets',   summary.total_tickets?.toLocaleString(),           'bg-brand-50 text-brand-700'],
            ['Open',            summary.open_tickets?.toLocaleString(),            'bg-amber-50 text-amber-700'],
            ['Resolved',        summary.resolved_tickets?.toLocaleString(),        'bg-emerald-50 text-emerald-700'],
            ['Processed Today', summary.tickets_processed_today?.toLocaleString(), 'bg-violet-50 text-violet-700'],
          ].map(([label, val, cls]) => (
            <div key={label} className={`card ${cls} p-3 sm:p-5`}>
              <p className="text-xs font-semibold uppercase tracking-wide opacity-70">{label}</p>
              <p className="text-xl sm:text-2xl font-extrabold mt-0.5">{val ?? '—'}</p>
            </div>
          ))}
        </div>
      )}

      {/* CSV Schema reference */}
      <details className="card cursor-pointer">
        <summary className="text-sm font-semibold text-slate-700 select-none">
          Required CSV format
        </summary>
        <div className="mt-3 overflow-x-auto -mx-4 sm:mx-0">
          <table className="min-w-full text-xs">
            <thead>
              <tr className="bg-brand-50">
                {['Column','Required','Format','Notes'].map(h => (
                  <th key={h} className="text-left px-3 py-2 font-semibold text-brand-700 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {[
                ['ticket_id','No','UUID string','Auto-generated if missing'],
                ['timestamp','Yes','YYYY-MM-DD HH:MM:SS',''],
                ['customer_id','Yes','string',''],
                ['channel','Yes','chat / email / web',''],
                ['message','Yes','text',"Customer's message"],
                ['agent_reply','No','text','Existing agent reply'],
                ['product','No','string','Product name'],
                ['order_value','No','numeric','Order value in USD'],
                ['customer_country','No','string','Country name'],
                ['resolution_status','No','open / resolved / escalated','Defaults to open'],
              ].map(([col, req, fmt, notes]) => (
                <tr key={col} className="hover:bg-slate-50">
                  <td className="px-3 py-1.5 font-mono text-brand-600 whitespace-nowrap">{col}</td>
                  <td className="px-3 py-1.5">{req === 'Yes'
                    ? <span className="text-emerald-600 font-semibold">Yes</span>
                    : <span className="text-slate-400">No</span>}</td>
                  <td className="px-3 py-1.5 text-slate-600 whitespace-nowrap">{fmt}</td>
                  <td className="px-3 py-1.5 text-slate-400">{notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button onClick={downloadSample} className="mt-3 btn-secondary text-xs">
          ⬇ Download 2-row sample
        </button>
      </details>

      {/* Download 1000-row dataset */}
      <div className="card flex flex-col sm:flex-row sm:items-center gap-4 bg-brand-50 border border-brand-200">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-brand-800 text-sm">Need data to explore the app?</p>
          <p className="text-xs text-brand-600 mt-0.5">
            Download the built-in 1,000-row sample dataset and upload it to populate all dashboards instantly.
          </p>
        </div>
        <button
          onClick={downloadSample}
          className="btn-primary flex items-center gap-2 shrink-0 text-sm px-4 py-2"
        >
          <Download size={15} />
          Download 1,000-row CSV
        </button>
      </div>

      {/* Drop zone */}
      <div
        className={`border-2 border-dashed rounded-2xl px-6 py-10 sm:p-10 text-center cursor-pointer transition-colors
          ${dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 hover:border-brand-400 hover:bg-brand-50/40'}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]) }}
      >
        <input ref={inputRef} type="file" accept=".csv" className="hidden"
          onChange={e => handleFile(e.target.files[0])} />
        <UploadIcon size={34} className="mx-auto text-brand-400 mb-3" />
        <p className="font-semibold text-slate-700 text-sm sm:text-base">
          {file ? file.name : 'Drop your CSV here or tap to browse'}
        </p>
        <p className="text-xs text-slate-400 mt-1">Max 50 MB · UTF-8 or Latin-1 encoding</p>
      </div>

      {file && !result && (
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 flex-1 min-w-0 bg-brand-50 rounded-xl px-4 py-2">
            <FileText size={15} className="text-brand-500 shrink-0" />
            <span className="text-sm font-medium text-brand-700 truncate">{file.name}</span>
            <span className="text-xs text-slate-400 ml-auto shrink-0">{(file.size / 1024).toFixed(1)} KB</span>
          </div>
          <button onClick={() => setFile(null)} className="text-slate-400 hover:text-slate-600 shrink-0">
            <X size={16} />
          </button>
          <button onClick={handleUpload} disabled={uploading}
            className="btn-primary flex items-center gap-2 px-5 shrink-0 w-full sm:w-auto justify-center">
            {uploading
              ? <><div className="w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" /> Uploading…</>
              : '🚀 Start Processing'}
          </button>
        </div>
      )}

      {error && (
        <div className="card border-l-4 border-rose-500 bg-rose-50 text-rose-700 flex gap-2 items-start">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {result && (
        <div className="card space-y-3">
          <div className="flex items-center gap-2 text-emerald-600 flex-wrap">
            <CheckCircle size={18} className="shrink-0" />
            <span className="font-semibold text-sm">{result.message}</span>
          </div>
          <p className="text-sm text-slate-500">
            Task ID: <code className="bg-slate-100 px-1.5 py-0.5 rounded text-xs">{result.task_id}</code>
            &nbsp;·&nbsp; Rows queued: <strong>{result.total_rows?.toLocaleString()}</strong>
          </p>
          {pollStatus && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>Pipeline: <strong>{pollStatus.status}</strong></span>
                <span>{progressVal}%</span>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-brand-500 rounded-full transition-all duration-500"
                  style={{ width: `${progressVal}%` }} />
              </div>
              {pollStatus.status === 'SUCCESS' && (
                <p className="text-sm text-emerald-600 font-semibold">
                  ✅ Pipeline complete! Processed {pollStatus.result?.processed ?? '?'} tickets.
                </p>
              )}
              {pollStatus.status === 'FAILURE' && (
                <p className="text-sm text-rose-600">Pipeline failed: {pollStatus.error ?? 'Unknown error'}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
