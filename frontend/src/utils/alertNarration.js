function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

export function alertTypeLabel(alertType) {
  const normalized = String(alertType || "").toUpperCase();
  if (normalized === "LOW_STOCK") {
    return "Low Stock";
  }
  if (normalized === "REORDER_ALERT") {
    return "Restock Recommended";
  }
  if (normalized === "HUMAN_INTERVENTION_REQUIRED") {
    return "Needs Review";
  }
  return normalized ? normalized.replace(/_/g, " ") : "Alert";
}

export function alertSummary(event, productNameFallback) {
  const data = event?.data || {};
  const productName = data.product_name || productNameFallback || (data.product_id ? `Product #${data.product_id}` : "This product");
  const alertType = String(data.alert_type || "").toUpperCase();
  const currentStock = Number(data.current_stock);
  const threshold = Number(data.threshold);

  if (alertType === "LOW_STOCK" && Number.isFinite(currentStock) && Number.isFinite(threshold)) {
    return `${productName} is low in stock. Only ${currentStock} units are left, below the alert level of ${threshold}.`;
  }

  if (alertType === "REORDER_ALERT") {
    return cleanText(
      data.reason || `${productName} may need a restock soon based on the AI review.`,
    );
  }

  if (alertType === "HUMAN_INTERVENTION_REQUIRED") {
    return cleanText(
      data.reason || `The AI could not complete the decision for ${productName}, so this item needs manual review.`,
    );
  }

  return cleanText(data.reason || `${productName} has a new alert.`);
}

export function alertActionText(event) {
  const data = event?.data || {};
  const alertType = String(data.alert_type || "").toUpperCase();
  if (data.recommended_action) {
    return cleanText(data.recommended_action);
  }
  if (alertType === "LOW_STOCK") {
    return "Restock this product soon.";
  }
  if (alertType === "REORDER_ALERT") {
    return "Review inventory and place a restock order if needed.";
  }
  if (alertType === "HUMAN_INTERVENTION_REQUIRED") {
    return "Review the AI decision and choose the next action manually.";
  }
  return "";
}
