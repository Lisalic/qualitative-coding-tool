import React from "react";
import {
  formatPaidModelPricingLine,
  getAiModelByValue,
} from "../../lib/aiModelCatalog";

export default function PaidModelPricingNotice({ modelValue }) {
  const model = getAiModelByValue(modelValue);
  if (!model?.paid) return null;

  return (
    <p className="paid-model-pricing-notice">{formatPaidModelPricingLine(model)}</p>
  );
}
