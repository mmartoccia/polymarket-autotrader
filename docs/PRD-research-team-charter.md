# PRD: Elite Research Team Charter & Task Definition
**Product Requirements Document**

---

## Document Information

- **Project:** Polymarket AutoTrader System Evaluation
- **Version:** 1.0.0
- **Date:** 2026-01-16
- **Status:** DRAFT - Task Definition Phase
- **Owner:** Lead Researcher (Binary Trading Systems & Gambling Philosophy Expert)

---

## Executive Summary

This PRD establishes the framework for systematically defining research tasks for each member of the elite evaluation team. Each researcher will receive a tailored PRD specifying their objectives, methodologies, deliverables, and success criteria.

**Goal:** Transform general expertise into actionable research plans that collectively evaluate the Polymarket AutoTrader's performance, risk profile, and optimization opportunities.

---

## Meta-Objective

**Create 8 Individual Researcher PRDs** that collectively answer:

1. **Is the system profitable?** (Expected value > 0 after fees)
2. **Is the system sustainable?** (Survives drawdowns, adapts to regime changes)
3. **Is the system optimizable?** (Clear path to 60-65% win rate target)
4. **Is the system safe?** (Risk controls prevent ruin)
5. **Is the system trustworthy?** (No hidden bugs, data leakage, or false claims)

---

## System Context Summary

### What We're Evaluating

**Polymarket AutoTrader v12.1** - Automated binary options trading bot

**Key Characteristics:**
- **Market:** 15-minute Up/Down crypto predictions (BTC/ETH/SOL/XRP)
- **Strategy:** Multi-agent consensus system (4-11 agents voting)
- **Risk:** Tiered position sizing, 30% drawdown halt, correlation limits
- **Performance:** 56-60% win rate claimed, $200.97 current balance (33% drawdown from $300 peak)
- **Fee Impact:** 3-6% round-trip fees depending on entry price
- **Production:** Trading live on VPS 24/7 since Jan 2026

**Critical Incidents:**
- Jan 14: Lost 95% ($157 → $7) due to trend filter bias (96.5% UP trades in downtrend)
- Jan 15: Recovered +$194 profit ($7 → $201)
- Jan 16: Discovered state tracking desync ($186 error in peak_balance)

**Current Focus:**
- 4-week optimization roadmap to improve win rate from 56% → 60-65%
- 27 shadow strategies running in parallel for A/B testing
- Per-agent performance tracking to identify underperformers

---

## Research Team Structure

### Team Composition

1. **Dr. Sarah Chen** - Probabilistic Mathematician
2. **James "Jimmy the Greek" Martinez** - Market Microstructure Specialist
3. **Dr. Amara Johnson** - Behavioral Finance Expert
4. **Victor "Vic" Ramanujan** - Quantitative Strategist
5. **Colonel Rita "The Guardian" Stevens** - Risk Management Architect
6. **Dmitri "The Hammer" Volkov** - System Reliability Engineer
7. **Prof. Eleanor Nash** - Game Theory Economist
8. **Dr. Kenji Nakamoto** - Data Forensics Specialist

---

## PRD Creation Process

### Phase 1: Individual Researcher PRD Drafting

For each researcher, we will create a comprehensive PRD containing:

#### A. Research Scope Definition
- **Primary Research Question:** What specific hypothesis are they testing?
- **Secondary Questions:** Supporting inquiries
- **Out of Scope:** What they are NOT responsible for (to prevent overlap)

#### B. Methodological Framework
- **Data Sources:** What system logs, code files, databases they'll analyze
- **Tools & Techniques:** Statistical methods, code auditing approaches, simulation tools
- **Access Requirements:** SSH access, API keys, database credentials

#### C. Deliverables Specification
- **Required Outputs:** Reports, data visualizations, code fixes
- **Format Standards:** Markdown reports, Jupyter notebooks, CSV exports
- **Delivery Timeline:** Milestones and deadlines

#### D. Success Criteria
- **Quantitative Metrics:** Statistical significance thresholds, confidence intervals
- **Qualitative Standards:** Code quality, documentation completeness
- **Acceptance Criteria:** What constitutes "done"

#### E. Dependencies & Collaboration
- **Upstream Dependencies:** What they need from other researchers
- **Downstream Consumers:** Who relies on their findings
- **Collaboration Touchpoints:** Joint analysis sessions

#### F. Risk & Mitigation
- **Data Availability Risks:** What if logs are incomplete?
- **Technical Risks:** What if VPS access fails?
- **Mitigation Strategies:** Fallback plans

---

## Sequential PRD Development Plan

### Order of Execution

We'll develop PRDs in this order (optimized for dependency flow):

1. **Dr. Kenji Nakamoto** (Data Forensics) - FIRST
   - Validates data integrity before others analyze it
   - Identifies p-hacking, overfitting, survivorship bias
   - Output: Clean datasets + red flags for others to investigate

2. **Dmitri Volkov** (System Reliability) - SECOND
   - Audits state management, API reliability, persistence logic
   - Ensures live system is trustworthy for observations
   - Output: Bug reports + system health baseline

3. **Dr. Sarah Chen** (Probabilistic Math) - THIRD
   - Requires clean data from Kenji to calculate accurate statistics
   - Validates fee economics, breakeven calculations, Kelly sizing
   - Output: Mathematical ground truth for profitability

4. **James Martinez** (Market Microstructure) - FOURTH
   - Builds on Sarah's fee analysis to evaluate entry timing
   - Analyzes order book dynamics, liquidity, spread costs
   - Output: Optimal entry price ranges + timing strategies

5. **Victor Ramanujan** (Quantitative Strategy) - FIFTH
   - Depends on clean data + reliable system metrics
   - Evaluates agent voting, ML model, shadow trading results
   - Output: Agent performance rankings + strategy recommendations

6. **Dr. Amara Johnson** (Behavioral Finance) - SIXTH
   - Analyzes human psychology embedded in risk controls
   - Evaluates recovery mode logic, loss aversion patterns
   - Output: Behavioral bias audit + psychological risk assessment

7. **Colonel Rita Stevens** (Risk Management) - SEVENTH
   - Synthesizes findings from Sarah, Dmitri, Victor
   - Stress tests drawdown protections, correlation limits
   - Output: Risk control validation + recommendations

8. **Prof. Eleanor Nash** (Game Theory) - EIGHTH (FINAL)
   - Integrates all findings into holistic strategic assessment
   - Evaluates multi-epoch dynamics, contrarian vs momentum equilibria
   - Output: Strategic roadmap + game-theoretic recommendations

---

## PRD Template Structure

Each individual researcher PRD will follow this structure:

```markdown
# PRD: [Researcher Name] - [Research Domain]

## 1. Executive Summary
- Research objective in 2-3 sentences
- Key deliverables
- Timeline

## 2. Research Questions
### Primary Question
- Core hypothesis to test

### Secondary Questions
- Supporting inquiries (3-5 questions)

### Out of Scope
- What this researcher will NOT investigate

## 3. Methodology
### Data Sources
- Specific files, logs, databases, APIs

### Analysis Techniques
- Statistical methods
- Code review approaches
- Simulation frameworks

### Tools & Environment
- Python libraries
- SSH access requirements
- Compute resources

## 4. Deliverables
### Required Outputs
1. [Deliverable 1]
2. [Deliverable 2]
3. [Deliverable 3]

### Format Standards
- Report format (Markdown, Jupyter, etc.)
- Visualization requirements
- Code documentation standards

### Delivery Schedule
- Milestone 1: [Date]
- Milestone 2: [Date]
- Final Delivery: [Date]

## 5. Success Criteria
### Quantitative Metrics
- Statistical significance thresholds
- Confidence intervals
- Sample size requirements

### Qualitative Standards
- Code quality criteria
- Documentation completeness
- Reproducibility requirements

### Acceptance Criteria
- Definition of "done"
- Review process
- Sign-off requirements

## 6. Dependencies
### Upstream Dependencies
- What inputs are needed from other researchers?
- Blocking dependencies

### Downstream Consumers
- Who relies on this research?
- How will outputs be used?

### Collaboration Requirements
- Joint analysis sessions
- Data sharing protocols
- Communication cadence

## 7. Risk Assessment
### Data Availability Risks
- What if required data is missing?
- Mitigation: Fallback data sources

### Technical Risks
- System access failures
- Compute resource constraints
- Mitigation: Backup environments

### Analytical Risks
- Insufficient sample sizes
- Confounding variables
- Mitigation: Sensitivity analysis

## 8. Resources
### Access Requirements
- VPS SSH access
- Database credentials
- API keys

### Computational Resources
- Local development environment
- Cloud compute (if needed)
- Storage requirements

### Domain Expertise Support
- Subject matter experts to consult
- Literature review resources
- External validation sources

## 9. Appendix
### Reference Materials
- Relevant code files
- System documentation
- Academic papers

### Glossary
- Domain-specific terms
- Acronyms

### Change Log
- Version history
- Major revisions
```

---

## Deliverables from This PRD

### Immediate Outputs (This Document)
- [x] Team structure defined
- [x] Sequential PRD development order established
- [x] PRD template created
- [ ] Stakeholder approval received

### Subsequent Outputs (8 Individual PRDs)
1. [x] PRD: Dr. Kenji Nakamoto - Data Forensics (COMPLETE - docs/PRD-kenji-nakamoto-data-forensics.md)
2. [ ] PRD: Dmitri Volkov - System Reliability
3. [ ] PRD: Dr. Sarah Chen - Probabilistic Mathematics
4. [ ] PRD: James Martinez - Market Microstructure
5. [ ] PRD: Victor Ramanujan - Quantitative Strategy
6. [ ] PRD: Dr. Amara Johnson - Behavioral Finance
7. [ ] PRD: Colonel Rita Stevens - Risk Management
8. [ ] PRD: Prof. Eleanor Nash - Game Theory

---

## Timeline

### Week 1: PRD Development Phase
- **Days 1-2:** Draft PRDs for Researchers 1-3 (Data, System, Math)
- **Days 3-4:** Draft PRDs for Researchers 4-6 (Microstructure, Quant, Behavioral)
- **Days 5-6:** Draft PRDs for Researchers 7-8 (Risk, Game Theory)
- **Day 7:** Review, revisions, stakeholder approval

### Week 2-5: Research Execution Phase
- Researchers execute their PRDs in sequence
- Daily standups to share findings
- Weekly integration sessions

### Week 6: Final Report Phase
- Synthesize all findings
- Create unified recommendations
- Present to stakeholders

---

## Success Metrics for This Charter

This meta-PRD is successful if:

1. **Clarity:** Each researcher knows exactly what to do
2. **Coverage:** All critical system aspects are evaluated
3. **Efficiency:** No redundant work, minimal dependencies blocking progress
4. **Actionability:** Findings lead to clear optimization decisions
5. **Completeness:** All 8 PRDs delivered on schedule

---

## Approval & Sign-off

- [ ] **Lead Researcher:** Approved structure and sequence
- [ ] **System Owner:** Agreed to VPS access and data sharing
- [ ] **Stakeholders:** Acknowledged timeline and resource requirements

---

## Next Steps

1. **IMMEDIATE:** Begin drafting PRD #1 (Dr. Kenji Nakamoto - Data Forensics)
2. Review draft with Lead Researcher
3. Iterate until approval
4. Proceed sequentially through remaining 7 PRDs

---

## Appendix A: System File Map

Key files each researcher will need access to:

### Trading System Core
- `bot/momentum_bot_v12.py` - Main trading logic (1600+ lines)
- `config/agent_config.py` - Agent system configuration
- `state/trading_state.json` - Current balance, mode, performance

### Agent System
- `agents/tech_agent.py` - Technical/momentum signals
- `agents/sentiment_agent.py` - Contrarian signals
- `agents/regime_agent.py` - Market classification
- `agents/risk_agent.py` - Risk management
- `agents/gambler_agent.py` - Probability gating
- `agents/time_pattern_agent.py` - Historical patterns
- `agents/voting/vote_aggregator.py` - Consensus mechanism

### Shadow Trading System
- `simulation/orchestrator.py` - Multi-strategy coordinator
- `simulation/shadow_strategy.py` - Virtual trading engine
- `simulation/trade_journal.db` - SQLite trade log (27 strategies)
- `simulation/strategy_configs.py` - Strategy definitions

### Monitoring & Analytics
- `dashboard/live_dashboard.py` - Real-time monitoring
- `bot.log` - Trading activity log (on VPS)
- `state/timeframe_trades.json` - Historical trade data

### VPS Environment
- **SSH:** `root@216.238.85.11`
- **Bot Path:** `/opt/polymarket-autotrader/`
- **Service:** `systemctl status polymarket-bot`

---

## Appendix B: Research Questions Master List

### Performance Questions
- Is the 56-60% win rate statistically significant?
- What's the expected value per trade after fees?
- Can the system sustain profitability over 1000+ trades?

### Risk Questions
- What's the probability of hitting 30% drawdown in next 100 trades?
- Are position sizing tiers optimal vs Kelly Criterion?
- Can the system survive a 10-loss streak?

### Strategy Questions
- Which agents consistently add value?
- Should contrarian trading be permanently disabled?
- Are shadow strategy results statistically meaningful?

### System Questions
- Are there hidden bugs beyond peak_balance desync?
- Is state management fault-tolerant?
- Can the VPS handle 2s scan intervals reliably?

### Optimization Questions
- What's the fastest path to 60-65% win rate?
- Should ML model replace agent voting?
- Which shadow strategy should be promoted to production?

---

**END OF CHARTER PRD**

---

**READY TO BEGIN:** Awaiting approval to start drafting PRD #1 (Dr. Kenji Nakamoto - Data Forensics Specialist).

Shall we proceed? 🎯
