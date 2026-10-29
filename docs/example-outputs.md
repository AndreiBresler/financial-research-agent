# Example outputs

Answers from the latest full `pytest -m e2e` run, the assignment's two queries first. Each answer is shown as the CLI renders it: any verification warning, the answer, then the Sources list written by code.

## query_1_document_only

**Question:** What are Apple's top 3 risk factors mentioned in their latest 10-K, and what percentage of total revenue did they spend on R&D?

**Tools:** search_10k, calculator · **Result:** passed

Apple's R&D spending was about 8.3% of total net sales in fiscal 2025 [C3bd255]. The first three risk factors the filing lists are macroeconomic conditions, political and geopolitical events, and competition.

**Top 3 risk factors (in filing order)**
1. **Global and regional economic conditions.** Apple's operations depend significantly on these conditions, and sales outside the U.S. are a majority of total net sales. A majority of supplier facilities are also outside the U.S. [D25]
2. **Political events, trade disputes and geopolitical tensions.** These can have a material adverse effect on Apple and its customers, employees, suppliers, contract manufacturers and channel partners. The list includes conflict, terrorism, natural disasters, public health issues and industrial accidents [D26].
3. **Competition and rapid technological change.** Apple's markets are highly competitive, with aggressive price competition and short product life cycles. Apple must make significant R&D investments that may not achieve expected returns [D38].

**R&D as a share of revenue**
- Fiscal 2025 research and development expense was $34,550 million [D135].
- Fiscal 2025 total net sales were $416,161 million [D135].
- The share is 34,550 / 416,161 × 100 = 8.3% [C3bd255]. The filing reports the same 8% for fiscal 2025 [D115].

### Assumptions
- "Top 3" means the first three risk factors in the order the filing lists them. I did not rank them by prominence or detail, so the list may differ from a ranking by emphasis.
- "Total revenue" is taken as total net sales, which is Apple's reported top-line figure.

### Data gaps
- I did not check whether the 10-K's risk factor summary (if any) ranks these risks differently from the order of the full risk factor text.

### Sources
- [C3bd255] 34550 / 416161 * 100 = 8.302075
- [D25] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 5
- [D26] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D38] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 7
- [D135] Form 10-K FY2025 › Part II › Item 8 › CONSOLIDATED STATEMENTS OF OPERATIONS, p. 29
- [D115] Form 10-K FY2025 › Part II › Item 7 › Operating Expenses, p. 24

## query_2_hybrid

**Question:** How does Apple's gross margin compare to Microsoft's current gross margin, and what reasons does Apple cite in their 10-K for any margin pressure?

**Tools:** search_10k, web_search, calculator · **Result:** passed · **Citation warnings:** 1

> **Verification warning:** some claims could not be tied to a source.
> - Uncited: **Apple's fiscal 2025 gross margin was 46.9%, well below Microsoft's most recent quarter at about 6…

**Apple's fiscal 2025 gross margin was 46.9%, well below Microsoft's most recent quarter at about 67.2%.** Apple's margin pressure came mainly from a shift in product mix and tariff costs, partly offset by favorable costs. The gap is about 20.3 percentage points against Microsoft's quarter, or about 21.0 points against Microsoft's full fiscal 2026 year.

**Apple (fiscal 2025, ended September 27, 2025)**
- Total gross margin was $195,201 million on net sales of $416,161 million [D135].
- The total gross margin percentage was 46.9%, up from 46.2% in fiscal 2024 [D112].
- Products gross margin percentage was 36.8%, down from 37.2%. Services was 75.4%, up from 73.9% [D112].
- Apple attributes the products margin percentage decline "primarily" to "a different mix of products and tariff costs, partially offset by other favorable costs." Products gross margin dollars rose on "favorable costs and a different mix of products, partially offset by tariff costs" [D113].
- Services margin percentage rose on "a different mix of services, partially offset by higher costs" [D113].
- Apple's tariff discussion says tariffs on products or their components can have a material adverse impact on "pricing and gross margin." It names new U.S. tariffs on imports from China, India, Japan, South Korea, Taiwan, Vietnam and the EU, and a Section 232 investigation into semiconductors [D103].
- Apple's risk factors list further drivers of gross margin volatility and downward pressure. These include industry-wide pricing pressure, competition, compressed product life cycles, supply shortages, component and content cost increases, product and service mix, foreign exchange, inflation, tariffs, and new products with lower margins [D71].
- Apple says it "believes, in general, gross margins will be subject to volatility and downward pressure" [D113].

**Microsoft (most recent reported period: fiscal Q4 2026, ended June 30, 2026)**
- Revenue was $90.0 billion and gross margin was $60,482 million [We7406b].
- Calculated from those figures, the quarterly gross margin percentage is 67.2% [C99fc3e].
- For the full fiscal 2026 year, gross margin was $225,465 million on revenue of $331,839 million, or 67.9% [C4fb787]. The annual revenue figure comes from a third-party data page [W535a1c], and the gross margin figure from Microsoft's release [We7406b].
- Microsoft's Microsoft Cloud gross margin percentage fell to 66% in fiscal Q3 2026. Microsoft attributed this to "continued investments in AI infrastructure and growing AI product usage" [W114c97].

**Comparison**
- Quarterly gap: 67.2% − 46.9% = 20.3 percentage points [C5168e7].
- Full-year gap: 67.9% − 46.9% = 21.0 percentage points [C4329bb].

### Assumptions
- Apple's figures are for its full fiscal year. The Microsoft figure I used is its most recent quarter, which is the closest like-for-like period available. I also show Microsoft's full fiscal 2026 year for comparison.
- Both gross margin percentages are calculated as gross margin divided by total revenue. Microsoft does not state a gross margin percentage in the excerpts I retrieved, so I calculated it from its reported figures.
- Apple and Microsoft have different business models and cost structures, so the gap reflects that, not a like-for-like efficiency comparison.

### Data gaps
- I did not retrieve Microsoft's own 10-K or its stated gross margin percentage. The Microsoft figures come from its press release and third-party data pages.
- I did not find an Apple quantification of how much tariffs reduced its gross margin in fiscal 2025.

### Sources
- [D135] Form 10-K FY2025 › Part II › Item 8 › CONSOLIDATED STATEMENTS OF OPERATIONS, p. 29
- [D112] Form 10-K FY2025 › Part II › Item 7 › Gross Margin, p. 24
- [D113] Form 10-K FY2025 › Part II › Item 7 › Gross Margin, p. 24
- [D103] Form 10-K FY2025 › Part II › Item 7 › Tariffs and Other Measures, p. 22
- [D71] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 15
- [We7406b] FY26 Q4 - Press Releases - Investor Relations - Microsoft, https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/press-release-webcast, retrieved 2026-10-29
- [C99fc3e] 60482 / 90007 * 100 = 67.196996
- [C4fb787] 225465 / 331839 * 100 = 67.944093
- [W535a1c] MICROSOFT Gross Margin %: 67.20% — Near Median | GuruFocus, https://www.gurufocus.com/term/gross-margin/MSFT, retrieved 2026-10-29
- [W114c97] FY26 Q3 - Performance - Investor Relations - Microsoft, https://www.microsoft.com/en-us/investor/earnings/fy-2026-q3/performance, retrieved 2026-10-29
- [C5168e7] 60482 / 90007 * 100 - 195201 / 416161 * 100 = 20.291832
- [C4329bb] 225465 / 331839 * 100 - 195201 / 416161 * 100 = 21.038929

## risk_factors_document_only

**Question:** What are Apple's risk factors?

**Tools:** search_10k · **Result:** passed

Apple's fiscal 2025 10-K lists risks in five groups: macroeconomic and industry, business operations, financial, legal and regulatory, and cybersecurity and data. The most prominent are weak global economic conditions, trade restrictions and tariffs, intense competition, supply concentration, and a growing body of antitrust and privacy regulation [D25][D28][D38][D43][D66][D61].

**Macroeconomic and industry risks**
- **Economic conditions:** Sales outside the U.S. are a majority of net sales, and most supplier facilities are outside the U.S. Slow growth, inflation, tighter credit, higher rates and currency moves can reduce demand and strain suppliers and channel partners [D25].
- **Trade and geopolitics:** Tariffs and other trade controls can disrupt the supply chain and raise prices. Restrictions can be announced with little notice, and a concentrated supply chain makes Apple exposed to geopolitical escalation [D28][D29][D31].
- **Political events and disasters:** Trade disputes, conflict, terrorism, natural disasters, public health events and industrial accidents can disrupt Apple and its partners [D26][D36][D37].
- **Competition and technology:** Markets are highly competitive, with price pressure, short product life cycles and rapid technological change. Apple's ability to compete depends on continued innovation and on protecting its intellectual property [D38].

**Business risks**
- **Product transitions:** Apple must manage frequent product launches and transitions, production ramps and inventory levels, and new products may lower margins [D41].
- **Outsourced manufacturing:** Most hardware is made by partners in China mainland, India, Japan, South Korea, Taiwan and Vietnam, and final assembly is largely in Asia. Apple relies on single-source suppliers for many components, and this reduces direct control [D42].
- **Components:** Shortages, commodity price swings and single-source custom parts can constrain supply and raise costs [D43].
- **Defects:** Hardware, software and service defects can lead to recalls, warranty costs, litigation and reputational harm. AI features are cited as adding to these risks [D44][D45].
- **IT systems:** Failures, network disruptions, ransomware and other cyber incidents could disrupt online services, transactions and manufacturing [D53].

**Financial risks**
- **Margins and sales volatility:** Net sales and gross margins face pressure from pricing, competition, component costs, mix, foreign exchange and tariffs. The filing also notes that a significant share of net sales comes from a single product category [D71].

**Legal and regulatory risks**
- **Complex and changing laws:** Apple is subject to rules on antitrust, privacy, online safety, age verification, AI, tax, trade and other areas. Compliance is costly, and violations could be material [D61].
- **Antitrust:** Apple faces U.S. civil antitrust suits over smartphone markets and investigations in Europe and elsewhere over App Store terms [D66].
- **EU Digital Markets Act:** Apple has changed iOS, the App Store and Safari in the EU to comply, and the Commission has challenged that compliance plan. The DMA provides for significant fines [D65].
- **U.S. App Store:** Apple is subject to a court order barring it from imposing commissions or fees on certain purchases [D64].
- **Google search revenue:** Apple's licensing revenue from Google search arrangements could be hurt if the remedies in the Google antitrust case are changed on appeal [D67].
- **Patents and other litigation:** Apple faces numerous patent claims tied to standards-enabled products, and claims may increase with AI integration [D58].
- **Privacy and data:** Apple faces growing personal-data laws, with extra obligations for minors' data and sensitive health, biometric and payment data [D69][D70].

**Cybersecurity and data**
- **Data breaches:** Losses of or unauthorized access to confidential information could cause reputational, financial and legal harm. Suppliers are also exposed to ransomware and other attacks [D54].

### Assumptions
- "Principal" risks means the order in which Item 1A presents them, as retrieved. Apple does not rank them by importance. The first risk in the filing is the global economic conditions risk [D25].
- The category groupings are my own, based on the headings Apple uses in Item 1A (Macroeconomic and Industry, Business, Financial, Legal and Regulatory).

### Data gaps
- **Changes versus prior filings:** I only retrieved the fiscal 2025 10-K. I could not compare its risk factors with fiscal 2024 or earlier filings, so I cannot say what is new or has changed in emphasis.
- **Partial coverage:** I did not retrieve the full text of every risk factor. The risks on key personnel, retail operations, tax, debt and foreign exchange were not checked separately.

### Sources
- [D25] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 5
- [D28] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D38] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 7
- [D43] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 8
- [D66] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 14
- [D61] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 13
- [D29] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D31] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D26] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D36] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 6
- [D37] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, pp. 6–7
- [D41] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 8
- [D42] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 8
- [D44] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 9
- [D45] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 9
- [D53] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 11
- [D71] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 15
- [D65] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 14
- [D64] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 14
- [D67] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 14
- [D58] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 12
- [D69] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 15
- [D70] Form 10-K FY2025 › Part I › Item 1A › Legal and Regulatory Compliance Risks, p. 15
- [D54] Form 10-K FY2025 › Part I › Item 1A › Business Risks, p. 11

## stock_price_web_only

**Question:** What's Apple's current stock price?

**Tools:** web_search · **Result:** passed · **Citation warnings:** 1

> **Verification warning:** some claims could not be tied to a source.
> - Uncited: Because these quotes come from different times and sources, treat them as approximate. Check a brok…

Apple's stock was about **$350.33** per share in the most recent quote I found, as of 2026-10-29 19:17 UTC, though sources disagree by a few dollars [Wdd2af1]. The quote was a regular-session price, up $6.51 (1.89%) on the day [Wdd2af1].

Other recent quotes in the same window:
- MarketWatch showed $349.33, against a previous close of $343.83 [Wb65440].
- Robinhood showed $345.66 as of 2026-10-28 [W35893d].

Because these quotes come from different times and sources, treat them as approximate. Check a brokerage or exchange feed for a live price.

### Assumptions
- "Current" means the latest quote in my search results, which were retrieved on 2026-10-29. I did not confirm the time of any quote beyond what each source printed.

### Data gaps
- I could not confirm a single authoritative real-time price, since the sources show different values and timestamps.
- The 10-K does not report share prices, so this answer relies only on web data.

### Sources
- [Wdd2af1] Apple Inc. (AAPL) Stock Price, News, Quote & History - Yahoo Finance, https://finance.yahoo.com/quote/AAPL, retrieved 2026-10-29
- [Wb65440] AAPL Stock Price | Apple Inc. Stock Quote (U.S.: Nasdaq) | MarketWatch, https://www.marketwatch.com/investing/stock/aapl, retrieved 2026-10-29
- [W35893d] Buy or Sell Apple Stock - AAPL Stock Price Quote & News | Robinhood, https://robinhood.com/us/en/stocks/AAPL, retrieved 2026-10-29

## pe_ratio_document_and_web

**Question:** How does Apple's P/E ratio compare to Microsoft?

**Tools:** search_10k, web_search, calculator · **Result:** passed

**Apple trades at a higher P/E than Microsoft on the basis you asked for.** Using Apple's fiscal 2025 diluted EPS and Microsoft's trailing twelve-month EPS, Apple's P/E is about 46.3x and Microsoft's is about 29.2x, a gap of roughly 17 turns [C56773e]. On a matched fiscal-year basis (both companies' fiscal 2025 diluted EPS), Microsoft is about 38.4x [Ca680fd], still below Apple's 46.3x.

**Apple**
- Fiscal 2025 diluted EPS was $7.46 on net income of $112,010 million [D136][D172].
- Share price was $345.66 as of 2026-10-28 [W35893d].
- P/E = 345.66 / 7.46 = 46.3x [Ceec3a6].
- Third-party trailing P/E figures are lower, around 34x to 40x, because they use a newer trailing EPS [W4b9a45][W01e33f].

**Microsoft**
- Share price was $524.347 as of 2026-10-29, with trailing twelve-month diluted EPS of $17.95 [W6dacb9].
- P/E = 524.347 / 17.95 = 29.2x [C638c7c]. The source itself reports 29.22 [W6dacb9].
- Microsoft's fiscal 2025 (year ended June 30, 2025) diluted EPS was $13.64 [W244017]. On that figure its P/E is 38.4x [Ca680fd].

### Assumptions
- P/E is share price divided by diluted EPS, as the question's method specifies. I used the filing's fiscal 2025 EPS for Apple, which is a trailing figure as of September 2025, against a current share price.
- The Microsoft trailing EPS of $17.95 comes from a third-party site. Its label says "ended Sep. 2026," but Microsoft's fiscal year ends in June. Its quarterly GAAP diluted EPS figures sum to about $17.96 for the four quarters through June 2026 [W67590c], so I treated $17.95 as the current trailing figure.
- The Apple price is one of several quotes for the same date. They ranged from $343.79 to $347.11 [W01e33f][W4b9a45][W35893d]. I used $345.66; the P/E moves by less than 0.5 turn across that range.
- The fiscal 2025 comparison is not like-for-like in time. Apple's fiscal 2025 ended September 2025, while Microsoft's ended June 2025. Its trailing figure is more current.

### Data gaps
- No primary-source Microsoft filing for the period after June 2025 is in the 10-K. The Microsoft trailing EPS and share prices come from web sources and could not be checked against Microsoft's own filings.
- The web sources give different trailing EPS values for Microsoft: $17.37 in one line of the same GuruFocus page and $17.95 in another [W6dacb9].
- The Apple price and P/E pulled from the web are dated late October 2026, so they are not tied to the filing's date.

### Sources
- [C56773e] 345.66 / 7.46 - 524.347 / 17.95 = 17.123589
- [Ca680fd] 524.347 / 13.64 = 38.441862
- [D136] Form 10-K FY2025 › Part II › Item 8 › CONSOLIDATED STATEMENTS OF OPERATIONS, p. 29
- [D172] Form 10-K FY2025 › Part II › Item 8 › Note 3 – Earnings Per Share, p. 36
- [W35893d] Buy or Sell Apple Stock - AAPL Stock Price Quote & News | Robinhood, https://robinhood.com/us/en/stocks/AAPL, retrieved 2026-10-29
- [Ceec3a6] 345.66 / 7.46 = 46.335121
- [W4b9a45] Apple (AAPL) Stock Price Today—Real Time Charts and Quotes | Gate, https://www.gate.com/tradfi/price/AAPL, retrieved 2026-10-29
- [W01e33f] Apple (AAPL) Stock Price Today, Pre-Market & After-Hours | CoinGlass, https://www.coinglass.com/stocks/AAPL, retrieved 2026-10-29
- [W6dacb9] MICROSOFT PE Ratio (TTM): 29.22 — 10% Below Median, https://www.gurufocus.com/term/pettm/MSFT, retrieved 2026-10-29
- [C638c7c] 524.347 / 17.95 = 29.211532
- [W244017] Microsoft 2025 Annual Report, https://www.microsoft.com/investor/reports/ar25/index.html, retrieved 2026-10-29
- [W67590c] Microsoft Earnings Explained: Dates and How to Read Them | BloFin, https://blofin.com/academy/education/msft/microsoft-earnings-explained, retrieved 2026-10-29

## not_available

**Question:** What was Apple's iPhone revenue in Brazil in fiscal 2025?

**Tools:** search_10k, web_search · **Result:** passed

Apple does not disclose iPhone revenue for Brazil in fiscal 2025. The filing reports iPhone net sales only on a worldwide basis, and Brazil is folded into the Americas segment. Total iPhone net sales were $209,586 million [D169], and Americas segment net sales were $178,353 million [D230]. The country-level table lists only the U.S., China and "other countries" [D234].

- Apple's reportable segments include Americas, which "includes both North and South America" [D229]. Brazil therefore falls inside the Americas segment.
- Net sales by product category (iPhone, Mac, iPad, Wearables, Home and Accessories, Services) are reported for the company as a whole, not by country [D169].
- Net sales for individual countries are disclosed only for countries that individually account for 10% or more of total net sales, and the table shows U.S., China and an aggregate "Other countries" line [D234]. Brazil is not shown separately.
- I found no published estimate of Brazil-specific iPhone revenue for fiscal 2025. A Statista page gives Apple's mobile device market share in Brazil for 2010–2025, but it is a market-share measure, not a revenue figure, and the 2025 value is not shown in the retrieved text [W579aad].

### Assumptions
- "iPhone revenue in Brazil" refers to iPhone net sales attributed to Brazil. Apple's segment and country tables do not provide that figure.
- Fiscal 2025 is the year ended September 27, 2025.

### Data gaps
- Brazil-specific iPhone net sales are not disclosed in the 10-K, and I could not find a reliable third-party estimate of them.
- Apple's iPhone net sales for the Americas segment as a whole are not disclosed either, so no Brazil share of iPhone revenue can be derived.

### Sources
- [D169] Form 10-K FY2025 › Part II › Item 8 › Note 2 – Revenue, p. 36
- [D230] Form 10-K FY2025 › Part II › Item 8 › Note 13 – Segment Information and Geographic Data, p. 47
- [D234] Form 10-K FY2025 › Part II › Item 8 › Note 13 – Segment Information and Geographic Data, p. 48
- [D229] Form 10-K FY2025 › Part II › Item 8 › Note 13 – Segment Information and Geographic Data, p. 47
- [W579aad] Brazil: Apple mobile device market share 2025 | Statista, https://www.statista.com/statistics/1418706/apple-mobile-device-market-share-brazil, retrieved 2026-10-29