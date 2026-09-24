-- gold: quarterly capex per company, plus trailing twelve months and year over year growth.
--
-- cash flow statements report fiscal year to date, so a quarter is its ytd value minus the
-- previous quarter's ytd value in the same fiscal year. partitioning by fiscal_year_start
-- makes Q4 fall out for free: the 10-K annual value minus the Q3 ytd value.

create or replace table gold_quarterly_capex as
with deltas as (
    select
        *,
        lag(fiscal_quarter) over w as prev_fiscal_quarter,
        lag(ytd_capex_usd) over w as prev_ytd_capex_usd
    from silver_capex_facts
    window w as (partition by ticker, fiscal_year_start order by end_date)
),

quarterly as (
    select
        ticker,
        fiscal_year,
        fiscal_quarter,
        end_date as quarter_end,
        -- map each fiscal quarter to the calendar quarter holding its midpoint, so a
        -- microsoft fiscal Q1 (jul to sep) lines up with alphabet's Q3 on one axis.
        year(cast(end_date - interval 45 day as date)) as calendar_year,
        quarter(cast(end_date - interval 45 day as date)) as calendar_quarter,
        case
            when fiscal_quarter = 1 then ytd_capex_usd
            when prev_fiscal_quarter = fiscal_quarter - 1 then ytd_capex_usd - prev_ytd_capex_usd
            -- a missing prior quarter leaves this null instead of silently doubling up
        end as capex_usd,
        ytd_capex_usd,
        source_concept,
        accession
    from deltas
)

select
    *,
    concat(cast(calendar_year as string), '-Q', cast(calendar_quarter as string)) as calendar_label,
    case when count(capex_usd) over last4 = 4 then sum(capex_usd) over last4 end as capex_ttm_usd,
    capex_usd / nullif(lag(capex_usd, 4) over by_company, 0) - 1 as capex_yoy_growth
from quarterly
window
    by_company as (partition by ticker order by quarter_end),
    last4 as (partition by ticker order by quarter_end rows between 3 preceding and current row);
