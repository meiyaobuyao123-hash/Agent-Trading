"use client"

import { useState } from "react"
import { ChevronLeft, ChevronRight, Calendar } from "lucide-react"

interface DatePickerProps {
  dates: string[]
  selectedDate: string
  onDateChange: (date: string) => void
  label?: string
}

export function DatePicker({ dates, selectedDate, onDateChange, label = "日期" }: DatePickerProps) {
  const [open, setOpen] = useState(false)
  const currentIndex = dates.indexOf(selectedDate)

  const handlePrev = () => {
    if (currentIndex < dates.length - 1) {
      onDateChange(dates[currentIndex + 1])
    }
  }

  const handleNext = () => {
    if (currentIndex > 0) {
      onDateChange(dates[currentIndex - 1])
    }
  }

  return (
    <div className="flex items-center gap-1 relative">
      <button
        onClick={handlePrev}
        disabled={currentIndex >= dates.length - 1}
        className="p-1.5 rounded-lg transition-all hover:opacity-80 disabled:opacity-30"
        style={{ background: 'var(--bg-card)', color: 'var(--text-dim)', border: '1px solid var(--border)' }}
      >
        <ChevronLeft size={14} />
      </button>

      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80"
        style={{ background: 'var(--bg-card)', color: 'var(--text)', border: '1px solid var(--border)' }}
      >
        <Calendar size={12} />
        {selectedDate || label}
      </button>

      <button
        onClick={handleNext}
        disabled={currentIndex <= 0}
        className="p-1.5 rounded-lg transition-all hover:opacity-80 disabled:opacity-30"
        style={{ background: 'var(--bg-card)', color: 'var(--text-dim)', border: '1px solid var(--border)' }}
      >
        <ChevronRight size={14} />
      </button>

      {open && dates.length > 0 && (
        <div
          className="absolute top-10 right-0 z-50 rounded-xl border shadow-xl py-1 max-h-60 overflow-y-auto"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', minWidth: 160 }}
        >
          {dates.map((d) => (
            <button
              key={d}
              onClick={() => { onDateChange(d); setOpen(false) }}
              className="w-full text-left px-3 py-2 text-xs hover:bg-white/[0.05] transition-colors"
              style={{
                color: d === selectedDate ? 'var(--blue)' : 'var(--text)',
                fontWeight: d === selectedDate ? 700 : 400,
              }}
            >
              {d}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
