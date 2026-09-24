-- validation checks. each query returns the offending rows, so an empty result is a pass.
-- build.py runs every statement separated by a line of dashes and fails if any return rows.

-- check: one row per company and fiscal quarter
select ticker, fiscal_year, fiscal_quarter, count(*) as n
from gold_quarterly_capex
group by ticker, fiscal_year, fiscal_quarter
having count(*) > 1;
-- ----
-- check: every quarter since 2018 has a value (a gap means a missing or mis-tagged filing)
select ticker, fiscal_year, fiscal_quarter, quarter_end
from gold_quarterly_capex
where capex_usd is null and quarter_end >= date '2018-01-01';
-- ----
-- check: capex is cash out the door, a negative quarter means the ytd math went wrong
select ticker, fiscal_year, fiscal_quarter, capex_usd
from gold_quarterly_capex
where capex_usd < 0;
-- ----
-- check: no skipped quarters, consecutive quarter ends sit roughly 3 months apart
select ticker, quarter_end, prev_end
from (
    select ticker, quarter_end, lag(quarter_end) over (partition by ticker order by quarter_end) as prev_end
    from gold_quarterly_capex
    where quarter_end >= date '2018-01-01'
) t
where prev_end is not null and quarter_end > cast(prev_end + interval 100 day as date);
-- ----
-- check: derived quarters agree with standalone 3 month values where a company reports them
-- (amazon's 10-Qs carry a three months ended column the ytd math never looks at)
select g.ticker, g.quarter_end, g.capex_usd as derived, b.value_usd as reported
from gold_quarterly_capex g
join (
    select ticker, end_date, value_usd,
           row_number() over (partition by ticker, end_date order by filed desc) as rn
    from bronze_capex_facts
    where duration_days between 84 and 98 and form like '10-Q%' and fiscal_period <> 'Q1'
) b on b.ticker = g.ticker and b.end_date = g.quarter_end and b.rn = 1
where abs(g.capex_usd - b.value_usd) > 0.01 * b.value_usd;
-- ----
-- check: freshness, every company has a quarter that ended in the last ~5 months
select ticker, max(quarter_end) as latest
from gold_quarterly_capex
group by ticker
having max(quarter_end) < cast(current_date - interval 150 day as date);
