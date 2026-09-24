-- silver: one clean cumulative (fiscal year to date) capex value per company and period.
--
-- 1. keep only 10-K / 10-Q facts (and amendments), drop 8-K press release copies.
-- 2. keep only year to date facts: a Q1 filing's 3 month value, Q2's 6 month, Q3's 9 month,
--    and the 10-K's 12 month value. this drops amazon's trailing twelve month and standalone
--    three month columns, which would otherwise look like extra periods.
-- 3. reconcile renamed tags and restatements in one pass: for each company and period, keep
--    the value from the most recent filing, whichever tag it used. amazon restated FY2016 from
--    6.74B (old tag) to 7.80B (new tag), so the newest filing has to win, not the oldest tag.

create or replace table silver_capex_facts as
with ytd_facts as (
    select
        *,
        case fiscal_period when 'Q1' then 1 when 'Q2' then 2 when 'Q3' then 3 when 'FY' then 4 end
            as fiscal_quarter
    from bronze_capex_facts
    where form in ('10-K', '10-K/A', '10-Q', '10-Q/A')
),

matched as (
    -- 91 days per quarter, with slack for 52/53 week fiscal years (nvidia)
    select *
    from ytd_facts
    where abs(duration_days - 91 * fiscal_quarter) <= 14
),

ranked as (
    select
        *,
        row_number() over (
            partition by ticker, start_date, end_date
            order by filed desc, accession desc
        ) as rn
    from matched
)

select
    ticker,
    cik,
    concept as source_concept,
    start_date as fiscal_year_start,
    end_date,
    fiscal_quarter,
    -- a fiscal year is named for the calendar year it ends in. only a year that starts on
    -- jan 1 ends in the same calendar year (msft, orcl, nvda all end in the next one).
    year(start_date) + case when month(start_date) = 1 and day(start_date) = 1 then 0 else 1 end
        as fiscal_year,
    value_usd as ytd_capex_usd,
    form,
    filed,
    accession
from ranked
where rn = 1;
