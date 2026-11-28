/** Shapes returned by the backend. Every number here was computed in Python. */

export type TxType = 'expense' | 'income';
export type CategoryKind = 'fixed' | 'variable' | 'investment';
export type Tab = 'overview' | 'transactions' | 'calendar' | 'forecast' | 'networth' | 'settings';

export interface Profile {
  id: string;
  label: string;
}
export interface ProfilesState {
  active: string;
  profiles: Profile[];
}

export interface YearSummary {
  year: number;
  transactions: number;
  opening_balance: number;
  closing_balance: number;
  start_month: number;
  last_recorded_month: number | null;
}
export interface YearsResponse {
  years: YearSummary[];
  needs_setup: boolean;
  settings: { currency: string; last_year: number | null; last_month: number | null };
  months: string[];
  current_year: number;
  current_month: number;
  today: string;
}

export interface Transaction {
  id: number;
  type: TxType;
  date: string;
  month: number;
  amount: number;
  desc: string;
  cat: string;
  /** Instalments of an investment plan this payment covered; null = not counted. */
  installments: number | null;
  /** Who was paid / who paid, as the bank wrote it (bank import only). */
  payee?: string;
  bank_ref?: string | null;
  /** Left out of every "usual" figure. */
  one_off?: boolean;
  /** Shared by both halves of a "Transfer to Joint". */
  link_id?: string | null;
  /** What arrived in the other currency (e.g. guaraníes for a land payment). */
  foreign_amount?: number | null;
  foreign_currency?: 'EUR' | 'PYG' | null;
}
export interface TransactionInput {
  type: TxType;
  date: string;
  amount: number;
  desc: string;
  cat: string;
  installments?: number | null;
  one_off?: boolean;
  foreign_amount?: number | null;
  foreign_currency?: 'EUR' | 'PYG' | null;
}
export interface TransactionList {
  transactions: Transaction[];
  count: number;
  total_expense: number;
  total_income: number;
  /** Cash in and cash out per date ("YYYY-MM-DD"), worked out by the backend. */
  days: Record<string, { income: number; expense: number }>;
}

export interface CategoryRow {
  name: string;
  kind: CategoryKind;
  essential: boolean;
  tax_relevant: boolean;
  transactions: number;
}
export interface Categories {
  expense: CategoryRow[];
  income: CategoryRow[];
}

export type BudgetStatus = 'under' | 'on_budget' | 'warning' | 'over' | 'unbudgeted';

export interface Dashboard {
  year: number;
  month: number;
  month_name: string;
  kpis: {
    balance_last_month: number;
    current_balance: number;
    income: number;
    income_budget: number;
    spent: number;
    spent_budget: number;
    savings: number;
    savings_rate: number;
    savings_vs_budget: number;
    negative_balance: boolean;
    earmarked: number;
    free_balance: number;
    liquidity: number;
    cash_in: number;
    cash_out: number;
    cash_out_budget: number;
    invested: number;
    invested_budget: number;
    wealth_built: number;
    wealth_rate: number;
  };
  position: Position;
  emergency: EmergencyFund;
  distribution: Distribution;
  costs: {
    month_spend: number;
    fixed: { total: number; share: number };
    variable: { total: number; share: number };
    ranked: {
      cat: string;
      amount: number;
      kind: CategoryKind;
      share: number;
      width: number;
      usual: number | null;
      vs_usual_pct: number | null;
      one_off: number;
    }[];
    usual_months: number;
    usual_months_with_data: number; // of usual_months, how many hold a non-one-off transaction (0 = no usual yet: hide "Usual month")
    unusual: { cat: string; amount: number; usual: number; over: number }[];
  };
  paid_from_funds: { total: number; items: { goal_id: number; name: string; amount: number; date: string }[] };
  upcoming: Upcoming;
  history: History;
  investments: Investments;
  goals: { goals: GoalBrief[]; summary: GoalsResponse['summary'] };
  budget_vs_real: {
    warning_pct: number;
    rows: (BudgetVsRealRow & BudgetUsual)[];
    total: { budget: number; real: number; diff: number; status: BudgetStatus };
    variable_totals: VariableTotals;
  };
}

/** One budget-vs-real line (Overview and Joint). */
export interface BudgetVsRealRow {
  cat: string;
  budget: number;
  real: number;
  diff: number;
  used_pct: number | null;
  progress: number;
  kind: CategoryKind;
  status: BudgetStatus;
}

/** Overview only: the category's usual month, for the │ marker on the budget bar. */
export interface BudgetUsual {
  usual: number | null;     // median of the months before, one-offs left out; null = no earlier month, or none of them has data
  usual_pct: number | null; // usual ÷ budget × 100 (2 decimals); null = no budget or no usual
}

/** Footer "752 € of 900 € spent · 11 days left" — the variable rows only. */
export interface VariableTotals {
  spent: number;            // real of all variable rows (unbudgeted ones included)
  budget: number;           // budget of all variable rows
  days_left: number | null; // days in month − today's day; null unless it is the current month
}

/** What you own, by how freely you can use it. */
export interface Position {
  liquidity: number;
  balance: number;
  earmarked: number;
  invested_value: number;
  total: number;
  parts: { key: 'liquid' | 'goals' | 'investments'; label: string; amount: number; width: number }[];
  usual_costs: number | null;
  costs_basis: 'typical' | 'this_month' | 'none';
  runway_months: number | null;
  over_earmarked: boolean;
}

export interface CalcResult {
  expression: string;
  result: number;
  text: string;
}

export type GuideStatus = 'within' | 'above' | 'below' | null;
export type SegmentKey = 'fixed' | 'variable' | 'investment' | 'goals' | 'unassigned';

/** Where one month's income went. Every figure is computed by the backend. */
export type JobKey = 'fixed' | 'variable' | 'investment' | 'savings';

/** One of the four jobs money can have, against the planning guide. */
export interface JobBlock {
  key: JobKey;
  label: string;
  amount: number;
  /** % of income. */
  share: number;
  guide_min: number | null;
  guide_max: number | null;
  status: GuideStatus;
  attention: boolean;
}

export interface Distribution {
  year: number;
  month: number;
  month_name: string;
  income: number;
  cash_out: number;
  blocks: JobBlock[];
  segments: { key: SegmentKey; label: string; amount: number; share: number; width: number }[];
  saved: number;
  to_goals: number;
  left_to_assign: number;
  shortfall: number;
  over_assigned: boolean;
  suggested: {
    goal_id: number;
    name: string;
    remaining: number;
    required_monthly_pace: number | null;
    status: GoalState;
    suggested: number;
  }[];
}
export interface DistributionPreview {
  month: number;
  saved: number;
  to_goals: number;
  left_to_assign: number;
  adding: number;
  left_after: number;
  over: boolean;
}

export interface HistoryRow {
  year: number;
  month: number;
  month_name: string;
  label: string;
  income: number;
  fixed: number;
  variable: number;
  invested: number;
  expenses: number;
  cash_out: number;
  net: number;
  variable_avg3: number | null;
}
export interface CostStats {
  current: number;
  avg_3m: number | null;
  avg_6m: number | null;
  median_6m: number | null;
  months: number;
  vs_avg_pct: number | null;
  /** This month without one-offs against the median of the months before. */
  vs_usual_pct: number | null;
  one_off: number;
  trend_pct: number | null;
}
export interface History {
  rows: HistoryRow[];
  fixed: CostStats;
  variable: CostStats;
  baseline_months: number;
}

export interface InvestmentPayment {
  year: number;
  id: number;
  date: string;
  amount: number;
  desc: string;
  installments: number;
}
export interface InvestmentPlan {
  id: number;
  name: string;
  category: string;
  unit: string;
  local_currency: string;
  installment_amount: number;
  total_installments: number;
  paid_before: number;
  cost_per_installment: number | null;
  market_value_local: number | null;
  notes: string;
  created_date: string;
  paid: number;
  remaining: number;
  progress_pct: number;
  paid_local: number;
  total_local: number;
  remaining_local: number;
  value_at_cost: number | null;
  remaining_cost: number | null;
  recorded_total: number;
  invested_year: number;
  invested_month: number;
  installments_month: number;
  paid_this_month: boolean;
  expected_end: string | null;
  status: 'active' | 'completed';
  payments: InvestmentPayment[];
}
export interface Investments {
  plans: InvestmentPlan[];
  invested_month: number;
  invested_year: number;
  value_at_cost: number;
}
export interface InvestmentInput {
  name: string;
  category: string;
  unit: string;
  local_currency: string;
  installment_amount: number;
  total_installments: number;
  paid_before: number;
  cost_per_installment: number | null;
  market_value_local?: number | null;
  notes: string;
}

export interface GoalBrief {
  id: number;
  name: string;
  saved: number;
  target_amount: number;
  remaining: number;
  progress_pct: number;
  target_date: string;
  months_remaining: number;
  required_monthly_pace: number | null;
  status: GoalState;
  added_this_month: number;
}

export interface ProjectionRow {
  month: number;
  month_name: string;
  month_short: string;
  income: number;
  expenses: number;
  invested: number;
  savings: number;
  cumulative: number;
  balance: number;
  actual: boolean;
  negative: boolean;
}
export interface Projection {
  year: number;
  rows: ProjectionRow[];
  summary: {
    opening_balance: number;
    actual_savings: number;
    actual_months: number;
    planned_savings: number;
    planned_months: number;
    year_end_savings: number;
    actual_invested: number;
    planned_invested: number;
    year_end_invested: number;
    year_end_balance: number;
    average_monthly_savings: number;
    average_actual_savings: number;
    average_planned_savings: number;
    lowest_balance: number;
    lowest_balance_month: number | null;
    goes_negative: boolean;
    last_actual_month: number | null;
    last_actual_month_name: string | null;
  };
}

export interface BudgetGridRow {
  cat: string;
  kind: CategoryKind;
  /** Average of the last finished months; null when there are none yet. */
  usual: number | null;
  values: number[];
  total: number;
  actuals: number[];
  transactions: number;
  /** Cash out only: each month's budget as a % of that month's planned income (null = no income planned). */
  shares: (number | null)[] | null;
  /** Cash out only: the % a cell is linked to (its euros follow the month's income), or null. */
  links: (number | null)[] | null;
  /** Boxes typed by hand over a figure that fills itself, per month. */
  manual: boolean[];
}
export interface KindTotal {
  monthly: number[];
  total: number;
}
export interface BudgetGrid {
  rows: BudgetGridRow[];
  monthly_totals: number[];
  grand_total: number;
  /** Expense grid only: the plan summed per kind (fixed, variable, investment). */
  kind_totals?: Record<'fixed' | 'variable' | 'investment', KindTotal>;
}
export interface Budgets {
  months: string[];
  start_month: number;
  usual_months: number;
  expense: BudgetGrid;
  income: BudgetGrid;
  saved: {
    planned: number[];
    planned_total: number;
    actual: (number | null)[];
    actual_total: number;
  };
  /** Which salary months come from the income calendar, and which months are still open. */
  links: {
    salary_category: string | null;
    calendar_months: boolean[];
    open_months: number[];
    panel?: SharePanel;
    /** Investment categories whose months follow an investment plan. */
    plan_months?: Record<string, boolean[]>;
    plans?: Record<string, { name: string; unit: string; cost: number | null }>;
    /** Rows that follow the Joint plan: "From <name>" in Joint, "Transfer to Joint" in Personal. */
    joint?: JointLinkedRows | null;
  };
  /** How the plan splits planned income into fixed, variable, investment and savings. */
  allocation: {
    months: (PlannedSplit & { month: number; name: string })[];
    year: PlannedSplit;
  };
}

export interface PlannedSplit {
  income: number;
  cash_out: number;
  /** ``width`` sizes each part of the bar (0 for negative savings). */
  blocks: (JobBlock & { width: number })[];
  /** How much more the plan spends than it earns. */
  shortfall: number;
  /** How many parts are outside the guide in the direction that matters. */
  attention: number;
}

export type GoalState = 'on_track' | 'behind' | 'met' | 'overdue' | 'completed' | 'abandoned';
export interface Contribution {
  id: number;
  date: string;
  amount: number;
  note: string;
  withdrawal: boolean;
  /** + for money in, − for money taken out (a sinking fund paying its bill). */
  signed: number;
}
export interface Goal {
  id: number;
  name: string;
  notes: string;
  emergency_fund: boolean;
  goal_type: GoalType;
  repeat_months: number | null;
  monthly_set_aside: number | null;
  target_amount: number;
  target_date: string;
  created_date: string;
  user_status: 'active' | 'completed' | 'abandoned';
  saved: number;
  remaining: number;
  progress_pct: number;
  months_remaining: number;
  required_monthly_pace: number | null;
  expected_monthly_savings: number;
  /** Stored choice (null = default) and what applies: is the goal spent on its date in the forecast? */
  spend_in_forecast: boolean | null;
  spends_in_forecast: boolean;
  shortfall: number;
  status: GoalState;
  contributions: Contribution[];
  /** The goal seen through the 12-month forecast; null when its date is after the months shown. */
  forecast?: {
    month: string;
    month_name: string;
    spent: boolean;
    /** Balance at the end of that month (after this and earlier purchases); lowest scenario. */
    balance: number;
    affordable: boolean;
    line: string | null;
  } | null;
}
export interface Allocation {
  year: number;
  saved_this_year: number;
  assigned: number;
  unassigned: number;
  over_assigned: boolean;
}
export interface GoalsResponse {
  year: number | null;
  goals: Goal[];
  allocation: Allocation;
  summary: {
    active_goals: number;
    open_goals: number;
    total_target: number;
    total_saved: number;
    total_required_pace: number;
    expected_monthly_savings: number;
    combined_covered: boolean;
    combined_shortfall: number;
  };
}

// -- Emergency fund ---------------------------------------------------------------

export interface EmergencyFund {
  state: 'ready' | 'no_goal' | 'no_essentials' | 'no_costs';
  goal_id: number | null;
  goal_name: string | null;
  target: number | null;
  saved: number;
  essential_categories: string[];
  usual_essential_costs: number | null;
  costs_basis: 'typical' | 'this_month' | 'none';
  months_covered: number | null;
  tone: 'red' | 'amber' | 'green' | null;
  status: string | null;
}

// -- Income calendar --------------------------------------------------------------

export interface LecturePeriod {
  start: string;
  end: string;
}
export interface GraduationScenario {
  name: string;
  job_end: string;
  health_insurance_monthly: number | null;
  new_net_salary: number | null;
}
export interface IncomeSettings {
  enabled: boolean;
  hourly_rate: number;
  hours_lecture_week: number;
  hours_break_week: number;
  lecture_periods: LecturePeriod[];
  salary_category: string;
  contract_pay_lag: number;
  extra_hours_delay: number;
  health_category: string;
  /** How net pay is worked out: German payroll rules (working student, tax class 1) or payslip ratio. */
  net_method: 'tax_rules' | 'payslips';
  /** Church tax as % of income tax: 0, 8 or 9. */
  church_tax_rate: 0 | 8 | 9;
  scenarios: GraduationScenario[];
  /** Day the pay arrives: -1 = the working day before the last one, 0 = last working day, 1–31 = that day. */
  pay_day: number;
}
export interface Payslip {
  id: number;
  month: string;
  gross: number;
  net: number;
  note: string;
}
export interface Vacation {
  id: number;
  start: string;
  end: string;
  note: string;
}
export interface IncomePlan extends IncomeSettings {
  payslips: Payslip[];
  next_payslip_id: number;
  /** Hours typed by hand: {"YYYY-MM": hours}. */
  hours_typed: Record<string, number>;
  vacations: Vacation[];
}
export type WorkMonthKind = 'lecture' | 'break' | 'mixed' | 'none';
export interface CalendarRow {
  key: string;
  label: string;
  month_name: string;
  kind: WorkMonthKind;
  lecture_days: number;
  break_days: number;
  /** Monday–Friday days on vacation (not worked, paid at the 3-month average). */
  vacation_days: number;
  hours: number;
  /** The hours the calendar works out from lecture periods and weekly hours. */
  hours_auto: number;
  /** The hours of this month were typed by hand. */
  hours_typed: boolean;
  hours_extra: number;
  /** Pay for one vacation day (the 3-month average), or null without vacation days. */
  vacation_rate: number | null;
  vacation_pay: number;
  gross: number;
  net: number | null;
  /** Tax rules only: income tax + solidarity + church tax, and pension insurance, for the month. */
  income_tax: number | null;
  pension: number | null;
  /** Share of gross that comes off. */
  deducted_pct: number | null;
  rules_year: number | null;
  received: number | null;
  contract_paid_in: string;
  extra_paid_in: string | null;
  job_ends: string[];
}
export type CalendarWarning = 'no_payslips' | 'no_lecture_periods' | 'lecture_periods_end_early' | 'no_hourly_rate' | 'werkstudent_26_weeks';
export interface IncomeView {
  plan: IncomePlan | null;
  active: boolean;
  calendar: {
    rows: CalendarRow[];
    total_gross: number;
    total_net: number | null;
    average_net: number | null;
    lecture_periods_until: string | null;
    warnings: CalendarWarning[];
    net_method: 'tax_rules' | 'payslips';
    /** Weeks with more than 20 hours of work in the 12 months shown. */
    long_weeks: number;
    payslip_checks: { id: number; month: string; gross: number; net: number; rules_net: number; difference: number }[];
    /** What the tax return may give back for one year (tax rules only). */
    refund: { year: number; rules_year: number; gross: number; pension: number; withheld: number; owed: number; refund: number } | null;
  } | null;
}

// -- Rolling forecast -------------------------------------------------------------

export interface RollingValues {
  income: number;
  expenses: number;
  invested: number;
  savings: number;
  balance: number;
  salary?: number | null;
  /** Planned months: goal purchases in this month, and balance minus money set aside for goals. */
  goal_spend?: number;
  free?: number | null;
}
export interface GoalPurchase { goal_id: number; name: string; amount: number; overdue: boolean }
export interface RollingRow {
  key: string;
  label: string;
  month_name: string;
  year: number;
  month: number;
  actual: boolean;
  budget_from: number | null;
  values: Record<string, RollingValues>;
  /** Planned months only: goals bought this month. */
  goals?: GoalPurchase[];
}
export interface RollingLine {
  key: string;
  name: string;
  job_end: string | null;
  end_balance: number;
  kept: number;
  average_kept: number;
  lowest_balance: number;
  lowest_label: string | null;
  goes_negative: boolean;
  spent_on_goals?: number;
  lowest_free?: number | null;
  lowest_free_label?: string | null;
}
export interface RollingForecast {
  rows: RollingRow[];
  lines: RollingLine[];
  calendar_used: boolean;
  start: string | null;
  start_name?: string;
  end_name?: string;
  starting_balance: number;
  last_recorded_name?: string | null;
  borrowed_budget_years?: number[];
  include_goals?: boolean;
  goals_spent?: number;
}

// -- Bank import and payee rules --------------------------------------------------

export type ImportStatus = 'new' | 'duplicate' | 'possible_duplicate' | 'skipped';
export type ImportReason =
  | 'pending' | 'currency' | 'zero' | 'not_tracked' | 'bank_ref' | 'same_amount_date_payee' | 'same_amount_date';
export interface ImportPreviewRow {
  line: number;
  bank_date: string;
  date: string;
  type: TxType;
  amount: number;
  payee: string;
  purpose: string;
  desc: string;
  cat: string;
  rule_id: number | null;
  bank_ref: string | null;
  status: ImportStatus;
  reason: ImportReason | null;
  match: { date: string; amount: number; desc: string; cat: string; payee: string } | null;
}
export interface ImportPreview {
  filename: string;
  rows: ImportPreviewRow[];
  new: number;
  skipped: number;
  skipped_by_reason: Partial<Record<ImportReason, number>>;
  total: number;
}
export interface ImportRowInput {
  date: string;
  type: TxType;
  amount: number;
  cat: string;
  desc: string;
  payee: string;
  bank_ref: string | null;
}
export interface PayeeRule {
  id: number;
  contains: string;
  category: string;
  tx_type: TxType | null;
  next_month_if_late: boolean;
}
export type PayeeRuleInput = Omit<PayeeRule, 'id'>;
export interface RuleSuggestion {
  contains: string;
  category: string;
  tx_type: TxType;
  count: number;
  example_payee: string;
}
export interface RulesResponse {
  rules: PayeeRule[];
  suggestions: RuleSuggestion[];
}

// -- Phase 2 ------------------------------------------------------------------------

export type GoalType = 'one_time' | 'sinking';

export interface UpcomingItem {
  bill_id: number;
  name: string;
  amount: number;
  category: string;
  due: string;
  days_left: number;
  overdue: boolean;
  source: 'fund' | 'liquidity';
  goal_name: string | null;
  ready: boolean;
  short_by: number;
}
export interface Upcoming {
  items: UpcomingItem[];
  days: number;
  total: number;
  liquidity: number;
  all_ready: boolean;
}
export interface CalendarBill {
  bill_id: number;
  name: string;
  amount: number;
  category: string;
  due: string;
  paid: boolean;
  paid_on: string | null;
  overdue: boolean;
  /** null = too far ahead to judge on today's money. */
  ready: boolean | null;
  short_by: number;
  goal_name: string | null;
  source: 'fund' | 'liquidity' | null;
}
export interface CalendarGoal {
  goal_id: number;
  name: string;
  date: string;
  status: string;
  target_amount: number;
}
/** One money date of the Calendar tab (salary, transfer, contribution, bill or goal deadline). */
export interface MoneyDateItem {
  /** Stable id, e.g. "bill/3/2026-12-01" (used by the iPhone sync later). */
  key: string;
  date: string;
  kind: 'salary' | 'contribution' | 'transfer' | 'bill' | 'goal' | 'sinking';
  name: string;
  amount: number;
  status: 'done' | 'due' | 'overdue' | 'expected';
  done: boolean;
  direction: 'in' | 'out' | 'goal';
  /** "YYYY-MM" the money is for (salary, transfer, contribution). */
  for_month: string | null;
  paid_on: string | null;
  ref_id: number | null;
}
export interface MoneyDates {
  profile: 'personal' | 'joint';
  start: string;
  end: string;
  today: string;
  pay_day: number;
  items: MoneyDateItem[];
  /** Still to pay in the window: bills and transfers not done (overdue included). */
  due_total: number;
  /** Still to come in: salary and contributions not done. */
  expected_total: number;
}
/** Calendar access as macOS reports it ("unavailable" = no Apple Calendar on this machine). */
export type CalendarAccess = 'full' | 'not_asked' | 'denied' | 'restricted' | 'write_only' | 'unavailable' | 'unknown';
export interface AppleCalendarInfo {
  id: string;
  title: string;
  /** "#rrggbb", the calendar's own colour in Apple Calendar. */
  color: string;
  account: string;
  shown: boolean;
}
export interface CalendarStatus {
  /** "apple" in the installed app; "fake" in tests and UI checks. */
  source: 'apple' | 'fake';
  access: CalendarAccess;
  calendars: AppleCalendarInfo[];
  /** iPhone sync switched on. */
  push: boolean;
  /** "YYYY-MM-DDTHH:MM" of the last sync, or null. */
  last_sync: string | null;
  /** Titles of the app's own iCloud calendars ("Centwise", "Centwise Joint"). */
  own_calendars: string[];
  /** How many days ahead the sync covers. */
  sync_days: number;
  granted?: boolean;
  error?: string | null;
  /** After a sync: how many entries were added, changed, removed. */
  added?: number;
  updated?: number;
  removed?: number;
}
export interface CalendarEvent {
  id: string;
  calendar_id: string;
  calendar: string;
  color: string;
  title: string;
  all_day: boolean;
  /** Timed: "YYYY-MM-DDTHH:MM"; all day: "YYYY-MM-DD". */
  start: string;
  /** Timed: "YYYY-MM-DDTHH:MM"; all day: the last day "YYYY-MM-DD". */
  end: string;
  location: string;
}
export interface CalendarDay {
  date: string;
  /** 0 = Monday. */
  weekday: number;
  is_today: boolean;
  /** Inside one of the income calendar's lecture periods (Personal). */
  lecture: boolean;
  events: CalendarEvent[];
  money: MoneyDateItem[];
}
export interface CalendarView {
  profile: 'personal' | 'joint';
  start: string;
  end: string;
  today: string;
  pay_day: number;
  access: CalendarAccess;
  events_error: string | null;
  days: CalendarDay[];
  /** Still to pay in the window: bills and transfers not done (overdue included). */
  due_total: number;
  /** Still to come in: salary and contributions not done. */
  expected_total: number;
}
export interface BillsCalendar {
  year: number;
  month: number;
  today: string;
  bills: CalendarBill[];
  goals: CalendarGoal[];
  total_due: number;
  total_paid: number;
}
export interface RecurringBillInput {
  name: string;
  amount: number;
  category: string;
  rhythm_months: number;
  next_due: string;
  match: string;
  goal_id: number | null;
}
export interface RecurringBill extends RecurringBillInput {
  id: number;
  rhythm_word: string;
  due: string;
  last_paid: string | null;
  goal_name: string | null;
  monthly_cost: number;
}
export interface BillSuggestion {
  key: string;
  name: string;
  amount: number;
  category: string;
  rhythm_months: number;
  rhythm_word: string;
  next_due: string;
  match: string;
  payments: number;
}
export interface BillsResponse {
  bills: RecurringBill[];
  suggestions: BillSuggestion[];
  upcoming: Upcoming;
}

export type Person = 'a' | 'b';
export interface FairShareInput {
  name_a: string;
  name_b: string;
  income_a: number | null;
  income_b: number | null;
}
export interface SharedExpense {
  id: number;
  date: string;
  desc: string;
  amount: number;
  paid_by: Person;
  split: 'fair' | 'equal';
  owed_by_other: number;
}
export interface Settlement {
  id: number;
  date: string;
  from_person: Person;
  amount: number;
  note: string;
}
export interface JointView {
  fair_share: FairShareInput & {
    basis: 'incomes' | 'equal';
    share_a_pct: number;
    share_b_pct: number;
    shared_costs: number | null;
    amount_a: number | null;
    amount_b: number | null;
  };
  settle_up: {
    expenses: SharedExpense[];
    settlements: Settlement[];
    balance_a: number;
    owes: Person | null;
    gets: Person | null;
    amount: number;
    text: string;
  };
}

export interface JointLinkedRows {
  role: 'joint' | 'personal';
  income: Record<string, { name: string; months: boolean[] }>;
  expense: Record<string, { name: string; months: boolean[] }>;
}

export interface JointSplit {
  basis: 'incomes' | 'equal';
  share_a_pct: number;
  share_b_pct: number;
}

/** One month of the shared plan: costs + goal saving, split into each person's part. */
export interface BillMonth {
  key: string;
  label: string;
  month_name: string;
  year: number;
  month: number;
  costs: number;
  goals: number;
  total: number;
  a: number;
  b: number;
}

export interface JointGoal {
  id: number;
  name: string;
  saved: number;
  target_amount: number;
  remaining: number;
  progress_pct: number;
  target_date: string;
  status: GoalState;
  monthly: number | null;
  a: number | null;
  b: number | null;
}

/** The Joint Overview (services/joint.py → household). */
export interface JointHousehold {
  year: number;
  month: number;
  month_name: string;
  pot: { balance: number; earmarked: number; free: number; negative: boolean };
  money: {
    put_in: number;
    from_people: number;
    other_in: number;
    spent: number;
    planned: number;
    left: number;
    spent_pct: number;
    status: 'none' | 'within' | 'over';
    kept: number;
  };
  split: JointSplit;
  bill: BillMonth;
  people: {
    person: Person;
    name: string;
    share_pct: number;
    category: string;
    planned: number;
    paid_in: number;
    to_go: number;
    progress: number;
    done: boolean;
  }[];
  categories: BudgetVsRealRow[];
  categories_total: Dashboard['budget_vs_real']['total'];
  months: { label: string; year: number; month: number; put_in: number; spent: number; kept: number }[];
  goals: { rows: JointGoal[]; monthly: { total: number; a: number; b: number } };
}

/** The Joint Forecast (services/joint.py → bill_forecast). */
export interface JointBill {
  names: { a: string; b: string };
  split: JointSplit;
  rows: (BillMonth & {
    other_income: number;
    goals_bought: { goal_id: number; name: string; amount: number; overdue: boolean }[];
    goal_spend: number;
    pot: number;
  })[];
  start_balance: number;
  start_name: string | null;
  end_name: string | null;
  average: { total: number; a: number; b: number; costs: number; goals: number } | null;
  end_pot: number;
  lowest_pot: number;
  lowest_name: string | null;
  goes_negative: boolean;
}

// -- Phase 3 ------------------------------------------------------------------------

export interface FileResponse {
  filename: string;
  content_base64: string;
}
export interface TaxView {
  year: number;
  categories: string[];
  rows: { date: string; type: TxType; cat: string; desc: string; amount: number; one_off: boolean }[];
  totals: { type: TxType; cat: string; amount: number; count: number }[];
  expenses_total: number;
  income_total: number;
  commute: { days: number; km: number; rate: number; amount: number } | null;
  commute_days: number | null;
  commute_km: number | null;
  work_costs_total: number;
}
export interface BackupCheck {
  ok: boolean;
  created: string | null;
  problems: string[];
  summary: { profile: string; label: string; years: number[]; transactions: number; goals: number }[];
  restored?: string[];
  safety_copies?: string[];
}
export type CurrencyCode = 'EUR' | 'PYG';
export interface NetWorthItem {
  kind: 'tracked' | 'account' | 'asset' | 'debt';
  name: string;
  side: 'own' | 'owe';
  currency: CurrencyCode;
  amount_local: number;
  eur: number | null;
  as_of: string | null;
  basis?: string;
  account_id?: number;
}
export interface AccountRow {
  id: number;
  name: string;
  kind: 'current' | 'savings' | 'investment' | 'cash' | 'other';
  currency: CurrencyCode;
  values: { date: string; amount: number }[];
  notes: string;
}
export interface ExchangePayment {
  year: number;
  id: number;
  date: string;
  desc: string;
  cat: string;
  eur_paid: number;
  foreign_amount: number;
  currency: string;
  rate_got: number;
  rate_reference: number | null;
  fair_eur: number | null;
  cost: number | null;
  cost_pct: number | null;
}
export interface NetWorth {
  items: NetWorthItem[];
  own: number;
  owe: number;
  net_worth: number;
  in_pyg: number;
  in_pyg_pct: number | null;
  rate: { currency: CurrencyCode; per_eur: number; date: string } | null;
  rates: { currency: CurrencyCode; per_eur: number; date: string }[];
  missing_rate: string[];
  accounts: AccountRow[];
  exchange: { payments: ExchangePayment[]; total_cost: number; total_paid: number };
}

export interface Range { min: number; max: number }

/** The "variable costs by % of income" panel, over the months not recorded yet. Figures from the backend. */
export interface SharePanel {
  months: number[];
  income: Range | null;
  fixed: { amount: Range | null; share: Range | null };
  investment: { amount: Range | null; share: Range | null };
  variable: { amount: Range | null; share: Range | null };
  savings: { share: Range | null; guide_min: number | null };
  rows: { cat: string; percent: number | null; mixed: boolean; amount: Range | null }[];
}

// -- Forecast ranges (added 2026-11-19, backend) -------------------------------------
// From backend/app/services/forecast_ranges.py. Sent as `ranges` on GET /api/forecast
// (around the first line) and GET /api/joint/bill (around the pot); null with fewer
// than 6 finished months of history (then hide the bands). All figures from the backend.

/** One forecast month: the most likely balance and the 50 % / 80 % bands around it. */
export interface ForecastRangeMonth {
  key: string;            // "2027-05"
  month_name: string;     // "May 2027"
  months_ahead: number;   // 1 for the first forecast month
  likely: number;
  low50: number;
  high50: number;
  low80: number;
  high80: number;
}

/** For "In 8 of 10 likely futures you stay above {floor_80} through {horizon_end_month}"
 *  and "Most likely balance in {horizon_end_month}: about {likely_end_about}". */
export interface ForecastRangeSummary {
  floor_80: number;
  horizon_end_name: string;   // "May 2027"
  horizon_end_month: string;  // "May"
  likely_end: number;
  likely_end_about: number;   // rounded to the nearest 50 €
}

export interface ForecastRanges extends ForecastRangeSummary {
  months: ForecastRangeMonth[];
  sigma: number;              // usual monthly wobble of "kept", in €
  history_months: number;     // "Based on N months of history"
  first_6: ForecastRangeSummary; // the same, over the first 6 months (Overview card)
  line_key: string | null;    // Personal: which forecast line; Joint: null
}

// Declaration merging: adds `ranges` to the interfaces defined above.
export interface RollingForecast { ranges: ForecastRanges | null }
export interface JointBill { ranges: ForecastRanges | null }

// --- New UI numbers (backend, 2026-11-19): KPI vs usual, "Worth a look", net worth history ---

/** One KPI tile against a usual month (median of up to 6 recorded months before;
 *  one-offs left out of flows on both sides). All comparison fields are null when
 *  there is no earlier month, or when none of them has data (months_with_data = 0). */
export interface KpiVsUsualFigure {
  current: number;          // the tile's figure (same as kpis.*)
  current_regular: number;  // without one-off transactions — what is compared
  one_off: number;          // current − current_regular
  usual: number | null;
  diff: number | null;      // current_regular − usual (+ = more than usual)
  pct: number | null;       // diff ÷ usual × 100 (null when usual is 0)
  direction: 'up' | 'down' | 'same' | null; // 'same' = "About the same as usual"
}

export interface KpiVsUsual {
  months: number;                           // earlier months the usual is built from
  months_with_data: number;                 // of those, how many hold a non-one-off transaction (0 -> no usual)
  same_within: { eur: number; pct: number }; // |diff| < max(eur, pct % of |usual|) -> 'same'
  balance: KpiVsUsualFigure;
  cash_in: KpiVsUsualFigure;
  cash_out: KpiVsUsualFigure;
  kept: KpiVsUsualFigure;                   // = kpis.savings
  wealth_built: KpiVsUsualFigure;
}

// Declaration merging: adds `vs_usual` to Dashboard.
export interface Dashboard { vs_usual: KpiVsUsual }

/** GET /api/{year}/attention?month= — null for any month but the current one. */
export interface Attention {
  status: 'problem' | 'all_clear';
  year: number;
  month: number;
  day: number;              // today's day of the month
  days_in_month: number;
  days_left: number;        // days_in_month − day ("38 € left for 11 days")
  checked: number;          // variable budgets looked at
  category: string | null;
  reason: 'over' | 'pace' | 'close' | null; // over budget / on pace to go over / ≥ 80 % used
  spent: number | null;
  budget: number | null;
  left: number | null;      // budget − spent (negative = over by)
  over: number | null;      // spent − budget when over budget (positive, "12,40 € over"), else null
  used_pct: number | null;
  pace: number | null;      // where spending ends at this pace
  needed: number;           // € to move, rounded up to 5 (0 = nothing)
  source: string | null;    // "Move {needed} € from {source}"
  source_budget: number | null;
  source_spent: number | null;
  source_pace: number | null;
  can_move: boolean;
  cannot_move_reason: 'nothing_needed' | 'no_room' | 'fills_itself' | 'linked' | null;
}

export interface AttentionMoveResult {
  budgets: Record<string, number>; // the two new budgets of the month
  attention: Attention | null;
}

export interface NetWorthHistoryItem {
  kind: 'tracked' | 'account' | 'asset' | 'debt' | string;
  name: string;
  side: 'own' | 'owe';
  eur: number | null;
  account_id: number | null;
  plan_id: number | null;
}

export interface NetWorthPoint {
  month: string;            // "2026-11"
  year: number;
  month_index: number;      // 0–11
  label: string;            // "Nov 26"
  own: number;              // the bar
  owe: number;
  net_worth: number;        // the number on top
  estimated: boolean;
  estimated_reasons: ('carried_back' | 'rate' | 'plan_before_added' | 'land_value' | 'not_recorded')[];
  source: 'live' | 'snapshot' | 'rebuilt';
  items: NetWorthHistoryItem[];
}

/** "Up {total} € in {months} months — about {saved_of_10} of every 10 euros came from what you saved". */
export interface NetWorthChange {
  from: string;
  to: string;
  months: number;
  total: number;
  saved: number;            // sum of wealth built (cash in − costs)
  growth: number;           // total − saved
  saved_share_pct: number | null; // only when total > 0
  saved_of_10: number | null;     // only when 0 ≤ saved ≤ total
  estimated: boolean;
}

/** GET /api/net-worth/history */
export interface NetWorthHistory {
  points: NetWorthPoint[];          // up to 12 month-ends, oldest first, last = this month
  start: NetWorthPoint | null;      // the month-end the change is measured from
  change: NetWorthChange | null;
  vs_previous_month: number | null; // "1.210 € more than at the end of October"
}
