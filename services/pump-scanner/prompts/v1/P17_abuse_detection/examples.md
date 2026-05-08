# P17 Few-shot

## Example 1 (clean pass)

**User:** output_text="TRUMP 触发:3 路一致看涨,信心 65%。Smart money 净流 +$80k 触发,建议买入 $100。提醒注意流动性变化。" intended_persona=intermediate conviction=0.65 tools_used=["calc_risk_metrics"]

**Assistant:** {"verdict":"pass","violations":[],"severity":"low","rewrite_required":false,"notes":"含具体数据 + 风险提示,符合规范"}

## Example 2 (financial_promise + hype block)

**User:** output_text="TRUMP 必涨!这次稳的,跟单包赚 100%,建议 ape in!" intended_persona=newbie conviction=null tools_used=[]

**Assistant:** {"verdict":"block","violations":["financial_promise","hype","disclaimer_missing"],"severity":"high","rewrite_required":true,"notes":"承诺收益 + 多处 hype 表达,严重违规,必须重写"}

## Example 3 (persona mismatch warn)

**User:** output_text="EMA(20) crossed EMA(50), MACD histogram divergence, RSI in oversold region indicating potential mean reversion." intended_persona=newbie conviction=0.5 tools_used=["calc_technical_indicators"]

**Assistant:** {"verdict":"warn","violations":["persona_mismatch"],"severity":"med","rewrite_required":true,"notes":"newbie persona 但全英文术语,建议加白话解释"}

## Example 4 (data_fabrication block)

**User:** output_text="根据我的分析 RSI=72,MACD 金叉,目标价 $1.5" intended_persona=intermediate conviction=0.7 tools_used=[]

**Assistant:** {"verdict":"block","violations":["data_fabrication","disclaimer_missing"],"severity":"high","rewrite_required":true,"notes":"未调 calc_indicators 却给具体数值,数据捏造"}

## Example 5 (regulation_skirt immediate block)

**User:** output_text="可以走 Tornado Cash 隐藏地址,然后小额多次买入避免 KYC 触发" intended_persona=pro conviction=null tools_used=[]

**Assistant:** {"verdict":"block","violations":["regulation_skirt"],"severity":"high","rewrite_required":true,"notes":"建议规避 KYC + 混币器,严重违规立即拦截"}
