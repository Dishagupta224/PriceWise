function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function formatPercentValue(value) {
  const number = Number(value);
  if (Number.isNaN(number)) {
    return null;
  }
  return `${number.toFixed(2).replace(/\.00$/, "")}%`;
}

function simplifyGuardrailMessage(text) {
  let match = text.match(
    /Competitive gap of ([\d.]+)% is below the ([\d.]+)% threshold for safe upward repricing\.?/i,
  );
  if (match) {
    const [, currentGap, requiredGap] = match;
    return `Our price is already very close to the competitor, so there is not enough room to safely raise the price. We are ${formatPercentValue(currentGap)} below the competitor, and we need at least ${formatPercentValue(requiredGap)}.`;
  }

  match = text.match(
    /Competitive overpricing gap of (-?[\d.]+)% is below the ([\d.]+)% threshold for a strategic price drop\.?/i,
  );
  if (match) {
    const [, currentGap, requiredGap] = match;
    return `We are only slightly more expensive than the competitor, so a price cut was not justified. The price difference is ${formatPercentValue(Math.abs(Number(currentGap)))}, and we would need at least ${formatPercentValue(requiredGap)} to lower the price safely.`;
  }

  match = text.match(/Proposed (drop|increase) of ([\d.]+)% exceeds the ([\d.]+)% per-action safety cap\.?/i);
  if (match) {
    const [, direction, proposed, cap] = match;
    return `The suggested price ${direction} was too large to apply safely. It was ${formatPercentValue(proposed)}, but the limit is ${formatPercentValue(cap)}.`;
  }

  match = text.match(/Proposed price ([\d.]+) exceeds the safe competitor ceiling ([\d.]+),?/i);
  if (match) {
    const [, proposedPrice, ceiling] = match;
    return `The suggested new price would put us too high above the safe market range. The proposal was ${proposedPrice}, but the safe ceiling was ${ceiling}.`;
  }

  if (/Cannot justify a strategic price increase without competitor market position data\.?/i.test(text)) {
    return "There was not enough competitor pricing data to safely raise the price.";
  }

  if (/Cannot justify a strategic price drop without competitor market position data\.?/i.test(text)) {
    return "There was not enough competitor pricing data to safely lower the price.";
  }

  return null;
}

export function simplifyReasoningSentence(sentence) {
  const text = cleanText(sentence);
  if (!text) {
    return "";
  }

  let match = text.match(/Decision ([A-Z_]+) for product '([^']+)':?/i);
  if (match) {
    const [, decisionType, productName] = match;
    const action = {
      PRICE_HOLD: "kept the price unchanged",
      PRICE_DROP: "decided to lower the price",
      PRICE_INCREASE: "decided to raise the price",
      REORDER_ALERT: "flagged this product for replenishment",
    }[decisionType] || "reviewed pricing";
    return `The AI ${action} for '${productName}'.`;
  }

  match = text.match(/Competitor ([^.]*) moved from ([\d.]+) to ([\d.]+) \(([-\d.]+)% change\)\.?/i);
  if (match) {
    const [, competitor, fromPrice, toPrice, change] = match;
    return `${competitor} changed its price from ${fromPrice} to ${toPrice} (${change}).`;
  }

  match = text.match(/Our current price remains ([\d.]+)\.?/i);
  if (match) {
    return `We kept our price at ${match[1]}.`;
  }

  match = text.match(/Our current price was ([\d.]+)\.?/i);
  if (match) {
    return `Our price before this decision was ${match[1]}.`;
  }

  match = text.match(/Our new price is ([\d.]+)\.?/i);
  if (match) {
    return `The updated price is ${match[1]}.`;
  }

  match = text.match(/Our current price is ([\d.]+)\. Proposed new price is ([\d.]+)\.?/i);
  if (match) {
    const [, currentPrice, proposedPrice] = match;
    return `The AI considered moving the price from ${currentPrice} to ${proposedPrice}.`;
  }

  match = text.match(/Agent reasoning:\s*(.*)/i);
  if (match) {
    const simplifiedReason = simplifyGuardrailMessage(match[1]) || cleanText(match[1]);
    return simplifiedReason;
  }

  match = text.match(/Update rejected:\s*(.*)/i);
  if (match) {
    return simplifyGuardrailMessage(match[1]) || cleanText(match[1]);
  }

  match = text.match(/Source event id:\s*([a-f0-9-]+)/i);
  if (match) {
    return `Event reference: ${match[1]}.`;
  }

  if (/Runtime session inactive\./i.test(text)) {
    return "AI pricing was inactive at that moment, so no automatic action was taken.";
  }

  if (/OpenAI API key is not configured\./i.test(text)) {
    return "AI pricing was not configured, so the system kept the price unchanged.";
  }

  if (/Agent execution failed:/i.test(text)) {
    return "The AI could not complete this action automatically, so it needs review.";
  }

  return simplifyGuardrailMessage(text) || text;
}

export function simplifyReasoningText(reasoning) {
  return splitReasoning(reasoning).join(" ");
}

export function splitReasoning(reasoning) {
  return cleanText(reasoning)
    .split(/(?<=[.?!])\s+/)
    .map((step) => simplifyReasoningSentence(step))
    .filter(Boolean);
}

export function summarizeHumanInterventionReason(reasoning) {
  const steps = splitReasoning(reasoning);
  const preferredStep = steps.find((step) =>
    /not enough room|not enough competitor pricing data|too large to apply safely|inactive|needs review|not configured/i.test(step),
  );
  return preferredStep || steps[0] || "The AI could not apply this change automatically and it needs review.";
}
