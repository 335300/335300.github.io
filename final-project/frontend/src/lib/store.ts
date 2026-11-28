import { create } from 'zustand';
import type { Tab } from './types';

/** UI state only — server data lives in TanStack Query. */
interface UiState {
  activeTab: Tab;
  selectedYear: number | null;
  selectedMonth: number;
  setTab: (tab: Tab) => void;
  setYear: (year: number) => void;
  setMonth: (month: number) => void;
  setPeriod: (year: number, month: number) => void;
  /** Forget the selection so App picks the newly opened profile's last position. */
  clearPeriod: () => void;
  /** The pocket calculator: kept here so it stays as it is when the tab changes. */
  calcOpen: boolean;
  calcText: string;
  setCalcOpen: (open: boolean) => void;
  setCalcText: (text: string) => void;
}

export const useUi = create<UiState>((set) => ({
  activeTab: 'overview',
  selectedYear: null,
  selectedMonth: 0,
  setTab: (activeTab) => set({ activeTab }),
  setYear: (selectedYear) => set({ selectedYear }),
  setMonth: (selectedMonth) => set({ selectedMonth }),
  setPeriod: (selectedYear, selectedMonth) => set({ selectedYear, selectedMonth }),
  clearPeriod: () => set({ selectedYear: null }),
  calcOpen: false,
  calcText: '',
  setCalcOpen: (calcOpen) => set({ calcOpen }),
  setCalcText: (calcText) => set({ calcText }),
}));
