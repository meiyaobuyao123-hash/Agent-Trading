"use client"

import { ChevronLeft, ChevronRight, Calendar } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

interface DatePickerProps {
  dates: string[]
  selectedDate: string
  onDateChange: (date: string) => void
  label?: string
}

export function DatePicker({ dates, selectedDate, onDateChange, label = "日期" }: DatePickerProps) {
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
    <div className="flex items-center gap-2">
      <Button
        variant="ghost"
        size="icon"
        onClick={handlePrev}
        disabled={currentIndex >= dates.length - 1}
        className="h-8 w-8"
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="gap-2">
            <Calendar className="h-4 w-4" />
            {selectedDate || label}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="center" className="max-h-64 overflow-y-auto">
          {dates.map((d) => (
            <DropdownMenuItem
              key={d}
              onClick={() => onDateChange(d)}
              className={d === selectedDate ? "bg-accent" : ""}
            >
              {d}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <Button
        variant="ghost"
        size="icon"
        onClick={handleNext}
        disabled={currentIndex <= 0}
        className="h-8 w-8"
      >
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  )
}
