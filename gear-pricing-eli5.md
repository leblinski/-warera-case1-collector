**How equipment prices are worked out — and what just changed**

Every piece of gear has a "roll": its exact stats, e.g. attack 280 / crit 47. Each roll gets its own price.

**Before**
We took every sale of that exact roll inside a fixed window and used the middle price. Simple, and fine for rolls that sell all day. Two problems:
• a roll that sold once had that single sale as its "value"
• a roll that never sold had no price at all

**Now**
1. **Rolls learn from their neighbours.** We fit a price-per-attack-point line for each crit level separately — because a point of attack is worth about 0.8 gold at crit 41 and about 4.4 gold at crit 50. Same item, completely different maths, so they can't share one line.
2. **We blend by confidence.** Plenty of its own sales → it keeps its own price. One sale → mostly the line. Never sold → the line. No roll is left blank any more.
3. **Each item picks its own window.** Not one setting for everything. Every item tries 1, 2, 3, 7, 14, 30 and 60 days, scores each against days it was not allowed to see, and keeps the winner. Gloves want 1 day. Chests want 14. Jets want 60. It re-checks every run, so if the market shifts, the window moves on its own — nobody edits anything.
4. **Old money is converted to today.** A 60-day window is lifted onto today's price level instead of quoting two-month-old prices.

**Does it actually work?**
Measured the honest way — learn from older days, then predict a day it has never seen:
• Jets: all 800 rolls priced, 4.8% average error
• Tanks 2.4% · Snipers 2.2% · Knives 4.1%
Each item publishes its window, its blend strength and its measured error, so you can see exactly how much to trust any number.

**Also new:** 70 days of dated history per item — where a price has been, not just where it is.
