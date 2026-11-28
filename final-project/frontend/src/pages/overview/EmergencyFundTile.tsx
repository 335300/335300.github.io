import { AlertTriangle, CircleCheck, LifeBuoy, TrendingUp } from 'lucide-react';
import type { ReactNode } from 'react';
import { Card, Hint } from '../../components/ui/Card';
import { fmtMoney } from '../../lib/format';
import type { EmergencyFund } from '../../lib/types';

const LOOK: Record<'red' | 'amber' | 'green', { cls: string; icon: ReactNode }> = {
  red: { cls: 'bg-negative-tint text-negative', icon: <AlertTriangle size={12} /> },
  amber: { cls: 'bg-warning-tint text-warning', icon: <TrendingUp size={12} /> },
  green: { cls: 'bg-positive-tint text-positive', icon: <CircleCheck size={12} /> },
};

/**
 * How many months of essential costs the emergency fund covers. Every figure and
 * the status word come from the backend (services/emergency.py); the colour is
 * always paired with an icon and a word.
 */
export function EmergencyFundTile({ data, className = '' }: { data: EmergencyFund; className?: string }) {
  return (
    <Card
      className={className}
      title={<span className="flex items-center gap-1.5"><LifeBuoy size={15} /> Emergency fund</span>}
    >
      {data.state === 'ready' && data.months_covered !== null && data.tone ? (
        <div>
          <div className="flex items-baseline gap-2">
            <span className="num text-[28px] font-semibold leading-none tracking-tight" data-testid="emergency-months">
              {data.months_covered.toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
            </span>
            <span className="text-sm text-ink-soft">month{data.months_covered === 1 ? '' : 's'} covered</span>
          </div>
          <span className={`mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${LOOK[data.tone].cls}`}>
            {LOOK[data.tone].icon}
            {data.status}
          </span>
          <dl className="num mt-3 space-y-1 text-xs text-ink-muted">
            <div className="flex justify-between"><dt>Saved in “{data.goal_name}”</dt><dd className="text-ink">{fmtMoney(data.saved)}</dd></div>
            <div className="flex justify-between">
              <dt>{data.costs_basis === 'this_month' ? "Essential costs this month" : 'Usual essential costs a month'}</dt>
              <dd className="text-ink">{fmtMoney(data.usual_essential_costs ?? 0)}</dd>
            </div>
          </dl>
          <Hint>Essential: {data.essential_categories.join(', ')}.</Hint>
        </div>
      ) : (
        <SetupHint data={data} />
      )}
    </Card>
  );
}

function SetupHint({ data }: { data: EmergencyFund }) {
  const steps = {
    no_goal: 'Choose which savings goal is your emergency fund: edit a goal on the Forecast tab and tick “This is my emergency fund”.',
    no_essentials: 'Mark your essential categories (rent, insurance, groceries…) with the shield button in Transactions → Categories.',
    no_costs: 'No essential costs are recorded yet, so there is nothing to measure against.',
    ready: '',
  } as const;
  return (
    <div className="space-y-2 text-sm text-ink-soft">
      <p>{steps[data.state]}</p>
      {data.state !== 'no_goal' && data.goal_name && (
        <p className="num text-xs text-ink-muted">Saved in “{data.goal_name}”: {fmtMoney(data.saved)}</p>
      )}
    </div>
  );
}
