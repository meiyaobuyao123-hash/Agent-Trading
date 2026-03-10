'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Plus,
  Trash2,
  Sparkles,
  Loader2,
  CheckCircle,
  AlertCircle,
  ChevronLeft,
  Code2,
  Save,
  Zap,
} from 'lucide-react'
import Link from 'next/link'

// ── Types ─────────────────────────────────────────────────────────────────────
type ConditionField = 'direction' | 'confidence_score' | 'chain_id' | 'risk_level'
type ConditionOp = 'eq' | 'gte' | 'lte' | 'in'

interface Condition {
  field: ConditionField
  op: ConditionOp
  value: string | number | string[]
}

interface ExecConfig {
  amount_usd: number
  slippage: number
  stop_loss_pct: number
  take_profit_pct: number
  max_gas_usd: number
}

// ── Config ────────────────────────────────────────────────────────────────────
const FIELDS: { value: ConditionField; label: string; ops: ConditionOp[] }[] = [
  { value: 'direction',        label: '信号方向',   ops: ['eq'] },
  { value: 'confidence_score', label: '信心分',     ops: ['gte', 'lte'] },
  { value: 'chain_id',         label: '目标链',     ops: ['in'] },
  { value: 'risk_level',       label: '风险等级',   ops: ['eq'] },
]
const OP_LABELS: Record<ConditionOp, string> = { eq: '等于 (=)', gte: '大于等于 (≥)', lte: '小于等于 (≤)', in: '包含 (∈)' }
const DIRECTION_OPTIONS = [
  { value: 'long',  label: '做多 📈', color: 'var(--green)' },
  { value: 'watch', label: '观察 👀', color: 'var(--yellow)' },
  { value: 'exit',  label: '退出 📉', color: 'var(--red)' },
]
const RISK_OPTIONS = [
  { value: 'low',    label: '低风险 🟢' },
  { value: 'medium', label: '中风险 🟡' },
  { value: 'high',   label: '高风险 🔴' },
]
const CHAIN_OPTIONS = [
  { value: '56',      label: 'BSC', color: '#F0B90B' },
  { value: '1',       label: 'ETH', color: '#627EEA' },
  { value: '900',     label: 'SOL', color: '#9945FF' },
]

function defaultCondition(): Condition {
  return { field: 'direction', op: 'eq', value: 'long' }
}

// ── Condition Row ─────────────────────────────────────────────────────────────
function ConditionRow({
  condition,
  index,
  onChange,
  onRemove,
  canRemove,
}: {
  condition: Condition
  index: number
  onChange: (c: Condition) => void
  onRemove: () => void
  canRemove: boolean
}) {
  const fieldCfg = FIELDS.find((f) => f.value === condition.field)!

  const handleFieldChange = (field: ConditionField) => {
    const cfg = FIELDS.find((f) => f.value === field)!
    const defaultOp = cfg.ops[0]
    let defaultValue: string | number | string[] = ''
    if (field === 'direction') defaultValue = 'long'
    else if (field === 'confidence_score') defaultValue = 70
    else if (field === 'chain_id') defaultValue = ['56']
    else if (field === 'risk_level') defaultValue = 'low'
    onChange({ field, op: defaultOp, value: defaultValue })
  }

  const inputStyle = {
    background: 'var(--bg-card2)',
    border: '1px solid var(--border)',
    color: 'var(--text)',
    borderRadius: '8px',
    padding: '6px 10px',
    fontSize: '13px',
    outline: 'none',
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span
        className="text-xs font-mono w-5 text-right shrink-0"
        style={{ color: 'var(--text-dim)' }}
      >
        {index + 1}
      </span>

      {/* Field */}
      <select
        value={condition.field}
        onChange={(e) => handleFieldChange(e.target.value as ConditionField)}
        style={inputStyle}
        className="w-32"
      >
        {FIELDS.map((f) => (
          <option key={f.value} value={f.value}>
            {f.label}
          </option>
        ))}
      </select>

      {/* Operator */}
      <select
        value={condition.op}
        onChange={(e) => onChange({ ...condition, op: e.target.value as ConditionOp })}
        style={inputStyle}
        className="w-36"
      >
        {fieldCfg.ops.map((op) => (
          <option key={op} value={op}>
            {OP_LABELS[op]}
          </option>
        ))}
      </select>

      {/* Value */}
      {condition.field === 'direction' && (
        <select
          value={condition.value as string}
          onChange={(e) => onChange({ ...condition, value: e.target.value })}
          style={inputStyle}
          className="w-32"
        >
          {DIRECTION_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      )}
      {condition.field === 'confidence_score' && (
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={0}
            max={100}
            value={condition.value as number}
            onChange={(e) => onChange({ ...condition, value: Number(e.target.value) })}
            style={{ ...inputStyle, width: '80px' }}
          />
          <span className="text-xs" style={{ color: 'var(--text-dim)' }}>/ 100</span>
          <div
            className="flex-1 h-1.5 rounded-full overflow-hidden"
            style={{ background: 'var(--border)', minWidth: 60 }}
          >
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${condition.value}%`,
                background: (condition.value as number) >= 80
                  ? 'var(--green)' : (condition.value as number) >= 60
                  ? 'var(--yellow)' : 'var(--red)',
              }}
            />
          </div>
        </div>
      )}
      {condition.field === 'chain_id' && (
        <div className="flex gap-1.5 flex-wrap">
          {CHAIN_OPTIONS.map((o) => {
            const selected = Array.isArray(condition.value) && (condition.value as string[]).includes(o.value)
            return (
              <button
                key={o.value}
                onClick={() => {
                  const cur = Array.isArray(condition.value) ? (condition.value as string[]) : []
                  const next = selected ? cur.filter((v) => v !== o.value) : [...cur, o.value]
                  onChange({ ...condition, value: next })
                }}
                className="px-2.5 py-1 rounded-lg text-xs font-semibold transition-all"
                style={{
                  background: selected ? `${o.color}22` : 'var(--bg-card2)',
                  color: selected ? o.color : 'var(--text-dim)',
                  border: `1px solid ${selected ? o.color + '55' : 'var(--border)'}`,
                }}
              >
                {o.label}
              </button>
            )
          })}
        </div>
      )}
      {condition.field === 'risk_level' && (
        <select
          value={condition.value as string}
          onChange={(e) => onChange({ ...condition, value: e.target.value })}
          style={inputStyle}
          className="w-32"
        >
          {RISK_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      )}

      {canRemove && (
        <button
          onClick={onRemove}
          className="p-1.5 rounded-lg ml-1"
          style={{ background: 'rgba(246,70,93,0.1)', color: 'var(--red)' }}
        >
          <Trash2 size={13} />
        </button>
      )}
    </div>
  )
}

// ── Slider Row ────────────────────────────────────────────────────────────────
function SliderRow({
  label, value, min, max, step = 1, unit = '', color,
  onChange,
}: {
  label: string; value: number; min: number; max: number; step?: number; unit?: string; color: string
  onChange: (v: number) => void
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="text-xs w-24 shrink-0" style={{ color: 'var(--text-dim)' }}>{label}</div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1 h-1.5 appearance-none rounded-full"
        style={{ accentColor: color, cursor: 'pointer' }}
      />
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="text-right text-xs font-mono font-bold w-16 rounded-lg px-2 py-1"
        style={{
          background: 'var(--bg-card2)',
          border: '1px solid var(--border)',
          color,
          outline: 'none',
        }}
      />
      <span className="text-xs shrink-0 w-4" style={{ color: 'var(--text-dim)' }}>{unit}</span>
    </div>
  )
}

// ── Section Card ──────────────────────────────────────────────────────────────
function SectionCard({ title, children, badge }: { title: string; children: React.ReactNode; badge?: string }) {
  return (
    <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      <div
        className="flex items-center justify-between px-5 py-3.5"
        style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-card2)' }}
      >
        <span className="text-sm font-bold" style={{ color: 'var(--text)' }}>{title}</span>
        {badge && (
          <span className="text-xs px-2 py-0.5 rounded font-medium" style={{ background: 'rgba(240,185,11,0.1)', color: 'var(--yellow)' }}>
            {badge}
          </span>
        )}
      </div>
      <div className="p-5">{children}</div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function CreateStrategyPage() {
  const router = useRouter()

  const [name, setName] = useState('')
  const [conditions, setConditions] = useState<Condition[]>([defaultCondition()])
  const [logic, setLogic] = useState<'AND' | 'OR'>('AND')
  const [execConfig, setExecConfig] = useState<ExecConfig>({
    amount_usd: 100,
    slippage: 0.5,
    stop_loss_pct: 10,
    take_profit_pct: 30,
    max_gas_usd: 5,
  })

  const [generatedScript, setGeneratedScript] = useState<string | null>(null)
  const [scriptSource, setScriptSource] = useState<string>('')
  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState<string | null>(null)

  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const updateCondition = (i: number, c: Condition) => {
    setConditions((prev) => prev.map((x, idx) => idx === i ? c : x))
  }
  const removeCondition = (i: number) => {
    setConditions((prev) => prev.filter((_, idx) => idx !== i))
  }
  const addCondition = () => {
    setConditions((prev) => [...prev, defaultCondition()])
  }

  const handleGenerate = async () => {
    if (!name.trim()) { setGenError('请先填写策略名称'); return }
    if (conditions.length === 0) { setGenError('请至少添加一个触发条件'); return }

    setGenerating(true)
    setGenError(null)
    setGeneratedScript(null)

    try {
      const res = await fetch('/api/strategies/temp/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          conditionTree: { conditions, logic },
          execConfig,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`)
      setGeneratedScript(data.script)
      setScriptSource(data.source ?? '')
    } catch (err) {
      setGenError(err instanceof Error ? err.message : '生成失败')
    } finally {
      setGenerating(false)
    }
  }

  const handleSave = async (status: 'draft' | 'active') => {
    if (!name.trim()) { setSaveError('请先填写策略名称'); return }
    if (conditions.length === 0) { setSaveError('请至少添加一个触发条件'); return }

    setSaving(true)
    setSaveError(null)

    try {
      const res = await fetch('/api/strategies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          condition_tree: { conditions, logic },
          exec_config: execConfig,
          generated_script: generatedScript ?? null,
          status,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`)
      setSaved(true)
      setTimeout(() => router.push('/strategy'), 1000)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  // Validation
  const isValid = name.trim().length > 0 && conditions.length > 0

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      {/* Topbar */}
      <div
        className="flex items-center justify-between px-6 py-4 sticky top-0 z-10"
        style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-3">
          <Link
            href="/strategy"
            className="p-2 rounded-lg transition-colors"
            style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
          >
            <ChevronLeft size={16} />
          </Link>
          <div>
            <div className="text-sm font-bold" style={{ color: 'var(--text)' }}>创建策略</div>
            <div className="text-xs" style={{ color: 'var(--text-dim)' }}>定义触发条件 · AI 生成脚本 · 自动执行</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleSave('draft')}
            disabled={saving || !isValid}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold"
            style={{
              background: 'var(--bg-card2)',
              color: isValid ? 'var(--text)' : 'var(--text-dim)',
              border: '1px solid var(--border)',
              opacity: saving || !isValid ? 0.6 : 1,
              cursor: saving || !isValid ? 'not-allowed' : 'pointer',
            }}
          >
            {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
            存为草稿
          </button>
          <button
            onClick={() => handleSave('active')}
            disabled={saving || !isValid}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
            style={{
              background: isValid ? 'var(--green)' : 'var(--bg-card2)',
              color: isValid ? '#000' : 'var(--text-dim)',
              opacity: saving || !isValid ? 0.6 : 1,
              cursor: saving || !isValid ? 'not-allowed' : 'pointer',
            }}
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : saved ? <CheckCircle size={14} /> : <Zap size={14} />}
            {saved ? '已保存！' : '保存并启用'}
          </button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 py-6 space-y-5">

        {/* Save error */}
        {saveError && (
          <div
            className="rounded-xl border px-4 py-3 flex items-center gap-2 text-xs"
            style={{ background: 'rgba(246,70,93,0.08)', borderColor: 'rgba(246,70,93,0.3)', color: 'var(--red)' }}
          >
            <AlertCircle size={13} />
            {saveError}
          </div>
        )}

        {/* 1. 策略名称 */}
        <SectionCard title="基本信息">
          <div className="space-y-2">
            <label className="text-xs" style={{ color: 'var(--text-dim)' }}>策略名称 *</label>
            <input
              type="text"
              placeholder="例如：聪明钱跟单 BSC 高信心"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-3 rounded-xl text-sm"
              style={{
                background: 'var(--bg-card2)',
                border: `1px solid ${name.trim() ? 'var(--yellow)' : 'var(--border)'}`,
                color: 'var(--text)',
                outline: 'none',
                transition: 'border-color 0.2s',
              }}
            />
          </div>
        </SectionCard>

        {/* 2. 触发条件 */}
        <SectionCard title="触发条件" badge={`${conditions.length} 条 · ${logic}`}>
          <div className="space-y-4">
            {/* Logic toggle */}
            <div className="flex items-center gap-3">
              <span className="text-xs" style={{ color: 'var(--text-dim)' }}>条件逻辑：</span>
              {(['AND', 'OR'] as const).map((l) => (
                <button
                  key={l}
                  onClick={() => setLogic(l)}
                  className="px-3 py-1 rounded-lg text-xs font-bold transition-all"
                  style={{
                    background: logic === l ? 'rgba(114,137,218,0.2)' : 'var(--bg-card2)',
                    color: logic === l ? '#7289da' : 'var(--text-dim)',
                    border: `1px solid ${logic === l ? 'rgba(114,137,218,0.4)' : 'var(--border)'}`,
                  }}
                >
                  {l} <span className="font-normal opacity-70">{l === 'AND' ? '（全部满足）' : '（任一满足）'}</span>
                </button>
              ))}
            </div>

            {/* Condition rows */}
            <div className="space-y-3 pl-2 border-l-2" style={{ borderColor: 'var(--border)' }}>
              {conditions.map((c, i) => (
                <ConditionRow
                  key={i}
                  condition={c}
                  index={i}
                  onChange={(updated) => updateCondition(i, updated)}
                  onRemove={() => removeCondition(i)}
                  canRemove={conditions.length > 1}
                />
              ))}
            </div>

            <button
              onClick={addCondition}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              style={{
                background: 'rgba(240,185,11,0.08)',
                color: 'var(--yellow)',
                border: '1px dashed rgba(240,185,11,0.3)',
              }}
            >
              <Plus size={12} />
              添加条件
            </button>
          </div>
        </SectionCard>

        {/* 3. 执行配置 */}
        <SectionCard title="执行配置">
          <div className="space-y-4">
            <SliderRow
              label="单次金额"
              value={execConfig.amount_usd}
              min={10}
              max={10000}
              step={10}
              unit="$"
              color="var(--yellow)"
              onChange={(v) => setExecConfig((c) => ({ ...c, amount_usd: v }))}
            />
            <SliderRow
              label="止损"
              value={execConfig.stop_loss_pct}
              min={1}
              max={50}
              step={0.5}
              unit="%"
              color="var(--red)"
              onChange={(v) => setExecConfig((c) => ({ ...c, stop_loss_pct: v }))}
            />
            <SliderRow
              label="止盈"
              value={execConfig.take_profit_pct}
              min={5}
              max={200}
              step={1}
              unit="%"
              color="var(--green)"
              onChange={(v) => setExecConfig((c) => ({ ...c, take_profit_pct: v }))}
            />
            <SliderRow
              label="滑点容忍"
              value={execConfig.slippage}
              min={0.1}
              max={5}
              step={0.1}
              unit="%"
              color="var(--blue)"
              onChange={(v) => setExecConfig((c) => ({ ...c, slippage: v }))}
            />
            <SliderRow
              label="最大 Gas"
              value={execConfig.max_gas_usd}
              min={1}
              max={50}
              step={0.5}
              unit="$"
              color="var(--text-dim)"
              onChange={(v) => setExecConfig((c) => ({ ...c, max_gas_usd: v }))}
            />

            {/* Config summary */}
            <div
              className="flex flex-wrap gap-3 px-4 py-3 rounded-xl text-xs"
              style={{ background: 'var(--bg-card2)' }}
            >
              <span>💵 <strong style={{ color: 'var(--yellow)' }}>${execConfig.amount_usd}</strong> / 次</span>
              <span>📉 止损 <strong style={{ color: 'var(--red)' }}>{execConfig.stop_loss_pct}%</strong></span>
              <span>📈 止盈 <strong style={{ color: 'var(--green)' }}>{execConfig.take_profit_pct}%</strong></span>
              <span>⚡ 滑点 <strong style={{ color: 'var(--blue)' }}>{execConfig.slippage}%</strong></span>
              <span>⛽ Gas ≤ <strong style={{ color: 'var(--text-dim)' }}>${execConfig.max_gas_usd}</strong></span>
            </div>
          </div>
        </SectionCard>

        {/* 4. AI 脚本生成 */}
        <SectionCard title="AI 生成交易脚本" badge="Claude">
          <div className="space-y-4">
            <div className="text-xs leading-relaxed" style={{ color: 'var(--text-dim)' }}>
              Claude 将根据你设定的触发条件和执行配置，生成可直接部署的 TypeScript 策略代码。
              代码包含条件检测函数、OKX DEX 执行逻辑和日志输出。
            </div>

            {/* Gen error */}
            {genError && (
              <div
                className="rounded-lg border px-4 py-3 flex items-center gap-2 text-xs"
                style={{ background: 'rgba(246,70,93,0.08)', borderColor: 'rgba(246,70,93,0.3)', color: 'var(--red)' }}
              >
                <AlertCircle size={13} />
                {genError}
              </div>
            )}

            <button
              onClick={handleGenerate}
              disabled={generating || !isValid}
              className="flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold w-full justify-center transition-all"
              style={{
                background: isValid && !generating
                  ? 'linear-gradient(135deg, rgba(240,185,11,0.2), rgba(82,196,26,0.2))'
                  : 'var(--bg-card2)',
                color: isValid ? 'var(--text)' : 'var(--text-dim)',
                border: `1px solid ${isValid ? 'rgba(240,185,11,0.3)' : 'var(--border)'}`,
                opacity: !isValid ? 0.5 : 1,
                cursor: !isValid || generating ? 'not-allowed' : 'pointer',
              }}
            >
              {generating ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Claude 生成中…
                </>
              ) : generatedScript ? (
                <>
                  <Sparkles size={16} color="var(--yellow)" />
                  重新生成脚本
                </>
              ) : (
                <>
                  <Sparkles size={16} />
                  ✨ 让 Claude 生成交易脚本
                </>
              )}
            </button>

            {/* Generated script viewer */}
            {generatedScript && (
              <div
                className="rounded-xl overflow-hidden"
                style={{ border: '1px solid rgba(82,196,26,0.3)' }}
              >
                <div
                  className="flex items-center justify-between px-4 py-2.5"
                  style={{ background: 'rgba(82,196,26,0.08)', borderBottom: '1px solid rgba(82,196,26,0.2)' }}
                >
                  <div className="flex items-center gap-2">
                    <Code2 size={13} color="var(--green)" />
                    <span className="text-xs font-semibold" style={{ color: 'var(--green)' }}>
                      脚本已生成
                    </span>
                    {scriptSource === 'claude' && (
                      <span
                        className="text-xs px-1.5 py-0.5 rounded"
                        style={{ background: 'rgba(240,185,11,0.1)', color: 'var(--yellow)' }}
                      >
                        Claude claude-haiku-4-5
                      </span>
                    )}
                    {scriptSource === 'template' && (
                      <span
                        className="text-xs px-1.5 py-0.5 rounded"
                        style={{ background: 'rgba(100,100,100,0.1)', color: 'var(--text-dim)' }}
                      >
                        模板（未配置 API Key）
                      </span>
                    )}
                    {scriptSource === 'template_fallback' && (
                      <span
                        className="text-xs px-1.5 py-0.5 rounded"
                        style={{ background: 'rgba(246,70,93,0.1)', color: 'var(--red)' }}
                      >
                        API 失败 → 模板回退
                      </span>
                    )}
                  </div>
                  <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
                    {generatedScript.split('\n').length} 行
                  </span>
                </div>
                <pre
                  className="overflow-auto text-xs leading-relaxed p-4"
                  style={{
                    color: '#a8ff78',
                    background: '#0a0f0a',
                    fontFamily: 'monospace',
                    maxHeight: '360px',
                  }}
                >
                  {generatedScript}
                </pre>
              </div>
            )}
          </div>
        </SectionCard>

        {/* Save bottom */}
        <div className="flex gap-3 pb-8">
          <Link
            href="/strategy"
            className="flex-1 flex items-center justify-center py-3 rounded-xl text-sm font-semibold"
            style={{
              background: 'var(--bg-card)',
              color: 'var(--text-dim)',
              border: '1px solid var(--border)',
            }}
          >
            取消
          </Link>
          <button
            onClick={() => handleSave('draft')}
            disabled={saving || !isValid}
            className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold"
            style={{
              background: 'var(--bg-card)',
              color: isValid ? 'var(--text)' : 'var(--text-dim)',
              border: `1px solid ${isValid ? 'var(--border)' : 'var(--bg-card2)'}`,
              opacity: saving || !isValid ? 0.6 : 1,
            }}
          >
            <Save size={14} />
            存为草稿
          </button>
          <button
            onClick={() => handleSave('active')}
            disabled={saving || !isValid}
            className="flex-[2] flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold"
            style={{
              background: isValid ? 'var(--green)' : 'var(--bg-card2)',
              color: isValid ? '#000' : 'var(--text-dim)',
              opacity: saving || !isValid ? 0.6 : 1,
            }}
          >
            {saving ? (
              <Loader2 size={14} className="animate-spin" />
            ) : saved ? (
              <CheckCircle size={14} />
            ) : (
              <Zap size={14} />
            )}
            {saved ? '已保存，跳转中…' : '保存并启用策略'}
          </button>
        </div>
      </div>
    </div>
  )
}
