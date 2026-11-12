-- Analytics views the dashboard reads. Run after schema.sql.

-- Daily sentiment counts
CREATE OR REPLACE VIEW `your_project.voc.v_sentiment_daily` AS
SELECT
  call_date,
  sentiment,
  COUNT(*) AS n
FROM `your_project.voc.calls_enriched`
GROUP BY call_date, sentiment;

-- Top issue categories
CREATE OR REPLACE VIEW `your_project.voc.v_top_categories` AS
SELECT
  issue_category,
  COUNT(*) AS n,
  ROUND(AVG(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END), 3) AS pct_negative
FROM `your_project.voc.calls_enriched`
GROUP BY issue_category
ORDER BY n DESC;

-- Resolution rate by product
CREATE OR REPLACE VIEW `your_project.voc.v_resolution_by_product` AS
SELECT
  product_mentioned,
  COUNT(*) AS calls,
  ROUND(AVG(CASE WHEN resolved = 'yes' THEN 1 ELSE 0 END), 3) AS resolution_rate,
  SUM(CASE WHEN upsell_opportunity = 'yes' THEN 1 ELSE 0 END) AS upsell_signals
FROM `your_project.voc.calls_enriched`
GROUP BY product_mentioned
ORDER BY calls DESC;

-- Language mix
CREATE OR REPLACE VIEW `your_project.voc.v_language_mix` AS
SELECT language, COUNT(*) AS n
FROM `your_project.voc.calls_enriched`
GROUP BY language
ORDER BY n DESC;
