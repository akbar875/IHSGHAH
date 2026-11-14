/* Generated from packages/contracts/v1/schema.json. Run npm run contracts. */

export type MarketResponse = (CandidatesResponse | StockDetailResponse | ChartResponse | SignalHistoryResponse | WatchlistResponse | RiskSettingsResponse | RiskProfileResponse | SettingsEligibilityResponse | PositionsResponse | PositionResponse | PositionMonitorResponse)
export type CandidatesResponse = ({
[k: string]: unknown
} & {
contract_version: "1.0.0"
as_of: string
mode: ("research" | "paper" | "live")
data_origin: ("simulation" | "market")
quality: Quality
/**
 * @maxItems 1000
 */
data: Signal[]
})
export type Probability = ({
status: ("unvalidated" | "unavailable")
value: null
calibration_version: null
} | {
status: "validated"
value: number
calibration_version: string
})
export type StockDetailResponse = ({
[k: string]: unknown
} & {
contract_version: "1.0.0"
as_of: string
mode: ("research" | "paper" | "live")
data_origin: ("simulation" | "market")
quality: Quality
data: StockDetail
})
export type Pressure = ({
[k: string]: unknown
} & {
window_minutes: (1 | 5 | 15)
buy_ratio: (number | null)
sell_ratio: (number | null)
classified_ratio: number
method: ("provider" | "estimated" | "unavailable")
validated: boolean
})
export type ChartResponse = ({
[k: string]: unknown
} & {
contract_version: "1.0.0"
as_of: string
mode: ("research" | "paper" | "live")
data_origin: ("simulation" | "market")
quality: Quality
data: Chart
})
export type Chart = ({
[k: string]: unknown
} & {
symbol: string
interval: ("1m" | "5m" | "15m")
/**
 * @maxItems 1000
 */
candles: Candle[]
/**
 * @maxItems 1000
 */
projection: Projection[]
model_version: (string | null)
horizon_minutes: (number | null)
coverage_status: ("unvalidated" | "validated" | "unavailable")
})
export type SignalHistoryResponse = ({
[k: string]: unknown
} & {
contract_version: "1.0.0"
as_of: string
mode: ("research" | "paper" | "live")
data_origin: ("simulation" | "market")
quality: Quality
/**
 * @maxItems 1000
 */
data: Signal[]
})
export type WatchlistResponse = ({
[k: string]: unknown
} & {
contract_version: "1.0.0"
as_of: string
mode: ("research" | "paper" | "live")
data_origin: ("simulation" | "market")
quality: Quality
data: Watchlist
})
export type RiskSettingsResponse = ({
[k: string]: unknown
} & {
contract_version: "1.0.0"
as_of: string
mode: ("research" | "paper" | "live")
data_origin: ("simulation" | "market")
quality: Quality
data: RiskSettings
})
export type RiskProfileResponse = ({
[k: string]: unknown
} & {
contract_version: "1.0.0"
as_of: string
mode: ("research" | "paper" | "live")
data_origin: ("simulation" | "market")
quality: Quality
data: RiskProfile
})
export type SettingsEligibilityResponse = ({
[k: string]: unknown
} & {
contract_version: "1.0.0"
as_of: string
mode: ("research" | "paper" | "live")
data_origin: ("simulation" | "market")
quality: Quality
data: SettingsEligibility
})
export type PositionsResponse = ({
[k: string]: unknown
} & {
contract_version: "1.0.0"
as_of: string
mode: ("research" | "paper" | "live")
data_origin: ("simulation" | "market")
quality: Quality
/**
 * @maxItems 1000
 */
data: Position[]
})
export type Position = ({
[k: string]: unknown
} & {
position_id: string
user_id: string
symbol: string
/**
 * @minItems 1
 * @maxItems 1000
 */
fills: [Fill, ...(Fill)[]]
remaining_lots: number
average_price_idr: string
fees_idr: string
opened_at: string
plan_version: number
status: ("OPEN" | "PARTIAL" | "EXIT_REQUESTED" | "CLOSED")
overnight_risk: boolean
})
export type PositionResponse = ({
[k: string]: unknown
} & {
contract_version: "1.0.0"
as_of: string
mode: ("research" | "paper" | "live")
data_origin: ("simulation" | "market")
quality: Quality
data: Position
})
export type PositionMonitorResponse = ({
[k: string]: unknown
} & {
contract_version: "1.0.0"
as_of: string
mode: ("research" | "paper" | "live")
data_origin: ("simulation" | "market")
quality: Quality
data: PositionMonitor
})

export interface Quality {
status: ("healthy" | "degraded" | "stale" | "disconnected" | "unavailable")
feed: ("live" | "delayed" | "disconnected" | "unavailable")
last_heartbeat_at: (string | null)
/**
 * @maxItems 1000
 */
reasons: ("SIMULATION" | "SEQUENCE_GAP" | "HEARTBEAT_TIMEOUT" | "DELAYED_FEED" | "INSUFFICIENT_DATA" | "MODEL_UNVALIDATED" | "MARKET_CLOSED" | "RESYNC_REQUIRED")[]
}
export interface Signal {
signal_id: string
version: number
symbol: string
generated_at: string
data_as_of: string
valid_until: string
horizon_minutes: (15 | 30 | 60 | 240)
model_version: string
policy_version: string
configuration_version: string
state: ("WATCH" | "READY" | "EXPIRED" | "CANCELLED")
entry_zone: {
lower_idr: string
upper_idr: string
}
trigger: ("PRICE_AND_TREND" | "PRICE_BREAKOUT" | "PRICE_PULLBACK")
invalidation: ("PRICE_BREACH" | "DATA_UNHEALTHY" | "TIME_EXPIRED")
stop_idr: string
/**
 * @minItems 1
 * @maxItems 2
 */
targets_idr: [string, ...(string)[]]
entry_from: string
entry_until: string
exit_deadline: string
return_quantiles: ({
p10: string
p50: string
p90: string
net_of_fees: true
} | null)
target_probability: Probability
assumptions: {
reference_price_idr: string
nominal_idr: string
fee_schedule_version: string
order_type: "LIMIT"
}
}
export interface StockDetail {
symbol: string
last_price_idr: (string | null)
rule: InstrumentRule
signal: (Signal | null)
liquidity: (LiquidityEstimate | null)
depth: (Depth | null)
/**
 * @maxItems 3
 */
pressure: Pressure[]
}
export interface InstrumentRule {
symbol: string
board: string
effective_from: string
effective_to: (string | null)
rule_version: string
lot_size_shares: number
/**
 * @minItems 1
 * @maxItems 1000
 */
tick_rule: [{
from_idr: string
to_idr: (string | null)
tick_idr: string
}, ...({
from_idr: string
to_idr: (string | null)
tick_idr: string
})[]]
limit_rule: {
reference_price_idr: string
lower_idr: string
upper_idr: string
version: string
}
session: string
calendar_version: string
tradability: ("tradable" | "suspended" | "unsupported" | "closed")
}
export interface LiquidityEstimate {
signal_id: string
signal_version: number
nominal_idr: string
lots: number
depth_as_of: string
order_policy: "LIMIT"
deadline: string
slippage_cap_ratio: string
category: ("sufficient" | "limited" | "insufficient" | "unavailable")
entry_fill_probability: Probability
exit_fill_probability: Probability
quality: Quality
}
export interface Depth {
symbol: string
snapshot_id: string
sequence: string
depth_as_of: string
/**
 * @maxItems 50
 */
bids: BookLevel[]
/**
 * @maxItems 50
 */
asks: BookLevel[]
available_levels: number
limited: boolean
}
export interface BookLevel {
price_idr: string
lots: number
cumulative_lots: number
}
export interface Candle {
at: string
open_idr: string
high_idr: string
low_idr: string
close_idr: string
volume_lots: number
}
export interface Projection {
at: string
median_idr: string
lower_idr: string
upper_idr: string
coverage: number
}
export interface Watchlist {
/**
 * @maxItems 200
 */
symbols: string[]
}
export interface RiskSettings {
configuration_version: string
nominal_idr: string
capital_idr: string
risk_per_position_ratio: string
max_combined_risk_ratio: string
max_positions: number
fee_schedule_version: string
}
export interface RiskProfile {
configuration_version: string
nominal_idr: string
capital_idr: string
risk_per_position_ratio: string
max_combined_risk_ratio: string
max_positions: number
fee_schedule_version: string
fee_schedule: UserFeeSchedule
}
export interface UserFeeSchedule {
version: string
buy_ratio: string
sell_ratio: string
effective_from: string
effective_to: string
source: string
verification: "user_assumption"
}
export interface SettingsEligibility {
configuration_version: string
risk_budget_idr: string
combined_budget_idr: string
budget_lots_ceiling: number
eligible_lots: 0
reason: ("MODEL_UNVALIDATED" | "FEE_SCHEDULE_EXPIRED")
}
export interface Fill {
fill_id: string
position_id: string
side: ("BUY" | "SELL")
price_idr: string
lots: number
filled_at: string
recorded_at: string
fees_idr: string
origin: ("manual" | "simulation")
}
export interface PositionMonitor {
position: Position
plan: (PositionPlan | null)
invested_idr: string
remaining_cost_idr: string
realized_pnl_idr: string
stop_loss_idr: (string | null)
target_net_idr: (string | null)
exit_reason: (("MANUAL" | "STOP" | "TARGET" | "DEADLINE") | null)
}
export interface PositionPlan {
stop_idr: string
target_idr: string
exit_deadline: string
sell_fee_ratio: string
}
