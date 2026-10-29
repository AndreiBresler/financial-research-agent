# Example outputs

## query_1_document_only

**Question:** What are Apple's top 3 risk factors mentioned in their latest 10-K, and what percentage of total revenue did they spend on R&D?

**Tools:** search_10k, calculator · **Result:** passed

Apple's first three risk factors in its fiscal 2025 10-K are economic conditions, political and trade disruptions, and competition. R&D was about 8.3% of total net sales in fiscal 2025 [C3bd255].

**Top 3 risk factors (the first three in Item 1A's order)**
1. **Global and regional economic conditions.** Apple's operations and performance depend significantly on them. Sales outside the U.S. are a majority of total net sales, and adverse conditions can materially hurt demand, suppliers and financial results [D25].
2. **Political events, trade disputes, geopolitical tensions, natural disasters and other business interruptions.** The filing says these can materially affect Apple, its suppliers and its channel partners [D26]. It highlights tariffs: new U.S. Tariffs were announced beginning in the second quarter of 2025, and several countries have threatened or imposed reciprocal tariffs [D32]. It also notes a significant majority of manufacturing is outsourced, primarily in China mainland, India, Japan, South Korea, Taiwan and Vietnam [D27].
3. **Highly competitive markets with rapid technological change.** Apple says it may be unable to compete effectively. It must make significant investments in R&D that may not achieve expected returns [D38].

**R&D as a share of total net sales (fiscal 2025, in millions of dollars)**
- R&D expense was $34,550 million [D115].
- Total net sales were $416,161 million [D108].
- R&D divided by net sales is about 8.3% [C3bd255]. The filing's own table rounds this to 8% [D115].

### Assumptions
- "Top 3" means the first three risk factors in the order Item 1A lists them. The filing doesn't rank them by importance.
- "Total revenue" means total net sales.
- The 10-K lists the three risk factors above under "Macroeconomic and Industry Risks" [D25][D26][D38].

### Sources
- [C3bd255] 34550 / 416161 * 100 = 8.302075
- [D25] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 5
- [D26] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D32] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D27] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D38] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 7
- [D115] Form 10-K FY2025 › Part II › Item 7 › Operating Expenses, p. 24
- [D108] Form 10-K FY2025 › Part II › Item 7 › Products and Services Performance, p. 23

## query_2_hybrid

**Question:** How does Apple's gross margin compare to Microsoft's current gross margin, and what reasons does Apple cite in their 10-K for any margin pressure?

**Tools:** search_10k, web_search, calculator · **Result:** passed · **Citation warnings:** 8

> **Verification warning:** some claims could not be tied to a source.
> - Uncited: That comment comes from Microsoft's fiscal 2026 Q3 results page.
> - Uncited: Pricing pressure and competition.
> - Uncited: Supply shortages.
> - Uncited: Higher costs for components, outside manufacturing and content.
> - Uncited: Shifts in product, service, geographic, currency or channel mix.
> - …and 3 more

Apple's gross margin is about 20 percentage points below Microsoft's. Apple's was 46.9% in fiscal 2025 [D112][C8b384d]. Microsoft's was 67.2% in its latest quarter, the quarter ended June 2026 [W535a1c][C99fc3e]. That is a gap of 20.3 points [Ceb3ee5]. Apple's 10-K cites tariff costs, product mix, foreign exchange, component costs and other factors as sources of margin pressure [D113][D71].

### Apple (fiscal year ended Sept 27, 2025, $ millions)
- Total net sales were $416,161 [D108].
- Total gross margin was $195,201, or 46.9% of net sales [D111][D112][C8b384d].
- Products gross margin was $112,887, or 36.8%, down from 37.2% in 2024 [D111][D112].
- Services gross margin was $82,314, or 75.4%, up from 73.9% in 2024 [D111][D112].

### Microsoft (web data)
- Microsoft's quarter ended June 2026 had gross profit of $60,482 million on revenue of $90,007 million, a 67.2% gross margin [W535a1c].
- The same quarter's margin was down 1.4 percentage points from a year earlier [W698586].
- Microsoft's fiscal year ended June 2025 had a gross margin of 68.8%. That is closer in time to Apple's fiscal 2025, and it is 21.9 points above Apple's 46.9% [W7a8b6f][C9ff41b].
- Microsoft's gross margin percentage decreased because of continued investments in AI infrastructure and growing AI product usage, partly offset by efficiency gains [W114c97]. That comment comes from Microsoft's fiscal 2026 Q3 results page.

### Reasons Apple cites for margin pressure in the 10-K
- **Products margin percentage fell in 2025.** Apple attributes the decline primarily to a different mix of products and to tariff costs, partly offset by other favorable costs [D113].
- **Services costs.** The Services gross margin percentage rose, but Apple says a different mix of services was partly offset by higher costs [D113].
- **Tariffs.** New U.S. tariffs were announced beginning in the second quarter of 2025, and several countries have threatened or imposed retaliatory tariffs. Apple says tariffs can materially affect its supply chain, pricing and gross margin, and that the ultimate impact is uncertain [D103].
- **Forward-looking view.** Apple says that in general its gross margins will be subject to volatility and downward pressure [D113].
- **Risk factors.** The list of factors includes:
  - Pricing pressure and competition.
  - Supply shortages.
  - Higher costs for components, outside manufacturing and content.
  - Shifts in product, service, geographic, currency or channel mix.
  - Foreign exchange fluctuations.
  - Inflation.
  - New tariffs.
  - New products with lower margins [D71].
- **Foreign exchange.** Apple says a weaker foreign currency can hurt the U.S. dollar value of its sales and margins. A stronger foreign currency can raise component costs [D72].
- **Component supply.** Apple says it faces supply and pricing risk because it sources some components from single or limited suppliers [D43].

### Assumptions
- Apple's total gross margin percentage is total gross margin divided by total net sales.
- Microsoft's fiscal year ends in June, so its periods don't line up with Apple's September year-end. I used its latest quarter as "current" and its fiscal 2025 margin as the closest period to Apple's.

### Data gaps
- The Microsoft figures come from third-party aggregator pages, not Microsoft's own filings, so they are unverified.

### Sources
- [D112] Form 10-K FY2025 › Part II › Item 7 › Gross Margin, p. 24
- [C8b384d] 195201 / 416161 * 100 = 46.905164
- [W535a1c] MICROSOFT Gross Margin %: 67.20% — Near Median | GuruFocus, https://www.gurufocus.com/term/gross-margin/MSFT, retrieved 2026-10-29
- [C99fc3e] 60482 / 90007 * 100 = 67.196996
- [Ceb3ee5] 67.2 - 46.9 = 20.3
- [D113] Form 10-K FY2025 › Part II › Item 7 › Gross Margin, p. 24
- [D71] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 15
- [D108] Form 10-K FY2025 › Part II › Item 7 › Products and Services Performance, p. 23
- [D111] Form 10-K FY2025 › Part II › Item 7 › Gross Margin, p. 24
- [W698586] Microsoft Corporation (MSFT) Earnings & Analysis — stockrow, https://stockrow.com/MSFT/earnings, retrieved 2026-10-29
- [W7a8b6f] Gross Profit Margin For Microsoft Corporation (MSFT), https://finbox.com/NASDAQGS:MSFT/explorer/gp_margin, retrieved 2026-10-29
- [C9ff41b] 68.8 - 46.9 = 21.9
- [W114c97] FY26 Q3 - Performance - Investor Relations - Microsoft, https://www.microsoft.com/en-us/investor/earnings/fy-2026-q3/performance, retrieved 2026-10-29
- [D103] Form 10-K FY2025 › Part II › Item 7 › Tariffs and Other Measures, p. 22
- [D72] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, pp. 15–16
- [D43] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 8

## risk_factors_document_only

**Question:** What are Apple's risk factors?

**Tools:** search_10k · **Result:** passed

Apple's fiscal 2025 Form 10-K groups its risk factors into five categories: macroeconomic and industry, business, legal and regulatory, financial, and general. The list below covers only the risk factors I retrieved. Several others in the filing, including data-security breaches, competition and retail, were not retrieved. Market-risk figures from Item 7A follow the list. [D25][D41][D61][D71][D77][D128]

### Macroeconomic and industry risks
- **Economic conditions:** Sales outside the U.S. are a majority of net sales, and most supplier facilities are outside the U.S. Slow growth, inflation, tighter credit, higher interest rates and currency swings can reduce demand. [D25]
- **Geopolitical events and disasters:** Political events, trade disputes, conflict, terrorism, natural disasters, public health issues and industrial accidents can disrupt Apple, its suppliers and its channel partners. Many operations and suppliers are in locations prone to earthquakes and other natural disasters. [D26][D36]
- **Trade restrictions and tariffs:** Most manufacturing is done by outsourcing partners, primarily in China mainland, India, Japan, South Korea, Taiwan and Vietnam. [D27]
  - Tariffs and export or import controls can raise costs, limit availability of components and products, and force supply chain changes. [D28][D29]
  - New U.S. tariffs were announced beginning in the second quarter of 2025, and other countries have imposed or threatened reciprocal tariffs. A Section 232 investigation into semiconductors is also under way. [D32][D33]
  - The ultimate impact is uncertain. [D34]
- **Single or limited sources:** Apple relies on single or limited sources for many critical components, so a business interruption at one of them would worsen the consequences. Insurance may not cover all losses. [D37]

### Business risks
- **Product and service transitions:** Apple must keep introducing and transitioning products and services. New offerings may replace existing ones at lower revenue and margin. [D41]
- **Component supply:** Apple gets some components from single or limited sources, and shortages and price swings can occur. Its new products often use custom components available from only one source. [D43]
- **Defects and quality:** Hardware, software and service defects can lead to product liability claims, recalls and reputational harm. New technologies such as AI features can add safety risks. [D45]
- **Third-party intellectual property:** Apple licenses technology from third parties and may be alleged to infringe others' rights. Machine learning and AI add to this risk, for example through the use of copyrighted training materials. [D47]
- **IT failures and network disruptions:** Apple and its supply chain depend on complex IT systems. Failures from ransomware, other cyber incidents or other causes can disrupt online services, transactions and manufacturing. [D53]

### Legal and regulatory risks
- **Complex and changing laws:** Apple faces onerous and expensive compliance across many areas. These include antitrust, privacy, online safety, AI, trade and tax. [D61]
- **Regulatory scrutiny and antitrust:** The technology industry faces intense regulatory scrutiny. [D64]
  - In the U.S., Apple is subject to a court order barring it from charging any commission or fee on certain App Store purchases. [D64]
  - Apple faces U.S. civil antitrust suits alleging monopolization in smartphone markets, and investigations in Europe and elsewhere over App Store terms. [D66]
- **EU Digital Markets Act (DMA):** Apple has changed iOS, the App Store and Safari in the EU. The European Commission has challenged its compliance plan, and the DMA provides for significant fines. [D65]
- **Google licensing revenue:** Apple earns revenue from search licensing arrangements with Google. Google was found to have violated U.S. antitrust laws, and the court ordered remedies on September 2, 2025. Those remedies are subject to further proceedings and appeal. If the remedies the DOJ originally proposed were imposed, they could materially hurt this revenue. [D67]
- **Privacy and data protection:** Compliance with personal-data laws is costly, and noncompliance can bring penalties. Rules on minors' data and sensitive data (health, biometric, financial) and on online safety and age verification add to the burden. [D69][D70]

### Financial risks
- **Net sales and gross margin volatility:** Margins face downward pressure from pricing, competition, component costs, mix shifts, foreign exchange, tariffs and new lower-margin products. A significant portion of net sales comes from a single product category. [D71]
- **U.S. dollar and foreign exchange:** A weaker foreign currency reduces the dollar value of foreign sales and earnings. Hedging may not offset more than part of the adverse effects. [D72][D73]
- **Credit and investment portfolio:** The value and liquidity of Apple's cash and marketable securities can fluctuate substantially. [D74]
- **Taxes:** Tax rates and laws, including OECD global minimum tax proposals, can change. Apple is also subject to tax examinations. [D76]

### General risks
- **Stock price volatility:** The stock has been volatile. A failure to meet expectations on growth, profitability, dividends or buybacks could cause a significant decline. [D77]

### Market risk disclosures (Item 7A)
- **Interest rates:** A 100 basis point rise in rates would reduce the fair value of the investment portfolio by $2,416 million, versus $2,755 million in fiscal 2024. It would also raise annual term-debt interest expense by $129 million, versus $139 million in fiscal 2024. [D130]
- **Foreign exchange:** Apple is a net receiver of non-U.S. dollar currencies, so a stronger dollar hurts net sales and gross margins. The estimated maximum one-day loss on its currency derivatives, at 95% confidence, was $590 million at September 27, 2025, versus $538 million a year earlier. [D131]

### Assumptions
- I treated the filing's own category headings as the structure. I did not rank the risks by importance.

### Data gaps
- The retrieval returned only part of Item 1A. I did not retrieve the other business risks, such as competition, cybersecurity and data breaches, reliance on outsourcing partners and carriers, retail and talent. Nor did I retrieve the remaining general risks. Say if you want those covered.

### Sources
- [D25] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 5
- [D41] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 8
- [D61] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 13
- [D71] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 15
- [D77] Form 10-K FY2025 › Part I › Item 1A › General Risks, p. 17
- [D128] Form 10-K FY2025 › Part II › Item 7A, p. 27
- [D26] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D36] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D27] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D28] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D29] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D32] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D33] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D34] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D37] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, pp. 6–7
- [D43] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 8
- [D45] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 9
- [D47] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 9
- [D53] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 11
- [D64] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 14
- [D66] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 14
- [D65] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 14
- [D67] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 14
- [D69] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 15
- [D70] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 15
- [D72] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, pp. 15–16
- [D73] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 16
- [D74] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 16
- [D76] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 16
- [D130] Form 10-K FY2025 › Part II › Item 7A › Interest Rate Risk, p. 27
- [D131] Form 10-K FY2025 › Part II › Item 7A › Foreign Exchange Rate Risk, p. 27

## stock_price_web_only

**Question:** What's Apple's current stock price?

**Tools:** web_search · **Result:** passed · **Citation warnings:** 1

> **Verification warning:** some claims could not be tied to a source.
> - Uncited: Apple (AAPL) was trading at about $345–$348 per share in the latest web snapshots, which were retri…

Apple (AAPL) was trading at about $345–$348 per share in the latest web snapshots, which were retrieved around 2026-10-29. The sources don't agree exactly, because they were captured at different moments and some are delayed.

- One snapshot showed $347.59, down 0.22% on the day. It was labelled "Market closed," and the previous close was $348.34 [We49fad].
- Investing.com pages showed $347.10 and $347.73 [Waaa071][W970c10].
- Robinhood showed $345.66 as of 2026-10-28, within a day range of $343.53–$347.20 [W35893d].
- A different Kraken snapshot showed $339.34, up 0.83% on the day, with a previous close of $336.55. It looks older than the others [Wc45e96].
- The 52-week range was $243.42 to $351.73, and market capitalization was about $5.0T [W35893d][We49fad].

### Assumptions
- I treated the roughly $347 figures as the most recent close. Several sources agree on that level, and one is explicitly labelled "Market closed."

### Data gaps
- None of the pages gave an exact timestamp. For a trading decision, check a live quote from your broker.

### Sources
- [We49fad] Apple (AAPL) Stock price today - quote & chart, https://www.kraken.com/stocks/aapl, retrieved 2026-10-29
- [Waaa071] Apple Stock Price Today | NASDAQ: AAPL Live - Investing.com, https://www.investing.com/equities/apple-computer-inc?GL_Ad_ID=592783804277&GL_Campaign_ID=16886355002&ISP=1, retrieved 2026-10-29
- [W970c10] Apple Share Price Today | NASDAQ AAPL Stock - Investing.com AU, https://au.investing.com/equities/apple-computer-inc, retrieved 2026-10-29
- [W35893d] Buy or Sell Apple Stock - AAPL Stock Price Quote & News | Robinhood, https://robinhood.com/us/en/stocks/AAPL, retrieved 2026-10-29
- [Wc45e96] Apple (AAPL) Stock price today - quote & chart, https://www.kraken.com/stocks/aapl#:~:text=The Apple Inc.,previous closing price was $254.37., retrieved 2026-10-29

## pe_ratio_document_and_web

**Question:** How does Apple's P/E ratio compare to Microsoft?

**Tools:** web_search, search_10k, calculator · **Result:** passed

Apple trades at a higher trailing P/E than Microsoft: about 39.9x against 29.3x in late October 2026. That is roughly 10.6 points, or about 36%, higher [Wfc38f4][W289eed][Cfd6ca0][C79e335].

**Current trailing P/E (late October 2026 web data)**
- Apple's P/E is 39.86 as of Oct. 24, 2026. This uses a share price of $347.725 and trailing-twelve-month diluted EPS of $8.72 for the period ended June 2026 [Wfc38f4].
- Microsoft's trailing P/E is 29.25, with trailing EPS of 17.95 [W289eed].
- The gap is 10.61 P/E points, so Apple trades at about a 36.3% premium to Microsoft [Cfd6ca0][C79e335].
- A second source pair gives a similar result. It shows Apple at 39.3 on Oct. 26, 2026 and Microsoft at 29.14 on Oct. 23, 2026, a premium of about 34.9% [Wd0998d][W22c5db][C895b30].

**Context**
- Apple's P/E is near the top of its 10-year range of 12.19 to 42.11. It is 45% above its historical median of 27.53 [Wfc38f4].
- Microsoft's P/E fell to 22.22 at 6/30/2026 and has since recovered to 27.74 on Yahoo's "Current" figure [W9c54a6].

**Check against the 10-K**
- Apple's reported fiscal 2025 diluted EPS (year ended Sept. 27, 2025) was $7.46 [D136][D172].
- Dividing the $347.725 share price by that older EPS gives about 46.6x [C252058]. The 39.86 quoted P/E is lower because it uses the more recent trailing EPS of $8.72 [Wfc38f4].

### Assumptions
- I used each source's "trailing twelve months" P/E as the headline figure.
- I paired Apple's GuruFocus figure with Microsoft's Yahoo Finance figure. Quote dates differ by a few days across sources.

### Data gaps
- I did not find Microsoft's exact quote date on the Yahoo page. Trailing P/E values differ slightly by provider, from 29.14 to 29.25 for Microsoft.
- I did not verify Microsoft's EPS against its own filings.
- Trailing P/E does not reflect differences in growth, margins or fiscal year-ends. Apple's fiscal year ends in September and Microsoft's in June.

### Sources
- [Wfc38f4] AAPL PE Ratio (TTM): 39.86 — 45% Above Median | GuruFocus, https://www.gurufocus.com/term/pettm/AAPL, retrieved 2026-10-29
- [W289eed] Microsoft Corporation (MSFT) Stock Price, News, Quote & History - Yahoo Finance, https://finance.yahoo.com/quote/MSFT, retrieved 2026-10-29
- [Cfd6ca0] 39.86 - 29.25 = 10.61
- [C79e335] (39.86 / 29.25 - 1) * 100 = 36.273504
- [Wd0998d] AAPL - Apple PE ratio, current and historical analysis, https://fullratio.com/stocks/nasdaq-aapl/pe-ratio, retrieved 2026-10-29
- [W22c5db] Microsoft PE ratio, current and historical analysis, https://fullratio.com/stocks/nasdaq-msft/pe-ratio, retrieved 2026-10-29
- [C895b30] (39.3 / 29.14 - 1) * 100 = 34.866163
- [W9c54a6] Microsoft Corporation (MSFT) Valuation Measures & Financial Statistics, https://finance.yahoo.com/quote/MSFT/key-statistics, retrieved 2026-10-29
- [D136] Form 10-K FY2025 › Part II › Item 8 › CONSOLIDATED STATEMENTS OF OPERATIONS, p. 29
- [D172] Form 10-K FY2025 › Part II › Item 8 › Note 3 – Earnings Per Share, p. 36
- [C252058] 347.725 / 7.46 = 46.61193

## not_available

**Question:** What was Apple's iPhone revenue in Brazil in fiscal 2025?

**Tools:** search_10k, web_search · **Result:** passed · **Citation warnings:** 2

> **Verification warning:** some claims could not be tied to a source.
> - Uncited: Apple doesn't disclose iPhone revenue in Brazil for fiscal 2025. The 10-K breaks out net sales for …
> - Uncited: My web search found no credible third-party estimate of Apple's iPhone revenue in Brazil for fiscal…

Apple doesn't disclose iPhone revenue in Brazil for fiscal 2025. The 10-K breaks out net sales for only the U.S. and China, and reports iPhone sales only as a worldwide total. Brazil is not reported on its own in either place.

**What the filing does report (fiscal 2025, ended September 27, 2025, in millions of dollars)**
- **Worldwide iPhone net sales:** $209,586 million [D108].
- **Americas segment net sales:** $178,353 million [D105]. This segment covers both North and South America, so Brazil is included but not separated [D229].
- **Country breakout:** Only countries that individually made up 10% or more of net sales are shown. These are the U.S. at $151,790 million and China at $64,377 million. Everything else is grouped as "Other countries" at $199,994 million [D234].
- **Brazil:** It is not named as a separate figure anywhere in these disclosures [D234].
- **iPhone commentary:** The management discussion says Americas net sales rose mainly on higher iPhone and Services sales. It gives no dollar figure for iPhone in the Americas, and none for any country [D106].

**Outside estimates**
- My web search found no credible third-party estimate of Apple's iPhone revenue in Brazil for fiscal 2025.
- The only iPhone revenue figure it turned up was the worldwide total, which matches Apple's reported figure [W4fce40].

### Data gaps
- There is no Brazil-specific net sales figure, for iPhone or for all products, in the 10-K.
- I found no outside estimate of Brazil iPhone revenue. Any figure I gave would be a guess, so I haven't given one.

### Sources
- [D108] Form 10-K FY2025 › Part II › Item 7 › Products and Services Performance, p. 23
- [D105] Form 10-K FY2025 › Part II › Item 7 › Segment Operating Performance, p. 22
- [D229] Form 10-K FY2025 › Part II › Item 8 › Note 13 – Segment Information and Geographic Data, p. 47
- [D234] Form 10-K FY2025 › Part II › Item 8 › Note 13 – Segment Information and Geographic Data, p. 48
- [D106] Form 10-K FY2025 › Part II › Item 7 › Segment Operating Performance, p. 22
- [W4fce40] Apple Statistics (2026) - Business of Apps, https://www.businessofapps.com/data/apple-statistics, retrieved 2026-10-29