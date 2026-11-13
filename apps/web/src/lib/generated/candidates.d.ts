/* Generated from packages/contracts/v1/schema.json. Run npm run contracts. */

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
