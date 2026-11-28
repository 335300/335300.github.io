/**
 * Server state via TanStack Query.
 *
 * Why a shared cache: adding a transaction must refresh Overview, Transactions
 * and Forecast together. Every mutation therefore invalidates all queries for
 * the app — the data is small and local, so refetching is instant.
 */

import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { api, enc } from './client';
import type {
  BackupCheck,
  BillsCalendar,
  CalendarStatus,
  CalendarView,
  MoneyDates,
  BillsResponse,
  Budgets,
  CalcResult,
  Categories,
  CategoryKind,
  Dashboard,
  DistributionPreview,
  GoalsResponse,
  ImportPreview,
  ImportRowInput,
  IncomeSettings,
  IncomeView,
  InvestmentInput,
  Investments,
  FairShareInput,
  FileResponse,
  JointBill,
  JointHousehold,
  JointView,
  NetWorth,
  TaxView,
  Person,
  RecurringBillInput,
  PayeeRuleInput,
  Projection,
  ProfilesState,
  RollingForecast,
  RulesResponse,
  TransactionInput,
  TransactionList,
  TxType,
  YearsResponse,
} from '../lib/types';
import type { Attention, AttentionMoveResult, NetWorthHistory } from '../lib/types';

export const keys = {
  profiles: ['profiles'] as const,
  prefs: ['prefs'] as const,
  years: ['years'] as const,
  dashboard: (year: number, month: number) => ['dashboard', year, month] as const,
  transactions: (year: number, filters: TxFilters) => ['transactions', year, filters] as const,
  categories: (year: number) => ['categories', year] as const,
  budgets: (year: number) => ['budgets', year] as const,
  projection: (year: number) => ['projection', year] as const,
  goals: (year: number) => ['goals', year] as const,
  investments: (year: number, month: number) => ['investments', year, month] as const,
  distributionPreview: (year: number, body: DistributionBody) => ['distribution-preview', year, body] as const,
  income: ['income'] as const,
  forecast: ['forecast'] as const,
  rules: ['rules'] as const,
  bills: ['bills'] as const,
  billsCalendar: (year: number, month: number) => ['bills-calendar', year, month] as const,
  moneyDates: (start: string, end: string) => ['money-dates', start, end] as const,
  calendarStatus: ['calendar', 'status'] as const,
  calendarView: (start: string, end: string) => ['calendar', 'view', start, end] as const,
  tax: (year: number) => ['tax', year] as const,
  netWorth: ['net-worth'] as const,
  joint: (year: number, month: number) => ['joint', year, month] as const,
  household: (year: number, month: number) => ['joint-household', year, month] as const,
  bill: ['joint-bill'] as const,
};

export interface DistributionBody {
  month: number;
  allocations: { goal_id: number; amount: number }[];
}

export interface TxFilters {
  type?: TxType | '';
  month?: number | '';
  cat?: string;
  q?: string;
}

function refreshAll(qc: QueryClient) {
  return qc.invalidateQueries();
}

// -- reads ---------------------------------------------------------------------

export const useProfiles = () =>
  useQuery({ queryKey: keys.profiles, queryFn: () => api.get<ProfilesState>('/api/profiles') });

export interface Prefs {
  show_savings_tile: boolean;
  /** Calendar tab: ids of the Apple calendars not shown (same in Personal and Joint). */
  calendar_hidden: string[];
  /** iPhone sync: money dates go to the app's own iCloud calendars. */
  calendar_push: boolean;
  /** Set by the backend only: the app's own calendars, per profile. */
  calendar_own_ids: Record<string, string>;
  /** Set by the backend only: "YYYY-MM-DDTHH:MM" of the last sync. */
  calendar_last_sync: string | null;
  /** Light / Dark / Match Mac ('system', the default). */
  appearance: 'system' | 'light' | 'dark';
}

/** Display preferences, saved by the backend in app-state.json so they survive restarts. */
export const usePrefs = () => useQuery({ queryKey: keys.prefs, queryFn: () => api.get<Prefs>('/api/prefs') });

export const useUpdatePrefs = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<Prefs>) => api.patch<Prefs>('/api/prefs', patch),
    // Flip the toggle instantly; the server's answer then confirms it.
    onMutate: (patch) => qc.setQueryData<Prefs>(keys.prefs, (old) => ({
      show_savings_tile: false, calendar_hidden: [], calendar_push: false, calendar_own_ids: {}, calendar_last_sync: null,
      appearance: 'system',
      ...old, ...patch,
    })),
    onSettled: () => Promise.all([
      qc.invalidateQueries({ queryKey: keys.prefs }),
      // Which calendars are shown changes the Calendar tab.
      qc.invalidateQueries({ queryKey: ['calendar'] }),
    ]),
  });
};

export const useYears = () =>
  useQuery({ queryKey: keys.years, queryFn: () => api.get<YearsResponse>('/api/years') });

export const useDashboard = (year: number, month: number) =>
  useQuery({
    queryKey: keys.dashboard(year, month),
    queryFn: () => api.get<Dashboard>(`/api/${year}/dashboard?month=${month}`),
    placeholderData: (prev) => prev,
  });

export const useTransactions = (year: number, filters: TxFilters) =>
  useQuery({
    queryKey: keys.transactions(year, filters),
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.type) params.set('type', filters.type);
      if (filters.month !== undefined && filters.month !== '') params.set('month', String(filters.month));
      if (filters.cat) params.set('cat', filters.cat);
      if (filters.q) params.set('q', filters.q);
      const qs = params.toString();
      return api.get<TransactionList>(`/api/${year}/transactions${qs ? `?${qs}` : ''}`);
    },
    placeholderData: (prev) => prev,
  });

export const useCategories = (year: number) =>
  useQuery({ queryKey: keys.categories(year), queryFn: () => api.get<Categories>(`/api/${year}/categories`) });

export const useBudgets = (year: number) =>
  useQuery({ queryKey: keys.budgets(year), queryFn: () => api.get<Budgets>(`/api/${year}/budgets`) });

export const useProjection = (year: number) =>
  useQuery({ queryKey: keys.projection(year), queryFn: () => api.get<Projection>(`/api/${year}/projection`) });

export const useGoals = (year: number) =>
  useQuery({ queryKey: keys.goals(year), queryFn: () => api.get<GoalsResponse>(`/api/goals?year=${year}`) });

/** Investment plans with their progress, seen from one month. */
export const useInvestments = (year: number, month: number) =>
  useQuery({
    queryKey: keys.investments(year, month),
    queryFn: () => api.get<Investments>(`/api/investments?year=${year}&month=${month}`),
    placeholderData: (prev) => prev,
  });

/** What a distribution would leave unassigned — computed by the backend, nothing is saved. */
export const useDistributionPreview = (year: number, body: DistributionBody, enabled: boolean) =>
  useQuery({
    queryKey: keys.distributionPreview(year, body),
    queryFn: () => api.post<DistributionPreview>(`/api/${year}/distribution/preview`, body),
    enabled,
    placeholderData: (prev) => prev,
  });

/**
 * The pocket calculator's answer. The arithmetic is done by the backend (exact
 * decimals); an unfinished expression simply has no answer yet, so it is not retried.
 */
export const useCalc = (expression: string) =>
  useQuery({
    queryKey: ['calc', expression] as const,
    queryFn: () => api.post<CalcResult>('/api/calc', { expression }),
    enabled: expression.trim() !== '',
    retry: false,
    staleTime: Infinity,
  });

// -- writes --------------------------------------------------------------------

/** A mutation that refreshes every view once it succeeds. */
function useWrite<TArgs, TResult = unknown>(fn: (args: TArgs) => Promise<TResult>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => refreshAll(qc) });
}

export const useSwitchProfile = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (profile: string) => api.post<ProfilesState>('/api/profiles/active', { profile }),
    // A different profile is a different database: drop everything cached.
    onSuccess: () => qc.resetQueries(),
  });
};

export const useSetup = () =>
  useWrite((body: { year: number; opening_balance: number; start_month: number; starter_categories: boolean }) =>
    api.post('/api/setup', body)
  );

export const useCreateYear = () => useWrite((year: number) => api.post('/api/years', { year }));

export const useUpdateYear = (year: number) =>
  useWrite((body: { opening_balance?: number; start_month?: number }) => api.patch(`/api/years/${year}`, body));

export const useAddTransaction = (year: number) =>
  useWrite((tx: TransactionInput) => api.post(`/api/${year}/transactions`, tx));

export const useBulkAdd = (year: number) =>
  useWrite((transactions: TransactionInput[]) =>
    api.post<{ count: number }>(`/api/${year}/transactions/bulk`, { transactions })
  );

export const useUpdateTransaction = (year: number) =>
  useWrite(({ id, tx }: { id: number; tx: TransactionInput }) => api.put(`/api/${year}/transactions/${id}`, tx));

export const useDeleteTransaction = (year: number) =>
  useWrite((id: number) => api.del(`/api/${year}/transactions/${id}`));

export const useAddCategory = (year: number) =>
  useWrite((body: { kind: TxType; name: string; category_kind: CategoryKind }) =>
    api.post(`/api/${year}/categories`, body)
  );

export const useUpdateCategory = (year: number) =>
  useWrite(({ kind, name, patch }: { kind: TxType; name: string; patch: { name?: string; category_kind?: CategoryKind; essential?: boolean; tax_relevant?: boolean } }) =>
    api.patch(`/api/${year}/categories/${kind}/${enc(name)}`, patch)
  );

export const useDeleteCategory = (year: number) =>
  useWrite(({ kind, name }: { kind: TxType; name: string }) => api.del(`/api/${year}/categories/${kind}/${enc(name)}`));

export const useSetBudget = (year: number) =>
  useWrite((body: { kind: TxType; cat: string; month: number; value?: number; percent?: number; auto?: boolean }) => api.put(`/api/${year}/budgets`, body));

/** Link one cost category to a % of planned income in every month not recorded yet (null removes the links). */
export const useSetRowShare = (year: number) =>
  useWrite((body: { cat: string; percent: number | null }) => api.put(`/api/${year}/budgets/row-share`, body));

export const useCreateGoal = () =>
  useWrite((body: { name: string; target_amount: number; target_date: string; notes: string; emergency_fund?: boolean; goal_type?: 'one_time' | 'sinking'; repeat_months?: number | null; spend_in_forecast?: boolean }) =>
    api.post('/api/goals', body)
  );

export const useUpdateGoal = () =>
  useWrite(({ id, patch }: { id: number; patch: Record<string, unknown> }) => api.patch(`/api/goals/${id}`, patch));

export const useDeleteGoal = () => useWrite((id: number) => api.del(`/api/goals/${id}`));

export const useAddContribution = () =>
  useWrite(({ goalId, body }: { goalId: number; body: { date: string; amount: number; note: string } }) =>
    api.post(`/api/goals/${goalId}/contributions`, body)
  );

export const useDeleteContribution = () =>
  useWrite(({ goalId, id }: { goalId: number; id: number }) => api.del(`/api/goals/${goalId}/contributions/${id}`));

export const useCreateInvestment = () => useWrite((body: InvestmentInput) => api.post('/api/investments', body));

export const useUpdateInvestment = () =>
  useWrite(({ id, patch }: { id: number; patch: Partial<InvestmentInput> }) => api.patch(`/api/investments/${id}`, patch));

export const useDeleteInvestment = () => useWrite((id: number) => api.del(`/api/investments/${id}`));

/** Put part of one month's savings toward goals — one contribution per goal. */
export const useApplyDistribution = (year: number) =>
  useWrite((body: DistributionBody) => api.post(`/api/${year}/distribution`, body));

/** Record a payment in whatever year its date falls in (used by investment plans). */
export const useAddTransactionAnyYear = () =>
  useWrite((tx: TransactionInput) => api.post(`/api/${tx.date.slice(0, 4)}/transactions`, tx));

// -- Phase 1: income calendar, rolling forecast, bank import, payee rules ------

export const useIncome = () => useQuery({ queryKey: keys.income, queryFn: () => api.get<IncomeView>('/api/income') });

/** The rolling forecast; ``includeGoals=false`` leaves goal purchases out, to compare. */
export const useForecast = (includeGoals = true) =>
  useQuery({
    queryKey: [...keys.forecast, includeGoals],
    queryFn: () => api.get<RollingForecast>(`/api/forecast${includeGoals ? '' : '?goals=false'}`),
    placeholderData: (prev) => prev,
  });

export const useSaveIncomeSettings = () =>
  useWrite((body: IncomeSettings) => api.put<IncomeView>('/api/income/settings', body));

export const useAddPayslip = () =>
  useWrite((body: { month: string; gross: number; net: number; note: string }) =>
    api.post<IncomeView>('/api/income/payslips', body)
  );

export const useDeletePayslip = () => useWrite((id: number) => api.del<IncomeView>(`/api/income/payslips/${id}`));

/** Hours worked in a month of work, typed by hand (null = back to the calendar's hours). */
export const useSetTypedHours = () =>
  useWrite(({ month, hours }: { month: string; hours: number | null }) =>
    api.put<IncomeView>(`/api/income/hours/${month}`, { hours })
  );

export const useAddVacation = () =>
  useWrite((body: { start: string; end: string; note: string }) => api.post<IncomeView>('/api/income/vacations', body));

export const useDeleteVacation = () => useWrite((id: number) => api.del<IncomeView>(`/api/income/vacations/${id}`));

/** Reads a statement file and reports what is new. Saves nothing, so nothing is refreshed. */
export const useImportPreview = () =>
  useMutation({
    mutationFn: (body: { filename: string; content_base64: string }) =>
      api.post<ImportPreview>('/api/import/preview', body),
  });

export const useImportCommit = () =>
  useWrite((rows: ImportRowInput[]) => api.post<{ created: number; skipped: number }>('/api/import/commit', { rows }));

export const useRules = () => useQuery({ queryKey: keys.rules, queryFn: () => api.get<RulesResponse>('/api/rules') });

export const useAddRule = () => useWrite((body: PayeeRuleInput) => api.post<RulesResponse>('/api/rules', body));

export const useUpdateRule = () =>
  useWrite(({ id, body }: { id: number; body: PayeeRuleInput }) => api.put<RulesResponse>(`/api/rules/${id}`, body));

export const useDeleteRule = () => useWrite((id: number) => api.del<RulesResponse>(`/api/rules/${id}`));

export const useDismissSuggestion = () =>
  useWrite((contains: string) => api.post<RulesResponse>('/api/rules/suggestions/dismiss', { contains }));

// -- Phase 2: sinking funds, recurring bills, Joint links --------------------------

export const usePayFromFund = () =>
  useWrite(({ goalId, body }: { goalId: number; body: { date: string; amount: number; category: string; desc: string } }) =>
    api.post<{ from_fund: number; from_free_money: number; next_due: string }>(`/api/goals/${goalId}/pay`, body)
  );

export const useBills = () => useQuery({ queryKey: keys.bills, queryFn: () => api.get<BillsResponse>('/api/bills') });

export const useBillsCalendar = (year: number, month: number) =>
  useQuery({
    queryKey: keys.billsCalendar(year, month),
    queryFn: () => api.get<BillsCalendar>(`/api/bills/calendar/${year}/${month}`),
    placeholderData: (prev) => prev,
  });

/** Calendar tab: the open profile's money dates from start to end (YYYY-MM-DD, both included). */
export const useMoneyDates = (start: string, end: string) =>
  useQuery({
    queryKey: keys.moneyDates(start, end),
    queryFn: () => api.get<MoneyDates>(`/api/calendar/money?start=${start}&end=${end}`),
    placeholderData: (prev) => prev,
  });

/** Calendar tab: is Apple Calendar allowed, and which calendars there are. */
export const useCalendarStatus = () =>
  useQuery({ queryKey: keys.calendarStatus, queryFn: () => api.get<CalendarStatus>('/api/calendar/status') });

/** Ask macOS for calendar access; the request waits until the user answers the macOS question. */
export const useAllowCalendar = () => useWrite(() => api.post<CalendarStatus>('/api/calendar/allow'));

/** iPhone sync now; the backend works out what changes (services/calendar_sync.py). */
export const useSyncCalendar = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: ['calendar-sync'],
    mutationFn: () => api.post<CalendarStatus>('/api/calendar/sync'),
    onSuccess: (status) => {
      qc.setQueryData(keys.calendarStatus, status);
      return qc.invalidateQueries({ queryKey: keys.prefs });
    },
  });
};

/** Switch the iPhone sync off and delete the app's own iCloud calendars (nothing else). */
export const useRemoveOwnCalendars = () => useWrite(() => api.del<CalendarStatus>('/api/calendar/own'));

/**
 * iPhone sync while it is on: once when the app opens (or the sync is switched on), and a
 * few seconds after any change, so moved or paid money dates reach the Centwise calendars.
 * Errors here stay quiet; Settings → Calendar shows the last sync and has "Sync now".
 */
export function useCalendarAutoSync() {
  const qc = useQueryClient();
  const on = usePrefs().data?.calendar_push ?? false;
  useEffect(() => {
    if (!on) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const run = () => {
      api.post<CalendarStatus>('/api/calendar/sync')
        .then((status) => qc.setQueryData(keys.calendarStatus, status))
        .catch(() => qc.invalidateQueries({ queryKey: keys.calendarStatus }));
    };
    run();
    const unsubscribe = qc.getMutationCache().subscribe((event) => {
      if (event.type !== 'updated' || event.action.type !== 'success') return;
      if (event.mutation.options.mutationKey?.[0] === 'calendar-sync') return;
      clearTimeout(timer);
      timer = setTimeout(run, 3000);
    });
    return () => {
      unsubscribe();
      clearTimeout(timer);
    };
  }, [on, qc]);
}

/** Calendar tab: day by day from start to end (YYYY-MM-DD): events, money dates, lecture days. */
export const useCalendarView = (start: string, end: string) =>
  useQuery({
    queryKey: keys.calendarView(start, end),
    queryFn: () => api.get<CalendarView>(`/api/calendar/view?start=${start}&end=${end}`),
    placeholderData: (prev) => prev,
  });

export const useAddBill = () => useWrite((body: RecurringBillInput) => api.post<BillsResponse>('/api/bills', body));

export const useUpdateBill = () =>
  useWrite(({ id, body }: { id: number; body: RecurringBillInput }) => api.put<BillsResponse>(`/api/bills/${id}`, body));

export const useDeleteBill = () => useWrite((id: number) => api.del<BillsResponse>(`/api/bills/${id}`));

export const useDismissBill = () =>
  useWrite((key: string) => api.post<BillsResponse>('/api/bills/suggestions/dismiss', { key }));

export const useJoint = (year: number, month: number) =>
  useQuery({ queryKey: keys.joint(year, month), queryFn: () => api.get<JointView>(`/api/joint?year=${year}&month=${month}`) });

export const useSaveFairShare = () => useWrite((body: FairShareInput) => api.put<JointView>('/api/joint/fair-share', body));

/** The Joint Overview: our pot, this month against the plan, who has paid in. */
export const useJointHousehold = (year: number, month: number) =>
  useQuery({
    queryKey: keys.household(year, month),
    queryFn: () => api.get<JointHousehold>(`/api/joint/household?year=${year}&month=${month}`),
  });

/** The Joint Forecast: what we pay each month, and who pays which part. */
export const useJointBill = () => useQuery({ queryKey: keys.bill, queryFn: () => api.get<JointBill>('/api/joint/bill') });

export const useAddShared = () =>
  useWrite((body: { date: string; desc: string; amount: number; paid_by: Person; split: 'fair' | 'equal' }) =>
    api.post<JointView>('/api/joint/shared', body)
  );

export const useDeleteShared = () => useWrite((id: number) => api.del<JointView>(`/api/joint/shared/${id}`));

export const useAddSettlement = () =>
  useWrite((body: { date: string; from_person: Person; amount: number; note: string }) =>
    api.post<JointView>('/api/joint/settlements', body)
  );

export const useDeleteSettlement = () => useWrite((id: number) => api.del<JointView>(`/api/joint/settlements/${id}`));

export const useTransferToJoint = () =>
  useWrite((body: { date: string; amount: number; note: string }) => api.post('/api/joint/transfer', body));

// -- Phase 3: tax export, data safety, net worth ----------------------------------

export const useTax = (year: number) =>
  useQuery({ queryKey: keys.tax(year), queryFn: () => api.get<TaxView>(`/api/${year}/tax`) });

export const useSaveTaxSettings = (year: number) =>
  useWrite((body: { commute_days: number | null; commute_km: number | null }) => api.put<TaxView>(`/api/${year}/tax/settings`, body));

/** Files made by the backend; the page passes them to the Save window. */
export const fetchTaxFile = (year: number) => api.get<FileResponse>(`/api/${year}/tax/file`);
export const fetchTransactionsCsv = () => api.get<FileResponse>('/api/data/export/transactions');
export const fetchDataJson = () => api.get<FileResponse>('/api/data/export/json');

export const useMakeBackup = () =>
  useMutation({ mutationFn: (password: string) => api.post<FileResponse>('/api/data/backup', { password }) });

export const useVerifyBackup = () =>
  useMutation({
    mutationFn: (body: { password: string; content_base64: string }) => api.post<BackupCheck>('/api/data/backup/verify', body),
  });

export const useRestoreBackup = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { password: string; content_base64: string }) => api.post<BackupCheck>('/api/data/backup/restore', body),
    // Every profile may have changed: refetch everything (in place, so this page stays open).
    onSuccess: () => qc.invalidateQueries(),
  });
};

export const useNetWorth = () => useQuery({ queryKey: keys.netWorth, queryFn: () => api.get<NetWorth>('/api/net-worth') });

export const useAddAccount = () =>
  useWrite((body: { name: string; kind: string; currency: string; notes: string }) => api.post<NetWorth>('/api/accounts', body));

export const useDeleteAccount = () => useWrite((id: number) => api.del<NetWorth>(`/api/accounts/${id}`));

export const useSetAccountValue = () =>
  useWrite(({ id, body }: { id: number; body: { date: string; amount: number } }) => api.post<NetWorth>(`/api/accounts/${id}/values`, body));

export const useSetRate = () =>
  useWrite((body: { currency: string; per_eur: number; date: string }) => api.post<NetWorth>('/api/rates', body));

export const useDeleteRate = () =>
  useWrite(({ currency, date }: { currency: string; date: string }) => api.del<NetWorth>(`/api/rates/${currency}/${date}`));

// --- New UI numbers (backend, 2026-11-19): "Worth a look" banner, net worth history ---
// (KPI euro differences arrive inside useDashboard as `vs_usual`.)

/** The Overview's "Worth a look" banner; `null` for any month but the current one. */
export const useAttention = (year: number, month: number) =>
  useQuery({
    queryKey: ['attention', year, month] as const,
    queryFn: () => api.get<Attention | null>(`/api/${year}/attention?month=${month}`),
  });

/** "Move {needed} € from {source}": send exactly what the banner offered (409 if it changed). */
export const useAttentionMove = (year: number) =>
  useWrite((body: { month: number; from_cat: string; to_cat: string; amount: number }) =>
    api.post<AttentionMoveResult>(`/api/${year}/attention/move`, body));

/** Month-end net worth for the last 12 months and the split of the change (Personal). */
export const useNetWorthHistory = () =>
  useQuery({ queryKey: [...keys.netWorth, 'history'] as const, queryFn: () => api.get<NetWorthHistory>('/api/net-worth/history') });
