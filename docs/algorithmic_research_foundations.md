# Algorithmic Foundations for DV360 Custom Bidding

This document outlines four foundational academic papers across automated bidding, Bayesian shrinkage, ad viewability prediction, and counterfactual auction evaluation. It details their core theoretical insights and how each directly shapes the algorithm design of `dv360-bidkit` and `dv360-bidkit-pro`.

---

## 1. Google Research on Auto-Bidding & Valuation Mechanics

* **Paper:** *Auto-bidding and Auctions in Online Advertising: A Survey*
* **Authors:** Santiago R. Balseiro, Christian Kroer, Vahab Mirrokni, et al. (Google Research, 2024)
* **Venue / Reference:** *arXiv:2408.07685* / *ACM SIGecom Exchanges*

### Core Theoretical Insights
1. **The Separation of Valuation and Auction Pacing:**  
   In modern demand-side platforms (DSPs) like DV360, advertisers do not submit real-time monetary bids directly. Instead, advertisers supply a valuation function $v(x)$ parameterized by impression attributes $x$. The DSP's machine-learning auto-bidding agent maps this valuation to an auction bid via a dynamic dual-pacing multiplier $\alpha_t$:
   $$\text{bid}_t(x) = \alpha_t \cdot \mathbb{E}[v(x) \mid x]$$
   where $\alpha_t$ is updated continuously via feedback control to satisfy daily budget caps or target CPA/ROAS constraints.
2. **Scale-Invariance vs. Relative Density:**  
   Because the auto-bidding agent dynamically adjusts $\alpha_t$, multiplying all rule weights in a custom bidding script by an arbitrary constant (e.g. $10\times$) has no long-term effect on auction outcomes. Bidding behavior is governed strictly by the **relative spread and rank order** between publisher tiers and conversion conditions.
3. **Censoring vs. Valueless Events:**  
   In DSP loss formulations, excluding an impression from model training (`return None`) is treated as a censored observation, removing it from gradient calculations. Scoring an impression as `0.0` treats it as an observed valueless event, forcing the model to lower its bid toward the floor.

### Concrete Algorithmic Applications in BidKit
* **Relative Scale Normalization:** Score outputs are normalized to a consistent $[0.0, 1.0]$ or $[0.0, \text{score\_scale}]$ range before rule emission, avoiding runaway numerical variance that can destabilize Google's neural network gradient updates.
* **Preserving the Zero vs. Exclusion Boundary:** `dv360-bidkit` strictly enforces that `InventoryAction.EXCLUDE_FROM_TRAINING` emits `return None` rather than `return 0.0`.
* **Budget Limits Verification:** Compilers enforce upper bounds on output scores and character lengths to ensure the generated script satisfies DSP execution constraints.

---

## 2. Empirical Bayes Shrinkage for Sparse Publisher Inventories

* **Paper:** *Empirical Bayes and the Winner's Curse in A/B Testing & Targeted Bidding*
* **Foundational Roots:** Bradley Efron & Carl Morris (*Stein's Paradox in Statistics*); modern web-scale adaptations in *AdKDD* & Google Data Science
* **Reference:** Journal of the American Statistical Association / *arXiv:2103.11056*

### Core Theoretical Insights
1. **The Long-Tail Sparsity Problem:**  
   Publisher domains in programmatic advertising exhibit extreme volume skew. In historical DV360 Active View reports, long-tail publishers often report tiny sample sizes (e.g. 5 impressions with 5 viewable impressions). Naive observed viewability ($5/5 = 100\%$) is wildly noisy and overestimates true quality due to the Winner's Curse.
2. **Conjugate Bayesian Shrinkage:**  
   For binomial outcomes (e.g. viewable vs. non-viewable), the posterior mean under a conjugate Beta-Binomial / normal-normal model shrinks the observed rate toward a population baseline $\mu_{\text{prior}}$:
   $$\lambda_g = \frac{n_g}{n_g + M}, \quad \text{score}_g = \lambda_g \cdot \bar{y}_g + (1 - \lambda_g) \cdot \mu_{\text{prior}}$$
   where $n_g$ is the measurable sample size and $M = \sigma^2 / \tau^2$ is the shrinkage strength (the ratio of observational noise variance to cross-publisher variance).

### Concrete Algorithmic Applications in BidKit
* **Display Quality Proxy Calibration (`dv360_bidkit_pro.calibration`):**  
   Implements exact empirical Bayes shrinkage from customer Active View reports. Groups with low support ($n_g < \text{minimum\_support}$) smoothly back off to the customer's aggregate baseline without external third-party attention vendor fees.
* **Data-Driven Prior Estimation (Roadmap):**  
   Instead of setting $M$ manually, BidKit can use Marginal Maximum Likelihood (Type-II ML) to estimate cross-publisher dispersion $\hat{\tau}^2$ directly from customer data:
   $$\hat{\tau}^2 = \max\left(0, \frac{1}{K - 1}\sum_{g=1}^K (\bar{y}_g - \bar{y})^2 - \frac{\bar{y}(1 - \bar{y})}{K}\sum_{g=1}^K \frac{1}{n_g}\right)$$
   This automatically tunes shrinkage intensity based on how much true variance exists across the advertiser's media plan.

---

## 3. Ad Viewability & Attention Exposure Modeling

* **Paper:** *Viewability Prediction for Online Display Ads*
* **Authors:** Chong Wang, Achir Kalra, Cristian Borcea, Yi Chen
* **Venue / Reference:** *ACM CIKM '15* (Proceedings of the 24th ACM International Conference on Information and Knowledge Management)

### Core Theoretical Insights
1. **Regime Differences Across Devices and Formats:**  
   Wang et al. demonstrated that ad viewability is not governed by a single universal process. On desktop web, viewability is primarily determined by page layout, viewport coordinates, and ad fold position. On mobile, it is dominated by user scroll velocity and viewport dwell times. Connected TV (CTV) operates under a completely distinct application-based model where web domain and viewport geometry do not apply.
2. **Diminishing Marginal Utility of Continuous Exposure:**  
   Eye-tracking and dwell-time research reveals that user attention decays exponentially over time. Valuing ad exposure linearly against raw seconds on screen rewards accidental background tabs and slow-loading scripts. Quality valuation should follow a concave utility curve:
   $$U(t) = 1 - e^{-\gamma \cdot t}$$
   where $\gamma$ is the attention decay rate.

### Concrete Algorithmic Applications in BidKit
* **Disallowed CTV Domain Ingestion:**  
   `dv360-bidkit.linter` flags scripts evaluating web `domain` alongside Connected TV (`device_type == 4`), preventing invalid rule application since CTV apps report bundle IDs rather than website hostnames.
* **Separate Device Baselines:**  
   The calibration pipeline validates device categories and allows segmenting baselines across desktop vs. mobile web environments.
* **Non-Linear Exposure Transformation:**  
   Future continuous Active View profiles in Pro apply concave exponential saturation rather than linear dwell-time multipliers.

---

## 4. Counterfactual & Off-Policy Evaluation (OPE) in Ad Auctions

* **Paper:** *Breaking Determinism: Stochastic Modeling for Reliable Off-Policy Evaluation in Ad Auctions*
* **Authors:** Multiple industry and academic teams (e.g. Bottou et al., *JMLR*; recent work on *AuctionNet* and *arXiv:2306.07125*)
* **Venue / Reference:** *ACM KDD* / *Journal of Machine Learning Research (JMLR)*

### Core Theoretical Insights
1. **The Zero-Propensity Bottleneck in RTB:**  
   Unlike recommender systems (where randomized exploration ensures every item has a non-zero probability of being shown), real-time ad auctions are **deterministic winner-takes-all mechanisms**:
   $$\text{Win}(b, m) = \mathbb{I}(b > m)$$
   where $b$ is the submitted bid and $m$ is the clearing market price. When evaluating a new custom bidding script on historical logs, we only observe outcomes for impressions that were **already won** under the historical strategy. We have zero observational data for lost impressions.
2. **Sample Selection Bias & Winner's Curse:**  
   Simulating a new script on winning impressions alone introduces severe upward selection bias. A script that assigns high scores to expensive, highly contested inventory may look strong on historical wins while failing to account for the win-rate drop when clearing prices exceed bids.

### Concrete Algorithmic Applications in BidKit
* **Strict Data Sufficiency Contracts (`dv360_bidkit.evaluator.coverage`):**  
   BidKit strictly refuses to extrapolate missing signals or invent unobserved impressions from aggregated averages. If a metric cannot be evaluated exactly from the supplied sample, it is marked `UNAVAILABLE`.
* **Explicit Denominators in Pre-Flight Diagnostics:**  
   `EvaluationMetrics` explicitly separates:
   $$\text{positive\_rate\_all} = \frac{\text{positive impressions}}{\text{total supplied impressions}}$$
   from:
   $$\text{positive\_rate\_scored} = \frac{\text{positive impressions}}{\text{successfully scored impressions}}$$
   This ensures traders are not misled by excluding rows to artificially inflate their positive scoring rate.
* **Distributional Verification vs. Causal Lift:**  
   BidKit frames offline evaluation as **pre-flight syntax validation and training readiness verification** (e.g. Google S2 minimum thresholds) rather than advertising speculative campaign lift percentages.
