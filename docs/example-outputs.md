# Example outputs

## query_1_document_only

**Question:** What are Apple's top 3 risk factors mentioned in their latest 10-K, and what percentage of total revenue did they spend on R&D?

**Tools:** search_10k, calculator · **Result:** passed

Apple spent about 8.3% of total net sales on R&D in fiscal 2025 (fiscal year ended September 27, 2025) [C3bd255]. The filing's first three risk factors cover macroeconomic conditions, geopolitical and business disruptions, and international trade and tariffs [D25][D26][D27].

**First three risk factors, in the order the filing lists them (Item 1A, "Macroeconomic and Industry Risks")**
1. **Global and regional economic conditions.** Sales outside the U.S. are a majority of net sales, and most supplier facilities are outside the U.S. [D25]
   - Slow growth, recession, inflation, higher interest rates and currency swings can reduce consumer spending and demand [D25].
   - These conditions can also hurt suppliers, manufacturers, carriers, channel partners and developers [D25].
2. **Political events, trade disputes, geopolitical tensions, conflict, natural disasters, public health issues, industrial accidents and other business interruptions.** These can materially harm Apple, its customers and its supply chain [D26].
   - Many Apple and supplier operations are in areas prone to earthquakes and other natural disasters [D36].
   - Apple relies on single or limited sources for many critical components, so an interruption at one source would make the damage worse [D37].
3. **International trade restrictions and tariffs.** This risk sits inside the second risk factor's discussion [D27].
   - A significant majority of manufacturing is done by outsourcing partners, mainly in China mainland, India, Japan, South Korea, Taiwan and Vietnam [D27].
   - New U.S. tariffs were announced beginning in the second quarter of 2025, and several countries have threatened or imposed retaliatory tariffs [D32].
   - Restrictions can raise costs, limit the availability of products and components, and force changes to suppliers or operations [D29][D30].

**R&D as a share of total net sales, fiscal 2025**
- Research and development expense was $34,550 million [D135].
- Total net sales were $416,161 million [D135].
- The share is 34,550 / 416,161 × 100 = 8.30% [C3bd255].

### Assumptions
- "Top 3" means the first three risk factors in the order the filing lists them. The filing doesn't rank risks by importance.
- The second risk factor in the filing is the broad one on political events, trade disputes and business interruptions [D26]. The trade and tariff text [D27] falls under that same heading. I split it out as a separate third item because it is a distinct theme. If you count by the filing's headings only, the third risk factor would be a different one that I didn't retrieve.
- "Total revenue" means total net sales, which is the revenue line on Apple's income statement.

### Sources
- [C3bd255] 34550 / 416161 * 100 = 8.302075
- [D25] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 5
- [D26] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D27] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D36] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D37] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, pp. 6–7
- [D32] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D29] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D30] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D135] Form 10-K FY2025 › Part II › Item 8 › CONSOLIDATED STATEMENTS OF OPERATIONS, p. 29

## query_2_hybrid

**Question:** How does Apple's gross margin compare to Microsoft's current gross margin, and what reasons does Apple cite in their 10-K for any margin pressure?

**Tools:** search_10k, web_search, calculator · **Result:** FAILED: verification flagged the answer

> **Verification warning:** some claims could not be tied to a source.
> - Uncited: The small difference is probably because my calculation uses revenue rounded to $331.8B.
> - Uncited: **Period mismatch:** The two fiscal years end about nine months apart, so the comparison isn't same…

Apple's fiscal 2025 gross margin was about 46.9%. Microsoft's most recent full fiscal year (ended June 2026) was about 68%, so Microsoft is roughly 21 percentage points higher. Apple's own filing says gross margins face "volatility and downward pressure" [D113].

### Gross margin comparison
- **Apple, fiscal 2025 (year ended Sept. 27, 2025):** Net sales were $416,161M and total gross margin was $195,201M [D135]. That works out to 46.9% [C8b384d], which matches the 46.9% Apple reports [D112].
  - Products gross margin was 36.8%, with $112,887M of gross margin [D112][D111].
  - Services gross margin was 75.4%, with $82,314M of gross margin [D112][D111].
- **Microsoft, fiscal 2026 (year ended June 30, 2026):** Revenue was $331.8B and gross margin was $225,465M [We7406b]. That is about 68.0% [C64409a]. A third-party site reports 67.9% for the trailing twelve months to June 2026 [W3f48a8].
  - The small difference is probably because my calculation uses revenue rounded to $331.8B.
- **Gap:** Microsoft's margin is about 21.0 percentage points above Apple's [Cb43558].
- **Period mismatch:** The two fiscal years end about nine months apart, so the comparison isn't same-period.

### Margin pressure reasons Apple cites in the 10-K
- **Fiscal 2025 results:**
  - The Products gross margin percentage fell from 37.2% to 36.8% [D112]. Apple attributes this mainly to a different mix of products and to tariff costs, partly offset by other favorable costs [D113].
  - Services gross margin percentage rose to 75.4% [D112]. Apple attributes this to a different mix of services, partly offset by higher costs [D113].
  - Total gross margin percentage still rose from 46.2% to 46.9% [D112].
- **Tariffs:**
  - New U.S. tariffs were announced beginning in the second quarter of fiscal 2025. They include additional tariffs on imports from China, India, Japan, South Korea, Taiwan, Vietnam and the EU, among others [D103].
  - Apple says tariffs can materially hurt pricing and gross margin. It also says the ultimate impact is uncertain [D103].
- **Risk-factor list:** Apple says gross margins are subject to volatility and downward pressure from a range of factors [D71]. These include:
  - global product pricing pressures;
  - increased competition;
  - supply shortages;
  - higher costs for components, outside manufacturing and content;
  - product quality and warranty costs;
  - shifts in product, service, geographic, currency or channel mix;
  - inflation;
  - new or increased tariffs;
  - new products with lower margins.
- **Foreign exchange:**
  - Apple says a stronger U.S. dollar hurts net sales and gross margins when expressed in dollars [D131].
  - Apple also says stronger foreign currencies can raise component costs [D72].
  - Hedging may offset only part of these effects [D73].

### Assumptions
- "Current" Microsoft gross margin means its latest reported full fiscal year (fiscal 2026, ended June 30, 2026). Its fourth-quarter figures are $60,482M gross margin on $90.0B revenue [We7406b].
- Apple's overall margin is calculated as total gross margin divided by total net sales.

### Data gaps
- I did not find Microsoft's reported gross margin percentage directly in its filings or press release. My figure is calculated from the press-release gross margin dollars and rounded revenue.
- The 10-K doesn't quantify how much each factor, such as tariffs, cost the gross margin.

### Sources
- [D113] Form 10-K FY2025 › Part II › Item 7 › Gross Margin, p. 24
- [D135] Form 10-K FY2025 › Part II › Item 8 › CONSOLIDATED STATEMENTS OF OPERATIONS, p. 29
- [C8b384d] 195201 / 416161 * 100 = 46.905164
- [D112] Form 10-K FY2025 › Part II › Item 7 › Gross Margin, p. 24
- [D111] Form 10-K FY2025 › Part II › Item 7 › Gross Margin, p. 24
- [We7406b] FY26 Q4 - Press Releases - Investor Relations - Microsoft, https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/press-release-webcast, retrieved 2026-10-29
- [C64409a] 225465 / 331800 * 100 = 67.95208
- [W3f48a8] MSFT Gross margin: 67.9% (FY2026) & 10-Year History — stockrow, https://stockrow.com/MSFT/metrics/gross-margin, retrieved 2026-10-29
- [Cb43558] 225465 / 331800 * 100 - 195201 / 416161 * 100 = 21.046915
- [D103] Form 10-K FY2025 › Part II › Item 7 › Tariffs and Other Measures, p. 22
- [D71] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 15
- [D131] Form 10-K FY2025 › Part II › Item 7A › Foreign Exchange Rate Risk, p. 27
- [D72] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, pp. 15–16
- [D73] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 16

## risk_factors_document_only

**Question:** What are Apple's risk factors?

**Tools:** search_10k, web_search · **Result:** FAILED: used web_search, which this question shouldn't need; verification flagged the answer

> **Verification warning:** some claims could not be tied to a source.
> - Uncited: This summary follows the filing's headings and covers the risks I retrieved. I did not retrieve eve…

Apple's fiscal 2025 10-K groups its risk factors into macroeconomic and industry, business, legal and regulatory, financial, and general risks. The main themes are tariffs and trade, concentrated supply chains, product and service execution, antitrust and regulatory pressure, margin and currency volatility, and IT or cybersecurity failures. [D25][D28][D42][D43][D64][D71][D53]

This summary follows the filing's headings and covers the risks I retrieved. I did not retrieve every risk factor.

## Macroeconomic and industry risks
- **Economic conditions:** More than half of Apple's net sales are outside the U.S., and most supplier facilities are outside the U.S. Slow growth, inflation, higher rates and currency swings can hurt demand and Apple's partners. [D25]
- **Trade and geopolitics:** Tariffs and export or import controls can raise costs, restrict components and rare earths, and force changes to suppliers or products. [D28][D29]
  - New U.S. tariffs began in the second quarter of 2025. They include additional tariffs on China, India, Japan, South Korea, Taiwan, Vietnam and the EU, and some countries have threatened or imposed retaliation. [D32]
  - A Section 232 investigation covers semiconductors and downstream products that contain them. The ultimate impact is described as uncertain. [D33][D34]
- **Disasters and disruptions:** Operations and suppliers sit in areas prone to earthquakes and other natural disasters. They are also exposed to climate-related events, industrial accidents, public health crises and cyberattacks. [D36][D37]
- **Single-source dependence:** Many critical components come from single or limited sources, so one interruption can have an outsized effect. Insurance may not cover all losses. [D37]

## Business risks
- **Product cycles:** Apple must keep launching and transitioning products and services. New offerings can displace existing ones and carry lower revenue and margins. [D41]
- **Components:** Apple faces supply shortages and price increases, especially for custom components available from only one source. [D43]
- **Outsourced manufacturing:** A significant majority of manufacturing is done by partners in China mainland, India, Japan, South Korea, Taiwan and Vietnam. Final assembly of substantially all hardware is done by partners primarily in Asia, and this reduces Apple's direct control. [D42]
- **Quality and safety:** Hardware, software and services can have defects. New technologies such as AI features can add safety risks, including exposing users to harmful or inaccurate content. [D45]
- **IT failures:** Apple and its supply chain depend on complex systems. Ransomware, other cybersecurity incidents and outages could disrupt services, transactions and manufacturing. [D53]

## Legal and regulatory risks
- **Complex global laws:** Apple faces onerous compliance costs across areas such as antitrust, privacy, AI, trade, tax and environmental rules. [D61]
- **Legal proceedings:** The number and size of claims have generally increased over time. Apple also faces many patent claims relating to its standards-enabled products. [D58]
- **Antitrust and platform rules:**
  - Apple faces U.S. civil antitrust suits alleging monopolization in smartphone markets, and investigations in Europe and elsewhere into App Store terms. [D66]
  - In the EU, Apple has changed iOS, the App Store and Safari to comply with the Digital Markets Act. The European Commission has challenged that compliance plan, and the Act provides for significant fines. [D65]
  - In the U.S., a court order currently bars Apple from charging a commission or fee on certain purchases. [D64]
- **Google search licensing:** Apple earns revenue from search licensing with Google. On September 2, 2025, the D.C. District Court ordered remedies in the Google antitrust case, and those remedies are subject to appeal. A reversal could lead to remedies that bar Google from offering Apple commercial terms for search distribution. That could materially hurt this revenue. [D67]
- **Privacy and online safety:** Apple has obligations around minors' data and sensitive data such as health and payment data. New age-verification and online-safety laws could require significant product changes. [D70]

## Financial risks
- **Margin pressure:** Net sales and gross margins face downward pressure from competition, component costs, mix shifts, currency, and tariffs and trade restrictions. A significant portion of net sales comes from a single product category. [D71]
- **Foreign exchange:** A weaker foreign currency reduces the U.S. dollar value of foreign sales, and hedges may offset only part of the effect. [D72][D73]
- **Investments and credit:** The value and liquidity of Apple's cash and marketable securities can fluctuate substantially. [D74]
- **Tax:** Apple faces changes in tax rates and legislation, including OECD global minimum tax proposals, and possible additional tax liabilities. [D76]
- **Stock price:** The stock has been volatile. If Apple misses market expectations on growth, profitability, dividends or buybacks, the price could fall significantly. [D77]

## Cybersecurity governance (Item 1C)
- The Head of Corporate Information Security has overall responsibility for managing material cybersecurity risks. This executive leads a dedicated team and coordinates with a Supplier Trust team that manages supplier-related risk. [D79]
- The Audit Committee oversees cybersecurity matters and regularly reviews them with management. Item 1C refers readers to Item 1A for the cybersecurity risks themselves. [D80]

## Developments after the filing
- A CNBC report on a February 2026 Supreme Court ruling says it found tariffs that were unilaterally imposed illegal, in a 6-3 decision. It says importers could be owed more than $175 billion in refunds. [Wb102df]
- The same report says Apple could see lower production costs and keep more of its margins. It also says Apple declined to comment on whether it would seek refunds. [Wb102df]
- The 10-K called the tariff impact uncertain and dependent on future measures. [D34] The ruling therefore changes one of Apple's stated risk factors, but it doesn't remove the risk. The report says the President did not commit to refunds and expects multi-year litigation. [Wb102df]

### Assumptions
- I grouped the risks under the filing's own headings and did not rank them by severity.

### Data gaps
- I did not retrieve the competition risk factor, the intellectual property and licensing risks, or the data-breach and privacy-incident risk factor in full.
- I also did not retrieve the risks on reliance on third-party developers and digital content, retail stores, and personnel.
- I did not verify the web report on the tariff ruling against a primary source. I also did not check other post-filing events, such as the status of the EU, Google and U.S. antitrust matters.

### Sources
- [D25] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 5
- [D28] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D42] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 8
- [D43] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 8
- [D64] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 14
- [D71] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 15
- [D53] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 11
- [D29] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D32] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D33] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D34] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D36] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D37] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, pp. 6–7
- [D41] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 8
- [D45] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 9
- [D61] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 13
- [D58] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 12
- [D66] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 14
- [D65] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 14
- [D67] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 14
- [D70] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 15
- [D72] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, pp. 15–16
- [D73] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 16
- [D74] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 16
- [D76] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 16
- [D77] Form 10-K FY2025 › Part I › Item 1A › General Risks, p. 17
- [D79] Form 10-K FY2025 › Part I › Item 1C, p. 17
- [D80] Form 10-K FY2025 › Part I › Item 1C, p. 17
- [Wb102df] How the Supreme Court's tariff decision affects Apple, https://www.cnbc.com/2026/02/20/supreme-court-tariff-decision-apple-trump-cook-iphone.html, retrieved 2026-10-29

## stock_price_web_only

**Question:** What's Apple's current stock price?

**Tools:** web_search · **Result:** passed

Apple (AAPL) was trading at about $345–348 per share in the most recent quotes I found, retrieved 2026-10-29. The quotes don't agree exactly, because the pages were captured at different times. [W35893d][W we49fad]

- Robinhood showed $345.66 as of 2026-10-28, with a day range of $343.53–$347.20. [W35893d]
- Kraken showed $347.59 with the market closed. The previous close was $348.34. [We49fad]
- Investing.com showed $347.10 on one page and $347.73 on its Australian page. [Waaa071][W970c10]
- Another Kraken snapshot showed $339.34, with a previous close of $336.55. This looks like a different, earlier capture. [Wc45e96]

Market capitalization was about $5.0T. [W35893d][Waaa071]

The 52-week range was a low of $243.42 and a high of $351.73. [W35893d]

### Assumptions
- I read "current" as the latest quotes from the retrieval date, 2026-10-29. None of these pages gives an exact timestamp, so I can't tell which quote is newest.

### Data gaps
- I couldn't confirm a single authoritative real-time price. Treat the figure as approximate and check a live brokerage or exchange feed for the exact quote.

### Sources
- [W35893d] Buy or Sell Apple Stock - AAPL Stock Price Quote & News | Robinhood, https://robinhood.com/us/en/stocks/AAPL, retrieved 2026-10-29
- [We49fad] Apple (AAPL) Stock price today - quote & chart, https://www.kraken.com/stocks/aapl, retrieved 2026-10-29
- [Waaa071] Apple Stock Price Today | NASDAQ: AAPL Live - Investing.com, https://www.investing.com/equities/apple-computer-inc?GL_Ad_ID=592783804277&GL_Campaign_ID=16886355002&ISP=1, retrieved 2026-10-29
- [W970c10] Apple Share Price Today | NASDAQ AAPL Stock - Investing.com AU, https://au.investing.com/equities/apple-computer-inc, retrieved 2026-10-29
- [Wc45e96] Apple (AAPL) Stock price today - quote & chart, https://www.kraken.com/stocks/aapl#:~:text=The Apple Inc.,previous closing price was $254.37., retrieved 2026-10-29

## pe_ratio_document_and_web

**Question:** How does Apple's P/E ratio compare to Microsoft?

**Tools:** web_search, search_10k, calculator · **Result:** FAILED: verification flagged the answer

> **Verification warning:** some claims could not be tied to a source.
> - Uncited: This is higher than the quoted 39.86 because the data providers use newer trailing earnings of $8.7…
> - Uncited: Both Apple's and Microsoft's EPS have grown, but Microsoft's P/E has compressed while Apple's has e…
> - Uncited: Investors are paying more per dollar of Apple's earnings than Microsoft's. That points to either hi…

Apple trades at a higher trailing P/E than Microsoft. The gap is about 10.6 points, or a premium of roughly 36%. Apple's trailing P/E is about 39.9 and Microsoft's is about 29.3, using late-October 2026 data from different sites [Wfc38f4][W289eed][C79e335].

**Current multiples (trailing twelve months)**
- **Apple:** The P/E is 39.86 as of Oct. 24, 2026. That uses a share price of $347.725 and trailing EPS of $8.72 for the twelve months ended June 2026 [Wfc38f4]. A second source gives 39.3 on Oct. 26, 2026 [Wd0998d].
- **Microsoft:** Yahoo Finance shows a trailing P/E of 29.25 and trailing EPS of $17.95 for the fiscal year ended June 30, 2026 [W289eed]. A second source gives 29.14 at a price of $524.51 on Oct. 23, 2026 [W22c5db].
- **Gap:** The difference is 39.86 − 29.25 = 10.61 P/E points [Cfd6ca0]. That is a 36.3% premium for Apple [C79e335]. The second pair of sources (39.3 vs. 29.14) gives a premium of about 34.9% [C895b30].

**Cross-check against the 10-K**
- Apple's fiscal 2025 diluted EPS (year ended Sept. 27, 2025) was $7.46, on net income of $112,010 million [D172].
- Dividing the Oct. 24, 2026 price of $347.725 by that fiscal 2025 EPS gives about 46.6x [C252058]. This is higher than the quoted 39.86 because the data providers use newer trailing earnings of $8.72, which run through June 2026.

**What the gap suggests**
- Apple's multiple is close to the top of its own range. The source says it is 45% above its historical median of 27.53 and near its 10-year high of 42.11 [Wfc38f4].
- Microsoft's trailing P/E has fallen from 37.97 at 9/30/2025 to 27.74 in Yahoo's "current" column [W9c54a6]. Its forward P/E is lower still, at 25.13 in that table [W9c54a6].
- Both Apple's and Microsoft's EPS have grown, but Microsoft's P/E has compressed while Apple's has expanded.
- Investors are paying more per dollar of Apple's earnings than Microsoft's. That points to either higher growth or lower perceived risk in Apple's earnings, or to enthusiasm that has pushed the price ahead of earnings.

### Assumptions
- "Current" means the late-October 2026 snapshots the sources show. The Apple and Microsoft figures come from different sites and dates, so the comparison is approximate.
- Microsoft's fiscal year ends in June and Apple's in September, so their trailing periods are not perfectly aligned.
- My reading of what the gap implies about growth and market expectations is interpretation. The sources don't state it.

### Data gaps
- I did not find a single source that gives both companies' P/E on the same date and methodology.
- I did not pull Microsoft's 10-K, so I could not cross-check its EPS against filings.
- I did not find Apple's forward P/E or growth estimates, so the forward comparison is one-sided.

### Sources
- [Wfc38f4] AAPL PE Ratio (TTM): 39.86 — 45% Above Median | GuruFocus, https://www.gurufocus.com/term/pettm/AAPL, retrieved 2026-10-29
- [W289eed] Microsoft Corporation (MSFT) Stock Price, News, Quote & History - Yahoo Finance, https://finance.yahoo.com/quote/MSFT, retrieved 2026-10-29
- [C79e335] (39.86 / 29.25 - 1) * 100 = 36.273504
- [Wd0998d] AAPL - Apple PE ratio, current and historical analysis, https://fullratio.com/stocks/nasdaq-aapl/pe-ratio, retrieved 2026-10-29
- [W22c5db] Microsoft PE ratio, current and historical analysis, https://fullratio.com/stocks/nasdaq-msft/pe-ratio, retrieved 2026-10-29
- [Cfd6ca0] 39.86 - 29.25 = 10.61
- [C895b30] (39.3 / 29.14 - 1) * 100 = 34.866163
- [D172] Form 10-K FY2025 › Part II › Item 8 › Note 3 – Earnings Per Share, p. 36
- [C252058] 347.725 / 7.46 = 46.61193
- [W9c54a6] Microsoft Corporation (MSFT) Valuation Measures & Financial Statistics, https://finance.yahoo.com/quote/MSFT/key-statistics, retrieved 2026-10-29

## not_available

**Question:** What was Apple's iPhone revenue in Brazil in fiscal 2025?

**Tools:** search_10k, web_search · **Result:** passed

Apple doesn't report iPhone revenue in Brazil for fiscal 2025, and the 10-K doesn't mention Brazil. A search of the filing for "Brazil" returned nothing relevant [D229][D234]. The filing gives only the figures below, and none of them isolates Brazil.

- **iPhone net sales, worldwide:** $209,586 million in fiscal 2025, up from $201,183 million in fiscal 2024 [D108].
- **Americas segment net sales:** $178,353 million in fiscal 2025. The segment "includes both North and South America", so Brazil is inside it and not shown separately [D105][D229].
- **Americas segment drivers:** net sales rose mainly on higher iPhone and Services sales. Weaker foreign currencies against the U.S. dollar had an unfavorable effect [D106].
- **Country-level disclosure:** Apple names only two countries. U.S. net sales were $151,790 million and China net sales were $64,377 million. The remaining $199,994 million is grouped as "Other countries" [D234].
- **iPhone by region:** the filing doesn't split iPhone sales by segment or country [D108][D169].

The web searches found only third-party worldwide figures, such as IDC's estimate of about 247.4 million iPhones shipped in 2025 [W4f1941]. They found no credible Brazil-specific iPhone revenue estimate for fiscal 2025.

### Data gaps
- Brazil iPhone revenue, and Brazil net sales of any kind, are not disclosed in the 10-K.
- I found no reliable external estimate of Apple's Brazil iPhone revenue for fiscal 2025.

### Sources
- [D229] Form 10-K FY2025 › Part II › Item 8 › Note 13 – Segment Information and Geographic Data, p. 47
- [D234] Form 10-K FY2025 › Part II › Item 8 › Note 13 – Segment Information and Geographic Data, p. 48
- [D108] Form 10-K FY2025 › Part II › Item 7 › Products and Services Performance, p. 23
- [D105] Form 10-K FY2025 › Part II › Item 7 › Segment Operating Performance, p. 22
- [D106] Form 10-K FY2025 › Part II › Item 7 › Segment Operating Performance, p. 22
- [D169] Form 10-K FY2025 › Part II › Item 8 › Note 2 – Revenue, p. 36
- [W4f1941] iPhone Statistics (2026): Users, Sales, and Market Share | Skillademia, https://www.skillademia.com/statistics/iphone-statistics, retrieved 2026-10-29