import { ArrowDownRight, ArrowUpRight, Droplets, PiggyBank, Sprout, Wallet } from 'lucide-react';
import { KpiTile, type KpiComparison } from '../../components/ui/KpiTile';
import { fmtExpense, fmtMoney, fmtPct, fmtSigned } from '../../lib/format';
import type { Dashboard, KpiVsUsualFigure } from '../../lib/types';

/**
 * Turns a backend "vs usual" figure into words. `upIsGood` says whether more
 * than usual is good news (kept, cash in) or not (cash out). The difference
 * itself is the backend's `diff`; it is only formatted here.
 */
function vsUsual(f: KpiVsUsualFigure, upIsGood: boolean, short = false): KpiComparison | undefined {
  if (f.direction === null || f.diff === null) return undefined;
  const usual = short ? 'usual' : 'your usual month';
  if (f.direction === 'same') return { direction: 'same', text: `About the same as ${usual}`, tone: 'neutral' };
  const up = f.direction === 'up';
  const amount = fmtMoney(up ? f.diff : -f.diff, { round: true });
  const word = up ? (short ? 'above' : 'more than') : (short ? 'below' : 'less than');
  return { direction: up ? 'up' : 'down', text: `${amount} ${word} ${usual}`, tone: up === upIsGood ? 'good' : 'bad' };
}

/** "€120 one-off not compared" — only when the month has one-offs. */
const oneOff = (f: KpiVsUsualFigure) => (f.one_off ? `${fmtMoney(f.one_off, { round: true })} one-off not compared` : null);

const join = (...parts: (string | null | false | undefined)[]) => parts.filter(Boolean).join(' · ');

const runway = (n: number) => n.toLocaleString('de-DE', { maximumFractionDigits: 1 });

/** Three hero tiles (Kept, Liquidity, Wealth built), then three compact ones (Balance, Cash in, Cash out). */
export function OverviewKpis({ data }: { data: Dashboard }) {
  const k = data.kpis;
  const p = data.position;
  const v = data.vs_usual;
  const months = v.months ? `the middle of your last ${v.months} month${v.months === 1 ? '' : 's'}` : 'your earlier months';
  // No earlier month holds data yet (fresh profile): the backend sends no usual, so nothing is compared.
  const noUsual = v.months_with_data === 0;
  const compared = noUsual ? 'There are no earlier months with transactions yet, so nothing is compared.' : `Compared with ${months}`;

  const liquidityLine = p.over_earmarked
    ? 'Goals hold more than the account has'
    : p.runway_months !== null
      ? `Covers about ${runway(p.runway_months)} month${p.runway_months === 1 ? '' : 's'} of ${p.costs_basis === 'this_month' ? "this month's" : 'usual'} costs`
      : 'Free to use — no goal has a claim on it';

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-4">
        <KpiTile
          variant="hero"
          testId="kpi-kept"
          label="Kept this month"
          icon={<PiggyBank size={14} />}
          value={fmtSigned(k.savings, { round: true })}
          tone={k.savings < 0 ? 'negative' : k.savings > 0 ? 'positive' : 'neutral'}
          comparison={noUsual ? { direction: 'none', text: 'No earlier months yet' } : vsUsual(v.kept, true)}
          help={<>Cash in minus cash out this month. {noUsual ? compared : `${compared} (one-off transactions left out).`}</>}
          meta={join(
            k.cash_in ? `${fmtPct(k.savings_rate)} of cash in` : 'No income recorded yet',
            k.savings < 0 && 'more went out than came in',
            data.paid_from_funds.total > 0 && `${fmtMoney(data.paid_from_funds.total, { round: true })} of bills paid from sinking funds`,
            oneOff(v.kept),
          )}
        />
        <KpiTile
          variant="hero"
          testId="kpi-liquidity"
          label="Liquidity"
          icon={<Droplets size={14} />}
          value={fmtMoney(p.liquidity, { round: true })}
          tone={p.liquidity < 0 ? 'negative' : 'neutral'}
          alert={p.liquidity < 0}
          comparison={{ direction: 'none', text: liquidityLine }}
          help="Your balance minus the money saved for goals: what is free to use. Investments are never part of it."
          meta={k.earmarked > 0 ? `${fmtMoney(k.earmarked, { round: true })} of the balance saved for goals` : undefined}
        />
        <KpiTile
          variant="hero"
          testId="kpi-wealth"
          label="Wealth built"
          icon={<Sprout size={14} />}
          value={fmtSigned(k.wealth_built, { round: true })}
          tone={k.wealth_built < 0 ? 'negative' : k.wealth_built > 0 ? 'positive' : 'neutral'}
          comparison={vsUsual(v.wealth_built, true)}
          help={<>Kept plus invested: the money that stayed in the account plus what went into an asset. {noUsual ? compared : `${compared}.`}</>}
          meta={join(k.cash_in ? `Kept + invested · ${fmtPct(k.wealth_rate)} of cash in` : 'Kept + invested', oneOff(v.wealth_built))}
        />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <KpiTile
          variant="compact"
          testId="kpi-balance"
          label="Balance"
          icon={<Wallet size={14} />}
          value={fmtMoney(k.current_balance)}
          tone={k.negative_balance ? 'negative' : 'neutral'}
          alert={k.negative_balance}
          comparison={vsUsual(v.balance, true, true)}
          meta={k.negative_balance ? 'Below zero — check the Forecast' : `Started ${data.month_name} at ${fmtMoney(k.balance_last_month, { round: true })}`}
        />
        <KpiTile
          variant="compact"
          testId="kpi-cash-in"
          label="Cash in"
          icon={<ArrowDownRight size={14} />}
          value={k.cash_in ? fmtMoney(k.cash_in, { sign: true }) : fmtMoney(0)}
          tone={k.cash_in ? 'positive' : 'neutral'}
          comparison={vsUsual(v.cash_in, true, true)}
          meta={k.income_budget ? `Planned ${fmtMoney(k.income_budget, { round: true })}` : undefined}
        />
        <KpiTile
          variant="compact"
          testId="kpi-cash-out"
          label="Cash out"
          icon={<ArrowUpRight size={14} />}
          value={fmtExpense(k.cash_out)}
          comparison={vsUsual(v.cash_out, false, true)}
          meta={k.invested
            ? `${fmtMoney(k.spent, { round: true })} costs · ${fmtMoney(k.invested, { round: true })} invested`
            : k.cash_out_budget ? `Planned ${fmtMoney(k.cash_out_budget, { round: true })}` : undefined}
        />
      </div>
    </div>
  );
}
